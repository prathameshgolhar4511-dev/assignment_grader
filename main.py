"""
main.py
Command-line entry point.

Usage:
    python main.py code          # fixed pipeline: code assignment
    python main.py math          # fixed pipeline: math assignment
    python main.py all           # fixed pipeline: both (default)
    python main.py agentic-code  # tool-calling CoordinatorAgent: code
    python main.py agentic-math  # tool-calling CoordinatorAgent: math

Outputs per run:
  - Terminal summary
  - report_<type>.json          raw pipeline report
  - report_<type>_prescribed.json   prescribed report format
  - report_<type>_prescribed.md     prescribed report as Markdown

Set GROQ_API_KEY (free at https://console.groq.com) for real LLM responses.
Without it the system runs fully in mock mode — all agents work, feedback
is placeholder text.
"""

import sys
import os
import json
import glob

from orchestrator import GradingOrchestrator
from agents.coordinator_agent import CoordinatorAgent
from utils import pretty
from report_formatter import build_report, to_markdown

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
    print(f"\n{'='*60}")
    print(f"  {report['assignment_type'].upper()} ASSIGNMENT REPORT")
    print(f"{'='*60}\n")
    for sid, data in report["students"].items():
        g = data["grading"]
        print(f"[ {sid} ]")
        print(f"  Score          : {g['score_pct']}%")
        print(f"  Feedback       :\n    {data['feedback'].strip()}\n")
        print(f"  Improvement    :\n    {data['improvement']['narrative'].strip()}\n")

    print("Plagiarism flags (sorted by similarity):")
    for flag in report["plagiarism_flags"]:
        marker = "⚠️  FLAGGED" if flag["flagged"] else "ok"
        print(f"  {flag['pair'][0]} vs {flag['pair'][1]}: "
              f"similarity={flag['similarity']}  [{marker}]")
    print()


def _write_prescribed(raw_report: dict, assignment_title: str, slug: str):
    """Build and write the prescribed format JSON + Markdown reports."""
    prescribed = build_report(raw_report, assignment_title)

    json_path = os.path.join(BASE, f"report_{slug}_prescribed.json")
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(pretty(prescribed))
    print(f"Prescribed JSON report  → {json_path}")

    md_path = os.path.join(BASE, f"report_{slug}_prescribed.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(to_markdown(prescribed))
    print(f"Prescribed MD report    → {md_path}")


def run_code():
    with open(os.path.join(BASE, "assignments/code_assignment.json")) as f:
        config = json.load(f)

    orch = GradingOrchestrator()
    report = orch.run_code_assignment(load_code_submissions(), config["test_cases"])
    print_summary(report)

    raw_path = os.path.join(BASE, "report_code.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(pretty(report))
    print(f"Raw JSON report         → {raw_path}")

    _write_prescribed(report, config["title"], "code")
    return report


def run_math():
    with open(os.path.join(BASE, "assignments/math_assignment.json")) as f:
        config = json.load(f)

    orch = GradingOrchestrator()
    report = orch.run_math_assignment(load_math_submissions(), config["expected_answer"])
    print_summary(report)

    raw_path = os.path.join(BASE, "report_math.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(pretty(report))
    print(f"Raw JSON report         → {raw_path}")

    _write_prescribed(report, config["title"], "math")
    return report


def run_agentic(assignment_type: str):
    """
    Demonstrates the tool-calling CoordinatorAgent: for each student the
    Groq LLM autonomously decides which specialist-agent tools to call and
    in what order. Prints the full tool-call trace so the orchestration
    decisions are visible (requirement #4).
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
        print(f"\n{'='*60}")
        print(f"  CoordinatorAgent run for: {sid}")
        print(f"{'='*60}")
        result = coordinator.run(sid)
        all_results[sid] = result

        print("Tool-call trace:")
        for step in result["tool_trace"]:
            print(f"  [{step['mode']}] → {step['tool']}({json.dumps(step['input'])})")
        print(f"Agent message : {result['agent_message']}")
        print(f"Final score   : {result['report'].get('score_pct')}%")

    out_path = os.path.join(BASE, f"report_agentic_{assignment_type}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(pretty(all_results))
    print(f"\nAgentic report + tool traces → {out_path}")
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
