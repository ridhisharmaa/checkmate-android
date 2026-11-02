"""Banded marking: every question ends up with full marks, half marks or zero.

The combined score (similarity + LLM rubric score + diagram/table/code bonus) is a
percentage between 0 and 100. It is turned into marks per question, not for the whole
paper:

    70% or more      -> full marks
    35% to under 70% -> half marks
    under 35%        -> zero

Half marks are rounded half up to a whole mark (5 marks -> 3, 7 marks -> 4), so a
question never gets a fractional award from the band. Teacher overrides use the same
half-marks rule, so an override and a band always give the same number.
"""
import math

FULL_MARKS_FROM_PCT = 70.0
HALF_MARKS_FROM_PCT = 35.0


def half_marks(max_marks: float) -> float:
    """Half of max_marks, rounded half up to a whole mark."""
    return float(math.floor(max_marks * 0.5 + 0.5))


def banded_marks(max_marks: float, score_pct: float) -> float:
    if score_pct >= FULL_MARKS_FROM_PCT:
        return max_marks
    if score_pct >= HALF_MARKS_FROM_PCT:
        return half_marks(max_marks)
    return 0.0
