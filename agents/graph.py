from typing import Dict, Any, TypedDict, Literal
from langgraph.graph import StateGraph, END
from models import MeetingState
from .calendar_parser import calendar_parser_agent
from .conflict_checker import conflict_checker_agent
from .slot_suggester import slot_suggester_agent
from .negotiator import negotiator_agent
from .invite_writer import invite_writer_agent


class AgentState(TypedDict):
    """State passed between agents."""
    meeting_state: Dict[str, Any]
    messages: list[str]
    current_step: str


def should_negotiate(state: AgentState) -> Literal["negotiate", "suggest", "end"]:
    """
    Phase 2/3 routing: decide whether to negotiate, suggest, or end.

    SAFEGUARD: Strict conditions to prevent infinite loops.
    """
    meeting_state = MeetingState(**state["meeting_state"])

    # SAFEGUARD #1: Negotiation succeeded — go directly to suggester
    if meeting_state.status == "negotiation_success":
        return "suggest"

    # SAFEGUARD #2: Hard limit on negotiation rounds
    if meeting_state.negotiation_rounds >= meeting_state.max_negotiation_rounds:
        state["messages"].append(
            f"⚠️ Router: Max negotiation rounds "
            f"({meeting_state.max_negotiation_rounds}) reached, ending"
        )
        return "end"

    # SAFEGUARD #3: No conflicts → suggest or end
    if not meeting_state.has_conflicts():
        if meeting_state.candidate_slots:
            return "suggest"
        return "end"

    # SAFEGUARD #4: Conflicts exist and rounds remain → negotiate
    if meeting_state.has_conflicts() and meeting_state.can_negotiate():
        return "negotiate"

    # SAFEGUARD #5: Have slots despite conflicts → suggest
    if meeting_state.candidate_slots:
        return "suggest"

    return "end"


def after_negotiation_routing(state: AgentState) -> Literal["negotiate", "suggest", "end"]:
    """
    Routing after negotiation.

    SAFEGUARD: Prevents infinite loops with strict exit conditions.
    """
    meeting_state = MeetingState(**state["meeting_state"])

    # SAFEGUARD #1: Round limit always checked first
    if meeting_state.negotiation_rounds >= meeting_state.max_negotiation_rounds:
        state["messages"].append(
            f"⚠️ Router: Rounds exhausted "
            f"({meeting_state.negotiation_rounds}/"
            f"{meeting_state.max_negotiation_rounds}), forcing end"
        )
        return "end"

    if not meeting_state.negotiation_history:
        return "end"

    last_result = meeting_state.negotiation_history[-1].get("result", "")

    # SAFEGUARD #2: Accepted → suggest only if we have candidate slots
    if last_result == "accepted":
        if meeting_state.candidate_slots:
            return "suggest"
        state["messages"].append(
            "⚠️ Router: Accepted but no candidate slots computed, ending"
        )
        return "end"

    # SAFEGUARD #3: Rejected → retry if rounds remain
    elif last_result in ["rejected", "target_not_found", "fallback_used"]:
        if meeting_state.can_negotiate():
            return "negotiate"
        return "end"

    # SAFEGUARD #4: Unknown result → end to prevent loops
    else:
        state["messages"].append(
            f"⚠️ Router: Unknown result '{last_result}', ending to prevent loop"
        )
        return "end"


def create_scheduler_graph():
    """
    Phase 3 flow:
    calendar_parser
      → conflict_checker
        → [negotiate | suggest | end]
      negotiator
        → [suggest | negotiate | end]
      slot_suggester
        → invite_writer  ← NEW in Phase 3
          → END
    """
    workflow = StateGraph(AgentState)

    workflow.add_node("calendar_parser",  calendar_parser_agent)
    workflow.add_node("conflict_checker", conflict_checker_agent)
    workflow.add_node("negotiator",       negotiator_agent)
    workflow.add_node("slot_suggester",   slot_suggester_agent)
    workflow.add_node("invite_writer",    invite_writer_agent)   # NEW

    workflow.set_entry_point("calendar_parser")
    workflow.add_edge("calendar_parser", "conflict_checker")

    workflow.add_conditional_edges(
        "conflict_checker",
        should_negotiate,
        {
            "negotiate": "negotiator",
            "suggest":   "slot_suggester",
            "end":       END
        }
    )

    workflow.add_conditional_edges(
        "negotiator",
        after_negotiation_routing,
        {
            "suggest":   "slot_suggester",
            "negotiate": "negotiator",
            "end":       END
        }
    )

    # Phase 3: slot_suggester feeds into invite_writer before END
    workflow.add_edge("slot_suggester", "invite_writer")
    workflow.add_edge("invite_writer",  END)

    return workflow.compile()


def run_scheduler(raw_input: str) -> Dict[str, Any]:
    """Run the full scheduling workflow."""
    initial_state: AgentState = {
        "meeting_state": MeetingState(raw_input=raw_input).model_dump(),
        "messages": [],
        "current_step": "start"
    }

    graph = create_scheduler_graph()

    try:
        return graph.invoke(initial_state)
    except RecursionError as e:
        initial_state["messages"].append(
            f"❌ FATAL: Recursion limit exceeded — {str(e)}"
        )
        initial_state["meeting_state"]["status"] = "system_error"
        return initial_state
    except Exception as e:
        initial_state["messages"].append(f"❌ FATAL: {str(e)}")
        initial_state["meeting_state"]["status"] = "system_error"
        return initial_state