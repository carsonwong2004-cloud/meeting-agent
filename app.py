import streamlit as st
import os
from dotenv import load_dotenv
from agents.graph import run_scheduler
from models import MeetingState

load_dotenv()

st.set_page_config(
    page_title="Campus Meeting Scheduler",
    page_icon="🤝",
    layout="wide"
)

st.markdown("""
<style>
  :root {
    --surface:      hsl(220 14% 97%);
    --raised:       hsl(0 0% 100%);
    --border:       hsl(220 13% 90%);
    --muted:        hsl(220 9% 55%);
    --body:         hsl(220 15% 15%);
    --accent:       hsl(221 83% 53%);
    --accent-light: hsl(221 83% 95%);
    --success:      hsl(142 71% 45%);
    --warning:      hsl(38 92% 50%);
    --danger:       hsl(0 72% 51%);
  }
  .agent-card {
    background: var(--raised);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 10px 14px;
    margin-bottom: 6px;
    font-size: 0.92rem;
    line-height: 1.5;
  }
  .agent-card.success { border-left: 4px solid var(--success); }
  .agent-card.warning { border-left: 4px solid var(--warning); }
  .agent-card.error   { border-left: 4px solid var(--danger);  }
  .agent-card.info    { border-left: 4px solid var(--accent);  }
  .agent-card.neutral { border-left: 4px solid var(--border);  }
  .invite-box {
    background: var(--accent-light);
    border: 1px solid hsl(221 83% 80%);
    border-radius: 10px;
    padding: 18px 22px;
    font-family: monospace;
    font-size: 0.88rem;
    white-space: pre-wrap;
    line-height: 1.6;
  }
  .metric-row { display: flex; gap: 12px; margin: 12px 0; }
  .metric-card {
    flex: 1;
    background: var(--raised);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 14px;
    text-align: center;
  }
  .metric-card .label { color: var(--muted); font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.04em; }
  .metric-card .value { color: var(--body); font-size: 1.6rem; font-weight: 700; margin-top: 4px; }
  .section-title {
    font-size: 1.05rem;
    font-weight: 600;
    color: var(--body);
    margin: 20px 0 10px;
    padding-bottom: 6px;
    border-bottom: 2px solid var(--border);
  }
</style>
""", unsafe_allow_html=True)

st.title("🤝 Campus Meeting Scheduler")
st.markdown("*AI agents that negotiate to find meeting times — powered by local DeepSeek-R1*")

with st.sidebar:
    st.header("How It Works")
    st.markdown("""
    **Agent pipeline:**
    1. 📋 **Parser** — reads everyone's availability
    2. 🔍 **Conflict Checker** — finds overlaps
    3. 🤝 **Negotiator** — resolves conflicts autonomously
    4. 🎯 **Slot Suggester** — ranks best times
    5. ✉️ **Invite Writer** — drafts the invitation *(Phase 3)*
    """)
    st.divider()
    st.markdown(f"**Model:** `{os.getenv('OLLAMA_MODEL', 'deepseek-r1:7b')}`")
    st.markdown("**Phase:** 3 — Invite Writer & Polish ✅")
    st.divider()
    st.subheader("Input Format")
    st.code("""Name:
Day time-time free
Constraint: description
Flexibility: 1-10""", language="text")

# ── Examples dict ──────────────────────────────────────────────────────────────
EXAMPLES = {
    "Phase 2 Demo — Negotiable Conflict": """\
Alice:
Monday 2-4pm free
Tuesday 6-8pm free
Constraint: must be after 6pm
Flexibility: 3

Bob:
Monday 3-7pm free
Tuesday 3-7pm free
Flexibility: 8

Carol:
Monday 2-8pm free
Tuesday 5-8pm free
Flexibility: 6""",

    "Three-Person Overlap": """\
Alice:
Tuesday 10am-2pm free
Flexibility: 4

Bob:
Tuesday 1pm-5pm free
Flexibility: 5

Carol:
Tuesday 3pm-6pm free
Flexibility: 8""",

    "Impossible Conflict": """\
Alice:
Wednesday 9am-12pm free
Constraint: no afternoons
Flexibility: 2

Bob:
Wednesday 2pm-5pm free
Constraint: must be after 1pm
Flexibility: 3""",

    "Simple — No Conflict": """\
Chris:
Monday 2-4pm free
Wednesday 2-4pm free

David:
Monday 3-5pm free
Wednesday 2-4pm free""",
}

