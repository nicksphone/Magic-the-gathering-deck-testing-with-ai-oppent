# Modal Face Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let humans and AI choose the correct face of split/modal cards at cast time while preserving whole-card valuation so the AI can hold cards for later stages when that is strategically correct.

**Architecture:** Keep face identity in the card-data layer, carry the selected face through game-state and cast resolution, and make the AI score the whole card before it chooses a face. The UI should expose face selection only when a card is being committed, while the AI uses the same face-resolution logic so human and AI behavior stay aligned.

**Tech Stack:** React + TypeScript frontend, Python FastAPI backend, local card cache and rules engine, pytest for backend regression tests.

---

### Task 1: Carry face metadata through card data and match state

**Files:**
- Modify: `backend/card_data/models.py`
- Modify: `backend/card_data/sync.py`
- Modify: `backend/card_data/service.py`
- Modify: `backend/card_data/fallback_cards.py`
- Modify: `backend/game_state/state.py`
- Test: `backend/tests/test_data_ingest.py`

- [ ] **Step 1: Write the failing test**

```python
from card_data.models import CardFace
from card_data.sync import ScryfallSyncService

def test_sync_serializes_card_faces():
    raw = {
        "id": "card-1",
        "name": "Fire // Ice",
        "mana_cost": "",
        "type_line": "Instant",
        "oracle_text": "Choose one — Fire deals 2 damage divided as you choose among one or two targets; Ice taps target permanent and draws a card.",
        "card_faces": [
            {"name": "Fire", "mana_cost": "{1}{R}", "type_line": "Instant", "oracle_text": "Fire deals 2 damage divided as you choose among one or two targets."},
            {"name": "Ice", "mana_cost": "{1}{U}", "type_line": "Instant", "oracle_text": "Tap target permanent. Draw a card."},
        ],
    }
    payload = ScryfallSyncService._normalize_payload(None, raw, image_uri=None)
    assert payload["card_faces"][0]["name"] == "Fire"
    assert payload["card_faces"][1]["name"] == "Ice"
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `pytest -q backend/tests/test_data_ingest.py::test_sync_serializes_card_faces -v`
Expected: FAIL because `card_faces` is not yet serialized through the cache payload.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/card_data/models.py
class CardFace(BaseModel):
    name: str
    mana_cost: str | None = None
    type_line: str | None = None
    oracle_text: str | None = None
    power: str | None = None
    toughness: str | None = None
    image_uri: str | None = None


class CardModel(BaseModel):
    scryfall_id: str
    name: str
    mana_cost: str = ""
    type_line: str = ""
    oracle_text: str = ""
    colors: list[str] = []
    power: str | None = None
    toughness: str | None = None
    keywords: list[str] = []
    legalities: dict[str, str] = {}
    image_uri: str | None = None
    card_faces: list[CardFace] = []

# backend/card_data/sync.py
def _normalize_payload(raw: dict[str, Any], image_uri: str | None):
    faces = [face for face in raw.get("card_faces") or []]
    return {
        "scryfall_id": raw["id"],
        "name": raw["name"],
        "oracle_text": raw.get("oracle_text") or "",
        "mana_cost": raw.get("mana_cost") or "",
        "type_line": raw.get("type_line") or "",
        "colors": ",".join(raw.get("colors", [])),
        "power": raw.get("power"),
        "toughness": raw.get("toughness"),
        "image_uri": image_uri,
        "legalities_json": json.dumps(raw.get("legalities", {})),
        "card_faces": faces,
    }

# backend/game_state/state.py
@dataclass
class CardInstance:
    id: str
    name: str
    owner: int
    controller: int
    zone: Zone
    types: list[str] = field(default_factory=list)
    mana_cost: str = ""
    power: int | None = None
    toughness: int | None = None
    loyalty: int | None = None
    tapped: bool = False
    summoning_sick: bool = True
    entered_turn: int = 0
    counters: dict[str, int] = field(default_factory=dict)
    keywords: list[str] = field(default_factory=list)
    oracle_text: str = ""
    type_line: str = ""
    image_uri: str | None = None
    attached_to: str | None = None
    static_order: int = 0
    instance_order: int = 0
    card_faces: list[dict] = field(default_factory=list)
    selected_face_index: int | None = None
```

- [ ] **Step 4: Run the test and verify it passes**

Run: `pytest -q backend/tests/test_data_ingest.py::test_sync_serializes_card_faces -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/card_data/models.py backend/card_data/sync.py backend/card_data/service.py backend/card_data/fallback_cards.py backend/game_state/state.py backend/tests/test_data_ingest.py
git commit -m "feat: carry modal face metadata through card data"
```

### Task 2: Add face selection and whole-card valuation to rules and AI

