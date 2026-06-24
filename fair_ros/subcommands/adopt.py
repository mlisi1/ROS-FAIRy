"""ros2 fair adopt — pull a recording the watchdog never saw into the mission.

The dashcam captures recordings automatically: those made via
``ros2 fair mission_record`` (into the spool) and those started in another
terminal (found by the watchdog's ``/proc`` recorder-process poller). ``adopt``
is the manual escape hatch for what slips through — a bag recorded while the
watchdog was down, copied from another machine, or otherwise out of reach.

It runs the same processing the watchdog's FINALISING step would (parse
``metadata.yaml``, topic-health analysis) and appends a ``source="adopted"`` bag
entry to ``harvest.json``, referenced in place and copied into the crate at
``mission_close``. See ``specs/cli.md`` and ``specs/watchdog.md``.

NOTE: behaviour is specified but **not yet implemented** — this module reserves
the ``fair.verb`` entry point so registration stays valid and ``ros2 fair adopt``
fails cleanly with a clear message rather than a plugin-load error.
"""

from rich.console import Console

from fair_ros.subcommands import VerbExtension, _configure_logging


def run(args, console: Console | None = None) -> int:
    _configure_logging(getattr(args, "debug", False))
    console = console or Console()
    console.print(
        "[yellow]`ros2 fair adopt` isn't available yet.[/yellow] The behaviour "
        "is specified in specs/cli.md and will land in a future release.")
    return 1


class AdoptVerb(VerbExtension):
    """Ingest a bag recorded outside mission_record (reserved; not yet built)."""

    def add_arguments(self, parser, cli_name):
        parser.add_argument(
            "bagdir",
            help="path to a rosbag2 recording directory (metadata.yaml + "
                 "storage file) to adopt into the current mission")
        parser.add_argument(
            "--json", action="store_true",
            help="machine-readable output for scripts")
        parser.add_argument(
            "--debug", action="store_true",
            help="verbose logging to stderr (for engineers)")

    def main(self, *, args):
        return run(args)
