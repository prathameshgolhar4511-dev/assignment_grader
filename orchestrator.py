"""
orchestrator.py
Coordinates the four agents into a single pipeline:

  1. GradingAgent      -> objective score per submission
  2. PlagiarismAgent   -> batch-wide similarity flags
  3. FeedbackAgent     -> personalized feedback text per submission
  4. ImprovementAgent  -> improvement suggestions per submission

Works for two assignment types: "code" and "math". Produces one combined
report (dict, JSON-serializable) covering the whole batch.
"""

from agents.grading_agent import GradingAgent
from agents.plagiarism_agent import PlagiarismAgent
from agents.feedback_agent import FeedbackAgent
from agents.improvement_agent import ImprovementAgent


class GradingOrchestrator:
    def __init__(self):
        self.grader = GradingAgent()
        self.plagiarism = PlagiarismAgent()
        self.feedback = FeedbackAgent()
        self.improver = ImprovementAgent()

    def run_code_assignment(self, submissions: dict, test_cases: list) -> dict:
        """submissions: {student_id: code_str}"""
        report = {"assignment_type": "code", "students": {}}

        for sid, code in submissions.items():
            grading = self.grader.grade_code(code, test_cases)
            report["students"][sid] = {
                "grading": grading,
                "feedback": self.feedback.generate(sid, grading),
                "improvement": self.improver.suggest(sid, grading),
            }

        report["plagiarism_flags"] = self.plagiarism.compare_code_batch(submissions)
        return report

    def run_math_assignment(self, submissions: dict, expected_answer: str) -> dict:
        """submissions: {student_id: {"answer": str, "work": str}}"""
        report = {"assignment_type": "math", "students": {}}

        for sid, sub in submissions.items():
            grading = self.grader.grade_math(sub["answer"], expected_answer, sub.get("work", ""))
            report["students"][sid] = {
                "grading": grading,
                "feedback": self.feedback.generate(sid, grading),
                "improvement": self.improver.suggest(sid, grading),
            }

        work_texts = {sid: sub.get("work", "") for sid, sub in submissions.items()}
        report["plagiarism_flags"] = self.plagiarism.compare_text_batch(work_texts)
        return report
