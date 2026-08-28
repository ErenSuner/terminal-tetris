import unittest

from terminal_tetris import pieces
from terminal_tetris.board import HEIGHT, HIDDEN, VISIBLE, WIDTH, Board


class BoardTests(unittest.TestCase):
    def setUp(self):
        self.board = Board()

    def test_starts_empty(self):
        self.assertTrue(all(not any(row) for row in self.board.grid))

    def test_out_of_bounds_reads_as_solid(self):
        self.assertEqual(self.board.at(-1, 5), -1)
        self.assertEqual(self.board.at(WIDTH, 5), -1)
        self.assertEqual(self.board.at(0, HEIGHT), -1)

    def test_fits_rejects_walls_and_floor(self):
        cells = pieces.cells("O", 0)
        self.assertTrue(self.board.fits(cells, 0, 0))
        self.assertFalse(self.board.fits(cells, -2, 0))
        self.assertFalse(self.board.fits(cells, WIDTH - 1, 0))
        self.assertFalse(self.board.fits(cells, 0, HEIGHT - 1))

    def test_fits_rejects_occupied_cells(self):
        self.board.grid[10][4] = 3
        cells = pieces.cells("O", 0)
        self.assertFalse(self.board.fits(cells, 3, 9))

    def test_drop_distance_reaches_the_floor(self):
        cells = pieces.cells("I", 0)
        distance = self.board.drop_distance(cells, 3, 0)
        self.assertEqual(distance, HEIGHT - 2)

    def test_drop_distance_stops_on_a_stack(self):
        self.board.grid[20][3] = 1
        cells = pieces.cells("I", 0)
        self.assertEqual(self.board.drop_distance(cells, 3, 0), 18)

    def test_lock_writes_the_color(self):
        self.board.lock(pieces.cells("O", 0), 3, 20, 7)
        self.assertEqual(self.board.grid[20][4], 7)
        self.assertEqual(self.board.grid[21][5], 7)

    def test_clear_lines_removes_full_rows_and_shifts_the_stack_down(self):
        self.board.grid[38] = [1] * WIDTH
        self.board.grid[39] = [1] * WIDTH
        self.board.grid[37][0] = 5  # a lone block riding above the clear

        cleared = self.board.clear_lines()

        self.assertEqual(cleared, [38, 39])
        self.assertEqual(self.board.grid[39][0], 5)
        self.assertEqual(sum(sum(row) for row in self.board.grid), 5)

    def test_clear_lines_ignores_partial_rows(self):
        self.board.grid[39] = [1] * (WIDTH - 1) + [0]
        self.assertEqual(self.board.clear_lines(), [])

    def test_visible_rows_is_the_bottom_window(self):
        self.board.grid[HIDDEN][0] = 4
        rows = self.board.visible_rows()
        self.assertEqual(len(rows), VISIBLE)
        self.assertEqual(rows[0][0], 4)


if __name__ == "__main__":
    unittest.main()
