"""generate default Slack workspace config if missing"""
from pathlib import Path

CONFIG_DIR = Path("config/slack")
WORKSPACE_FILE = Path(CONFIG_DIR, "workspace.py")
TEMPLATE_PATH = Path(__file__).with_name("_workspace_template.py")


def _load_template() -> str:
    """Return the text of the workspace template shipped with the package."""
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(
            f"Template file missing: {TEMPLATE_PATH}. Did you delete it?"
        )
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def ensure_workspace_config() -> None:
    """Create default workspace config if it doesn't exist."""
    # Ensure package directories exist
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    (Path("config") / "__init__.py").write_text("", encoding="utf-8")
    (CONFIG_DIR / "__init__.py").write_text("", encoding="utf-8")

    if WORKSPACE_FILE.exists():
        print(f"✅ Config file already exists at {WORKSPACE_FILE}")
        return

    WORKSPACE_FILE.write_text(_load_template(), encoding="utf-8")
    print(f"🎉 Created default workspace config at {WORKSPACE_FILE}")
    print(
        "⚠️  Please edit the file to include your actual workspace URL and team ID "
        "before running Slack extract scripts."
    )


def main() -> None:
    """Main function."""
    ensure_workspace_config()


if __name__ == "__main__":
    main()
