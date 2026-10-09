"""Ask Jev typed questions. The decision itself lives in gate.py."""

from dataclasses import dataclass

from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

from placement.gate import SKILL_LEVELS, decide
from placement.scrape import Posting
from placement.settings import Settings


@dataclass(frozen=True)
class Fit:
    decision: str
    reasons: list[str]
    jev_verdict: str
    skill_index: int
    skill_label: str
    bond: float
    above_fresher: float

    def report(self) -> str:
        bar = "█" * (self.skill_index + 1) + "░" * (len(SKILL_LEVELS) - self.skill_index - 1)
        lines = [
            f"Code decision : {self.decision}",
            f"Jev verdict   : {self.jev_verdict}",
            f"Skill overlap : {bar}  {self.skill_index}/4  {self.skill_label}",
            f"Bond likely   : {self.bond:.0%}",
            f"Above fresher : {self.above_fresher:.0%}",
            "Why:",
            *[f"  - {reason}" for reason in self.reasons],
        ]
        return "\n".join(lines)


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
        "verdict": Choice(
            instructions="If this candidate applied, which bucket fits the posting?",
            criteria={
                "apply": "Core skills match and nothing in the posting blocks a fresher.",
                "stretch": "Related skills match, but a real gap remains.",
                "skip": "A hard mismatch: missing degree, years of experience, or a bond.",
            },
        ),
    }

    # WORKSHOP: add one question, then use the answer inside decide() in gate.py.
    # Example:
    # built["onsite_far"] = Noul(
    #     instructions="The role is onsite outside Kerala and offers no relocation support.",
    # )
    return built


def _level(answer: object, labels: list[str]) -> tuple[int, str]:
    """Read a score answer as an index into labels.

    Some SDK builds return the index, others return the label text.
    """
    raw = getattr(answer, "score")
    if isinstance(raw, int) and 0 <= raw < len(labels):
        return raw, labels[raw]
    text = str(raw).strip()
    if text.isdigit():
        index = int(text)
        if 0 <= index < len(labels):
            return index, labels[index]
    if text in labels:
        return labels.index(text), text
    raise SystemExit(
        f"Jev returned skill score {raw!r}. Expected an index or one of: {labels}"
    )


def score_fit(resume: str, posting: Posting, settings: Settings) -> Fit:
    with TypeSafeClient(
        api_key=settings.futurex_api_key,
        base_url=settings.jev_base_url,
        model=settings.jev_model,
    ) as client:
        result = client.system_one(
            state={"resume": resume, "posting": posting.text},
            questions=questions(),
        )

    skill_index, skill_label = _level(result.scores["skill_overlap"], SKILL_LEVELS)
    bond = float(result.nouls["requires_bond"].noul)
    above_fresher = float(result.nouls["above_fresher"].noul)
    jev_verdict = str(result.choices["verdict"].choice)
    decision, reasons = decide(skill_index, bond, above_fresher)

    if jev_verdict != decision:
        reasons.append(f"Jev's own bucket was '{jev_verdict}'. The code gate kept '{decision}'.")

    return Fit(
        decision=decision,
        reasons=reasons,
        jev_verdict=jev_verdict,
        skill_index=skill_index,
        skill_label=skill_label,
        bond=bond,
        above_fresher=above_fresher,
    )
