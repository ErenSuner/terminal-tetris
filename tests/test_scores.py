import json
import tempfile
import unittest
from pathlib import Path

from terminal_tetris import scores
from terminal_tetris.engine import Game


def played(score=1000, lines=12, level=3, combo=4, elapsed=90.0):
    """A game object standing in for a finished run."""
    game = Game(level=1, seed=1)
    game.score = score
    game.lines = lines
    game.level = level
    game.max_combo = combo
    game.elapsed = elapsed
    return game


class FileTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = Path(self.dir.name) / "sub" / "records.json"

    def test_save_then_load_round_trips(self):
        records = scores.Records(score=500, lines=8, level=2, combo=3, time=42.5)
        self.assertTrue(scores.save(records, self.path))
        self.assertEqual(scores.load(self.path), records)

    def test_a_missing_file_loads_as_an_empty_record(self):
        self.assertEqual(scores.load(self.path), scores.Records())

    def test_broken_json_loads_as_an_empty_record(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{not json", encoding="utf-8")
        self.assertEqual(scores.load(self.path), scores.Records())

    def test_wrong_types_are_skipped_field_by_field(self):
        self.path.parent.mkdir(parents=True)
        payload = {"best": {"score": 700, "lines": "kirk", "date": 5}}
        self.path.write_text(json.dumps(payload), encoding="utf-8")
        records = scores.load(self.path)
        self.assertEqual(records.score, 700)
        self.assertEqual(records.lines, 0)
        self.assertEqual(records.date, "")

    def test_an_unwritable_path_fails_quietly(self):
        blocker = Path(self.dir.name) / "file"
        blocker.write_text("x", encoding="utf-8")
        self.assertFalse(scores.save(scores.Records(), blocker / "records.json"))

    def test_clear_removes_the_file_and_tolerates_a_missing_one(self):
        scores.save(scores.Records(score=5), self.path)
        self.assertTrue(scores.clear(self.path))
        self.assertFalse(self.path.exists())
        self.assertTrue(scores.clear(self.path))

    def test_the_default_path_lives_under_an_app_directory(self):
        path = scores.records_path()
        self.assertEqual(path.name, scores.FILE_NAME)
        self.assertEqual(path.parent.name, scores.APP_DIR)


class MergeTests(unittest.TestCase):
    def test_beats_names_only_the_improved_fields(self):
        best = scores.Records(score=2000, lines=5, level=9, combo=1, time=10.0)
        broken = best.beats(played(score=1000, lines=12, level=3, combo=4))
        self.assertEqual(broken, ["lines", "combo", "time"])

    def test_merged_keeps_the_best_of_each_field(self):
        best = scores.Records(score=2000, lines=5, level=9, combo=1, time=10.0)
        merged = best.merged(played())
        self.assertEqual(merged.score, 2000)
        self.assertEqual(merged.lines, 12)
        self.assertEqual(merged.level, 9)
        self.assertEqual(merged.combo, 4)
        self.assertEqual(merged.time, 90.0)

    def test_the_date_only_moves_when_something_is_beaten(self):
        best = scores.Records(score=9999, lines=99, level=99, combo=99,
                              time=999.0, date="2020-01-01")
        weak = best.merged(played())
        self.assertEqual(weak.date, "2020-01-01")
        strong = best.merged(played(score=10000, lines=100, level=100,
                                    combo=100, elapsed=1000.0))
        self.assertNotEqual(strong.date, "2020-01-01")


if __name__ == "__main__":
    unittest.main()
