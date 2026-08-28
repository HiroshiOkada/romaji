"""FastAPI アプリケーション。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from romaji.auth import ALLOWED_USERS, SessionManager, UserStore
from romaji.config import AppConfig, ConfigError, load_config
from romaji.llm import LlmError, convert_romaji, convert_romaji_stream, create_client, revise_logic
from romaji.logic import LogicError, LogicStore
from romaji.store import ExampleStore, StoreError

ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = ROOT / "static"


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    return load_config()


def get_logic_store() -> LogicStore:
    store = LogicStore(get_config().paths.logic_dir)
    store.ensure_initialized()
    return store


def get_example_store() -> ExampleStore:
    store = ExampleStore(get_config().paths.examples_dir)
    store.ensure_initialized()
    return store


def get_user_store() -> UserStore:
    store = UserStore(get_config().paths.auth_dir)
    store.ensure_initialized()
    return store


def get_session_manager() -> SessionManager:
    return SessionManager(get_config().paths.auth_dir)


def extract_token(request: Request) -> str | None:
    token = request.cookies.get("romaji_session")
    if token:
        return token
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    return None


def get_current_user_optional(request: Request) -> str | None:
    token = extract_token(request)
    if not token:
        return None
    session_mgr = get_session_manager()
    return session_mgr.verify_token(token)


def get_current_user(request: Request) -> str:
    user = get_current_user_optional(request)
    if not user:
        raise HTTPException(status_code=401, detail="認証が必要です。ログインしてください。")
    return user


def require_admin(request: Request) -> str:
    user = get_current_user(request)
    if user != "admin":
        raise HTTPException(status_code=403, detail="管理者権限が必要です。")
    return user


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    username: str
    role: str


class MeResponse(BaseModel):
    authenticated: bool
    username: str | None = None
    role: str | None = None


class ConvertRequest(BaseModel):
    text: str = Field(default="")


class ConvertResponse(BaseModel):
    output: str
    logic_version_id: str


class ConfirmRequest(BaseModel):
    input_text: str
    auto_output: str = ""
    confirmed_output: str


class ConfirmResponse(BaseModel):
    id: str
    logic_version_id: str


class LogicResponse(BaseModel):
    version_id: str
    text: str


class LogicUpdateResponse(BaseModel):
    version_id: str
    text: str
    example_count: int


class UiConfigResponse(BaseModel):
    debounce_ms: int


def create_app() -> FastAPI:
    app = FastAPI(title="romaji", version="0.1.0")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/auth/login", response_model=LoginResponse)
    def login(body: LoginRequest, response: Response) -> LoginResponse:
        user_store = get_user_store()
        if not user_store.verify_password(body.username, body.password):
            raise HTTPException(status_code=401, detail="ユーザー名またはパスワードが正しくありません")
        session_mgr = get_session_manager()
        token = session_mgr.create_token(body.username)
        response.set_cookie(
            key="romaji_session",
            value=token,
            httponly=True,
            samesite="lax",
            max_age=7 * 86400,
            path="/",
        )
        return LoginResponse(username=body.username, role=body.username)

    @app.post("/api/auth/logout")
    def logout(response: Response) -> dict[str, str]:
        response.delete_cookie(key="romaji_session", path="/")
        return {"status": "ok"}

    @app.get("/api/auth/me", response_model=MeResponse)
    def auth_me(request: Request) -> MeResponse:
        user = get_current_user_optional(request)
        if user:
            return MeResponse(authenticated=True, username=user, role=user)
        return MeResponse(authenticated=False, username=None, role=None)

    @app.get("/api/ui-config", response_model=UiConfigResponse)
    def ui_config() -> UiConfigResponse:
        return UiConfigResponse(debounce_ms=get_config().ui.debounce_ms)

    @app.get("/api/logic", response_model=LogicResponse)
    def get_logic() -> LogicResponse:
        store = get_logic_store()
        return LogicResponse(version_id=store.current_version_id(), text=store.read_current())

    @app.post("/api/convert", response_model=ConvertResponse)
    def convert(body: ConvertRequest) -> ConvertResponse:
        config = get_config()
        logic_store = get_logic_store()
        client = create_client(config.llm)
        try:
            output = convert_romaji(
                client,
                config,
                logic=logic_store.read_current(),
                text=body.text,
            )
        except LlmError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return ConvertResponse(
            output=output,
            logic_version_id=logic_store.current_version_id(),
        )

    @app.post("/api/convert/stream")
    def convert_stream(body: ConvertRequest) -> StreamingResponse:
        config = get_config()
        logic_store = get_logic_store()
        client = create_client(config.llm)

        def event_iter():
            try:
                for chunk in convert_romaji_stream(
                    client,
                    config,
                    logic=logic_store.read_current(),
                    text=body.text,
                ):
                    yield chunk
            except LlmError as exc:
                yield f"\n[ERROR] {exc}"

        return StreamingResponse(event_iter(), media_type="text/plain; charset=utf-8")

    @app.post("/api/confirm", response_model=ConfirmResponse)
    def confirm(body: ConfirmRequest) -> ConfirmResponse:
        logic_store = get_logic_store()
        example_store = get_example_store()
        version_id = logic_store.current_version_id()
        try:
            saved = example_store.save(
                input_text=body.input_text,
                auto_output=body.auto_output,
                confirmed_output=body.confirmed_output,
                logic_version_id=version_id,
            )
        except StoreError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return ConfirmResponse(id=saved.id, logic_version_id=version_id)

    @app.post("/api/logic/update", response_model=LogicUpdateResponse)
    def update_logic() -> LogicUpdateResponse:
        config = get_config()
        logic_store = get_logic_store()
        example_store = get_example_store()
        examples = example_store.list_examples()
        if not examples:
            raise HTTPException(status_code=400, detail="確定例がありません")

        client = create_client(config.llm)
        try:
            revised = revise_logic(
                client,
                config,
                current_logic=logic_store.read_current(),
                examples=examples,
            )
            version_id = logic_store.update(revised, label="llm-revision")
        except (LlmError, LogicError) as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        return LogicUpdateResponse(
            version_id=version_id,
            text=logic_store.read_current(),
            example_count=len(examples),
        )

    @app.get("/")
    def index() -> FileResponse:
        index_path = STATIC_DIR / "index.html"
        if not index_path.is_file():
            raise HTTPException(status_code=404, detail="static/index.html がありません")
        return FileResponse(index_path)

    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    return app


app = create_app()


def run() -> None:
    try:
        config = load_config()
    except ConfigError as exc:
        raise SystemExit(f"設定エラー: {exc}") from exc

    # 設定変更を拾えるようキャッシュをクリア
    get_config.cache_clear()
    uvicorn.run(
        "romaji.app:app",
        host=config.server.host,
        port=config.server.port,
        reload=False,
    )


if __name__ == "__main__":
    run()
