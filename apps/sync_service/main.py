from shared.config.settings import load_settings_from_env
from shared.errors.exceptions import ConfigError


def main() -> int:
    """CLI bootstrap for sync pipeline M1 foundation."""
    try:
        settings = load_settings_from_env()
    except ConfigError as exc:
        print(f"Configuration error: {exc}")
        return 2

    print("Sync service configuration loaded")
    print(f"repository_id={settings.repository_id}")
    print(f"source_root={settings.source_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
