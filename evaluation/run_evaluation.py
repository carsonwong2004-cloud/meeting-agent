"""
Phase 4 Evaluation Runner
Runs all 20 scenarios and outputs a metrics report + CSV results.
"""

import json
import os
import csv
import time
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.graph import run_scheduler
from models import MeetingState
from evaluation.metrics import compute_metrics, print_report


def load_scenarios(path: str = "data/real_scenarios.json") -> list:
    """Load scenarios from JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["scenarios"]


def run_single_scenario(scenario: dict) -> dict:
    """
    Run one scenario through the scheduler and collect results.

    Returns:
        dict with scenario_id, ground_truth, system_output, duration_seconds
    """
    scenario_id = scenario["id"]
    raw_input   = scenario["input"]
    ground_truth = scenario["ground_truth"]

    print(f"\n[{scenario_id}] Running: {scenario['description'][:60]}...")

    start_time = time.time()

    try:
        result = run_scheduler(raw_input)
        meeting_state = MeetingState(**result["meeting_state"])

        # Extract final slot as plain dict for comparison
        final_slot_dict = None
        if meeting_state.final_slot:
            final_slot_dict = {
                "day":        meeting_state.final_slot.day,
                "start_time": meeting_state.final_slot.start_time,
                "end_time":   meeting_state.final_slot.end_time
            }

        # First target asked (for targeting accuracy metric)
        first_target = None
        if meeting_state.negotiation_history:
            first_target = meeting_state.negotiation_history[0].get("target")

        system_output = {
            "status":               meeting_state.status,
            "final_slot":           final_slot_dict,
            "negotiation_rounds":   meeting_state.negotiation_rounds,
            "negotiation_history":  meeting_state.negotiation_history,
            "first_target_asked":   first_target,
            "participant_count":    len(meeting_state.participants),
            "conflicts_detected":   meeting_state.conflicts,
        }

        duration = round(time.time() - start_time, 2)
        resolved = "✅" if final_slot_dict else "❌"
        print(f"  {resolved} Status: {meeting_state.status} | "
              f"Slot: {final_slot_dict} | "
              f"Rounds: {meeting_state.negotiation_rounds} | "
              f"Time: {duration}s")

        return {
            "scenario_id":    scenario_id,
            "category":       scenario["category"],
            "description":    scenario["description"],
            "ground_truth":   ground_truth,
            "system_output":  system_output,
            "duration_seconds": duration,
            "messages":       result.get("messages", [])
        }

    except Exception as e:
        duration = round(time.time() - start_time, 2)
        print(f"  ❌ ERROR: {str(e)}")
        return {
            "scenario_id":    scenario_id,
            "category":       scenario.get("category", "unknown"),
            "description":    scenario.get("description", ""),
            "ground_truth":   ground_truth,
            "system_output":  {"error": str(e), "final_slot": None,
                               "negotiation_rounds": 0, "negotiation_history": []},
            "duration_seconds": duration,
            "messages":       []
        }


def save_results_csv(results: list, path: str = "evaluation/results.csv") -> None:
    """Save per-scenario results to CSV for further analysis."""
    os.makedirs(os.path.dirname(path), exist_ok=True)

    rows = []
    for r in results:
        gt = r["ground_truth"]
        so = r["system_output"]

        # Did the slot match?
        from evaluation.metrics import slot_matches_ground_truth
        slot_correct = slot_matches_ground_truth(
            so.get("final_slot"),
            gt.get("expected_slot")
        )

        # Was the first target correct?
        exp_target   = gt.get("expected_negotiation_target", "")
        first_target = so.get("first_target_asked", "")
        target_ok    = (
            exp_target and first_target and
            first_target.lower() == exp_target.lower()
        ) if exp_target else None

        rows.append({
            "scenario_id":          r["scenario_id"],
            "category":             r["category"],
            "should_resolve":       gt.get("should_resolve"),
            "resolved":             so.get("final_slot") is not None,
            "slot_correct":         slot_correct,
            "requires_negotiation": gt.get("requires_negotiation"),
            "negotiation_rounds":   so.get("negotiation_rounds", 0),
            "target_correct":       target_ok,
            "status":               so.get("status", ""),
            "duration_seconds":     r["duration_seconds"],
            "error":                so.get("error", "")
        })

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n📄 Results saved to {path}")


def save_results_json(results: list, path: str = "evaluation/results.json") -> None:
    """Save full results to JSON (includes messages for deep analysis)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)

    # Strip messages to keep file size manageable
    slim = []
    for r in results:
        slim.append({
            k: v for k, v in r.items() if k != "messages"
        })

    with open(path, "w", encoding="utf-8") as f:
        json.dump({"results": slim}, f, indent=2, ensure_ascii=False)

    print(f"📄 Full results saved to {path}")


def main():
    """Run all 20 scenarios and produce evaluation report."""
    print("=" * 60)
    print("  PHASE 4 EVALUATION — CAMPUS MEETING SCHEDULER")
    print("=" * 60)
    print(f"  Model: {os.getenv('OLLAMA_MODEL', 'deepseek-r1:7b')}")
    print(f"  Scenarios: 20")

    # Load scenarios
    scenarios = load_scenarios()
    print(f"\nLoaded {len(scenarios)} scenarios from data/real_scenarios.json")

    # Run all scenarios
    all_results = []
    total_start = time.time()

    for i, scenario in enumerate(scenarios, 1):
        print(f"\n── Scenario {i}/20 ──────────────────────────────────────")
        result = run_single_scenario(scenario)
        all_results.append(result)

    total_duration = round(time.time() - total_start, 1)
    print(f"\n⏱️  Total evaluation time: {total_duration}s "
          f"({round(total_duration/60, 1)} min)")

    # Compute metrics
    metrics = compute_metrics(all_results)

    # Print report to terminal
    print_report(metrics)

    # Save outputs
    save_results_csv(all_results)
    save_results_json(all_results)

    # Save metrics summary
    os.makedirs("evaluation", exist_ok=True)
    with open("evaluation/metrics_summary.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    print("📄 Metrics summary saved to evaluation/metrics_summary.json")


if __name__ == "__main__":
    main()