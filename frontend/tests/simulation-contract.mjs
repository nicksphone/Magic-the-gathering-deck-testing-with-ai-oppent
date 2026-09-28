import assert from "node:assert/strict";
import { parseBatchJobStatus } from "../src/api/simulation-contract.ts";

const base = { job_id: "job-1", status: "running", completed_matches: 3, total_matches: 10, started_at: 1700000000, result: null };
assert.equal(parseBatchJobStatus(base), base);
const completed = { ...base, status: "completed", completed_matches: 10, result: { matches: 10, win_rate_deck_a: 60, win_rate_deck_b: 40 } };
assert.equal(parseBatchJobStatus(completed), completed);
assert.throws(() => parseBatchJobStatus({ ...base, completed_matches: 11 }), /status or progress/);
assert.throws(() => parseBatchJobStatus({ ...base, status: "unknown" }), /status or progress/);
assert.throws(() => parseBatchJobStatus({ ...completed, result: "done" }), /result must be an object/);
assert.throws(() => parseBatchJobStatus({ ...completed, result: { matches: 10 } }), /missing metrics/);
console.log("PASS simulation job response contract cases");
