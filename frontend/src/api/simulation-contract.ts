import type { BatchSimulationJobStatus, SimulationCoverage } from "./client";

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function parseSimulationCoverage(value: unknown): SimulationCoverage {
  if (!record(value) || value.status !== "exploratory"
    || !Array.isArray(value.known_unsupported_cards)
    || !value.known_unsupported_cards.every((item) => record(item)
      && ["A", "B"].includes(String(item.deck)) && typeof item.card_name === "string"
      && Array.isArray(item.mechanics) && item.mechanics.every((name) => typeof name === "string")
      && (item.static_clause_gaps === undefined || (Array.isArray(item.static_clause_gaps)
        && item.static_clause_gaps.every((gap) => record(gap)
          && typeof gap.clause === "string" && typeof gap.condition === "string"
          && typeof gap.face_name === "string"
          && (gap.face_index === null || (Number.isInteger(gap.face_index) && (gap.face_index as number) >= 0))
          && Array.isArray(gap.reasons) && gap.reasons.length > 0
          && gap.reasons.every((reason) => typeof reason === "string")))))) {
    throw new Error("Invalid simulation rules coverage response");
  }
  return value as SimulationCoverage;
}

export function parseBatchJobStatus(value: unknown): BatchSimulationJobStatus {
  if (!record(value) || typeof value.job_id !== "string" || !value.job_id
    || !["queued", "running", "completed", "failed", "canceled"].includes(String(value.status))
    || !Number.isInteger(value.completed_matches) || !Number.isInteger(value.total_matches)
    || (value.completed_matches as number) < 0 || (value.total_matches as number) < 1
    || (value.completed_matches as number) > (value.total_matches as number)
    || typeof value.started_at !== "number" || !Number.isFinite(value.started_at)) {
    throw new Error("Invalid simulation job response: status or progress fields");
  }
  if (value.result != null && !record(value.result)) {
    throw new Error("Invalid simulation job response: result must be an object");
  }
  if (value.status === "completed" && (!record(value.result)
    || typeof value.result.matches !== "number"
    || typeof value.result.win_rate_deck_a !== "number"
    || typeof value.result.win_rate_deck_b !== "number")) {
    throw new Error("Invalid simulation job response: completed result is missing metrics");
  }
  if (record(value.result) && value.result.rules_coverage !== undefined) {
    try {
      parseSimulationCoverage(value.result.rules_coverage);
    } catch {
      throw new Error("Invalid simulation job response: rules coverage");
    }
  }
  return value as BatchSimulationJobStatus;
}
