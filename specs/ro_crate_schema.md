# Spec: RO-Crate JSON-LD Schema

`archive/ro_crate.py` writes `ro-crate-metadata.json` at the crate root,
conformant with **RO-Crate 1.1**, using **schema.org** types plus **W3C
SSN/SOSA** for sensors and observation context. The file is generated from the
`MissionRecord` only — it must never contain information absent from
`mission_record.json`.

## Context

```json
"@context": [
  "https://w3id.org/ro/crate/1.1/context",
  {
    "sosa": "http://www.w3.org/ns/sosa/",
    "ssn":  "http://www.w3.org/ns/ssn/"
  }
]
```

## Entity inventory

| Entity | `@type` | `@id` convention | From |
|---|---|---|---|
| Metadata descriptor | `CreativeWork` | `ro-crate-metadata.json` | fixed |
| Root Data Entity | `Dataset` | `./` | whole mission |
| Operator | `Person` | `#operator` | `identity` |
| Owner | `Organization` | `#organization` | `robot` |
| Location | `Place` | `#place` | `intent.location_name` |
| Robot | `sosa:Platform` (+ `Thing`) | `#robot` | `robot` |
| Each sensor | `sosa:Sensor` | `#sensor-<sensor_id>` | `sensors[]` |
| The mission act | `CreateAction` | `#mission` | `identity` + `intent` |
| fair-ros | `SoftwareApplication` | `https://github.com/<org>/fair-ros` | `provenance` |
| ROS 2 | `SoftwareApplication` | `#ros2` | `software.ros_distro` |
| Python runtime | `SoftwareApplication` | `#python-runtime` | `software.python_env` |
| Each container image | `SoftwareApplication` | `#container-<name>` | `software.docker_containers[]` |
| Each bag dir | `Dataset` | `bags/<dir>/` (trailing slash) | `bags[]` |
| Each plain file | `File` | crate-relative path | manifest/cal/docker files |
| Each PropertyValue | `PropertyValue` | `#…` (see below) | sensor facts, bag topics, confidence, python props |

Rules:
- Data entities (things that are files/dirs in the crate) use **relative path**
  `@id`s; contextual entities use `#fragment` ids; external things use URLs.
- Every data entity reachable from the root `Dataset.hasPart` (directly or via
  nested bag `Dataset`s).
- `mission_record.json`, `harvest/harvest.json`, etc. are `File` entities with
  `encodingFormat: "application/json"`.
- **Flattened form:** the crate is *flattened* JSON-LD — no nested node objects.
  Every `PropertyValue` is its own `@graph` entity with an `@id`, referenced from
  its parent via `{"@id": …}`. This is what lets the `rocrate` library load the
  crate (it rejects nested objects that lack an `@id`). PropertyValue ids:
  - confidence marker: `#confidence-user` (one shared entity, referenced by
    `#operator`, `#place`, `#mission`);
  - sensor facts: `#sensor-<id>-topic`, `#sensor-<id>-frame_id`,
    `#sensor-<id>-detected_at_start`;
  - python runtime: `#python-runtime-executable`, `#python-runtime-venv_path`;
  - bag topics: `#bag<n>-measure-<m>` (n = 1-based bag, m = 1-based topic).

## Root Data Entity mapping

| JSON-LD property | MissionRecord source |
|---|---|
| `name` | `intent.goal` |
| `description` | goal + environment + notes, joined as readable sentences |
| `identifier` | `identity.mission_id` |
| `dateCreated` | `identity.created_at` |
| `datePublished` | `provenance.assembled_at` |
| `author` | `{"@id": "#operator"}` |
| `publisher` | `{"@id": "#organization"}` |
| `contentLocation` | `{"@id": "#place"}` |
| `license` | from optional `robot_identity.yaml → owner.default_license` (SPDX URL); omitted if unset |
| `keywords` | `["robotics", "field-mission", intent.environment?]` |
| `hasPart` | all bag Datasets + all File entities |
| `mentions` | `{"@id": "#mission"}` |

## Key contextual mappings

