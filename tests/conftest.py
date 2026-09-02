import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# The Lambda bundle's root is the lambda/ directory, so make its packages
# importable the same way the deployed functions import them. The CDK app and
# the helper scripts likewise import their siblings by bare name.
for directory in ("lambda", "cdk_stack", "scripts"):
    sys.path.insert(0, str(REPO_ROOT / directory))
