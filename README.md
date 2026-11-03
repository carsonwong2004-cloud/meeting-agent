# Campus Meeting Scheduler — Multi-Agent LLM System

An autonomous meeting scheduler built with LangGraph, Streamlit, and a local DeepSeek-R1 model via Ollama. Five AI agents parse natural language availability, detect scheduling conflicts, negotiate solutions autonomously, and generate a polished meeting invitation.

---

## Quick Start

```bash
# 1. Pull the model
ollama pull deepseek-r1:7b

# 2. Install dependencies
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS/Linux
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env         # already set up for Ollama, no API key needed

# 4. Run
streamlit run app.py
```

Open `http://localhost:8501`.

---

## Input Format

```
Name:
Day time-time free
Constraint: must be after 6pm   (optional)
Flexibility: 8                  (optional, 1–10, default 5)
```

**Example:**
```
Alice:
Monday 2-4pm free
Tuesday 6-8pm free
Constraint: must be after 6pm
Flexibility: 3

Bob:
Monday 3-7pm free
Flexibility: 8
```

---

## Agent Pipeline

```
Calendar Parser → Conflict Checker → Negotiator (up to 3 rounds)
                                   → Slot Suggester → Invite Writer
```

All time arithmetic runs in pure Python. The LLM handles only language tasks — parsing natural text, crafting negotiation messages, writing invitations.

---

## Project Structure

```
meeting-agent/
├── agents/          calendar_parser, conflict_checker, negotiator,
│                    slot_suggester, invite_writer, graph
├── models/          TimeSlot, Participant, MeetingState (Pydantic)
├── utils/           time_overlap, constraints, simulate_response
├── prompts/         parser.txt, negotiator.txt, invite_writer.txt
├── data/            real_scenarios.json, response_templates.json
├── evaluation/      metrics.py, run_evaluation.py, plot_results.py
├── tests/           test_models, test_time_overlap, test_constraints,
│                    test_negotiator
├── docs/            architecture.mermaid, prompt_design.md,
│                    user_guide.md, demo_script.md,
│                    final_report.md, presentation_outline.md
├── app.py
├── requirements.txt
└── .env.example
```

---

## Evaluation Results (20 scenarios)

| Metric | Result |
|---|---|
| Solvable success rate | 100% (16/16) |
| Impossible detection rate | 100% (4/4) |
| False positive rate | 0% |
| Avg negotiation rounds | 0.25 |

---

## Running Tests

```bash
pytest tests/ -v
```

## Running Evaluation

```bash
py evaluation/run_evaluation.py
py evaluation/plot_results.py
```

---

## Phase Completion

| Phase | Description |
|---|---|
| 1 ✅ | Foundation & Core Agents |
| 2 ✅ | Negotiation Agent |
| 3 ✅ | Invite Writer & Polish |
| 4 ✅ | Evaluation & Metrics |
| 5 ✅ | Documentation & Presentation |

---

## Requirements

- Python 3.10+
- [Ollama](https://ollama.ai) with `deepseek-r1:7b` pulled
- 8 GB RAM minimum (16 GB recommended)

---

## Team

4-person Undergraduate Data Science Group Project — 6-month timeline
