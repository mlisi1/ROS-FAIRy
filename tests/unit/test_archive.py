import json

import pytest

from fair_ros.archive import assembler, index, ro_crate
from fair_ros.archive.assembler import AssemblyError
from fair_ros.manifest import builder
from fair_ros.utils import fsio, paths
from tests.conftest import make_bag

T0 = 1_750_000_000.0


def _steady(start, end, hz):
    n = int((end - start) * hz)
    return [start + i / hz for i in range(n + 1)]


def _spool(fair_dirs, n_bags=1, with_cal=True):
    """Populate the spool with real bags + harvest + context documents."""
    cal_file = fair_dirs["cfg"] / "gps0.yaml"
    cal_file.write_text("fx: 1\n")
    identity = {
        "robot": {"name": "Heron-02", "platform": "Clearpath Heron USV",
                  "serial_number": "H02", "owner_organization": "Lab",
                  "owner_contact": "fleet@example.org"},
        "sensors": [{"sensor_id": "gps0", "type": "gps",
                     "make_model": "u-blox ZED-F9P", "topic": "/fix",
                     "frame_id": "gps_link",
                     "calibration_ref": "gps0_cal" if with_cal else None}],
        "calibrations": [{"name": "gps0_cal", "source_path": str(cal_file),
                          "format": "yaml"}] if with_cal else [],
        "default_license": "https://spdx.org/licenses/CC-BY-4.0",
    }
    harvest = builder.compose_harvest(
        identity=identity,
        system={"hostname": "r1", "kernel": "Linux 6.8", "arch": "x86_64",
                "ros_distro": "jazzy", "apt_ros_versions": {}},
        graph={"captured_at": "2026-06-12T14:03:00+00:00",
               "nodes": ["/navsat"],
               "topics": [{"name": "/fix",
                           "type": "sensor_msgs/msg/NavSatFix"}],
               "ros_packages": ["rclpy"], "parameters": {}, "complete": True},
        docker={"docker_containers": [
            {"name": "navstack", "image": "example/navstack:1.4",
             "digest": "example/navstack@sha256:7be1",
             "compose_project": None, "compose_file": None}],
            "raw_inspect": [{"Name": "/navstack"}], "available": True},
        descriptions={"robot_description": "<robot name='heron'/>",
                      "tf_static": [{"parent_frame": "base", "child_frame":
                                     "gps_link"}]},
        harvest_status={"robot_identity": "ok", "system_info": "ok",
                        "ros_graph": "ok", "ros_descriptions": "ok",
                        "docker_info": "ok"})
    for i in range(n_bags):
        bag = make_bag(paths.bags_dir() / f"rosbag2_{i}",
                       {"/fix": _steady(T0 + i * 700, T0 + i * 700 + 600, 10)})
        harvest["bags"].append({
            "path": str(bag), "storage_format": "sqlite3",
            "size_bytes": fsio.dir_size_bytes(bag),
            "start_time": "2026-06-12T14:03:00+00:00",
            "end_time": "2026-06-12T14:13:00+00:00",
            "duration_s": 600.0, "message_count": 6001,
            "topics": [{"name": "/fix", "type": "sensor_msgs/msg/NavSatFix",
                        "message_count": 6001, "avg_frequency_hz": 10.0}],
            "health_warnings": []})
    harvest["provenance"]["harvested_at"] = "2026-06-12T14:14:00+00:00"
    context = builder.new_mission_context(
        operator_name="Jane Doe", goal="Survey eelgrass beds",
        location_name="Marsh Creek, north bank", environment="marine")
    fsio.atomic_write_json(paths.harvest_json_path(), harvest)
    fsio.atomic_write_json(paths.mission_context_path(), context)
    return harvest, context


def test_sanitise():
    assert assembler.sanitise("Marsh Creek, north bank") == \
        "marsh-creek-north-bank"
    assert assembler.sanitise("Jane Doe") == "jane-doe"
    assert assembler.sanitise("Forêt d'Orléans!") == "foret-d-orleans"
    assert assembler.sanitise("///") == "unknown"


def test_assemble_full_crate(fair_dirs):
    harvest, context = _spool(fair_dirs)
    record = builder.build(harvest, context)
    final = assembler.assemble(record, harvest)

    assert final.parent == paths.archive_dir()
    assert final.name.endswith("_marsh-creek-north-bank_jane-doe")
    # bags moved, not copied
    assert not any(paths.bags_dir().iterdir())
    assert (final / "bags" / "rosbag2_0" / "metadata.yaml").is_file()
    # artifacts
    assert (final / "harvest" / "harvest.json").is_file()
    assert (final / "harvest" / "robot_description.urdf").read_text() == \
        "<robot name='heron'/>"
    assert (final / "harvest" / "tf_static.json").is_file()
    assert (final / "calibrations" / "gps0.yaml").is_file()
    assert (final / "docker" / "containers.json").is_file()
    assert "Survey eelgrass beds" in (final / "README.md").read_text()
    # manifest updated with crate-relative paths and hashes
    saved = json.loads((final / "mission_record.json").read_text())
    assert saved["bags"][0]["path"] == "bags/rosbag2_0"
    assert saved["ros_graph"]["robot_description"] == \
        "harvest/robot_description.urdf"
    assert saved["calibrations"][0]["archived_path"] == \
        "calibrations/gps0.yaml"
    assert len(saved["calibrations"][0]["sha256"]) == 64
    # spool context cleared
    assert not paths.harvest_json_path().exists()
    assert not paths.mission_context_path().exists()
    # indexed
    rows, total = index.query()
    assert total == 1
    assert rows[0]["operator"] == "Jane Doe"
    assert rows[0]["archive_path"] == str(final)
    assert rows[0]["bag_count"] == 1


