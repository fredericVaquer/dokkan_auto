import unittest

from dokkan_pathing.game.objective import Objective, load_objectives
from dokkan_pathing.game.state import METRIC_NAMES, Metrics


class ObjectiveTest(unittest.TestCase):
    def test_score_is_weighted_sum(self):
        objective = Objective("t", {"fights": -1000, "rolls": -10, "exclusive_items": 50, "ki": 2})
        metrics = Metrics(rolls=4, fights=1, exclusive_items=2, ki=3, zeni=99)
        self.assertEqual(objective.score(metrics), -1000 - 40 + 100 + 6)

    def test_breakdown_lists_nonzero_contributions(self):
        objective = Objective("t", {"fights": -1000, "rolls": -10, "zeni": 5})
        self.assertEqual(objective.breakdown(Metrics(rolls=3, zeni=2)), {"rolls": -30, "zeni": 10})

    def test_unknown_metric_is_rejected(self):
        with self.assertRaises(ValueError):
            Objective("t", {"boss": -100})

    def test_presets_exist_and_use_known_metrics(self):
        objectives = load_objectives()
        self.assertTrue({"fast", "safe", "farming", "balanced"} <= set(objectives))
        for objective in objectives.values():
            self.assertTrue(set(objective.weights) <= set(METRIC_NAMES))

    def test_a_fight_outweighs_any_single_reward_in_every_preset(self):
        for objective in load_objectives().values():
            fight = -objective.weights["fights"]
            best_reward = max(w for w in objective.weights.values() if w > 0)
            self.assertGreater(fight, best_reward, objective.name)

    def test_preset_priorities(self):
        o = load_objectives()
        self.assertLess(o["fast"].weights["rolls"], o["farming"].weights["rolls"])
        self.assertGreater(o["farming"].weights["exclusive_items"], o["balanced"].weights["exclusive_items"])
        self.assertLess(o["safe"].weights["damage"], o["fast"].weights["damage"])


if __name__ == "__main__":
    unittest.main()
