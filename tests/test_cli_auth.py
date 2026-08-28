"""CLI パスワード発行コマンドの単体テスト。"""

from __future__ import annotations

from pathlib import Path

import pytest

from romaji.auth import UserStore
from romaji.cli import main
from romaji.config import load_config


def test_cli_issue_password_admin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    config_path = tmp_path / "config.toml"
    auth_dir = tmp_path / "auth"
    config_path.write_text(
        f"""
[server]
host = "127.0.0.1"
port = 18765

[paths]
logic_dir = "data/logic"
examples_dir = "data/examples"
auth_dir = "{auth_dir.as_posix()}"

[llm]
base_url = "https://openrouter.ai/api/v1"
api_key_env = "LLM_INPUT_API_KEY"

[llm.conversion]
model = "google/gemini-3.1-flash-lite-preview"

[llm.logic_revision]
model = "openai/gpt-5.6-terra"

[ui]
debounce_ms = 800
""".strip()
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("LLM_INPUT_API_KEY", "dummy-key")
    monkeypatch.setattr("romaji.cli.load_config", lambda: load_config(config_path, load_env=False))

    # Issue admin password
    rc = main(["issue-password", "admin"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "admin" in captured.out
    lines = [line.strip() for line in captured.out.strip().splitlines() if line.strip()]
    issued_pw = lines[-1]
    assert len(issued_pw) >= 20

    # Verify store
    store = UserStore(auth_dir)
    assert store.verify_password("admin", issued_pw) is True

    # Re-issue (overwrite)
    rc2 = main(["issue-password", "admin"])
    assert rc2 == 0
    captured2 = capsys.readouterr()
    issued_pw2 = [line.strip() for line in captured2.out.strip().splitlines() if line.strip()][-1]
    assert issued_pw2 != issued_pw
    assert store.verify_password("admin", issued_pw) is False
    assert store.verify_password("admin", issued_pw2) is True


def test_cli_issue_password_guest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    config_path = tmp_path / "config.toml"
    auth_dir = tmp_path / "auth"
    config_path.write_text(
        f"""
[server]
host = "127.0.0.1"
port = 18765

[paths]
logic_dir = "data/logic"
examples_dir = "data/examples"
auth_dir = "{auth_dir.as_posix()}"

[llm]
base_url = "https://openrouter.ai/api/v1"
api_key_env = "LLM_INPUT_API_KEY"

[llm.conversion]
model = "google/gemini-3.1-flash-lite-preview"

[llm.logic_revision]
model = "openai/gpt-5.6-terra"

[ui]
debounce_ms = 800
""".strip()
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("LLM_INPUT_API_KEY", "dummy-key")
    monkeypatch.setattr("romaji.cli.load_config", lambda: load_config(config_path, load_env=False))

    rc = main(["issue-password", "guest"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "guest" in captured.out
    issued_pw = [line.strip() for line in captured.out.strip().splitlines() if line.strip()][-1]
    assert len(issued_pw) >= 20

    store = UserStore(auth_dir)
    assert store.verify_password("guest", issued_pw) is True
