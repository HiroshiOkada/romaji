# romaji

ローマ字入力を LLM（OpenRouter など OpenAI 互換 API）で、読みやすい日本語文に変換する自分専用 Web アプリです。

左ペインに入力したローマ字をそのまま残し、右ペインに変換結果を表示します。変換のルールは「変換ロジック」（LLM への指示文）として持ち、人間が直した確定例から後で改訂できます。

## 特徴

- 入力停止後に自動変換（debounce）
- 変換結果を右ペインで編集可能
- **admin / guest ログイン認証**:
  - `admin`: フル機能（変換・確定保存・ロジック更新）
  - `guest`: 変換機能のみ（履歴保存・ロジック更新は無効）
- **確定／保存** で学習用の入出力だけを永続化（下書きはブラウザ／セッションのみ）
- **ロジック更新** で確定例から指示文を改訂（確認なしで即反映、過去版へ復元可）
- 設定は TOML、API キーは `.env`

## 準備

```bash
cp .env.example .env
# .env 例:
# LLM_INPUT_API_KEY=sk-or-v1-...
uv sync

# パスワードの発行 (admin / guest)
uv run romaji issue-password admin
uv run romaji issue-password guest
```

### パスワードの発行・再発行

CLI から `admin` および `guest` のパスワードを安全なランダム文字列として発行します。再発行時は単純な上書き保存となります。

```bash
uv run romaji issue-password admin
uv run romaji issue-password guest
```


### 設定ファイル

| ファイル | 内容 | Git |
|----------|------|-----|
| `.env` | API キー本体 | コミットしない |
| `config.toml` | host/port、モデル、`api_key_env`、パス、debounce など | コミットしてよい |

`config.toml` の要点:

- `[server] host` / `port` … **必須**（コード側デフォルトなし）
- `[llm] api_key_env` … キーを読む環境変数名（既定例: `LLM_INPUT_API_KEY`）
- `[llm.conversion] model` … 変換用（暫定。完成後の実測で確定予定）
- `[llm.logic_revision] model` … ロジック改訂用

よくあるローカル LLM ポート（`11434`, `1234`, `8080`, `8000`, `7860`, `5000`, `3000`）は避け、例として `127.0.0.1:18765` を使っています。

## 起動

```bash
uv run romaji-server
```

ブラウザで `http://127.0.0.1:18765`（`config.toml` の値）を開きます。

外出先からは、サーバー側で起動したまま SSH ポートフォワードで手元に持ってくると使えます。

```bash
ssh -L 18765:127.0.0.1:18765 user@your-server
```

## 使い方（Web）

1. 左にローマ字を入力する → 入力が途切れると自動変換
2. 右の結果を必要なら手で直す
3. **確定／保存** … `data/examples/` に JSON で記録
4. 例が貯まったら **ロジック更新** … 高度モデルが指示文を改訂し、即現行化

画面下部に現行ロジックの版 ID（例: `v20260811T073007Z`）が表示されます。

## ロジックの確認方法

変換に使われている指示文は、次のどれかで確認できます。

### 1. CLI（おすすめ）

```bash
# 現行版 ID と履歴一覧
uv run romaji logic-list

# 現行ロジック本文
uv run romaji logic-show

# 過去版の本文
uv run romaji logic-show --version v20260811T073007Z
```

### 2. ファイルを直接見る

| パス | 内容 |
|------|------|
| `data/logic/current.md` | いま使っている指示文 |
| `data/logic/current_version.txt` | 現行の版 ID |
| `data/logic/versions/*.md` | 過去スナップショット |

### 3. HTTP API（サーバー起動中）

```bash
curl -s http://127.0.0.1:18765/api/logic
```

`version_id` と `text`（指示文全文）が返ります。

> Web UI にはロジック全文ビューアはまだありません。版 ID の表示と、上記 CLI／ファイル／API で確認してください。

## ロジックの復元

更新は確認なしで反映されます。戻したいときは CLI で復元します。

```bash
uv run romaji logic-list
uv run romaji logic-restore v20260811T073007Z
```

復元後の内容も新しい版として履歴に残ります。

## データの置き場

```text
data/
  logic/
    current.md              # 現行指示文
    current_version.txt     # 現行版 ID
    versions/               # 履歴
  examples/                 # 確定／保存した入出力 JSON
config.toml
.env
```

通常の入力・変換・編集は永続化しません。**確定／保存** と **ロジック更新**（および CLI 復元）だけがディスクに残ります。

## テスト

```bash
# 単体テストのみ
uv run pytest tests/test_logic.py tests/test_config.py

# すべて（実 API の統合テストを含む）
uv run pytest
```

統合テストは短いローマ字（`konnichiwa`）だけを実 API に送ります。`.env` のキーが無い場合はスキップされます。

## 開発メモ

- 作業ルールは `AGENTS.md`
- フェーズ 000 のゴール／実装計画は `.task/`
- 変換モデルの最終選定は、ある程度使ったあとの実測で行う想定です
