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


def test_logic_adopt_existing_initial_file(tmp_path: Path) -> None:
    logic_dir = tmp_path / "logic"
    versions_dir = logic_dir / "versions"
    versions_dir.mkdir(parents=True)
    initial_file = versions_dir / "v20260811T073007Z_initial.md"
    initial_file.write_text("初期テキスト\n", encoding="utf-8")

    store = LogicStore(logic_dir)
    store.ensure_initialized()

    assert store.current_version_id() == "v20260811T073007Z"
    assert store.read_current() == "初期テキスト\n"
    # Should not create duplicate files
    assert len(list(versions_dir.glob("v*.md"))) == 1


def test_logic_reconcile_existing_current_md(tmp_path: Path) -> None:
    logic_dir = tmp_path / "logic"
    versions_dir = logic_dir / "versions"
    versions_dir.mkdir(parents=True)
    initial_file = versions_dir / "v20260811T073007Z_initial.md"
    initial_file.write_text("初期テキスト\n", encoding="utf-8")
    current_file = logic_dir / "current.md"
    current_file.write_text("初期テキスト\n", encoding="utf-8")

    store = LogicStore(logic_dir)
    store.ensure_initialized()

    assert store.current_version_id() == "v20260811T073007Z"
    assert (logic_dir / "current_version.txt").read_text(encoding="utf-8").strip() == "v20260811T073007Z"
