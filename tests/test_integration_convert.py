"""実 API を使った最小の統合テスト。"""

from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv

from romaji.config import load_config
from romaji.llm import convert_romaji, create_client
from romaji.logic import LogicStore

load_dotenv()

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def has_api_key() -> bool:
    return bool(os.environ.get("LLM_INPUT_API_KEY", "").strip())


def test_real_convert_short_romaji(has_api_key: bool) -> None:
    if not has_api_key:
        pytest.skip("LLM_INPUT_API_KEY が未設定のためスキップ")

    config = load_config()
    logic = LogicStore(config.paths.logic_dir).read_current()
    client = create_client(config.llm)

    # 週額上限を意識し、ごく短い入力のみ
    output = convert_romaji(client, config, logic=logic, text="konnichiwa")
    assert isinstance(output, str)
    assert output.strip()
    # 日本語らしさの緩い確認（ひらがな/漢字が含まれること）
    assert any("\u3040" <= ch <= "\u30ff" or "\u4e00" <= ch <= "\u9fff" for ch in output)
