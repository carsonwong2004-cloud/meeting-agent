from typing import Dict, Any, Optional
from langchain_ollama import ChatOllama
import json
import os
import re
from models import MeetingState, Participant


def load_prompt(filename: str) -> str:
    """Load prompt template from file."""
    prompt_path = os.path.join("prompts", filename)
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def select_best_target(
    participants: list[Participant],
    negotiation_history: list
) -> Optional[Participant]:
    """
    Fallback logic to select negotiation target if LLM fails.

    Priority:
    1. Highest flexibility who hasn't been asked yet
    2. Anyone with flexibility >= 5 who hasn't been asked
    3. Anyone who hasn't been asked at all
    """
    asked_names = set(entry.get("target", "") for entry in negotiation_history)

    available = [p for p in participants if p.name not in asked_names]

    if not available:
        available = [p for p in participants if p.flexibility_score >= 5]

    if not available:
        return None

    available.sort(key=lambda p: p.flexibility_score, reverse=True)
    return available[0]


def format_participant_summary(participants: list[Participant]) -> str:
    """Format participant info for prompt."""
    lines = []
    for p in participants:
        slots_str = ", ".join([
            f"{s.day} {s.start_time}-{s.end_time}"
            for s in p.free_slots[:3]
        ])
        if len(p.free_slots) > 3:
            slots_str += f" (and {len(p.free_slots) - 3} more)"

        if p.constraints:
            constraint_str = f"Constraint: {', '.join(p.constraints)}"
        else:
            constraint_str = "No constraints"

        lines.append(
            f"- {p.name}: {slots_str} | "
            f"{constraint_str} | "
            f"Flexibility: {p.flexibility_score}/10"
        )

    return "\n".join(lines)


def compute_pre_calculated_overlaps(
    participants: list[Participant],
    messages: list[str]
) -> str:
    """
    Option A fix: compute ALL overlaps using Python math before sending to LLM.

    Returns a formatted string of verified overlap facts to inject into the
    negotiator prompt so the LLM never has to (and never can) hallucinate
    time intersection arithmetic.
    """
    from utils.time_overlap import find_common_slots

    lines = []
    lines.append("=== VERIFIED OVERLAP DATA (computed by Python, not estimated) ===")
    lines.append("IMPORTANT: Use ONLY these values. Do NOT recalculate overlaps yourself.")
    lines.append("")

    # --- N-way overlap (all participants together) ---
    all_overlap = find_common_slots(participants, min_duration_minutes=30)
    if all_overlap:
        slots_str = ", ".join([
            f"{s.day} {s.start_time}-{s.end_time}" for s in all_overlap
        ])
        lines.append(
            f"ALL {len(participants)} participants share these slots: {slots_str}"
        )
    else:
        lines.append(
            f"NO slot exists where all {len(participants)} participants overlap."
        )

    lines.append("")
    lines.append("Pairwise overlaps (who blocks whom):")

    # --- Pairwise overlaps (2-person intersections) ---
    for i in range(len(participants)):
        for j in range(i + 1, len(participants)):
            p1 = participants[i]
            p2 = participants[j]
            pair_overlap = find_common_slots([p1, p2], min_duration_minutes=30)
            if pair_overlap:
                pair_str = ", ".join([
                    f"{s.day} {s.start_time}-{s.end_time}" for s in pair_overlap
                ])
                lines.append(f"  {p1.name} ∩ {p2.name} = {pair_str}")
            else:
                lines.append(f"  {p1.name} ∩ {p2.name} = NO overlap")

    lines.append("")
    lines.append(
        "The goal is to find ONE adjustment that creates a full N-way overlap. "
        "Use only the pairwise data above to reason about who needs to adjust."
    )

    result = "\n".join(lines)

    # Print to terminal for debugging
    print("\n[Pre-calculated overlaps injected into prompt]:")
    print(result)
    print()

    return result


def format_negotiation_history(history: list) -> str:
    """Format past negotiation attempts for prompt."""
    if not history:
        return "None yet (this is the first negotiation attempt)"

    lines = []
    for i, entry in enumerate(history, 1):
        result = entry.get("result", "pending")
        lines.append(
            f"Round {i}: Asked {entry.get('target', 'unknown')} to "
            f"{entry.get('requested_change', 'adjust')} → Result: {result}"
        )

    return "\n".join(lines)


