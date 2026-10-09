"""The pipeline, in order: load a posting, score it, write only if the gate opens."""

import argparse
from pathlib import Path

from placement.agent import run_agent
from placement.score import score_fit
from placement.scrape import Posting, scrape_url
from placement.settings import ROOT, load_settings
from placement.write import draft


def _read(path: Path) -> str:
    if not path.is_file():
        raise SystemExit(f"File not found: {path}")
    return path.read_text(encoding="utf-8")


def load_posting(args: argparse.Namespace, settings) -> Posting:
    if args.url:
        return scrape_url(args.url, settings)
    text = _read(Path(args.jd))
    return Posting(source=str(args.jd), title=Path(args.jd).stem, text=text)


def main() -> None:
    parser = argparse.ArgumentParser(description="Score a posting, then draft if it fits.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--url", help="Job posting URL. Uses Firecrawl.")
    source.add_argument("--jd", help="Local posting file. Skips Firecrawl.")
    parser.add_argument("--resume", default=str(ROOT / "resume.md"), help="Resume markdown.")
    parser.add_argument(
        "--agent",
        action="store_true",
        help="Let a Strands agent call scrape and score. Requires --url.",
    )
    args = parser.parse_args()

    if args.agent and not args.url:
        raise SystemExit("--agent scrapes a URL. Pass --url, not --jd.")

    resume = _read(Path(args.resume))
    settings = load_settings(need_firecrawl=bool(args.url))

    if args.agent:
        print(run_agent(args.url, resume, settings))
        return

    posting = load_posting(args, settings)
    print(f"Posting: {posting.title}")
    print(f"Source:  {posting.source}\n")

    fit = score_fit(resume, posting, settings)
    print(fit.report())
    print()

    if fit.decision == "skip":
        print("No draft. The gate said skip.")
        return

    print(draft(resume, posting, fit, settings))


if __name__ == "__main__":
    main()
