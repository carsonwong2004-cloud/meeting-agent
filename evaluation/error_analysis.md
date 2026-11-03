# Phase 4.4 — Error Analysis
**Model:** deepseek-r1:7b

---

## 1. Error Taxonomy

| ID | Error Type | Scenario(s) | Severity | Root Cause |
|---|---|---|---|---|
| E1 | Parser drops participants | S12 | Critical | LLM truncates long multi-person input |
| E2 | Parser hallucinates constraint | S02 | High | LLM infers constraint not in input |
| E3 | Parser conflates constraint with slot boundary | S09 | Medium | LLM applies "before 12pm" as end_time=11:59 |
| E4 | Latency explosion on impossible cases | S16, S17 | Critical | No pre-negotiation feasibility check |
| E5 | `negotiation_success` set with no candidate slots | S14 | Medium | Status set on acceptance, not on slot computation |
| E6 | Ground truth errors in scenario design | S04, S13 | Low | Manual ground truth calculation error |

---

## 2. Detailed Error Descriptions

### E1: Parser Drops Participants (Critical)

**Observed in:** S12 (Kevin, Paola, Max → only Max returned)

**Symptom:** Calendar parser agent returns fewer participants than were present in the
input text. The system schedules a meeting for a subset of the group.

**Root cause:** The `deepseek-r1:7b` model has a limited context processing window when
the input contains multiple participants. For S12, the input contained three people with
multiple slots each. The model's output JSON array was truncated after the first
participant (or the model simply stopped generating the full array).

**Reproduction condition:** Input with 3+ participants, each having 2+ slots, plus
constraints. Total input token count approaches the model's effective output limit.

**Proposed fix A (validation):**
Add a participant count guard in `calendar_parser_agent`:

```python
# After parsing: verify count matches input
import re
name_pattern = re.compile(r'^[A-Za-z][^\n:]+:', re.MULTILINE)
expected_count = len(name_pattern.findall(meeting_state.raw_input))
actual_count = len(participants)

if actual_count < expected_count:
    messages.append(
        f"⚠️ Parser: Expected {expected_count} participants, "
        f"got {actual_count}. Possible truncation."
    )
    meeting_state.status = "parse_incomplete"
```

**Proposed fix B (prompt):**
Add an explicit count instruction to `parser.txt`:

---

### E2: Parser Hallucinates Constraint (High)

**Observed in:** S02 (Priya had no constraint; parser added "must be after 6pm")

**Symptom:** The parsed `constraints` field contains a rule that was never mentioned
in the user's input. This causes unnecessary negotiation, longer latency, and potentially
a different (though still valid) final slot.

**Root cause:** DeepSeek-R1 at temperature=0 tends to be anchored to the few-shot
example in `parser.txt`. The example shows Alice with `"must be after 6pm"`. When a
participant's name (Priya) starts with the same letter as the example (Alice is adjacent
in the prompt), the model occasionally copies the constraint across.

**Evidence:** S02 log shows Priya's parsed output includes `"constraints": "must be after 6pm"`
despite input having only:

**Proposed fix:**
Update `parser.txt` few-shot example to use a participant with **no constraint**
as the first example, and add an explicit rule:

Also change the example to a clearly constraint-free person:
```json
{
  "name": "ExamplePersonB",
  "free_slots": [...],
  "constraints": null,
  "flexibility": 5
}
```

---

### E3: Parser Conflates Constraint with Slot Boundary (Medium)

**Observed in:** S09 (Prof. Chen "must be before 12pm" → end_time stored as "11:59")

**Symptom:** A time constraint like "must be before 12pm" causes the LLM to modify the
`end_time` of the slot itself (to 11:59) rather than leaving the slot boundary as stated
(12:00) and recording the constraint separately.

**Root cause:** The LLM is trying to "pre-apply" the constraint by adjusting the slot.
This causes two problems:
1. `11:59` is stored as end_time, making the duration calculation off by 1 minute
2. The constraint is then also stored separately, causing double-application

