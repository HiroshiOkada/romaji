"""静的 UI ファイルの単体テスト。"""

from __future__ import annotations

import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from fastapi.testclient import TestClient

from romaji.app import create_app

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def test_index_html_has_copy_next_button() -> None:
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    assert 'id="copyNextBtn"' in html
    assert ">コピーして次へ<" in html
    # アクションバー内に配置されていること
    assert html.index('id="appActions"') < html.index('id="copyNextBtn"')


def test_app_js_has_copy_next_handler() -> None:
    js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    assert 'getElementById("copyNextBtn")' in js
    # クリップボードへのコピー処理
    assert "navigator.clipboard" in js
    assert 'writeText(' in js
    # コピー成功後に入力欄と変換結果欄をクリアする
    assert 'inputEl.value = ""' in js
    assert 'outputEl.value = ""' in js
    # 変換結果が空の場合はコピーしない
    assert "コピーする変換結果がありません" in js


def test_app_js_syntax_is_valid() -> None:
    result = subprocess.run(
        ["node", "--check", str(STATIC_DIR / "app.js")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_style_css_hidden_attribute_guard() -> None:
    """display 指定が hidden 属性を無効化しないためのガードがあること。"""
    css = (STATIC_DIR / "style.css").read_text(encoding="utf-8")
    assert "[hidden]" in css
    assert "display: none" in css


def test_favicon_exists_and_referenced_in_html() -> None:
    """ファビコン SVG が存在して整形式であり、index.html から参照されていること。"""
    favicon_path = STATIC_DIR / "favicon.svg"
    assert favicon_path.is_file()
    svg_text = favicon_path.read_text(encoding="utf-8")
    root = ET.fromstring(svg_text)
    assert root.tag.endswith("svg")

    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    assert '<link rel="icon" href="/static/favicon.svg" type="image/svg+xml">' in html


def test_favicon_served_via_http() -> None:
    """/static/favicon.svg と /favicon.ico の両方でファビコンが取得できること。"""
    client = TestClient(create_app())
    for path in ("/static/favicon.svg", "/favicon.ico"):
        res = client.get(path)
        assert res.status_code == 200
        assert "image/svg+xml" in res.headers["content-type"]
        assert "<svg" in res.text

