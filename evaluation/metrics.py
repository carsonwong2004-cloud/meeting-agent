"""
Phase 4 Evaluation Metrics
Computes all WBS metrics: success rate, accuracy, negotiation efficiency.
"""

from typing import List, Dict, Any, Optional


def slot_matches_ground_truth(
    found_slot: Optional[Dict],
    expected_slot: Optional[Dict],
    tolerance_minutes: int = 30
) -> bool:
    """
    Check if a found slot matches the ground truth.
    Allows ±tolerance_minutes on start/end times.

    Args:
        found_slot:    dict with day, start_time, end_time (or None)
        expected_slot: dict with day, start_time, end_time (or None)
        tolerance_minutes: how many minutes off is still considered correct

    Returns:
        True if slot matches within tolerance
    """
    if expected_slot is None and found_slot is None:
        return True
    if expected_slot is None or found_slot is None:
        return False

    # Day must match exactly
    if found_slot.get("day", "").lower() != expected_slot.get("day", "").lower():
        return False

    # Convert times to minutes for comparison
    def to_minutes(t: str) -> int:
        h, m = map(int, t.split(":"))
        return h * 60 + m

    try:
        found_start = to_minutes(found_slot.get("start_time", "00:00"))
        found_end   = to_minutes(found_slot.get("end_time",   "00:00"))
        exp_start   = to_minutes(expected_slot.get("start_time", "00:00"))
        exp_end     = to_minutes(expected_slot.get("end_time",   "00:00"))
    except (ValueError, AttributeError):
        return False

    start_ok = abs(found_start - exp_start) <= tolerance_minutes
    end_ok   = abs(found_end   - exp_end)   <= tolerance_minutes

    return start_ok and end_ok