def compute_candidate_slots_after_acceptance(
    participants: list[Participant],
    accepted_target_name: str,
    messages: list[str]
) -> list:
    """
    After acceptance, compute the slot that now exists due to the adjustment.
    
    For Phase 2: compute overlap among remaining participants (simple fallback).
    Phase 3 will parse the requested_change and actually modify slots.
    """
    from utils.time_overlap import find_common_slots
    from utils.constraints import apply_constraints
    import copy
    
    # Deep copy participants so we don't mutate the original
    adjusted_participants = copy.deepcopy(participants)
    
    # Find the accepted participant
    target = next((p for p in adjusted_participants if p.name == accepted_target_name), None)
    
    if not target:
        return []
    
    # Phase 2 fallback: compute others' overlap
    others = [p for p in adjusted_participants if p.name != accepted_target_name]
    
    if len(others) < 2:
        return others[0].free_slots if others else []
    
    raw_overlaps = find_common_slots(others, min_duration_minutes=30)
    
    if not raw_overlaps:
        messages.append("⚠️ Post-negotiation: No overlap among remaining participants")
        return []
    
    constrained = apply_constraints(raw_overlaps, others)
    
    if constrained:
        messages.append(
            f"✅ Post-negotiation slots: "
            f"{[f'{s.day} {s.start_time}-{s.end_time}' for s in constrained]}"
        )
        return constrained
    else:
        messages.append(
            f"⚠️ Constraints still restrict — using raw overlap: "
            f"{[f'{s.day} {s.start_time}-{s.end_time}' for s in raw_overlaps]}"
        )
        return raw_overlaps


