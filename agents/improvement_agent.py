"""
improvement_agent.py
Looks at a student's grading history/result and suggests concrete topics
to revisit, combining a rule-based topic map with an LLM-polished summary.
"""

from utils import call_llm

TOPIC_HINTS = {
    "timeout": "Efficiency / algorithm complexity (your solution may be too slow for large inputs).",
    "bare_except": "Exception handling — avoid bare `except:`; catch specific exceptions.",
    "no_function": "Code organization — break logic into functions for clarity and reuse.",
    "low_score_math": "Revisit the core formula/derivation for this topic before the next assignment.",
}


class ImprovementAgent:
    name = "ImprovementAgent"
    SYSTEM_PROMPT = (
        "You are an academic advisor. Given a short list of weak areas for "
        "a student, produce a tight, encouraging list of 2-4 improvement "
        "actions (bullet points), no more than 80 words total."
    )

    def suggest(self, student_id: str, grading_result: dict) -> dict:
        weak_points = []

        if grading_result["type"] == "code":
            if any(r.get("actual") == "TIMEOUT" for r in grading_result["test_results"]):
                weak_points.append(TOPIC_HINTS["timeout"])
            if grading_result["static_checks"].get("uses_bare_except"):
                weak_points.append(TOPIC_HINTS["bare_except"])
            if not grading_result["static_checks"].get("has_function_def"):
                weak_points.append(TOPIC_HINTS["no_function"])
        else:
            if grading_result["score_pct"] < 60:
                weak_points.append(TOPIC_HINTS["low_score_math"])

        if not weak_points:
            weak_points.append("No major weak areas detected — keep it up.")

        prompt = f"Student {student_id} weak areas:\n" + "\n".join(f"- {w}" for w in weak_points)
        narrative = call_llm(self.SYSTEM_PROMPT, prompt)

        return {"weak_points": weak_points, "narrative": narrative}
