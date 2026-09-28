import type { BatchSimulationJobStatus } from "./client";

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function parseBatchJobStatus(value: unknown): BatchSimulationJobStatus {
  if (!record(value) || typeof value.job_id !== "string" || !value.job_id
    || !["queued", "running", "completed", "failed"].includes(String(value.status))
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
  return value as BatchSimulationJobStatus;
}
