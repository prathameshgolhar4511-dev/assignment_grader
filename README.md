# Intelligent Assignment Grader & Feedback Generator

Multi-agent system that grades programming and math assignments,
generates detailed per-student feedback, flags plagiarism patterns, and
suggests improvement areas.

**Framework**: pure Python + Groq API (tool-calling), as explicitly
permitted by the lab brief.

---

## Setup & Implementation Steps

### 1. Clone / download the project

```
assignment_grader/       ← repo root (.env, .gitignore live here)
└── assignment_grader/   ← app root (main.py, requirements.txt live here)
```

### 2. Navigate to the app root

All commands must be run from the inner `assignment_grader/` folder
where `main.py` lives:

```powershell
# if you extracted the zip:
cd "assignment_grader (2)\assignment_grader\assignment_grader"

# or if you cloned the repo:
cd assignment_grader\assignment_grader
```

### 3. Create a virtual environment

```powershell
# Windows (PowerShell)
python -m venv venv
venv\Scripts\activate
```

```bash
# macOS / Linux
python -m venv venv
source venv/bin/activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure your API key

Set your Groq key — get one free at https://console.groq.com (no credit card):

```powershell
# Windows PowerShell (current session)
$env:GROQ_API_KEY="your_actual_key_here"
```

```bash
# macOS / Linux
export GROQ_API_KEY=your_actual_key_here
```

Or create a `.env` file in the app root (`assignment_grader/assignment_grader/.env`):

```
GROQ_API_KEY=your_actual_key_here
```

> Without a key the system still runs fully in **mock mode** — all agents
> work, you just get placeholder text instead of real LLM responses.

### 6. Run it

```bash
python main.py all             # fixed pipeline: code + math
python main.py code            # fixed pipeline: code only
python main.py math            # fixed pipeline: math only
python main.py agentic-code    # tool-calling Coordinator: code
python main.py agentic-math    # tool-calling Coordinator: math
```

### 6. Check the output

Each run prints a human-readable summary to the terminal and writes a
full JSON report with per-student grading, feedback, improvement
suggestions, and batch-wide plagiarism flags:

- `report_code.json`
- `report_math.json`
- `report_agentic_code.json`
- `report_agentic_math.json`

---

## Lab requirements → where each is satisfied

| # | Requirement | Where |
|---|---|---|
| 2 | Multi-agent system, ≥3 agents | 5 agents: `CoordinatorAgent` + `GradingAgent` + `PlagiarismAgent` + `FeedbackAgent` + `ImprovementAgent` |
| 3 | Any suitable framework | Pure Python + Groq LLM API (no external agent framework needed) |
| 4 | Tool calling + basic orchestration | `CoordinatorAgent` exposes the other 4 agents as callable tools via the Groq function-calling API. When `GROQ_API_KEY` is set, the LLM decides which tools to call and in what order — real tool-calling, not a hard-coded sequence. |
| 5 | Prescribed report format | Not yet applied — share the template and it can be generated. |
| 6 | GitHub + README | This README. |
| 7 | Individual work | N/A to the code itself. |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          main.py  (CLI)                             │
│              python main.py all / agentic-code / ...                │
└──────────────────────┬──────────────────────┬───────────────────────┘
                       │                      │
           Fixed pipeline mode         Agentic mode
                       │                      │
                       ▼                      ▼
        ┌──────────────────────┐   ┌─────────────────────────────────┐
        │   orchestrator.py    │   │       CoordinatorAgent          │
        │  GradingOrchestrator │   │   (agents/coordinator_agent.py) │
        │                      │   │                                 │
        │  direct Python calls │   │  Groq LLM  ◄──► tool schemas   │
        │  in fixed order      │   │  decides which tools to call,   │
        └──────┬───────────────┘   │  in what order, autonomously    │
               │                   └────────────┬────────────────────┘
               │                                │  tool calls
               │            ┌───────────────────┼───────────────────┐
               │            │                   │                   │
               ▼            ▼                   ▼                   ▼
  ┌────────────────┐ ┌─────────────┐ ┌──────────────────┐ ┌────────────────────┐
  │  GradingAgent  │ │ Plagiarism  │ │  FeedbackAgent   │ │ ImprovementAgent   │
  │                │ │   Agent     │ │                  │ │                    │
  │ • run code vs  │ │             │ │ • LLM call via   │ │ • rule-based weak  │
  │   test cases   │ │ • AST-norm  │ │   Groq API       │ │   signal detection │
  │   (subprocess) │ │   + diff    │ │ • personalized   │ │ • LLM-polished     │
  │ • sympy math   │ │   (code)    │ │   feedback text  │ │   improvement list │
  │   comparison   │ │ • TF-IDF    │ │                  │ │                    │
  │ • static checks│ │   cosine    │ └──────────────────┘ └────────────────────┘
  └────────────────┘ │   (math)    │
                     └─────────────┘

                     ┌─────────────────────────────┐
                     │          utils.py            │
                     │  call_llm()  run_tool_agent() │
                     │                             │
                     │  GROQ_API_KEY set → Groq    │
                     │  no key → mock mode         │
                     └─────────────────────────────┘

                     ┌─────────────────────────────┐
                     │         Output              │
                     │  report_code.json           │
                     │  report_math.json           │
                     │  report_agentic_code.json   │
                     │  report_agentic_math.json   │
                     └─────────────────────────────┘
```