def negotiator_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Autonomous negotiation agent that resolves scheduling conflicts.
    Uses pre-calculated Python overlap data to prevent LLM hallucination.
    
    SAFEGUARD: Includes retry limits for LLM parsing to prevent infinite loops.
    """
    meeting_state = MeetingState(**state["meeting_state"])
    messages = state.get("messages", [])

    # Check if we can still negotiate
    if not meeting_state.can_negotiate():
        messages.append(
            f"❌ Negotiator: Max rounds "
            f"({meeting_state.max_negotiation_rounds}) reached"
        )
        meeting_state.status = "negotiation_failed"
        state["meeting_state"] = meeting_state.model_dump()
        state["messages"] = messages
        return state

    if not meeting_state.conflicts:
        messages.append("⚠️ Negotiator: No conflicts to negotiate")
        state["meeting_state"] = meeting_state.model_dump()
        state["messages"] = messages
        return state

    participants = meeting_state.participants

    messages.append(
        f"🤝 Negotiator: Starting negotiation round "
        f"{meeting_state.negotiation_rounds + 1}/"
        f"{meeting_state.max_negotiation_rounds}"
    )

    # Pre-compute all overlaps in Python
    pre_calculated_overlaps = compute_pre_calculated_overlaps(participants, messages)

    participant_summary = format_participant_summary(participants)
    conflicts_text = "\n".join([f"- {c}" for c in meeting_state.conflicts])
    history_text = format_negotiation_history(meeting_state.negotiation_history)

    prompt_template = load_prompt("negotiator.txt")

    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model_name = os.getenv("OLLAMA_MODEL", "deepseek-r1:7b")

    llm = ChatOllama(
        base_url=base_url,
        model=model_name,
        temperature=0.7
    )

    # SAFEGUARD: Maximum retry attempts for LLM parsing
    MAX_LLM_RETRIES = 2
    
    negotiation_data = None
    last_error = None
    
    for attempt in range(MAX_LLM_RETRIES + 1):
        try:
            PLACEHOLDER_SUMMARY = "<<<PARTICIPANT_SUMMARY>>>"
            PLACEHOLDER_CONFLICTS = "<<<CONFLICTS>>>"
            PLACEHOLDER_HISTORY = "<<<HISTORY>>>"
            PLACEHOLDER_OVERLAPS = "<<<PRE_COMPUTED_OVERLAPS>>>"

            formatted_prompt = (
                prompt_template
                .replace(PLACEHOLDER_SUMMARY, participant_summary)
                .replace(PLACEHOLDER_CONFLICTS, conflicts_text)
                .replace(PLACEHOLDER_HISTORY, history_text)
                .replace(PLACEHOLDER_OVERLAPS, pre_calculated_overlaps)
            )

            # Guard: verify all placeholders were replaced
            for placeholder in [
                PLACEHOLDER_SUMMARY,
                PLACEHOLDER_CONFLICTS,
                PLACEHOLDER_HISTORY,
                PLACEHOLDER_OVERLAPS,
            ]:
                if placeholder in formatted_prompt:
                    raise ValueError(
                        f"Placeholder {placeholder} not replaced in negotiator.txt"
                    )

            if attempt == 0:  # Only print on first attempt
                print("=" * 70)
                print("NEGOTIATOR PROMPT (first 800 chars):")
                print(formatted_prompt[:800], "...[truncated]")
                print("=" * 70)

            result = llm.invoke(formatted_prompt)
            content = result.content.strip()

            # Strip DeepSeek R1's  reasoning block
            content = re.sub(
                r"", 
                "", 
                content, 
                flags=re.DOTALL | re.IGNORECASE
            ).strip()

            print(f"\n[Ollama {model_name} Negotiator Output (attempt {attempt + 1})]:\n{content[:500]}...\n")

            # Extract JSON from markdown code fences
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            # Try parsing JSON
            negotiation_data = json.loads(content)
            
            # Success! Break out of retry loop
            break

        except json.JSONDecodeError as e:
            last_error = e
            if attempt < MAX_LLM_RETRIES:
                messages.append(
                    f"⚠️ Negotiator: JSON parse failed (attempt {attempt + 1}/"
                    f"{MAX_LLM_RETRIES + 1}), retrying..."
                )
                continue  # Retry with new LLM call
            else:
                # Max retries exhausted
                messages.append(
                    f"❌ Negotiator: Failed to parse LLM response after "
                    f"{MAX_LLM_RETRIES + 1} attempts - {str(e)}"
                )
                messages.append(f"   Last raw output: {content[:200]}")
                break

        except Exception as e:
            last_error = e
            messages.append(f"❌ Negotiator: Unexpected error on attempt {attempt + 1} - {str(e)}")
            if attempt < MAX_LLM_RETRIES:
                continue
            else:
                break

    # If all retries failed, use fallback
    if negotiation_data is None:
        messages.append("🔄 Negotiator: Switching to rule-based fallback selection")
        
        target = select_best_target(participants, meeting_state.negotiation_history)
        if target:
            fallback_message = (
                f"Hi {target.name}, could you adjust your availability "
                f"to help resolve this scheduling conflict?"
            )
            messages.append(
                f"🔄 Fallback: Asking {target.name} "
                f"(flexibility: {target.flexibility_score}/10)"
            )
            
            meeting_state.record_negotiation(
                target=target.name,
                message=fallback_message,
                result="fallback_used"
            )
        else:
            messages.append("❌ No suitable negotiation target found")
            meeting_state.status = "negotiation_failed"
        
        state["meeting_state"] = meeting_state.model_dump()
        state["messages"] = messages
        return state

    # Successfully parsed negotiation data
    try:
        target_name = negotiation_data.get("target")
        message = negotiation_data.get("message")
        reasoning = negotiation_data.get("reasoning")
        requested_change = negotiation_data.get("requested_change", "adjust schedule")

        messages.append(f"🎯 Target: {target_name}")
        messages.append(f"📝 Message: {message}")
        messages.append(f"💭 Reasoning: {reasoning}")

        target_participant = meeting_state.get_participant(target_name)

        if target_participant:
            import random

            # Calculate acceptance probability based on flexibility
            if target_participant.flexibility_score >= 8:
                accept_prob = 0.70
            elif target_participant.flexibility_score >= 5:
                accept_prob = 0.50
            else:
                accept_prob = 0.20

            # Reduce probability for repeated asks
            times_asked = sum(
                1 for entry in meeting_state.negotiation_history
                if entry.get("target") == target_name
            )
            accept_prob *= (0.7 ** times_asked)

            accepted = random.random() < accept_prob

            if accepted:
                result_text = "accepted"
                messages.append(f"✅ {target_name} accepted the request!")
                meeting_state.status = "negotiation_success"

                # Compute candidate slots after acceptance
                candidate_slots = compute_candidate_slots_after_acceptance(
                    participants, target_name, messages
                )

                if candidate_slots:
                    meeting_state.candidate_slots = candidate_slots
                    messages.append(
                        f"📅 {len(candidate_slots)} candidate slot(s) ready for ranking"
                    )
                else:
                    messages.append(
                        "⚠️ Accepted, but no overlap exists among remaining "
                        "participants — conflict may still be unresolvable"
                    )
                    meeting_state.status = "negotiating"
            else:
                result_text = "rejected"
                messages.append(f"❌ {target_name} declined the request")
                meeting_state.status = "negotiating"

        else:
            result_text = "target_not_found"
            messages.append(f"⚠️ Could not find participant '{target_name}'")

        # Record this negotiation attempt
        meeting_state.record_negotiation(
            target=target_name,
            message=message,
            result=result_text
        )

    except Exception as e:
        messages.append(f"❌ Negotiator: Error processing negotiation data - {str(e)}")
        meeting_state.status = "negotiation_failed"

    state["meeting_state"] = meeting_state.model_dump()
    state["messages"] = messages

    return state