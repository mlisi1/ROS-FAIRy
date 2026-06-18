"""ros2 fair verb implementations.

Each module exposes a plain ``run(args, console) -> int`` (unit-testable
without ROS) plus a thin ros2cli VerbExtension wrapper. The shim below lets
the modules import in environments without ros2cli (CI, unit tests).
"""

try:
    from ros2cli.verb import VerbExtension
except ImportError:  # pragma: no cover - exercised only outside ROS
    class VerbExtension:
        """Stand-in with the same interface as ros2cli's VerbExtension."""

        def add_arguments(self, parser, cli_name):
            pass
