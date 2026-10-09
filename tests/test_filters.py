import unittest
from types import SimpleNamespace

from placement.filters import (
    company_name,
    looks_like_jd,
    looks_like_job_url,
    looks_like_listing_title,
    pay_amount,
)
from placement.match import rank_scored
from placement.query import search_query


class UrlTests(unittest.TestCase):
    def test_keeps_recruiter_links(self):
        kept = [
            "https://boards.greenhouse.io/acme/jobs/7",
            "https://jobs.lever.co/acme/abc",
            "https://jobs.ashbyhq.com/acme/1",
            "https://careers.razorpay.com/jobs/backend-intern",
            "https://example.com/careers/backend-intern",
            "https://example.com/jobs/backend-intern/apply",
        ]
        for url in kept:
            self.assertTrue(looks_like_job_url(url), url)

    def test_drops_blogs_and_homepages(self):
        dropped = [
            "https://example.com/",
            "https://blog.example.com/how-to-get-hired",
            "https://medium.com/some-career-advice",
            "https://www.naukri.com/front-end-engineer-jobs-in-bengaluru",
            "https://www.naukri.com/job-listings-frontend-developer-1",
            "https://wellfound.com/role/l/frontend-engineer/india",
            "https://jobschat.ai/jobs/frontend-developer/bengaluru",
            "https://huntboard.ai/jobs/bangalore/frontend-developer",
            "https://example.com/jobs/bangalore/frontend-developer",
        ]
        for url in dropped:
            self.assertFalse(looks_like_job_url(url), url)


class JdTests(unittest.TestCase):
    def test_needs_length_and_a_marker(self):
        self.assertFalse(looks_like_jd("Apply now. Requirements: Python."))
        self.assertFalse(looks_like_jd("word " * 200))
        text = "Responsibilities\n" + ("Build Python services. Requirements listed below. Apply. " * 20)
        self.assertTrue(looks_like_jd(text))


class PayTests(unittest.TestCase):
    def test_reads_a_stated_stipend(self):
        found = pay_amount("Monthly stipend of ₹35,000 per month. No bond.")
        self.assertIn("35,000", found)

    def test_empty_when_pay_is_missing(self):
        self.assertEqual(pay_amount("We are hiring a backend intern."), "")


class ListingTitleTests(unittest.TestCase):
    def test_drops_a_search_heading(self):
        self.assertTrue(looks_like_listing_title("Front End Engineer Jobs In Bengaluru - Naukri.com"))
        self.assertFalse(looks_like_listing_title("Frontend Engineer"))


class CompanyTests(unittest.TestCase):
    def test_reads_the_board_slug(self):
        self.assertEqual(
            company_name("https://boards.greenhouse.io/groww/jobs/1"),
            "groww",
        )


class QueryTests(unittest.TestCase):
    def test_appends_what_the_student_typed(self):
        query = search_query("backend", "intern", "python", "Bengaluru, no bond")
        self.assertIn("python backend engineer intern", query)
        self.assertIn("Bengaluru", query)
        self.assertIn("no bond", query)


class RankTests(unittest.TestCase):
    def test_apply_beats_stretch_ask_and_skip(self):
        def job(decision: str, skill: int, bond: float):
            return SimpleNamespace(fit=SimpleNamespace(decision=decision, skill_index=skill, bond=bond))

        ranked = rank_scored(
            [
                job("skip", 4, 0.0),
                job("ask", 3, 0.1),
                job("stretch", 2, 0.2),
                job("apply", 3, 0.4),
            ],
            limit=4,
        )
        self.assertEqual([item.fit.decision for item in ranked], ["apply", "stretch", "ask", "skip"])


if __name__ == "__main__":
    unittest.main()