def compute_metrics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compute all Phase 4 metrics from a list of scenario results.

    Args:
        results: List of dicts, each containing:
            - scenario_id
            - ground_truth (from JSON)
            - system_output (from run_scheduler)

    Returns:
        Dict of all computed metrics
    """
    total = len(results)
    if total == 0:
        return {"error": "No results to evaluate"}

    # ── Counters ───────────────────────────────────────────────────────────────
    solvable_total          = 0
    solvable_resolved       = 0
    solvable_slot_correct   = 0

    impossible_total        = 0
    impossible_detected     = 0
    false_positives         = 0

    negotiation_rounds_list = []
    target_correct_count    = 0
    negotiation_needed      = 0

    errors = []

    for r in results:
        sid      = r.get("scenario_id", "?")
        gt       = r.get("ground_truth", {})
        output   = r.get("system_output", {})

        should_resolve = gt.get("should_resolve", False)
        req_neg        = gt.get("requires_negotiation", False)
        exp_target     = gt.get("expected_negotiation_target")
        exp_slot       = gt.get("expected_slot")

        # Parse system output
        final_slot         = output.get("final_slot")
        neg_rounds         = output.get("negotiation_rounds", 0)
        neg_history        = output.get("negotiation_history", [])
        status             = output.get("status", "")

        if "error" in output:
            errors.append({"id": sid, "error": output["error"]})
            continue

        # ── Solvable scenarios ─────────────────────────────────────────────────
        if should_resolve:
            solvable_total += 1

            if final_slot:
                solvable_resolved += 1

                # Check slot accuracy
                if slot_matches_ground_truth(final_slot, exp_slot):
                    solvable_slot_correct += 1

            # Negotiation metrics (only for scenarios that need it)
            if req_neg:
                negotiation_needed += 1
                negotiation_rounds_list.append(neg_rounds)

                # Check if correct target was asked first
                if neg_history and exp_target:
                    first_target = neg_history[0].get("target", "")
                    if first_target.lower() == exp_target.lower():
                        target_correct_count += 1

        # ── Impossible scenarios ───────────────────────────────────────────────
        else:
            impossible_total += 1

            # Correctly identified as impossible (no final_slot)
            if not final_slot:
                impossible_detected += 1
            else:
                # System claimed success on an impossible case
                false_positives += 1

    # ── Derived metrics ────────────────────────────────────────────────────────
    success_rate = (
        solvable_resolved / solvable_total * 100
        if solvable_total > 0 else 0.0
    )

    slot_accuracy = (
        solvable_slot_correct / solvable_resolved * 100
        if solvable_resolved > 0 else 0.0
    )

    impossible_detection_rate = (
        impossible_detected / impossible_total * 100
        if impossible_total > 0 else 0.0
    )

    false_positive_rate = (
        false_positives / impossible_total * 100
        if impossible_total > 0 else 0.0
    )

    avg_negotiation_rounds = (
        sum(negotiation_rounds_list) / len(negotiation_rounds_list)
        if negotiation_rounds_list else 0.0
    )

    targeting_accuracy = (
        target_correct_count / negotiation_needed * 100
        if negotiation_needed > 0 else 0.0
    )

    return {
        "summary": {
            "total_scenarios":      total,
            "errors":               len(errors),
            "evaluated":            total - len(errors)
        },
        "solvable": {
            "total":                solvable_total,
            "resolved":             solvable_resolved,
            "success_rate_pct":     round(success_rate, 1),
            "slot_accuracy_pct":    round(slot_accuracy, 1),
        },
        "impossible": {
            "total":                impossible_total,
            "correctly_detected":   impossible_detected,
            "detection_rate_pct":   round(impossible_detection_rate, 1),
            "false_positives":      false_positives,
            "false_positive_rate_pct": round(false_positive_rate, 1),
        },
        "negotiation": {
            "scenarios_requiring_negotiation": negotiation_needed,
            "avg_rounds_to_resolution":        round(avg_negotiation_rounds, 2),
            "targeting_accuracy_pct":          round(targeting_accuracy, 1),
        },
        "errors": errors
    }


def print_report(metrics: Dict[str, Any]) -> None:
    """Print a formatted evaluation report to the terminal."""
    print("\n" + "=" * 60)
    print("  PHASE 4 EVALUATION REPORT")
    print("=" * 60)

    s = metrics.get("summary", {})
    print(f"\n📊 OVERVIEW")
    print(f"   Total scenarios : {s.get('total_scenarios', 0)}")
    print(f"   Evaluated       : {s.get('evaluated', 0)}")
    print(f"   Errors          : {s.get('errors', 0)}")

    sv = metrics.get("solvable", {})
    print(f"\n✅ SOLVABLE SCENARIOS (n={sv.get('total', 0)})")
    print(f"   Success rate    : {sv.get('success_rate_pct', 0)}%")
    print(f"   Slot accuracy   : {sv.get('slot_accuracy_pct', 0)}%")
    print(f"   Resolved        : {sv.get('resolved', 0)}/{sv.get('total', 0)}")

    im = metrics.get("impossible", {})
    print(f"\n❌ IMPOSSIBLE SCENARIOS (n={im.get('total', 0)})")
    print(f"   Detection rate  : {im.get('detection_rate_pct', 0)}%")
    print(f"   False positives : {im.get('false_positives', 0)} "
          f"({im.get('false_positive_rate_pct', 0)}%)")

    ng = metrics.get("negotiation", {})
    print(f"\n🤝 NEGOTIATION")
    print(f"   Scenarios needing negotiation : {ng.get('scenarios_requiring_negotiation', 0)}")
    print(f"   Avg rounds to resolution      : {ng.get('avg_rounds_to_resolution', 0)}")
    print(f"   Target selection accuracy     : {ng.get('targeting_accuracy_pct', 0)}%")

    errors = metrics.get("errors", [])
    if errors:
        print(f"\n⚠️  ERRORS")
        for e in errors:
            print(f"   [{e['id']}] {e['error']}")

    print("\n" + "=" * 60 + "\n")