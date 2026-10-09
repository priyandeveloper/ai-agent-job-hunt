"""Order titles and scored jobs. No model."""

SKILLS = (
    "python",
    "java",
    "javascript",
    "typescript",
    "react",
    "sql",
    "fastapi",
    "django",
    "node",
    "kotlin",
    "android",
    "machine learning",
    "golang",
    "go",
)

ROLE_WORDS = ("engineer", "developer", "intern", "sde", "software")
ORDER = {"apply": 0, "stretch": 1, "ask": 2, "skip": 3}


def signals(resume: str) -> list[str]:
    text = resume.lower()
    found = [skill for skill in SKILLS if skill in text]
    if any(word in text for word in ("intern", "student", "b.tech", "final year", "final-year")):
        found.append("intern")
    return found


def rank_listings(listings: list, words: list[str], limit: int = 8) -> list:
    """Best title matches first. Unmatched recruiter links stay in the list."""
    scored: list[tuple[int, object]] = []
    rest: list[object] = []
    for listing in listings:
        title = listing.title.lower()
        score = sum(2 for word in words if word in title)
        if any(role in title for role in ROLE_WORDS):
            score += 1
        if score:
            scored.append((score, listing))
        else:
            rest.append(listing)
    scored.sort(key=lambda item: item[0], reverse=True)
    ordered = [listing for _, listing in scored] + rest
    return ordered[:limit]


def rank_scored(jobs: list, limit: int = 3) -> list:
    ranked = sorted(
        jobs,
        key=lambda job: (
            ORDER.get(job.fit.decision, 9),
            -job.fit.skill_index,
            job.fit.bond,
        ),
    )
    return ranked[:limit]
