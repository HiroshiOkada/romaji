# romaji

ローマ字入力を LLM（OpenRouter など OpenAI 互換 API）で、読みやすい日本語文に変換する自分専用 Web アプリです。

左ペインに入力したローマ字をそのまま残し、右ペインに変換結果を表示します。変換のルールは「変換ロジック」（LLM への指示文）として持ち、人間が直した確定例から後で改訂できます。

```text
左ペイン: konnichiwa, kyou wa ii tenki desu ne.
右ペイン: こんにちは、今日はいい天気ですね。
```

## 動機

かな入力や IME を使わずに、ローマ字を打つだけで自然な日本語文を作りたい、という個人の用途のために作っています。変換の質は LLM への指示文（ロジック）次第なので、変換結果をおかしいと感じたら手で直して確定し、確定例が貯まったところでロジックを改訂する、という改善ループを回せます。

## 特徴

- 入力停止後に自動変換（debounce。既定 800ms、`config.toml` で変更可）
- 変換結果を右ペインで編集可能
- **admin / guest ログイン認証**:
  - `admin`: フル機能（変換・確定保存・ロジック更新）
  - `guest`: 変換機能のみ（履歴保存・ロジック更新は無効）
- **確定／保存** で学習用の入出力だけを永続化（下書きはブラウザ／セッションのみ）
- **ロジック更新** で確定例から指示文を改訂（確認なしで即反映、過去版へ復元可）
- **コピーして次へ** ボタンで、変換結果のクリップボードへのコピーと入力欄クリアを一度に行う
- パスワードは PBKDF2（ソルト付き 100,000 回反復）でハッシュ化して保存
- 設定は TOML、API キーは `.env`

## 動作の仕組み

```text
[ブラウザ] ローマ字入力
    |  入力停止 (debounce) 後に POST /api/convert
    v
[FastAPI サーバ] 認証チェック → 現行ロジック (data/logic/current.md) を読む
    |  ロジック＋入力を OpenAI 互換 API に送信
    v
[LLM] 日本語文を生成
    |  右ペインに表示（SSE ストリーミング対応）
    v
[確定／保存] 入出力ペアを data/examples/ に記録
[ロジック更新] 確定例から指示文を改訂 → 新しい版として data/logic/versions/ に保存
```

通常の入力・変換・編集はどこにも残りません。ディスクに書き込まれるのは **確定／保存** と **ロジック更新**（および CLI での復元）だけです。

## 必要要件

