# romaji

ローマ字入力を LLM（OpenRouter 等の OpenAI 互換 API）で日本語文に変換する、自分専用の Web アプリです。

## 準備

```bash
cp .env.example .env
# .env に API キーを設定（例: LLM_INPUT_API_KEY=...）
uv sync
```

`config.toml` で host / port / モデルなどを設定します。`[server] host` と `port` にコード側デフォルトはありません。

## 起動

```bash
uv run romaji-server
```

ブラウザで `http://127.0.0.1:18765`（`config.toml` の値）を開きます。

## 使い方

- 左ペインにローマ字を入力すると、入力停止後に自動変換されます
- 右ペインの結果は編集できます
- **確定／保存**: 学習用に入出力を `data/examples/` へ保存
- **ロジック更新**: 確定例を使って変換指示文を改訂（確認なしで即反映）

## ロジックの復元（CLI）

```bash
uv run romaji logic-list
uv run romaji logic-show
uv run romaji logic-show --version vXXXXXXXX
uv run romaji logic-restore vXXXXXXXX
```

## テスト

```bash
uv run pytest
```

統合テストは実 API を呼び出します（短い入力のみ）。
