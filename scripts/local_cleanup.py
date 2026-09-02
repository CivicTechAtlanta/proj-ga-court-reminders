"""Remove the Docker containers (and, on request, volumes) Floci created for this project.

Floci names the containers it starts after the CDK stack (Lambda and
custom-resource helpers), the RDS engine (`floci-rds-*`), and its image
registry, and it does not remove them, or the volumes behind them, when a
stack is deleted. Without this step they outlive `docker compose down`.

    python scripts/local_cleanup.py            # containers only (local-down)
    python scripts/local_cleanup.py --volumes  # also the data (local-reset)
"""

import argparse
import json
import subprocess


PROJECT_NETWORK = "court-reminders_default"
# Every stack in this project, including any deployed by mistake.
STACK_PREFIX = "floci-Court"
# Shared helper names; claimed only when attached to the project network.
SHARED_HELPERS = ("floci-rds-", "floci-ecr-registry")
# Lambda code volumes carry the stack name; RDS volumes are found through
# the containers that mount them.
CODE_VOLUME_PREFIX = "floci-code-Court"


def _docker(*args):
    return subprocess.run(
        ["docker", *args], check=True, capture_output=True, text=True
    ).stdout


def _container_names():
    return _docker("ps", "--all", "--format", "{{.Names}}").splitlines()


def _inspect(name):
    return json.loads(_docker("inspect", name))[0]


def _belongs_to_project(name):
    if name.startswith(STACK_PREFIX):
        return True
    if not name.startswith(SHARED_HELPERS):
        return False
    return PROJECT_NETWORK in _inspect(name)["NetworkSettings"]["Networks"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--volumes", action="store_true", help="also remove the containers' volumes"
    )
    args = parser.parse_args()

    containers = [name for name in _container_names() if _belongs_to_project(name)]
    volumes = set()
    if args.volumes:
        for name in containers:
            volumes.update(
                mount["Name"]
                for mount in _inspect(name)["Mounts"]
                if mount["Type"] == "volume"
            )
        volumes.update(
            volume
            for volume in _docker("volume", "ls", "--quiet").splitlines()
            if volume.startswith(CODE_VOLUME_PREFIX)
        )

    if containers:
        subprocess.run(["docker", "rm", "--force", *containers], check=True)
    else:
        print("No Floci helper containers to remove")
    if volumes:
        subprocess.run(["docker", "volume", "rm", *sorted(volumes)], check=True)
        print(f"Removed {len(volumes)} Floci volume(s)")


if __name__ == "__main__":
    main()
