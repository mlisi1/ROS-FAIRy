# Spec: Data Model

Authoritative definition of every field in a `MissionRecord`. The Pydantic models in
`fair_ros/manifest/schema.py` must match this document exactly.

## Conventions

- **Confidence**: `auto` (harvested silently) or `user` (typed by the operator).
  There is no third tier. Serialized records expose confidence via
  `provenance.field_confidence` (see below), keeping the data fields themselves clean.
- **Required**: a record cannot be archived without this field. Validation failures
  produce plain-language errors naming the missing information, never a traceback.
- **Timestamps**: ISO 8601 with explicit UTC offset (`2026-06-12T14:03:00+00:00`).
- **Source** column names the harvest module function or briefing question that
  produces the field.
- All models are Pydantic v2, `model_config = ConfigDict(extra="forbid")`.
- `schema_version` for this document: `"1.0"`.

## Top-level structure

```
MissionRecord
├── schema_version: str          # literal "1.0"
├── identity:      Identity
├── intent:        Intent
├── robot:         Robot
├── sensors:       list[Sensor]
├── software:      Software
├── ros_graph:     RosGraph
├── calibrations:  list[Calibration]
├── bags:          list[Bag]
└── provenance:    Provenance
```

---

## `identity`

| Field | Type | Req | Conf | Source | Description |
|---|---|---|---|---|---|
| `mission_id` | `str` | yes | auto | `manifest/builder.py` | `m-YYYYMMDD-HHMMSS-xxxx` where `xxxx` is 4 lowercase hex chars from `uuid4`. Generated when `mission_context.json` is first written (at `mission_start`), or at `mission_close` if the operator skipped the briefing. |
| `created_at` | `datetime` | yes | auto | builder | Time the mission context was created (UTC). |
| `operator_name` | `str` | **yes** | user | Briefing Q1 | Free text, 1–80 chars, stripped. |
| `operator_contact` | `str \| None` | no | user | Setup-time default | Defaults to `robot_identity.yaml → owner.contact_email`; the operator is never asked for it. |

## `intent`

| Field | Type | Req | Conf | Source | Description |
|---|---|---|---|---|---|
| `goal` | `str` | **yes** | user | Briefing Q2 | One-sentence mission goal, 1–280 chars. |
| `location_name` | `str` | **yes** | user | Briefing Q3 | Human place name ("Marsh Creek, north bank"). Also used (sanitised) in the archive directory name. |
| `environment` | `str \| None` | no | user | Briefing Q4 | Free text or one of the suggested choices (`outdoor`, `indoor`, `underground`, `marine`, `aerial`). Skippable. |
| `notes` | `str \| None` | no | user | Briefing Q5 | Anything else. Skippable. |

## `robot`

All fields come from `harvest/robot_identity.py`, which is a thin validated reader of
`/etc/fair-ros/robot_identity.yaml` (written once by `ros2 fair setup`).

| Field | Type | Req | Conf | Source | Description |
|---|---|---|---|---|---|
| `name` | `str` | yes | auto | identity yaml `robot.name` | Friendly robot name ("Heron-02"). |
| `platform` | `str` | yes | auto | yaml `robot.platform` | Make + model ("Clearpath Heron USV"). |
| `serial_number` | `str` | yes | auto | yaml `robot.serial_number` | Manufacturer serial or asset tag. |
| `owner_organization` | `str` | yes | auto | yaml `owner.organization` | Owning institution. |
| `owner_contact` | `str` | yes | auto | yaml `owner.contact_email` | Steward email; validated at setup time. |

## `sensors[]`

Static description from `robot_identity.yaml → sensors[]`, enriched at harvest time
with a liveness check (topic present in `ros2 topic list` output).