- Python 3.14 以上
- [uv](https://docs.astral.sh/uv/)
- OpenAI 互換 API のキー（例: OpenRouter）

## セットアップ

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

CLI から `admin` および `guest` のパスワードを、20 文字の英数字からなる安全なランダム文字列として発行します。発行されたパスワードは一度だけ画面に出力されるので、手元に控えてください。

再発行時は単純な上書き保存となります（旧パスワードは無効化されます）。

```bash
uv run romaji issue-password admin
uv run romaji issue-password guest
```

パスワードは `data/auth/` 配下にソルト付きハッシュ（PBKDF2-SHA256、100,000 反復）として保存されます。平文はどこにも残りません。

### 設定ファイル

| ファイル | 内容 | Git |
|----------|------|-----|
| `.env` | API キー本体 | コミットしない |
| `config.toml` | host/port、モデル、`api_key_env`、パス、debounce など | コミットしてよい |

`config.toml` の要点:

| キー | 説明 |
|------|------|
| `[server] host` / `port` | **必須**（コード側デフォルトなし。未設定だと起動失敗する） |
| `[paths] logic_dir` | ロジックの保存先（既定: `data/logic`） |
| `[paths] examples_dir` | 確定例の保存先（既定: `data/examples`） |
| `[paths] auth_dir` | 認証情報の保存先（既定: `data/auth`） |
| `[llm] base_url` | OpenAI 互換 API のベース URL |
| `[llm] api_key_env` | キーを読む環境変数名（既定例: `LLM_INPUT_API_KEY`） |
| `[llm.conversion] model` | 変換用モデル（暫定。完成後の実測で確定予定） |
| `[llm.logic_revision] model` | ロジック改訂用モデル（変換用より高度なものを使う想定） |
| `[ui] debounce_ms` | 入力停止後、自動変換までの待機時間（ミリ秒） |

よくあるローカル LLM ポート（`11434`, `1234`, `8080`, `8000`, `7860`, `5000`, `3000`）は避け、例として `127.0.0.1:18765` を使っています。

## 起動

```bash
uv run romaji-server
```

ブラウザで `http://127.0.0.1:18765`（`config.toml` の値）を開きます。

ログインフォームが表示されるので、セットアップ時に発行した `admin` または `guest` のパスワードでログインします。

### 外出先からの利用

外出先からは、サーバー側で起動したまま SSH ポートフォワードで手元に持ってくると使えます。

```bash
ssh -L 18765:127.0.0.1:18765 user@your-server
```

手元のブラウザで `http://127.0.0.1:18765` を開けば、サーバー上のアプリにそのままアクセスできます。サーバーは `127.0.0.1` のみでリッスンする設定を推奨します（インターネットに直接公開しない）。

## 使い方（Web）

1. 左にローマ字を入力する → 入力が途切れると自動変換
2. 右の結果を必要なら手で直す
3. **確定／保存** … `data/examples/` に JSON で記録（admin のみ）
4. 例が貯まったら **ロジック更新** … 高度モデルが指示文を改訂し、即現行化（admin のみ）

その他の操作:

- **コピーして次へ** … 変換結果をクリップボードにコピーし、左右のペインをクリアします。連続して変換→貼り付けを繰り返すときに使います。
- **ログアウト** … ユーザーバーからセッションを終了します。

`guest` でログインした場合、確定／保存・ロジック更新のボタンは無効化されます（変換だけ可能です）。

画面下部に現行ロジックの版 ID（例: `v20260811T073007Z`）が表示されます。

## 変換ロジックについて

変換ロジックとは、LLM に渡す指示文（システムプロンプト）のことです。現行版の内容は `data/logic/current.md` にあり、たとえば次のような方針を含みます。

- 入力の意味・情報量・構成を保ったまま日本語へ変換する（依頼に答えない）
- 固有名詞・コマンド・URL・コード記法は正確に保持する
- 原文の文体・丁寧さを保ち、自然な漢字かな交じりに整える

この指示文は手で編集するものではありません。**確定／保存** した例から **ロジック更新** で自動改訂するか、後述の `logic-restore` で過去版に戻すことで変化させます。

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

復元後の内容も新しい版として履歴に残ります（履歴は失われません）。

## HTTP API リファレンス

認証が必要なエンドポイントは、`POST /api/auth/login` で取得したセッショントークンを Cookie または `Authorization` ヘッダで送ります。

| メソッド | パス | 認証 | 説明 |
|----------|------|------|------|
| GET | `/api/health` | 不要 | 動作確認 |
| POST | `/api/auth/login` | 不要 | ログイン（セッショントークン発行） |
| POST | `/api/auth/logout` | 不要 | ログアウト |
| GET | `/api/auth/me` | 不要 | 現在のユーザー取得（未ログインは `null`） |
| GET | `/api/ui-config` | ログイン必須 | debounce などの UI 設定 |
| GET | `/api/logic` | ログイン必須 | 現行ロジックの版 ID と本文 |
| POST | `/api/convert` | ログイン必須 | ローマ字を日本語へ変換 |
| POST | `/api/convert/stream` | ログイン必須 | 同上（SSE ストリーミング） |
| POST | `/api/confirm` | admin のみ | 確定例の保存 |
| POST | `/api/logic/update` | admin のみ | 確定例からロジックを改訂 |

```bash
# 例: ログインして変換する
curl -s -X POST http://127.0.0.1:18765/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username": "admin", "password": "..."}'
```

## CLI リファレンス

| コマンド | 説明 |
|----------|------|
| `romaji logic-list` | 現行版 ID と保存済みロジック版の一覧表示 |
| `romaji logic-show` | 現行ロジックの本文表示 |
| `romaji logic-show --version <ID>` | 指定版の本文表示 |
| `romaji logic-restore <ID>` | 指定版を現行に復元（新規版として履歴に残る） |
| `romaji issue-password admin` | admin のパスワードを発行・上書き |
| `romaji issue-password guest` | guest のパスワードを発行・上書き |

## データの置き場

```text
data/
  logic/
    current.md              # 現行指示文
    current_version.txt     # 現行版 ID
    versions/               # 履歴
  examples/                 # 確定／保存した入出力 JSON
  auth/                     # パスワードハッシュ（PBKDF2）
config.toml
.env
```

通常の入力・変換・編集は永続化しません。**確定／保存** と **ロジック更新**（および CLI 復元）だけがディスクに残ります。

バックアップするときは `data/` ディレクトリ全体をコピーすれば十分です（`.env` の API キーは別途管理してください）。

## ソースコード構成

```text
src/romaji/
  app.py       # FastAPI アプリ・HTTP API・静的ファイル配信
  auth.py      # 認証・ユーザー管理・パスワード発行
  cli.py       # CLI エントリポイント
  config.py    # config.toml の読み込み
  llm.py       # OpenAI 互換 API クライアント
  logic.py     # ロジック（指示文）の保存・版管理
  store.py     # 確定例の保存
static/        # Web UI（HTML / CSS / JS）
tests/         # 単体テスト・統合テスト
```

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
