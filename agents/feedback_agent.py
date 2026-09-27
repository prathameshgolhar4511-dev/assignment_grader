"""
feedback_agent.py
Turns raw grading output into personalized, human-readable feedback using
an LLM (or the offline mock — see utils.call_llm).
"""

from utils import call_llm


class FeedbackAgent:
    name = "FeedbackAgent"
    SYSTEM_PROMPT = (
        "You are an experienced, encouraging teaching assistant writing "
        "feedback for a student's assignment submission. Be specific, "
        "reference the actual failing tests or errors given to you, keep "
        "it under 120 words, and end with one concrete, actionable tip."
    )

    def generate(self, student_id: str, grading_result: dict) -> str:
        if grading_result["type"] == "code":
            failing = [r for r in grading_result["test_results"] if not r["passed"]]
            details = "\n".join(
                f"- Test {r['test']}: expected `{r['expected']}`, got `{r['actual']}`"
                for r in failing[:5]
            ) or "All test cases passed."
            prompt = (
                f"Student {student_id} scored {grading_result['score_pct']}% "
                f"({grading_result['tests_passed']}/{grading_result['tests_total']} tests passed).\n"
                f"Failing cases:\n{details}\n"
                f"Static check notes: {grading_result['static_checks']}\n"
                "Write feedback for this student."
            )
        else:
            prompt = (
                f"Student {student_id} answer correct: {grading_result['correct_final_answer']}, "
                f"shows work: {grading_result['shows_work']}, "
                f"score: {grading_result['score_pct']}%.\n"
                "Write feedback for this student's math submission."
            )

        return call_llm(self.SYSTEM_PROMPT, prompt)
