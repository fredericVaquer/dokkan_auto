import unittest

from dokkan_pathing.game import rules
from dokkan_pathing.game.rules import EventKind
from dokkan_pathing.game.state import Phase
from dokkan_pathing.tests.helpers import build_map, line_map, node


def kinds(events):
    return [e.kind for e in events]


class NormalMovementTest(unittest.TestCase):
    def setUp(self):
        self.map = line_map("start", "normal", "normal", "normal", "normal", "normal", "final")

    def test_moves_exactly_die_value_steps(self):
        state = rules.play_die(rules.initial_state(self.map, (3, 1, 1)), self.map, 0)
        self.assertEqual(state.position, "n3")
        self.assertEqual(state.steps_remaining, 0)
        self.assertIs(state.phase, Phase.ROLL)

    def test_one_move_event_per_step(self):
        state, events = rules.select_die(rules.initial_state(self.map, (3, 1, 1)), self.map, 0)
        self.assertIs(state.phase, Phase.MOVING)
        moves = []
        while state.phase is Phase.MOVING:
            state, events = rules.step(state, self.map)
            moves += [e.node for e in events if e.kind is EventKind.MOVE]
        self.assertEqual(moves, ["n1", "n2", "n3"])

    def test_each_die_used_counts_one_roll(self):
        state = rules.initial_state(self.map, (1, 1, 1))
        for expected in (1, 2, 3):
            state = rules.play_die(state, self.map, 0)
            state, _ = rules.roll(state, 1)
            self.assertEqual(state.metrics.rolls, expected)

    def test_rules_do_not_mutate_input_state(self):
        before = rules.initial_state(self.map, (3, 1, 1))
        rules.play_die(before, self.map, 0)
        self.assertEqual(before.position, "n0")
        self.assertEqual(before.dice, (3, 1, 1))


class StoppingFightTest(unittest.TestCase):
    def setUp(self):
        self.map = build_map(
            node("s", "start", ["a"]),
            node("a", "normal", ["f"]),
            node("f", "fight", ["b"], stop=True),
            node("b", "normal", ["c"]),
            node("c", "normal", ["end"]),
            node("end", "final"),
        )

    def test_fight_stops_movement_and_remaining_steps_are_lost(self):
        state, events = rules.select_die(rules.initial_state(self.map, (5, 1, 1)), self.map, 0)
        state, more = rules.advance(state, self.map)
        events += more
        self.assertEqual(state.position, "f")
        self.assertEqual(state.metrics.fights, 1)
        self.assertEqual(state.steps_remaining, 0)
        self.assertIs(state.phase, Phase.ROLL)
        lost = [e for e in events if e.kind is EventKind.MOVEMENT_LOST]
        self.assertEqual(len(lost), 1)
        self.assertEqual(lost[0].value, 3)

    def test_landing_exactly_on_fight_loses_nothing(self):
        state, events = rules.select_die(rules.initial_state(self.map, (2, 1, 1)), self.map, 0)
        state, more = rules.advance(state, self.map)
        self.assertEqual(state.position, "f")
        self.assertEqual(state.metrics.fights, 1)
        self.assertNotIn(EventKind.MOVEMENT_LOST, kinds(events + more))

    def test_replacement_die_is_rolled_after_fight(self):
        state = rules.play_die(rules.initial_state(self.map, (5, 2, 3)), self.map, 0)
        state, _ = rules.roll(state, 4)
        self.assertEqual(state.dice, (4, 2, 3))

    def test_player_stays_on_fight_tile_and_fight_is_consumed(self):
        state = rules.play_die(rules.initial_state(self.map, (5, 1, 1)), self.map, 0)
        self.assertIn("f", state.consumed)
        state, _ = rules.roll(state, 2)
        state = rules.play_die(state, self.map, 0)
        self.assertEqual(state.position, "c")
        self.assertEqual(state.metrics.fights, 1)


class PlainFightTest(unittest.TestCase):
    def setUp(self):
        self.map = line_map("start", "normal", "fight", "normal", "normal", "final")

    def test_passing_a_plain_fight_does_not_fight(self):
        state = rules.play_die(rules.initial_state(self.map, (4, 1, 1)), self.map, 0)
        self.assertEqual(state.position, "n4")
        self.assertEqual(state.metrics.fights, 0)
        self.assertNotIn("n2", state.consumed)

    def test_landing_on_a_plain_fight_fights_and_consumes_it(self):
        state = rules.play_die(rules.initial_state(self.map, (2, 1, 1)), self.map, 0)
        self.assertEqual(state.metrics.fights, 1)
        self.assertIn("n2", state.consumed)


