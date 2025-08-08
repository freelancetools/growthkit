Below is a **drop-in mini-guide** you can paste into your project.
It recreates everything we just planned—dataclass schema, loader, INI defaults—in a way that works on Python 3.8 +, no third-party deps.

---

## 🗺️ 1. Directory layout (per CLI repo)

```
your-tool/
│ utils/
│ ├── schema.py          # <-- dataclass defaults only
│ └── engine.py          # <-- loader / coercion
│
├ config.ini             # optional overrides
└ main_logic.py          # your CLI script
```

### `.gitignore` snippet

```
# per-machine overrides only
config.ini
```

---

## 🏗️ 2. `utils/cfg/schema.py`

```python
from dataclasses import dataclass
from pathlib import Path

@dataclass                # [paths]
class Paths:
    """Configuration for file and directory paths."""
    voices_dir: Path = Path("voices")
    cli_exe:   Path = Path("venv/Scripts/f5-tts_infer-cli.exe")

@dataclass                # [tts]
class TTS:
    """Configuration for text-to-speech settings."""
    default_voice:   str   = "prime"
    default_speed:   float = 1.0
    default_cadence: float = 0.8
    nfe_steps:       int   = 32

@dataclass
class Display:              # [display]
    """Configuration for display and UI settings."""
    max_sample_length: int = 50
    preview_length:   int = 100

@dataclass                # [network]
class Network:
    """Configuration for network settings."""
    timeout: int = 10

@dataclass                # glue them
class Config:
    """Main configuration container."""
    paths:    Paths    = Paths()
    tts:      TTS      = TTS()
    display:  Display  = Display()
    network:  Network  = Network()
```

*Everything here is pure data & defaults—no I/O.*

---

## 🔌 3. `utils/cfg/engine.py`

```python
from pathlib import Path
from configparser import ConfigParser
from dataclasses import asdict

from schema import Config

ROOT = Path(__file__).resolve().parent.parent.parent
INI_FILE = ROOT / "config.ini"

# Cast strings coming from INI back to the original field type
def _cast(template_value, raw: str):
    """Cast the raw INI string back to the dataclass field type."""
    t = type(template_value)
    return Path(raw) if t is Path else t(raw)

# Write a template INI that mirrors the dataclass defaults
def _create_config(cfg: Config, path: Path) -> None:
    """Write a template INI that mirrors the dataclass defaults."""
    cp = ConfigParser()
    for section, mapping in asdict(cfg).items():
        cp[section] = {k: str(v) for k, v in mapping.items()}
    with path.open("w", encoding="utf-8") as f:
        cp.write(f)

def load(path: Path | None = None) -> Config:
    """Return Config object, creating INI with defaults if it doesn't exist."""
    cfg = Config()                       # 1️⃣ dataclass defaults
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
```

On first run the file is auto-generated from the dataclass defaults—edit only the values you want to change; absent keys fall back automatically.

---

## 📄 4. Minimal `config.ini` example

```ini
[paths]
voices_dir = voices        ; same as default—could omit

[tts]
default_voice = nova
default_speed = 1.25
nfe_steps     = 48
```

Only list keys that differ from the dataclass; absent keys fall back automatically.

---

## 🚀 5. Using it in your CLI (`main_logic.py`)

```python
from utils.cfg import engine
config = engine.load()

# normal attribute access
print(config.tts.default_speed)
wav_dir = config.paths.voices_dir
```

Need a quick dump for debugging?

```python
import json, dataclasses
print(json.dumps(dataclasses.asdict(config), indent=2))
```

---

## 🌍 5.1  Optional helper: stable path resolution

If you keep **relative** paths in `config.ini` (e.g. `voices_dir = voices`), your script needs a reference point to make them absolute.  A tiny helper keeps things predictable no matter where the user launches the CLI from:

```python
from pathlib import Path

# directory that contains *this* script – works even when invoked via a batch wrapper
REPO_ROOT = Path(__file__).resolve().parent

def _resolve(p: Path) -> Path:
    """Return absolute path, resolving paths that are still relative to REPO_ROOT."""
    return p if p.is_absolute() else (REPO_ROOT / p).resolve()

# Example usage
voices_dir = _resolve(config.paths.voices_dir)
cli_exe    = _resolve(config.paths.cli_exe)
```

Why bother?

* Run the same command from any folder (`C:\project> tts` vs `C:\Users\you> tts`).
* Keep the INI human-readable & portable (no machine-specific absolute paths).
* Adds only two lines of code and zero dependencies.

It is **optional** – drop it if you always run the CLI from the project root *or* store absolute paths in the INI.

---

## 🔧 5.1.1  Reusable helper for any executable

