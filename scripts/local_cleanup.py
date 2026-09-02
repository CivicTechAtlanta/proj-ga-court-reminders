"""Remove extra Docker containers that Floci created for this project.

This prevents local Lambda helper containers from continuing after shutdown.
"""

import json
import subprocess


PROJECT_NETWORK = "court-reminders_default"
# Floci names Lambda and custom-resource helpers after the CDK stack;
# match every stack in this project, including any deployed by mistake.
LAMBDA_PREFIX = "floci-Court"
FLOCI_HELPERS = {"floci-ecr-registry"}


def _container_names():
    result = subprocess.run(
        ["docker", "ps", "--all", "--format", "{{.Names}}"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.splitlines()


def _belongs_to_project(name):
    if name.startswith(LAMBDA_PREFIX):
        return True
    if name not in FLOCI_HELPERS:
        return False

    result = subprocess.run(
        ["docker", "inspect", name, "--format", "{{json .NetworkSettings.Networks}}"],
        check=True,
        capture_output=True,
        text=True,
    )
    return PROJECT_NETWORK in json.loads(result.stdout)


def main():
    containers = [name for name in _container_names() if _belongs_to_project(name)]
    if not containers:
        print("No Floci helper containers to remove")
        return

    subprocess.run(["docker", "rm", "--force", *containers], check=True)


if __name__ == "__main__":
    main()
