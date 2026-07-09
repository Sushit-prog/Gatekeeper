import sys
from pathlib import Path

# Add project root to sys.path for benchmark imports
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)
