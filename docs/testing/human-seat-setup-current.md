# Human Seat Selection

Base: immutable 67da698, with the published late-game AI repair unchanged.
The backend already accepts either controller assignment. The real application
formerly hardcoded the human to seat 1 in Player vs AI, leaving seat 2 inaccessible
from match setup despite the both-seat release requirement.

Match setup now offers Human seat 1 (Deck A) or 2 (Deck B) in Player vs AI only.
The public start payload uses the existing controller_a/controller_b fields.
Human vs Human and AI vs AI mappings stay unchanged. Changing seat invalidates
support review through the existing complete-wire signature; a pending uncertain
start retains its original request and key. Saved match restore derives the visible
human seat from the actual controller map, rather than silently reverting it.

Actual original Controls plus the NEW desired test failed at the missing human
seat control. The repaired real React controls pass both-seat callbacks, rejection
of unoffered seat values, mode boundaries and no default render mutation. Public
controller mappings, complete pending-start roundtrip and review invalidation pass.
The full configured npm test chain, lint, TypeScript build and production Vite
build all exited zero using the unchanged declared cached dependencies. No new
package was installed. The new control test is included in the configured chain.

The first full chain stopped because MTG_TEST_PYTHON was not supplied; the next
passed tests/lint but the build found an old typed Controls fixture missing new
required props. Both ledgers are retained. Only one setup line was added to that
human-vs-human fixture; every old assertion remains. The final full chain passed.

This is frontend component/payload acceptance, not a browser/API/SQLite or
natural game certificate. The final full built-app gate must exercise genuine
Player vs AI creation and play from both human seats. Backend rules, schemas,
AI weights, privacy projections and original controller admission are unchanged.
