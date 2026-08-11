"""OpenAI 互換 API クライアント（OpenRouter 等）。"""

from __future__ import annotations

from collections.abc import Iterator

from openai import OpenAI

from romaji.config import AppConfig, LlmConfig
from romaji.store import ConfirmedExample


class LlmError(RuntimeError):
    """LLM 呼び出し失敗。"""


def create_client(llm: LlmConfig) -> OpenAI:
    return OpenAI(base_url=llm.base_url, api_key=llm.api_key)


def convert_romaji(
    client: OpenAI,
    config: AppConfig,
    *,
    logic: str,
    text: str,
) -> str:
    """ローマ字テキストを現行ロジックに従って日本語へ変換する。"""
    if not text.strip():
        return ""

    try:
        response = client.chat.completions.create(
            model=config.llm.conversion.model,
            messages=[
                {"role": "system", "content": logic},
                {"role": "user", "content": text},
            ],
            temperature=0.2,
        )
    except Exception as exc:  # noqa: BLE001 - SDK 例外をアプリ例外へ
        raise LlmError(f"変換 API 呼び出しに失敗しました: {exc}") from exc

    content = response.choices[0].message.content
    if not content:
        raise LlmError("変換結果が空でした")
    return content.strip()


def convert_romaji_stream(
    client: OpenAI,
    config: AppConfig,
    *,
    logic: str,
    text: str,
) -> Iterator[str]:
    """変換結果をストリーミングで返す。"""
    if not text.strip():
        return

    try:
        stream = client.chat.completions.create(
            model=config.llm.conversion.model,
            messages=[
                {"role": "system", "content": logic},
                {"role": "user", "content": text},
            ],
            temperature=0.2,
            stream=True,
        )
    except Exception as exc:  # noqa: BLE001
        raise LlmError(f"変換 API 呼び出しに失敗しました: {exc}") from exc

    for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta


REVISION_SYSTEM = """\
あなたはローマ字→日本語変換のための system 指示文を改訂する専門家です。
与えられた現行指示文と、人間が確定した入出力例（自動変換と確定文の差分を含む）を見て、
今後の変換品質が上がるよう指示文を更新してください。

出力規則:
- 新しい system 指示文の本文だけを返す
- 前置き、解説、コードフェンスは付けない
- 現行指示の有用な規則は残しつつ、確定例から学べる表記・文体・例外を具体的に足す
"""


def revise_logic(
    client: OpenAI,
    config: AppConfig,
    *,
    current_logic: str,
    examples: list[ConfirmedExample],
) -> str:
    """確定例を踏まえて変換ロジック（指示文）を改訂する。"""
    if not examples:
        raise LlmError("ロジック更新には確定例が1件以上必要です")

    example_blocks: list[str] = []
    for i, ex in enumerate(examples, start=1):
        example_blocks.append(
            "\n".join(
                [
                    f"## 例 {i}",
                    f"入力:\n{ex.input_text}",
                    f"自動変換:\n{ex.auto_output}",
                    f"確定文:\n{ex.confirmed_output}",
                    f"当時のロジック版: {ex.logic_version_id}",
                ]
            )
        )

    user_content = (
        "# 現行の変換指示文\n"
        f"{current_logic.strip()}\n\n"
        "# 確定例\n"
        + "\n\n".join(example_blocks)
        + "\n\n上記を踏まえ、更新後の変換指示文だけを出力してください。"
    )

    try:
        response = client.chat.completions.create(
            model=config.llm.logic_revision.model,
            messages=[
                {"role": "system", "content": REVISION_SYSTEM},
                {"role": "user", "content": user_content},
            ],
            temperature=0.3,
        )
    except Exception as exc:  # noqa: BLE001
        raise LlmError(f"ロジック改訂 API 呼び出しに失敗しました: {exc}") from exc

    content = response.choices[0].message.content
    if not content or not content.strip():
        raise LlmError("改訂結果が空でした")
    return content.strip()
