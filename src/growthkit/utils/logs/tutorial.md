Below is a **drop-in mini-guide** you can paste into your project.
It recreates everything we just planned—centralized logging setup, automatic file creation, UTF-8 handling—in a way that works on Python 3.8+, no third-party deps beyond standard library.

---

## 🗺️ 1. Directory layout (per CLI repo)

```
your-tool/
│ utils/
│ ├── logs/
│ │   └── report.py          # <-- logging configuration
│ │
│ ├── logs/                  # <-- auto-created log files
│ │   ├── main_script.log
│ │   ├── helper_util.log
│ │   └── another_tool.log
│ │
└ main_script.py             # your CLI script
```

### `.gitignore` snippet

```
# Log files are local to each machine
logs/
*.log
```

---

## 🏗️ 2. `utils/logs/report.py`

```python
"""Configures the logging system for the script."""
import os
import sys
import logging
from logging.handlers import RotatingFileHandler

def settings(script_path):
    """Configures the logging system for the script."""
    script_name = os.path.basename(script_path)
    root = os.path.dirname(os.path.dirname(__file__))
    log_name = script_name.rsplit('.', 1)[0] + '.log'
    log_file = os.path.join(root, 'logs', log_name)
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    # Create a logger instance
    logger = logging.getLogger(script_name)

    # Prevent adding multiple handlers
    if not logger.handlers:
        # Set up the RotatingFileHandler
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=1024*1024*10,  # 10 MB
            backupCount=10,
            encoding='utf-8'
        )
        formatter = logging.Formatter(
            '%(asctime)s %(levelname)s [%(filename)s:%(lineno)d] %(message)s'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        logger.setLevel(logging.INFO)

        # Optional: Disable propagation to prevent duplicate logs in parent loggers
        logger.propagate = False

    # Ensure sys.stdout is using UTF-8
    sys.stdout.reconfigure(encoding='utf-8')

    return logger
```

*This module handles all the logging setup—file creation, rotation, formatting, UTF-8 encoding.*

---

## 🚀 3. Using it in your main script

```python
from utils.logs import report
from utils.style import ansi  # For colored console output

# Initialize logging at the top of your script
logger = report.settings(__file__)

def main():
    logger.info("Starting application")
    print(f"Starting application...")
    
    try:
        # Your main logic here
        result = some_function()
        logger.info("Operation completed successfully: %s", result)
        print(f"Operation completed: {ansi.green}{result}{ansi.reset}")
        
    except Exception as e:
        logger.error("Application failed: %s", str(e))
        print(f"{ansi.red}Application failed:{ansi.reset} {str(e)}")
        raise
    
    logger.info("Application finished")
    print(f"Application finished")

if __name__ == "__main__":
    main()
```

---

## 🔧 4. Different logging levels

```python
from utils.logs import report
from utils.style import ansi
logger = report.settings(__file__)

# Information - general flow
logger.info("Starting download for URL: %s", url)
print(f"Starting download for URL: {ansi.cyan}{url}{ansi.reset}")

logger.info("Download completed in %.2f seconds", duration)
print(f"Download completed in {ansi.yellow}{duration:.2f}{ansi.reset} seconds\n")

# Debug - detailed information for troubleshooting
logger.debug("Raw response: %s", response.text)
# Debug typically doesn't need console output

# Warning - something unexpected but not fatal
logger.warning("Retrying in %.2f seconds...", delay)
print(f"Retrying in {ansi.yellow}{delay:.2f}{ansi.reset} seconds...")

logger.warning("File already exists, skipping: %s", filepath)
print(f"File {ansi.yellow}already exists{ansi.reset}, skipping: {filepath}")

# Error - something went wrong
logger.error("Failed to process file %s: %s", filename, str(e))
print(f"{ansi.red}Failed{ansi.reset} to process file: {filename} - {str(e)}")

logger.error("HTTP Error %s: %s", response.status_code, response.reason)
print(f"HTTP {ansi.red}Error {response.status_code}{ansi.reset}: {response.reason}")

# Critical - severe error that might stop the program
logger.critical("Database connection failed, shutting down")
print(f"{ansi.red}CRITICAL:{ansi.reset} Database connection failed, shutting down")
```

---

## 🎨 5. Dual logging pattern: Files + Colored Console

The key feature of this logging system is **dual output** - every important message is both logged to a file AND displayed in the console with colors for real-time feedback.

### 5.1 The dual logging pattern

```python
from utils.logs import report
from utils.style import ansi
logger = report.settings(__file__)

# Pattern: Log first, then print colored version
logger.info("Starting transcription for %s", filename)
print(f"Starting transcription for: {ansi.cyan}{filename}{ansi.reset}")

logger.info("Transcription completed in %.2f seconds", duration)
print(f"Transcription completed in {ansi.yellow}{duration:.2f}{ansi.reset} seconds\n")

logger.error("Failed to process %s: %s", filename, str(e))
print(f"{ansi.red}Failed{ansi.reset} to process: {filename} - {str(e)}")
```

