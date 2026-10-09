import unittest

from placement.gate import decide


class DecideTests(unittest.TestCase):
    def test_bond_skips_even_when_skills_match(self):
        decision, _ = decide(skill_index=4, bond=0.8, above_fresher=0.1)
        self.assertEqual(decision, "skip")

    def test_experience_bar_skips(self):
        decision, _ = decide(skill_index=4, bond=0.1, above_fresher=0.9)
        self.assertEqual(decision, "skip")

    def test_strong_skills_apply(self):
        decision, _ = decide(skill_index=3, bond=0.2, above_fresher=0.2)
        self.assertEqual(decision, "apply")

    def test_partial_skills_stretch(self):
        decision, _ = decide(skill_index=2, bond=0.2, above_fresher=0.2)
        self.assertEqual(decision, "stretch")

    def test_weak_skills_skip(self):
        decision, _ = decide(skill_index=1, bond=0.1, above_fresher=0.1)
        self.assertEqual(decision, "skip")


if __name__ == "__main__":
    unittest.main()
