"""This script is used to sanitize the file name."""
import re

def up(name):
    """
    Sanitize the file name by replacing spaces with hyphens,
    removing non-alphanumeric characters except dots and hyphens,
    converting to lowercase for the main part of the filename,
    while preserving the original case and hyphens inside square brackets.
    """
    # Function to sanitize the main part of the filename
    def alphanumeric(text):
        sanitization = text.replace(' ', '-')
        sanitization = re.sub(r'[^a-zA-Z0-9.\-_]', '', sanitization)
        sanitization = re.sub(r'-{2,}', '-', sanitization)
        sanitization = sanitization.lower()
        sanitization = sanitization.strip('-')
        return sanitization

    return alphanumeric(name)
