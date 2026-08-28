import unittest

from terminal_tetris import pieces
from terminal_tetris.board import WIDTH
from terminal_tetris.engine import (
    GAME_OVER,
    MAX_LOCK_RESETS,
    PAUSED,
    PLAYING,
    Game,
    Piece,
)


def fill_row(game, y, empty=()):
    game.board.grid[y] = [0 if x in empty else 1 for x in range(WIDTH)]


class BagTests(unittest.TestCase):
    def test_every_window_of_seven_is_a_permutation(self):
        game = Game(seed=7)
        sequence = [game.piece.kind]
        for _ in range(20):
            game._spawn()
            sequence.append(game.piece.kind)
        for start in range(0, 14, 7):
            window = sequence[start : start + 7]
            self.assertEqual(sorted(window), sorted(pieces.TYPES))

    def test_the_seed_makes_the_order_repeatable(self):
        self.assertEqual(Game(seed=42).queue, Game(seed=42).queue)

    def test_the_queue_always_shows_five_upcoming_pieces(self):
        game = Game(seed=1)
        for _ in range(30):
            game._spawn()
            self.assertGreaterEqual(len(game.queue), 5)


class GravityTests(unittest.TestCase):
    def test_higher_levels_fall_faster(self):
        slow = Game(level=1).gravity_interval
        fast = Game(level=10).gravity_interval
        self.assertLess(fast, slow)

    def test_gravity_moves_the_piece_down_one_row_per_interval(self):
        game = Game(level=1, seed=1)
        start_y = game.piece.y
        game.update(game.gravity_interval, [])
        self.assertEqual(game.piece.y, start_y + 1)

    def test_soft_drop_scores_one_per_cell(self):
        game = Game(seed=1)
        game.update(0.0, ["soft"])
        self.assertEqual(game.score, 1)

    def test_hard_drop_scores_two_per_cell_and_locks(self):
        game = Game(seed=1)
        piece = game.piece
        distance = game.board.drop_distance(piece.cells, piece.x, piece.y)
        game.update(0.0, ["hard"])
        self.assertEqual(game.score, 2 * distance)
        self.assertIsNot(game.piece, piece)


class LockDelayTests(unittest.TestCase):
    def test_a_grounded_piece_locks_after_the_delay(self):
        game = Game(level=1, seed=1)
        game.piece = Piece("O", x=3, y=38)
        game.update(0.6, [])
        self.assertTrue(any(game.board.grid[39]))

    def test_moves_reset_the_timer_only_fifteen_times(self):
        game = Game(level=1, seed=1)
        game.piece = Piece("O", x=3, y=38)
        for i in range(20):
            game._try_move(1 if i % 2 == 0 else -1, 0)
        self.assertEqual(game.lock_resets, MAX_LOCK_RESETS)

        game.lock_timer = 0.4
        game._try_move(1, 0)
        self.assertEqual(game.lock_timer, 0.4)


class HoldTests(unittest.TestCase):
    def test_first_hold_stores_the_piece(self):
        game = Game(seed=1)
        kind = game.piece.kind
        upcoming = game.queue[0]
        game.update(0.0, ["hold"])
        self.assertEqual(game.hold, kind)
        self.assertEqual(game.piece.kind, upcoming)

    def test_hold_is_locked_out_until_the_next_piece(self):
        game = Game(seed=1)
        game.update(0.0, ["hold"])
        held, current = game.hold, game.piece.kind
        game.update(0.0, ["hold"])
        self.assertEqual(game.hold, held)
        self.assertEqual(game.piece.kind, current)

    def test_hold_swaps_once_a_piece_is_stored(self):
        game = Game(seed=1)
        game.update(0.0, ["hold"])
        stored = game.hold
        game.update(0.0, ["hard"])
        dropped_next = game.piece.kind
        game.update(0.0, ["hold"])
        self.assertEqual(game.piece.kind, stored)
        self.assertEqual(game.hold, dropped_next)


class ScoringTests(unittest.TestCase):
    def drop_tetris(self, game):
        for y in range(36, 40):
            fill_row(game, y, empty={0})
        game.piece = Piece("I", rotation=1, x=-2, y=0)
        game.hard_drop()

    def test_tetris_scores_eight_hundred_times_the_level(self):
        game = Game(level=1, seed=1)
        self.drop_tetris(game)
        self.assertEqual(game.last_clear.lines, 4)
        self.assertEqual(game.last_clear.label, "TETRIS")
        self.assertEqual(game.last_clear.points, 800)
        self.assertTrue(game.back_to_back)

    def test_back_to_back_tetris_gets_the_bonus(self):
        game = Game(level=1, seed=1)
        self.drop_tetris(game)
        game.combo = -1  # isolate the back-to-back multiplier from the combo
        self.drop_tetris(game)
        self.assertTrue(game.last_clear.back_to_back)
        self.assertEqual(game.last_clear.points, 1200)

    def test_a_single_breaks_the_back_to_back_chain(self):
        game = Game(level=1, seed=1)
        self.drop_tetris(game)
        fill_row(game, 39, empty={0, 1})
        game.piece = Piece("O", x=-1, y=0)
        game.hard_drop()
        self.assertEqual(game.last_clear.lines, 1)
        self.assertFalse(game.back_to_back)

    def test_combo_adds_fifty_per_chained_clear(self):
        game = Game(level=1, seed=1)
        fill_row(game, 39, empty={0, 1})
        game.piece = Piece("O", x=-1, y=0)
        game.hard_drop()
        self.assertEqual(game.last_clear.combo, 0)

        fill_row(game, 39, empty={0, 1})
        game.piece = Piece("O", x=-1, y=0)
        game.hard_drop()
        self.assertEqual(game.last_clear.combo, 1)
        self.assertEqual(game.last_clear.points, 100 + 50)

    def test_ten_lines_raise_the_level(self):
        game = Game(level=1, seed=1)
        game.lines = 9
        fill_row(game, 39, empty={0, 1})
        game.piece = Piece("O", x=-1, y=0)
        game.hard_drop()
        self.assertEqual(game.lines, 10)
        self.assertEqual(game.level, 2)