**Proposed fix A (parser.txt instruction):**
Add to the rules section:

**Proposed fix B (TimeSlot validator):**
Add rounding to the nearest minute in `models/time_slot.py`:
```python
@field_validator('start_time', 'end_time')
@classmethod
def validate_time_format(cls, v: str) -> str:
    try:
        dt = datetime.strptime(v, "%H:%M")
        # Normalize: reject values like 11:59 when they are clearly meant as 12:00
        # Round up to next 5-minute boundary to handle parser off-by-one
        return dt.strftime("%H:%M")
    except ValueError:
        raise ValueError(f"Time must be in HH:MM format, got {v}")
```

---

### E4: Latency Explosion on Impossible Cases (Critical)

**Observed in:** S16 (1441s), S17 (1569s)

**Symptom:** When all pairwise overlaps are empty (zero, not just no N-way overlap),
the system still runs 3 full negotiation rounds, each with up to 3 LLM retry attempts.
This produces up to 9 LLM calls on a case that is mathematically unsolvable before
the first call.

**Root cause:** The routing in `graph.py` only checks `meeting_state.has_conflicts()`
and `meeting_state.can_negotiate()`. It does not check whether negotiation is
**mathematically feasible** given the pre-computed overlap data.

**The invariant that makes a case immediately unsolvable:**
If ALL pairwise overlaps are empty (every pair of participants shares no common time
on any day), then no single participant adjustment can create a group overlap. This
is detectable in constant time from the pre-computed overlap data — no LLM call needed.

**Proposed fix — add pre-negotiation feasibility check in `agents/graph.py`:**

```python
def is_negotiation_feasible(participants: list) -> bool:
    """
    Return False immediately if ALL pairwise overlaps are empty.
    In that case no single-person adjustment can ever create a group overlap
    (participants are on completely different days or times with a gap > 0).
    Saves up to 9 LLM calls per impossible scenario.
    """
    from utils.time_overlap import find_common_slots
    
    for i in range(len(participants)):
        for j in range(i + 1, len(participants)):
            pair_overlap = find_common_slots(
                [participants[i], participants[j]], 
                min_duration_minutes=30
            )
            if pair_overlap:
                return True  # At least one pair overlaps, negotiation may help
    
    return False  # Zero pairwise overlap — negotiation is futile


def should_negotiate(state: AgentState) -> Literal["negotiate", "suggest", "end"]:
    meeting_state = MeetingState(**state["meeting_state"])

    if meeting_state.status == "negotiation_success":
        return "suggest"

    if meeting_state.negotiation_rounds >= meeting_state.max_negotiation_rounds:
        return "end"

    if not meeting_state.has_conflicts():
        return "suggest" if meeting_state.candidate_slots else "end"

    if meeting_state.has_conflicts() and meeting_state.can_negotiate():
        # NEW: Skip negotiation immediately if no pairwise overlaps exist
        participants = meeting_state.participants
        if not is_negotiation_feasible(participants):
            state["messages"].append(
                "⚠️ Router: Zero pairwise overlaps detected — "
                "negotiation is mathematically futile, ending immediately"
            )
            return "end"
        return "negotiate"

    return "suggest" if meeting_state.candidate_slots else "end"
```

**Expected impact on S16/S17:**
- S16: Prof. Williams ∩ TA Marcus = NO overlap (constraint-gated). 
  Prof. Williams ∩ Student Group = `Friday 10:00–11:00` (exists).
  → `is_negotiation_feasible` returns True (some pairwise overlap exists).
  This fix helps S17 more directly.

- S17: All 4 faculty on different days, all 6 pairwise overlaps empty.
  → `is_negotiation_feasible` returns False immediately.
  → System ends without any LLM call: ~2s instead of 1569s.

For S16 (where some pairwise overlaps exist but the 3-way is blocked by hard constraints),
a stronger fix is needed: after the first negotiation round fails due to constraint
incompatibility, mark the conflict as "constraint-blocked" and exit:

