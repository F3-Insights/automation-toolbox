import sys
from pathlib import Path

# The scripts import their sibling _common.py; another skill's _common must not be the one cached.
sys.modules.pop("_common", None)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
