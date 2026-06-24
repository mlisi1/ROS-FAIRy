# Design note: FAIR-ifying bags recorded outside `mission_record`

**Status:** Forks resolved (2026-06-24) — ready to spec; not yet implemented.
**Date:** 2026-06-24

## Decisions (settled 2026-06-24, PR #32)

1. **Detection — `/proc` process-scan as primary.** The watchdog polls `/proc`
   for the rosbag2 recorder process, resolves the output dir from cmdline/cwd,
   and harvests at true record-start. inotify-on-spool stays unchanged for the
   `mission_record` path; `ros2 fair adopt <bagdir>` is the manual escape hatch
   for off-watchdog / historical bags.
2. **Concurrency — one bag, one mission.** Keep today's single-active-bag state
   machine: a second recording (foreign or otherwise) that starts while
   RECORDING is queued and logged, not captured concurrently. Revisit only if
   real multi-recording missions show up.

## Problem

The dashcam promise is "always on when bags are detected", but detection is
currently **scoped to the spool**:

- `ros2 fair mission_record` is a wrapper that records *into*
  `/var/fair-ros/spool/bags/...` and writes `<spool>/session.env` (the
  operator's DDS settings) so the watchdog harvests on the right partition.
- The watchdog's inotify only watches `/var/fair-ros/spool/bags/`.

So the automatic context capture only happens **if the operator uses
`mission_record`**. If someone opens another terminal and runs plain
`ros2 bag record -o ~/run42 /scan`, the bag lands in their cwd, invisible to the
watchdog — no harvest, no context, not FAIR. We want to close this case so *any*
recording, started any way, gets FAIR-ified.

## Decision axes

### 1. Detection mechanism

| Mechanism | Catches | Cost / caveat |
|---|---|---|
| **Process scan (`/proc`)** — poll for a rosbag2 recorder process | CLI *and* launch-file recordings, anywhere | needs periodic scan; parse cmdline/cwd to find output dir |
| **ROS-graph node** — recorder appears as a node subscribing to topics | any recording, *if* ROS reachable | reveals that a recording exists but **not where the file is**; DDS-partition-sensitive |
| **fanotify (mount-wide)** — root watches whole FS for `*.mcap`/`*.db3` | any bag file appearing | heavy, noisy, can't tell a recording from a file copy |
| **Explicit `ros2 fair adopt <bagdir>`** | historical / off-watchdog bags | manual, not dashcam |

**DECIDED: `/proc` process-scan as primary.** Robot- and version-agnostic (just
`/proc`, even lighter than principle #5's subprocess rule), catches recordings
started any way, and lets harvest fire at **true record-start** instead of after
the fact. `/proc/<pid>/cmdline` + `/proc/<pid>/cwd` resolve the real output dir.
The ROS-graph signal is a useful corroborator but useless for locating the file.
Keep the existing inotify-on-spool unchanged for the `mission_record` path.
`adopt` stays as the manual escape hatch for bags recorded while the watchdog
was down / on another machine / historical.

### 2. Context problem (no briefing happened)

Already half-solved: the spec lets `mission_record` skip briefing and ask the 3
REQUIRED fields (operator, goal, location) at `mission_close`. A detected
foreign recording can therefore be **fully automatic at record time**, with
operator input deferred to close. Zero friction, on-model.

### 3. Where the foreign bag lives (it's in the operator's cwd, not spool)

- *Copy into spool at detection* — single source of truth, but doubles disk
  during long recordings and fights a workflow that chose another location.
- *Reference in place, ingest at close* — lighter, respects the operator, but
  the file can be moved/deleted before close.

**Lean: reference-in-place, ingest at `mission_close`** (assembler already moves
spool bags; ingesting a foreign path is a small conceptual extension). Guard the
move/delete-before-close case with a loud warning + existing `verify`.

### 4. Harvest timing → quality

Detect-at-start (process scan) → clean live harvest. Detect-late (filesystem,
after `metadata.yaml`) → ROS may be down, graph stale — but `quality.py` already
grades that `degraded`/`poor`, so even a late catch yields a **findable
degraded** record instead of nothing. Strictly better than the status quo.

## Key insight: `/proc/<pid>/environ` replaces `session.env` for foreign bags

`session.env` exists to fix DDS-partition drift when harvesting a
`mission_record` session. A foreign recorder won't write `session.env` — but we
can read **`/proc/<pid>/environ`** of the recorder process and adopt *its*
`ROS_DOMAIN_ID` / `RMW_IMPLEMENTATION` directly. This solves the
harvest-partition problem more directly than `session.env`, under the same
security rule already in the spec: **adopt discovery keys only, never loader
paths** (`PATH` / `LD_LIBRARY_PATH` / `PYTHONPATH` / overlay). Detection and
partition-correct harvest fall out of the same `/proc` read.

## Edge cases to resolve

- **Concurrency — DECIDED: one bag, one mission.** Keep the single-active-bag
  state machine; a second recording (foreign or otherwise) starting while
  RECORDING is queued and logged, not captured concurrently. Foreign detection
  must therefore respect the same queue, not bypass it. Revisit only if real
  multi-recording missions appear.
- **Recorder vs. file copy** — process detection sidesteps this; fanotify does
  not.
- **Removable / network mount** as the recording target.
- **Watchdog down during the recording** → the `adopt` escape hatch covers it.
- **Identifying the recorder process reliably** — match the rosbag2 recorder
  executable / `ros2 bag record` cmdline; avoid false positives from `play`,
  `info`, `convert`.

## Forks (settled 2026-06-24 — see Decisions at top)

1. **Detection:** ✅ `/proc` process-scan as primary, + inotify-on-spool, +
   manual `adopt`.
2. **Concurrency:** ✅ one-bag-one-mission (queue a second recording, as today).

## Rough implementation sketch

1. Watchdog gains a **recorder-process poller** (e.g. every N s) alongside the
   inotify loop: scan `/proc` for rosbag2 recorder processes, resolve output dir
   from cmdline/cwd, dedupe against bags already tracked (incl. spool ones from
   `mission_record`).
2. On a *new* foreign recorder: read `/proc/<pid>/environ`, adopt discovery keys
   (reuse `ros_env.SESSION_ADOPT_KEYS`), then run the existing harvest pipeline;
   dynamically arm an inotify W2 on the resolved output dir so the existing
   RECORDING→FINALISING machinery applies unchanged.
3. Finalise when the recorder process exits **and** `metadata.yaml` appears
   (or inactivity fallback), same as today.
4. Record the bag's real (foreign) path in `harvest.json.bags[]`; mark
   `source = "foreign"` vs `"mission_record"` for provenance.
5. `mission_close`: if foreign bags are present and no briefing exists, ask the 3
   REQUIRED questions; assembler ingests the foreign path (copy into the crate),
   warns if it has moved/vanished.
6. New `ros2 fair adopt <bagdir>` verb: manual ingest for off-watchdog /
   historical bags (mirrors `repair`'s "accepts a single bag dir" precedent).
7. Spec updates: `specs/watchdog.md` (poller, environ adoption, concurrency
   decision), `specs/cli.md` (`adopt`, mission_close foreign-bag flow),
   `specs/data_model.md` (`bags[].source`).

## Touch points in the current code (reference)

- `fair_ros/watchdog/watchdog.py` — inotify loop + state machine (add poller).
- `fair_ros/utils/ros_env.py` — `SESSION_ADOPT_KEYS`, env adoption logic.
- `fair_ros/manifest/builder.py` — `load_spool`, `build`, `HARVEST_MODULES`.
- `fair_ros/archive/assembler.py` — bag ingest into the crate.
- `fair_ros/subcommands/mission_close.py` — late briefing + foreign-bag prompt.
- `specs/watchdog.md`, `specs/cli.md`, `specs/data_model.md`.
