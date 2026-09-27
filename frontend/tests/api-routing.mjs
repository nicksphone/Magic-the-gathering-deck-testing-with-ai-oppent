import assert from "node:assert/strict";
import { apiBase, cardMediaUrl } from "../src/api/routing.ts";

assert.equal(apiBase(undefined), "/api");
assert.equal(apiBase(""), "/api");
assert.equal(apiBase("https://example.test:9999/"), "https://example.test:9999");
assert.equal(cardMediaUrl("/card-images/example.svg", apiBase()), "/card-images/example.svg");
assert.equal(cardMediaUrl("/card-images/example.svg", apiBase("https://example.test:9999")), "https://example.test:9999/card-images/example.svg");
assert.equal(cardMediaUrl("https://scryfall.test/card.jpg", apiBase()), "https://scryfall.test/card.jpg");
console.log("PASS same-origin and separate-backend routing cases");
