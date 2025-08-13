#!/usr/bin/env python3
"""Run the Gmail full archive."""
from growthkit.connectors.mail import gmail_sync

if __name__ == "__main__":
    gmail_sync.main()
