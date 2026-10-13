"""Tiny map builders so each test can define exactly the board it needs."""

from __future__ import annotations

from dokkan_pathing.game.map import GameMap


def node(node_id: str, type_: str = "normal", next_: tuple[str, ...] | list[str] = (), **extra) -> dict:
    return {"id": node_id, "type": type_, "next": list(next_), **extra}


def build_map(*nodes: dict, start: str = "s", dice: tuple[int, int, int] | None = None) -> GameMap:
    data = {"name": "test", "start": start, "nodes": list(nodes)}
    if dice:
        data["initial_dice"] = list(dice)
    return GameMap.from_dict(data)


def line_map(*types: str) -> GameMap:
    """A straight line n0 -> n1 -> ... where ``types[i]`` is the type of ``n{i}``.

    ``line_map("start", "normal", "fight", "final")`` gives n0(start) -> n1 -> n2(fight) -> n3(final).
    """
    nodes = []
    for i, type_ in enumerate(types):
        nxt = [f"n{i + 1}"] if i + 1 < len(types) else []
        nodes.append(node(f"n{i}", type_, nxt))
    return build_map(*nodes, start="n0")
