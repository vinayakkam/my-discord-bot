"""
space_tweets.py — OLIT Discord Bot Module
==========================================
Fetches SpaceX, Blue Origin, NASA, Rocket Lab & ULA tweets via free RSS feeds.
All commands use the ! prefix.

COMMANDS:
    !spacenow       — fetch & post ALL tweets from today
    !spacediag      — test every RSS source, shows what works
    !spacestatus    — show current config
    !spacetoggle    — enable / disable feed
    !spacedebug     — dump raw RSS fields to diagnose image parsing

REQUIREMENTS:
    pip install "discord.py>=2.3" aiohttp feedparser python-dotenv
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import pathlib
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

import aiohttp
import discord
import feedparser
from discord.ext import commands, tasks
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger("olit.space_tweets")

# ─────────────────────────────────────────────
#  Settings
# ─────────────────────────────────────────────

POLL_INTERVAL_MINUTES: int = 8
MAX_TWEET_AGE_HOURS:   int = 24

# ─────────────────────────────────────────────────────────────────────────────
#  ✏️  RSS.APP FEEDS  — paste your URLs here
#  Get them free at https://rss.app → New Feed → Twitter/X Profile
# ─────────────────────────────────────────────────────────────────────────────

RSS_APP_FEEDS: dict[str, str] = {
    "SpaceX":     "https://nitter.net/{username}/rss",
    "BlueOrigin": "https://nitter.net/{username}/rss",
    "NASA":       "https://nitter.net/{username}/rss",
    "RocketLab":  "https://nitter.net/{username}/rss",
    "ULA":        "https://nitter.net/{username}/rss",
}

# Updated fallback pool order based on latest diagnostics
NITTER_MIRRORS: list[str] = [
    "https://nitter.net/{username}/rss",
    "https://xcancel.com/{username}/rss",
]

# ─────────────────────────────────────────────
#  Accounts
# ─────────────────────────────────────────────

ACCOUNTS: dict[str, dict] = {
    "SpaceX": {
        "username":          "SpaceX",
        "display":           "SpaceX",
        "handle":            "@SpaceX",
        "color":             0x1D9BF0,
        "profile_url":       "https://x.com/SpaceX",
        "accent":            "🚀",
        "fallback_logo_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/36/SpaceX-Logo-Xonly.svg/512px-SpaceX-Logo-Xonly.svg.png",
    },
    "BlueOrigin": {
        "username":          "blueorigin",
        "display":           "Blue Origin",
        "handle":            "@blueorigin",
        "color":             0x005288,
        "profile_url":       "https://x.com/blueorigin",
        "accent":            "🔵",
        "fallback_logo_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b2/Blue_Origin_logo.svg/512px-Blue_Origin_logo.svg.png",
    },
    "NASA": {
        "username":          "NASA",
        "display":           "NASA",
        "handle":            "@NASA",
        "color":             0x0B3D91,
        "profile_url":       "https://x.com/NASA",
        "accent":            "🌌",
        "fallback_logo_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e5/NASA_logo.svg/512px-NASA_logo.svg.png",
    },
    "RocketLab": {
        "username":          "RocketLab",
        "display":           "Rocket Lab",
        "handle":            "@RocketLab",
        "color":             0xCC0000,
        "profile_url":       "https://x.com/RocketLab",
        "accent":            "🧨",
        "fallback_logo_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/00/Rocket_Lab_Logo.svg/512px-Rocket_Lab_Logo.svg.png",
    },
    "ULA": {
        "username":          "ulalaunch",
        "display":           "ULA",
        "handle":            "@ulalaunch",
        "color":             0x003087,
        "profile_url":       "https://x.com/ulalaunch",
        "accent":            "🛸",
        "fallback_logo_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/84/ULA_Logo.svg/512px-ULA_Logo.svg.png",
    },
}

# Runtime avatar cache: account_key → URL string
_avatar_cache: dict[str, str] = {}


def _extract_feed_avatar(feed: feedparser.FeedParserDict) -> Optional[str]:
    """Try to pull a profile image URL out of the RSS feed metadata."""
    try:
        url = feed.feed.image.href
        if url and not any(s in url for s in ("emoji", "abs.twimg")):
            return url
    except AttributeError:
        pass
    try:
        url = feed.feed.logo
        if url:
            return url
    except AttributeError:
        pass
    for entry in feed.entries[:3]:
        for mc in entry.get("media_content", []):
            href = mc.get("url", "")
            if "profile_images" in href and "_400x400" in href:
                return href
    return None


# ─────────────────────────────────────────────────────────────────────────────
#  ✏️  HARDCODED SERVER → CHANNEL MAPPING
# ─────────────────────────────────────────────────────────────────────────────

HARDCODED_SERVERS: dict[int, dict] = {
    1210475350119813120: {
        "channel_id": 1418959517957357579,
        "enabled":    False,
    },
    1481151926216429683: {
        "channel_id": 1507775435545772052,
        "enabled":    True,
    },
}

# ─────────────────────────────────────────────
#  Runtime config (hardcoded + saved overrides)
# ─────────────────────────────────────────────

CONFIG_PATH = pathlib.Path("space_tweets_config.json")


def _load_saved() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except Exception:
            pass
    return {}


def _save_config(data: dict) -> None:
    saveable = {gid: gcfg for gid, gcfg in data.items() if int(gid) not in HARDCODED_SERVERS}
    CONFIG_PATH.write_text(json.dumps(saveable, indent=2))


def _build_runtime_config() -> dict[str, dict]:
    merged: dict[str, dict] = {}
    for gid, gcfg in _load_saved().items():
        merged[str(gid)] = gcfg
    for gid, gcfg in HARDCODED_SERVERS.items():
        merged[str(gid)] = gcfg
    return merged


_guild_config: dict[str, dict] = _build_runtime_config()


# ─────────────────────────────────────────────
#  RSS Fetcher
# ─────────────────────────────────────────────

class RSSFetcher:
    def __init__(self) -> None:
        self._seen:           dict[str, set[str]] = {}
        self._session:        Optional[aiohttp.ClientSession] = None
        self._working_mirror: dict[str, str] = {}

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                timeout=aiohttp.ClientTimeout(total=15),
            )
        return self._session

    async def _try_url(self, url: str) -> Optional[feedparser.FeedParserDict]:
        session = await self._get_session()
        try:
            async with session.get(url, allow_redirects=True) as resp:
                if resp.status != 200:
                    log.debug("  [%s] %s", resp.status, url)
                    return None
                raw  = await resp.text()
                feed = feedparser.parse(raw)
                if feed.entries:
                    return feed
                log.debug("  [200 but 0 entries] %s", url)
                return None
        except Exception as e:
            log.debug("  [ERR] %s — %s", url, e)
            return None

    async def _fetch_feed(self, account_key: str, username: str) -> Optional[feedparser.FeedParserDict]:
        # 1. rss.app
        rss_app = RSS_APP_FEEDS.get(account_key, "").strip()
        if rss_app:
            feed = await self._try_url(rss_app)
            if feed:
                log.info("SpaceTweets: rss.app → @%s", username)
                self._cache_avatar(account_key, feed)
                return feed
            log.warning("SpaceTweets: rss.app failed for %s", account_key)

        # 2. cached working mirror
        last = self._working_mirror.get(username)
        if last:
            feed = await self._try_url(last)
            if feed:
                self._cache_avatar(account_key, feed)
                return feed
            log.info("SpaceTweets: cached mirror dead, rescanning...")
            del self._working_mirror[username]

        # 3. scan all nitter mirrors
        log.info("SpaceTweets: scanning mirrors for @%s ...", username)
        for tpl in NITTER_MIRRORS:
            url  = tpl.format(username=username)
            feed = await self._try_url(url)
            if feed:
                self._working_mirror[username] = url
                log.info("SpaceTweets: mirror working → %s", url)
                self._cache_avatar(account_key, feed)
                return feed

        # 4. rsshub
        feed = await self._try_url(RSSHUB_URL.format(username=username))
        if feed:
            log.info("SpaceTweets: rsshub working for @%s", username)
            self._cache_avatar(account_key, feed)
            return feed

        log.error("SpaceTweets: ALL sources dead for @%s", username)
        return None

    @staticmethod
    def _cache_avatar(account_key: str, feed: feedparser.FeedParserDict) -> None:
        if account_key in _avatar_cache:
            return
        url = _extract_feed_avatar(feed)
        if url:
            _avatar_cache[account_key] = url
            log.info("SpaceTweets: cached avatar for %s", account_key)

    @staticmethod
    def _entry_id(entry) -> str:
        raw = getattr(entry, "id", None) or entry.get("link", "")
        return hashlib.md5(raw.encode()).hexdigest()

    @staticmethod
    def _parse_images(entry) -> list[str]:
        images: list[str] = []
        seen:   set[str]  = set()

        entry_link = entry.get("link", "")
        m = re.match(r"(https?://[^/]+)", entry_link)
        entry_base = m.group(1) if m else ""

        def normalise(u: str) -> str:
            u = u.strip()
            if u.startswith("/pic/") and entry_base:
                return entry_base + u
            return u

        def add(u: str) -> None:
            u = normalise(u)
            skip = (
                "emoji",
                "abs.twimg",
                "/profile_images/",
                "ext_tw_video_thumb",
                "tweet_video_thumb",
                "amplify_video_thumb",
                "video.twimg.com",
            )
            if u and u.startswith("http") and u not in seen and not any(s in u for s in skip):
                seen.add(u)
                images.append(u)

        for m in re.finditer(r'<img[^>]+src=["\']([^"\']+)["\']', entry.get("summary", "")):
            add(m.group(1))
        for enc in entry.get("enclosures", []):
            if enc.get("type", "").startswith("image/"):
                add(enc.get("href") or enc.get("url", ""))
        for mc in entry.get("media_content", []):
            t      = mc.get("type", "")
            medium = mc.get("medium", "")
            url    = mc.get("url", "")
            if medium == "image" or t.startswith("image/") or (url and not t):
                add(url)
        for mt in entry.get("media_thumbnail", []):
            add(mt.get("url", ""))

        return images

    @staticmethod
    def _clean_text(entry) -> str:
        text = entry.get("title", "") or entry.get("summary", "")
        text = re.sub(r"<[^>]+>",             " ", text)
        text = re.sub(r"https?://t\.co/\S+",   "", text)
        text = re.sub(r"https?://nitter\.\S+", "", text)
        text = re.sub(r"\s{2,}",              " ", text).strip()
        return text or "*[media only]*"

    @staticmethod
    def _parse_date(entry) -> datetime:
        try:
            return parsedate_to_datetime(
                entry.get("published") or entry.get("updated", "")
            ).astimezone(timezone.utc)
        except Exception:
            return datetime.now(timezone.utc)

    @staticmethod
    def _canonical_url(entry, username: str) -> str:
        link  = entry.get("link", "")
        match = re.search(r"/status/(\d+)", link)
        return f"https://x.com/{username}/status/{match.group(1)}" if match else link

    async def _enrich_images(self, tweet_url: str, existing: list[str]) -> tuple[list[str], bool]:
        """
        Calls fxtwitter API to get full media for a tweet.
        Returns (image_urls, is_video):
          - Photos → (all photo URLs, False)
          - Video  → ([thumbnail_url], True)
          - Fail   → (existing, False)
        """
        m = re.search(r"/status/(\d+)", tweet_url)
        if not m:
            return existing, False

        parts    = tweet_url.rstrip("/").split("/")
        username = parts[-3] if len(parts) >= 3 else "i"
        tweet_id = m.group(1)
        api_url  = f"https://api.fxtwitter.com/{username}/status/{tweet_id}"

        try:
            session = await self._get_session()
            async with session.get(api_url, allow_redirects=True) as resp:
                if resp.status != 200:
                    return existing, False
                data  = await resp.json(content_type=None)
                media = data.get("tweet", {}).get("media", {}) or {}

                photos = media.get("photos", [])
                urls   = [p["url"] for p in photos if p.get("url")]
                if urls:
                    log.info("SpaceTweets: fxtwitter %s → %d photos", tweet_id, len(urls))
                    return urls, False

                videos = media.get("videos", [])
                if videos:
                    thumb = videos[0].get("thumbnail_url", "")
                    log.info("SpaceTweets: %s is video", tweet_id)
                    return ([thumb] if thumb else []), True

        except Exception as e:
            log.debug("fxtwitter enrich failed: %s", e)

        return existing, False

    async def fetch_new(self, account_key: str, username: str) -> list[dict]:
        """Auto-poll: only unseen tweets within MAX_TWEET_AGE_HOURS."""
        feed = await self._fetch_feed(account_key, username)
        if not feed:
            return []

        seen    = self._seen.setdefault(username, set())
        now     = datetime.now(timezone.utc)
        results = []

        for entry in feed.entries:
            eid     = self._entry_id(entry)
            created = self._parse_date(entry)
            age_h   = (now - created).total_seconds() / 3600

            if age_h > MAX_TWEET_AGE_HOURS:
                seen.add(eid)
                continue
            if eid in seen:
                continue

            url              = self._canonical_url(entry, username)
            images, is_video = await self._enrich_images(url, self._parse_images(entry))
            results.append({
                "id":         eid,
                "text":       self._clean_text(entry),
                "created_at": created,
                "images":     images,
                "is_video":   is_video,
                "url":        url,
            })
            seen.add(eid)

        results.sort(key=lambda t: t["created_at"])
        return results

    async def fetch_today(self, account_key: str, username: str) -> list[dict]:
        """!spacenow: all tweets since midnight UTC, ignores seen cache."""
        feed = await self._fetch_feed(account_key, username)
        if not feed:
            return []

        now          = datetime.now(timezone.utc)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        results      = []

        for entry in feed.entries:
            created = self._parse_date(entry)
            if created >= start_of_day:
                url              = self._canonical_url(entry, username)
                images, is_video = await self._enrich_images(url, self._parse_images(entry))
                results.append({
                    "id":         self._entry_id(entry),
                    "text":       self._clean_text(entry),
                    "created_at": created,
                    "images":     images,
                    "is_video":   is_video,
                    "url":        url,
                })

        results.sort(key=lambda t: t["created_at"])
        return results

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()


# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────

def _get_logo_url(account_key: str) -> Optional[str]:
    return _avatar_cache.get(account_key) or ACCOUNTS[account_key].get("fallback_logo_url")


def _relative_time(dt: datetime) -> str:
    secs = int((datetime.now(timezone.utc) - dt).total_seconds())
    if secs < 60:     return f"{secs}s"
    if secs < 3600:   return f"{secs // 60}m"
    if secs < 86400:  return f"{secs // 3600}h"
    if secs < 604800: return f"{secs // 86400}d"
    return dt.strftime("%-d %b")


# ─────────────────────────────────────────────
#  Embed builder
# ─────────────────────────────────────────────

def build_embeds(tweet: dict, account_key: str) -> list[discord.Embed]:
    cfg      = ACCOUNTS[account_key]
    images   = tweet.get("images", [])
    is_video = tweet.get("is_video", False)
    logo_url = _get_logo_url(account_key)

    link_label = "🎬  Watch on X" if is_video else "🔗  View on X"

    main = discord.Embed(
        description=tweet["text"],
        color=cfg["color"],
        timestamp=tweet["created_at"],
        url=tweet["url"],
    )
    main.set_author(
        name=f"{cfg['display']}  \u2713  {cfg['handle']}",
        url=cfg["profile_url"],
        icon_url=logo_url,
    )
    if images:
        main.set_image(url=images[0])
    main.add_field(
        name="",
        value=f"[{link_label}  \u00b7  {_relative_time(tweet['created_at'])}]({tweet['url']})",
        inline=False,
    )
    main.set_footer(
        text=f"OLIT Space Feed  \u00b7  {cfg['accent']} {cfg['display']}",
        icon_url=logo_url,
    )

    embeds = [main]
    # Discord gallery: all embeds share the same url — max 4 total
    for img_url in images[1:4]:
        extra = discord.Embed(url=tweet["url"], color=cfg["color"])
        extra.set_image(url=img_url)
        embeds.append(extra)

    return embeds


# ─────────────────────────────────────────────
#  Broadcast helper
# ─────────────────────────────────────────────

async def _broadcast(bot: commands.Bot, tweet: dict, account_key: str) -> None:
    embeds = build_embeds(tweet, account_key)
    for gid_str, gcfg in _guild_config.items():
        if not gcfg.get("enabled", True):
            continue
        ch = bot.get_channel(gcfg.get("channel_id", 0))
        if ch is None:
            log.warning("SpaceTweets: channel %s not found (guild %s)", gcfg.get("channel_id"), gid_str)
            continue
        try:
            await ch.send(embeds=embeds)
            log.info("SpaceTweets: posted %s → #%s", account_key, ch.name)
        except discord.Forbidden:
            log.error("SpaceTweets: missing send permission in #%s", ch.name)
        except Exception:
            log.exception("SpaceTweets: send failed → %s", gcfg.get("channel_id"))


# ─────────────────────────────────────────────
#  Cog
# ─────────────────────────────────────────────

class SpaceTweetsCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot     = bot
        self.fetcher = RSSFetcher()
        self._poll.start()
        log.info("SpaceTweets: cog loaded")

    def cog_unload(self) -> None:
        self._poll.cancel()
        asyncio.create_task(self.fetcher.close())

    @tasks.loop(minutes=POLL_INTERVAL_MINUTES)
    async def _poll(self) -> None:
        all_tweets: list[tuple[dict, str]] = []
        for account_key, cfg in ACCOUNTS.items():
            try:
                tweets = await self.fetcher.fetch_new(account_key, cfg["username"])
                for t in tweets:
                    all_tweets.append((t, account_key))
            except Exception:
                log.exception("SpaceTweets: unhandled error polling @%s", cfg["username"])

        all_tweets.sort(key=lambda x: x[0]["created_at"])
        for tweet, account_key in all_tweets:
            await _broadcast(self.bot, tweet, account_key)

    @_poll.before_loop
    async def _before_poll(self) -> None:
        await self.bot.wait_until_ready()
        log.info("SpaceTweets: polling every %d min", POLL_INTERVAL_MINUTES)

    # ── !spacenow ─────────────────────────────────────────────────────────────

    @commands.command(name="spacenow")
    @commands.has_permissions(administrator=True)
    async def spacenow(self, ctx: commands.Context) -> None:
        """Fetch and post ALL tweets from today (since midnight UTC)."""
        msg = await ctx.send("🔄 Fetching today's tweets...")
        all_tweets: list[tuple[dict, str]] = []
        errors: list[str] = []

        for account_key, cfg in ACCOUNTS.items():
            try:
                tweets = await self.fetcher.fetch_today(account_key, cfg["username"])
                for t in tweets:
                    all_tweets.append((t, account_key))
            except Exception as e:
                errors.append(f"@{cfg['username']}: {e}")

        all_tweets.sort(key=lambda x: x[0]["created_at"])
        for tweet, account_key in all_tweets:
            await _broadcast(self.bot, tweet, account_key)

        date_str = datetime.now(timezone.utc).strftime("%d %b %Y")
        desc = (
            f"Posted **{len(all_tweets)}** tweet(s) from today ({date_str} UTC)."
            if all_tweets
            else f"No tweets found for today ({date_str} UTC)."
        )
        if errors:
            desc += "\n\n⚠️ Errors:\n" + "\n".join(errors)

        await msg.edit(content=None, embed=discord.Embed(
            title="🔄  Done", description=desc, color=0x1D9BF0,
        ))

    # ── !spacediag ────────────────────────────────────────────────────────────

    @commands.command(name="spacediag")
    @commands.has_permissions(administrator=True)
    async def spacediag(self, ctx: commands.Context) -> None:
        """Test every RSS source and show what's alive."""
        msg = await ctx.send("🔍 Testing all RSS sources, please wait...")
        lines: list[str] = []
        session = await self.fetcher._get_session()

        async def check(label: str, url: str) -> str:
            try:
                async with session.get(url, allow_redirects=True) as r:
                    if r.status != 200:
                        return f"❌  `{label}` → HTTP {r.status}"
                    feed = feedparser.parse(await r.text())
                    if feed.entries:
                        avatar = _extract_feed_avatar(feed)
                        return f"✅  `{label}` → {len(feed.entries)} entries | avatar={'✅' if avatar else '❌'}"
                    return f"⚠️  `{label}` → connected but 0 entries"
            except Exception as e:
                return f"💀  `{label}` → {type(e).__name__}"

        for account_key, cfg in ACCOUNTS.items():
            cached_av = _avatar_cache.get(account_key, "not cached yet")
            lines.append(f"**@{cfg['username']}** | avatar: `{cached_av[:60] if len(cached_av) > 60 else cached_av}`")
            rss_url = RSS_APP_FEEDS.get(account_key, "").strip()
            if rss_url:
                lines.append(await check("rss.app", rss_url))
            else:
                lines.append("⬜  `rss.app` — not configured (recommended)")
            for tpl in NITTER_MIRRORS:
                url = tpl.format(username=cfg["username"])
                lines.append(await check(url.split("/")[2], url))
            lines.append(await check("rsshub.app", RSSHUB_URL.format(username=cfg["username"])))
            lines.append("")

        lines.append("─────────────────────────────────────")
        lines.append("Get reliable free feeds → <https://rss.app>")

        await msg.edit(content=None, embed=discord.Embed(
            title="🔍  Space Feed Diagnostics",
            description="\n".join(lines)[:4000],
            color=0x1D9BF0,
        ))

    # ── !spacestatus ──────────────────────────────────────────────────────────

    @commands.command(name="spacestatus")
    async def spacestatus(self, ctx: commands.Context) -> None:
        """Show the current Space Feed configuration."""
        gid  = str(ctx.guild.id)
        gcfg = _guild_config.get(gid)

        if not gcfg or not gcfg.get("channel_id"):
            embed = discord.Embed(
                title="⚠️  Not Configured",
                description="Add this server to `HARDCODED_SERVERS` in `space_tweets.py`.",
                color=0xFF6B00,
            )
        else:
            ch     = self.bot.get_channel(gcfg["channel_id"])
            ch_str = ch.mention if ch else f"`{gcfg['channel_id']}` (**not found — check ID!**)"
            source = "🔒 Hardcoded" if int(gid) in HARDCODED_SERVERS else "⚙️ Config file"
            status = "🟢 Enabled" if gcfg.get("enabled", True) else "🔴 Disabled"
            feed_status = [
                f"{cfg['accent']} {cfg['display']}: {'✅ rss.app' if RSS_APP_FEEDS.get(ak, '').strip() else '⚠️ Nitter only'}"
                for ak, cfg in ACCOUNTS.items()
            ]
            avatar_status = [
                f"{cfg['accent']} {cfg['display']}: {'✅ cached' if ak in _avatar_cache else '⏳ pending'}"
                for ak, cfg in ACCOUNTS.items()
            ]
            embed = discord.Embed(title="🛰️  Space Feed Status", color=0x1D9BF0)
            embed.add_field(name="Channel",  value=ch_str,                   inline=True)
            embed.add_field(name="Status",   value=status,                   inline=True)
            embed.add_field(name="Source",   value=source,                   inline=True)
            embed.add_field(name="Interval", value=f"Every {POLL_INTERVAL_MINUTES} min", inline=True)
            embed.add_field(name="Feeds",    value="\n".join(feed_status),   inline=False)
            embed.add_field(name="Avatars",  value="\n".join(avatar_status), inline=False)

        embed.set_footer(text="OLIT Space Feed")
        await ctx.send(embed=embed)

    # ── !spacetoggle ──────────────────────────────────────────────────────────

    @commands.command(name="spacetoggle")
    @commands.has_permissions(administrator=True)
    async def spacetoggle(self, ctx: commands.Context) -> None:
        """Enable or disable the Space Feed for this server."""
        gid = str(ctx.guild.id)
        if gid not in _guild_config:
            await ctx.send("⚠️ This server isn't configured. Add it to `HARDCODED_SERVERS`.")
            return
        current = _guild_config[gid].get("enabled", True)
        _guild_config[gid]["enabled"] = not current
        _save_config(_guild_config)
        state = "🟢 Enabled" if not current else "🔴 Disabled"
        await ctx.send(f"Space Feed is now **{state}**.")

    # ── !spacedebug ───────────────────────────────────────────────────────────

    @commands.command(name="spacedebug")
    @commands.has_permissions(administrator=True)
    async def spacedebug(self, ctx: commands.Context) -> None:
        """Dump raw RSS entry fields for latest tweet to diagnose image parsing."""
        msg     = await ctx.send("🔬 Fetching raw feed data...")
        session = await self.fetcher._get_session()
        IMG_RE  = re.compile(r'<img[^>]+src=["\'][^"\']+["\']')
        SRC_RE  = re.compile(r'src=["\']([^"\']+)["\']')

        for account_key, cfg in ACCOUNTS.items():
            rss_url = RSS_APP_FEEDS.get(account_key, "").strip()
            if not rss_url:
                continue
            try:
                async with session.get(rss_url, allow_redirects=True) as resp:
                    raw  = await resp.text()
                    feed = feedparser.parse(raw)
                    if not feed.entries:
                        await ctx.send(f"⚠️ No entries for {account_key}")
                        continue
                    e = feed.entries[0]

                    summary  = e.get("summary", "")
                    img_srcs = [SRC_RE.search(t).group(1) for t in IMG_RE.findall(summary) if SRC_RE.search(t)]
                    mcs      = e.get("media_content", [])
                    encs     = e.get("enclosures", [])
                    mts      = e.get("media_thumbnail", [])
                    parsed   = self.fetcher._parse_images(e)

                    lines = [
                        f"**@{cfg['username']} latest entry**",
                        f"`link:` {e.get('link', 'n/a')}",
                        f"`summary <img> count: {len(img_srcs)}`",
                    ]
                    for u in img_srcs:
                        lines.append(f"  \u2022 `{u[:120]}`")
                    lines.append(f"`enclosures: {len(encs)}`")
                    for en in encs:
                        lines.append(f"  \u2022 type={en.get('type')} `{str(en.get('href') or en.get('url', ''))[:100]}`")
                    lines.append(f"`media_content: {len(mcs)}`")
                    for mc in mcs:
                        lines.append(f"  \u2022 medium={mc.get('medium')} type={mc.get('type')} `{str(mc.get('url', ''))[:100]}`")
                    lines.append(f"`media_thumbnail: {len(mts)}`")
                    for mt in mts:
                        lines.append(f"  \u2022 `{str(mt.get('url', ''))[:100]}`")
                    lines.append(f"`_parse_images result: {len(parsed)}`")
                    for u in parsed:
                        lines.append(f"  \u2705 `{u[:120]}`")

                    await ctx.send(embed=discord.Embed(
                        title=f"🔬 Raw feed: {cfg['display']}",
                        description="\n".join(lines)[:4000],
                        color=0x1D9BF0,
                    ))
            except Exception as ex:
                await ctx.send(f"Error fetching {account_key}: {ex}")

        await msg.delete()

    # ── error handler ─────────────────────────────────────────────────────────

    @spacenow.error
    @spacediag.error
    @spacetoggle.error
    @spacedebug.error
    async def admin_error(self, ctx: commands.Context, error: Exception) -> None:
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You need Administrator permission to use this command.")


# ─────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────

def setup_space_tweets(bot: commands.Bot) -> None:
    async def _add():
        await bot.add_cog(SpaceTweetsCog(bot))
        log.info("SpaceTweets: cog registered")

    bot.loop.create_task(_add())