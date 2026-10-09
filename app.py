"""Hunt jobs from a resume. A Strands agent chooses the tools. Jev scores the jobs."""

import argparse
from pathlib import Path

from placement.compare import compare
from placement.resume_text import load_resume
from placement.score import score_fit
from placement.scrape import Posting, scrape_url
from placement.settings import ROOT, load_settings
from placement.write import draft


def _posting(args: argparse.Namespace, settings) -> Posting:
    if getattr(args, "url", None):
        return scrape_url(args.url, settings)
    path = Path(args.jd)
    if not path.is_file():
        raise SystemExit(f"File not found: {path}")
    return Posting(source=str(path), title=path.stem, text=path.read_text(encoding="utf-8"))


def _add_source(parser: argparse.ArgumentParser) -> None:
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--jd", help="Local posting file. Skips Firecrawl.")
    source.add_argument("--url", help="One job URL. Uses Firecrawl.")


def main() -> None:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--resume", default=str(ROOT / "resume.md"), help="PDF, markdown, or text resume.")

    parser = argparse.ArgumentParser(description="Read a resume, search recruiter jobs, score each one with Jev.")
    commands = parser.add_subparsers(dest="command", required=True)

    score = commands.add_parser("score", parents=[common], help="Score one posting with Jev.")
    _add_source(score)
    score.add_argument("--draft", action="store_true", help="Write the email even when the gate says ask.")

    hunt_cmd = commands.add_parser("hunt", parents=[common], help="Strands agent: search from the resume and score the jobs.")
    hunt_cmd.add_argument("--want", default="", help="What you are looking for, in your own words.")

    compare_cmd = commands.add_parser("compare", parents=[common], help="Time Jev against a chat model on one posting.")
    _add_source(compare_cmd)

    agent_cmd = commands.add_parser("agent", parents=[common], help="Same Strands hunt as the hunt command.")
    agent_cmd.add_argument("--want", default="", help="What you are looking for, in your own words.")

    args = parser.parse_args()
    resume = load_resume(Path(args.resume))
    needs_firecrawl = args.command in {"hunt", "agent"} or bool(getattr(args, "url", None))
    settings = load_settings(need_firecrawl=needs_firecrawl)

    if args.command in {"hunt", "agent"}:
        from placement.agent import run_agent

        run_agent(resume, settings, want=getattr(args, "want", ""))
        return

    posting = _posting(args, settings)
    if args.command == "compare":
        print(compare(resume, posting, settings))
        return

    fit = score_fit(resume, posting, settings)
    print(f"Posting: {posting.title}\n")
    print(fit.report())
    print()
    if fit.decision == "skip":
        print("No email. The gate said skip.")
        return
    if fit.decision == "ask" and not args.draft:
        print("No email. The gate said ask. Pass --draft if you still want one.")
        return
    print(draft(resume, posting, fit, settings))


if __name__ == "__main__":
    main()
