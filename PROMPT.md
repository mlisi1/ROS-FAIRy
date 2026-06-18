You are implementing `fair-ros`, a ROS 2 tool that makes field robotics mission data FAIR-compliant. Read `CLAUDE.md` fully before doing anything else — it is the project constitution and defines every design decision, file layout, and implementation order.

Your first task is to generate the `specs/` sub-specification files that `CLAUDE.md` references. These files are the detailed technical contracts for each component. Generate all five of them now:

**`specs/data_model.md`**
Define every field in `MissionRecord` with:
- Field name, type, description
- Confidence tag: `auto` or `user`
- Whether it is required or optional
- Where it comes from (which harvest module, or which briefing question)

Include all sub-records: `identity`, `intent`, `robot`, `sensors[]`, `software`, `ros_graph`, `calibrations[]`, `bags[]`, `provenance`.

**`specs/watchdog.md`**
Define the watchdog service behaviour precisely:
- inotify watch targets and events
- State machine: IDLE → RECORDING → FINALISING → IDLE
- What harvest modules are called at each state transition and in what order
- Timeout values (bag inactivity threshold, rclpy timeout, docker timeout)
- Error handling: what happens if ROS 2 is not running, if Docker is absent, if robot_identity.yaml is missing
- The `watchdog.state` file format

**`specs/cli.md`**
Define the exact behaviour of every `ros2 fair` subcommand:
- `setup`: step-by-step wizard flow, every question, validation rules
- `mission_start`: every briefing question (max 5), exact wording, which field each maps to, skip behaviour
- `mission_record`: exact subprocess call, output behaviour, error cases
- `mission_close`: summary panel contents, warning generation logic, save/discard flow
- `mission_status`: what is shown, format
- `list`: table columns, sort order, filter options

**`specs/archive.md`**
Define the archive assembly process:
- Exact directory structure of a completed RO-Crate mission folder
- File copy/link strategy for bags (copy vs symlink, size considerations)
- What gets snapshotted from Docker (compose file path discovery, image digest extraction)
- SQLite schema for the mission index (table, columns, indices)
- What happens on partial failure (bag copy fails halfway, etc.)

**`specs/ro_crate_schema.md`**
Define the complete `ro-crate-metadata.json` JSON-LD structure:
- Context declarations (RO-Crate 1.1, schema.org, SSN/SOSA prefixes)
- Root Data Entity fields
- Every entity type used: Dataset, File, SoftwareApplication, Person, sensor entities
- Mapping from `MissionRecord` fields to JSON-LD properties
- A complete example document for a fictional mission

---

After generating all five spec files, stop and report:
1. Any ambiguities or gaps you found in `CLAUDE.md` that need clarification before implementation
2. Any external library choices you want to confirm (e.g. inotify library, Pydantic version, rich version)
3. Your confidence level on each spec

Do not write any implementation code yet.
