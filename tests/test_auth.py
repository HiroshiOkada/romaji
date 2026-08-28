"""認証・パスワード管理・セッショントークンの単体テスト。"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from romaji.auth import (
    ALLOWED_USERS,
    AuthError,
    SessionManager,
    UserStore,
    generate_secure_password,
    hash_password,
    verify_password_hash,
)


def test_generate_secure_password() -> None:
    pw1 = generate_secure_password()
    pw2 = generate_secure_password()
    assert len(pw1) >= 20
    assert len(pw2) >= 20
    assert pw1 != pw2
    assert any(c.isupper() for c in pw1) or any(c.islower() for c in pw1)
    assert any(c.isdigit() for c in pw1) or any(c.isalnum() for c in pw1)


def test_hash_and_verify_password() -> None:
    password = "SuperSecretPassword123"
    salt_hex, hash_hex = hash_password(password)
    assert verify_password_hash(password, salt_hex, hash_hex) is True
    assert verify_password_hash("WrongPassword", salt_hex, hash_hex) is False
    assert verify_password_hash(password, "invalid_salt", hash_hex) is False


def test_user_store_issue_and_verify(tmp_path: Path) -> None:
    store = UserStore(tmp_path / "auth")
    assert store.has_user("admin") is False
    assert store.has_user("guest") is False

    # Issue password for admin
    pw_admin = store.issue_password("admin")
    assert isinstance(pw_admin, str)
    assert len(pw_admin) >= 20
    assert store.has_user("admin") is True
    assert store.verify_password("admin", pw_admin) is True
    assert store.verify_password("admin", "wrong") is False

    # Issue password for guest
    pw_guest = store.issue_password("guest")
    assert store.has_user("guest") is True
    assert store.verify_password("guest", pw_guest) is True
    assert pw_admin != pw_guest

    # Reject unsupported username
    with pytest.raises(AuthError, match="無効なユーザー名"):
        store.issue_password("root")

    assert store.verify_password("root", "any") is False


def test_user_store_overwrite_password(tmp_path: Path) -> None:
    store = UserStore(tmp_path / "auth")
    pw1 = store.issue_password("admin")
    assert store.verify_password("admin", pw1) is True

    # Re-issue overwrites previous password
    pw2 = store.issue_password("admin")
    assert pw1 != pw2
    assert store.verify_password("admin", pw1) is False
    assert store.verify_password("admin", pw2) is True


def test_session_manager_token_flow(tmp_path: Path) -> None:
    session_mgr = SessionManager(tmp_path / "auth", ttl_seconds=2)
    token = session_mgr.create_token("admin")
    assert isinstance(token, str)
    assert session_mgr.verify_token(token) == "admin"

    # Guest token
    guest_token = session_mgr.create_token("guest")
    assert session_mgr.verify_token(guest_token) == "guest"

    # Invalid token
    assert session_mgr.verify_token("invalid.token") is None
    assert session_mgr.verify_token("") is None

    # Tampered token
    tampered = token[:-4] + "aaaa"
    assert session_mgr.verify_token(tampered) is None


def test_session_manager_expiration(tmp_path: Path) -> None:
    session_mgr = SessionManager(tmp_path / "auth", ttl_seconds=1)
    token = session_mgr.create_token("admin")
    assert session_mgr.verify_token(token) == "admin"

    time.sleep(1.2)
    assert session_mgr.verify_token(token) is None
