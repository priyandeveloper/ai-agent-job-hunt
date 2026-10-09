"""Hunt jobs from a resume. A Strands agent chooses the tools. Jev scores the jobs."""

import argparse
from pathlib import Path

from placement import load_resume
from placement.settings import ROOT, load_settings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read a resume, search recruiter jobs, score each one with Jev."
    )
    parser.add_argument(
        "--resume",
        default=str(ROOT / "resume.md"),
        help="PDF, markdown, or text resume.",
    )
    parser.add_argument(
        "--want",
        default="",
        help="What you are looking for, in your own words.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Number of jobs to score (10 to 30, default 20).",
    )
    args = parser.parse_args()

    resume = load_resume(Path(args.resume))
    settings = load_settings(need_firecrawl=True)

    from placement.agent import run_agent

    run_agent(resume, settings, want=args.want, limit=args.limit)


if __name__ == "__main__":
    main()
