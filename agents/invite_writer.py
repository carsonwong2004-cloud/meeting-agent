from typing import Dict, Any
from langchain_ollama import ChatOllama
import json
import os
import re
from models import MeetingState


def load_prompt(filename: str) -> str:
    """Load prompt template from file."""
    prompt_path = os.path.join("prompts", filename)
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def build_fallback_invite(meeting_state: MeetingState) -> Dict[str, Any]:
    """
    Rule-based fallback invite if LLM fails.
    Guaranteed to always produce a valid result.
    """
    slot = meeting_state.final_slot
    names = [p.name for p in meeting_state.participants]
    names_str = ", ".join(names)

    subject = f"Meeting Scheduled: {slot.day} {slot.start_time}-{slot.end_time}"

    body = (
        f"Hi {names_str},\n\n"
        f"We have found a common time slot for our meeting.\n\n"
        f"📅 When: {slot.day}, {slot.start_time} - {slot.end_time}\n"
        f"👥 Attendees: {names_str}\n\n"
        f"Please confirm your attendance. Looking forward to seeing everyone!"
    )

    return {
        "subject": subject,
        "body": body,
        "agenda_items": [
            "Welcome and introductions",
            "Main discussion topics",
            "Action items and next steps"
        ]
    }


def format_invite_text(invite_data: Dict[str, Any], meeting_state: MeetingState) -> str:
    """Format the final invite as a clean copyable text block."""
    slot = meeting_state.final_slot
    names = [p.name for p in meeting_state.participants]

    agenda_text = "\n".join([
        f"  {i+1}. {item}"
        for i, item in enumerate(invite_data.get("agenda_items", []))
    ])

    return (
        f"Subject: {invite_data['subject']}\n"
        f"\n"
        f"{invite_data['body']}\n"
        f"\n"
        f"📅 When: {slot.day}, {slot.start_time} - {slot.end_time}\n"
        f"👥 Who: {', '.join(names)}\n"
        f"\n"
        f"Agenda:\n{agenda_text}\n"
        f"\n"
        f"Please reply to confirm attendance."
    )


def invite_writer_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Invite Writer Agent: generates a polished meeting invitation
    from the final confirmed slot and participant list.

    Uses LLM for natural language generation with a rule-based fallback.
    """
    meeting_state = MeetingState(**state["meeting_state"])
    messages = state.get("messages", [])

    # Guard: only run if we have a final slot
    if not meeting_state.final_slot:
        messages.append("⚠️ Invite Writer: No final slot available, skipping")
        state["meeting_state"] = meeting_state.model_dump()
        state["messages"] = messages
        return state

    messages.append("✉️ Invite Writer: Generating meeting invitation...")

    # Build context for the prompt
    slot = meeting_state.final_slot
    slot_text = (
        f"Day: {slot.day}\n"
        f"Start: {slot.start_time}\n"
        f"End: {slot.end_time}\n"
        f"Duration: {slot.duration_minutes()} minutes"
    )

    participants_text = "\n".join([
        f"- {p.name}" + (f" (constraints: {', '.join(p.constraints)})" if p.constraints else "")
        for p in meeting_state.participants
    ])

    negotiation_rounds = str(meeting_state.negotiation_rounds)

    prompt_template = load_prompt("invite_writer.txt")

    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model_name = os.getenv("OLLAMA_MODEL", "deepseek-r1:7b")

    llm = ChatOllama(
        base_url=base_url,
        model=model_name,
        temperature=0.5  # Slightly creative but consistent
    )

    MAX_RETRIES = 2
    invite_data = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            PLACEHOLDER_SLOT = "<<<FINAL_SLOT>>>"
            PLACEHOLDER_PARTICIPANTS = "<<<PARTICIPANTS>>>"
            PLACEHOLDER_ROUNDS = "<<<NEGOTIATION_ROUNDS>>>"

            formatted_prompt = (
                prompt_template
                .replace(PLACEHOLDER_SLOT, slot_text)
                .replace(PLACEHOLDER_PARTICIPANTS, participants_text)
                .replace(PLACEHOLDER_ROUNDS, negotiation_rounds)
            )

            # Guard: verify all placeholders replaced
            for placeholder in [PLACEHOLDER_SLOT, PLACEHOLDER_PARTICIPANTS, PLACEHOLDER_ROUNDS]:
                if placeholder in formatted_prompt:
                    raise ValueError(
                        f"Placeholder {placeholder} not replaced in invite_writer.txt"
                    )

            result = llm.invoke(formatted_prompt)
            content = result.content.strip()

            # Strip DeepSeek R1's  reasoning block
            content = re.sub(
                r"",
                "",
                content,
                flags=re.DOTALL | re.IGNORECASE
            ).strip()

            print(f"\n[Invite Writer Output (attempt {attempt + 1})]:\n{content[:400]}...\n")

            # Extract JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            invite_data = json.loads(content)

            # Validate required fields
            if not all(k in invite_data for k in ["subject", "body", "agenda_items"]):
                raise ValueError("Missing required fields in LLM invite response")

            # Success
            break

        except json.JSONDecodeError as e:
            if attempt < MAX_RETRIES:
                messages.append(
                    f"⚠️ Invite Writer: JSON parse failed "
                    f"(attempt {attempt + 1}/{MAX_RETRIES + 1}), retrying..."
                )
                continue
            else:
                messages.append(
                    f"⚠️ Invite Writer: LLM failed after {MAX_RETRIES + 1} attempts, "
                    f"using template fallback"
                )
                invite_data = None

        except Exception as e:
            messages.append(f"⚠️ Invite Writer: Error on attempt {attempt + 1} - {str(e)}")
            if attempt < MAX_RETRIES:
                continue
            else:
                invite_data = None

    # Use fallback if LLM failed
    if invite_data is None:
        invite_data = build_fallback_invite(meeting_state)
        messages.append("🔄 Invite Writer: Using rule-based fallback template")

    # Format and store the final invite
    final_invite_text = format_invite_text(invite_data, meeting_state)
    meeting_state.final_message = final_invite_text

    messages.append("✅ Invite Writer: Meeting invitation generated successfully")
    messages.append(f"📧 Subject: {invite_data['subject']}")

    state["meeting_state"] = meeting_state.model_dump()
    state["messages"] = messages

    return state