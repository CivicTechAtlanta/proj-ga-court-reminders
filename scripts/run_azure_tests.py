"""Start the Azure Functions host, run integration tests, then shut it down.

Usage:
    uv run python scripts/run_azure_tests.py
"""

import subprocess
import sys
import time
import urllib.error
import urllib.request

FUNC_HOST_URL = "http://localhost:7071/api/twilioHandler"
MAX_WAIT_SECONDS = 10


def start_function_host():
    """Start 'func start' in the azure_functions/ directory as a background process."""
    return subprocess.Popen(
        ["uv", "run", "func", "start"],
        cwd="azure_functions",
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def wait_for_host(url=FUNC_HOST_URL, timeout=MAX_WAIT_SECONDS):
    """Poll the function host until it responds or the timeout is reached."""
    for i in range(timeout):
        try:
            urllib.request.urlopen(url)
            return True
        except urllib.error.URLError:
            time.sleep(1)
    return False


def run_tests():
    """Run the Azure integration tests and return the exit code."""
    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "pytest",
            "tests/integration/test_azure_functions.py",
            "-v",
        ],
    )
    return result.returncode


def main():
    print("Starting function host...")
    host_process = start_function_host()

    try:
        if not wait_for_host():
            print(
                f"Function host did not start within {MAX_WAIT_SECONDS}s",
                file=sys.stderr,
            )
            sys.exit(1)

        exit_code = run_tests()
    finally:
        host_process.terminate()
        host_process.wait()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
