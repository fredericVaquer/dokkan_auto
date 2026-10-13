"""Target tests for YOUR Smart AI. They skip until the matching TODO is implemented.

Run them after each exercise:  python -m unittest dokkan_pathing.tests.test_smart_agent -v
A skip shows which TODO is still missing; a failure means it is implemented but wrong.

The value tests use tiny maps where every branch of the tree reaches the final tile
within the search depth, so the exact expected score can be computed by hand
and does not depend on any heuristic you add to evaluate() later.
"""

import unittest

from dokkan_pathing.agents.smart_agent import SmartAgent
from dokkan_pathing.game import rules
from dokkan_pathing.game.dice import DiceDistribution
from dokkan_pathing.game.map import load_map
from dokkan_pathing.game.objective import Objective, load_objectives
from dokkan_pathing.game.simulator import Simulator
from dokkan_pathing.search import expectimax
from dokkan_pathing.search.evaluation import evaluate
from dokkan_pathing.search.expectimax import SearchContext
from dokkan_pathing.tests.helpers import build_map, line_map, node

UNIFORM = DiceDistribution.uniform()
SIMPLE = Objective("simple", {"rolls": -25, "damage": -25, "zeni": 8, "fights": -1000})


def todo_guard(test):
    """Turn NotImplementedError (an unfinished TODO) into a skip instead of an error."""

    def wrapper(self):
        try:
            test(self)
        except NotImplementedError as exc:
            self.skipTest(str(exc).replace("\n", " "))

    wrapper.__name__ = test.__name__
    wrapper.__doc__ = test.__doc__
    return wrapper


class Exercise1EvaluateTest(unittest.TestCase):
    @todo_guard
    def test_terminal_state_scores_its_metrics(self):
        game_map = line_map("start", "zeni", "final")
        state = rules.play_die(rules.initial_state(game_map, (2, 1, 1)), game_map, 0)
        self.assertTrue(state.is_terminal)
        self.assertEqual(evaluate(state, SearchContext(game_map, SIMPLE, UNIFORM)), -25 + 8)


class Exercise2ExpectimaxTest(unittest.TestCase):
    @todo_guard
    def test_deterministic_finish(self):
        """Any die reaches the final tile: value = 1 roll + 1 zeni."""
        game_map = line_map("start", "zeni", "final")
        state = rules.initial_state(game_map, (2, 3, 4))
        value = expectimax.expectimax_value(state, 1, SearchContext(game_map, SIMPLE, UNIFORM))
        self.assertAlmostEqual(value, -25 + 8)

    @todo_guard
    def test_chance_node_averages_over_rolls(self):
        """s -> a -> b(damage) -> final with dice (1, 1, 1).

        Turn 1: forced to a.  Replacement die f:
          f >= 2: use it, jump over the damage to the final -> 2 rolls          = -50
          f == 1: every die is a 1 -> land on damage, then finish -> 3 rolls+1 dmg = -100
        Expected = P(1) * -100 + (1 - P(1)) * -50
        """
        game_map = line_map("start", "normal", "damage", "final")
        state = rules.initial_state(game_map, (1, 1, 1))
        for dist in (UNIFORM, DiceDistribution.from_weights("low", [3, 2, 2, 1, 1, 1])):
            p1 = dist.probability(1)
            value = expectimax.expectimax_value(state, 4, SearchContext(game_map, SIMPLE, dist))
            self.assertAlmostEqual(value, p1 * -100 + (1 - p1) * -50, msg=dist.name)

    @todo_guard
    def test_directions_do_not_consume_depth(self):
        """Two dice turns are needed; the branch in between must not use up depth 2."""
        game_map = build_map(
            node("s", "start", ["z", "n"]),
            node("z", "zeni", ["end"]),
            node("n", "normal", ["end"]),
            node("end", "final"),
        )
        state = rules.initial_state(game_map, (1, 1, 1))
        value = expectimax.expectimax_value(state, 2, SearchContext(game_map, SIMPLE, UNIFORM))
        self.assertAlmostEqual(value, -50 + 8)

    @todo_guard
    def test_counts_visited_nodes(self):
        game_map = line_map("start", "zeni", "final")
        ctx = SearchContext(game_map, SIMPLE, UNIFORM)
        expectimax.expectimax_value(rules.initial_state(game_map, (2, 3, 4)), 1, ctx)
        self.assertGreater(ctx.nodes_visited, 0)


