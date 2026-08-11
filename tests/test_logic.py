"""ロジック版管理の単体テスト。"""

from __future__ import annotations

from pathlib import Path

from romaji.logic import LogicStore


def test_logic_update_and_restore(tmp_path: Path) -> None:
    store = LogicStore(tmp_path / "logic")
    store.ensure_initialized()
    first = store.current_version_id()
    original = store.read_current()

    second = store.update("新しい指示", label="manual")
    assert second != first
    assert "新しい指示" in store.read_current()

    third = store.restore(first)
    assert third != second
    assert store.read_current() == original
