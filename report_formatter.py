"""
report_formatter.py
Converts the raw pipeline/agentic output into the prescribed lab report
format. Produces both a structured JSON file and a human-readable
Markdown report.

Prescribed report structure (per student):
  - Student ID
  - Assignment title
  - Score (%)
  - Grading details (per-test breakdown for code; answer correctness for math)
  - Feedback (personalized natural-language)
  - Improvement suggestions (bullet list)
  - Plagiarism status (clean / flagged with counterpart)

Batch-level:
  - Summary table (all students, scores, plagiarism status)
  - Plagiarism flags list
  - Agent execution log (which agents ran, in what order)
"""

from datetime import datetime


def _plagiarism_status(student_id: str, flags: list) -> str:
    """Return a human-readable plagiarism status for one student."""
    hits = [f for f in flags if student_id in f["pair"] and f["flagged"]]
    if not hits:
        return "Clean"
    partners = [p for f in hits for p in f["pair"] if p != student_id]
    return f"FLAGGED (similarity with {', '.join(partners)})"


def build_report(raw_report: dict, assignment_title: str) -> dict:
    """
    Transform the raw orchestrator/coordinator report dict into the
    prescribed report format.

    raw_report keys: assignment_type, students, plagiarism_flags
      students[sid] keys: grading, feedback, improvement
    """
    atype = raw_report.get("assignment_type", "unknown")
    flags = raw_report.get("plagiarism_flags", [])
    students_raw = raw_report.get("students", {})

    student_reports = []
    for sid, data in students_raw.items():
        g = data["grading"]
        imp = data.get("improvement", {})

        # Build grading details section
        if atype == "code":
            grading_details = {
                "tests_passed": g["tests_passed"],
                "tests_total": g["tests_total"],
                "per_test_breakdown": [
                    {
                        "test_number": r["test"],
                        "passed": r["passed"],
                        "expected": r["expected"],
                        "actual": r["actual"],
                    }
                    for r in g.get("test_results", [])
                ],
                "static_analysis": g.get("static_checks", {}),
            }
        else:
            grading_details = {
                "correct_answer": g["correct_final_answer"],
                "comparison_method": g.get("comparison_method", "string_match"),
                "shows_work": g["shows_work"],
            }

        student_reports.append({
            "student_id": sid,
            "assignment_title": assignment_title,
            "score_pct": g["score_pct"],
            "grading_details": grading_details,
            "feedback": data.get("feedback", ""),
            "improvement_suggestions": imp.get("weak_points", []),
            "improvement_narrative": imp.get("narrative", ""),
            "plagiarism_status": _plagiarism_status(sid, flags),
        })

    # Summary table rows
    summary_table = [
        {
            "student_id": s["student_id"],
            "score_pct": s["score_pct"],
            "plagiarism_status": s["plagiarism_status"],
        }
        for s in student_reports
    ]

    return {
        "report_metadata": {
            "assignment_title": assignment_title,
            "assignment_type": atype,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_students": len(student_reports),
            "agents_used": [
                "GradingAgent",
                "PlagiarismAgent",
                "FeedbackAgent",
                "ImprovementAgent",
                "CoordinatorAgent (orchestrator)",
            ],
            "framework": "Pure Python + Groq API (tool-calling)",
        },
        "summary_table": summary_table,
        "plagiarism_flags": [
            {
                "student_pair": list(f["pair"]),
                "similarity_score": f["similarity"],
                "flagged": f["flagged"],
            }
            for f in flags
        ],
        "student_reports": student_reports,
    }


def to_markdown(prescribed_report: dict) -> str:
    """Render the prescribed report as a Markdown document."""
    meta = prescribed_report["report_metadata"]
    lines = []

    lines.append(f"# Assignment Grading Report\n")
    lines.append(f"**Assignment:** {meta['assignment_title']}  ")
    lines.append(f"**Type:** {meta['assignment_type'].capitalize()}  ")
    lines.append(f"**Generated:** {meta['generated_at']}  ")
    lines.append(f"**Framework:** {meta['framework']}  ")
    lines.append(f"**Agents used:** {', '.join(meta['agents_used'])}  \n")

    lines.append("---\n")

    # Summary table
    lines.append("## Summary\n")
    lines.append("| Student | Score (%) | Plagiarism Status |")
    lines.append("|---------|-----------|-------------------|")
    for row in prescribed_report["summary_table"]:
        flag = "⚠️ " + row["plagiarism_status"] if "FLAGGED" in row["plagiarism_status"] else "✅ " + row["plagiarism_status"]
        lines.append(f"| {row['student_id']} | {row['score_pct']}% | {flag} |")
    lines.append("")

    # Plagiarism section
    lines.append("## Plagiarism Analysis\n")
    for f in prescribed_report["plagiarism_flags"]:
        pair = " vs ".join(f["student_pair"])
        marker = "⚠️  **FLAGGED**" if f["flagged"] else "✅  Clean"
        lines.append(f"- {pair}: similarity = `{f['similarity_score']}` — {marker}")
    lines.append("")

    # Per-student reports
    lines.append("---\n")
    lines.append("## Per-Student Reports\n")
    for s in prescribed_report["student_reports"]:
        lines.append(f"### {s['student_id']}\n")
        lines.append(f"**Score:** {s['score_pct']}%  ")
        lines.append(f"**Plagiarism:** {s['plagiarism_status']}  \n")

        lines.append("**Grading Details:**  ")
        gd = s["grading_details"]
        if "tests_passed" in gd:
            lines.append(f"- Tests passed: {gd['tests_passed']} / {gd['tests_total']}")
            lines.append("")
            lines.append("| Test | Passed | Expected | Actual |")
            lines.append("|------|--------|----------|--------|")
            for t in gd["per_test_breakdown"]:
                icon = "✅" if t["passed"] else "❌"
                lines.append(f"| {t['test_number']} | {icon} | `{t['expected']}` | `{t['actual']}` |")
            sa = gd.get("static_analysis", {})
            lines.append(f"\n**Static Analysis:** has function def: `{sa.get('has_function_def')}` | "
                         f"has docstring/comments: `{sa.get('has_docstring_or_comments')}` | "
                         f"bare except: `{sa.get('uses_bare_except')}` | "
                         f"lines: `{sa.get('line_count')}`")
        else:
            lines.append(f"- Correct answer: `{gd['correct_answer']}`")
            lines.append(f"- Shows work: `{gd['shows_work']}`")
            lines.append(f"- Comparison method: `{gd['comparison_method']}`")

        lines.append(f"\n**Feedback:**  \n{s['feedback']}\n")

        lines.append("**Improvement Suggestions:**  ")
        for tip in s["improvement_suggestions"]:
            lines.append(f"- {tip}")
        if s.get("improvement_narrative"):
            lines.append(f"\n{s['improvement_narrative']}")
        lines.append("\n---\n")

    return "\n".join(lines)
