"""Makes `pytest` work from the backend/ directory without an editable install."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
