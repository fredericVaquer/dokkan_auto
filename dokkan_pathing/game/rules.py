"""The movement rules as pure functions: ``(state, input) -> (new_state, events)``.

Nothing here has side effects or randomness. Randomness enters only through
``roll(state, value)``, where the *caller* supplies the value. That is what lets
the same rules serve two very different users:

* the Simulator, which samples a value and animates the events;
* the search, which calls ``roll`` once per possible value to build a chance node.

Fine-grained API (used by the simulator/UI to animate step by step)::

    select_die(state, map, slot)        CHOOSE_DIE       -> MOVING | CHOOSE_DIRECTION | ROLL | DONE
    step(state, map)                    MOVING           -> (same set)
    select_direction(state, map, node)  CHOOSE_DIRECTION -> (same set)
    roll(state, value)                  ROLL             -> CHOOSE_DIE

Macro API (used by search, which only cares about decision points)::

    play_die(state, map, slot)          select_die + all forced steps
    play_direction(state, map, node)    select_direction + all forced steps

After a macro action the phase is never MOVING.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from dokkan_pathing.game.dice import FACES
from dokkan_pathing.game.map import GameMap, Node
from dokkan_pathing.game.state import Dice, GameState, Phase
from dokkan_pathing.game.tiles import TILE_RULES, TileRule, TileType, Trigger


class EventKind(Enum):
    DIE_SELECTED = "die_selected"
    MOVE = "move"
    BRANCH = "branch"
    COLLECT = "collect"
    FIGHT = "fight"
    TELEPORT = "teleport"
    DAMAGE = "damage"
    NEGATIVE = "negative"
    RANDOM = "random"
    MOVEMENT_LOST = "movement_lost"
    STOP = "stop"
    ROLL = "roll"
    BOSS = "boss"


@dataclass(frozen=True)
class Event:
    """Something that happened, for the log and the animation. Not used by the rules."""

    kind: EventKind
    node: str | None = None
    value: int | None = None
    message: str = ""


Transition = tuple[GameState, list[Event]]

_EVENT_FOR_TILE = {
    TileType.FIGHT: EventKind.FIGHT,
    TileType.DAMAGE: EventKind.DAMAGE,
    TileType.NEGATIVE: EventKind.NEGATIVE,
    TileType.RANDOM: EventKind.RANDOM,
}


# --------------------------------------------------------------------------- dice


def initial_state(game_map: GameMap, dice: tuple[int, int, int]) -> GameState:
    if len(dice) != 3 or not all(d in FACES for d in dice):
        raise ValueError(f"need three dice in 1..6, got {dice}")
    return GameState(position=game_map.start, dice=tuple(dice))


def replace_die(dice: Dice, slot: int, value: int | None) -> Dice:
    """Put ``value`` in ``slot`` and leave the other slots exactly where they are."""
    if not 0 <= slot < len(dice):
        raise IndexError(f"slot {slot} out of range")
    return dice[:slot] + (value,) + dice[slot + 1 :]


def available_slots(state: GameState) -> list[int]:
    if state.phase is not Phase.CHOOSE_DIE:
        return []
    return [i for i, d in enumerate(state.dice) if d is not None]


def direction_options(state: GameState, game_map: GameMap) -> tuple[str, ...]:
    if state.phase is not Phase.CHOOSE_DIRECTION:
        return ()
    return game_map.successors(state.position)


# ---------------------------------------------------------------- public transitions


def select_die(state: GameState, game_map: GameMap, slot: int) -> Transition:
    _require(state, Phase.CHOOSE_DIE)
    if not isinstance(slot, int) or not 0 <= slot < len(state.dice):
        raise ValueError(f"invalid dice slot {slot!r}; expected 0, 1 or 2")
    value = state.dice[slot]
    if value is None:
        raise ValueError(f"slot {slot} has no die")
    state = replace(
        state,
        dice=replace_die(state.dice, slot, None),
        metrics=state.metrics.add("rolls"),
        active_slot=slot,
        steps_remaining=value,
    )
    events = [Event(EventKind.DIE_SELECTED, state.position, value, f"Use die {slot + 1}: move {value}")]
    state, more = _continue_movement(state, game_map)
    return state, events + more


def step(state: GameState, game_map: GameMap) -> Transition:
    """Take the single forced step. MOVING guarantees exactly one successor."""
    _require(state, Phase.MOVING)
    (successor,) = game_map.successors(state.position)
    return _enter(state, game_map, successor)


def select_direction(state: GameState, game_map: GameMap, node_id: str) -> Transition:
    _require(state, Phase.CHOOSE_DIRECTION)
    options = game_map.successors(state.position)
    if node_id not in options:
        raise ValueError(f"{node_id!r} is not a direction from {state.position!r}; options: {options}")
    return _enter(state, game_map, node_id)


def roll(state: GameState, value: int) -> Transition:
    """Fill the slot used for this move with ``value``."""
    _require(state, Phase.ROLL)
    if value not in FACES:
        raise ValueError(f"die value must be in 1..6, got {value!r}")
    slot = state.active_slot
    state = replace(state, dice=replace_die(state.dice, slot, value), active_slot=None, phase=Phase.CHOOSE_DIE)
    return state, [Event(EventKind.ROLL, None, value, f"New die in slot {slot + 1}: {value}")]


def advance(state: GameState, game_map: GameMap) -> Transition:
    """Run forced steps until the next decision, chance node, or terminal state."""
    events: list[Event] = []
    while state.phase is Phase.MOVING:
        state, more = step(state, game_map)
        events += more
    return state, events


def play_die(state: GameState, game_map: GameMap, slot: int) -> GameState:
    state, _ = select_die(state, game_map, slot)
    state, _ = advance(state, game_map)
    return state


def play_direction(state: GameState, game_map: GameMap, node_id: str) -> GameState:
    state, _ = select_direction(state, game_map, node_id)
    state, _ = advance(state, game_map)
    return state


# ------------------------------------------------------------------------ internals


def _require(state: GameState, phase: Phase) -> None:
    if state.phase is not phase:
        raise ValueError(f"expected phase {phase.name}, but state is in {state.phase.name}")


def _continue_movement(state: GameState, game_map: GameMap) -> Transition:
    """Decide what comes next once the player stands on ``state.position``."""
    if state.steps_remaining == 0:
        return _land(state, game_map)
    options = game_map.successors(state.position)
    if len(options) > 1:
        msg = f"Branch at {state.position}: choose one of {', '.join(options)}"
        return replace(state, phase=Phase.CHOOSE_DIRECTION), [Event(EventKind.BRANCH, state.position, len(options), msg)]
    return replace(state, phase=Phase.MOVING), []


def _enter(state: GameState, game_map: GameMap, node_id: str) -> Transition:
    """Move onto ``node_id`` (consuming one step) and apply what happens there."""
    node = game_map.node(node_id)
    state = replace(state, position=node_id, steps_remaining=state.steps_remaining - 1)
    events = [Event(EventKind.MOVE, node_id)]

    if node.type is TileType.BOSS:
        return _reach_boss(state, node_id, events)

    rule = TILE_RULES[node.type]
    active = node_id not in state.consumed
    if active and rule.trigger is Trigger.ENTER:
        state, fired = _fire(state, node, rule)
        events += fired

    if active and rule.forced_stop:
        lost = state.steps_remaining
        state = replace(state, steps_remaining=0, phase=Phase.ROLL)
        if node.type is TileType.KINTON:
            state = replace(state, position=node.target)
            events.append(Event(EventKind.TELEPORT, node.target, None, f"Kinton cloud: {node_id} -> {node.target}"))
            if game_map.node(node.target).type is TileType.BOSS:
                return _reach_boss(state, node.target, events)
        if lost:
            events.append(Event(EventKind.MOVEMENT_LOST, state.position, lost, f"Forced stop: {lost} step(s) lost"))
        return state, events

    state, more = _continue_movement(state, game_map)
    return state, events + more


def _land(state: GameState, game_map: GameMap) -> Transition:
    """The move ended normally on ``state.position``."""
    node = game_map.node(state.position)
    rule = TILE_RULES[node.type]
    events = [Event(EventKind.STOP, node.id, None, f"Stopped on {node.id}")]
    if node.id not in state.consumed and rule.trigger is Trigger.LAND:
        state, fired = _fire(state, node, rule)
        events += fired
    return replace(state, phase=Phase.ROLL), events


def _fire(state: GameState, node: Node, rule: TileRule) -> Transition:
    metrics = state.metrics.add(rule.metric, node.amount) if rule.metric else state.metrics
    consumed = state.consumed | {node.id} if rule.consumable else state.consumed
    kind = _EVENT_FOR_TILE.get(node.type, EventKind.COLLECT)
    text = f"{node.type.value.replace('_', ' ')}" + (f" x{node.amount}" if node.amount != 1 else "")
    return replace(state, metrics=metrics, consumed=consumed), [Event(kind, node.id, node.amount, text)]


def _reach_boss(state: GameState, node_id: str, events: list[Event]) -> Transition:
    state = replace(state, position=node_id, steps_remaining=0, phase=Phase.DONE)
    return state, events + [Event(EventKind.BOSS, node_id, None, "Boss reached - stage complete!")]
