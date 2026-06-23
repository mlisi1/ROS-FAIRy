"""Capture, serialise and read back the ROS 2 environment.

The watchdog runs as a system service with no login shell, so the ROS
environment the operator had sourced is snapshotted into a systemd-style
``KEY=value`` file. Two such files exist:

- ``/etc/fair-ros/watchdog.env`` — frozen at ``ros2 fair setup``, loaded by the
  unit's ``EnvironmentFile=``. This is what the service starts with.
- ``<spool>/session.env`` — refreshed by ``mission_start`` / ``mission_record``
  from the *live recording shell* and applied by the watchdog at harvest time,
  so the harvest always matches the session actually recording even if the
  frozen snapshot has drifted (different ROS_DOMAIN_ID / RMW / overlay).

This module is the single source of truth for which variables count as "the ROS
environment" and how the files are written and parsed.
"""

import os
from collections.abc import Mapping
from pathlib import Path

# Every ROS/build-tool variable plus the search paths ros2 and rclpy need to
# find their plugins and libraries. Keep in sync with the unit documentation.
ROS_ENV_PREFIXES = ("ROS_", "AMENT_", "RMW_", "COLCON_")
ROS_ENV_NAMES = (
    "PATH", "LD_LIBRARY_PATH", "PYTHONPATH", "CMAKE_PREFIX_PATH",
    "CYCLONEDDS_URI", "FASTRTPS_DEFAULT_PROFILES_FILE",
    "FASTDDS_DEFAULT_PROFILES_FILE",
)

# Variables whose mismatch puts the watchdog on a different DDS partition than
# the recorder (an empty graph even though everything is "running").
DISCOVERY_KEYS = ("ROS_DOMAIN_ID", "RMW_IMPLEMENTATION")


def capture(environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """The ROS-relevant subset of an environment (defaults to the process)."""
    source: Mapping[str, str] = os.environ if environ is None else environ
    return {
        key: val for key, val in source.items()
        if key in ROS_ENV_NAMES or key.startswith(ROS_ENV_PREFIXES)
    }


def serialize(env: dict[str, str]) -> str:
    """Render as a systemd EnvironmentFile (``KEY=value`` per line, sorted)."""
    lines = [f"{key}={env[key]}" for key in sorted(env)]
    return "\n".join(lines) + ("\n" if lines else "")


def parse(text: str) -> dict[str, str]:
    """Parse ``KEY=value`` lines; ignores blanks and ``#`` comments."""
    env: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, val = line.partition("=")
        if sep:
            env[key.strip()] = val.strip()
    return env


def read_file(path: Path) -> dict[str, str]:
    """Parsed env file, or ``{}`` if it is absent or unreadable."""
    try:
        return parse(path.read_text())
    except OSError:
        return {}


def write_file(path: Path, env: dict[str, str], mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialize(env))
    try:
        os.chmod(path, mode)
    except OSError:
        pass