class Exercise3And4DecisionTest(unittest.TestCase):
    @todo_guard
    def test_score_dice_prefers_jumping_over_damage(self):
        game_map = line_map("start", "damage", "normal", "final")
        state = rules.initial_state(game_map, (1, 2, 3))
        scored = expectimax.score_dice(state, 2, SearchContext(game_map, SIMPLE, UNIFORM))
        self.assertEqual([s.action for s in scored], [0, 1, 2])
        self.assertEqual(max(scored, key=lambda s: s.value).action, 2)  # the 3 finishes at once

    @todo_guard
    def test_score_directions_avoids_fight(self):
        game_map = build_map(
            node("s", "start", ["f", "n"]),
            node("f", "fight", ["end"], stop=True),
            node("n", "normal", ["end"]),
            node("end", "final"),
        )
        state = rules.play_die(rules.initial_state(game_map, (2, 2, 2)), game_map, 0)
        scored = expectimax.score_directions(state, 1, SearchContext(game_map, SIMPLE, UNIFORM))
        self.assertEqual([s.action for s in scored], ["f", "n"])
        self.assertEqual(max(scored, key=lambda s: s.value).action, "n")

    @todo_guard
    def test_agent_avoids_fights_on_fight_avoidance_map(self):
        game_map = load_map("fight_avoidance")
        objective = load_objectives()["balanced"]
        for seed in range(10):
            result = Simulator(game_map, UNIFORM, seed=seed).run_episode(SmartAgent(objective, UNIFORM, 2))
            self.assertEqual(result.metrics.fights, 0, f"seed {seed}")

    @todo_guard
    def test_agent_records_decision_for_ui(self):
        game_map = load_map("basic")
        agent = SmartAgent(load_objectives()["balanced"], UNIFORM, 1)
        agent.choose_die(rules.initial_state(game_map, (2, 4, 6)), game_map)
        self.assertIsNotNone(agent.last_decision)
        self.assertEqual(len(agent.last_decision.options), 3)
        self.assertTrue(all(o.value is not None for o in agent.last_decision.options))


class Exercise6HeuristicTest(unittest.TestCase):
    """Needs the cost-to-go heuristic in evaluate(). With a plain objective score, at
    depth 2 the long route looks free: the extra roll it costs lies beyond the horizon."""

    @todo_guard
    def test_objective_changes_route_on_farming_map(self):
        game_map = load_map("farming")
        objectives = load_objectives()
        # Die 3 from s: s -> a -> b, then 1 step left at the branch.
        state = rules.play_die(rules.initial_state(game_map, (3, 1, 1)), game_map, 0)
        options = rules.direction_options(state, game_map)
        farming = SmartAgent(objectives["farming"], UNIFORM, 2).choose_direction(state, game_map, options)
        fast = SmartAgent(objectives["fast"], UNIFORM, 2).choose_direction(state, game_map, options)
        self.assertEqual(farming, "c", "farming should take the long route with the exclusive item")
        self.assertEqual(fast, "h", "fast should take the short route")


class Exercise5MemoizationTest(unittest.TestCase):
    @todo_guard
    def test_cache_gives_same_values_with_fewer_nodes(self):
        game_map = load_map("mixed")
        state = rules.initial_state(game_map, (2, 4, 6))
        objective = load_objectives()["balanced"]
        expectimax.cache_key(state, 3)  # skip until the TODO exists
        cold = SearchContext(game_map, objective, UNIFORM)
        first = expectimax.expectimax_value(state, 3, cold)
        warm_nodes_before = cold.nodes_visited
        second = expectimax.expectimax_value(state, 3, cold)  # same context: cache is warm
        self.assertAlmostEqual(first, second)
        self.assertGreater(cold.cache_hits, 0)
        self.assertLess(cold.nodes_visited - warm_nodes_before, warm_nodes_before)


if __name__ == "__main__":
    unittest.main()
