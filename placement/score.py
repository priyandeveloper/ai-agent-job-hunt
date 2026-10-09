"""Ask Jev typed questions and decide apply, stretch, or skip.

gate.py is merged here: the policy constants and decide() sit next to the
scoring code that feeds them.
"""

import re
from dataclasses import dataclass

from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

from placement.filters import pay_amount
from placement.scrape import Posting
from placement.settings import Settings

# ---------------------------------------------------------------------------
# Decision gate
# ---------------------------------------------------------------------------

# Lowest to highest. The index is what decide() compares.
SKILL_LEVELS = [
    "Almost no overlap with the required skills",
    "A few matching skills, with large gaps",
    "Partial overlap; the candidate could contribute with support",
    "Strong overlap with the core requirements",
    "The resume already shows the core stack in real projects",
]

# WORKSHOP: move these and watch the same posting change buckets.
BOND_SKIP = 0.65
EXPERIENCE_SKIP = 0.65
SKILL_APPLY = 3
SKILL_STRETCH = 2
# How close to a cutoff still counts as "ask the user".
ASK_BAND = 0.12
# Maximum number of postings scored per hunt.
TOP_N = 30


def _near_cutoff(value: float, cutoff: float) -> bool:
    return 0 < (cutoff - value) <= ASK_BAND


def decide(skill_index: int, bond: float, above_fresher: float) -> tuple[str, list[str]]:
    """Turn three numbers into apply, stretch, skip, or ask.

    skip and apply are confident. ask means a probability is sitting
    next to a cutoff, so the loop should stop and wait for a person.
    """
    if bond >= BOND_SKIP:
        return "skip", [f"Bond language is likely ({bond:.0%})."]
    if above_fresher >= EXPERIENCE_SKIP:
        return "skip", [f"The experience bar is above a fresher ({above_fresher:.0%})."]
    if _near_cutoff(bond, BOND_SKIP) or _near_cutoff(above_fresher, EXPERIENCE_SKIP):
        return "ask", ["A probability sits next to a cutoff. Ask before you draft."]
    if skill_index >= SKILL_APPLY:
        return "apply", ["The core skills show up in the resume."]
    if skill_index >= SKILL_STRETCH:
        return "stretch", ["Some skills match. The email should name the gap."]
    return "skip", ["The required skills are mostly absent from the resume."]


# ---------------------------------------------------------------------------
# Jev scoring
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Fit:
    decision: str
    reasons: list[str]
    jev_verdict: str
    skill_index: int
    skill_label: str
    bond: float
    above_fresher: float
    skill_score: float = 0.0
    note: str = ""
    pay_type: str = "not_posted"
    pay_amount: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


def questions() -> dict:
    built = {
        "skill_overlap": Score(
            instructions=(
                "How well does the resume cover the skills this posting requires? "
                "Count only skills the resume shows in a project or internship."
            ),
            criteria=SKILL_LEVELS,
        ),
        "requires_bond": Noul(
            instructions=(
                "The posting requires a service bond, a training agreement, "
                "or a fee the candidate must repay if they leave early."
            ),
        ),
        "above_fresher": Noul(
            instructions=(
                "The posting requires more than one year of full-time work, "
                "or a degree the resume does not show. "
                "Internships and course projects are not full-time years."
            ),
        ),
        "pay_type": Choice(
            instructions="How is this role paid, using only words in the posting?",
            criteria={
                "stipend": "A monthly stipend or internship allowance, not a full salary",
                "salaried": "A salary, CTC, or annual pay",
                "not_posted": "The posting does not state pay",
            },
        ),
        "verdict": Choice(
            instructions="If this candidate applied, which bucket fits the posting?",
            criteria={
                "apply": "Core skills match and nothing in the posting blocks a fresher.",
                "stretch": "Related skills match, but a real gap remains.",
                "skip": "A hard mismatch: missing degree, years of experience, or a bond.",
            },
        ),
    }

    # WORKSHOP: add one question, then use the answer inside decide() above.
    # Example:
    # built["onsite_far"] = Noul(
    #     instructions="The role is onsite outside Kerala and offers no relocation support.",
    # )
    return built


# Names Jev may cite. Longer names are checked first so "java" does not match inside "javascript".
SKILL_NAMES = (
    ("machine learning", "machine learning"),
    ("javascript", "JavaScript"),
    ("typescript", "TypeScript"),
    ("fastapi", "FastAPI"),
    ("django", "Django"),
    ("kotlin", "Kotlin"),
    ("android", "Android"),
    ("python", "Python"),
    ("react", "React"),
    ("java", "Java"),
    ("sql", "SQL"),
    ("node", "Node"),
    ("golang", "Go"),
)


