"""End-to-end mission lifecycle without a live ROS graph.

Drives the real modules together: watchdog (fake inotify, fake harvest
pipeline) -> mission_start (mocked prompts) -> mission_close (save) ->
ros2 fair list. Only subprocess-level ROS interaction is faked.
"""

import io
import json
from types import SimpleNamespace
from unittest import mock

from inotify_simple import flags
from rich.console import Console

from fair_ros.manifest import builder
from fair_ros.subcommands import list_missions, mission_close, mission_start
from fair_ros.utils import paths
from fair_ros.watchdog.watchdog import Watchdog
from tests.conftest import make_bag
from tests.unit.test_watchdog import FakeClock, FakeINotify, good_pipeline

T0 = 1_750_000_000.0


def _console():
    return Console(file=io.StringIO(), width=120, force_terminal=False)


def test_full_mission_lifecycle(fair_dirs):
    # 1. watchdog comes up with an empty spool (boot)
    ino, clock = FakeINotify(), FakeClock()
    dog = Watchdog(inotify=ino, clock=clock, pipeline=good_pipeline,
                   harvest_in_thread=False)
    dog.start()

    # 2. operator runs the briefing
    answers = {"operator_name": "Jane Doe", "goal": "Survey eelgrass beds",
               "location_name": "Marsh Creek, north bank",
               "environment": "marine", "notes": None}
    with mock.patch.object(mission_start.briefing, "ask_briefing",
                           return_value=answers):
        assert mission_start.run(SimpleNamespace(), console=_console()) == 0

    # 3. a recording happens (rosbag2 simulated by the fixture); GPS drops
    #    out for ~4 minutes mid-mission
    fix = [t for t in
           [T0 + i / 10 for i in range(0, 12000)] if not
           (T0 + 240 < t < T0 + 480)]
    bag = make_bag(paths.bags_dir() / "rosbag2_mission",
                   {"/fix": fix},
                   types={"/fix": "sensor_msgs/msg/NavSatFix"})
    ino.emit_dir_created(paths.bags_dir(), "rosbag2_mission")
    dog.step(0)
    ino.emit_file(bag, "rosbag2_mission_0.db3", flags.CREATE)
    dog.step(0)
    assert dog.state == "RECORDING"
    ino.emit_file(bag, "metadata.yaml", flags.CLOSE_WRITE)
    dog.step(0)
    assert dog.state == "IDLE"

    # 4. operator closes the mission and saves
    console = _console()
    with mock.patch.object(mission_close.review, "confirm_save",
                           return_value="save"):
        assert mission_close.run(SimpleNamespace(), console=console) == 0
    out = console.file.getvalue()
    assert "GPS signal was lost for 4 minutes" in out
    assert "Mission saved" in out

    # 5. the crate is complete and the spool is clean
    archives = [p for p in paths.archive_dir().iterdir()
                if p.is_dir() and p.name != ".staging"]
    assert len(archives) == 1
    crate = archives[0]
    assert crate.name.endswith("_marsh-creek-north-bank_jane-doe")
    assert (crate / "bags" / "rosbag2_mission" / "metadata.yaml").is_file()
    doc = json.loads((crate / "ro-crate-metadata.json").read_text())
    ids = {e["@id"] for e in doc["@graph"]}
    assert {"./", "#operator", "#place", "#robot", "#sensor-gps0",
            "#mission", "#ros2"} <= ids
    record = json.loads((crate / "mission_record.json").read_text())
    assert record["provenance"]["field_confidence"]["intent.goal"] == "user"
    assert record["bags"][0]["health_warnings"][0]["kind"] == "gap"
    assert not any(paths.bags_dir().iterdir())
    assert not paths.harvest_json_path().exists()

    # 6. the mission is findable
    console = _console()
    args = SimpleNamespace(operator=None, location=None, since=None,
                           until=None, limit=20, path=False)
    assert list_missions.run(args, console=console) == 0
    listing = console.file.getvalue()
    assert "Jane Doe" in listing
    assert "Marsh Creek" in listing
    assert "1" in listing  # the warning column
