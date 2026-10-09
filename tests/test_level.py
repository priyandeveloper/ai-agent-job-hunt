import unittest
from types import SimpleNamespace

from placement.gate import SKILL_LEVELS
from placement.score import _level, _note, _skills_in


class LevelTests(unittest.TestCase):
    def test_fractional_score_rounds_onto_the_rubric(self):
        index, label = _level(SimpleNamespace(score=1.63), SKILL_LEVELS)
        self.assertEqual(index, 2)
        self.assertEqual(label, SKILL_LEVELS[2])

    def test_whole_float_stays_on_that_level(self):
        index, _label = _level(SimpleNamespace(score=1.0), SKILL_LEVELS)
        self.assertEqual(index, 1)


class NoteTests(unittest.TestCase):
    def test_sentence_names_the_skill_jev_picked(self):
        labels = _skills_in("We need Python and SQL.")
        text = _note("python", "sql", labels)
        self.assertIn("resume shows Python", text)
        self.assertIn("asks for SQL", text)


if __name__ == "__main__":
    unittest.main()
