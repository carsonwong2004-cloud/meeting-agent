# ── Python ─────────────────────────────────────────────────────
__pycache__/
*.py[cod]
*.pyo
*.pyd
*.pyc
.Python

# ── Virtual environments ────────────────────────────────────────
venv/
env/
.venv/
ENV/

# ── Environment & secrets ───────────────────────────────────────
.env
*.env
!.env.example

# ── Distribution / packaging ────────────────────────────────────
dist/
build/
*.egg-info/
*.egg
.eggs/
MANIFEST

# ── Testing & coverage ──────────────────────────────────────────
.pytest_cache/
.coverage
coverage.xml
htmlcov/
.tox/

# ── Streamlit ───────────────────────────────────────────────────
.streamlit/secrets.toml

# ── Evaluation outputs (generated, not source) ──────────────────
evaluation/results.csv
evaluation/results.json
evaluation/metrics_summary.json
evaluation/fig*.png

# ── IDE / editor ────────────────────────────────────────────────
.vscode/
.idea/
*.swp
*.swo
*.suo
*.user
.DS_Store
Thumbs.db

# ── Jupyter ─────────────────────────────────────────────────────
.ipynb_checkpoints/
*.ipynb

# ── Logs ────────────────────────────────────────────────────────
*.log
logs/
