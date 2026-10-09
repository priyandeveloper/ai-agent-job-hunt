import unittest

from placement.boards import Listing, html_to_text, parse_greenhouse
from placement.match import rank_listings, signals


class ParseTests(unittest.TestCase):
    def test_reads_greenhouse_titles(self):
        payload = {
            "jobs": [
                {"id": 7, "title": "Backend Intern", "absolute_url": "https://boards.greenhouse.io/acme/jobs/7"},
                {"id": "", "title": "Skip me", "absolute_url": "https://example.com"},
            ]
        }
        found = parse_greenhouse("Acme", "acme", payload)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].title, "Backend Intern")

    def test_strips_html(self):
        self.assertEqual(html_to_text("<p>Python &amp; SQL</p>"), "Python & SQL")


class MatchTests(unittest.TestCase):
    def test_student_resume_picks_the_intern_title(self):
        resume = "Final-year B.Tech. Built a Python FastAPI project. Internship at a startup."
        listings = [
            Listing("Acme", "Account Executive", "https://example.com/a", "acme", "1"),
            Listing("Acme", "Backend Intern", "https://example.com/b", "acme", "2"),
            Listing("Acme", "Staff Engineer, Python", "https://example.com/c", "acme", "3"),
        ]
        ranked = rank_listings(listings, signals(resume))
        self.assertEqual(ranked[0].title, "Backend Intern")
        self.assertEqual(len(ranked), 3)


if __name__ == "__main__":
    unittest.main()
