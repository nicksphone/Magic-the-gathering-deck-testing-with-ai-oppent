import assert from "node:assert/strict";
import { parseBatchJobStatus } from "../src/api/simulation-contract.ts";

const base = { job_id: "job-1", status: "running", completed_matches: 3, total_matches: 10, started_at: 1700000000, result: null };
assert.equal(parseBatchJobStatus(base), base);
const completed = { ...base, status: "completed", completed_matches: 10, result: { matches: 10, win_rate_deck_a: 60, win_rate_deck_b: 40 } };
assert.equal(parseBatchJobStatus(completed), completed);
const exploratory = { ...completed, result: { ...completed.result, rules_coverage: { status: "exploratory", known_unsupported_cards: [{ deck: "A", card_name: "Old Fogey", mechanics: ["bands with other"] }] } } };
assert.equal(parseBatchJobStatus(exploratory), exploratory);
assert.throws(() => parseBatchJobStatus({ ...exploratory, result: { ...exploratory.result, rules_coverage: { status: "certified", known_unsupported_cards: [] } } }), /rules coverage/);
assert.throws(() => parseBatchJobStatus({ ...base, completed_matches: 11 }), /status or progress/);
assert.throws(() => parseBatchJobStatus({ ...base, status: "unknown" }), /status or progress/);
assert.throws(() => parseBatchJobStatus({ ...completed, result: "done" }), /result must be an object/);
assert.throws(() => parseBatchJobStatus({ ...completed, result: { matches: 10 } }), /missing metrics/);
console.log("PASS simulation job response contract cases");
