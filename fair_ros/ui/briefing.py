"""The mission_start briefing wizard (specs/cli.md).

Exactly five questions, plain language, under two minutes. Also reused by
mission_close to fill in required answers the operator skipped.
"""

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

# (field, prompt text, required) — order and wording fixed by specs/cli.md
QUESTIONS = [
    ("operator_name", "What's your name?", True),
    ("goal", "In one sentence, what is this mission trying to do?", True),
    ("location_name",
     "Where are you? (place name, e.g. 'Marsh Creek, north bank')", True),
    ("environment",
     "What's the environment like? (e.g. outdoor, indoor, marine — press "
     "Enter to skip)", False),
    ("notes", "Anything else worth noting? (press Enter to skip)", False),
]


def _ask_one(console: Console, field: str, prompt: str, required: bool,
             default: str | None) -> str | None:
    while True:
        kwargs = {"default": default} if default else {}
        answer = Prompt.ask(prompt, console=console, **kwargs)
        answer = (answer or "").strip()
        if answer:
            return answer
        if not required:
            return None
        console.print("[yellow]This one I really need — it's what makes the "
                      "mission findable later.[/yellow]")


def ask_briefing(console: Console | None = None,
                 default_operator: str | None = None) -> dict:
    """Run the full five-question briefing; returns field -> answer."""
    console = console or Console()
    console.print(Panel("Quick mission briefing — five questions, "
                        "under two minutes.", title="fair-ros",
                        border_style="cyan"))
    answers = {}
    for field, prompt, required in QUESTIONS:
        default = default_operator if field == "operator_name" else None
        answers[field] = _ask_one(console, field, prompt, required, default)
    return answers


def ask_missing(fields: list[str], console: Console | None = None) -> dict:
    """Ask only the named required questions (gap-fill at mission_close)."""
    console = console or Console()
    by_field = {f: (p, r) for f, p, r in QUESTIONS}
    console.print("A few details are missing before this mission can be "
                  "saved:")
    answers = {}
    for field in fields:
        prompt, required = by_field[field]
        answers[field] = _ask_one(console, field, prompt, required, None)
    return answers
