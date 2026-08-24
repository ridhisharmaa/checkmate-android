"""Stage: resolve 'Attempt any N of M' choice groups and compute totals.

Resolution happens AFTER grading, not before: every attempted unit in a choice
group gets graded, then only the best-N-by-score count toward the total (the
"best N of M" exam convention, not "first N attempted"). Everything else stays
in the response marked counted_toward_total=False rather than being discarded.
"""
from collections import defaultdict

from app.schemas.document import TeacherDocument
from app.schemas.grading import OverviewSummary, QuestionGradeResult, SubmissionResult

_GRADE_BANDS = [
    (90, "A+"), (80, "A"), (70, "B"), (60, "C"), (50, "D"), (0, "F"),
]


def grade_letter(pct: float) -> str:
    for threshold, letter in _GRADE_BANDS:
        if pct >= threshold:
            return letter
    return "F"


def aggregate(
    teacher_doc: TeacherDocument,
    results: list[QuestionGradeResult],
    overview: OverviewSummary,
    handwriting_confidence: float,
) -> SubmissionResult:
    # QuestionGradeResult doesn't carry section_id directly (only path[0] = section title),
    # so group by the section title recorded in path — stable since it's set once at flatten time.
    by_section: dict[str, list[QuestionGradeResult]] = defaultdict(list)
    title_to_rule = {s.title: s.selection_rule for s in teacher_doc.sections}
    for r in results:
        section_title = r.path[0] if r.path else ""
        by_section[section_title].append(r)

    for section_title, section_results in by_section.items():
        rule = title_to_rule.get(section_title)
        if rule is None or rule.type != "attempt_n_of_m":
            continue

        # Exactly `rule.n` units count, no more and no fewer — the section is out of
        # n questions' worth of marks regardless of how many the student attempted.
        # Best-n-by-score of the attempted ones count first; if the student attempted
        # fewer than n, unattempted units (in document order) pad the denominator out
        # to n so the skipped questions cost marks. Everything beyond n is excluded
        # from BOTH total_score and max_score — leaving unattempted extras counted is
        # what previously scored a perfect "attempt any 2 of 4" paper as 20/40.
        attempted = sorted(
            (r for r in section_results if r.attempted), key=lambda r: r.final_score, reverse=True
        )
        unattempted = [r for r in section_results if not r.attempted]
        keep_ids = {r.unit_id for r in (attempted + unattempted)[: rule.n]}
        for r in section_results:
            r.counted_toward_total = r.unit_id in keep_ids

    counted = [r for r in results if r.counted_toward_total]
    total_score = round(sum(r.final_score for r in counted), 2)
    max_score = round(sum(r.max_marks for r in counted), 2)
    pct = (total_score / max_score * 100) if max_score > 0 else 0.0

    return SubmissionResult(
        overview=overview,
        handwriting_confidence=handwriting_confidence,
        results=results,
        total_score=total_score,
        max_score=max_score,
        grade_letter=grade_letter(pct),
    )
