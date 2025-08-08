"""
Configuration engine: load dataclass defaults first, then merge INI overrides.
On first run, a template `config.ini` mirroring the dataclass defaults is written
at the repository root so the user has something to tweak.

This module also includes TokenManager for handling dynamic token storage.
"""

import json
import sys
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import asdict
from configparser import ConfigParser
from datetime import datetime, timezone

from growthkit.connectors.facebook.schema import Config, Token, User, Page
from growthkit.utils.style import ansi
from growthkit.utils.logs import report

# Initialize logger
logger = report.settings(__file__)

# Paths
ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG = Path(ROOT, "config", "facebook")
INI_FILE = Path(CONFIG, "facebook.ini")


# Helpers
def _cast(template_value, raw: str):
    """Cast the raw INI string back to the dataclass field type."""
    # Handle None/empty values for Optional fields
    if raw.strip() in ('', 'None', 'none', 'null'):
        return None

    # Handle None template values (Optional fields)
    if template_value is None:
        # For Optional fields, try to cast as string by default
        # More sophisticated type inference could be added here
        return raw

    t = type(template_value)
    return Path(raw) if t is Path else t(raw)


def _create_config(path: Path) -> None:
    """Create a user-friendly initial config with only fields users should fill out."""
    cp = ConfigParser()

    # App section - required fields users must configure
    cp['app'] = {
        'app_id': 'YOUR_APP_ID_HERE',
        'app_secret': 'YOUR_APP_SECRET_HERE',
        'api_version': 'v23.0'
    }

    # Token section - required fields short-lived token users must provide
    cp['token'] = {
        'access_token': 'SHORT_LIVED_TOKEN_HERE'
    }

    # Page section - optional page info users can specify
    cp['page'] = {
        'page_id': 'FACEBOOK_PAGE_ID_HERE',
        'page_name': 'FACEBOOK_PAGE_NAME_HERE'
    }

    with path.open("w", encoding="utf-8") as f:
        cp.write(f)


# Public API
def load(path: Optional[Path] = None) -> Config:
    """Load configuration from INI file and return Config object."""
    cfg = Config()
    ini = path or INI_FILE

    # Create user-friendly template on first run with only fields users should fill out
    if not ini.exists():
        _create_config(ini)

        # Prompt user to fill in the configuration before proceeding
        print(f"\n{ansi.yellow}🔧 First-time setup detected!{ansi.reset}")
        print(f"A new config file has been created at: {ansi.cyan}{ini.relative_to(ROOT)}{ansi.reset}")
        print(f"\n{ansi.yellow}Please edit this file with your Facebook app credentials:{ansi.reset}")
        print(f"  1. Set your {ansi.cyan}app_id{ansi.reset} from Facebook Developer Console")
        print(f"  2. Set your {ansi.cyan}app_secret{ansi.reset} from Facebook Developer Console")
        print(f"  3. Set your {ansi.cyan}temp_token{ansi.reset} (or use --temp-token)")
        print(f"  4. Set your {ansi.cyan}page_id{ansi.reset}, {ansi.cyan}page_name{ansi.reset} is optional.")
        print(f"\n{ansi.red}The script will now exit so you can edit the config file.{ansi.reset}")
        print("Run the script again after updating the configuration.")

        logger.info("Created new config file at: %s", ini)
        logger.info("Exiting to allow user to configure credentials")
        sys.exit(0)

    cp = ConfigParser()
    cp.read(ini, encoding="utf-8")

    for sect in cp.sections():
        if not hasattr(cfg, sect):
            continue
        dst = getattr(cfg, sect)
        for key, raw in cp.items(sect):
            if hasattr(dst, key):
                setattr(dst, key, _cast(getattr(dst, key), raw))
    return cfg


