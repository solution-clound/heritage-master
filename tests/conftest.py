import sys
from pathlib import Path

# Add src to path so tests can import heritage_master
src_dir = str(Path(__file__).parent.parent / "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)