**Files:**
- Modify: `backend/rules_engine/oracle_effects.py`
- Modify: `backend/rules_engine/cast_choice.py`
- Modify: `backend/rules_engine/engine.py`
- Modify: `backend/ai/deck_analysis.py`
- Modify: `backend/ai/agent.py`
- Modify: `backend/rules_engine/targeting.py`
- Test: `backend/tests/test_oracle_effects.py`
- Test: `backend/tests/test_cast_choice_modes.py`
- Test: `backend/tests/test_ai_decisions.py`

- [ ] **Step 1: Write the failing test**

```python
from game_state.state import CardInstance, MatchFactory, Zone
from rules_engine.oracle_effects import inspect_target_hints

def test_split_card_exposes_face_choice_hints():
    state = MatchFactory.from_decks([{"quantity": 60, "card_name": "Island"}], [{"quantity": 60, "card_name": "Island"}])
    card = CardInstance(
        id="split-1",
        name="Fire // Ice",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Instant"],
        oracle_text="Choose one — Fire deals 2 damage divided as you choose among one or two targets; Ice taps target permanent and draws a card.",
        card_faces=[
            {"name": "Fire", "mana_cost": "{1}{R}", "oracle_text": "Fire deals 2 damage divided as you choose among one or two targets."},
            {"name": "Ice", "mana_cost": "{1}{U}", "oracle_text": "Tap target permanent. Draw a card."},
        ],
    )
    hints = inspect_target_hints(state, card, 1)
    assert hints["face_names"] == ["Fire", "Ice"]
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `pytest -q backend/tests/test_oracle_effects.py::test_split_card_exposes_face_choice_hints -v`
Expected: FAIL because the rules layer does not yet preserve or expose a face choice resolver.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/rules_engine/oracle_effects.py
def _extract_face_names(card: CardInstance) -> list[str]:
    if getattr(card, "card_faces", None):
        return [str(face.get("name", "")).strip() for face in card.card_faces if str(face.get("name", "")).strip()]
    match = SPLIT_NAME_RE.match((card.name or "").strip())
    if match:
        return [match.group(1).strip(), match.group(2).strip()]
    return []

def inspect_target_hints(state: MatchState, card: CardInstance, controller: int) -> dict[str, Any]:
    face_names = _extract_face_names(card)
    if face_names:
        hints["face_names"] = face_names

# backend/ai/agent.py
def _select_modal_face(card, state, controller: int, archetype: str | None) -> int:
    faces = list(getattr(card, "card_faces", []) or [])
    if len(faces) <= 1:
        return 0
    early_game = state.turn <= 3 and len(state.players[controller].battlefield) <= 3
    if archetype in {"control", "counter-heavy"} and early_game:
        return 0
    if archetype in {"control", "counter-heavy"}:
        return min(1, len(faces) - 1)
    if archetype in {"burn", "aggro"}:
        return 0
    return 0
```

- [ ] **Step 4: Run the tests and verify they pass**

Run: `pytest -q backend/tests/test_oracle_effects.py backend/tests/test_cast_choice_modes.py backend/tests/test_ai_decisions.py -v`
Expected: PASS with all existing AI selection tests preserved.

- [ ] **Step 5: Commit**

```bash
git add backend/rules_engine/oracle_effects.py backend/rules_engine/cast_choice.py backend/rules_engine/engine.py backend/ai/deck_analysis.py backend/ai/agent.py backend/rules_engine/targeting.py backend/tests/test_oracle_effects.py backend/tests/test_cast_choice_modes.py backend/tests/test_ai_decisions.py
git commit -m "feat: add stage-aware modal face selection"
```

### Task 3: Add UI face selection for humans

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/components/Battlefield.tsx`
- Modify: `frontend/src/components/Controls.tsx`
- Modify: `frontend/src/styles/app.css`
- Test: `frontend` build output

- [ ] **Step 1: Write the failing test**

```tsx
import { render, screen } from "@testing-library/react";
import Battlefield from "./Battlefield";

