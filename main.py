"""
main.py
Command-line entry point.

Usage:
    python main.py code    # grade sample programming submissions
    python main.py math    # grade sample math submissions
    python main.py all     # run both (default)

Writes a full JSON report to report_<type>.json and prints a human-readable
summary to stdout. Set the GROQ_API_KEY env var to get real LLM-written
feedback instead of the offline mock text.
"""

import sys
import os
import json
import glob

from orchestrator import GradingOrchestrator
from agents.coordinator_agent import CoordinatorAgent
from utils import pretty

BASE = os.path.dirname(os.path.abspath(__file__))


def load_code_submissions():
    submissions = {}
    for path in sorted(glob.glob(os.path.join(BASE, "sample_submissions/code/*.py"))):
        sid = os.path.splitext(os.path.basename(path))[0]
        with open(path) as f:
            submissions[sid] = f.read()
    return submissions


def load_math_submissions():
    with open(os.path.join(BASE, "sample_submissions/math/submissions.json")) as f:
        return json.load(f)


def print_summary(report: dict):
    print(f"\n=== {report['assignment_type'].upper()} ASSIGNMENT REPORT ===\n")
    for sid, data in report["students"].items():
        g = data["grading"]
        print(f"--- {sid} ---")
        print(f"Score: {g['score_pct']}%")
        print(f"Feedback:\n{data['feedback']}\n")
        print(f"Improvement:\n{data['improvement']['narrative']}\n")

    print("--- Plagiarism flags (sorted by similarity) ---")
    for flag in report["plagiarism_flags"]:
        marker = "⚠️  FLAGGED" if flag["flagged"] else "ok"
        print(f"{flag['pair'][0]} vs {flag['pair'][1]}: similarity={flag['similarity']}  [{marker}]")
    print()


def run_code():
    with open(os.path.join(BASE, "assignments/code_assignment.json")) as f:
        config = json.load(f)

    orch = GradingOrchestrator()
    report = orch.run_code_assignment(load_code_submissions(), config["test_cases"])
    print_summary(report)

    out_path = os.path.join(BASE, "report_code.json")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(pretty(report))
    print(f"Full JSON report written to {out_path}")
    return report


def run_math():
    with open(os.path.join(BASE, "assignments/math_assignment.json")) as f:
        config = json.load(f)

    orch = GradingOrchestrator()
    report = orch.run_math_assignment(load_math_submissions(), config["expected_answer"])
    print_summary(report)

    out_path = os.path.join(BASE, "report_math.json")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(pretty(report))
    print(f"Full JSON report written to {out_path}")
    return report


def run_agentic(assignment_type: str):
    """
    Demonstrates the tool-calling Coordinator agent: for each student in
    the batch, spins up a CoordinatorAgent and lets it (autonomously, if
    GROQ_API_KEY is set) decide which specialist-agent tools to call.
    Prints the full tool-call trace so the decision sequence is visible.
    """
    if assignment_type == "code":
        with open(os.path.join(BASE, "assignments/code_assignment.json")) as f:
            config = json.load(f)
        submissions = load_code_submissions()
    else:
        with open(os.path.join(BASE, "assignments/math_assignment.json")) as f:
            config = json.load(f)
        submissions = load_math_submissions()

    coordinator = CoordinatorAgent(assignment_type, submissions, config)
    all_results = {}

    for sid in submissions:
        print(f"\n=== Coordinator agent run for {sid} ===")
        result = coordinator.run(sid)
        all_results[sid] = result

        print("Tool call trace:")
        for step in result["tool_trace"]:
            print(f"  [{step['mode']}] {step['tool']}({step['input']})")
        print(f"Agent's closing message: {result['agent_message']}")
        print(f"Final score: {result['report'].get('score_pct')}%")

    out_path = os.path.join(BASE, f"report_agentic_{assignment_type}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(pretty(all_results))
    print(f"\nFull agentic report + tool traces written to {out_path}")
    return all_results


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode == "code":
        run_code()
    elif mode == "math":
        run_math()
    elif mode == "agentic-code":
        run_agentic("code")
    elif mode == "agentic-math":
        run_agentic("math")
    else:
        run_code()
        run_math()
