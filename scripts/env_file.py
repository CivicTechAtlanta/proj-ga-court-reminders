"""Read a .env file without a dependency.

Both the local deploy and the TrueDialog check need the repository .env, and
neither wants python-dotenv pulled in for it. Nothing here touches
os.environ: callers decide what wins.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_ROOT / ".env"


def read(path=None):
    """KEY=VALUE pairs from a .env file: blank lines, comments, and an
    `export ` prefix are tolerated and surrounding quotes are stripped.
    A missing file is an empty mapping, not an error."""
    path = ENV_FILE if path is None else Path(path)
    values = {}
    if not path.exists():
        return values
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values