class TokenManager:
    """
    Manages Facebook API tokens with timestamped JSON storage.

    Each run creates a new JSON file with format: tokens-YYYY-MM-DD-HHMMSS.json
    This preserves the history of token operations and separates concerns between
    static configuration and dynamic token artifacts.
    """

    def __init__(self, storage_dir: Path = Path("config", "facebook", "tokens")):
        """
        Initialize TokenManager with storage directory.

        Args:
            storage_dir: Directory to store token JSON files (default: "tokens")
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)
        self.current_run_timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        self.current_file = self.storage_dir / f"tokens-{self.current_run_timestamp}.json"

        # Initialize empty token data
        self.user_config = User()
        self.page_configs: Dict[str, Page] = {}
        self.run_metadata = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "run_id": self.current_run_timestamp
        }

    def _serialize_token_info(self, token_info: Optional[Token]) -> Optional[Dict]:
        """Convert Token dataclass to dict for JSON serialization."""
        if token_info is None:
            return None
        return asdict(token_info)

    def _deserialize_token_info(self, data: Optional[Dict]) -> Optional[Token]:
        """Convert dict back to Token dataclass."""
        if data is None:
            return None
        return Token(**data)

    def _serialize_user_config(self, user_config: User) -> Dict:
        """Convert User dataclass to dict for JSON serialization."""
        data = asdict(user_config)
        # Handle nested Token
        if data.get('long_lived_token'):
            data['long_lived_token'] = self._serialize_token_info(user_config.long_lived_token)
        return data

    def _deserialize_user_config(self, data: Dict) -> User:
        """Convert dict back to User dataclass."""
        # Handle nested Token
        if data.get('long_lived_token'):
            data['long_lived_token'] = self._deserialize_token_info(data['long_lived_token'])
        return User(**data)

    def _serialize_page_config(self, page_config: Page) -> Dict:
        """Convert Page dataclass to dict for JSON serialization."""
        data = asdict(page_config)
        # Handle nested Token
        if data.get('page_access_token'):
            data['page_access_token'] = self._serialize_token_info(page_config.page_access_token)
        return data

    def _deserialize_page_config(self, data: Dict) -> Page:
        """Convert dict back to Page dataclass."""
        # Handle nested Token
        if data.get('page_access_token'):
            data['page_access_token'] = self._deserialize_token_info(data['page_access_token'])
        return Page(**data)

    def save_run_data(self) -> str:
        """
        Save current run data to timestamped JSON file.

        Returns:
            Path to the saved file
        """
        run_data = {
            "metadata": self.run_metadata,
            "user_config": self._serialize_user_config(self.user_config),
            "page_configs": {
                page_id: self._serialize_page_config(page_config)
                for page_id, page_config in self.page_configs.items()
            }
        }

        with open(self.current_file, 'w', encoding='utf-8') as f:
            json.dump(run_data, f, indent=2, ensure_ascii=False)

        return str(self.current_file)

    def load_run_data(self, file_path: str) -> None:
        """
        Load run data from a specific JSON file.

        Args:
            file_path: Path to the JSON file to load
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            run_data = json.load(f)

        self.run_metadata = run_data.get("metadata", {})
        self.user_config = self._deserialize_user_config(run_data.get("user_config", {}))
        self.page_configs = {
            page_id: self._deserialize_page_config(page_data)
            for page_id, page_data in run_data.get("page_configs", {}).items()
        }

    def get_latest_run_file(self) -> Optional[str]:
        """
        Get the path to the most recent token file.

        Returns:
            Path to the latest token file, or None if no files exist
        """
        token_files = list(self.storage_dir.glob("tokens-*.json"))
        if not token_files:
            return None

        # Sort by filename (which includes timestamp) and get the latest
        latest_file = sorted(token_files, key=lambda f: f.name)[-1]
        return str(latest_file)

    def list_run_files(self) -> List[str]:
        """
        List all token run files, sorted by timestamp (newest first).

        Returns:
            List of file paths
        """
        token_files = list(self.storage_dir.glob("tokens-*.json"))
        return [str(f) for f in sorted(token_files, key=lambda f: f.name, reverse=True)]

    def update_user_config(
        self,
        user_id: str = None,
        user_name: str = None,
        short_lived_token: str = None,
        long_lived_token: Token = None
    ) -> None:
        """Update user configuration with new values."""
        if user_id is not None:
            self.user_config.user_id = user_id
        if user_name is not None:
            self.user_config.user_name = user_name
        if short_lived_token is not None:
            self.user_config.short_lived_token = short_lived_token
        if long_lived_token is not None:
            self.user_config.long_lived_token = long_lived_token

    def add_page_config(self, page_id: str, page_config: Page) -> None:
        """Add or update a page configuration."""
        self.page_configs[page_id] = page_config

    def get_page_config(self, page_id: str) -> Optional[Page]:
        """Get a specific page configuration."""
        return self.page_configs.get(page_id)

    def get_summary(self) -> Dict:
        """Get a summary of the current token state."""
        return {
            "run_id": self.run_metadata.get("run_id"),
            "created_at": self.run_metadata.get("created_at"),
            "user_id": self.user_config.user_id,
            "user_name": self.user_config.user_name,
            "has_long_lived_token": self.user_config.long_lived_token is not None,
            "page_count": len(self.page_configs),
            "page_names": [config.page_name for config in self.page_configs.values() if config.page_name]
        }
