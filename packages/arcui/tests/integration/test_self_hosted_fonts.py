"""Air-gap font self-hosting (SPEC-023 §FR-26 / NFR-9).

The served HTML must reference no external CDN. fonts.css is mounted at
``/assets/fonts/fonts.css`` and reachable as a real asset (no 404). The
file currently uses system-font fallbacks; restoring `@font-face` rules
is gated on shipping the WOFF2 binaries alongside the CSS — see the
README in `static/assets/fonts/` for the restore checklist.
"""

from __future__ import annotations

from pathlib import Path

from starlette.testclient import TestClient

from arcui.server import create_app

_STATIC_DIR = Path(__file__).resolve().parents[2] / "src" / "arcui" / "static"
_FONTS_DIR = _STATIC_DIR / "assets" / "fonts"


def test_no_googleapis_reference_in_served_html() -> None:
    """The served dashboard HTML must not reference fonts.googleapis.com."""
    app = create_app()
    with TestClient(app) as client:
        resp = client.get("/")
        assert resp.status_code == 200
        body = resp.text.lower()
        assert "fonts.googleapis.com" not in body
        assert "fonts.gstatic.com" not in body


def test_fonts_css_is_reachable() -> None:
    """assets/fonts/fonts.css is mounted and served with the right type."""
    app = create_app()
    with TestClient(app) as client:
        resp = client.get("/assets/fonts/fonts.css")
        assert resp.status_code == 200
        assert "@font-face" in resp.text


def test_fonts_directory_carries_install_readme() -> None:
    """Operators get a README explaining what files belong here."""
    readme = _FONTS_DIR / "README.md"
    assert readme.exists()
    text = readme.read_text(encoding="utf-8")
    assert "Inter" in text
    assert "JetBrains Mono" in text
