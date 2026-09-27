# Intelligent Assignment Grader & Feedback Generator

A multi-agent system that automatically grades programming and math assignments, generates personalised per-student feedback, detects plagiarism patterns, and suggests improvement areas.

**Framework:** Pure Python + Groq API (tool-calling) — permitted by the lab brief.  
**GitHub:** https://github.com/prathameshgolhar4511-dev/assignment_grader

---

## Lab Requirements Checklist

| # | Requirement | Status | Where satisfied |
|---|---|---|---|
| 1 | One problem statement per student | ✅ | Two assignment types: Fibonacci (code) + Quadratic (math) |
| 2 | Multi-agent system (≥ 3 agents) | ✅ | **5 agents**: `GradingAgent`, `PlagiarismAgent`, `FeedbackAgent`, `ImprovementAgent`, `CoordinatorAgent` |
| 3 | Any suitable framework | ✅ | Pure Python + Groq LLM API — no external agent framework required |
| 4 | Tool calling + basic orchestration | ✅ | `CoordinatorAgent` exposes all 4 specialist agents as callable tools via Groq function-calling; the LLM autonomously decides which tools to call and in what order |
| 5 | Prescribed report format | ✅ | `report_formatter.py` — outputs `report_*_prescribed.json` + `report_*_prescribed.md` per run |
| 6 | GitHub + clear README | ✅ | This README; repo at link above |
| 7 | Individual work | ✅ | — |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        main.py  (CLI)                            │
│         python main.py all / code / math / agentic-*            │
└─────────────────────┬────────────────────┬───────────────────────┘
                      │                    │
          Fixed pipeline mode        Agentic mode (tool-calling)
                      │                    │
                      ▼                    ▼
       ┌─────────────────────┐  ┌──────────────────────────────┐
       │   orchestrator.py   │  │      CoordinatorAgent        │
       │  GradingOrchestrator│  │  agents/coordinator_agent.py │
       │  (direct calls,     │  │                              │
       │   fixed order)      │  │  Groq LLM ◄──► tool schemas │
       └──────┬──────────────┘  │  LLM decides which tools to  │
              │                 │  call, in what order          │
              │                 └─────────────┬────────────────┘
              │                               │  tool calls
              │          ┌────────────────────┼──────────────────┐
              │          │                    │                  │
              ▼          ▼                    ▼                  ▼
 ┌──────────────┐ ┌────────────┐ ┌─────────────────┐ ┌──────────────────┐
 │ GradingAgent │ │Plagiarism  │ │  FeedbackAgent  │ │ImprovementAgent  │
 │              │ │Agent       │ │                 │ │                  │
 │ • subprocess │ │            │ │ • Groq LLM call │ │ • rule-based     │
 │   sandbox    │ │ • AST-norm │ │ • personalised  │ │   weak signals   │
 │ • sympy math │ │   + diff   │ │   feedback text │ │ • LLM-polished   │
 │ • static     │ │ • TF-IDF   │ │                 │ │   suggestions    │
 │   checks     │ │   cosine   │ │                 │ │                  │
 └──────────────┘ └────────────┘ └─────────────────┘ └──────────────────┘

              ┌──────────────────────────────────────────┐
              │              report_formatter.py          │
              │  build_report()  →  prescribed JSON       │
              │  to_markdown()   →  prescribed .md        │
              └──────────────────────────────────────────┘
```

### Agent Roles

| Agent | File | Responsibility |
|---|---|---|
| **GradingAgent** | `agents/grading_agent.py` | Runs student code against test cases in a subprocess sandbox (timeout-bounded). Grades math answers symbolically via `sympy`. Returns score + per-test breakdown + static analysis. |
| **PlagiarismAgent** | `agents/plagiarism_agent.py` | Code: normalises AST (strips all variable/function names) then computes structural similarity — catches copy-and-rename cheating. Math: TF-IDF cosine similarity on "work shown". |
| **FeedbackAgent** | `agents/feedback_agent.py` | Sends grading results to the Groq LLM and returns personalised, student-specific feedback (≤ 120 words, one actionable tip). |
| **ImprovementAgent** | `agents/improvement_agent.py` | Detects weak signals (timeouts, bare excepts, no function defs, low math score) and calls the LLM to produce a polished 2–4 point improvement plan. |
| **CoordinatorAgent** | `agents/coordinator_agent.py` | Supervisor agent. Exposes the four specialists as callable tools (`grade_submission`, `check_plagiarism_for_student`, `generate_feedback`, `suggest_improvements`, `submit_final_report`) and passes them to the Groq function-calling API. The LLM decides the order autonomously. |

### Tool-Calling Flow (Agentic Mode)

```
User prompt  →  CoordinatorAgent
                    │
                    ▼
              Groq LLM receives tool schemas
                    │
          ┌─────────▼──────────┐
          │  grade_submission  │  ← LLM calls first (score needed before feedback)
          └─────────┬──────────┘
                    │ result injected back into context
          ┌─────────▼──────────────────┐
          │  check_plagiarism_for_     │
          │  student                   │
          └─────────┬──────────────────┘
                    │
          ┌─────────▼──────────┐
          │  generate_feedback │
          └─────────┬──────────┘
                    │
          ┌─────────▼──────────────┐
          │  suggest_improvements  │
          └─────────┬──────────────┘
                    │
          ┌─────────▼──────────────┐
          │  submit_final_report   │  ← LLM assembles & submits
          └────────────────────────┘
