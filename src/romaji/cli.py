"""CLI: 変換ロジックの一覧・表示・復元。"""

from __future__ import annotations

import argparse
import sys

from romaji.config import ConfigError, load_config
from romaji.logic import LogicError, LogicStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="romaji", description="ローマ字変換アプリ用 CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("logic-list", help="保存済みロジック版を一覧表示")
    show = sub.add_parser("logic-show", help="現行または指定版のロジックを表示")
    show.add_argument("--version", help="版 ID（省略時は現行）")

    restore = sub.add_parser("logic-restore", help="指定版のロジックを現行に復元")
    restore.add_argument("version_id", help="復元する版 ID（例: v20260811T070000Z）")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_config()
    except ConfigError as exc:
        print(f"設定エラー: {exc}", file=sys.stderr)
        return 2

    store = LogicStore(config.paths.logic_dir)
    store.ensure_initialized()

    try:
        if args.command == "logic-list":
            print(f"現行版: {store.current_version_id()}")
            versions = store.list_versions()
            if not versions:
                print("(履歴なし)")
                return 0
            for item in versions:
                label = f" ({item.label})" if item.label else ""
                marker = " *" if item.version_id == store.current_version_id() else ""
                print(f"- {item.version_id}{label}{marker}")
            return 0

        if args.command == "logic-show":
            if args.version:
                print(store.read_version(args.version), end="")
            else:
                print(f"# version: {store.current_version_id()}")
                print(store.read_current(), end="")
            return 0

        if args.command == "logic-restore":
            new_id = store.restore(args.version_id)
            print(f"復元しました。新しい現行版 ID: {new_id}")
            return 0
    except LogicError as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        return 1

    parser.error(f"未知のコマンド: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
