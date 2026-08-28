import re
import unittest

from terminal_tetris.engine import GAME_OVER, PAUSED, ClearInfo, Game, Piece
from terminal_tetris.render import ASCII_CHARS, BANNER_TIME, MIN_COLS, MIN_ROWS, Renderer
from terminal_tetris.scores import Records

ANSI = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")


def plain(text):
    return ANSI.sub("", text)


class FrameTests(unittest.TestCase):
    def setUp(self):
        self.game = Game(level=1, seed=5)

    def test_the_frame_fits_the_smallest_supported_terminal(self):
        lines = plain(Renderer().frame(self.game, MIN_COLS, MIN_ROWS)).split("\n")
        self.assertEqual(len(lines), MIN_ROWS)
        self.assertLessEqual(max(len(line) for line in lines), MIN_COLS)

    def test_lines_never_exceed_the_terminal_width(self):
        for cols in (MIN_COLS, 60, 80):
            lines = plain(Renderer().frame(self.game, cols, 30)).split("\n")
            self.assertLessEqual(max(len(line) for line in lines), cols, cols)

    def test_a_too_small_terminal_gets_a_message_instead_of_a_crash(self):
        text = plain(Renderer().frame(self.game, 20, 5))
        self.assertIn("cok kucuk", text)

    def test_ascii_mode_emits_no_wide_characters(self):
        text = Renderer(color=False, unicode=False).frame(self.game, 80, 30)
        self.assertTrue(text.isascii())

    def test_the_active_piece_and_its_ghost_are_drawn(self):
        self.game.piece = Piece("O", x=3, y=20)
        rows = Renderer(color=False, unicode=False)._board_rows(self.game)
        flat = "".join("".join(row) for row in rows)
        self.assertIn("[]", flat)
        self.assertIn("::", flat)

    def test_overlays_keep_the_board_width(self):
        renderer = Renderer()
        expected = len(plain(renderer._board_lines(self.game)[0]))
        for phase, needle in ((PAUSED, "PAUSED"), (GAME_OVER, "OYUN BITTI")):
            self.game.phase = phase
            lines = [plain(line) for line in renderer._board_lines(self.game)]
            self.assertEqual({len(line) for line in lines}, {expected}, phase)
            self.assertTrue(any(needle in line for line in lines), phase)


class PanelTests(unittest.TestCase):
    def setUp(self):
        self.game = Game(level=1, seed=5)
        self.renderer = Renderer(color=False, unicode=False)

    def test_the_panel_shows_the_stored_best_score(self):
        text = plain(self.renderer.frame(self.game, 80, 30, Records(score=4321)))
        self.assertIn("BEST", text)
        self.assertIn("4321", text)

    def test_the_current_run_overtakes_a_lower_best(self):
        self.game.score = 5000
        text = plain(self.renderer.frame(self.game, 80, 30, Records(score=100)))
        self.assertIn("5000", text)

    def test_the_combo_meter_grows_with_the_chain(self):
        self.game.combo = 3
        lines = [plain(line) for line in self.renderer._left_panel(self.game)]
        self.assertTrue(any("x3 ###.." in line for line in lines), lines)

    def test_the_panel_never_outgrows_the_board(self):
        board = self.renderer._board_lines(self.game)
        self.assertLessEqual(len(self.renderer._left_panel(self.game)), len(board))


class ControlHintTests(unittest.TestCase):
    """Every key has to be visible somewhere; clipping used to eat the tail."""

    def setUp(self):
        self.game = Game(level=1, seed=5)
        self.renderer = Renderer(color=False, unicode=False)

    def hint_text(self, cols, rows):
        lines = plain(self.renderer.frame(self.game, cols, rows)).split("\n")
        return " ".join(lines[MIN_ROWS - 2 :])

    def test_a_roomy_terminal_shows_every_key_with_its_action(self):
        text = self.hint_text(80, 30)
        for key, action in ASCII_CHARS["controls"]:
            self.assertIn(f"{key} {action}", text)

    def test_the_smallest_terminal_drops_the_labels_but_keeps_the_keys(self):
        text = self.hint_text(MIN_COLS, MIN_ROWS)
        for key, _ in ASCII_CHARS["controls"]:
            self.assertIn(key, text)

    def test_hint_lines_never_exceed_the_width(self):
        for cols, rows in ((MIN_COLS, MIN_ROWS), (60, 26), (80, 30), (120, 40)):
            for line in self.renderer._control_lines(cols, 3):
                self.assertLessEqual(len(line), cols, (cols, rows))


class BannerTests(unittest.TestCase):
    def setUp(self):
        self.game = Game(level=1, seed=5)
        self.renderer = Renderer(color=False, unicode=False)

    def test_the_banner_clears_itself_after_its_time(self):
        self.game.last_clear = ClearInfo(lines=4, points=800)
        self.game.last_clear_at = 0.0
        self.game.elapsed = 0.1
        self.assertIn("TETRIS", plain(self.renderer.frame(self.game, 80, 30)))
        self.game.elapsed = BANNER_TIME + 0.1
        self.assertNotIn("TETRIS", plain(self.renderer.frame(self.game, 80, 30)))

    def test_the_banner_reports_the_points_scored(self):
        self.game.last_clear = ClearInfo(lines=2, combo=2, points=350)
        self.game.last_clear_at = self.game.elapsed
        self.assertIn("+350", plain(self.renderer.frame(self.game, 80, 30)))

    def test_the_playfield_is_drawn_exactly_as_the_engine_holds_it(self):
        """No overlays, so a cleared row leaves no trace on the next frame."""
        before = self.renderer._board_rows(self.game)
        self.game.last_clear = ClearInfo(lines=1, points=100)
        self.game.last_clear_at = self.game.elapsed
        self.assertEqual(self.renderer._board_rows(self.game), before)

    def test_a_beaten_record_is_announced_on_the_game_over_screen(self):
        self.game.phase = GAME_OVER
        self.game.score = 9999
        text = "".join(plain(line) for line in
                       self.renderer._board_lines(self.game, Records(score=10)))
        self.assertIn("YENI REKOR", text)
        text = "".join(plain(line) for line in
                       self.renderer._board_lines(self.game, Records(score=99999)))
        self.assertIn("R yeniden", text)


if __name__ == "__main__":
    unittest.main()
