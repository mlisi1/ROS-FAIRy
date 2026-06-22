# Real rosbag2 fixtures

The unit tests build bags with `tests/conftest.make_bag` / `make_mcap_bag`,
which **hand-write** `metadata.yaml` and the storage file. That proves the code
is self-consistent, but not that it matches what `ros2 bag record` actually
produces — Jazzy writes metadata **version 9** with QoS / compression /
type-hash fields our synthetic fixtures omit.

Dropping a couple of *real* bags here makes `tests/integration/test_real_bags.py`
exercise the real parse → health → assemble path. The tests **skip cleanly when
this directory has no bags**, so CI stays green until you add them.

## What to add

One directory per bag, each containing rosbag2's `metadata.yaml` and its storage
file(s). Any directory under `tests/fixtures/` that contains a `metadata.yaml`
is auto-discovered. Suggested layout:

```
tests/fixtures/
├── real_sqlite3/
│   ├── metadata.yaml
│   └── real_sqlite3_0.db3
└── real_mcap/
    ├── metadata.yaml
    └── real_mcap_0.mcap
```

## How to record them (on a Jazzy machine)

Keep them **tiny** — a few seconds of one trivial topic, so they're fine to
commit (well under ~100 KB each).

```bash
# Terminal 1: a simple publisher
ros2 run demo_nodes_cpp talker

# Terminal 2: record ~5 seconds, one topic, then Ctrl-C
ros2 bag record -s sqlite3 -o real_sqlite3 /chatter   # sqlite3 backend
ros2 bag record -s mcap    -o real_mcap    /chatter   # mcap backend (Jazzy default)
```

Then move `real_sqlite3/` and `real_mcap/` into this directory and commit them.

Any small real bag works — `/chatter` is just the easiest. The tests assert on
structure (schema keys, sane timestamps, sorted message times, a valid crate),
not on specific topic names, so your own field bags are fine too. Avoid
committing anything with sensitive payloads.