class KintonTest(unittest.TestCase):
    def setUp(self):
        self.map = build_map(
            node("s", "start", ["a"]),
            node("a", "normal", ["k"]),
            node("k", "kinton", target="t"),
            node("x", "normal", ["t"]),
            node("t", "zeni", ["u"]),
            node("u", "normal", ["end"]),
            node("end", "final"),
        )

    def test_kinton_stops_teleports_and_loses_remaining_movement(self):
        state, events = rules.select_die(rules.initial_state(self.map, (5, 1, 1)), self.map, 0)
        state, more = rules.advance(state, self.map)
        events += more
        self.assertEqual(state.position, "t")
        self.assertIs(state.phase, Phase.ROLL)
        self.assertEqual(state.steps_remaining, 0)
        self.assertIn(EventKind.TELEPORT, kinds(events))
        lost = [e.value for e in events if e.kind is EventKind.MOVEMENT_LOST]
        self.assertEqual(lost, [3])

    def test_teleport_arrival_triggers_nothing(self):
        state = rules.play_die(rules.initial_state(self.map, (2, 1, 1)), self.map, 0)
        self.assertEqual(state.position, "t")
        self.assertEqual(state.metrics.zeni, 0)

    def test_replacement_die_after_kinton_and_movement_continues_from_target(self):
        state = rules.play_die(rules.initial_state(self.map, (2, 5, 6)), self.map, 0)
        state, _ = rules.roll(state, 1)
        self.assertEqual(state.dice, (1, 5, 6))
        state = rules.play_die(state, self.map, 0)
        self.assertEqual(state.position, "u")

    def test_kinton_can_be_reused(self):
        self.assertNotIn("k", rules.play_die(rules.initial_state(self.map, (2, 1, 1)), self.map, 0).consumed)

    def test_kinton_onto_final_tile_ends_stage(self):
        game_map = build_map(
            node("s", "start", ["k"]),
            node("k", "kinton", target="end"),
            node("end", "final"),
        )
        state = rules.play_die(rules.initial_state(game_map, (3, 1, 1)), game_map, 0)
        self.assertIs(state.phase, Phase.DONE)
        self.assertEqual(state.position, "end")


class BranchingTest(unittest.TestCase):
    def setUp(self):
        self.map = build_map(
            node("s", "start", ["a"]),
            node("a", "normal", ["up", "mid", "down"]),
            node("up", "normal", ["up2"]),
            node("up2", "normal", ["end"]),
            node("mid", "normal", ["end"]),
            node("down", "zeni", ["down2"]),
            node("down2", "normal", ["end"]),
            node("end", "final"),
        )

    def test_branch_with_steps_left_asks_for_direction(self):
        state = rules.play_die(rules.initial_state(self.map, (3, 1, 1)), self.map, 0)
        self.assertIs(state.phase, Phase.CHOOSE_DIRECTION)
        self.assertEqual(state.position, "a")
        self.assertEqual(state.steps_remaining, 2)
        self.assertEqual(rules.direction_options(state, self.map), ("up", "mid", "down"))

    def test_chosen_direction_uses_remaining_steps(self):
        state = rules.play_die(rules.initial_state(self.map, (3, 1, 1)), self.map, 0)
        state = rules.play_direction(state, self.map, "down")
        self.assertEqual(state.position, "down2")
        self.assertEqual(state.metrics.zeni, 1)
        self.assertIs(state.phase, Phase.ROLL)

    def test_invalid_direction_raises(self):
        state = rules.play_die(rules.initial_state(self.map, (3, 1, 1)), self.map, 0)
        with self.assertRaises(ValueError):
            rules.select_direction(state, self.map, "end")

    def test_landing_exactly_on_branch_needs_no_decision_yet(self):
        state = rules.play_die(rules.initial_state(self.map, (1, 1, 1)), self.map, 0)
        self.assertEqual(state.position, "a")
        self.assertIs(state.phase, Phase.ROLL)

    def test_move_starting_on_branch_asks_immediately(self):
        state = rules.play_die(rules.initial_state(self.map, (1, 2, 1)), self.map, 0)
        state, _ = rules.roll(state, 1)
        state, _ = rules.select_die(state, self.map, 1)
        self.assertIs(state.phase, Phase.CHOOSE_DIRECTION)
        self.assertEqual(state.steps_remaining, 2)


