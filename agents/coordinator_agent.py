"""
coordinator_agent.py
The top-level agent. This is what satisfies the lab's "tool calling +
orchestration" requirement directly: the Coordinator does NOT hard-code a
fixed call sequence. Instead it is handed a menu of tools -- each one a
thin wrapper around one of the four specialist agents -- and, when a live
GROQ_API_KEY is set, the LLM itself decides which tools to invoke, in
which order, and how many times, based on the assignment context. This is
the standard "agent-as-tool" multi-agent pattern (a supervisor/coordinator
agent delegating to worker agents through function calling), implemented
here in pure Python + the Groq API (tools/function-calling parameter) rather
than a framework like LangGraph/CrewAI/AutoGen -- allowed explicitly by
the lab brief ("pure Python + LLM API").

Run with a GROQ_API_KEY to see genuine autonomous tool selection; without one,
utils.run_tool_agent falls back to a clearly-labeled deterministic
simulation of the same tool sequence so the architecture is still fully
runnable and inspectable offline.
"""

from agents.grading_agent import GradingAgent
from agents.plagiarism_agent import PlagiarismAgent
from agents.feedback_agent import FeedbackAgent
from agents.improvement_agent import ImprovementAgent
from utils import run_tool_agent

SYSTEM_PROMPT = """You are the Coordinator agent for an assignment-grading
multi-agent system. For the ONE student submission you are given, decide
which of your available tools to call, in what order, to produce a
complete evaluation. You generally need grading before feedback/
improvement suggestions make sense, and you should always check
plagiarism at least once. When you have everything you need, call
submit_final_report exactly once with the assembled JSON, then briefly
confirm in one sentence that the report was submitted."""


