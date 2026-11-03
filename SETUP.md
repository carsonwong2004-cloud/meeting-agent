# Phase 1 Setup Guide

## Prerequisites
- Python 3.10 or higher
- OpenAI API key

## Installation Steps

### 1. Clone/Download Project
```bash
# Ensure you have this directory structure:
campus-scheduler/
├── agents/
├── models/
├── utils/
├── prompts/
├── tests/
├── data/
├── app.py
├── requirements.txt
└── .env
```

### 2. Create Virtual Environment
```bash
python3 -m venv venv

# Activate it:
# On macOS/Linux:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure API Key
```bash
# Copy the example env file
cp .env.example .env

# Edit .env and add your OpenAI API key:
# OPENAI_API_KEY=sk-...your-key-here...
```

### 5. Run Tests (Verify Installation)
```bash
pytest tests/ -v --cov=.
```

Expected output:
```
tests/test_models.py::TestTimeSlot::... PASSED
tests/test_time_overlap.py::... PASSED
tests/test_constraints.py::... PASSED

---------- coverage: ... ----------
```

### 6. Run the Application
```bash
streamlit run app.py
```

Browser should open to `http://localhost:8501`

## Quick Test

1. Leave the default example in the text area
2. Click "🚀 Find Meeting Time"
3. You should see:
   - ✅ Calendar Parser: Successfully parsed 2 participants
   - 🔍 Conflict Checker: Found overlapping time blocks
   - ✅ Slot Suggester: Recommending top slot
   - 🎯 Result showing a Monday time slot

## Troubleshooting

**Error: "No module named 'langgraph'"**
- Run: `pip install -r requirements.txt` again

**Error: "OPENAI_API_KEY not found"**
- Check your `.env` file exists and has `OPENAI_API_KEY=sk-...`

**Error: "Rate limit exceeded"**
- You've hit OpenAI API limits. Wait a minute or upgrade your API plan.

**Tests failing?**
- Make sure you're in the project root directory
- Run: `python -m pytest tests/` instead

## Next Steps

Phase 1 is complete! Next up:
- **Phase 2**: Build the Negotiator agent
- **Phase 3**: Add Invite Writer and UI polish
- **Phase 4**: Evaluation metrics
- **Phase 5**: Documentation and presentation

## Cost Estimates

Phase 1 testing costs (approximate):
- Each scheduling run: ~2,000-3,000 tokens
- Cost per run: ~$0.001-0.002 (with GPT-4o-mini)
- 100 test runs: ~$0.10-0.20

Very affordable for a 6-month project!
