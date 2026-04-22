"""Entry point for pyinstaller - server mode"""

import sys
import os

# Add current directory to path for imports
sys.path.insert(0, os.getcwd())

from cli.main import main

if __name__ == "__main__":
    main()