```python
from pathlib import Path
import shutil, sys

REPO_ROOT = Path(__file__).resolve().parent

def _resolve_cmd(cfg_value: str | Path, *, default_name: str) -> Path:
    """
    Return an absolute Path to an executable.

    1. If cfg_value is empty → resolve default_name from the user's PATH.
    2. If cfg_value is just "whisperx" (no slash) → same PATH lookup.
    3. Otherwise treat cfg_value as a user-supplied path (absolute or
       repo-relative) and make it absolute.

    Exit with a friendly error message if nothing is found.
    """
    if not cfg_value:
        found = shutil.which(default_name)
        if found: return Path(found)
        _fatal(default_name)

    p = Path(cfg_value)

    if p.name == str(p):                       # bare command
        found = shutil.which(p.name)
        if found: return Path(found)
        _fatal(p.name)

    abs_path = p if p.is_absolute() else (REPO_ROOT / p).resolve()
    if abs_path.exists(): return abs_path
    _fatal(abs_path)

def _fatal(target):
    print(f"[ERROR] Executable not found: {target}")
    sys.exit(1)
```

Usage:

```python
whisperx = _resolve_cmd(config.paths.whisperx, default_name="whisperx")
ffmpeg   = _resolve_cmd(config.paths.ffmpeg,   default_name="ffmpeg")
tts_py   = _resolve_cmd(config.paths.tts_python, default_name="python")
```

This single helper covers every edge-case:

* empty INI value → use whatever is on PATH  
* bare name in INI → also PATH lookup  
* relative or absolute path in INI → resolve & verify  
* exits early with a clear message if the executable is missing

---

## 🛰️ 5.2  Wiring binary paths (ffmpeg / whisperx)

```python
from pathlib import Path
import shutil
from utils.cfg import engine

config = engine.load()

# 1️⃣  FFmpeg
ffmpeg_cmd = str(config.paths.ffmpeg) if config.paths.ffmpeg else "ffmpeg"
ffmpeg_path = (
    ffmpeg_cmd
    if Path(ffmpeg_cmd).is_absolute()
    else shutil.which(ffmpeg_cmd)
)
if not ffmpeg_path:
    raise RuntimeError("FFmpeg not found – install it or point paths.ffmpeg in config.ini to the binary")

# 2️⃣  WhisperX
whisperx_cmd = str(config.paths.whisperx) if config.paths.whisperx else "whisperx"
whisperx_path = (
    whisperx_cmd
    if Path(whisperx_cmd).is_absolute()
    else shutil.which(whisperx_cmd)
)
if not whisperx_path:
    raise RuntimeError("WhisperX not found – install it or point paths.whisperx in config.ini to the binary")
```

Both helpers fall back to the user's `PATH` when the INI keeps the default value.

---

## 🏷️ 5.3  Using config values as *argparse* defaults

A convenient pattern is to inject the dataclass values straight into your CLI flags so users can still override them on the command line:

```python
parser.add_argument(
    "-m", "--model",
    default=config.whisper.model,
    help=f"WhisperX model (default: {config.whisper.model})",
)
parser.add_argument(
    "-b", "--batch_size",
    type=int,
    default=config.whisper.batch_size,
    help=f"Batch size (default: {config.whisper.batch_size})",
)
parser.add_argument(
    "-ct", "--compute_type",
    default=config.whisper.compute_type,
    help=f"Compute type (default: {config.whisper.compute_type})",
)
```

Users keep the ergonomic `--help` hints *and* a single source-of-truth lives in `config.ini`.

---

## 🖥️ 6.  Optional `[system]` section

The loader ships with an *informational* `system` dataclass that captures the current machine's OS and CPU architecture:

```python
@dataclass
class System:
    machine_os:   str = platform.system().lower()  # windows / linux / darwin
    machine_arch: str = platform.machine()         # x86_64 / arm64 / …
```

It is **read-only by default** and mainly helpful for conditional logic, e.g. deciding whether to download an Apple-Silicon wheel or selecting a different default `compute_type`.  You rarely need to override these values, but you can expose them in `config.ini` if desired.

---

## 🛠️ 7. Extending later

| Want                          | How                                                                                                                                                        |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Per-machine overrides**     | `config.ini` is already .gitignored. Run once to generate it, then tweak values locally. |
| **Env or `.env` secrets**     | Re-inject a tiny `python-dotenv` block in `engine.py` when you need it.                                                                               |
| **CLI flag overrides**        | After `argparse.parse_args()`, call `setattr` on the dataclass fields you wish to change; type-cast with `_cast()` helper. |
| **Share loader across repos** | Move `engine.py` to a tiny internal package (`mindsmith_config`) and `pip install -e` it everywhere. Each repo keeps only its own `schema.py`. |

---

### Quick mental model

* **Dataclass** = typed defaults, IDE autocomplete, no runtime key typos.  
* **INI** = the *delta* from defaults—only what you changed.  
* **Loader** = glue that merges & type-casts.

Copy the two files, adjust the schema for each project, and you're done—no third-party libraries, works on 3.8+, totally self-contained.