| Field | Type | Req | Conf | Source | Description |
|---|---|---|---|---|---|
| `sensor_id` | `str` | yes | auto | yaml | Stable slug unique within the robot ("gps0", "lidar_front"). |
| `type` | `str` | yes | auto | yaml | Plain category: `gps`, `lidar`, `camera`, `imu`, `sonar`, `other`. Maps to SSN/SOSA in the crate (see `ro_crate_schema.md`). |
| `make_model` | `str` | yes | auto | yaml | "u-blox ZED-F9P". |
| `topic` | `str` | yes | auto | yaml | Primary ROS topic the sensor publishes. |
| `frame_id` | `str \| None` | no | auto | yaml | TF frame, if known. |
| `calibration_ref` | `str \| None` | no | auto | yaml | `Calibration.name` this sensor uses, if any. Must match an entry in `calibrations[]`. |
| `detected_at_start` | `bool` | yes | auto | `harvest/ros_graph.py` | True if `topic` appeared in the topic list during harvest. False is not an error; it becomes a plain-language warning at `mission_close`. |

## `software`

| Field | Type | Req | Conf | Source | Description |
|---|---|---|---|---|---|
| `ros_distro` | `str \| None` | no | auto | `harvest/system_info.py` (`$ROS_DISTRO`) | e.g. `"jazzy"`. `None` if ROS env not sourced when harvested. |
| `ros_packages` | `list[str]` | yes | auto | `harvest/ros_graph.py` (`ros2 pkg list`) | Sorted package names visible on the path. Empty list if ROS unavailable. |
| `apt_ros_versions` | `dict[str, str]` | yes | auto | system_info (`dpkg-query -W ros-*`) | Debian package → version for installed `ros-<distro>-*` packages. Empty dict on non-Debian systems. |
| `docker_containers` | `list[DockerContainer]` | yes | auto | `harvest/docker_info.py` | Empty list when Docker is absent or has no running containers. |
| `fair_ros_version` | `str` | yes | auto | `fair_ros.__version__` | Version of this tool at harvest time. |

### `DockerContainer`

| Field | Type | Description |
|---|---|---|
| `name` | `str` | Container name. |
| `image` | `str` | Image reference as run (`org/img:tag`). |
| `digest` | `str \| None` | First `RepoDigests` entry; `None` for locally built, never-pushed images. |
| `compose_project` | `str \| None` | From label `com.docker.compose.project`. |
| `compose_file` | `str \| None` | From label `com.docker.compose.project.config_files`; the file is snapshotted into the archive (see `specs/archive.md`). |

## `ros_graph`

Snapshot taken when the watchdog enters RECORDING (see `specs/watchdog.md`).

| Field | Type | Req | Conf | Source | Description |
|---|---|---|---|---|---|
| `captured_at` | `datetime \| None` | no | auto | `harvest/ros_graph.py` | `None` if ROS was never reachable. |
| `nodes` | `list[str]` | yes | auto | `ros2 node list` | Fully-qualified node names. Empty if unreachable. |
| `topics` | `list[TopicInfo]` | yes | auto | `ros2 topic list -t` | `TopicInfo = {name: str, type: str}`. |
| `parameters` | `dict[str, dict]` | yes | auto | `ros2 param dump <node>` per node | Node name → parameter tree. Nodes that fail to dump are simply absent. |
| `robot_description` | `str \| None` | no | auto | `harvest/ros_descriptions.py` | URDF XML string, `None` on 5 s timeout. Stored as a separate file in the archive; the manifest holds only its relative path after assembly. |
| `tf_static` | `list[dict] \| None` | no | auto | ros_descriptions | Serialized static transforms, `None` on timeout. |
| `complete` | `bool` | yes | auto | watchdog | False if any subprocess call failed; triggers a warning at close. |

## `calibrations[]`

| Field | Type | Req | Conf | Source | Description |
|---|---|---|---|---|---|
| `name` | `str` | yes | auto | yaml `calibrations[].name` | Unique slug ("camera_front_intrinsics"). |
| `source_path` | `str` | yes | auto | yaml | Absolute path on the robot at harvest time. |
| `archived_path` | `str \| None` | no | auto | `archive/assembler.py` | Relative path inside the crate after copy (`calibrations/<file>`); `None` before archiving or if the source file was missing. |
| `sha256` | `str \| None` | no | auto | assembler | Hash of the copied file. |
| `format` | `str \| None` | no | auto | yaml | e.g. `yaml`, `json`, `kalibr`. |