def test_ro_crate_document(fair_dirs):
    harvest, context = _spool(fair_dirs)
    record = builder.build(harvest, context)
    final = assembler.assemble(record, harvest)
    doc = json.loads((final / "ro-crate-metadata.json").read_text())

    assert doc["@context"][0] == "https://w3id.org/ro/crate/1.1/context"
    assert doc["@context"][1]["sosa"] == "http://www.w3.org/ns/sosa/"
    by_id = {e["@id"]: e for e in doc["@graph"]}

    root = by_id["./"]
    assert root["name"] == "Survey eelgrass beds"
    assert root["license"] == "https://spdx.org/licenses/CC-BY-4.0"
    assert {"@id": "bags/rosbag2_0/"} in root["hasPart"]
    assert {"@id": "mission_record.json"} in root["hasPart"]
    assert "marine" in root["keywords"]

    assert by_id["#operator"]["name"] == "Jane Doe"
    assert by_id["#operator"]["email"] == "fleet@example.org"
    assert by_id["#place"]["name"] == "Marsh Creek, north bank"
    assert by_id["#robot"]["@type"] == ["Thing", "sosa:Platform"]
    assert by_id["#robot"]["sosa:hosts"] == [{"@id": "#sensor-gps0"}]

    sensor = by_id["#sensor-gps0"]
    assert sensor["sosa:isHostedBy"] == {"@id": "#robot"}
    assert sensor["subjectOf"] == {"@id": "calibrations/gps0.yaml"}

    mission = by_id["#mission"]
    assert mission["agent"] == {"@id": "#operator"}
    assert {"@id": "#robot"} in mission["instrument"]
    assert {"@id": "#ros2"} in mission["instrument"]
    assert {"@id": "#container-navstack"} in mission["instrument"]
    assert mission["startTime"] == "2026-06-12T14:03:00+00:00"

    bag = by_id["bags/rosbag2_0/"]
    assert bag["encodingFormat"] == "application/x-sqlite3"
    assert bag["variableMeasured"][0]["name"] == "/fix"
    assert by_id["#ros2"]["version"] == "jazzy"
    assert by_id["#container-navstack"]["identifier"] == \
        "example/navstack@sha256:7be1"
    assert by_id["calibrations/gps0.yaml"]["sha256"]
    assert by_id["ro-crate-metadata.json"]["about"] == {"@id": "./"}


def test_archive_name_collision(fair_dirs):
    harvest, context = _spool(fair_dirs, n_bags=2)
    record = builder.build(harvest, context)
    first = assembler.assemble(record, harvest)

    harvest2, context2 = _spool(fair_dirs)
    context2["identity"]["created_at"] = context["identity"]["created_at"]
    record2 = builder.build(harvest2, context2)
    record2.identity.created_at = record.identity.created_at
    second = assembler.assemble(record2, harvest2)
    assert second.name == first.name + "_2"


def test_failure_before_bag_move_leaves_spool_intact(fair_dirs, monkeypatch):
    harvest, context = _spool(fair_dirs)
    record = builder.build(harvest, context)

    def boom(*a, **kw):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(assembler.ro_crate, "write", boom)
    with pytest.raises(AssemblyError, match="disk space"):
        assembler.assemble(record, harvest)
    assert (paths.bags_dir() / "rosbag2_0" / "metadata.yaml").is_file()
    assert paths.harvest_json_path().exists()
    assert not any(paths.archive_dir().glob("2026*"))
    assert not list(paths.staging_dir().glob("*"))


def test_bag_move_failure_rolls_back(fair_dirs, monkeypatch):
    harvest, context = _spool(fair_dirs, n_bags=2)
    record = builder.build(harvest, context)

    real_move = assembler._move_bag
    calls = {"n": 0}

    def flaky_move(src, dest, progress):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError(5, "Input/output error")
        real_move(src, dest, progress)

    monkeypatch.setattr(assembler, "_move_bag", flaky_move)
    with pytest.raises(AssemblyError, match="back in the spool"):
        assembler.assemble(record, harvest)
    assert (paths.bags_dir() / "rosbag2_0").is_dir()
    assert (paths.bags_dir() / "rosbag2_1").is_dir()
    assert not list(paths.staging_dir().glob("*"))


def test_resume_interrupted_staging(fair_dirs):
    harvest, context = _spool(fair_dirs)
    record = builder.build(harvest, context)
    name = assembler.archive_name(record)
    staging = paths.staging_dir() / name
    staging.mkdir(parents=True)
    record.provenance.assembled_at = record.identity.created_at
    fsio.atomic_write_json(staging / "mission_record.json",
                           record.model_dump(mode="json"))

    found = assembler.find_interrupted_staging()
    assert found == staging
    final = assembler.resume_commit(found)
    assert final.name == name
    rows, total = index.query()
    assert total == 1


def test_index_filters(fair_dirs):
    harvest, context = _spool(fair_dirs)
    record = builder.build(harvest, context)
    assembler.assemble(record, harvest)

    rows, total = index.query(operator="jane")
    assert total == 1
    rows, total = index.query(operator="nobody")
    assert total == 0
    rows, total = index.query(location="marsh")
    assert total == 1
    rows, total = index.query(since="2099-01-01")
    assert total == 0
    rows, total = index.query(limit=0)
    assert rows == [] and total == 1


def test_reindex_rebuilds(fair_dirs):
    harvest, context = _spool(fair_dirs)
    record = builder.build(harvest, context)
    final = assembler.assemble(record, harvest)
    paths.index_db_path().unlink()
    assert index.reindex() == 1
    rows, total = index.query()
    assert rows[0]["archive_path"] == str(final)
