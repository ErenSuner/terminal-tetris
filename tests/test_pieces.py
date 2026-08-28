import unittest

from terminal_tetris import pieces


class ShapeTests(unittest.TestCase):
    def test_every_piece_has_four_cells_in_every_rotation(self):
        for kind in pieces.TYPES:
            for rotation in range(4):
                cells = pieces.cells(kind, rotation)
                self.assertEqual(len(cells), 4, kind)
                self.assertEqual(len(set(cells)), 4, kind)

    def test_cells_stay_inside_the_bounding_box(self):
        for kind in pieces.TYPES:
            size = pieces.BOX[kind]
            for rotation in range(4):
                for x, y in pieces.cells(kind, rotation):
                    self.assertTrue(0 <= x < size and 0 <= y < size, (kind, rotation))

    def test_o_piece_never_changes(self):
        first = pieces.cells("O", 0)
        for rotation in range(4):
            self.assertEqual(pieces.cells("O", rotation), first)

    def test_rotation_wraps(self):
        self.assertEqual(pieces.cells("T", 4), pieces.cells("T", 0))


class KickTests(unittest.TestCase):
    def test_jlstz_table_covers_all_quarter_turns(self):
        for frm in range(4):
            for turn in (1, -1):
                to = (frm + turn) % 4
                offsets = pieces.kicks("T", frm, to)
                self.assertEqual(len(offsets), 5)
                self.assertEqual(offsets[0], (0, 0))

    def test_i_piece_uses_its_own_table(self):
        self.assertNotEqual(pieces.kicks("I", 0, 1), pieces.kicks("J", 0, 1))
        self.assertEqual(pieces.kicks("I", 0, 1)[1], (-2, 0))

    def test_o_piece_gets_no_kicks(self):
        self.assertEqual(pieces.kicks("O", 0, 1), ((0, 0),))

    def test_half_turn_uses_the_180_table(self):
        self.assertEqual(pieces.kicks("T", 0, 2), pieces.KICKS_180)
        self.assertEqual(pieces.kicks("L", 1, 3), pieces.KICKS_180)


if __name__ == "__main__":
    unittest.main()