### 5.2 Consistent color scheme

Follow these color conventions for coherent visual feedback:

```python
# Success/Completion/Results → GREEN
logger.info("Processing completed: %s files", count)
print(f"Processing completed: {ansi.green}{count}{ansi.reset} files")

# Processing/Actions → MAGENTA  
logger.info("Processing file: %s", filename)
print(f"{ansi.magenta}Processing{ansi.reset}: {filename}")

# Timing/Progress → YELLOW
logger.info("Operation took %.2f seconds", duration)
print(f"Operation took {ansi.yellow}{duration:.2f}{ansi.reset} seconds")

# Information/Paths → CYAN
logger.info("Output file: %s", filepath)
print(f"Output file: {ansi.cyan}{filepath}{ansi.reset}")

# Warnings/Retries → YELLOW
logger.warning("Retrying in %.2f seconds...", delay)
print(f"Retrying in {ansi.yellow}{delay:.2f}{ansi.reset} seconds...")

# Errors → RED
logger.error("HTTP Error %s: %s", status, reason)
print(f"HTTP {ansi.red}Error {status}{ansi.reset}: {reason}")
```

### 5.3 When to use dual logging

```python
# ✅ DO - Important user-facing events
logger.info("Download started")
print(f"Download started...")

# ✅ DO - Progress updates
logger.info("Step 2/3: Processing audio")
print(f"Step {ansi.magenta}2{ansi.reset}/{ansi.green}3{ansi.reset}: Processing audio")

# ✅ DO - Results and completion
logger.info("Generated %d files", count)
print(f"Generated {ansi.green}{count}{ansi.reset} files")

# ❌ DON'T - Debug information (logs only)
logger.debug("Raw API response: %s", response.text)
# No print statement needed for debug info

# ❌ DON'T - Verbose internal details
logger.info("Setting handler maxBytes to %d", maxbytes)
# No print statement needed for internal configuration
```

### 5.4 Color formatting rules

```python
# Highlight VALUES and KEYWORDS, not entire sentences
print(f"Processing file: {ansi.cyan}{filename}{ansi.reset}")  # ✅ Good
print(f"{ansi.cyan}Processing file: {filename}{ansi.reset}")  # ❌ Too much color

# Use selective highlighting for readability
print(f"Completed {ansi.green}{count}{ansi.reset}/{ansi.green}{total}{ansi.reset} files")  # ✅ Good
print(f"{ansi.green}Completed {count}/{total} files{ansi.reset}")  # ❌ Overwhelming

# Keep progress indicators clean
print(f"{ansi.magenta}Processing {index}{ansi.reset}/{ansi.green}{total}{ansi.reset}: {filename}")  # ✅ Good
print(f"{ansi.magenta}Processing {index} out of {total}: {filename}{ansi.reset}")  # ❌ Verbose
```

---

## 🛠️ 6. Advanced usage patterns

### 6.1 Logging in utility modules

```python
# utils/downloader.py
from utils.logs import report
from utils.style import ansi
logger = report.settings(__file__)

def download_file(url):
    logger.info("Starting download: %s", url)
    print(f"Starting download: {ansi.cyan}{url}{ansi.reset}")
    
    # ... download logic ...
    
    logger.info("Download complete: %s", local_path)
    print(f"Download complete: {ansi.green}{local_path}{ansi.reset}")
    return local_path
```

### 6.2 Logging with caller context (for shared utilities)

```python
# utils/shell.py - for utilities used by multiple scripts
import inspect
from utils.logs import report
from utils.style import ansi

def execute_command(command):
    # Get the caller's module for context
    caller_frame = inspect.currentframe().f_back
    caller_module = inspect.getmodule(caller_frame)
    logger = report.settings(caller_module.__file__)
    
    logger.info("Executing command: %s", command)
    print(f"{ansi.grey}{command}{ansi.reset}")
    # ... execution logic ...
```

### 6.3 Logging large data structures

```python
# For large objects, log key details only
metadata = {"title": "Long Video", "duration": 3600, "size": "2GB"}
logger.info("Processing video: %s", metadata['title'])
print(f"Processing video: {ansi.cyan}{metadata['title']}{ansi.reset}")
logger.debug("Full metadata: %s", metadata)  # Only in debug mode

# For API responses, log status and key fields
logger.info("API response status: %s", response.status_code)
print(f"API response status: {ansi.green}{response.status_code}{ansi.reset}")
logger.debug("Full API response: %s", response.json())
```

---

## 📁 7. Log file structure

The system automatically creates log files with this structure:

```
logs/
├── main_script.log          # From main_script.py
├── video_processor.log      # From video_processor.py  
├── notification_sender.log  # From notification_sender.py
└── data_cleaner.log        # From data_cleaner.py
```

