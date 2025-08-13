"""Generate default Slack workspace config if missing"""
from pathlib import Path
from growthkit.utils.style import ansi

CONFIG_DIR = Path("config/slack")
WORKSPACE_FILE = Path(CONFIG_DIR, "workspace.json")


def _template_json() -> str:
    """Return default JSON content for the workspace config."""
    return (
        '{\n'
        '  "note": "Enter your workspace URL and team ID here.",\n'
        '  "url": "https://YOUR_WORKSPACE.slack.com",\n'
        '  "team_id": "TXXXXXXXX"\n'
        '}\n'
    )


def ensure_workspace_config() -> None:
    """Create default workspace config if it doesn't exist."""
    # Ensure package directories exist
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    (Path("config") / "__init__.py").write_text("", encoding="utf-8")
    (CONFIG_DIR / "__init__.py").write_text("", encoding="utf-8")

    if WORKSPACE_FILE.exists():
        print(f"✅ Config file already exists: {ansi.grey}{WORKSPACE_FILE}{ansi.reset}")
        return

    WORKSPACE_FILE.write_text(_template_json(), encoding="utf-8")
    print(f"🎉 Created default workspace config at {ansi.green}{WORKSPACE_FILE}{ansi.reset}")
    print(
        "⚠️  Please edit the file to include your actual workspace URL and team ID "
        "before running Slack extract scripts."
    )


def main() -> None:
    """Main function."""
    ensure_workspace_config()


if __name__ == "__main__":
    main()