class BossTest(unittest.TestCase):
    def setUp(self):
        self.map = line_map("start", "normal", "boss", "normal", "boss", "final")

    def test_boss_always_stops_and_is_not_a_fight(self):
        state, events = rules.select_die(rules.initial_state(self.map, (6, 1, 1)), self.map, 0)
        state, more = rules.advance(state, self.map)
        self.assertEqual(state.position, "n2")
        self.assertIs(state.phase, Phase.ROLL)
        self.assertIn(EventKind.BOSS, kinds(events + more))
        self.assertEqual(state.metrics.bosses, 1)
        self.assertEqual(state.metrics.fights, 0)

    def test_run_continues_after_boss_to_the_next_boss(self):
        state = rules.play_die(rules.initial_state(self.map, (6, 6, 1)), self.map, 0)
        state, _ = rules.roll(state, 6)
        state = rules.play_die(state, self.map, 1)
        self.assertEqual(state.position, "n4")
        self.assertEqual(state.metrics.bosses, 2)
        self.assertFalse(state.is_terminal)


class FinalTileTest(unittest.TestCase):
    def setUp(self):
        self.map = line_map("start", "normal", "final")

    def test_final_tile_ends_stage_even_with_steps_left(self):
        state, events = rules.select_die(rules.initial_state(self.map, (6, 1, 1)), self.map, 0)
        state, more = rules.advance(state, self.map)
        self.assertIs(state.phase, Phase.DONE)
        self.assertTrue(state.is_terminal)
        self.assertEqual(state.position, "n2")
        self.assertEqual(state.steps_remaining, 0)
        self.assertIn(EventKind.FINAL, kinds(events + more))

    def test_no_roll_after_final_tile(self):
        state = rules.play_die(rules.initial_state(self.map, (2, 1, 1)), self.map, 0)
        self.assertIs(state.phase, Phase.DONE)
        with self.assertRaises(ValueError):
            rules.roll(state, 3)


class TileEffectTest(unittest.TestCase):
    def test_items_are_collected_when_passed_over(self):
        game_map = line_map("start", "support_item", "training_item", "zeni", "ki", "exclusive", "normal", "final")
        state = rules.play_die(rules.initial_state(game_map, (6, 1, 1)), game_map, 0)
        m = state.metrics
        self.assertEqual(
            (m.support_items, m.training_items, m.zeni, m.ki, m.exclusive_items), (1, 1, 1, 1, 1)
        )
        self.assertEqual(state.consumed, {"n1", "n2", "n3", "n4", "n5"})

    def test_amount_scales_metric(self):
        game_map = build_map(node("s", "start", ["z"]), node("z", "zeni", ["end"], amount=3), node("end", "final"))
        state = rules.play_die(rules.initial_state(game_map, (1, 1, 1)), game_map, 0)
        self.assertEqual(state.metrics.zeni, 3)

    def test_items_are_not_collected_twice(self):
        game_map = build_map(
            node("s", "start", ["a"]),
            node("a", "zeni", ["k", "b"]),
            node("k", "kinton", target="s"),
            node("b", "normal", ["end"]),
            node("end", "final"),
        )
        state = rules.play_die(rules.initial_state(game_map, (2, 1, 1)), game_map, 0)
        state = rules.play_direction(state, game_map, "k")
        self.assertEqual(state.position, "s")
        state, _ = rules.roll(state, 1)
        state = rules.play_die(state, game_map, 1)
        self.assertEqual(state.position, "a")
        self.assertEqual(state.metrics.zeni, 1)

    def test_damage_baba_and_random_only_fire_on_landing(self):
        game_map = line_map("start", "damage", "baba", "random", "normal", "final")
        passed = rules.play_die(rules.initial_state(game_map, (4, 1, 1)), game_map, 0)
        self.assertEqual((passed.metrics.damage, passed.metrics.baba_shops, passed.metrics.random_tiles), (0, 0, 0))
        for die, metric in ((1, "damage"), (2, "baba_shops"), (3, "random_tiles")):
            landed = rules.play_die(rules.initial_state(game_map, (die, 1, 1)), game_map, 0)
            self.assertEqual(getattr(landed.metrics, metric), 1, metric)

    def test_damage_amount_and_damage_is_not_consumed(self):
        game_map = build_map(
            node("s", "start", ["d"]),
            node("d", "damage", ["k", "b"], amount=2),
            node("k", "kinton", target="s"),
            node("b", "normal", ["end"]),
            node("end", "final"),
        )
        state = rules.play_die(rules.initial_state(game_map, (1, 1, 1)), game_map, 0)
        self.assertEqual(state.metrics.damage, 2)
        self.assertNotIn("d", state.consumed)

    def test_random_tile_is_consumed(self):
        game_map = line_map("start", "random", "final")
        state = rules.play_die(rules.initial_state(game_map, (1, 1, 1)), game_map, 0)
        self.assertIn("n1", state.consumed)


if __name__ == "__main__":
    unittest.main()
