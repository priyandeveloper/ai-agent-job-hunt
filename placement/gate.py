"""The policy. No network, no model.

Jev supplies numbers. This file decides apply, stretch, or skip.
"""

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


def decide(skill_index: int, bond: float, above_fresher: float) -> tuple[str, list[str]]:
    """Turn three numbers into apply, stretch, or skip."""
    if bond >= BOND_SKIP:
        return "skip", [f"Bond language is likely ({bond:.0%})."]
    if above_fresher >= EXPERIENCE_SKIP:
        return "skip", [f"The experience bar is above a fresher ({above_fresher:.0%})."]
    if skill_index >= SKILL_APPLY:
        return "apply", ["The core skills show up in the resume."]
    if skill_index >= SKILL_STRETCH:
        return "stretch", ["Some skills match. The draft should name the gap."]
    return "skip", ["The required skills are mostly absent from the resume."]
