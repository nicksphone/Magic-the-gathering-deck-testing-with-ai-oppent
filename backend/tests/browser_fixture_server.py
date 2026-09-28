"""Loopback-only browser fixtures; never mount these routes in production."""
from collections import Counter
from pathlib import Path
if (Path(__file__).resolve().parents[2] / ".git").exists():
    raise RuntimeError("Run browser fixtures only from an isolated source copy, not the live Git checkout")
from main import app, ACTIVE_MATCHES, MatchController, get_match, _persist_active_match
from ai.agent import AIAgent
from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine
from persistence.db import init_db, engine
from persistence.repository import Repository
from sqlmodel import Session

init_db()


@app.post("/fixture/start-decks")
def fixture_start_decks():
    deck = [{"quantity": 60, "card_name": "Island"}]
    with Session(engine) as session:
        repo = Repository(session)
        a = repo.save_deck("Start retry A", "fixture", deck, [], "Control")
        b = repo.save_deck("Start retry B", "fixture", deck, [], "Control")
        return {"a": a.id, "b": b.id}


@app.post("/fixture")
def fixture(pregame: bool = False, modal: bool = False, modal_mana: int = 3, face_kind: str = ""):
    if face_kind == "draw_replacement":
        from effects.registry import resolve_effect
        deck = [{"quantity": 60, "card_name": "Island", "type_line": "Basic Land - Island"}]
        state = MatchFactory.from_decks(deck, deck, seed=35)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.active_player = state.priority_player = 2
        state.turn = 2
        state.step = Step.DRAW
        state.replacement_choice_required = True
        state.replacement_choice_players = {2}
        reflection = CardInstance(
            id="reflection", name="Thought Reflection", owner=2, controller=2,
            zone=Zone.BATTLEFIELD, types=["Enchantment"],
            oracle_text="If you would draw a card, draw two cards instead.",
        )
        dredger = CardInstance(
            id="stinkweed", name="Stinkweed Imp", owner=2, controller=2,
            zone=Zone.GRAVEYARD, types=["Creature"],
            oracle_text="Flying\nWhenever this creature deals combat damage to a creature, destroy that creature.\nDredge 5 (If you would draw a card, you may mill five cards instead. If you do, return this card from your graveyard to your hand.)",
        )
        state.cards.update({reflection.id: reflection, dredger.id: dredger})
        state.players[2].battlefield.append(reflection.id)
        state.players[2].graveyard.append(dredger.id)
        resolve_effect(state, 2, "draw_cards", {"amount": 1})
        return publish(state, deck)
    if face_kind == "company":
        from rules_engine.ability_model import build_ability_spec
        from rules_engine.stack_engine import add_to_stack, resolve_top_of_stack
        deck = [{"quantity": 60, "card_name": "Forest", "type_line": "Basic Land - Forest"}]
        state = MatchFactory.from_decks(deck, deck, seed=34)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.active_player = state.priority_player = 2
        state.step = Step.PRECOMBAT_MAIN
        state.replacement_choice_required = True
        state.replacement_choice_players = {2}
        for cid, name in zip(state.players[2].library[-6:],
            ["Grizzly Bears", "Llanowar Elves", "Island", "Plains", "Swamp", "Mountain"]):
            card = state.cards[cid]
            card.name = name
            if name in {"Grizzly Bears", "Llanowar Elves"}:
                card.types = ["Creature"]
                card.type_line = "Creature"
                card.mana_cost = "{1}{G}" if name == "Grizzly Bears" else "{G}"
                card.power = card.toughness = 2 if name == "Grizzly Bears" else 1
            else:
                card.types = ["Land"]
                card.type_line = f"Basic Land - {name}"
        spell = CardInstance(
            id="company", name="Collected Company", owner=2, controller=2,
            zone=Zone.STACK, types=["Instant"],
            oracle_text="Look at the top six cards of your library. Put up to two creature cards with mana value 3 or less from among them onto the battlefield. Put the rest on the bottom of your library in any order.",
        )
        state.cards[spell.id] = spell
        spec = build_ability_spec(state, spell, 2)
        add_to_stack(state, spell.id, 2, spell.name, spec.effect.key, spec.effect.payload)
        resolve_top_of_stack(state)
        return publish(state, deck)
    if face_kind == "iteration":
        from effects.registry import resolve_effect
        deck = [{"quantity": 60, "card_name": "Forest", "type_line": "Basic Land - Forest"}]
        state = MatchFactory.from_decks(deck, deck, seed=32)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.active_player = state.priority_player = 2
        state.step = Step.PRECOMBAT_MAIN
        state.replacement_choice_required = True
        state.replacement_choice_players = {2}
        for cid, name, cost, types in zip(state.players[2].library[-3:],
            ["Lightning Bolt", "Counterspell", "Llanowar Elves"],
            ["{R}", "{U}{U}", "{G}"], [["Instant"], ["Instant"], ["Creature"]]):
            card = state.cards[cid]
            card.name, card.mana_cost, card.types = name, cost, types
        resolve_effect(state, 2, "look_top_choose", {"top_n": 3})
        return publish(state, deck)
    if face_kind == "search":
        from effects.registry import resolve_effect
        deck = [{"quantity": 60, "card_name": "Forest", "type_line": "Basic Land - Forest"}]
        state = MatchFactory.from_decks(deck, deck, seed=33)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.active_player = state.priority_player = 2
        state.step = Step.PRECOMBAT_MAIN
        state.replacement_choice_required = True
        state.replacement_choice_players = {2}
        for cid, name, cost, power in zip(state.players[2].library[-2:],
            ["Llanowar Elves", "Grizzly Bears"], ["{G}", "{1}{G}"], [1, 2]):
            card = state.cards[cid]
            card.name, card.mana_cost, card.types = name, cost, ["Creature"]
            card.type_line = "Creature"
            card.power = card.toughness = power
        resolve_effect(state, 2, "search_library", {"contains": "creature", "destination": "hand", "count": 1, "shuffle": True})
        return publish(state, deck)
    if face_kind in {"bo3", "bo3_sideboard"}:
        deck = ([{"quantity": 45, "card_name": "Island", "type_line": "Basic Land - Island"},
                 {"quantity": 15, "card_name": "Mountain", "type_line": "Basic Land - Mountain"}]
                if face_kind == "bo3_sideboard" else
                [{"quantity": 60, "card_name": "Island", "type_line": "Basic Land - Island"}])
        state = MatchFactory.from_decks(deck, deck, seed=31)
        state.winner = 2 if face_kind == "bo3_sideboard" else 1
        state.score = {1: 0, 2: 1} if face_kind == "bo3_sideboard" else {1: 1, 2: 0}
        publish(state, deck)
        match = ACTIVE_MATCHES[state.id]
        match.current_game_recorded = True
        match.root_seed = 31
        if face_kind == "bo3_sideboard":
            match.sideboards[1] = [{"quantity": 15, "card_name": "Forest"}]
        with Session(engine) as session:
            _persist_active_match(Repository(session), match)
        return get_match(state.id)
    if face_kind in {"trigger", "cast_trigger"}:
        import json
        rows = json.loads((Path(__file__).parent / "fixtures/permanent_spell_context.json").read_text())
        deck = [{"quantity": 60, "card_name": "Island", "type_line": "Basic Land - Island"}]
        state = MatchFactory.from_decks(deck, deck, seed=17)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.active_player = state.priority_player = 2
        state.step = Step.PRECOMBAT_MAIN
        state.trigger_order_choice_required = True
        state.trigger_order_choice_players = {2}
        state.players[2].mana_pool.update({"G": 3, "C": 12 if face_kind == "cast_trigger" else 3})

        for cid, name, owner, zone in (
            ("cast-source" if face_kind == "cast_trigger" else "sage",
             "Ulamog, the Infinite Gyre" if face_kind == "cast_trigger" else "Reclamation Sage", 2, Zone.HAND),
            ("ring", "Sol Ring", 2, Zone.BATTLEFIELD),
            ("copter", "Smuggler's Copter", 1, Zone.BATTLEFIELD),
        ):
            row = rows[name]
            card = CardInstance(
                id=cid, name=name, owner=owner, controller=owner, zone=zone,
                types=row["type_line"].split(" — ")[0].split(),
                type_line=row["type_line"], oracle_text=row["oracle_text"],
                mana_cost=row["mana_cost"],
                power=int(row["power"]) if row["power"] else None,
                toughness=int(row["toughness"]) if row["toughness"] else None,
            )
            state.cards[cid] = card
            getattr(state.players[owner], zone.value).append(cid)
        return publish(state, deck)
    if face_kind == "alternative_target":
        from card_data.fallback_cards import fallback_card_payload

        deck = [{"quantity": 60, "card_name": "Mountain"}]
        state = MatchFactory.from_decks(deck, deck, seed=23)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.active_player = state.priority_player = 2
        state.step = Step.PRECOMBAT_MAIN
        state.players[2].mana_pool["R"] = 1
        spell = CardInstance(
            id="lava-spike", name="Lava Spike", owner=2, controller=2, zone=Zone.HAND,
            types=["Sorcery"], mana_cost="{R}",
            oracle_text="Lava Spike deals 3 damage to target player or planeswalker.",
        )
        walker = CardInstance(
            id="teferi", name="Teferi, Hero of Dominaria", owner=1, controller=1,
            zone=Zone.BATTLEFIELD, types=["Planeswalker"], loyalty=4,
            type_line="Legendary Planeswalker — Teferi",
            oracle_text=fallback_card_payload("Teferi, Hero of Dominaria")["oracle_text"],
        )
        state.cards.update({spell.id: spell, walker.id: walker})
        state.players[2].hand.append(spell.id)
        state.players[1].battlefield.append(walker.id)
        return publish(state, deck)
    if face_kind == "first_strike_window":
        deck = [{"quantity": 60, "card_name": "Island"}]
        state = MatchFactory.from_decks(deck, deck, seed=37)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.active_player = state.priority_player = 1
        state.step = Step.DECLARE_BLOCKERS
        swiftblade = CardInstance(
            id="swiftblade", name="Boros Swiftblade", owner=1, controller=1,
            zone=Zone.BATTLEFIELD, types=["Creature"], power=1, toughness=2,
            keywords=["double strike"], oracle_text="Double strike",
        )
        state.cards[swiftblade.id] = swiftblade
        state.players[1].battlefield.append(swiftblade.id)
        state.attackers = [swiftblade.id]
        state.attack_targets = {swiftblade.id: "player:2"}
        state.attackers_declared = True
        state.blockers_declared = True
        return publish(state, deck)
    if face_kind == "combat_damage_assignment":
        deck = [{"quantity": 60, "card_name": "Island"}]
        state = MatchFactory.from_decks(deck, deck, seed=83)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.mechanic_choice_players = {1, 2}
        state.active_player = state.priority_player = 1
        state.step = Step.DECLARE_BLOCKERS
        state.blockers_declared = True
        for cid, name, owner, power, toughness in (
            ("courser", "Centaur Courser", 1, 3, 3),
            ("bears", "Grizzly Bears", 2, 2, 2),
            ("giant", "Hill Giant", 2, 3, 3),
        ):
            card = CardInstance(
                id=cid, name=name, owner=owner, controller=owner, zone=Zone.BATTLEFIELD,
                types=["Creature"], power=power, toughness=toughness, summoning_sick=False,
            )
            state.cards[cid] = card
            state.players[owner].battlefield.append(cid)
        state.attackers = ["courser"]
        state.blocks = {"courser": ["bears", "giant"]}
        return publish(state, deck)
    if face_kind == "shared_trample":
        deck = [{"quantity": 60, "card_name": "Island"}]
        state = MatchFactory.from_decks(deck, deck, seed=89)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.mechanic_choice_players = {1, 2}
        state.active_player = state.priority_player = 1
        state.step = Step.DECLARE_BLOCKERS
        state.blockers_declared = True
        for cid, name, owner, power, toughness, keywords, oracle in (
            ("first", "Charging Monstrosaur", 1, 5, 5, ["trample", "haste"], "Trample, haste"),
            ("second", "Charging Monstrosaur", 1, 5, 5, ["trample", "haste"], "Trample, haste"),
            ("guard", "Palace Guard", 2, 1, 4, [], "Palace Guard can block any number of creatures."),
        ):
            card = CardInstance(
                id=cid, name=name, owner=owner, controller=owner, zone=Zone.BATTLEFIELD,
                types=["Creature"], power=power, toughness=toughness,
                keywords=keywords, oracle_text=oracle, summoning_sick=False,
            )
            state.cards[cid] = card
            state.players[owner].battlefield.append(cid)
        state.attackers = ["first", "second"]
        state.blocks = {"first": ["guard"], "second": ["guard"]}
        return publish(state, deck)
    if modal or face_kind:
        import json
        name = {"land": "Bala Ged Recovery // Bala Ged Sanctuary", "adventure": "Bonecrusher Giant // Stomp"}.get(face_kind, "Wandering Archaic // Explore the Vastlands")
        raw = json.loads((Path(__file__).parent / "fixtures/modal_spell_faces.json").read_text())[name]
        deck = [{"quantity": 60, "card_name": raw["name"], **raw["card_faces"][0], "layout": raw["layout"], "card_faces": raw["card_faces"]}]
        state = MatchFactory.from_decks(deck, deck, seed=9)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.active_player = state.priority_player = 2
        state.step = Step.PRECOMBAT_MAIN
        state.players[2].mana_pool["C"] = modal_mana
        if face_kind == "adventure":
            state.players[2].mana_pool["R"] = 4
        return publish(state, deck)
    deck = [{"quantity": 60, "card_name": "Island", "type_line": "Basic Land - Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=15)
    if pregame:
        state.kept_hands = {1}
        state.priority_player = 2
        state.mulligan_count[2] = 1
        return publish(state, deck)
    state.pregame_pending = False
    state.active_player = state.priority_player = 2
    state.step = Step.PRECOMBAT_MAIN
    state.players[2].hand = []
    state.players[2].mana_pool.update({"G": 3, "R": 3})

    def add(cid, name, zone, types, cost="", text="", power=None, toughness=None, type_line=""):
        card = CardInstance(id=cid, name=name, owner=2, controller=2, zone=zone, types=types, mana_cost=cost, oracle_text=text, power=power, toughness=toughness, type_line=type_line.replace(" - ", " \u2014 "), summoning_sick=False)
        state.cards[cid] = card
        getattr(state.players[2], zone.value).append(cid)
        return card

    add("forest", "Forest", Zone.HAND, ["Land"], type_line="Basic Land - Forest")
    add("pyromancer", "Prodigal Pyromancer", Zone.BATTLEFIELD, ["Creature"], "{2}{R}", "{T}: Prodigal Pyromancer deals 1 damage to any target.", 1, 1)
    add("bear", "Grizzly Bears", Zone.BATTLEFIELD, ["Creature"], "{1}{G}", power=2, toughness=2)
    add("copter", "Smuggler's Copter", Zone.BATTLEFIELD, ["Artifact"], "{2}", "Flying\nCrew 1", 3, 3, "Artifact - Vehicle")
    add("shock", "Shock", Zone.EXILE, ["Instant"], "{R}", "Shock deals 2 damage to any target.")
    state.players[2].exile_play_until["shock"] = state.turn
    walker = add("walker", "Realmwalker", Zone.BATTLEFIELD, ["Creature"], "{2}{G}", "You may cast creature spells of the chosen type from the top of your library.", 2, 3)
    walker.chosen_creature_type = "Elf"
    add("elf", "Llanowar Elves", Zone.LIBRARY, ["Creature"], "{G}", "{T}: Add {G}.", 1, 1, "Creature - Elf Druid")
    return publish(state, deck)


def publish(state, deck):
    ACTIVE_MATCHES.clear()
    ACTIVE_MATCHES[state.id] = MatchController(state=state, rules=RulesEngine(), controllers={1: "human", 2: "human"}, ai={1: AIAgent(), 2: AIAgent()}, mode="human_vs_human", deck_ids=(None, None), mainboards={1: deck, 2: deck}, sideboards={1: [], 2: []}, game_number=1, current_game_recorded=False, match_complete=False, best_of=3)
    with Session(engine) as session:
        _persist_active_match(Repository(session), ACTIVE_MATCHES[state.id])
    return get_match(state.id)


@app.get("/fixture/sideboard-pool/{match_id}")
def fixture_sideboard_pool(match_id: str):
    match = ACTIVE_MATCHES[match_id]
    player = match.state.players[1]
    return dict(Counter(match.state.cards[cid].name for cid in player.hand + player.library))