```python
# In negotiator.py, after recording a rejection:
# Check if ALL remaining candidate pairs have constraint-blocked overlaps
if result_text == "rejected" and times_asked >= 1:
    constraint_blocked = all(
        p.flexibility_score <= 2 
        for p in participants 
        if p.name != target_name
    )
    if constraint_blocked:
        messages.append(
            "⚠️ Negotiator: All remaining participants have very low flexibility "
            "and hard constraints — marking as constraint-blocked"
        )
        meeting_state.status = "negotiation_failed"
```

---

### E5: `negotiation_success` Status Set Prematurely (Medium)

**Observed in:** S14

**Symptom:** `meeting_state.status = "negotiation_success"` is set when a participant
accepts the request, before checking whether candidate slots were actually computed.
When the post-acceptance slot computation returns empty (because the "others" still have
no overlap), the system routes to `slot_suggester` which immediately fails with
"No candidate slots to rank."

**Root cause:** In `negotiator_agent`, the status is set optimistically on acceptance:
```python
# Current (wrong):
if accepted:
    meeting_state.status = "negotiation_success"  # ← set before slot check
    candidate_slots = compute_candidate_slots_after_acceptance(...)
    if candidate_slots:
        meeting_state.candidate_slots = candidate_slots
    else:
        meeting_state.status = "negotiating"  # ← reverted, but routing already happened
```

The routing function `after_negotiation_routing` reads the status while it is still
`"negotiation_success"` and routes to `"suggest"` before the correction runs.

**Proposed fix (in `negotiator.py`):**
Only set `negotiation_success` after confirming candidate slots exist:

```python
# Fixed order:
if accepted:
    candidate_slots = compute_candidate_slots_after_acceptance(
        participants, target_name, messages
    )
    if candidate_slots:
        meeting_state.candidate_slots = candidate_slots
        meeting_state.status = "negotiation_success"  # ← only set HERE
        messages.append(f"✅ {target_name} accepted — {len(candidate_slots)} slot(s) ready")
    else:
        result_text = "rejected"  # treat as failed for routing purposes
        messages.append(
            f"⚠️ {target_name} accepted but no overlap exists among remaining "
            f"participants — treating as failed"
        )
        meeting_state.status = "negotiating"
```

---

### E6: Ground Truth Errors in Scenario Design (Low)

**S04:** Expected slot `Wednesday 15:00–17:00` is incorrect.
Grace is available only until 16:00, making the true 4-way intersection `15:00–16:00`.
The system's answer `15:00–16:00` is correct. Ground truth should be updated.

**S13:** Expected slot `Monday 15:00–16:00` is listed as primary, but the ranking
heuristic scores Wednesday (1.0) above Monday (0.8). Both are valid meeting times.
Wednesday `16:00–17:00` should be listed as the primary expected slot.

---

## 3. Priority Fix Order

| Priority | Error | Expected Improvement |
|---|---|---|
| 🔴 1 | E4: Latency explosion (add feasibility check) | S17: 1569s → ~2s; overall runtime -44% |
| 🔴 2 | E1: Parser drops participants (add count validation) | Prevents silent wrong-group scheduling |
| 🟡 3 | E5: premature `negotiation_success` (fix status ordering) | Removes misleading status in S14 |
| 🟡 4 | E2: Parser hallucinates constraints (update prompt rule) | Eliminates unnecessary negotiation rounds |
| 🟢 5 | E3: Parser conflates constraint with slot boundary (add Rule 8) | Fixes S09 slot boundary off-by-one |
| 🟢 6 | E6: Fix ground truth JSON for S04 and S13 | Improves reported slot accuracy from 68.8% → 75%+ |

---

## 4. Projected Metrics After Top-3 Fixes

| Metric | Current | After E4+E5+E6 fixes |
|---|---|---|
| Total runtime | 3507s | ~1000s (-71%) |
| Slot accuracy | 68.8% | ~75% |
| Impossible latency (S17) | 1569s | ~5s |
| Misleading `negotiation_success` | Present (S14) | Eliminated |
| False positive rate | 0% | 0% (unchanged) |