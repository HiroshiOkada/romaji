"""互換用エントリ。実体は romaji.app / romaji.cli を使う。"""

from romaji.app import run


def main() -> None:
    run()


if __name__ == "__main__":
    main()
