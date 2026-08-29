"""The coach wire format: a line-tagged stream, and the parser that reads it.

The coach used to answer in a single JSON object. That cost us three things:
it could not be streamed (JSON is unreadable until the closing brace), a single
malformed brace threw away the whole paid response, and a quarter of the output
tokens were syntax.

The replacement has one rule: **prose is the default, and a line starting with
`@` is structure.** Nothing to escape, nothing to balance, nothing to close.

    Off the tee is where you're losing it — your driver dispersion is
    nearly double what it is with 3-wood.

    @insight Driver dispersion is 2x your 3-wood

    @drill Gate Drill
    @focus Driver face control
    @step Place two tees just wider than your driver head
    @step Make ten swings without clipping either tee
    @win Ten clean swings before you move on

Because the format is line-oriented, a truncated response still yields every
complete line — a mangled tag costs one drill card, not the whole reply. And an
unrecognised tag falls back to prose, so the worst case is a stray `@thing` in
the message rather than a 502.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, List


# ──────────────────────────────────────────────────────────────────────────────
# The spec we hand the model
# ──────────────────────────────────────────────────────────────────────────────

FORMAT_INSTRUCTIONS = """

Write your answer as normal prose. Structure is marked by lines starting with @:

@insight <one short, specific observation — repeat for each>
@drill <drill name>
@focus <what the drill fixes>
@step <one step — repeat for each step>
@win <what success looks like>

Rules:
- One line per tag. Never wrap a tag across two lines.
- @focus, @step and @win belong to the @drill above them.
- Put each @drill block after the paragraph that motivates it.
- Everything not starting with @ is prose shown directly to the player.
- Only use @ at the start of a line when you mean a tag."""


# ──────────────────────────────────────────────────────────────────────────────
# Events
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class Delta:
    """A run of prose to append to the visible answer."""
    text: str


@dataclass
class Insight:
    """One completed `@insight` line."""
    text: str


@dataclass
class Drill:
    """A drill, emitted again on every field that lands.

    Clients upsert on `index`, which lets a card paint its header the moment
    `@drill` arrives and fill in steps as they stream. `index` doubles as the
    old `priority` — order of appearance is the priority, so the model no
    longer has to number them.
    """
    index: int
    drill_name: str = ""
    focus_area: str = ""
    steps: List[str] = field(default_factory=list)
    expected_outcome: str = ""

    @property
    def priority(self) -> int:
        return self.index + 1

    @property
    def instructions(self) -> str:
        """Steps as one string, for clients that predate the `steps` field."""
        if not self.steps:
            return ""
        if len(self.steps) == 1:
            return self.steps[0]
        return " ".join(f"{i}. {s}" for i, s in enumerate(self.steps, 1))


Event = Delta | Insight | Drill


# ──────────────────────────────────────────────────────────────────────────────
# Parser
# ──────────────────────────────────────────────────────────────────────────────

_DRILL_FIELDS = {"@focus": "focus_area", "@win": "expected_outcome"}


class CoachStreamParser:
    """Incremental parser. Feed it text as it arrives, get events out.

    Prose is released as soon as it arrives — the parser only needs the first
    character of a line to know whether it is prose or a tag, so streaming stays
    token-by-token rather than line-by-line. Tag lines are held until their
    newline, which is why the format forbids wrapping one across two lines.
    """

    _PROSE = "prose"
    _TAG = "tag"

    def __init__(self) -> None:
        self._buf = ""
        self._mode: str | None = None
        self._drills: List[Drill] = []

    def feed(self, chunk: str) -> Iterator[Event]:
        self._buf += chunk.replace("\r\n", "\n")
        while True:
            if self._mode is None:
                if not self._buf:
                    return
                self._mode = self._TAG if self._buf[0] == "@" else self._PROSE

            newline = self._buf.find("\n")

            if self._mode is self._PROSE:
                if newline == -1:
                    # Partial prose line — release it now, stay in prose mode.
                    if self._buf:
                        yield Delta(self._buf)
                        self._buf = ""
                    return
                text, self._buf = self._buf[: newline + 1], self._buf[newline + 1 :]
                self._mode = None
                yield Delta(text)
            else:
                if newline == -1:
                    return  # Hold the tag until we can read the whole line.
                line, self._buf = self._buf[:newline], self._buf[newline + 1 :]
                self._mode = None
                yield from self._parse_tag(line)

    def finish(self) -> Iterator[Event]:
        """Flush whatever the stream ended mid-way through."""
        if not self._buf:
            return
        line, self._buf = self._buf, ""
        if line.startswith("@"):
            yield from self._parse_tag(line)
        else:
            yield Delta(line)

    # ── internals ────────────────────────────────────────────────────────────

    def _parse_tag(self, line: str) -> Iterator[Event]:
        tag, _, value = line.partition(" ")
        tag = tag.lower()
        value = value.strip()

        if tag == "@insight":
            if value:
                yield Insight(value)
            return

        if tag == "@drill":
            drill = Drill(index=len(self._drills), drill_name=value)
            self._drills.append(drill)
            yield drill
            return

        if tag == "@step" and self._drills and value:
            self._drills[-1].steps.append(value)
            yield self._drills[-1]
            return

        if tag in _DRILL_FIELDS and self._drills and value:
            setattr(self._drills[-1], _DRILL_FIELDS[tag], value)
            yield self._drills[-1]
            return

        # Unrecognised tag, or a drill field with no drill open. Don't drop the
        # text — show it. A stray line beats a lost response.
        yield Delta(line + "\n")


# ──────────────────────────────────────────────────────────────────────────────
# Whole-response convenience
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class CoachAnswer:
    answer: str
    key_insights: List[str]
    drills: List[Drill]


def parse(text: str) -> CoachAnswer:
    """Parse a complete response. Same code path as the streaming one."""
    parser = CoachStreamParser()
    return collect(parser.feed(text), parser)


def collect(events: Iterator[Event], parser: "CoachStreamParser | None" = None) -> CoachAnswer:
    """Drain an event stream into a finished answer."""
    prose: List[str] = []
    insights: List[str] = []
    drills: List[Drill] = []

    def absorb(event: Event) -> None:
        if isinstance(event, Delta):
            prose.append(event.text)
        elif isinstance(event, Insight):
            insights.append(event.text)
        elif isinstance(event, Drill) and not any(d is event for d in drills):
            drills.append(event)

    for event in events:
        absorb(event)
    if parser is not None:
        for event in parser.finish():
            absorb(event)

    return CoachAnswer(
        answer="".join(prose).strip(),
        key_insights=insights,
        drills=drills,
    )
