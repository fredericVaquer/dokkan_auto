"""Generate ``maps/huge.json``: a long stage with wide, nested branches and two bosses.

Writing a 150-tile map by hand means computing every ``pos`` so branches don't
overlap. Here the stage is described as a sequence of tiles and splits instead,
and ``place`` works out the coordinates and the ``next`` links.

    python3 -m dokkan_pathing.tools.gen_huge_map            # rewrite maps/huge.json
    python3 -m dokkan_pathing.tools.gen_huge_map out.json   # write somewhere else

Edit ``MAIN`` below to change the stage, then run it again.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from dokkan_pathing.game.map import MAPS_DIR, GameMap


@dataclass
class T:
    """One tile. ``kw`` holds extra JSON fields (``stop``, ``amount``, ``target``, ``label``)."""

    type: str = "normal"
    id: str | None = None  # auto-generated (t1, t2, ...) unless something must refer to it
    kw: dict = field(default_factory=dict)


@dataclass
class Split:
    """The previous tile branches into ``branches``; they all rejoin at the next tile.

    ``ys`` are the vertical offsets of the branches. The order of ``branches`` is the
    order of the options in the game (Max always takes the first).
    """

    branches: list
    ys: list


def t(type_="normal", id=None, **kw):
    return T(type_, id, kw)


def n(k=1):
    return [t() for _ in range(k)]


def width(seq):
    """Horizontal room ``seq`` needs: one unit per tile, the longest branch for a split."""
    return sum(1 if isinstance(e, T) else max(width(b) for b in e.branches) for e in seq)


def place(seq, x0, span, y, prev, nodes, counter):
    """Lay ``seq`` out over [x0, x0+span) at height ``y`` and link the ``prev`` ids to its first tile.

    Shorter branches are stretched to the same span so all branches of a split rejoin
    at the same x. Returns the ids the following tile must be linked from.
    """
    scale = span / width(seq)
    x = x0
    for e in seq:
        if isinstance(e, T):
            counter[0] += 1
            nid = e.id or f"t{counter[0]}"
            node = {"id": nid, "type": e.type, "pos": [round(x, 2), y], "next": []}
            for key, value in e.kw.items():
                node[key] = value
            nodes[nid] = node
            for p in prev:
                nodes[p]["next"].append(nid)
            prev = [] if e.type in ("kinton", "final") else [nid]
            x += scale
        else:
            w = max(width(b) for b in e.branches) * scale
            exits = []
            for branch, dy in zip(e.branches, e.ys):
                exits += place(branch, x, w, y + dy, prev, nodes, counter)
            prev = exits
            x += w
    return prev


def S():
    """Stopping enemy: reaching it ends the move."""
    return t("fight", stop=True)


def F():
    """Plain enemy: only fights you if you land on it."""
    return t("fight")


MAIN = [
    t("start", id="s"), *n(2), t("zeni"), *n(1),
    # A: three long routes
    Split([
        [*n(1), t("zeni"), *n(1), t("ki"), F(), *n(2), t("exclusive"), *n(1), S(), *n(1), t("support_item"), *n(2)],
        [*n(1), t("damage"), *n(2), t("damage", amount=2), *n(1), t("training_item"), *n(1)],
        [*n(1), t("random"), *n(1), F(), *n(2), t("baba"), *n(1), t("zeni", amount=2), *n(1)],
    ], [-6, 0, 6]),
    *n(2), t("ki"), *n(1),
    # B: a route with a nested split, and a Kinton shortcut route
    Split([
        [*n(1), t("zeni"), *n(1),
         Split([[*n(1), t("exclusive"), *n(2), S(), *n(1)], [*n(1), t("damage"), *n(2)]], [-2, 2]),
         *n(1), t("ki"), *n(1)],
        [*n(1), t("support_item"), *n(2), t("kinton", target="pre_mid")],
    ], [-4, 4]),
    *n(2), t("damage"), t(id="pre_mid"), t("boss", id="mid_boss", label="Mid boss"), *n(2),
    # C: three very long routes
    Split([
        [*n(1), t("exclusive"), *n(2), S(), *n(1), t("zeni", amount=2), *n(2), t("training_item"), *n(1),
         t("exclusive"), *n(1), S(), *n(2), t("support_item"), *n(2), t("ki"), *n(1)],
        [*n(1), F(), *n(1), t("damage"), *n(2), F(), *n(1), t("zeni"), *n(2), F(), *n(1), t("damage"), *n(1)],
        [*n(1), t("random"), *n(1),
         Split([[*n(1), t("damage"), *n(1), t("baba"), *n(2)],
                [*n(1), t("training_item"), *n(1), F(), *n(1), t("support_item"), *n(2)]], [-2, 2]),
         *n(1), t("random"), *n(2)],
    ], [-7, 0, 7]),
    *n(2), t("zeni"), *n(1),
    # D: short last choice
    Split([[*n(1), S(), *n(2)], [*n(2), t("damage"), *n(3)]], [-2, 2]),
    *n(2), t("boss", id="boss", label="Final boss"), t("final", id="end"),
]

DATA = {
    "name": "Huge Stage",
    "description": ("A long stage, much wider than the window: drag the board, use the mouse wheel "
                    "(Shift for sideways) or the arrow keys to look around; press C to recentre on the "
                    "token. Four branch zones with long and nested routes, plain fights you can walk "
                    "past and stopping fights (dashed red ring), a Kinton shortcut, a mid boss and a "
                    "final boss before the final tile."),
    "start": "s",
    "initial_dice": [3, 5, 2],
}


def build() -> dict:
    nodes: dict[str, dict] = {}
    place(MAIN, 0, width(MAIN), 0, [], nodes, [0])
    for node in nodes.values():
        if not node["next"]:
            del node["next"]
    return {**DATA, "nodes": list(nodes.values())}


def to_json(data: dict) -> str:
    """Pretty-print with one node per line, like the hand-written maps."""
    header = {k: v for k, v in data.items() if k != "nodes"}
    lines = [json.dumps(n, separators=(", ", ": ")) for n in data["nodes"]]
    return json.dumps(header, indent=2)[:-2] + ',\n  "nodes": [\n    ' + ",\n    ".join(lines) + "\n  ]\n}\n"


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else MAPS_DIR / "huge.json"
    data = build()
    GameMap.from_dict(data)  # raises MapError if the stage is inconsistent
    out.write_text(to_json(data), encoding="utf-8")
    print(f"wrote {out}: {len(data['nodes'])} tiles, {width(MAIN)} columns")


if __name__ == "__main__":
    main()