CUSTOM_DEFAULT = """\
Alice:
Monday 2-4pm free
Tuesday 6-8pm free

Bob:
Monday 3-5pm free
Wednesday 5-7pm free"""

# ── Layout ─────────────────────────────────────────────────────────────────────
col_input, col_tips = st.columns([3, 2])

with col_input:
    st.subheader("📅 Input Availability")

    example_choice = st.selectbox(
        "Load example scenario:",
        ["Custom Input"] + list(EXAMPLES.keys())
    )

    # FIX: Determine the correct text based on current selectbox value.
    # Do NOT use key= on st.text_area — combining key= with value= causes
    # Streamlit to ignore value= after the first render, freezing the content.
    if example_choice == "Custom Input":
        default_text = CUSTOM_DEFAULT
    else:
        default_text = EXAMPLES[example_choice]

    # No key= here — value= is respected on every render
    calendar_input = st.text_area(
        "Paste everyone's availability:",
        value=default_text,
        height=280,
    )

    run_button = st.button(
        "🚀 Find Meeting Time",
        type="primary",
        use_container_width=True
    )

with col_tips:
    st.subheader("💡 Tips")
    st.info("""
**Flexibility scale:**
- 8-10 → Very flexible (70%+ acceptance)
- 5-7  → Moderate (50% acceptance)
- 1-4  → Rigid (20% acceptance)

**Constraint examples:**
- `must be after 6pm`
- `must be before 5pm`
- `no mornings`
- `need at least 2 hours`

Higher flexibility = negotiator targets you first.
""")