**`#mission` (CreateAction)** — models the recording act:
`agent → #operator`, `instrument → #robot`, `location → #place`,
`startTime / endTime` from earliest bag start / latest bag end,
`result → ./`, `description → intent.goal`.

**`#robot` (sosa:Platform)** — `name`, `model` (= `robot.platform`),
`serialNumber`, `owner → #organization`, and `sosa:hosts` listing every sensor id.

**`#sensor-<id>` (sosa:Sensor)** — `name` (= make_model),
`description` ("<type> publishing on <topic>"), `sosa:isHostedBy → #robot`.
If the sensor has a calibration: `subjectOf → calibrations/<file>` File entity.
`additionalProperty`: **references** to hoisted PropertyValue entities for
`topic`, `frame_id` (omitted when unset), and `detected_at_start` — these are
facts future users need; PropertyValue keeps us schema.org-valid without
inventing terms.

**Bag `Dataset`s** — `name` ("Recording 1"), `contentSize` (bytes, as string),
`dateCreated` / `temporalCoverage` (`start/end` ISO interval),
`encodingFormat`: `"application/x-sqlite3"` or `"application/x-mcap"` (storage
format from the bag), `variableMeasured`: a list of **references** to hoisted
`PropertyValue` entities, one per bag topic (`name` = topic,
`description` = ROS type, `value` = message count).
Health warnings: each becomes a `comment` string on the bag Dataset, using the
pre-rendered `plain_text`.

**Software** — `#ros2`: `name: "ROS 2"`, `version: software.ros_distro`,
`url: "https://ros.org"`. `#python-runtime` (emitted only when
`software.python_env` is set): `name: "Python"`, `version: python_env.version`,
plus `additionalProperty` PropertyValue pairs for `executable` and (when present)
`venv_path`. Containers: `name`, `softwareVersion` (image tag), `identifier`
(digest, when present). The root Dataset does not list software in `hasPart`
(they are not files); instead `#mission` lists them in `instrument` alongside the
robot, in order: `#robot`, `#ros2`, `#python-runtime`, `#container-<name>…`.

**Hardware** — `hardware_devices[]` is **not** mapped to per-device contextual
entities. A field robot exposes 15–30 USB/PCI entries (hubs, internal devices,
dongles) and the link from a raw device to a declared `sosa:Sensor` is not
established by the harvest layer, so individual entities would bloat the graph
without adding trustworthy structure. The full inventory lives in
`mission_record.json → hardware_devices[]`; humans read `harvest/lsusb_verbose.txt`.
(A future version may add `schema:IndividualProduct` entities once
sensor↔device matching exists.)

**Provenance of the crate itself** — the `CreativeWork` descriptor gets
`about → ./` (per spec) and `sdPublisher → fair-ros SoftwareApplication` with
`version: provenance.fair_ros_version`.

Confidence tags: each entity derived from `user`-confidence fields carries
`"additionalProperty": {"@id": "#confidence-user"}`, referencing the single
shared `PropertyValue` entity
`{"@id": "#confidence-user", "@type": "PropertyValue", "name": "fair-ros:confidence", "value": "user"}`.
It is referenced only where the distinction matters: `#operator`, `#place`, and
`#mission`. Auto fields carry no marker (auto is the default).

## Complete example (fictional mission)

