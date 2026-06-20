"""Write ro-crate-metadata.json (specs/ro_crate_schema.md).

Hand-rolled JSON-LD so the entity layout matches the spec exactly. The crate
is generated from the MissionRecord only; the assembler supplies the inventory
of extra files it actually copied (this writer does no filesystem reads).
"""

import json
from pathlib import Path

from fair_ros.manifest.schema import MissionRecord

FAIR_ROS_ID = "https://github.com/gdl-res/ROS-FAIRy"

_ENCODING = {
    "sqlite3": "application/x-sqlite3",
    "mcap": "application/x-mcap",
}

_CONFIDENCE_USER = {"@type": "PropertyValue", "name": "fair-ros:confidence",
                    "value": "user"}


def _prop(name: str, value) -> dict:
    return {"@type": "PropertyValue", "name": name, "value": value}


def build(record: MissionRecord, extra_files: list[dict] | None = None,
          license_url: str | None = None) -> dict:
    """The complete JSON-LD document as a dict.

    extra_files: [{"id": relpath, "name": ..., "encodingFormat": ...,
                   "sha256": ...?}] for files the assembler copied beyond
    mission_record.json and README.md.
    """
    extra_files = extra_files or []
    graph: list[dict] = []

    graph.append({
        "@id": "ro-crate-metadata.json",
        "@type": "CreativeWork",
        "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
        "about": {"@id": "./"},
        "sdPublisher": {"@id": FAIR_ROS_ID},
    })

    description = record.intent.goal
    if record.intent.environment:
        description += f" Environment: {record.intent.environment}."
    if record.intent.notes:
        description += f" Notes: {record.intent.notes}."

    file_entities = [
        {"@id": "mission_record.json", "@type": "File",
         "name": "Mission record (machine-readable)",
         "encodingFormat": "application/json"},
        {"@id": "README.md", "@type": "File", "name": "Mission summary",
         "encodingFormat": "text/markdown"},
    ]
    for extra in extra_files:
        entity = {"@id": extra["id"], "@type": "File",
                  "name": extra["name"],
                  "encodingFormat": extra["encodingFormat"]}
        if extra.get("sha256"):
            entity["sha256"] = extra["sha256"]
        file_entities.append(entity)
    for cal in record.calibrations:
        if cal.archived_path:
            entity = {"@id": cal.archived_path, "@type": "File",
                      "name": f"Calibration: {cal.name}",
                      "encodingFormat": "application/yaml"
                      if (cal.format or "yaml") == "yaml"
                      else "application/octet-stream"}
            if cal.sha256:
                entity["sha256"] = cal.sha256
            file_entities.append(entity)

    bag_ids = [b.path.rstrip("/") + "/" for b in record.bags]

    root: dict = {
        "@id": "./",
        "@type": "Dataset",
        "identifier": record.identity.mission_id,
        "name": record.intent.goal,
        "description": description,
        "dateCreated": record.identity.created_at.isoformat(),
        "author": {"@id": "#operator"},
        "contentLocation": {"@id": "#place"},
        "keywords": ["robotics", "field-mission"] +
                    ([record.intent.environment]
                     if record.intent.environment else []),
        "mentions": {"@id": "#mission"},
        "hasPart": [{"@id": f["@id"]} for f in file_entities] +
                   [{"@id": bid} for bid in bag_ids],
    }
    if record.provenance.assembled_at:
        root["datePublished"] = record.provenance.assembled_at.isoformat()
    if record.robot:
        root["publisher"] = {"@id": "#organization"}
    if license_url:
        root["license"] = license_url
    graph.append(root)

    operator: dict = {"@id": "#operator", "@type": "Person",
                      "name": record.identity.operator_name,
                      "additionalProperty": _CONFIDENCE_USER}
    if record.identity.operator_contact:
        operator["email"] = record.identity.operator_contact
    graph.append(operator)

    if record.robot:
        graph.append({"@id": "#organization", "@type": "Organization",
                      "name": record.robot.owner_organization,
                      "email": record.robot.owner_contact})

    graph.append({"@id": "#place", "@type": "Place",
                  "name": record.intent.location_name,
                  "additionalProperty": _CONFIDENCE_USER})

    cal_paths = {c.name: c.archived_path for c in record.calibrations}
    if record.robot:
        graph.append({
            "@id": "#robot",
            "@type": ["Thing", "sosa:Platform"],
            "name": record.robot.name,
            "model": record.robot.platform,
            "serialNumber": record.robot.serial_number,
            "owner": {"@id": "#organization"},
            "sosa:hosts": [{"@id": f"#sensor-{s.sensor_id}"}
                           for s in record.sensors],
        })
    for sensor in record.sensors:
        entity: dict = {
            "@id": f"#sensor-{sensor.sensor_id}",
            "@type": "sosa:Sensor",
            "name": sensor.make_model,
            "description": f"{sensor.type} publishing on {sensor.topic}",
            "sosa:isHostedBy": {"@id": "#robot"},
            "additionalProperty": [
                _prop("topic", sensor.topic),
                _prop("detected_at_start",
                      str(sensor.detected_at_start).lower()),
            ],
        }
        if sensor.frame_id:
            entity["additionalProperty"].insert(
                1, _prop("frame_id", sensor.frame_id))
        archived = cal_paths.get(sensor.calibration_ref or "")
        if archived:
            entity["subjectOf"] = {"@id": archived}
        graph.append(entity)

    instruments = []
    if record.robot:
        instruments.append({"@id": "#robot"})
    if record.software.ros_distro:
        instruments.append({"@id": "#ros2"})
    if record.software.python_env:
        instruments.append({"@id": "#python-runtime"})
    instruments += [{"@id": f"#container-{c.name}"}
                    for c in record.software.docker_containers]
    mission: dict = {
        "@id": "#mission",
        "@type": "CreateAction",
        "name": f"Field mission {record.identity.mission_id}",
        "description": record.intent.goal,
        "agent": {"@id": "#operator"},
        "location": {"@id": "#place"},
        "result": {"@id": "./"},
        "additionalProperty": _CONFIDENCE_USER,
    }
    if instruments:
        mission["instrument"] = instruments
    if record.bags:
        mission["startTime"] = min(b.start_time
                                   for b in record.bags).isoformat()
        mission["endTime"] = max(b.end_time for b in record.bags).isoformat()
    graph.append(mission)

    graph.append({"@id": FAIR_ROS_ID, "@type": "SoftwareApplication",
                  "name": "fair-ros",
                  "version": record.provenance.fair_ros_version})
    if record.software.ros_distro:
        graph.append({"@id": "#ros2", "@type": "SoftwareApplication",
                      "name": "ROS 2", "version": record.software.ros_distro,
                      "url": "https://ros.org"})
    if record.software.python_env:
        pe = record.software.python_env
        py_entity = {"@id": "#python-runtime",
                     "@type": "SoftwareApplication",
                     "name": "Python",
                     "version": pe.version,
                     "additionalProperty": [_prop("executable",
                                                  pe.executable)]}
        if pe.venv_path:
            py_entity["additionalProperty"].append(
                _prop("venv_path", pe.venv_path))
        graph.append(py_entity)
    for container in record.software.docker_containers:
        entity = {"@id": f"#container-{container.name}",
                  "@type": "SoftwareApplication",
                  "name": container.name,
                  "softwareVersion": container.image}
        if container.digest:
            entity["identifier"] = container.digest
        graph.append(entity)

    for i, bag in enumerate(record.bags, start=1):
        entity = {
            "@id": bag.path.rstrip("/") + "/",
            "@type": "Dataset",
            "name": f"Recording {i}",
            "contentSize": str(bag.size_bytes),
            "dateCreated": bag.start_time.isoformat(),
            "temporalCoverage": f"{bag.start_time.isoformat()}/"
                                f"{bag.end_time.isoformat()}",
            "encodingFormat": _ENCODING.get(bag.storage_format,
                                            "application/octet-stream"),
            "variableMeasured": [
                {"@type": "PropertyValue", "name": t.name,
                 "description": t.type, "value": t.message_count}
                for t in bag.topics],
        }
        comments = [w.plain_text for w in bag.health_warnings]
        if len(comments) == 1:
            entity["comment"] = comments[0]
        elif comments:
            entity["comment"] = comments
        graph.append(entity)

    graph.extend(file_entities)

    return {
        "@context": [
            "https://w3id.org/ro/crate/1.1/context",
            {"sosa": "http://www.w3.org/ns/sosa/",
             "ssn": "http://www.w3.org/ns/ssn/"},
        ],
        "@graph": graph,
    }


def write(record: MissionRecord, crate_root: Path,
          extra_files: list[dict] | None = None,
          license_url: str | None = None) -> None:
    document = build(record, extra_files, license_url)
    (crate_root / "ro-crate-metadata.json").write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n")
