import unittest

from terminal_tetris import cli as tetris


class KeyMapTests(unittest.TestCase):
    def test_arrows_and_wasd_share_the_same_actions(self):
        pairs = [("LEFT", "a"), ("RIGHT", "d"), ("DOWN", "s"), ("SPACE", "w")]
        for arrow, letter in pairs:
            self.assertEqual(
                tetris.KEY_ACTIONS[arrow], tetris.KEY_ACTIONS[letter], letter
            )

    def test_wasd_does_not_collide_with_the_other_bindings(self):
        self.assertEqual(tetris.KEY_ACTIONS["f"], "flip")
        for letter in "wasd":
            self.assertNotIn(letter, tetris.QUIT_KEYS)

    def test_every_action_the_engine_understands_is_reachable(self):
        expected = {"left", "right", "soft", "hard", "cw", "ccw", "flip", "hold",
                    "pause", "restart"}
        self.assertEqual(set(tetris.KEY_ACTIONS.values()), expected)


if __name__ == "__main__":
    unittest.main()
