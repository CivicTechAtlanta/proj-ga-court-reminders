import sys
from pathlib import Path

# The Lambda bundle's root is the lambda/ directory, so make its packages
# importable the same way the deployed functions import them.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lambda"))
