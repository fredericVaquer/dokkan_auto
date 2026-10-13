import math
import unittest

from dokkan_pathing.agents.max_agent import MaxAgent
from dokkan_pathing.game import rules
from dokkan_pathing.game.dice import DiceDistribution
from dokkan_pathing.game.map import GameMap, MapError, available_maps, load_map
from dokkan_pathing.game.simulator import Simulator
from dokkan_pathing.game.state import Phase
from dokkan_pathing.game.tiles import TileType
from dokkan_pathing.tests.helpers import build_map, node

REQUIRED_MAPS = {"basic", "fight_avoidance", "farming", "fast", "damage", "mixed"}


class MapLoadingTest(unittest.TestCase):
    def test_all_example_maps_load_and_reach_the_final_tile(self):
        self.assertTrue(REQUIRED_MAPS <= set(available_maps()))
        for key in available_maps():
            game_map = load_map(key)
            self.assertLess(game_map.distance_to_final(game_map.start), math.inf, key)
            self.assertTrue(any(len(n.next) > 1 for n in game_map.nodes.values()), f"{key} has no branch")

    def test_mixed_map_contains_every_mechanic(self):
        game_map = load_map("mixed")
        types = {n.type for n in game_map.nodes.values()}
        for t in (TileType.FIGHT, TileType.KINTON, TileType.DAMAGE, TileType.EXCLUSIVE,
                  TileType.RANDOM, TileType.BABA, TileType.BOSS, TileType.FINAL):
            self.assertIn(t, types)
        self.assertTrue(any(len(n.next) == 3 for n in game_map.nodes.values()))

    def test_distance_to_final_counts_steps_and_kinton_shortcuts(self):
        game_map = build_map(
            node("s", "start", ["a", "k"]),
            node("a", "normal", ["b"]),
            node("b", "normal", ["c"]),
            node("c", "normal", ["end"]),
            node("k", "kinton", target="c"),
            node("end", "final"),
        )
        self.assertEqual(game_map.distance_to_final("end"), 0)
        self.assertEqual(game_map.distance_to_final("a"), 3)
        self.assertEqual(game_map.distance_to_final("k"), 1)
        self.assertEqual(game_map.distance_to_final("s"), 2)

    def test_invalid_maps_are_rejected(self):
        end = node("end", "final")
        bad = [
            dict(nodes=[node("s", "start", ["nowhere"]), end]),  # dangling edge
            dict(nodes=[node("s", "start", ["a"]), node("a"), end]),  # dead end
            dict(nodes=[node("s", "start", ["k"]), node("k", "kinton"), end]),  # kinton without target
            dict(nodes=[node("s", "start", ["a"]), node("a", "normal", ["s"])]),  # no final tile
            dict(nodes=[node("s", "start", ["end"]), end], initial_dice=[1, 2]),  # bad dice
        ]
        for spec in bad:
            with self.assertRaises(MapError, msg=str(spec)):
                GameMap.from_dict({"name": "bad", "start": "s", **spec})


class SimulatorTest(unittest.TestCase):
    def test_same_seed_gives_same_run(self):
        game_map = load_map("mixed")
        runs = [Simulator(game_map, DiceDistribution.uniform(), seed=7).run_episode(MaxAgent()) for _ in range(2)]
        self.assertEqual(runs[0].metrics, runs[1].metrics)
        self.assertEqual(runs[0].events, runs[1].events)

    def test_max_agent_completes_every_map(self):
        for key in available_maps():
            for seed in range(20):
                result = Simulator(load_map(key), DiceDistribution.uniform(), seed=seed).run_episode(MaxAgent())
                self.assertTrue(result.completed, f"{key} seed {seed}")
                self.assertFalse(result.aborted)

    def test_random_initial_dice_when_map_has_none(self):
        game_map = build_map(node("s", "start", ["end"]), node("end", "final"))
        sim = Simulator(game_map, DiceDistribution.uniform(), seed=3)
        self.assertTrue(all(1 <= d <= 6 for d in sim.state.dice))

    def test_step_by_step_interface(self):
        sim = Simulator(load_map("basic"), DiceDistribution.uniform(), seed=1)
        sim.select_die(0)  # the 2: s -> a -> b
        while sim.phase is Phase.MOVING:
            sim.step()
        self.assertIs(sim.phase, Phase.ROLL)
        sim.roll(5)
        self.assertEqual(sim.state.dice, (5, 4, 6))
        with self.assertRaises(ValueError):
            sim.advance()  # CHOOSE_DIE needs a decision, not an automatic step

    def test_runaway_agent_is_aborted(self):
        # The first direction always loops back to the start, so Max never finishes.
        game_map = build_map(
            node("s", "start", ["a"]),
            node("a", "normal", ["k", "end"]),
            node("k", "kinton", target="s"),
            node("end", "final"),
        )
        result = Simulator(game_map, DiceDistribution.uniform(), seed=0, max_rolls=30).run_episode(MaxAgent())
        self.assertTrue(result.aborted)
        self.assertFalse(result.completed)
        self.assertEqual(result.metrics.rolls, 30)


class MaxAgentTest(unittest.TestCase):
    def setUp(self):
        self.map = load_map("basic")

    def test_picks_largest_die(self):
        agent = MaxAgent()
        for dice, expected in (((2, 4, 6), 2), ((6, 4, 2), 0), ((1, 5, 3), 1)):
            state = rules.initial_state(self.map, dice)
            self.assertEqual(agent.choose_die(state, self.map), expected)
            self.assertIsNotNone(agent.last_decision)

    def test_ties_go_to_leftmost(self):
        state = rules.initial_state(self.map, (3, 5, 5))
        self.assertEqual(MaxAgent().choose_die(state, self.map), 1)

    def test_takes_first_direction(self):
        state = rules.play_die(rules.initial_state(self.map, (6, 1, 1)), self.map, 0)
        options = rules.direction_options(state, self.map)
        self.assertEqual(MaxAgent().choose_direction(state, self.map, options), options[0])


if __name__ == "__main__":
    unittest.main()