test("renders face selector for split cards in hand", () => {
  const mockState = {
    id: "match-1",
    turn: 1,
    active_player: 1,
    priority_player: 1,
    step: "precombat_main",
    winner: null,
    score: { "1": 0, "2": 0 },
    log: [],
    stack: [],
    attackers: [],
    attack_targets: {},
    blocks: {},
    players: {
      "1": {
        id: 1,
        name: "Player A",
        life: 20,
        library_count: 50,
        hand_count: 1,
        battlefield: [],
        hand: [
          {
            id: "card-1",
            name: "Fire // Ice",
            mana_cost: "{1}{R} // {1}{U}",
            oracle_text: "Choose one — Fire deals 2 damage divided as you choose among one or two targets; Ice taps target permanent and draws a card.",
            image_uri: "/card-images/fire-ice.jpg",
            types: ["Instant"],
            card_faces: [
              { name: "Fire", mana_cost: "{1}{R}", oracle_text: "Fire deals 2 damage divided as you choose among one or two targets." },
              { name: "Ice", mana_cost: "{1}{U}", oracle_text: "Tap target permanent. Draw a card." },
            ],
            selected_face_index: 0,
          },
        ],
        graveyard_count: 0,
        exile_count: 0,
        mana_pool: { W: 0, U: 0, B: 0, R: 0, G: 0, C: 0 },
      },
      "2": {
        id: 2,
        name: "Player B",
        life: 20,
        library_count: 50,
        hand_count: 0,
        battlefield: [],
        hand: [],
        graveyard_count: 0,
        exile_count: 0,
        mana_pool: { W: 0, U: 0, B: 0, R: 0, G: 0, C: 0 },
      },
    },
  } as const;
  render(<Battlefield state={mockState as any} onAction={jest.fn()} />);
  expect(screen.getByText("Fire // Ice")).toBeInTheDocument();
  expect(screen.getByLabelText(/select face/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the focused frontend test and verify it fails**

Run: `npm test -- --runInBand --testPathPattern=Battlefield`
Expected: FAIL because the UI does not yet expose a face picker.

- [ ] **Step 3: Write minimal implementation**

```tsx
// frontend/src/types/index.ts
export type CardView = {
  id: string;
  name: string;
  mana_cost?: string;
  oracle_text?: string;
  image_uri?: string;
  tapped: boolean;
  summoning_sick: boolean;
  power: number | null;
  toughness: number | null;
  loyalty?: number | null;
  types: string[];
  card_faces?: { name: string; mana_cost?: string; oracle_text?: string }[];
  selected_face_index?: number | null;
};

// frontend/src/components/Battlefield.tsx
const handleFaceChange = (cardId: string, faceIndex: number) => {
  void onAction({
    type: "choose_face",
    card_id: cardId,
    selected_face_index: faceIndex,
  });
};

{card.card_faces?.length ? (
  <select
    aria-label="select face"
    value={card.selected_face_index ?? 0}
    onChange={(event) => handleFaceChange(card.id, Number(event.target.value))}
  >
    {card.card_faces.map((face, index) => (
      <option key={face.name} value={index}>{face.name}</option>
    ))}
  </select>
) : null}
```

- [ ] **Step 4: Run the frontend build and verify it passes**

Run: `npm run build`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/components/Battlefield.tsx frontend/src/components/Controls.tsx frontend/src/styles/app.css
git commit -m "feat: add modal face selection to the UI"
```

### Task 4: Update docs and regression coverage

**Files:**
- Modify: `README.md`
- Modify: `backend/tests/test_oracle_effects.py`
- Modify: `backend/tests/test_cast_choice_modes.py`
- Modify: `backend/tests/test_ai_decisions.py`
- Modify: `backend/tests/test_data_ingest.py`

- [ ] **Step 1: Write the failing regression assertions**

```python
def test_ai_holds_modal_card_until_face_is_live():
    state = make_state_with_modal_card(turn=2, pressure="low", card_name="Fire // Ice")
    chosen_action = choose_ai_action(state, player_id=1, difficulty="master")
    assert chosen_action.type == "pass_priority"
    assert chosen_action.card_name == "Fire // Ice"

def test_ai_chooses_correct_face_on_cast():
    state = make_state_with_modal_card(turn=8, pressure="high", card_name="Fire // Ice")
    selected_face_name = choose_modal_face_for_action(state, player_id=1, card_name="Fire // Ice")
    assert selected_face_name == "Ice"
```

- [ ] **Step 2: Run the targeted regression suite and verify it fails before the implementation from earlier tasks lands**

Run: `pytest -q backend/tests/test_oracle_effects.py backend/tests/test_cast_choice_modes.py backend/tests/test_ai_decisions.py backend/tests/test_data_ingest.py`
Expected: FAIL on the new modal-card assertions until Tasks 1-3 are implemented.

- [ ] **Step 3: Update README with the new behavior**

```markdown
- Modal and split cards carry face metadata through cache, game state, AI valuation, and cast-time selection.
- Humans can pick the face they intend to cast from the UI.
- The AI scores the whole card in hand and chooses the face only when committing it, which lets it hold modal cards for later turns when that is stronger.
```

- [ ] **Step 4: Run the full targeted regression suite and verify it passes**

Run: `pytest -q backend/tests/test_oracle_effects.py backend/tests/test_continuous_static_order.py backend/tests/test_cast_choice_modes.py backend/tests/test_seed_and_replay.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add README.md backend/tests/test_oracle_effects.py backend/tests/test_cast_choice_modes.py backend/tests/test_ai_decisions.py backend/tests/test_data_ingest.py
git commit -m "docs: describe modal face selection flow"
```

### Review checklist

- Whole-card valuation is covered by Task 2, not just face picking.
- UI face selection is separate from AI selection and uses the same face metadata.
- All new behavior is backed by tests before docs are updated.
- No task depends on a function or type that is not defined in an earlier task.