```

---

## Prescribed Report Format (Requirement #5)

Each run produces three output files:

| File | Contents |
|---|---|
| `report_<type>.json` | Raw pipeline output (full grading + feedback + improvement data) |
| `report_<type>_prescribed.json` | Structured prescribed-format JSON (see schema below) |
| `report_<type>_prescribed.md` | Human-readable Markdown version of the prescribed report |

### Prescribed JSON Schema

```json
{
  "report_metadata": {
    "assignment_title": "string",
    "assignment_type": "code | math",
    "generated_at": "YYYY-MM-DD HH:MM:SS",
    "total_students": "integer",
    "agents_used": ["list of agent names"],
    "framework": "string"
  },
  "summary_table": [
    { "student_id": "string", "score_pct": "float", "plagiarism_status": "Clean | FLAGGED (...)" }
  ],
  "plagiarism_flags": [
    { "student_pair": ["id_a", "id_b"], "similarity_score": "float", "flagged": "boolean" }
  ],
  "student_reports": [
    {
      "student_id": "string",
      "assignment_title": "string",
      "score_pct": "float",
      "grading_details": { "...type-specific fields..." },
      "feedback": "string",
      "improvement_suggestions": ["bullet list"],
      "improvement_narrative": "string",
      "plagiarism_status": "string"
    }
  ]
}
```

---

## Project Layout

```
assignment_grader/
├── main.py                      # CLI entry point
├── orchestrator.py              # Fixed pipeline orchestration
├── report_formatter.py          # Prescribed report builder (JSON + Markdown)
├── utils.py                     # Shared LLM wrapper (Groq live + mock mode)
├── requirements.txt
├── .env.example                 # Copy to .env and add your GROQ_API_KEY
├── .gitignore
├── agents/
│   ├── coordinator_agent.py     # Tool-calling supervisor agent
│   ├── grading_agent.py         # Objective scoring (code + math)
│   ├── plagiarism_agent.py      # Similarity detection
│   ├── feedback_agent.py        # LLM-generated personalised feedback
│   └── improvement_agent.py     # LLM-polished improvement suggestions
├── assignments/
│   ├── code_assignment.json     # Problem definition + test cases
│   └── math_assignment.json     # Problem definition + expected answer
└── sample_submissions/
    ├── code/student_A.py  ...   # 4 sample Python submissions
    └── math/submissions.json    # 4 sample math submissions
```

---

## Setup & Run

### 1. Clone the repo

```bash
git clone https://github.com/prathameshgolhar4511-dev/assignment_grader.git
cd assignment_grader
```

### 2. Create a virtual environment

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

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure API key

Get a free Groq key at https://console.groq.com (no credit card needed).

```bash
# copy the template
cp .env.example .env
# then open .env and set:
# GROQ_API_KEY=your_actual_key_here
```

> **No key?** The system runs fully in **mock mode** — all 5 agents execute, grading is deterministic, and feedback/improvement outputs are clearly labelled placeholder text. Useful for demos without credentials.

### 5. Run

```bash
python main.py all             # fixed pipeline: code + math assignments
python main.py code            # fixed pipeline: code only
python main.py math            # fixed pipeline: math only
python main.py agentic-code    # tool-calling CoordinatorAgent: code
python main.py agentic-math    # tool-calling CoordinatorAgent: math
```

### 6. Output files

| File | Description |
|---|---|
| `report_code.json` | Raw code grading report |
| `report_code_prescribed.json` | Prescribed-format JSON (code) |
| `report_code_prescribed.md` | Prescribed-format Markdown (code) |
| `report_math.json` | Raw math grading report |
| `report_math_prescribed.json` | Prescribed-format JSON (math) |
| `report_math_prescribed.md` | Prescribed-format Markdown (math) |
| `report_agentic_code.json` | Agentic run with full tool-call trace (code) |
| `report_agentic_math.json` | Agentic run with full tool-call trace (math) |

---

## Sample Results

### Programming Assignment — Fibonacci (memoised)

| Student | Score | Plagiarism | Key Finding |
|---|---|---|---|
| student_A | 100% | ✅ Clean | All 8 tests passed. Has docstring + memoisation. |
| student_B | 100% | ⚠️ FLAGGED | All 8 tests passed. AST similarity 0.988 vs student_A — copy with renamed variables. |
| student_C | 100% | ✅ Clean | All 8 tests passed. Correct iterative approach. |
| student_D | 87.5% | ✅ Clean | 7/8 tests passed. Naive recursion TIMEOUTs on n=50. Efficiency improvement flagged. |

### Math Assignment — Quadratic x²−5x+6=0 (larger root)

| Student | Answer | Score | Plagiarism | Notes |
|---|---|---|---|---|
| student_E | 3 | 100% | ✅ Clean | Correct + full working shown. |
| student_F | 2 | 30% | ✅ Clean | Wrong root chosen; partial credit for shown work. |
| student_G | 4 | 30% | ✅ Clean | Wrong answer, flawed method; partial credit for shown work. |
| student_H | 3 | 100% | ✅ Clean | Correct answer, no working shown — feedback flags missing steps. |

---

## Two Modes Explained

**Fixed pipeline** (`python main.py code / math / all`)  
`orchestrator.py` calls each specialist agent directly in Python in a fixed order. Fast, deterministic, suitable for bulk grading.

**Agentic / tool-calling** (`python main.py agentic-code / agentic-math`)  
`CoordinatorAgent` runs for each student. The Groq LLM receives tool schemas and decides autonomously which tools to call and in what sequence. The full **tool-call trace** is printed to the terminal, making the orchestration decisions visible. This directly demonstrates requirement #4.

---

## Dependencies

```
sympy>=1.12          # symbolic math comparison
groq>=0.11.0         # Groq Python SDK (tool-calling)
python-dotenv>=1.0.0 # .env file loading
```

All other functionality uses Python standard library only (`ast`, `difflib`, `subprocess`, `re`, `json`, `glob`, `math`, `collections`, `itertools`).