class TSpinTests(unittest.TestCase):
    def test_three_corners_with_both_fronts_filled_is_a_full_tspin(self):
        game = Game(seed=1)
        game.piece = Piece("T", rotation=2, x=3, y=30)
        game.last_move_was_rotation = True
        game.board.grid[32][3] = 1
        game.board.grid[32][5] = 1
        game.board.grid[30][3] = 1
        self.assertEqual(game._detect_tspin(), "full")

    def test_only_one_front_corner_is_a_mini(self):
        game = Game(seed=1)
        game.piece = Piece("T", rotation=2, x=3, y=30)
        game.last_move_was_rotation = True
        game.board.grid[30][3] = 1
        game.board.grid[30][5] = 1
        game.board.grid[32][3] = 1
        self.assertEqual(game._detect_tspin(), "mini")

    def test_the_last_kick_promotes_a_mini_to_a_full_tspin(self):
        game = Game(seed=1)
        game.piece = Piece("T", rotation=2, x=3, y=30)
        game.last_move_was_rotation = True
        game.last_kick_index = 4
        game.board.grid[30][3] = 1
        game.board.grid[30][5] = 1
        game.board.grid[32][3] = 1
        self.assertEqual(game._detect_tspin(), "full")

    def test_a_piece_that_only_moved_is_never_a_tspin(self):
        game = Game(seed=1)
        game.piece = Piece("T", rotation=2, x=3, y=30)
        game.last_move_was_rotation = False
        game.board.grid[32][3] = 1
        game.board.grid[32][5] = 1
        game.board.grid[30][3] = 1
        self.assertEqual(game._detect_tspin(), "")

    def test_rotating_into_a_notch_scores_a_tspin_double(self):
        game = Game(level=1, seed=1)
        fill_row(game, 38, empty={3, 4, 5})
        fill_row(game, 39, empty={4})
        game.board.grid[37][3] = 1  # the overhang that forces a spin entry

        game.piece = Piece("T", rotation=1, x=3, y=37)
        self.assertTrue(game._try_rotate(1))
        game.hard_drop()

        self.assertEqual(game.last_clear.tspin, "full")
        self.assertEqual(game.last_clear.lines, 2)
        self.assertEqual(game.last_clear.label, "T-SPIN DOUBLE")
        self.assertEqual(game.last_clear.points, 1200)


class PhaseTests(unittest.TestCase):
    def test_pause_toggles(self):
        game = Game(seed=1)
        game.update(0.0, ["pause"])
        self.assertEqual(game.phase, PAUSED)
        game.update(0.0, ["pause"])
        self.assertEqual(game.phase, PLAYING)

    def test_a_paused_game_ignores_gravity(self):
        game = Game(level=1, seed=1)
        game.update(0.0, ["pause"])
        y = game.piece.y
        game.update(5.0, [])
        self.assertEqual(game.piece.y, y)

    def test_a_blocked_spawn_ends_the_game(self):
        game = Game(seed=1)
        for y in range(20, 24):
            fill_row(game, y)
        game._spawn()
        self.assertEqual(game.phase, GAME_OVER)

    def test_restart_clears_the_board_and_score(self):
        game = Game(seed=1)
        game.score = 999
        game.phase = GAME_OVER
        game.update(0.0, ["restart"])
        self.assertEqual(game.phase, PLAYING)
        self.assertEqual(game.score, 0)
        self.assertTrue(all(not any(row) for row in game.board.grid))


class ComboStateTests(unittest.TestCase):
    def clear_a_row(self, game):
        fill_row(game, 39, empty={0, 1})
        game.piece = Piece("O", x=-1, y=0)
        game.hard_drop()

    def test_max_combo_keeps_the_longest_chain_of_the_run(self):
        game = Game(level=1, seed=1)
        for _ in range(3):
            self.clear_a_row(game)
        self.assertEqual(game.max_combo, 2)
        game.piece = Piece("O", x=0, y=0)
        game.hard_drop()  # no clear, chain broken
        self.assertEqual(game.combo, -1)
        self.assertEqual(game.max_combo, 2)

    def test_a_clear_records_when_it_happened(self):
        game = Game(level=1, seed=1)
        game.elapsed = 12.5
        self.clear_a_row(game)
        self.assertEqual(game.last_clear_at, 12.5)


if __name__ == "__main__":
    unittest.main()