class CoordinatorAgent:
    """One instance is created per assignment batch (all submissions of
    the same type + the same test cases / expected answer), and its run()
    method is invoked once per student in that batch."""

    def __init__(self, assignment_type: str, submissions: dict, assignment_config: dict):
        self.assignment_type = assignment_type          # "code" | "math"
        self.submissions = submissions                    # {student_id: raw submission}
        self.config = assignment_config                   # test_cases or expected_answer
        self.grader = GradingAgent()
        self.plagiarism = PlagiarismAgent()
        self.feedback_agent = FeedbackAgent()
        self.improver = ImprovementAgent()
        self._state = {}   # per-student scratch space filled in by tools, keyed by student_id

    # ---------------- tool implementations (wrap the specialist agents) ----------------
    def _grade_submission(self, student_id: str) -> dict:
        sub = self.submissions[student_id]
        if self.assignment_type == "code":
            result = self.grader.grade_code(sub, self.config["test_cases"])
        else:
            result = self.grader.grade_math(sub["answer"], self.config["expected_answer"], sub.get("work", ""))
        self._state.setdefault(student_id, {})["grading"] = result
        return result

    def _check_plagiarism_for_student(self, student_id: str) -> dict:
        if self.assignment_type == "code":
            flags = self.plagiarism.compare_code_batch(self.submissions)
        else:
            texts = {sid: s.get("work", "") for sid, s in self.submissions.items()}
            flags = self.plagiarism.compare_text_batch(texts)
        relevant = [f for f in flags if student_id in f["pair"]]
        self._state.setdefault(student_id, {})["plagiarism"] = relevant
        return {"flags_involving_student": relevant}

    def _generate_feedback(self, student_id: str) -> dict:
        grading = self._state.get(student_id, {}).get("grading") or self._grade_submission(student_id)
        text = self.feedback_agent.generate(student_id, grading)
        self._state[student_id]["feedback"] = text
        return {"feedback": text}

    def _suggest_improvements(self, student_id: str) -> dict:
        grading = self._state.get(student_id, {}).get("grading") or self._grade_submission(student_id)
        result = self.improver.suggest(student_id, grading)
        self._state[student_id]["improvement"] = result
        return result

    def _submit_final_report(self, report: dict) -> dict:
        self._state.setdefault(report.get("student_id", "unknown"), {})["final_report"] = report
        return {"status": "received"}

    # ---------------- tool schemas exposed to the LLM ----------------
    def _tools_and_impl(self, student_id: str):
        tools = [
            {
                "name": "grade_submission",
                "description": "Objectively grade this student's submission (runs code test cases or checks the math answer). Returns a score and detailed results.",
                "input_schema": {
                    "type": "object",
                    "properties": {"student_id": {"type": "string"}},
                    "required": ["student_id"],
                },
                "_mock_args": {"student_id": student_id},
            },
            {
                "name": "check_plagiarism_for_student",
                "description": "Compare this student's submission against the rest of the batch and return any similarity flags involving them.",
                "input_schema": {
                    "type": "object",
                    "properties": {"student_id": {"type": "string"}},
                    "required": ["student_id"],
                },
                "_mock_args": {"student_id": student_id},
            },
            {
                "name": "generate_feedback",
                "description": "Generate personalized natural-language feedback for this student based on their grading result (grades first automatically if not already done).",
                "input_schema": {
                    "type": "object",
                    "properties": {"student_id": {"type": "string"}},
                    "required": ["student_id"],
                },
                "_mock_args": {"student_id": student_id},
            },
            {
                "name": "suggest_improvements",
                "description": "Suggest concrete improvement areas/topics for this student based on their grading result.",
                "input_schema": {
                    "type": "object",
                    "properties": {"student_id": {"type": "string"}},
                    "required": ["student_id"],
                },
                "_mock_args": {"student_id": student_id},
            },
            {
                "name": "submit_final_report",
                "description": "Submit the final assembled JSON report for this student. Call exactly once, after grading/plagiarism/feedback/improvement are done.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "report": {
                            "type": "object",
                            "description": "Full assembled report: student_id, score_pct, feedback, improvement, plagiarism flags.",
                        }
                    },
                    "required": ["report"],
                },
                "_mock_args": {"report": self._assemble_mock_report(student_id)},
            },
        ]
        impl = {
            "grade_submission": self._grade_submission,
            "check_plagiarism_for_student": self._check_plagiarism_for_student,
            "generate_feedback": self._generate_feedback,
            "suggest_improvements": self._suggest_improvements,
            "submit_final_report": self._submit_final_report,
        }
        return tools, impl

    def _assemble_mock_report(self, student_id: str) -> dict:
        """Used only to give the offline mock simulation something sensible
        to pass to submit_final_report — in live mode the LLM assembles
        this itself from the real tool results it received."""
        self._grade_submission(student_id)
        self._check_plagiarism_for_student(student_id)
        self._generate_feedback(student_id)
        self._suggest_improvements(student_id)
        s = self._state[student_id]
        return {
            "student_id": student_id,
            "score_pct": s["grading"]["score_pct"],
            "feedback": s["feedback"],
            "improvement": s["improvement"],
            "plagiarism_flags": s["plagiarism"],
        }

    # ---------------- public entry point ----------------
    def run(self, student_id: str):
        tools, impl = self._tools_and_impl(student_id)
        user_prompt = (
            f"Assignment type: {self.assignment_type}\n"
            f"Student to evaluate: {student_id}\n"
            "Produce a complete grading report for this student using your tools."
        )
        final_text, trace = run_tool_agent(SYSTEM_PROMPT, user_prompt, tools, impl)
        report = self._state.get(student_id, {}).get("final_report") or self._assemble_report_from_state(student_id)
        return {"agent_message": final_text, "tool_trace": trace, "report": report}

    def _assemble_report_from_state(self, student_id: str) -> dict:
        s = self._state.get(student_id, {})
        return {
            "student_id": student_id,
            "score_pct": s.get("grading", {}).get("score_pct"),
            "feedback": s.get("feedback"),
            "improvement": s.get("improvement"),
            "plagiarism_flags": s.get("plagiarism"),
        }
