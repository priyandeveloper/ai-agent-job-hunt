"""Local cache. A second hunt over the same pages costs nothing.

Scraped pages live in .cache/jds, Jev answers in .cache/fits. A cache hit
skips the network call, so a repeated hunt is instant and free.
"""

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from placement.score import Fit
from placement.scrape import Posting
from placement.settings import ROOT

CACHE_DIR = ROOT / ".cache"


def _digest(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _read(folder: str, key: str, cache_dir: Path) -> dict | None:
    path = cache_dir / folder / f"{key}.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _write(folder: str, key: str, payload: dict, cache_dir: Path) -> None:
    folder_path = cache_dir / folder
    folder_path.mkdir(parents=True, exist_ok=True)
    (folder_path / f"{key}.json").write_text(json.dumps(payload), encoding="utf-8")


def cached_posting(url: str, cache_dir: Path = CACHE_DIR) -> Posting | None:
    data = _read("jds", _digest(url), cache_dir)
    if not data:
        return None
    return Posting(source=data["source"], title=data["title"], text=data["text"])


def cache_posting(posting: Posting, cache_dir: Path = CACHE_DIR) -> None:
    _write(
        "jds",
        _digest(posting.url),
        {"source": posting.source, "title": posting.title, "text": posting.text},
        cache_dir,
    )


def fit_key(url: str, resume: str, want: str) -> str:
    """A Jev answer is valid only for this job, this resume, and this want text."""
    return _digest(f"{url}\n{resume[:2500]}\n{want.strip()[:400]}")


def cached_fit(key: str, cache_dir: Path = CACHE_DIR) -> Fit | None:
    data = _read("fits", key, cache_dir)
    if not data:
        return None
    return Fit(**data)


def cache_fit(key: str, fit: Fit, cache_dir: Path = CACHE_DIR) -> None:
    _write("fits", key, asdict(fit), cache_dir)
