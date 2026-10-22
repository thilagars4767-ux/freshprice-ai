"""FreshPrice AI — Main Application Entrypoint.

Can be launched directly via:
    streamlit run app.py
or:
    streamlit run src/dashboard.py
"""

from __future__ import annotations

from pathlib import Path
import sys

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.dashboard import main

if __name__ == "__main__":
    main()
