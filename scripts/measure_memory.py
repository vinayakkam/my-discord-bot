"""Measure how much memory the bot costs before it connects to Discord.

Imports `main` in a fresh interpreter (which registers every command, view and
listener but does not start Flask or the gateway) and prints the process's
resident memory, peak memory and the heavy third-party modules that ended up
loaded. Run it before and after a change to see what the change bought:

    python scripts/measure_memory.py
    python scripts/measure_memory.py --json

This is the import-time baseline only. Gateway caches (members, messages) grow
after login and are not visible here.
"""

import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Modules big enough that loading one shows up in RSS.
HEAVY_MODULES = (
    "PIL", "flask", "requests", "aiohttp", "discord", "pytz",
    "wavelink", "spotipy", "bs4", "nacl", "async_lru",
)

# Runs inside the child interpreter. Dependency-free (no psutil) so it works
# on any host the bot runs on.
_PROBE = r"""
import json, os, sys

def rss_and_peak():
    # Current and peak resident set size in bytes.
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        get_info = ctypes.windll.psapi.GetProcessMemoryInfo
        get_info.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
        get_info(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
        return pmc.WorkingSetSize, pmc.PeakWorkingSetSize

    fields = {}
    with open("/proc/self/status") as fh:
        for line in fh:
            key, _, value = line.partition(":")
            if key in ("VmRSS", "VmHWM"):
                fields[key] = int(value.split()[0]) * 1024
    return fields.get("VmRSS", 0), fields.get("VmHWM", 0)

before, _ = rss_and_peak()
sys.path.insert(0, os.environ["OLIT_ROOT"])
import main  # noqa: F401  (registers everything, connects to nothing)
after, peak = rss_and_peak()

heavy = json.loads(os.environ["OLIT_HEAVY"])
print(json.dumps({
    "rss_before_import": before,
    "rss_after_import": after,
    "peak_rss": peak,
    "modules_loaded": len(sys.modules),
    "heavy_modules_loaded": sorted(m for m in heavy if m in sys.modules),
    "commands": len(main.bot.commands),
}))
"""


def measure() -> dict:
    """Run the probe in a clean child process and return its report."""
    env = dict(os.environ)
    env["OLIT_ROOT"] = ROOT
    env["OLIT_HEAVY"] = json.dumps(HEAVY_MODULES)
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, "-c", _PROBE],
        cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8",
        timeout=120,
    )
    if proc.returncode != 0:
        raise SystemExit(f"probe failed:\n{proc.stderr}")
    # main.py may print during import; the report is the last line.
    return json.loads(proc.stdout.strip().splitlines()[-1])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="print raw JSON")
    args = parser.parse_args()

    report = measure()
    if args.json:
        print(json.dumps(report, indent=2))
        return

    def mb(n):
        return f"{n / (1024 * 1024):.1f} MB"

    print(f"RSS before import : {mb(report['rss_before_import'])}")
    print(f"RSS after import  : {mb(report['rss_after_import'])}")
    print(f"Peak RSS          : {mb(report['peak_rss'])}")
    print(f"Modules loaded    : {report['modules_loaded']}")
    print(f"Prefix commands   : {report['commands']}")
    print(f"Heavy modules     : {', '.join(report['heavy_modules_loaded']) or 'none'}")


if __name__ == "__main__":
    main()
