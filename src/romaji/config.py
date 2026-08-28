"""TOML 設定と環境変数の読込。"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = ROOT / "config.toml"


@dataclass(frozen=True)
class ServerConfig:
    host: str
    port: int


@dataclass(frozen=True)
class LlmRoleConfig:
    model: str


@dataclass(frozen=True)
class LlmConfig:
    base_url: str
    api_key_env: str
    api_key: str
    conversion: LlmRoleConfig
    logic_revision: LlmRoleConfig


@dataclass(frozen=True)
class PathsConfig:
    logic_dir: Path
    examples_dir: Path
    auth_dir: Path



@dataclass(frozen=True)
class UiConfig:
    debounce_ms: int


@dataclass(frozen=True)
class AppConfig:
    server: ServerConfig
    llm: LlmConfig
    paths: PathsConfig
    ui: UiConfig
    config_path: Path


class ConfigError(ValueError):
    """設定不正。"""


def _require_mapping(data: object, section: str) -> dict:
    if not isinstance(data, dict):
        raise ConfigError(f"[{section}] がありません")
    return data


def _require_str(section: dict, key: str, section_name: str) -> str:
    value = section.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"[{section_name}] {key} は必須の文字列です（デフォルトなし）")
    return value.strip()


def _require_int(section: dict, key: str, section_name: str) -> int:
    value = section.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"[{section_name}] {key} は必須の整数です（デフォルトなし）")
    return value


def _resolve_path(raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    return path


def load_config(config_path: Path | None = None, *, load_env: bool = True) -> AppConfig:
    """設定ファイルを読み、API キーを環境変数から解決する。"""
    if load_env:
        load_dotenv(ROOT / ".env")

    path = config_path or DEFAULT_CONFIG_PATH
    if not path.is_file():
        raise ConfigError(f"設定ファイルがありません: {path}")

    with path.open("rb") as fh:
        raw = tomllib.load(fh)

    server_raw = _require_mapping(raw.get("server"), "server")
    host = _require_str(server_raw, "host", "server")
    port = _require_int(server_raw, "port", "server")
    if not (1 <= port <= 65535):
        raise ConfigError("[server] port は 1..65535 である必要があります")

    paths_raw = _require_mapping(raw.get("paths"), "paths")
    logic_dir = _resolve_path(_require_str(paths_raw, "logic_dir", "paths"))
    examples_dir = _resolve_path(_require_str(paths_raw, "examples_dir", "paths"))
    auth_dir_val = paths_raw.get("auth_dir", "data/auth")
    if not isinstance(auth_dir_val, str) or not auth_dir_val.strip():
        raise ConfigError("[paths] auth_dir は有効な文字列パスである必要があります")
    auth_dir = _resolve_path(auth_dir_val.strip())

    llm_raw = _require_mapping(raw.get("llm"), "llm")
    base_url = _require_str(llm_raw, "base_url", "llm")
    api_key_env = _require_str(llm_raw, "api_key_env", "llm")
    api_key = os.environ.get(api_key_env, "").strip()
    if not api_key:
        raise ConfigError(
            f"環境変数 {api_key_env} が未設定です。.env を確認してください"
        )

    conversion_raw = _require_mapping(llm_raw.get("conversion"), "llm.conversion")
    revision_raw = _require_mapping(llm_raw.get("logic_revision"), "llm.logic_revision")
    conversion = LlmRoleConfig(model=_require_str(conversion_raw, "model", "llm.conversion"))
    logic_revision = LlmRoleConfig(
        model=_require_str(revision_raw, "model", "llm.logic_revision")
    )

    ui_raw = _require_mapping(raw.get("ui"), "ui")
    debounce_ms = _require_int(ui_raw, "debounce_ms", "ui")
    if debounce_ms < 0:
        raise ConfigError("[ui] debounce_ms は 0 以上である必要があります")

    return AppConfig(
        server=ServerConfig(host=host, port=port),
        llm=LlmConfig(
            base_url=base_url,
            api_key_env=api_key_env,
            api_key=api_key,
            conversion=conversion,
            logic_revision=logic_revision,
        ),
        paths=PathsConfig(
            logic_dir=logic_dir,
            examples_dir=examples_dir,
            auth_dir=auth_dir,
        ),
        ui=UiConfig(debounce_ms=debounce_ms),
        config_path=path,
    )
