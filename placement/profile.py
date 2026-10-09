"""One Jev call on the resume. The answers become the job-search query.

No chat model. What the student typed in --want is appended as-is.
query.py is merged here: the search query builder sits next to the profiler.
"""

from dataclasses import dataclass

from typesafe_sdk import Choice, TypeSafeClient

from placement.settings import Settings

# ---------------------------------------------------------------------------
# Query builder (merged from query.py)
# ---------------------------------------------------------------------------

ROLE_PHRASE = {
    "backend": "backend engineer",
    "frontend": "frontend engineer",
    "data": "data analyst",
    "ml": "machine learning engineer",
    "mobile": "mobile developer",
    "swe": "software engineer",
}
LEVEL_PHRASE = {
    "intern": "intern",
    "fresher": "fresher",
    "experienced": "engineer",
}


def search_query(role: str, level: str, language: str, want: str = "") -> str:
    role_str = ROLE_PHRASE.get(role, "software engineer")
    level_str = LEVEL_PHRASE.get(level, "intern")
    extra = " ".join(want.split())[:180]

    # Combine terms avoiding redundant repetition
    terms: list[str] = []
    if extra:
        terms.append(extra)
    if language and language.lower() not in extra.lower():
        terms.append(language)
    if role_str and role_str.lower() not in extra.lower():
        terms.append(role_str)
    if level_str and level_str.lower() not in extra.lower():
        terms.append(level_str)

    ats_targets = "greenhouse.io OR lever.co OR ashbyhq.com"
    return f"{' '.join(terms)} jobs {ats_targets}"


# ---------------------------------------------------------------------------
# Resume profiling
# ---------------------------------------------------------------------------

def _tokens(result: object) -> tuple[int, int]:
    usage = getattr(result, "usage", None)
    in_tok = getattr(usage, "input_tokens", None)
    out_tok = getattr(usage, "output_tokens", None)
    if in_tok is None and isinstance(usage, dict):
        in_tok = usage.get("input_tokens", 0)
        out_tok = usage.get("output_tokens", 0)
    return int(in_tok or 0), int(out_tok or 0)


@dataclass(frozen=True)
class Profile:
    role: str
    level: str
    language: str
    query: str
    input_tokens: int
    output_tokens: int = 0


def profile_resume(resume: str, settings: Settings, want: str = "") -> Profile:
    with TypeSafeClient(
        api_key=settings.futurex_api_key,
        base_url=settings.jev_base_url,
        model=settings.jev_model,
    ) as client:
        result = client.system_one(
            state=resume[:4000],
            questions={
                "role": Choice(
                    instructions="Which role family has the strongest evidence in this resume?",
                    criteria={
                        "backend": "APIs, server-side code, or databases in a project or internship",
                        "frontend": "React, UI, or web pages the person built",
                        "data": "SQL, analysis, or tables, with little product code",
                        "ml": "A trained model or a dataset project",
                        "mobile": "An Android, iOS, or other mobile app",
                        "swe": "Software projects, and no single family dominates",
                    },
                ),
                "level": Choice(
                    instructions="What level of role fits the work history in this resume?",
                    criteria={
                        "intern": "Student, or projects and at most one internship",
                        "fresher": "New graduate, or under one year of full-time work",
                        "experienced": "More than one year of full-time work",
                    },
                ),
                "language": Choice(
                    instructions="Which language shows up in a real project, not only in a skills list?",
                    criteria={
                        "python": "Python in a project or internship",
                        "javascript": "JavaScript or TypeScript in a project",
                        "java": "Java in a project",
                        "sql": "SQL or data work, and little application code",
                    },
                ),
            },
        )

    role = str(result.choices["role"].choice)
    level = str(result.choices["level"].choice)
    language = str(result.choices["language"].choice)
    in_tokens, out_tokens = _tokens(result)
    return Profile(
        role=role,
        level=level,
        language=language,
        query=search_query(role, level, language, want),
        input_tokens=in_tokens,
        output_tokens=out_tokens,
    )
