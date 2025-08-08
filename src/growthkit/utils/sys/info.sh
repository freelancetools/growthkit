#!/bin/bash

echo "- Operating System"
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    sw_vers
    uname -r
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    lsb_release -a
    uname -r
elif [[ "$OSTYPE" == "msys" ]]; then
    # Windows (Git Bash)
    systeminfo | findstr /B /C:"OS Name" /C:"OS Version"
    ver
fi

echo
echo "- Environment"
echo "Shell:       $SHELL ($(uname -m))"
if command -v brew &> /dev/null; then
    echo "Homebrew:    $(brew --version | head -n 1 | cut -d ' ' -f 2)"
fi
if command -v python3 &> /dev/null; then
    echo "Python:      $(python3 --version | cut -d ' ' -f 2)"
fi