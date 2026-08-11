"""変換ロジック（指示文）の版管理。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

INITIAL_LOGIC = """\
あなたはローマ字入力を、読みやすい自然な日本語の文章に変換するアシスタントです。

# 規則
- 入力の意味を保ちつつ、漢字かな交じりの日本語文にする。
- 固有名詞・製品名・略語（AI, NVIDIA, CUDA など）は適切に残す。
- 不要な説明や前置きは出さず、変換後の本文だけを返す。
- 句読点や空白は日本語として自然になるよう整える。
"""

# 例: v20260811T073007Z_initial.md / v20260811T073007123Z_update.md
VERSION_NAME_RE = re.compile(r"^(v\d{8}T\d{6,9}Z)(?:_(.+))?\.md$")


@dataclass(frozen=True)
class LogicVersion:
    version_id: str
    path: Path
    label: str | None = None


class LogicError(ValueError):
    """ロジック操作の失敗。"""


class LogicStore:
    def __init__(self, logic_dir: Path) -> None:
        self.logic_dir = logic_dir
        self.current_path = logic_dir / "current.md"
        self.versions_dir = logic_dir / "versions"
        self.meta_path = logic_dir / "current_version.txt"

    def ensure_initialized(self) -> None:
        self.logic_dir.mkdir(parents=True, exist_ok=True)
        self.versions_dir.mkdir(parents=True, exist_ok=True)
        if not self.current_path.is_file():
            self._write_new_version(INITIAL_LOGIC, label="initial")

    def current_version_id(self) -> str:
        self.ensure_initialized()
        if self.meta_path.is_file():
            value = self.meta_path.read_text(encoding="utf-8").strip()
            if value:
                return value
        return "unknown"

    def read_current(self) -> str:
        self.ensure_initialized()
        return self.current_path.read_text(encoding="utf-8")

    def read_version(self, version_id: str) -> str:
        self.ensure_initialized()
        target = self._find_version_file(version_id)
        if target is None:
            raise LogicError(f"版が見つかりません: {version_id}")
        return target.read_text(encoding="utf-8")

    def list_versions(self) -> list[LogicVersion]:
        self.ensure_initialized()
        versions: list[LogicVersion] = []
        for path in sorted(self.versions_dir.glob("v*.md"), reverse=True):
            match = VERSION_NAME_RE.match(path.name)
            if not match:
                continue
            versions.append(
                LogicVersion(
                    version_id=match.group(1),
                    path=path,
                    label=match.group(2),
                )
            )
        return versions

    def update(self, new_text: str, *, label: str = "update") -> str:
        """現行ロジックを置き換える。新しい内容を版として保存する。"""
        self.ensure_initialized()
        text = new_text.strip()
        if not text:
            raise LogicError("空のロジックは保存できません")
        return self._write_new_version(text, label=label)

    def restore(self, version_id: str) -> str:
        """指定版の内容を現行に戻す（復元内容が新しい現行版になる）。"""
        restored_text = self.read_version(version_id)
        return self.update(restored_text, label=f"restore-{version_id}")

    def _write_new_version(self, text: str, *, label: str) -> str:
        body = text if text.endswith("\n") else text + "\n"
        version_id = self._new_version_id()
        safe_label = self._safe_label(label)
        snapshot = self.versions_dir / f"{version_id}_{safe_label}.md"
        snapshot.write_text(body, encoding="utf-8")
        self.current_path.write_text(body, encoding="utf-8")
        self.meta_path.write_text(version_id + "\n", encoding="utf-8")
        return version_id

    def _find_version_file(self, version_id: str) -> Path | None:
        matches = sorted(self.versions_dir.glob(f"{version_id}*.md"))
        return matches[0] if matches else None

    def _new_version_id(self) -> str:
        for _ in range(50):
            version_id = self._timestamp()
            if not any(self.versions_dir.glob(f"{version_id}*")):
                return version_id
        raise LogicError("一意な版 ID を生成できませんでした")

    @staticmethod
    def _timestamp() -> str:
        now = datetime.now(timezone.utc)
        return now.strftime("v%Y%m%dT%H%M%S") + f"{now.microsecond // 1000:03d}Z"

    @staticmethod
    def _safe_label(label: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", label.strip())
        return cleaned.strip("-")[:60] or "update"
