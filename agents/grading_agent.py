"""
grading_agent.py
Agent responsible for objective, deterministic grading:
  - Programming submissions: executes the student's code against a set of
    test cases (subprocess sandboxed, timeout-bounded) and scores by
    percentage of tests passed. Also runs light static checks.
  - Math submissions: parses the student's final answer and compares it
    symbolically (via sympy) to the expected answer, tolerant of
    equivalent forms (e.g. 1/2 == 0.5 == 2/4).
"""

import subprocess
import sys
import tempfile
import os
import re

try:
    import sympy
    from sympy.parsing.sympy_parser import parse_expr
    HAVE_SYMPY = True
except ImportError:
    HAVE_SYMPY = False


class GradingAgent:
    name = "GradingAgent"

    # ---------------- Programming ----------------
    def grade_code(self, code_str: str, test_cases: list, timeout: float = 5.0) -> dict:
        """
        test_cases: list of dicts like {"input": "3 4\n", "expected": "7\n"}
        Runs the submitted script once per test case, feeding stdin and
        comparing stdout (whitespace-normalized).
        """
        results = []
        passed = 0

        with tempfile.TemporaryDirectory() as tmp:
            script_path = os.path.join(tmp, "submission.py")
            with open(script_path, "w") as f:
                f.write(code_str)

            for i, case in enumerate(test_cases):
                try:
                    proc = subprocess.run(
                        [sys.executable, script_path],
                        input=case.get("input", ""),
                        capture_output=True,
                        text=True,
                        timeout=timeout,
                    )
                    actual = proc.stdout.strip()
                    expected = case["expected"].strip()
                    ok = actual == expected and proc.returncode == 0
                    results.append({
                        "test": i + 1,
                        "passed": ok,
                        "expected": expected,
                        "actual": actual if not proc.stderr else f"ERROR: {proc.stderr.strip()[:300]}",
                    })
                    if ok:
                        passed += 1
                except subprocess.TimeoutExpired:
                    results.append({"test": i + 1, "passed": False, "expected": case["expected"].strip(),
                                     "actual": "TIMEOUT"})

        total = len(test_cases) or 1
        score_pct = round(100 * passed / total, 1)

        static = self._static_checks(code_str)

        return {
            "type": "code",
            "tests_passed": passed,
            "tests_total": total,
            "score_pct": score_pct,
            "test_results": results,
            "static_checks": static,
        }

    def _static_checks(self, code_str: str) -> dict:
        """Cheap heuristics — not a substitute for real static analysis,
        but useful signal for the feedback agent."""
        return {
            "has_function_def": bool(re.search(r"^\s*def\s+\w+\(", code_str, re.M)),
            "has_docstring_or_comments": ("\"\"\"" in code_str or "'''" in code_str or "#" in code_str),
            "line_count": len(code_str.strip().splitlines()),
            "uses_bare_except": bool(re.search(r"except\s*:", code_str)),
        }

    # ---------------- Math ----------------
    def grade_math(self, student_answer: str, expected_answer: str, partial_work: str = "") -> dict:
        """
        Compares a final answer symbolically. Falls back to string/number
        comparison if sympy isn't available or parsing fails.
        """
        correct = False
        method = "string_match"

        if HAVE_SYMPY:
            try:
                s_expr = parse_expr(student_answer.replace("^", "**"))
                e_expr = parse_expr(expected_answer.replace("^", "**"))
                correct = sympy.simplify(s_expr - e_expr) == 0
                method = "symbolic_equivalence"
            except Exception:
                correct = student_answer.strip() == expected_answer.strip()
        else:
            correct = student_answer.strip() == expected_answer.strip()

        shows_work = len(partial_work.strip()) > 10
        score_pct = 100.0 if correct else (30.0 if shows_work else 0.0)

        return {
            "type": "math",
            "correct_final_answer": correct,
            "comparison_method": method,
            "shows_work": shows_work,
            "score_pct": score_pct,
        }
