"""Regression checks for the memory work.

Each test pins one thing that used to make the bot hold more RAM than it
needed, so it cannot quietly come back.
"""

import io
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _modules_after_importing_main():
    """Names of the modules a fresh interpreter has loaded after `import main`."""
    code = (
        "import json, sys; sys.path.insert(0, sys.argv[1]); import main; "
        "print(json.dumps(sorted(sys.modules)))"
    )
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    proc = subprocess.run(
        [sys.executable, "-c", code, ROOT],
        cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8",
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    return set(json.loads(proc.stdout.strip().splitlines()[-1]))


def test_pillow_is_not_loaded_at_startup():
    """Pillow is only needed by !pixelart, so it must load on first use."""
    assert "PIL" not in _modules_after_importing_main()


def test_pixel_art_still_converts_with_lazy_pillow():
    from PIL import Image

    import pixel_art

    src = io.BytesIO()
    Image.new("RGB", (40, 30), (200, 50, 50)).save(src, format="PNG")

    out = pixel_art.convert_to_pixel_art(src.getvalue(), resolution=16, colors=8)
    result = Image.open(out)
    assert result.format == "PNG"
    assert result.size[0] > 0 and result.size[1] > 0


def test_pixel_art_palette_style_with_lazy_pillow():
    """The preset-palette path imports Pillow separately; cover it too."""
    from PIL import Image

    import pixel_art

    src = io.BytesIO()
    Image.new("RGB", (40, 30), (20, 120, 220)).save(src, format="PNG")

    out = pixel_art.convert_to_pixel_art(src.getvalue(), resolution=16, style="gameboy")
    assert Image.open(out).format == "PNG"
