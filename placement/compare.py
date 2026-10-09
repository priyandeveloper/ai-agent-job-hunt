"""Run one posting through Jev and through a chat model. Print time and tokens.

Jev is the fast decision model (the session blurb calls it RLCD).
The chat model is the FutureX draft model, asked only to judge, not to write.
"""

import time

from openai import OpenAI

from placement.score import score_fit
from placement.scrape import Posting
from placement.settings import Settings

JUDGE = """Compare one student resume to one job posting.
Reply with exactly two lines:
decision: apply|stretch|skip|ask
because: one sentence
Use ask when you are unsure. Do not draft an email.
"""


def _judge(resume: str, posting: Posting, settings: Settings) -> tuple[str, float, int, int]:
    client = OpenAI(api_key=settings.futurex_api_key, base_url=settings.futurex_base_url)
    started = time.perf_counter()
    response = client.chat.completions.create(
        model=settings.chat_model,
        temperature=0,
        messages=[
            {"role": "system", "content": JUDGE},
            {"role": "user", "content": f"Posting:\n{posting.text}\n\nResume:\n{resume}"},
        ],
    )
    elapsed = time.perf_counter() - started
    usage = response.usage
    prompt_tokens = int(usage.prompt_tokens) if usage else 0
    completion_tokens = int(usage.completion_tokens) if usage else 0
    text = (response.choices[0].message.content or "").strip()
    return text, elapsed, prompt_tokens, completion_tokens


def compare(resume: str, posting: Posting, settings: Settings) -> str:
    started = time.perf_counter()
    fit = score_fit(resume, posting, settings)
    jev_seconds = time.perf_counter() - started
    reply, chat_seconds, prompt_tokens, completion_tokens = _judge(resume, posting, settings)

    return "\n".join(
        [
            f"Posting: {posting.title}",
            "",
            f"Jev ({settings.jev_model})",
            f"  time: {jev_seconds:.2f}s",
            f"  input tokens: {fit.input_tokens}",
            f"  decision: {fit.decision}",
            "",
            f"Chat ({settings.chat_model})",
            f"  time: {chat_seconds:.2f}s",
            f"  input tokens: {prompt_tokens}",
            f"  output tokens: {completion_tokens}",
            "  reply:",
            reply,
        ]
    )
