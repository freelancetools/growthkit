"""
This file is used to define the schema for the config file.
"""
import time
from typing import Optional
from dataclasses import dataclass, field

@dataclass
class App:
    """Facebook App configuration - static user settings"""
    app_id: str = "YOUR_APP_ID_HERE"
    app_secret: str = "YOUR_APP_SECRET_HERE"
    api_version: str = "v23.0"

    @property
    def base_url(self) -> str:
        """Get the base URL for the Facebook Graph API"""
        return f"https://graph.facebook.com/{self.api_version}"


@dataclass
class Token:
    """Token information with expiration tracking"""
    access_token: str = ""
    expires_at: Optional[int] = None  # Unix timestamp
    expires_in: Optional[int] = None  # Seconds from now
    token_type: str = ""

    def is_expired(self) -> bool:
        """Check if token is expired"""
        if self.expires_at is None:
            return False
        return time.time() >= self.expires_at

    def time_until_expiry(self) -> Optional[int]:
        """Get seconds until token expires"""
        if self.expires_at is None:
            return None
        return max(0, int(self.expires_at - time.time()))


@dataclass
class User:
    """User configuration and token info"""
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    short_lived_token: Optional[str] = None
    long_lived_token: Optional[Token] = None


@dataclass
class Page:
    """Page configuration and token info"""
    page_id: Optional[str] = None
    page_name: Optional[str] = None
    page_access_token: Optional[Token] = None
    category: Optional[str] = None


@dataclass
class Config:
    """Main configuration container aggregating all sections."""
    app:     App    = field(default_factory=App)
    token:   Token  = field(default_factory=Token)
    user:    User   = field(default_factory=User)
    page:    Page   = field(default_factory=Page)
