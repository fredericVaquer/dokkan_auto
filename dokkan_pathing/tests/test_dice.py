import random
import unittest
from collections import Counter

from dokkan_pathing.game import rules
from dokkan_pathing.game.dice import DiceDistribution, load_distributions
from dokkan_pathing.game.state import Phase
from dokkan_pathing.tests.helpers import line_map


class ReplaceDieTest(unittest.TestCase):
    def test_each_slot_is_replaced_in_place(self):
        self.assertEqual(rules.replace_die((2, 4, 6), 0, 5), (5, 4, 6))
        self.assertEqual(rules.replace_die((2, 4, 6), 1, 5), (2, 5, 6))
        self.assertEqual(rules.replace_die((2, 4, 6), 2, 5), (2, 4, 5))

    def test_invalid_slot_raises(self):
        with self.assertRaises(IndexError):
            rules.replace_die((2, 4, 6), 3, 1)


class DiceSlotsDuringPlayTest(unittest.TestCase):
    def setUp(self):
        self.map = line_map("start", *["normal"] * 20, "final")

    def test_used_slot_is_empty_until_roll_then_refilled_in_same_slot(self):
        state = rules.initial_state(self.map, (6, 4, 2))
        state, _ = rules.select_die(state, self.map, 1)
        self.assertEqual(state.dice, (6, None, 2))
        state, _ = rules.advance(state, self.map)
        self.assertIs(state.phase, Phase.ROLL)
        state, _ = rules.roll(state, 1)
        # Not sorted: the new 1 sits where the 4 was.
        self.assertEqual(state.dice, (6, 1, 2))
        self.assertIs(state.phase, Phase.CHOOSE_DIE)
        self.assertIsNone(state.active_slot)

    def test_every_slot_keeps_its_position(self):
        for slot in range(3):
            state = rules.initial_state(self.map, (2, 4, 6))
            state = rules.play_die(state, self.map, slot)
            state, _ = rules.roll(state, 1)
            expected = list((2, 4, 6))
            expected[slot] = 1
            self.assertEqual(state.dice, tuple(expected))

    def test_available_slots_only_in_choose_die(self):
        state = rules.initial_state(self.map, (2, 4, 6))
        self.assertEqual(rules.available_slots(state), [0, 1, 2])
        state, _ = rules.select_die(state, self.map, 0)
        self.assertEqual(rules.available_slots(state), [])

    def test_invalid_inputs_raise(self):
        state = rules.initial_state(self.map, (2, 4, 6))
        with self.assertRaises(ValueError):
            rules.select_die(state, self.map, 3)
        with self.assertRaises(ValueError):
            rules.select_die(state, self.map, None)
        with self.assertRaises(ValueError):
            rules.roll(state, 3)  # wrong phase
        state = rules.play_die(state, self.map, 0)
        with self.assertRaises(ValueError):
            rules.roll(state, 7)
        with self.assertRaises(ValueError):
            rules.initial_state(self.map, (0, 4, 6))


class DistributionTest(unittest.TestCase):
    def test_from_weights_normalises(self):
        dist = DiceDistribution.from_weights("x", [1, 1, 1, 1, 2, 2])
        self.assertAlmostEqual(sum(dist.probabilities), 1.0)
        self.assertAlmostEqual(dist.probability(5), 0.25)
        self.assertAlmostEqual(dist.probability(1), 0.125)

    def test_invalid_distributions_raise(self):
        with self.assertRaises(ValueError):
            DiceDistribution("x", (0.5, 0.5))
        with self.assertRaises(ValueError):
            DiceDistribution("x", (0.5, 0.5, 0.5, 0, 0, -0.5))
        with self.assertRaises(ValueError):
            DiceDistribution("x", (0.1,) * 6)
        with self.assertRaises(ValueError):
            DiceDistribution.from_weights("x", [0] * 6)

    def test_outcomes_skip_impossible_faces(self):
        dist = DiceDistribution.from_weights("x", [0, 1, 0, 1, 0, 2])
        self.assertEqual([f for f, _ in dist.outcomes()], [2, 4, 6])
        self.assertAlmostEqual(sum(p for _, p in dist.outcomes()), 1.0)

    def test_mean(self):
        self.assertAlmostEqual(DiceDistribution.uniform().mean, 3.5)

    def test_sampling_matches_probabilities(self):
        dist = DiceDistribution.from_weights("x", [3, 2, 2, 1, 1, 1])
        rng = random.Random(1234)
        n = 60_000
        counts = Counter(dist.sample(rng) for _ in range(n))
        for face, p in dist.outcomes():
            self.assertAlmostEqual(counts[face] / n, p, delta=0.01)

    def test_sampling_never_returns_zero_probability_face(self):
        dist = DiceDistribution.from_weights("x", [0, 0, 1, 0, 0, 1])
        rng = random.Random(0)
        self.assertEqual({dist.sample(rng) for _ in range(2000)}, {3, 6})

    def test_configured_distributions_load(self):
        dists = load_distributions()
        self.assertIn("uniform", dists)
        for dist in dists.values():
            self.assertAlmostEqual(sum(dist.probabilities), 1.0)


if __name__ == "__main__":
    unittest.main()
