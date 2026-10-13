"""Finite-horizon expectimax over the pathing game.  <-- YOUR MAIN EXERCISE

The search tree
---------------
Each state's ``phase`` already tells you which kind of tree node it is:

    phase               node type     value
    ------------------  ------------  ------------------------------------------------
    DONE                terminal      evaluate(state)
    CHOOSE_DIE          MAX           max over slots     of V(play_die(state, slot))
    CHOOSE_DIRECTION    MAX           max over options   of V(play_direction(state, node))
    ROLL                CHANCE        sum over faces f   of P(f) * V(roll(state, f))
    MOVING              (never seen)  play_die / play_direction always advance past it

One "turn" looks like:

    CHOOSE_DIE ──play_die──► [CHOOSE_DIRECTION ──play_direction──► ...] ──► ROLL ──roll(f)──► CHOOSE_DIE
     (max)                     (max, zero or more times)                 (chance)

Depth
-----
``depth`` = how many more *dice turns* to look ahead. Spend one unit of depth per
turn (the natural place: when a ROLL node creates the next CHOOSE_DIE state).
Direction choices happen *inside* a turn, so they must NOT consume depth.
When depth reaches 0 at a non-terminal state, stop and return evaluate(state).

Building blocks (all pure, all in game/rules.py)
------------------------------------------------
    available_slots(state)                -> [0, 1, 2] (slots holding a die)
    direction_options(state, map)         -> ("c", "g", ...)
    play_die(state, map, slot)            -> next GameState (never MOVING)
    play_direction(state, map, node_id)   -> next GameState (never MOVING)
    roll(state, face)                     -> (next GameState, events); take [0]
    ctx.distribution.outcomes()           -> ((1, p1), (2, p2), ...)

Exercises (see docs/LEARNING_PATH.md for the full progression)
--------------------------------------------------------------
    2. expectimax_value  — the recursion.
    3. score_dice        — turn values into a decision (then wire up SmartAgent).
    4. score_directions  — the same for branches.
    5. cache_key + memoization in expectimax_value.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from dokkan_pathing.game import rules
from dokkan_pathing.game.dice import DiceDistribution
from dokkan_pathing.game.map import GameMap
from dokkan_pathing.game.objective import Objective
from dokkan_pathing.game.state import GameState, Phase
from dokkan_pathing.search.evaluation import evaluate



@dataclass
class SearchContext:
    """Everything the search needs besides the state, bundled to keep signatures short."""

    game_map: GameMap
    objective: Objective
    distribution: DiceDistribution
    cache: dict = field(default_factory=dict)  # for Exercise 5 (memoization)
    nodes_visited: int = 0  # increment once per expectimax_value call; shown in the UI
    cache_hits: int = 0  # increment when the cache answers a call (Exercise 5)


@dataclass(frozen=True)
class ScoredAction:
    action: int | str  # dice slot index, or node id for a direction
    value: float  # expected score of taking this action


def expectimax_value(state: GameState, depth: int, ctx: SearchContext) -> float:
    """Expected score of ``state`` when playing optimally for ``depth`` more dice turns.

    Dispatch on ``state.phase`` following the table at the top of this file.
    It is recursive: MAX nodes call it on their children, CHANCE nodes call it
    on each roll outcome.
    """
    # TODO(Exercise 2): implement the recursion.
    #   Start with:   ctx.nodes_visited += 1
    #   Then handle, in this order: terminal state, depth cutoff, ROLL (chance),
    #   CHOOSE_DIRECTION (max, same depth), CHOOSE_DIE (max).
    #   Hint: score_dice / score_directions (Ex. 3/4) can be reused for the MAX nodes,
    #   or you can write the max() inline first and refactor later.
    ctx.nodes_visited += 1
    if state.is_terminal:
        return evaluate(state, ctx)
    if depth == 0:
        return evaluate(state, ctx)
    if state.phase is Phase.ROLL:
        return sum(prob * expectimax_value(rules.roll(state, outcome)[0], depth-1, ctx)
                   for outcome, prob in ctx.distribution.outcomes())
    if state.phase is Phase.CHOOSE_DIRECTION:
        return max(score_directions(state, depth, ctx), key=lambda a: a.value).value
    if state.phase is Phase.CHOOSE_DIE:
        return max(score_dice(state, depth, ctx), key=lambda a: a.value).value


def score_dice(state: GameState, depth: int, ctx: SearchContext) -> list[ScoredAction]:
    """One ``ScoredAction`` per available slot, in slot order. State is in CHOOSE_DIE."""
    # TODO(Exercise 3): for each slot, value = expectimax_value(play_die(...), depth, ctx).
    #   Question to answer before coding: should this call use depth or depth - 1,
    #   given where you decided to decrement depth in Exercise 2?
    raise NotImplementedError("TODO: implement score_dice() in search/expectimax.py (Exercise 3)")


def score_directions(state: GameState, depth: int, ctx: SearchContext) -> list[ScoredAction]:
    """One ``ScoredAction`` per branch option, in map order. State is in CHOOSE_DIRECTION."""
    # TODO(Exercise 4): like score_dice, but over direction_options and play_direction.
    raise NotImplementedError("TODO: implement score_directions() in search/expectimax.py (Exercise 4)")


def cache_key(state: GameState, depth: int) -> object:
    """Hashable key identifying a (state, depth) pair for the memo table."""
    # TODO(Exercise 5): the simplest correct key is (state, depth): GameState is frozen
    #   and therefore hashable. Then think about this: state.metrics is part of the
    #   state, so two different paths reaching the same tile with the same dice but a
    #   different history never share a cache entry. Could expectimax_value return the
    #   value of the *future only* (relative to state.metrics) so that metrics can be
    #   left out of the key? What would have to change in evaluate()?
    raise NotImplementedError("TODO: implement cache_key() in search/expectimax.py (Exercise 5)")