A `source_path` that no longer exists at archive time is a warning, not a failure.

## `bags[]`

One entry per rosbag2 recording directory found in the spool. Produced in the
watchdog FINALISING step from rosbag2's own `metadata.yaml` plus
`utils/topic_health.py`.

| Field | Type | Req | Conf | Source | Description |
|---|---|---|---|---|---|
| `path` | `str` | yes | auto | watchdog | Relative path inside the crate after assembly (`bags/<dir>`); spool-absolute before. |
| `storage_format` | `str` | yes | auto | bag `metadata.yaml` | `sqlite3` or `mcap`. |
| `size_bytes` | `int` | yes | auto | filesystem | Total directory size. |
| `start_time` | `datetime` | yes | auto | bag metadata | First message time. |
| `end_time` | `datetime` | yes | auto | bag metadata | Last message time. |
| `duration_s` | `float` | yes | auto | bag metadata | |
| `message_count` | `int` | yes | auto | bag metadata | |
| `topics` | `list[BagTopic]` | yes | auto | bag metadata | `BagTopic = {name, type, message_count, avg_frequency_hz}`. |
| `health_warnings` | `list[HealthWarning]` | yes | auto | `utils/topic_health.py` | Empty list = healthy. |

### `HealthWarning`

| Field | Type | Description |
|---|---|---|
| `topic` | `str` | Affected topic. |
| `sensor_id` | `str \| None` | Back-reference to `sensors[]` when the topic matches a declared sensor. |
| `kind` | `str` | `gap` (silence > 1 s mid-recording), `never_published` (declared sensor topic absent from bag), `low_rate` (avg rate < 25 % of other periods). |
| `start_offset_s` | `float \| None` | Seconds from bag start where the problem began. |
| `duration_s` | `float \| None` | Length of the gap. |
| `plain_text` | `str` | Pre-rendered sentence shown to the user: "GPS signal was lost for 4 minutes, starting 12 minutes in." UI layers must show this string, never the raw numbers. |

## `provenance`

| Field | Type | Req | Conf | Source | Description |
|---|---|---|---|---|---|
| `fair_ros_version` | `str` | yes | auto | package | Duplicated from `software` deliberately: survives even if `software` harvest failed. |
| `schema_version` | `str` | yes | auto | builder | `"1.0"`. |
| `harvested_at` | `datetime \| None` | no | auto | watchdog | When `harvest.json` was finalised. |
| `assembled_at` | `datetime \| None` | no | auto | assembler | When the crate was written. |
| `hostname` | `str` | yes | auto | system_info | |
| `kernel` | `str` | yes | auto | system_info (`uname -sr`) | |
| `arch` | `str` | yes | auto | system_info (`uname -m`) | |
| `field_confidence` | `dict[str, str]` | yes | auto | builder | Flat map of dotted field path → `"auto"` \| `"user"`, e.g. `"intent.goal": "user"`. Covers every populated leaf field. This is the single machine-readable source of confidence tags. |
| `harvest_status` | `dict[str, str]` | yes | auto | watchdog | Per harvest module: `ok`, `failed`, `skipped`, `timeout`. Module keys: `robot_identity`, `system_info`, `ros_graph`, `ros_descriptions`, `docker_info`. |

---

## Intermediate files (spool)

Two JSON files in `/var/fair-ros/spool/` feed `manifest/builder.py`:

- **`harvest.json`** — written by the watchdog. Contains `robot`, `sensors`,
  `software`, `ros_graph`, `bags` (added at FINALISING), and the `provenance`
  harvest fields. All `auto`.
- **`mission_context.json`** — written by `mission_start`. Contains `identity`
  (id, created_at, operator) and `intent`. All `user` except the generated id.

`builder.py` merges the two, fills `field_confidence`, and returns a `MissionRecord`.
`validator.py` then checks the three required user fields (`operator_name`, `goal`,
`location_name`) and the presence of at least one bag. Anything else missing is a
warning, never a validation failure — the dashcam must not lose data over missing
nice-to-haves.
