import assert from "node:assert/strict";
import { httpErrorMessage } from "../src/api/errors.ts";

assert.equal(httpErrorMessage('{"detail":{"code":"illegal_action","message":"Choose a target"}}', 422), "Choose a target");
assert.equal(httpErrorMessage('{"detail":[{"loc":["body","action","card_id"],"msg":"Field required"}]}', 422), "body.action.card_id: Field required");
assert.equal(httpErrorMessage('{"detail":"Match not found"}', 404), "Match not found");
assert.equal(httpErrorMessage("null", 500), "null");
assert.equal(httpErrorMessage('{"detail":[null,1,{"msg":42}]}', 500), '{"detail":[null,1,{"msg":42}]}');
assert.equal(httpErrorMessage("Bad gateway", 502), "Bad gateway");
assert.equal(httpErrorMessage("", 503), "HTTP 503");
console.log("PASS seven API error-boundary cases");
