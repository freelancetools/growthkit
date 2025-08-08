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
        logger.setLevel(logging.DEBUG)

        # Optional: Disable propagation to prevent duplicate logs in parent loggers
        logger.propagate = False

    # Ensure sys.stdout is using UTF-8
    sys.stdout.reconfigure(encoding='utf-8')

    return logger