```json
{
  "@context": [
    "https://w3id.org/ro/crate/1.1/context",
    { "sosa": "http://www.w3.org/ns/sosa/", "ssn": "http://www.w3.org/ns/ssn/" }
  ],
  "@graph": [
    {
      "@id": "ro-crate-metadata.json",
      "@type": "CreativeWork",
      "conformsTo": { "@id": "https://w3id.org/ro/crate/1.1" },
      "about": { "@id": "./" },
      "sdPublisher": { "@id": "https://github.com/example/fair-ros" }
    },
    {
      "@id": "./",
      "@type": "Dataset",
      "identifier": "m-20260612-140258-9f3a",
      "name": "Survey eelgrass beds along the north bank",
      "description": "Survey eelgrass beds along the north bank. Environment: marine. Notes: strong current near the weir.",
      "dateCreated": "2026-06-12T14:02:58+00:00",
      "datePublished": "2026-06-12T15:11:40+00:00",
      "author": { "@id": "#operator" },
      "publisher": { "@id": "#organization" },
      "contentLocation": { "@id": "#place" },
      "keywords": ["robotics", "field-mission", "marine"],
      "mentions": { "@id": "#mission" },
      "hasPart": [
        { "@id": "mission_record.json" },
        { "@id": "README.md" },
        { "@id": "harvest/harvest.json" },
        { "@id": "harvest/robot_description.urdf" },
        { "@id": "calibrations/gps0_cal.yaml" },
        { "@id": "docker/containers.json" },
        { "@id": "bags/rosbag2_2026_06_12-14_02_58/" }
      ]
    },
    {
      "@id": "#operator",
      "@type": "Person",
      "name": "Jane Doe",
      "email": "fleet@example.org",
      "additionalProperty": { "@id": "#confidence-user" }
    },
    {
      "@id": "#organization",
      "@type": "Organization",
      "name": "Example Marine Robotics Lab",
      "email": "fleet@example.org"
    },
    {
      "@id": "#place",
      "@type": "Place",
      "name": "Marsh Creek, north bank",
      "additionalProperty": { "@id": "#confidence-user" }
    },
    {
      "@id": "#robot",
      "@type": ["Thing", "sosa:Platform"],
      "name": "Heron-02",
      "model": "Clearpath Heron USV",
      "serialNumber": "H02-2031-XK",
      "owner": { "@id": "#organization" },
      "sosa:hosts": [ { "@id": "#sensor-gps0" }, { "@id": "#sensor-sonar0" } ]
    },
    {
      "@id": "#sensor-gps0",
      "@type": "sosa:Sensor",
      "name": "u-blox ZED-F9P",
      "description": "gps publishing on /fix",
      "sosa:isHostedBy": { "@id": "#robot" },
      "subjectOf": { "@id": "calibrations/gps0_cal.yaml" },
      "additionalProperty": [
        { "@id": "#sensor-gps0-topic" },
        { "@id": "#sensor-gps0-frame_id" },
        { "@id": "#sensor-gps0-detected_at_start" }
      ]
    },
    {
      "@id": "#sensor-sonar0",
      "@type": "sosa:Sensor",
      "name": "BlueRobotics Ping2",
      "description": "sonar publishing on /depth",
      "sosa:isHostedBy": { "@id": "#robot" },
      "additionalProperty": [
        { "@id": "#sensor-sonar0-topic" },
        { "@id": "#sensor-sonar0-detected_at_start" }
      ]
    },
    {
      "@id": "#mission",
      "@type": "CreateAction",
      "name": "Field mission m-20260612-140258-9f3a",
      "description": "Survey eelgrass beds along the north bank",
      "agent": { "@id": "#operator" },
      "instrument": [ { "@id": "#robot" }, { "@id": "#ros2" }, { "@id": "#python-runtime" }, { "@id": "#container-navstack" } ],
      "location": { "@id": "#place" },
      "startTime": "2026-06-12T14:02:58+00:00",
      "endTime": "2026-06-12T14:44:31+00:00",
      "result": { "@id": "./" },
      "additionalProperty": { "@id": "#confidence-user" }
    },
    {
      "@id": "https://github.com/example/fair-ros",
      "@type": "SoftwareApplication",
      "name": "fair-ros",
      "version": "0.1.0"
    },
    {
      "@id": "#ros2",
      "@type": "SoftwareApplication",
      "name": "ROS 2",
      "version": "jazzy",
      "url": "https://ros.org"
    },
    {
      "@id": "#python-runtime",
      "@type": "SoftwareApplication",
      "name": "Python",
      "version": "3.12.3 (main, Apr 10 2026, 09:12:00) [GCC 13.2.0]",
      "additionalProperty": [
        { "@id": "#python-runtime-executable" },
        { "@id": "#python-runtime-venv_path" }
      ]
    },
    {
      "@id": "#container-navstack",
      "@type": "SoftwareApplication",
      "name": "navstack",
      "softwareVersion": "example/navstack:1.4.2",
      "identifier": "example/navstack@sha256:7be1f0c1..."
    },
    {
      "@id": "bags/rosbag2_2026_06_12-14_02_58/",
      "@type": "Dataset",
      "name": "Recording 1",
      "contentSize": "3328599041",
      "dateCreated": "2026-06-12T14:02:58+00:00",
      "temporalCoverage": "2026-06-12T14:02:58+00:00/2026-06-12T14:44:31+00:00",
      "encodingFormat": "application/x-sqlite3",
      "variableMeasured": [
        { "@id": "#bag1-measure-1" },
        { "@id": "#bag1-measure-2" }
      ],
      "comment": "GPS signal was lost for 4 minutes, starting 12 minutes in."
    },
    { "@id": "mission_record.json", "@type": "File", "name": "Mission record (machine-readable)", "encodingFormat": "application/json" },
    { "@id": "README.md", "@type": "File", "name": "Mission summary", "encodingFormat": "text/markdown" },
    { "@id": "harvest/harvest.json", "@type": "File", "name": "Raw harvest data", "encodingFormat": "application/json" },
    { "@id": "harvest/robot_description.urdf", "@type": "File", "name": "Robot description (URDF)", "encodingFormat": "application/xml" },
    { "@id": "calibrations/gps0_cal.yaml", "@type": "File", "name": "Calibration: gps0_cal", "encodingFormat": "application/yaml", "sha256": "c3ab8ff13720e8ad9047dd39466b3c8974e592c2fa383d4a3960714caef0c4f2" },
    { "@id": "docker/containers.json", "@type": "File", "name": "Container inventory", "encodingFormat": "application/json" },

    { "@id": "#confidence-user", "@type": "PropertyValue", "name": "fair-ros:confidence", "value": "user" },
    { "@id": "#sensor-gps0-topic", "@type": "PropertyValue", "name": "topic", "value": "/fix" },
    { "@id": "#sensor-gps0-frame_id", "@type": "PropertyValue", "name": "frame_id", "value": "gps_link" },
    { "@id": "#sensor-gps0-detected_at_start", "@type": "PropertyValue", "name": "detected_at_start", "value": "true" },
    { "@id": "#sensor-sonar0-topic", "@type": "PropertyValue", "name": "topic", "value": "/depth" },
    { "@id": "#sensor-sonar0-detected_at_start", "@type": "PropertyValue", "name": "detected_at_start", "value": "true" },
    { "@id": "#python-runtime-executable", "@type": "PropertyValue", "name": "executable", "value": "/opt/ros_ws/.venv/bin/python3" },
    { "@id": "#python-runtime-venv_path", "@type": "PropertyValue", "name": "venv_path", "value": "/opt/ros_ws/.venv" },
    { "@id": "#bag1-measure-1", "@type": "PropertyValue", "name": "/fix", "description": "sensor_msgs/msg/NavSatFix", "value": 24654 },
    { "@id": "#bag1-measure-2", "@type": "PropertyValue", "name": "/depth", "description": "ping_msgs/msg/Ping", "value": 49308 }
  ]
}
```

Note: `sha256` on File entities uses the term from the RO-Crate 1.1 context
(it is defined there); no custom vocabulary is needed for it.

## Generation rules for `ro_crate.py`

- Deterministic output: entities sorted as in the example (descriptor, root,
  people/org/place, robot, sensors, mission, software, bags, files, then all
  hoisted `PropertyValue` entities in creation order); keys in insertion order;
  2-space indent; UTF-8; trailing newline.
- Optional `MissionRecord` fields that are `None`/empty produce **no** property
  (never `null` in the JSON-LD).
- All `PropertyValue`s are hoisted to top-level `@graph` entities with `@id`s and
  referenced from their parents (flattened JSON-LD — see the inventory Rules).
- The writer takes `(record: MissionRecord, crate_root: Path)` and must not do
  I/O other than writing the one file — all hashing and copying belongs to the
  assembler.
- Validation target: the file must pass `rocrate` library loading
  (`ROCrate(path)`) — exercised by
  `tests/integration/test_mission_lifecycle.py::test_crate_loads_with_rocrate_library`
  (skipped when the optional `rocrate` package is absent). Generation is
  hand-rolled to keep the entity layout exactly as specified.
