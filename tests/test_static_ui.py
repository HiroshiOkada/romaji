"""静的 UI ファイルの単体テスト。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

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
