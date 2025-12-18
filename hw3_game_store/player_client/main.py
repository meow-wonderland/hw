#!/usr/bin/env python3
"""
Player Client Main Entry Point
"""
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from gui.app import main

if __name__ == '__main__':
    main()
