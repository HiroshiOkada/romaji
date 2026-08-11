"""確定例の永続化。"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


@dataclass(frozen=True)
class ConfirmedExample:
    id: str
    created_at: str
    input_text: str
    auto_output: str
    confirmed_output: str
    logic_version_id: str


class StoreError(ValueError):
    """保存操作の失敗。"""


class ExampleStore:
    def __init__(self, examples_dir: Path) -> None:
        self.examples_dir = examples_dir

    def ensure_initialized(self) -> None:
        self.examples_dir.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        *,
        input_text: str,
        auto_output: str,
        confirmed_output: str,
        logic_version_id: str,
    ) -> ConfirmedExample:
        self.ensure_initialized()
        if not input_text.strip():
            raise StoreError("入力が空です")
        if not confirmed_output.strip():
            raise StoreError("確定文が空です")

        example = ConfirmedExample(
            id=uuid4().hex,
            created_at=datetime.now(timezone.utc).isoformat(),
            input_text=input_text,
            auto_output=auto_output,
            confirmed_output=confirmed_output,
            logic_version_id=logic_version_id,
        )
        path = self.examples_dir / f"{example.created_at[:19].replace(':', '')}_{example.id}.json"
        path.write_text(
            json.dumps(asdict(example), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return example

    def list_examples(self) -> list[ConfirmedExample]:
        self.ensure_initialized()
        examples: list[ConfirmedExample] = []
        for path in sorted(self.examples_dir.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            examples.append(ConfirmedExample(**data))
        return examples