**Layer 1 — specialist agents** (each owns one responsibility):

| Agent | File | Responsibility |
|---|---|---|
| **GradingAgent** | `agents/grading_agent.py` | Runs code against test cases (subprocess sandbox) or checks math answers symbolically (sympy). Deterministic scoring. |
| **PlagiarismAgent** | `agents/plagiarism_agent.py` | Code: normalizes AST (strips variable/function names) then diffs structure — catches copy-and-rename cheating. Math/text: TF-IDF cosine similarity over "work shown". |
| **FeedbackAgent** | `agents/feedback_agent.py` | Turns grading output into personalized natural-language feedback via an LLM call. |
| **ImprovementAgent** | `agents/improvement_agent.py` | Maps weak signals (timeouts, bare excepts, low scores, no functions) to concrete improvement topics, polished by an LLM call. |

**Layer 2 — CoordinatorAgent** (`agents/coordinator_agent.py`):
Wraps the 4 specialist agents as tools (`grade_submission`,
`check_plagiarism_for_student`, `generate_feedback`,
`suggest_improvements`, `submit_final_report`) and hands them to the
LLM via `utils.run_tool_agent()`. This is the standard
"supervisor delegates to workers through function calling" multi-agent
pattern — implemented with the raw Groq API instead of
LangGraph/CrewAI/AutoGen.

`utils.py` auto-selects the provider: `GROQ_API_KEY` set → live Groq
calls; no key → deterministic mock mode. Both paths exercise the full
agent loop, so the architecture is demoable without any credentials.

---

## Two ways to run it

1. **Fixed pipeline** (`python main.py code / math / all`) —
   `orchestrator.py` calls each agent directly in Python. Simple and
   fast for bulk grading.

2. **Agentic / tool-calling** (`python main.py agentic-code / agentic-math`) —
   The `CoordinatorAgent` runs for each student and prints the full
   **tool-call trace** (which tools were called, arguments, results) so
   the orchestration decisions are visible. This demonstrates requirement
   #4. Use with `GROQ_API_KEY` for genuine model-driven tool selection.

---

## Project layout

```
.
├── .env                        # your real keys (gitignored)
├── .env.example                # template to copy
├── .gitignore
└── assignment_grader/
    ├── main.py                 # CLI entry point
    ├── orchestrator.py         # fixed pipeline: ties 4 agents together
    ├── utils.py                # shared LLM wrapper (Groq + mock mode)
    ├── requirements.txt
    ├── agents/
    │   ├── coordinator_agent.py
    │   ├── grading_agent.py
    │   ├── plagiarism_agent.py
    │   ├── feedback_agent.py
    │   └── improvement_agent.py
    ├── assignments/
    │   ├── code_assignment.json    # test cases for the programming task
    │   └── math_assignment.json   # expected answer for the math task
    └── sample_submissions/
        ├── code/student_A.py ... student_D.py
        └── math/submissions.json
```

---

## Sample Output

These results are from the included sample batch. Run `python main.py all` to regenerate them.

### Programming Assignment — Fibonacci (memoized)

| Student | Score | Key finding |
|---|---|---|
| student_A | 100% | All 8 tests passed. Has docstring + memoization. Minor: could use `functools.lru_cache`. |
| student_B | 100% | All 8 tests passed. **Plagiarism flagged** — AST similarity 1.0 vs student_A (copy with renamed variables). |
| student_C | 100% | All 8 tests passed. Correct iterative approach. No docstring → improvement suggestion triggered. |
| student_D | 0% | Naive recursion TIMEOUTs on n=35 and n=50. Passes small cases only. Efficiency improvement flagged. |

Plagiarism flags (code batch):

```
student_A vs student_B: similarity=1.000  [FLAGGED]
student_C vs student_D: similarity=0.275  [ok]
student_A vs student_D: similarity=0.189  [ok]
```

Sample feedback — student_D:
> Your solution returns correct results for small inputs but times out on
> n=35 and n=50. This is a classic exponential-time recursion problem.
> Tip: add memoization (cache already-computed values) or switch to an
> iterative bottom-up approach to bring this down to O(n).

---

### Math Assignment — Quadratic x²-5x+6=0 (larger root)

| Student | Answer | Score | Notes |
|---|---|---|---|
| student_E | 3 | 100% | Correct + full working shown (factored form). |
| student_F | 2 | 0% | Used quadratic formula correctly but picked the smaller root. |
| student_G | 4 | 30% | Wrong answer, flawed method — but partial credit for shown work. |
| student_H | 3 | 100% | Correct answer, zero working shown → feedback flags missing steps. |

Plagiarism flags (math batch):

```
student_F vs student_G: similarity=0.651  [ok]
student_E vs student_G: similarity=0.622  [ok]
student_E vs student_H: similarity=0.000  [ok]
```

Full JSON reports are written to `report_code.json` and `report_math.json` after each run.

---


## Extending it

- **New assignment types**: add a `grade_<type>()` method to `GradingAgent`
  and a matching `run_<type>_assignment()` to the orchestrator.
- **Real classroom use**: swap `sample_submissions/` for actual student
  files; the format in `assignments/*.json` is designed to be authored
  per real assignment.
- **Stronger plagiarism detection**: thresholds (0.80 code, 0.75 text)
  are tunable constants in `plagiarism_agent.py`.
