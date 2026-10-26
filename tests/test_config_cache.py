"""ConfigCache (mtime 監視による自動再読込) の単体テスト。"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from romaji.config import ConfigCache, ConfigError

MIN_CONFIG = """\
[server]
host = "127.0.0.1"
port = 18765

[paths]
logic_dir = "logic"
examples_dir = "examples"

[llm]
base_url = "https://openrouter.ai/api/v1"
api_key_env = "ROMAJI_CACHE_TEST_API_KEY"

[llm.conversion]
model = "test-conversion-model"

[llm.logic_revision]
model = "test-revision-model"

[ui]
debounce_ms = 500
"""


def write_config(path: Path, *, model: str = "test-conversion-model") -> None:
    path.write_text(MIN_CONFIG.replace("test-conversion-model", model), encoding="utf-8")


def later_mtime(path: Path) -> None:
    """ファイルの mtime を確実に変化させる（FS の時刻刻み対策）。"""
    os.utime(path, (time.time() + 1, time.time() + 1))


def test_cache_reloads_on_config_change(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "config.toml"
    write_config(config_path)
    monkeypatch.setenv("ROMAJI_CACHE_TEST_API_KEY", "k1")
    cache = ConfigCache(config_path)

    first = cache.get()
    assert first.llm.conversion.model == "test-conversion-model"

    # 変更がないうちはキャッシュを返す
    assert cache.get() is first

    # 変更したら再読込する
    write_config(config_path, model="updated-model")
    later_mtime(config_path)
    assert cache.get().llm.conversion.model == "updated-model"


def test_cache_reloads_env_api_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ROMAJI_CACHE_TEST_API_KEY", raising=False)
    config_path = tmp_path / "config.toml"
    write_config(config_path)
    # 初回読込は load_config 既定の env 解決に従う（プロセス環境から拾う）
    monkeypatch.setenv("ROMAJI_CACHE_TEST_API_KEY", "old-key")

    cache = ConfigCache(config_path)
    assert cache.get().llm.api_key == "old-key"

    # .env 更新 → 再読込時は override 読込で新キーに追随
    env_path = tmp_path / ".env"
    env_path.write_text("ROMAJI_CACHE_TEST_API_KEY=new-key\n", encoding="utf-8")
    later_mtime(env_path)
    assert cache.get().llm.api_key == "new-key"


def test_cache_falls_back_on_broken_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "config.toml"
    write_config(config_path)
    monkeypatch.setenv("ROMAJI_CACHE_TEST_API_KEY", "k1")
    cache = ConfigCache(config_path)
    first = cache.get()

    # 不正な設定を書き込んでも、前回の値で続行する
    config_path.write_text("[server]\nhost = '127.0.0.1'\n", encoding="utf-8")
    later_mtime(config_path)
    assert cache.get() is first

    # 再び正しい設定に戻すと復帰する
    write_config(config_path, model="recovered-model")
    later_mtime(config_path)
    assert cache.get().llm.conversion.model == "recovered-model"


def test_cache_first_load_raises_on_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROMAJI_CACHE_TEST_API_KEY", "k1")
    cache = ConfigCache(tmp_path / "missing.toml")
    with pytest.raises(ConfigError):
        cache.get()
