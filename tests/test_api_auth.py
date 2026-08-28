"""API の認証・認可エンドポイントのテスト。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from romaji.app import create_app, get_config
from romaji.auth import UserStore
from romaji.config import load_config
from romaji.logic import LogicStore


@pytest.fixture
def app_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_path = tmp_path / "config.toml"
    auth_dir = tmp_path / "auth"
    logic_dir = tmp_path / "logic"
    examples_dir = tmp_path / "examples"

    config_path.write_text(
        f"""
[server]
host = "127.0.0.1"
port = 18765

[paths]
logic_dir = "{logic_dir.as_posix()}"
examples_dir = "{examples_dir.as_posix()}"
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

    cfg = load_config(config_path, load_env=False)
    monkeypatch.setattr("romaji.app.get_config", lambda: cfg)

    # Initialize logic store
    logic_store = LogicStore(logic_dir)
    logic_store.ensure_initialized()

    # Create user store and issue passwords
    user_store = UserStore(auth_dir)
    admin_pw = user_store.issue_password("admin")
    guest_pw = user_store.issue_password("guest")

    app = create_app()
    client = TestClient(app)
    return client, admin_pw, guest_pw


def test_unauthenticated_access(app_client) -> None:
    client, _, _ = app_client

    # Health check is public
    res = client.get("/api/health")
    assert res.status_code == 200

    # /api/auth/me returns authenticated: False
    res = client.get("/api/auth/me")
    assert res.status_code == 200
    assert res.json() == {"authenticated": False, "username": None, "role": None}

    # Protected endpoints return 401
    assert client.get("/api/ui-config").status_code == 401
    assert client.get("/api/logic").status_code == 401
    assert client.post("/api/convert", json={"text": "test"}).status_code == 401
    assert client.post("/api/confirm", json={"input_text": "a", "confirmed_output": "あ"}).status_code == 401
    assert client.post("/api/logic/update").status_code == 401


def test_login_failure_and_success(app_client) -> None:
    client, admin_pw, guest_pw = app_client

    # Wrong password
    res = client.post("/api/auth/login", json={"username": "admin", "password": "wrongpassword"})
    assert res.status_code == 401

    # Non-existent user
    res = client.post("/api/auth/login", json={"username": "unknown", "password": "any"})
    assert res.status_code == 401

    # Successful admin login
    res = client.post("/api/auth/login", json={"username": "admin", "password": admin_pw})
    assert res.status_code == 200
    assert res.json() == {"username": "admin", "role": "admin"}
    assert "romaji_session" in client.cookies

    # /api/auth/me after login
    res = client.get("/api/auth/me")
    assert res.status_code == 200
    assert res.json() == {"authenticated": True, "username": "admin", "role": "admin"}

    # Logout
    res = client.post("/api/auth/logout")
    assert res.status_code == 200
    assert client.get("/api/auth/me").json()["authenticated"] is False


def test_guest_permissions(app_client, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _, guest_pw = app_client

    # Login as guest
    res = client.post("/api/auth/login", json={"username": "guest", "password": guest_pw})
    assert res.status_code == 200
    assert res.json() == {"username": "guest", "role": "guest"}

    # /api/auth/me
    res = client.get("/api/auth/me")
    assert res.json() == {"authenticated": True, "username": "guest", "role": "guest"}

    # Guest can read logic and ui-config
    assert client.get("/api/ui-config").status_code == 200
    assert client.get("/api/logic").status_code == 200

    # Guest can convert (mocked LLM)
    monkeypatch.setattr("romaji.app.convert_romaji", lambda *args, **kwargs: "テスト")
    res = client.post("/api/convert", json={"text": "test"})
    assert res.status_code == 200
    assert res.json()["output"] == "テスト"

    # Guest CANNOT confirm/save (403 Forbidden)
    res = client.post(
        "/api/confirm",
        json={"input_text": "test", "auto_output": "テスト", "confirmed_output": "テスト"},
    )
    assert res.status_code == 403
    assert "管理者権限" in res.json()["detail"]

    # Guest CANNOT update logic (403 Forbidden)
    res = client.post("/api/logic/update")
    assert res.status_code == 403
    assert "管理者権限" in res.json()["detail"]


def test_admin_permissions(app_client) -> None:
    client, admin_pw, _ = app_client

    # Login as admin
    client.post("/api/auth/login", json={"username": "admin", "password": admin_pw})

    # Admin CAN confirm/save
    res = client.post(
        "/api/confirm",
        json={"input_text": "test", "auto_output": "テスト", "confirmed_output": "テスト確定"},
    )
    assert res.status_code == 200
    assert "id" in res.json()
