"""One chat call. Writes bullets only from lines that are already in the resume."""

from openai import OpenAI

from placement.score import Fit
from placement.scrape import Posting
from placement.settings import Settings

SYSTEM = """You write application material for a student.

Rules:
- Use only facts that appear in the resume. If a posting skill is missing, say it is missing.
- Do not invent employers, metrics, tools, or years of experience.
- Write four resume bullets and one short note of about 120 words.
- Each bullet starts with a verb and names the project or internship it comes from.
- When the decision is "stretch", the note must say what the gap is.
"""


def draft(resume: str, posting: Posting, fit: Fit, settings: Settings) -> str:
    client = OpenAI(
        api_key=settings.futurex_api_key,
        base_url=settings.futurex_base_url,
    )
    user = (
        f"Decision: {fit.decision}\n"
        f"Reasons:\n- " + "\n- ".join(fit.reasons) + "\n\n"
        f"Posting ({posting.title}):\n{posting.text}\n\n"
        f"Resume:\n{resume}"
    )
    # WORKSHOP: tighten SYSTEM above. Ask for the project name in every bullet.
    response = client.chat.completions.create(
        model=settings.chat_model,
        temperature=0.3,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
    )
    text = response.choices[0].message.content
    if not text:
        raise SystemExit("The chat model returned an empty draft.")
    return text.strip()