def _skills_in(text: str) -> dict[str, str]:
    lowered = text.lower()
    found = {"none": "none"}
    for key, label in SKILL_NAMES:
        if re.search(rf"(?<![a-z]){re.escape(key)}(?![a-z])", lowered):
            found[key.replace(" ", "_")] = label
    return found


def _skill_name(choice: str, labels: dict[str, str]) -> str:
    if choice in labels and choice != "none":
        return labels[choice]
    for key, label in labels.items():
        if key != "none" and choice == label:
            return label
    return ""


def _note(shown: str, missing: str, labels: dict[str, str]) -> str:
    shown_name = _skill_name(shown, labels)
    missing_name = _skill_name(missing, labels)
    if not shown_name and not missing_name:
        return "No listed skill in this posting lines up with the resume."
    parts = []
    if shown_name:
        parts.append(f"The resume shows {shown_name}, which this role asks for.")
    else:
        parts.append("The resume does not show a listed skill this role asks for.")
    if missing_name and missing_name != shown_name:
        parts.append(f"It also asks for {missing_name}, which the resume does not show.")
    return " ".join(parts)


def _level(answer: object, labels: list[str]) -> tuple[int, str]:
    """Read a score answer as an index into labels.

    The SDK returns a float expected value, often a whole number like 1.0.
    """
    raw = getattr(answer, "score")
    if isinstance(raw, str):
        text = raw.strip()
        if text in labels:
            return labels.index(text), text
        try:
            raw = float(text)
        except ValueError:
            raw = text
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        index = int(round(float(raw)))
        if 0 <= index < len(labels):
            return index, labels[index]
        raw = index
    raise SystemExit(
        f"Jev returned skill score {raw!r}. Expected a number or one of: {labels}"
    )


def score_fit(resume: str, posting: Posting, settings: Settings, want: str = "") -> Fit:
    state = {
        "resume": resume[:2500],
        "posting": posting.text[:3500],
    }
    if want.strip():
        state["looking_for"] = want.strip()[:400]
    skill_labels = _skills_in(posting.text)
    asked = questions()
    asked["shown_skill"] = Choice(
        instructions=(
            "Which of these skills does the resume show in a project or internship "
            "and the posting also requires? Choose none if the resume does not show one."
        ),
        criteria=skill_labels,
    )
    asked["missing_skill"] = Choice(
        instructions=(
            "Which of these skills does the posting require that the resume does not "
            "show in a project or internship? Choose none if you cannot name one."
        ),
        criteria=skill_labels,
    )
    with TypeSafeClient(
        api_key=settings.futurex_api_key,
        base_url=settings.jev_base_url,
        model=settings.jev_model,
    ) as client:
        result = client.system_one(
            state=state,
            questions=asked,
        )

    raw_skill = result.scores["skill_overlap"].score
    skill_index, skill_label = _level(result.scores["skill_overlap"], SKILL_LEVELS)
    try:
        skill_score = float(raw_skill)
    except (TypeError, ValueError):
        skill_score = float(skill_index)
    bond = float(result.nouls["requires_bond"].noul)
    above_fresher = float(result.nouls["above_fresher"].noul)
    jev_verdict = str(result.choices["verdict"].choice)
    pay_type = str(result.choices["pay_type"].choice)
    shown = str(result.choices["shown_skill"].choice)
    missing = str(result.choices["missing_skill"].choice)
    note = _note(shown, missing, skill_labels)
    usage = getattr(result, "usage", None)
    raw_tokens = getattr(usage, "input_tokens", None)
    out_tokens = getattr(usage, "output_tokens", None)
    if raw_tokens is None and isinstance(usage, dict):
        raw_tokens = usage.get("input_tokens", 0)
        out_tokens = usage.get("output_tokens", 0)
    input_tokens = int(raw_tokens or 0)
    output_tokens = int(out_tokens or 0)
    decision, reasons = decide(skill_index, bond, above_fresher)

    if jev_verdict != decision:
        reasons.append(f"Jev's own bucket was '{jev_verdict}'. The code gate kept '{decision}'.")

    return Fit(
        decision=decision,
        reasons=reasons,
        jev_verdict=jev_verdict,
        skill_index=skill_index,
        skill_label=skill_label,
        skill_score=skill_score,
        note=note,
        bond=bond,
        above_fresher=above_fresher,
        pay_type=pay_type,
        pay_amount=pay_amount(posting.text),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
