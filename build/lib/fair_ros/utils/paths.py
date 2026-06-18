"""Canonical filesystem paths for fair-ros.

Every other module must obtain paths from here. The roots are overridable via
environment variables so tests (and unusual deployments) can relocate them:

- ``FAIR_ROS_VAR_DIR``    -> default ``/var/fair-ros``
- ``FAIR_ROS_CONFIG_DIR`` -> default ``/etc/fair-ros``

Paths are resolved lazily (functions, not module constants) so an env change
made by a test fixture takes effect immediately.
"""

import os
from pathlib import Path

DEFAULT_VAR_DIR = "/var/fair-ros"
DEFAULT_CONFIG_DIR = "/etc/fair-ros"


def var_dir() -> Path:
    return Path(os.environ.get("FAIR_ROS_VAR_DIR", DEFAULT_VAR_DIR))


def config_dir() -> Path:
    return Path(os.environ.get("FAIR_ROS_CONFIG_DIR", DEFAULT_CONFIG_DIR))


def robot_identity_path() -> Path:
    return config_dir() / "robot_identity.yaml"


def spool_dir() -> Path:
    return var_dir() / "spool"


def bags_dir() -> Path:
    return spool_dir() / "bags"


def harvest_json_path() -> Path:
    return spool_dir() / "harvest.json"


def mission_context_path() -> Path:
    return spool_dir() / "mission_context.json"


def archive_dir() -> Path:
    return var_dir() / "archive"


def staging_dir() -> Path:
    return archive_dir() / ".staging"


def index_db_path() -> Path:
    return var_dir() / "index.db"


def watchdog_state_path() -> Path:
    return var_dir() / "watchdog.state"
