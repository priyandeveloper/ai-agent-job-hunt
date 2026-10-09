"""Load the campus key and the two base URLs from .env."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _need(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(
            f"Missing {name}. Copy .env.example to .env and fill in the value."
        )
    return value


@dataclass(frozen=True)
class Settings:
    futurex_api_key: str
    futurex_base_url: str
    jev_base_url: str
    jev_model: str
    chat_model: str
    firecrawl_api_key: str


def load_settings(*, need_firecrawl: bool = False) -> Settings:
    firecrawl = os.getenv("FIRECRAWL_API_KEY", "").strip()
    if need_firecrawl and not firecrawl:
        raise SystemExit(
            "Missing FIRECRAWL_API_KEY. A job URL needs it. "
            "A local posting file does not: python app.py --jd samples/posting.md"
        )
    return Settings(
        futurex_api_key=_need("FUTUREX_API_KEY"),
        futurex_base_url=_need("FUTUREX_BASE_URL").rstrip("/"),
        jev_base_url=_need("JEV_BASE_URL").rstrip("/"),
        jev_model=os.getenv("JEV_MODEL", "jev-latest").strip() or "jev-latest",
        chat_model=_need("CHAT_MODEL"),
        firecrawl_api_key=firecrawl,
    )
