"""
This file is used to define the schema for the config file.
"""
import platform
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class Paths:
    """Configuration for common file and directory paths."""
    ffmpeg:     Path = Path("ffmpeg")


@dataclass
class System:
    """System information."""
    machine_os:   str = platform.system().lower()
    machine_arch: str = platform.machine()


@dataclass
class Config:
    """Main configuration container aggregating all sections."""
    paths:   Paths   = field(default_factory=Paths)
    system:  System  = field(default_factory=System)
