"""Same two functions, registered as tools a Strands agent can call.

Run this after the linear pipeline already makes sense.
The agent may call the tools in any order. The linear path in app.py cannot.
"""

from strands import Agent, tool
from strands.models.openai import OpenAIModel

from placement.score import score_fit
from placement.scrape import Posting, scrape_url
from placement.settings import Settings
from placement.write import SYSTEM

_SETTINGS: Settings | None = None
_RESUME = ""


def _settings() -> Settings:
    if _SETTINGS is None:
        raise RuntimeError("Call run_agent() first.")
    return _SETTINGS


@tool
def scrape_job(url: str) -> str:
    """Scrape a job posting URL and return its title plus the page text.

    Args:
        url: The job posting link.
    """
    posting = scrape_url(url, _settings())
    return f"Title: {posting.title}\nSource: {posting.source}\n\n{posting.text}"


@tool
def score_job(posting_text: str) -> str:
    """Score the loaded resume against a job posting. Returns the code decision.

    Args:
        posting_text: The job posting text, usually from scrape_job.
    """
    posting = Posting(source="agent", title="posting", text=posting_text)
    fit = score_fit(_RESUME, posting, _settings())
    return fit.report()


def run_agent(url: str, resume: str, settings: Settings) -> str:
    global _SETTINGS, _RESUME
    _SETTINGS = settings
    _RESUME = resume

    model = OpenAIModel(
        client_args={
            "api_key": settings.futurex_api_key,
            "base_url": settings.futurex_base_url,
        },
        model_id=settings.chat_model,
        params={"temperature": 0.3},
    )
    agent = Agent(
        model=model,
        tools=[scrape_job, score_job],
        system_prompt=(
            SYSTEM
            + "\nCall scrape_job on the URL, then score_job on that text. "
            "If the code decision is skip, explain the reasons and stop. "
            "Do not draft bullets for a skip."
        ),
    )
    result = agent(
        f"Job URL: {url}\n\nResume:\n{resume}\n\n"
        "Scrape the posting, score it, then follow the code decision."
    )
    return str(result)


if __name__ == "__main__":
    raise SystemExit("Run python app.py --url <job-url> --agent")
