import sys

MISSING_CLI_EXTRA = (
    "The bilkatogo command needs the CLI extra: pip install 'bilkatogo[cli]' "
    "or uvx --from 'bilkatogo[cli]' bilkatogo"
)


def main() -> None:
    try:
        from .cli import main as cli_main
    except ModuleNotFoundError as err:
        if err.name != "typer":
            raise
        print(MISSING_CLI_EXTRA, file=sys.stderr)
        sys.exit(1)
    cli_main()


if __name__ == "__main__":
    main()
