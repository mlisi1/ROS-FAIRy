# fair-ros

Make robotics field mission data **FAIR** (Findable, Accessible,
Interoperable, Reusable) with zero friction for the operator.

fair-ros works like a dashcam: a background watchdog notices when a rosbag
recording starts, silently captures the context around it (robot identity,
ROS graph, software versions, container digests, sensor health), and at the
end of the mission asks the operator one question: *save or discard?*

Saved missions become self-contained [RO-Crate](https://w3id.org/ro/crate)
archives — rosbags plus machine-readable JSON-LD metadata aligned to
schema.org and W3C SSN/SOSA — indexed locally in SQLite. No cloud, no
network, everything on the robot.

## Commands

```
ros2 fair setup            # one-time robot setup (engineer, needs sudo)
ros2 fair mission_start    # 5-question briefing, under 2 minutes
ros2 fair mission_record   # record (wraps ros2 bag record)
ros2 fair mission_close    # review summary, then save or discard
ros2 fair mission_status   # what is the assistant doing right now?
ros2 fair list             # table of saved missions
```

## Documentation

- `CLAUDE.md` — project constitution: design principles, layout, rules
- `specs/` — authoritative sub-specifications per component

## Development

```
python3 -m pytest tests/        # no robot or live ROS graph required
```

Requires Python ≥ 3.10, pydantic ≥ 2.5, rich ≥ 13, PyYAML, inotify_simple.