# ── Execution ──────────────────────────────────────────────────────────────────
if run_button:
    if not calendar_input.strip():
        st.error("Please enter availability data.")
    else:
        with st.spinner("🤖 Agents working — DeepSeek-R1 may take 15-30 s per round..."):
            try:
                # FIX: read from the local variable, not st.session_state
                result = run_scheduler(calendar_input)
                meeting_state = MeetingState(**result["meeting_state"])
                messages = result.get("messages", [])

                # ── Agent Log ──────────────────────────────────────────────────
                st.markdown('<div class="section-title">📋 Agent Execution Log</div>',
                            unsafe_allow_html=True)

                in_negotiation = False
                for msg in messages:
                    if "Negotiator: Starting" in msg and not in_negotiation:
                        st.markdown("**🤝 Negotiation Phase**")
                        in_negotiation = True

                    if msg.startswith("✅"):
                        css = "success"
                    elif msg.startswith(("⚠️", "🔄")):
                        css = "warning"
                    elif msg.startswith("❌"):
                        css = "error"
                    elif msg.startswith(("🤝", "🎯", "📝", "💭", "📅", "✉️")):
                        css = "info"
                    else:
                        css = "neutral"

                    st.markdown(
                        f'<div class="agent-card {css}">{msg}</div>',
                        unsafe_allow_html=True
                    )

                # ── Final Result ───────────────────────────────────────────────
                st.markdown('<div class="section-title">🎯 Final Result</div>',
                            unsafe_allow_html=True)

                if meeting_state.final_slot:
                    st.success("✅ Meeting time found!")

                    slot = meeting_state.final_slot
                    st.markdown(f"""
<div class="metric-row">
  <div class="metric-card">
    <div class="label">Day</div>
    <div class="value">{slot.day}</div>
  </div>
  <div class="metric-card">
    <div class="label">Start</div>
    <div class="value">{slot.start_time}</div>
  </div>
  <div class="metric-card">
    <div class="label">End</div>
    <div class="value">{slot.end_time}</div>
  </div>
  <div class="metric-card">
    <div class="label">Duration</div>
    <div class="value">{slot.duration_minutes()} min</div>
  </div>
</div>""", unsafe_allow_html=True)

                    if meeting_state.negotiation_rounds > 0:
                        st.markdown("**📊 Negotiation Summary**")
                        accepted = sum(
                            1 for h in meeting_state.negotiation_history
                            if h.get("result") == "accepted"
                        )
                        rejected = sum(
                            1 for h in meeting_state.negotiation_history
                            if h.get("result") == "rejected"
                        )
                        c1, c2, c3 = st.columns(3)
                        c1.metric("Rounds Used", f"{meeting_state.negotiation_rounds}/3")
                        c2.metric("Accepted",    accepted)
                        c3.metric("Rejected",    rejected)

                    if meeting_state.final_message:
                        st.markdown('<div class="section-title">✉️ Meeting Invitation</div>',
                                    unsafe_allow_html=True)
                        st.markdown(
                            f'<div class="invite-box">{meeting_state.final_message}</div>',
                            unsafe_allow_html=True
                        )
                        with st.expander("📋 Copy invitation text"):
                            st.text_area(
                                "Select all and copy:",
                                value=meeting_state.final_message,
                                height=220,
                                label_visibility="collapsed"
                            )
                        ics_content = (
                            "BEGIN:VCALENDAR\n"
                            "VERSION:2.0\n"
                            "PRODID:-//Campus Meeting Scheduler//EN\n"
                            "BEGIN:VEVENT\n"
                            "SUMMARY:Team Meeting\n"
                            "DESCRIPTION:Scheduled via Campus Meeting Scheduler\n"
                            f"DTSTART;VALUE=DATE:{slot.day.upper()[:3]}\n"
                            "END:VEVENT\n"
                            "END:VCALENDAR\n"
                        )
                        st.download_button(
                            label="📥 Download .ics calendar file",
                            data=ics_content,
                            file_name="meeting.ics",
                            mime="text/calendar"
                        )

                elif meeting_state.conflicts:
                    st.error("❌ Unable to resolve scheduling conflicts")
                    st.markdown("**Remaining conflicts:**")
                    for conflict in meeting_state.conflicts:
                        st.markdown(f"- {conflict}")
                    if meeting_state.negotiation_history:
                        st.markdown(
                            f"**Negotiation attempts:** "
                            f"{meeting_state.negotiation_rounds} rounds"
                        )
                        for entry in meeting_state.negotiation_history:
                            st.markdown(
                                f"- Asked **{entry['target']}**: "
                                f"{entry.get('result', 'unknown')}"
                            )
                    st.info(
                        "💡 These constraints may be truly incompatible. "
                        "Consider: longer timeframe, async meeting, or splitting sessions."
                    )

                else:
                    st.warning("⚠️ Unable to complete scheduling")

                if meeting_state.negotiation_history:
                    with st.expander("🔍 Detailed Negotiation History"):
                        for i, entry in enumerate(meeting_state.negotiation_history, 1):
                            st.markdown(f"**Round {i}**")
                            st.markdown(f"- **Target:** {entry.get('target')}")
                            st.markdown(f"- **Message:** {entry.get('message', 'N/A')}")
                            st.markdown(f"- **Result:** {entry.get('result')}")
                            if i < len(meeting_state.negotiation_history):
                                st.divider()

                with st.expander("🔍 Debug: Parsed Participants"):
                    for p in meeting_state.participants:
                        st.markdown(f"**{p.name}**")
                        st.markdown(f"- Flexibility: {p.flexibility_score}/10")
                        st.markdown(
                            f"- Constraints: "
                            f"{', '.join(p.constraints) if p.constraints else 'None'}"
                        )
                        st.markdown(f"- Free slots: {len(p.free_slots)}")
                        for s in p.free_slots:
                            st.markdown(f"  - {s.day}: {s.start_time}–{s.end_time}")

            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                with st.expander("Show error details"):
                    st.exception(e)

# ── Footer ─────────────────────────────────────────────────────────────────────
st.divider()
st.markdown(
    "<div style='text-align:center;color:hsl(220 9% 55%);font-size:0.85rem'>"
    "Phase 1: Foundation ✅ &nbsp;|&nbsp; "
    "Phase 2: Negotiation ✅ &nbsp;|&nbsp; "
    "Phase 3: Invite Writer & Polish ✅ &nbsp;|&nbsp; "
    "Phase 4: Evaluation (next)"
    "</div>",
    unsafe_allow_html=True
)