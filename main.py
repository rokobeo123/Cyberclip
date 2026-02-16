#!/usr/bin/env python3
"""CyberClip - Advanced Clipboard Manager with Cyberpunk GUI.

Launch the application:
    python main.py

Hotkeys (default):
    Ctrl+Shift+V  - Toggle window
    Ctrl+Shift+N  - Paste next from magazine
    Ctrl+Shift+G  - Toggle ghost mode
    Escape        - Panic button / hide window
"""
import sys
import os

# Ensure the project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cyberclip.app import run

if __name__ == "__main__":
    run()
