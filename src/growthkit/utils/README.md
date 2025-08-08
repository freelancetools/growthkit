# Python Utils Library

> ⚠️  **Read-Only Notice**
>
> This `utils/` package is mirrored from a **separate upstream repo** that
> follows its own release cycle. **Do not** generate, commit, or edit code here
> within this project. All modifications must happen in the upstream repository
> and be pulled in via vendoring.



A comprehensive collection of Python utilities designed to be cloned into new projects as a foundation for building robust, well-structured Python scripts and applications. This library helps coding assistants generate more pythonic and useful code by providing battle-tested components for common development tasks.

## 🎯 Purpose

This repository serves as a **project template and utility library** that provides:
- Consistent patterns for configuration, logging, and CLI output
- Cross-platform compatibility utilities
- Development workflow helpers
- Code quality and formatting standards

Perfect for bootstrapping new Python projects or enhancing existing ones with proven utilities.

## 📑 Navigation

- [🔧 Configuration Management](#configuration-management-cfg)
- [🖥️ Command Line Interface](#command-line-interface-cli)  
- [📋 Cross-Platform Clipboard](#cross-platform-clipboard-clip)
- [📊 Logging System](#logging-system-logs)
- [📈 Progress Tracking](#progress-tracking-progress)
- [🎨 Styling & Formatting](#styling--formatting-style)
- [🖥️ System Information](#system-information-sys)
- [🔄 Version Control](#version-control-vcs)
- [🧹 Development Cleanup](#development-cleanup-clean)
- [🚀 Getting Started](#getting-started)
- [🎨 Design Principles](#design-principles)
- [📚 Tutorials](#tutorials)
- [🤖 For Coding Assistants](#for-coding-assistants)

## 📁 Module Overview

### 🔧 Configuration Management (`cfg/`)
**Dataclass-based configuration with INI file overrides**
- [`engine.py`](cfg/engine.py) - Configuration loader with automatic INI generation
- [`schema.py`](cfg/schema.py) - Configuration schema using dataclasses
- [`tutorial.md`](cfg/tutorial.md) - Complete implementation guide

**Features:**
- Automatic INI template generation from dataclass defaults
- Type-safe configuration loading with proper casting
- Cross-platform path handling
- No third-party dependencies

**Quick Start:**
```python
from utils.cfg import engine
config = engine.load()  # Auto-creates config.ini from defaults
print(config.paths.ffmpeg)  # Type-safe access
```

### 🖥️ Command Line Interface (`cli/`)
**Enhanced shell command execution**
- [`shell.py`](cli/shell.py) - Execute commands with logging and colored output

**Features:**
- Dual output modes: background (`execute()`) and interactive (`run()`)
- Automatic logging of commands and output
- Colored terminal output with error highlighting
- Caller-aware logging

**Quick Start:**
```python
from utils.cli import shell
result = shell.execute("ls -la")  # Background execution
shell.run("python script.py")     # Interactive execution
```

### 📋 Cross-Platform Clipboard (`clip/`)
**Universal clipboard operations**
- [`board.py`](clip/board.py) - Cross-platform clipboard with copy/paste functions

**Features:**
- Windows, macOS, and Linux support
- Multiple backend implementations (native APIs, command-line tools)
- Automatic fallback handling
- No external dependencies on most platforms

**Quick Start:**
```python
from utils.clip import board
board.copy('Hello, World!')
text = board.paste()
```

### 📊 Logging System (`logs/`)
**Centralized logging with file rotation**
- [`report.py`](logs/report.py) - Rotating file logger with UTF-8 support
- [`tutorial.md`](logs/tutorial.md) - Comprehensive logging patterns

**Features:**
- Automatic log file creation named after calling script
- 10MB rotating logs with 10 backup files
- UTF-8 encoding support
- Prevents duplicate handlers
- Caller-aware log file naming

**Quick Start:**
```python
from utils.logs import report
logger = report.settings(__file__)
logger.info("Application started")
```

### 📈 Progress Tracking (`progress/`)
**Session management and git workflow helpers**
- [`truncate.py`](progress/truncate.py) - Git diff truncation utility
- [`create-diffs.md`](progress/create-diffs.md) - Session diff creation guide
- [`start-session.md`](progress/start-session.md) - Session workflow
- [`end-session.md`](progress/end-session.md) - Session summary guide

**Features:**
- Large git diff truncation (useful for .har files, large JSON)
- Project session tracking via git diffs
- Configurable line preservation

**Quick Start:**
```bash
python progress/truncate.py session.diff session_clean.diff --ext .har --lines 10
```

### 🎨 Styling & Formatting (`style/`)
**Consistent terminal output and text formatting**
- [`ansi.py`](style/ansi.py) - ANSI color constants
- [`split.py`](style/split.py) - Intelligent text chunking
- [`tabs.py`](style/tabs.py) - Tab pattern matching
- [`tutorial.md`](style/tutorial.md) - Comprehensive styling guide

**Features:**
- Curated color palette for consistent CLI output
- Markdown-aware text splitting with sentence preservation
- Comprehensive styling patterns for different message types

**Quick Start:**
```python
from utils.style import ansi
print(f"{ansi.green}Success!{ansi.reset} Operation completed")
print(f"Processing: {ansi.cyan}filename.txt{ansi.reset}")
```

### 🖥️ System Information (`sys/`)
**Cross-platform system utilities**
- [`info.sh`](sys/info.sh) - Unix/macOS system information
- [`info.ps1`](sys/info.ps1) - Windows PowerShell system information

**Features:**
- OS detection and version reporting
- Environment tool detection (Python, Git, Node.js, etc.)
- Consistent output format across platforms

### 🔄 Version Control (`vcs/`)
**Git workflow and standards**
- [`commits.md`](vcs/commits.md) - Conventional commit message guide
- [`pr.md`](vcs/pr.md) - Pull request template

**Features:**
- Conventional commit standards with examples
- Git hook scripts for commit validation
- Comprehensive PR template

### 🧹 Development Cleanup (`clean/`)
**Project maintenance utilities**
- [`new.py`](clean/new.py) - Remove development artifacts

**Features:**
- Recursive `__pycache__` directory removal
- Log file cleanup with pattern matching
- Safe error handling with detailed logging

**Quick Start:**
```python
python clean/new.py  # Clean entire project
```

## 🚀 Getting Started

### 1. Clone into your project
```bash
git clone https://github.com/your-username/utils.git
# or add as git submodule
git submodule add https://github.com/your-username/utils.git utils
```

### 2. Basic project structure
```
your-project/
├── utils/           # This repository
│   ├── cfg/
│   ├── cli/
│   ├── logs/
│   └── ...
├── config.ini       # Auto-generated config
└── main.py          # Your application
```

### 3. Example integration
```python
#!/usr/bin/env python3
"""Example script using utils library."""

from utils.cfg import engine
from utils.logs import report  
from utils.style import ansi
from utils.cli import shell

# Initialize configuration and logging
config = engine.load()
logger = report.settings(__file__)

def main():
    logger.info("Starting application")
    print(f"Starting application with config: {ansi.cyan}{config.paths.ffmpeg}{ansi.reset}")
    
    # Execute commands with proper logging
    result = shell.execute("python --version")
    
    if result['error']:
        logger.error("Command failed: %s", result['error'])
        print(f"{ansi.red}Error:{ansi.reset} {result['error']}")
    else:
        logger.info("Python version: %s", result['output'])
        print(f"Python version: {ansi.green}{result['output']}{ansi.reset}")

if __name__ == "__main__":
    main()
```

## 🎨 Design Principles

### **Consistency**
- Unified color scheme across all modules
- Consistent error handling and logging patterns
- Standardized configuration and initialization

### **Cross-Platform**
- Works on Windows, macOS, and Linux
- Handles encoding issues (especially UTF-8)
- Platform-specific implementations where needed

### **Zero Dependencies**
- Uses only Python standard library
- Optional enhancements for better functionality
- Graceful degradation when optional features unavailable

### **Developer Experience**
- Comprehensive tutorials and examples
- Type hints and clear documentation
- Caller-aware logging and error reporting

## 📚 Tutorials

Each module includes detailed tutorials:
- [`cfg/tutorial.md`](cfg/tutorial.md) - Configuration system setup
- [`logs/tutorial.md`](logs/tutorial.md) - Logging patterns and best practices  
- [`style/tutorial.md`](style/tutorial.md) - CLI styling and color usage
- [`progress/create-diffs.md`](progress/create-diffs.md) - Session management
- [`vcs/commits.md`](vcs/commits.md) - Git commit conventions

## 🤖 For Coding Assistants

This library is specifically designed to help AI coding assistants generate better Python code by providing:

### **Ready-to-use patterns:**
```python
# Configuration
config = engine.load()

# Logging with colors
logger = report.settings(__file__)
logger.info("Processing file: %s", filename)
print(f"Processing: {ansi.cyan}{filename}{ansi.reset}")

# Safe command execution  
result = shell.execute(command)
if result['error']:
    logger.error("Command failed: %s", result['error'])
```

### **Consistent styling:**
- Use `ansi.green` for success/completion
- Use `ansi.cyan` for file paths and information
- Use `ansi.yellow` for warnings and timing
- Use `ansi.red` for errors
- Use `ansi.magenta` for processing status

### **Robust error handling:**
- All utilities include proper exception handling
- Logging includes caller information
- Graceful degradation for missing dependencies

---

**Built for developers, by developers. Clone, customize, and build amazing Python applications!** 🐍✨