Each log file contains entries like:
```
2024-01-15 14:30:22,123 INFO [main_script.py:45] Starting application
2024-01-15 14:30:22,456 INFO [downloader.py:23] Starting download: https://example.com/video
2024-01-15 14:30:45,789 WARNING [processor.py:67] File already exists, skipping: output.mp4
2024-01-15 14:30:46,012 ERROR [uploader.py:12] Upload failed: Connection timeout
```

---

## 🔄 8. Log rotation features

The system automatically handles log rotation:

- **Max size**: 10 MB per log file
- **Backup count**: 10 old files kept (so 11 total including current)
- **Auto-cleanup**: Oldest files are automatically deleted
- **Example**: `main_script.log`, `main_script.log.1`, `main_script.log.2`, etc.

---

## 🎯 9. Best practices

### 8.1 What to log

```python
# ✅ Good - log key milestones
logger.info("Processing started for: %s", filename)
logger.info("Step 1/3: Download completed")
logger.info("Step 2/3: Transcription completed")  
logger.info("Step 3/3: Upload completed")

# ✅ Good - log errors with context
logger.error("Failed to process %s: %s", filename, str(e))

# ❌ Avoid - logging in tight loops
for item in huge_list:
    logger.info("Processing item: %s", item)  # Creates massive logs

# ✅ Better - log summary
logger.info("Processing %d items", len(huge_list))
```

### 8.2 Performance-friendly logging

```python
# ✅ Good - use string formatting in log calls
logger.info("Processing file: %s (size: %d MB)", filename, size_mb)

# ❌ Avoid - pre-formatting strings
logger.info(f"Processing file: {filename} (size: {size_mb} MB)")
# ^ This does string formatting even if logging is disabled

# ✅ Good - for expensive operations, check log level
if logger.isEnabledFor(logging.DEBUG):
    expensive_debug_info = generate_debug_data()
    logger.debug("Debug info: %s", expensive_debug_info)
```

### 8.3 Structured logging for complex data

```python
# For tracking performance metrics
start_time = time.perf_counter()
# ... do work ...
duration = time.perf_counter() - start_time
logger.info("Operation completed in %.2f seconds", duration)

# For API calls
logger.info("API call: %s %s", method, url)
logger.info("Response: %d %s (%.2f seconds)", status, reason, elapsed)
```

---

## 🛰️ 10. Integration with existing scripts

To add logging to an existing script:

1. **Add the import**:
   ```python
   from utils.logs import report
   ```

2. **Initialize the logger**:
   ```python
   logger = report.settings(__file__)
   ```

3. **Replace print statements** with dual logging pattern:
   ```python
   # Before
   print("Starting process...")
   print(f"Error: {e}")
   
   # After  
   logger.info("Starting process...")
   print(f"Starting process...")
   
   logger.error("Process failed: %s", str(e))
   print(f"{ansi.red}Process failed:{ansi.reset} {str(e)}")
   ```

---

## 🔧 11. Customizing the logger

### 10.1 Different log levels per script

```python
# In your script after initializing the logger
logger.setLevel(logging.DEBUG)  # Show all messages
logger.setLevel(logging.WARNING)  # Only warnings and errors
```

### 10.2 Adding console output

```python
# Modified report.py to also log to console
def settings(script_path, console=False):
    # ... existing code ...
    
    if console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    return logger
```

### 10.3 Custom log format

```python
# In report.py, change the formatter
formatter = logging.Formatter(
    '%(asctime)s [%(levelname)8s] %(message)s'  # Simpler format
)

# Or more detailed
formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s'
)
```

---

## 🌍 12. Extending for different environments

| Want                          | How                                                                                                                                                        |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Different log levels**      | Set `logger.setLevel(logging.DEBUG)` for development, `logging.INFO` for production |
| **Console + file logging**    | Add a `StreamHandler` alongside the `RotatingFileHandler` |
| **JSON structured logs**      | Replace the formatter with a JSON formatter like `python-json-logger` |
| **Remote logging**            | Add handlers like `HTTPHandler` or `SMTPHandler` for alerts |
| **Per-environment config**    | Load log level from environment variables or config files |

---

## 🔍 13. Debugging logging issues

### 12.1 Check if logging is working

```python
logger = report.settings(__file__)
logger.info("Test message")
print(f"Log file should be at: {logger.handlers[0].baseFilename}")
```

### 12.2 View current log level

```python
print(f"Current log level: {logger.level}")
print(f"Effective log level: {logger.getEffectiveLevel()}")
```

### 12.3 List all handlers

```python
for handler in logger.handlers:
    print(f"Handler: {handler}")
    print(f"Level: {handler.level}")
    print(f"Formatter: {handler.formatter}")
```

---

### Quick mental model

* **`report.py`** = centralized logging setup, handles file creation & rotation
* **`logger = report.settings(__file__)`** = one line to get a configured logger
* **Log files** = automatically created in `logs/` directory, one per script
* **UTF-8** = handled automatically for international characters
* **Rotation** = automatic cleanup when files get too large

Copy the `report.py` file, add the two import lines to your scripts, and you're logging—no dependencies, works on 3.8+, completely self-contained. 