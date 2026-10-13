"""The search-based agent.  <-- YOUR EXERCISE (after expectimax_value works)

The agent is thin on purpose: all the thinking lives in ``search/``. The agent's
job is to (1) build a SearchContext, (2) ask the search to score every option,
(3) pick the best one, and (4) record a DecisionInfo so the UI can show the
scores next to each option.
"""

from __future__ import annotations

from dokkan_pathing.agents.base_agent import Agent
from dokkan_pathing.game.dice import DiceDistribution
from dokkan_pathing.game.map import GameMap
from dokkan_pathing.game.objective import Objective
from dokkan_pathing.game.state import GameState
from dokkan_pathing.search.expectimax import SearchContext


class SmartAgent(Agent):
    name = "Auto — Smart"

    def __init__(self, objective: Objective, distribution: DiceDistribution, depth: int = 4) -> None:
        super().__init__()
        self.objective = objective
        self.distribution = distribution
        self.depth = depth

    def make_context(self, game_map: GameMap) -> SearchContext:
        return SearchContext(game_map, self.objective, self.distribution)

    def choose_die(self, state: GameState, game_map: GameMap) -> int:
        # TODO(Exercise 3): pick the slot with the highest expected score.
        #   ctx = self.make_context(game_map)
        #   scored = score_dice(state, self.depth, ctx)       # from search.expectimax
        #   best = max(scored, key=lambda s: s.value)
        #   Then fill self.last_decision so the UI shows the reasoning:
        #     DecisionInfo(kind="die",
        #                  options=[OptionScore(f"Die {s.action + 1} ({state.dice[s.action]})", s.value)
        #                           for s in scored],
        #                  chosen_index=scored.index(best),
        #                  notes=[f"Search depth: {self.depth}",
        #                         f"Nodes visited: {ctx.nodes_visited}"])
        #   and return best.action.
        #   Think: if two dice have the *same* expected score, which should win? Does it matter?
        ctx = self.make_context(game_map)
        scored = score_dice(state, self.depth, ctx)
        raise NotImplementedError("Smart AI not implemented yet.\nTODO: implement SmartAgent.choose_die()")

    def choose_direction(self, state: GameState, game_map: GameMap, options: tuple[str, ...]) -> str:
        # TODO(Exercise 4): same pattern with score_directions(state, self.depth, ctx).
        #   Use direction_label(game_map, node_id) from base_agent for the option labels.
        raise NotImplementedError("Smart AI not implemented yet.\nTODO: implement SmartAgent.choose_direction()")
