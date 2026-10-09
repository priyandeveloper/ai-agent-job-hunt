"""Search text from Jev's labels plus what the student typed. No network."""

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
    base = (
        f"{language} {ROLE_PHRASE[role]} {LEVEL_PHRASE[level]} "
        "hiring careers greenhouse.io lever.co ashbyhq.com"
    )
    extra = " ".join(want.split())[:180]
    if not extra:
        return base
    return f"{base} {extra}"
