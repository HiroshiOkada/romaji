"""設定読込の単体テスト。"""

from __future__ import annotations

from pathlib import Path

import pytest

from romaji.config import ConfigError, load_config


def test_load_config_requires_api_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[server]
host = "127.0.0.1"
port = 18765

[paths]
logic_dir = "data/logic"
examples_dir = "data/examples"

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
    monkeypatch.delenv("LLM_INPUT_API_KEY", raising=False)
    with pytest.raises(ConfigError, match="LLM_INPUT_API_KEY"):
        load_config(config_path, load_env=False)


def test_load_config_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[server]
host = "127.0.0.1"
port = 18765

[paths]
logic_dir = "data/logic"
examples_dir = "data/examples"

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
    monkeypatch.setenv("LLM_INPUT_API_KEY", "test-key")
    cfg = load_config(config_path, load_env=False)
    assert cfg.server.port == 18765
    assert cfg.llm.api_key_env == "LLM_INPUT_API_KEY"
    assert cfg.llm.api_key == "test-key"
