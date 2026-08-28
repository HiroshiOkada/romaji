"""認証・ユーザー管理およびパスワード発行モジュール。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import string
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ALLOWED_USERS = {"admin", "guest"}
PASSWORD_LENGTH = 20
PASSWORD_ALPHABET = string.ascii_letters + string.digits
PBKDF2_ITERATIONS = 100_000


class AuthError(ValueError):
    """認証・ユーザー操作エラー。"""


def generate_secure_password(length: int = PASSWORD_LENGTH) -> str:
    """必要十分な強度を持つランダムパスワードを生成する。"""
    return "".join(secrets.choice(PASSWORD_ALPHABET) for _ in range(length))


def hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    """パスワードをソルト付きハッシュ化する。(salt_hex, hash_hex) を返す。"""
    if salt is None:
        salt = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return salt.hex(), key.hex()


def verify_password_hash(password: str, salt_hex: str, hash_hex: str) -> bool:
    """入力パスワードが保存されたソルト・ハッシュと一致するか検証する。"""
    try:
        salt = bytes.fromhex(salt_hex)
        expected_hash = bytes.fromhex(hash_hex)
    except ValueError:
        return False
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return hmac.compare_digest(key, expected_hash)


@dataclass(frozen=True)
class UserRecord:
    username: str
    salt: str
    password_hash: str
    updated_at: str


class UserStore:
    """ユーザー認証情報の永続化ストア。"""

    def __init__(self, auth_dir: Path) -> None:
        self.auth_dir = auth_dir
        self.users_file = auth_dir / "users.json"

    def ensure_initialized(self) -> None:
        self.auth_dir.mkdir(parents=True, exist_ok=True)

    def _load_data(self) -> dict[str, dict[str, str]]:
        if not self.users_file.is_file():
            return {}
        try:
            return json.loads(self.users_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise AuthError(f"ユーザー情報の読み込みに失敗しました: {exc}") from exc

    def _save_data(self, data: dict[str, dict[str, str]]) -> None:
        self.ensure_initialized()
        self.users_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def issue_password(self, username: str) -> str:
        """指定ユーザーのパスワードを新規発行・上書き保存し、平文パスワードを返す。"""
        if username not in ALLOWED_USERS:
            raise AuthError(
                f"無効なユーザー名です: {username}。許可されているユーザーは {', '.join(sorted(ALLOWED_USERS))} のみです。"
            )

        password = generate_secure_password()
        salt_hex, hash_hex = hash_password(password)

        data = self._load_data()
        data[username] = {
            "salt": salt_hex,
            "hash": hash_hex,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save_data(data)
        return password

    def verify_password(self, username: str, password: str) -> bool:
        """指定ユーザーのパスワードを検証する。"""
        if username not in ALLOWED_USERS or not password:
            return False

        data = self._load_data()
        record = data.get(username)
        if not record:
            return False

        salt_hex = record.get("salt", "")
        hash_hex = record.get("hash", "")
        if not salt_hex or not hash_hex:
            return False

        return verify_password_hash(password, salt_hex, hash_hex)

    def has_user(self, username: str) -> bool:
        """ユーザーのパスワードが設定済みか確認する。"""
        data = self._load_data()
        return username in data


class SessionManager:
    """HMAC署名付きセッショントークンの管理。"""

    def __init__(self, auth_dir: Path, ttl_seconds: int = 7 * 86400) -> None:
        self.auth_dir = auth_dir
        self.key_file = auth_dir / "session.key"
        self.ttl_seconds = ttl_seconds

    def ensure_secret_key(self) -> bytes:
        self.auth_dir.mkdir(parents=True, exist_ok=True)
        if self.key_file.is_file():
            try:
                key = self.key_file.read_bytes()
                if len(key) >= 32:
                    return key
            except OSError:
                pass
        key = secrets.token_bytes(32)
        self.key_file.write_bytes(key)
        return key

    def create_token(self, username: str) -> str:
        if username not in ALLOWED_USERS:
            raise AuthError(f"無効なユーザー名です: {username}")
        secret = self.ensure_secret_key()
        now = int(time.time())
        payload = {
            "sub": username,
            "iat": now,
            "exp": now + self.ttl_seconds,
        }
        payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode("ascii").rstrip("=")
        signature = hmac.new(secret, payload_b64.encode("ascii"), hashlib.sha256).digest()
        sig_b64 = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
        return f"{payload_b64}.{sig_b64}"

    def verify_token(self, token: str) -> str | None:
        if not token or "." not in token:
            return None
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_b64, sig_b64 = parts
        secret = self.ensure_secret_key()

        expected_sig = hmac.new(secret, payload_b64.encode("ascii"), hashlib.sha256).digest()
        padded_sig_b64 = sig_b64 + "=" * (-len(sig_b64) % 4)
        try:
            actual_sig = base64.urlsafe_b64decode(padded_sig_b64.encode("ascii"))
        except Exception:
            return None
        if not hmac.compare_digest(actual_sig, expected_sig):
            return None

        padded_payload_b64 = payload_b64 + "=" * (-len(payload_b64) % 4)
        try:
            payload_raw = base64.urlsafe_b64decode(padded_payload_b64.encode("ascii"))
            payload = json.loads(payload_raw.decode("utf-8"))
        except Exception:
            return None

        username = payload.get("sub")
        exp = payload.get("exp")
        if username not in ALLOWED_USERS or not isinstance(exp, (int, float)):
            return None
        if time.time() > exp:
            return None

        return username

