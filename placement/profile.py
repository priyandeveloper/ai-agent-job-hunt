"""One Jev call on the resume. The answers become the job-search query.

No chat model. What the student typed in --want is appended as-is.
"""

from dataclasses import dataclass

from typesafe_sdk import Choice, TypeSafeClient

from placement.query import search_query
from placement.settings import Settings


def _tokens(result: object) -> int:
    usage = getattr(result, "usage", None)
    raw = getattr(usage, "input_tokens", None)
    if raw is None and isinstance(usage, dict):
        raw = usage.get("input_tokens", 0)
    return int(raw or 0)


@dataclass(frozen=True)
class Profile:
    role: str
    level: str
    language: str
    query: str
    input_tokens: int


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
    return Profile(
        role=role,
        level=level,
        language=language,
        query=search_query(role, level, language, want),
        input_tokens=_tokens(result),
    )
