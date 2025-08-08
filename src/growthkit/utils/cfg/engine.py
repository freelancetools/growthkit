"""
Configuration engine: load dataclass defaults first, then merge INI overrides.
On first run, a template `config.ini` mirroring the dataclass defaults is written
at the repository root so the user has something to tweak.
"""

from pathlib import Path
from typing import Optional
from dataclasses import asdict
from configparser import ConfigParser

from growthkit.utils.cfg.schema import Config


# Paths
ROOT = Path(__file__).resolve().parent.parent.parent
INI_FILE = Path(ROOT, "config.ini")


# Helpers
def _cast(template_value, raw: str):
    """Cast the raw INI string back to the dataclass field type."""
    t = type(template_value)
    return Path(raw) if t is Path else t(raw)

def _create_config(cfg: Config, path: Path) -> None:
    """Write a template INI that mirrors the dataclass defaults."""
    cp = ConfigParser()
    for section, mapping in asdict(cfg).items():
        cp[section] = {k: str(v) for k, v in mapping.items()}
    with path.open("w", encoding="utf-8") as f:
        cp.write(f)


# Public API
def load(path: Optional[Path] = None) -> Config:
    """Load configuration from INI file and return Config object."""
    cfg = Config()
    ini = path or INI_FILE

    # Create template on first run so users have something to tweak
    if not ini.exists():
        _create_config(cfg, ini)

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
