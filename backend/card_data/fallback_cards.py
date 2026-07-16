from __future__ import annotations

import re
from typing import Any


FALLBACK_CARD_DATA: dict[str, dict[str, Any]] = {
    # Blue Control
    "counterspell": {"mana_cost": "{U}{U}", "type_line": "Instant", "oracle_text": "Counter target spell."},
    "consider": {"mana_cost": "{U}", "type_line": "Instant", "oracle_text": "Draw a card."},
    "memory deluge": {"mana_cost": "{2}{U}{U}", "type_line": "Instant", "oracle_text": "Draw two cards."},
    "supreme verdict": {"mana_cost": "{1}{W}{W}{U}", "type_line": "Sorcery", "oracle_text": "Destroy all creatures."},
    "the wandering emperor": {"mana_cost": "{2}{W}{W}", "type_line": "Legendary Planeswalker", "oracle_text": "+1: Gain 2 life.", "loyalty": "3"},
    "teferi, hero of dominaria": {"mana_cost": "{3}{W}{U}", "type_line": "Legendary Planeswalker", "oracle_text": "+1: Draw a card.", "loyalty": "4"},
    "shark typhoon": {"mana_cost": "{5}{U}", "type_line": "Enchantment", "oracle_text": "Whenever you cast a noncreature spell, create a token."},
    "march of otherworldly light": {"mana_cost": "{X}{W}", "type_line": "Instant", "oracle_text": "Exile target artifact, creature, or enchantment."},
    "farewell": {"mana_cost": "{4}{W}{W}", "type_line": "Sorcery", "oracle_text": "Exile all creatures."},
    "clarion spirit": {"mana_cost": "{1}{W}", "type_line": "Creature", "oracle_text": "Whenever you cast your second spell each turn, create a 1/1 white Spirit creature token with flying.", "power": "2", "toughness": "2"},
    "march of the multitudes": {"mana_cost": "{X}{G}{W}{W}", "type_line": "Instant", "oracle_text": "Create X 1/1 white Soldier creature tokens with lifelink. Convoke."},
    "spectral procession": {"mana_cost": "{2/W}{2/W}{2/W}", "type_line": "Sorcery", "oracle_text": "Create three 1/1 white Spirit creature tokens with flying."},
    "adeline, resplendent cathar": {"mana_cost": "{1}{W}{W}", "type_line": "Legendary Creature", "oracle_text": "Vigilance. Adeline's power is equal to the number of creatures you control. Whenever you attack, for each opponent, create a 1/1 white Human creature token that's tapped and attacking that opponent.", "power": "*/4", "toughness": "4"},
    "boros charm": {"mana_cost": "{R}{W}", "type_line": "Instant", "oracle_text": "Choose one — Boros Charm deals 4 damage to target player or planeswalker; permanents you control gain indestructible until end of turn; or target creature gains double strike until end of turn."},
    "delver of secrets": {"mana_cost": "{U}", "type_line": "Creature", "oracle_text": "At the beginning of your upkeep, look at the top card of your library. You may reveal that card. If an instant or sorcery card is revealed this way, transform Delver of Secrets.", "power": "1", "toughness": "1"},
    "realmwalker": {"mana_cost": "{2}{G}", "type_line": "Creature", "oracle_text": "As Realmwalker enters the battlefield, choose a creature type. You may look at the top card of your library any time. You may cast creature spells of the chosen type from the top of your library.", "power": "2", "toughness": "3"},
    "llanowar elves": {"mana_cost": "{G}", "type_line": "Creature", "oracle_text": "{T}: Add {G}.", "power": "1", "toughness": "1"},
    "unholy heat": {"mana_cost": "{R}", "type_line": "Instant", "oracle_text": "Unholy Heat deals 2 damage to target creature or planeswalker. Delirium — It deals 6 damage instead if there are four or more card types among cards in your graveyard."},
    "sprite dragon": {"mana_cost": "{U}{R}", "type_line": "Creature", "oracle_text": "Flying, haste. Whenever you cast a noncreature spell, put a +1/+1 counter on Sprite Dragon.", "power": "1", "toughness": "1"},
    "elvish archdruid": {"mana_cost": "{1}{G}{G}", "type_line": "Creature", "oracle_text": "Other Elf creatures you control get +1/+1. {T}: Add {G} for each Elf you control.", "power": "2", "toughness": "2"},
    "elvish mystic": {"mana_cost": "{G}", "type_line": "Creature", "oracle_text": "{T}: Add {G}.", "power": "1", "toughness": "1"},
    "elvish warmaster": {"mana_cost": "{G}", "type_line": "Creature", "oracle_text": "Whenever one or more other Elves enter the battlefield under your control, create a 1/1 green Elf Warrior creature token. {3}{G}: Elves you control get +2/+2 and gain deathtouch until end of turn.", "power": "2", "toughness": "2"},
    "spell pierce": {"mana_cost": "{U}", "type_line": "Instant", "oracle_text": "Counter target noncreature spell unless its controller pays {2}."},
    "goblin guide": {"mana_cost": "{R}", "type_line": "Creature", "oracle_text": "Haste. Whenever Goblin Guide attacks, defending player reveals the top card of their library. That player may put that card into their hand if it's a land card.", "power": "2", "toughness": "2"},
    "intangible virtue": {"mana_cost": "{1}{W}", "type_line": "Enchantment", "oracle_text": "Creature tokens you control get +1/+1 and have vigilance."},
    "elvish clancaller": {"mana_cost": "{G}", "type_line": "Creature", "oracle_text": "Other Elves you control get +1/+1. {4}{G}{G}: Search your library for an Elf card, reveal it, put it into your hand, then shuffle.", "power": "1", "toughness": "1"},
    "monastery swiftspear": {"mana_cost": "{R}", "type_line": "Creature", "oracle_text": "Haste. Prowess.", "power": "1", "toughness": "2"},
    "wedding announcement": {"mana_cost": "{2}{W}", "type_line": "Enchantment", "oracle_text": "At the beginning of your end step, if you attacked with two or more creatures this turn, draw a card. Otherwise, create a 1/1 white Human creature token. Then if you control three or more creatures with different powers, transform Wedding Announcement."},
    "shaman of the pack": {"mana_cost": "{1}{B}{G}", "type_line": "Creature", "oracle_text": "When Shaman of the Pack enters the battlefield, target opponent loses life equal to the number of Elves you control.", "power": "3", "toughness": "2"},
    "hydroid krasis": {"mana_cost": "{X}{G}{U}", "type_line": "Creature", "oracle_text": "When you cast Hydroid Krasis, you gain half X life and draw half X cards, rounded down each time. Flying, trample.", "power": "0", "toughness": "0"},
    "deadly dispute": {"mana_cost": "{1}{B}", "type_line": "Instant", "oracle_text": "As an additional cost to cast this spell, sacrifice an artifact or creature. Draw two cards and create a Treasure token."},
    "dreadhorde butcher": {"mana_cost": "{B}{R}", "type_line": "Creature", "oracle_text": "Haste. Whenever Dreadhorde Butcher deals combat damage to a player or planeswalker, put that many +1/+1 counters on it.", "power": "1", "toughness": "1"},
    "expressive iteration": {"mana_cost": "{U}{R}", "type_line": "Sorcery", "oracle_text": "Look at the top three cards of your library. Put one of them into your hand, one on the bottom of your library, and one into exile. You may play the card exiled this way this turn."},
    "blood artist": {"mana_cost": "{1}{B}", "type_line": "Creature", "oracle_text": "Whenever Blood Artist or another creature dies, target player loses 1 life and you gain 1 life.", "power": "0", "toughness": "1"},
    "zulaport cutthroat": {"mana_cost": "{1}{B}", "type_line": "Creature", "oracle_text": "Whenever Zulaport Cutthroat or another creature you control dies, each opponent loses 1 life and you gain 1 life.", "power": "1", "toughness": "1"},
    "priest of forgotten gods": {"mana_cost": "{B}", "type_line": "Creature", "oracle_text": "{T}, Sacrifice two other creatures: Each opponent loses 2 life and sacrifices a creature. You add {B}{B} and draw a card.", "power": "1", "toughness": "2"},
    "village rites": {"mana_cost": "{B}", "type_line": "Instant", "oracle_text": "As an additional cost to cast this spell, sacrifice a creature. Draw two cards."},
    "cauldron familiar": {"mana_cost": "{B}", "type_line": "Creature", "oracle_text": "When Cauldron Familiar enters the battlefield, target opponent loses 1 life and you gain 1 life. Sacrifice a Food: Return Cauldron Familiar from your graveyard to the battlefield.", "power": "1", "toughness": "1"},
    "searing blaze": {"mana_cost": "{R}{R}", "type_line": "Instant", "oracle_text": "Searing Blaze deals 1 damage to target player and 1 damage to target creature that player controls. Landfall — If you had a land enter the battlefield under your control this turn, Searing Blaze deals 3 damage to that player and 3 damage to that creature instead."},
    "skullcrack": {"mana_cost": "{1}{R}", "type_line": "Instant", "oracle_text": "Skullcrack deals 3 damage to target player. Players can't gain life this turn. Damage can't be prevented this turn."},
    "go for the throat": {"mana_cost": "{1}{B}", "type_line": "Instant", "oracle_text": "Destroy target nonartifact creature."},
    "supreme verdict": {"mana_cost": "{1}{W}{W}{U}", "type_line": "Sorcery", "oracle_text": "Destroy all creatures. Supreme Verdict can't be countered."},
    "abrupt decay": {"mana_cost": "{B}{G}", "type_line": "Instant", "oracle_text": "Destroy target nonland permanent with mana value 3 or less."},
    "bloodtithe harvester": {"mana_cost": "{1}{B}", "type_line": "Creature", "oracle_text": "When Bloodtithe Harvester enters the battlefield, create a Blood token. {T}, Sacrifice Bloodtithe Harvester: Target creature gets -X/-X until end of turn, where X is twice the number of Blood tokens you control.", "power": "3", "toughness": "2"},
    "bonecrusher giant": {"mana_cost": "{2}{R}", "type_line": "Creature", "oracle_text": "When Bonecrusher Giant enters the battlefield, it deals 2 damage to target creature. Stomp is an Adventure. Damage can't be prevented this turn.", "power": "4", "toughness": "3"},
    "fable of the mirror-breaker": {"mana_cost": "{2}{R}", "type_line": "Enchantment", "oracle_text": "When this Saga enters and after your draw step, create a Goblin Shaman token. Then discard up to two cards and draw that many cards. Creatures you control get +2/+0.", "power": None, "toughness": None},
    "thoughtseize": {"mana_cost": "{B}", "type_line": "Sorcery", "oracle_text": "Target player reveals their hand. You choose a nonland card from it. That player discards that card and you lose 2 life."},
    "light up the stage": {"mana_cost": "{2}{R}", "type_line": "Sorcery", "oracle_text": "Exile the top two cards of your library. Until the end of your next turn, you may play those cards."},
    "kumano faces kakkazan": {"mana_cost": "{R}", "type_line": "Enchantment", "oracle_text": "When Kumano Faces Kakkazan enters the battlefield and at the beginning of your upkeep, it deals 1 damage to each opponent and each planeswalker they control. Creatures you control that entered the battlefield this turn have haste."},
    "soul-scar mage": {"mana_cost": "{R}", "type_line": "Creature", "oracle_text": "Prowess. Noncreature spells your opponents cast with power 4 or greater cost {2} more to cast.", "power": "1", "toughness": "2"},
    "tarmogoyf": {"mana_cost": "{1}{G}", "type_line": "Creature", "oracle_text": "Tarmogoyf's power is equal to the number of card types among cards in all graveyards and its toughness is equal to that number plus 1.", "power": "*/1", "toughness": "1/*"},
    "collected company": {"mana_cost": "{3}{G}", "type_line": "Instant", "oracle_text": "Look at the top six cards of your library. Put up to two creature cards with mana value 3 or less from among them onto the battlefield."},
    "witch's oven": {"mana_cost": "{1}", "type_line": "Artifact", "oracle_text": "{T}, Sacrifice a creature: Create a Food token."},
    "claim the firstborn": {"mana_cost": "{R}", "type_line": "Sorcery", "oracle_text": "Gain control of target creature with mana value 3 or less until end of turn. Untap that creature. It gains haste until end of turn."},
    "eidolon of the great revel": {"mana_cost": "{R}{R}", "type_line": "Creature", "oracle_text": "Whenever a player casts a spell with mana value 2 or less, Eidolon of the Great Revel deals 2 damage to that player.", "power": "2", "toughness": "2"},
    "secure the wastes": {"mana_cost": "{X}{W}", "type_line": "Instant", "oracle_text": "Create X 1/1 white Warrior creature tokens."},
    "raise the alarm": {"mana_cost": "{1}{W}", "type_line": "Instant", "oracle_text": "Create two 1/1 white Soldier creature tokens."},
    "brazen borrower": {"mana_cost": "{1}{U}{U}", "type_line": "Creature", "oracle_text": "Flash. Flying. Petty Theft is an Adventure. Return target nonland permanent an opponent controls to its owner's hand.", "power": "3", "toughness": "1"},
    "hopeful initiate": {"mana_cost": "{G}", "type_line": "Creature", "oracle_text": "Training. {2}{G}, Remove two +1/+1 counters from among creatures you control: Destroy target artifact or enchantment.", "power": "1", "toughness": "2"},
    "ossification": {"mana_cost": "{1}{W}", "type_line": "Enchantment", "oracle_text": "When Ossification enters the battlefield, exile target creature or planeswalker an opponent controls until Ossification leaves the battlefield."},
    "lay down arms": {"mana_cost": "{W}", "type_line": "Sorcery", "oracle_text": "Exile target creature or planeswalker with mana value less than or equal to the number of Plains you control. You gain 3 life."},
    "recruitment officer": {"mana_cost": "{1}{W}", "type_line": "Creature", "oracle_text": "{3}{W}: Look at the top four cards of your library. You may reveal a creature card with power 2 or less from among them and put it into your hand.", "power": "2", "toughness": "1"},
    "thalia, guardian of thraben": {"mana_cost": "{1}{W}", "type_line": "Legendary Creature", "oracle_text": "First strike. Noncreature spells cost {1} more to cast.", "power": "2", "toughness": "1"},
    "brutal cathar": {"mana_cost": "{2}{W}", "type_line": "Creature", "oracle_text": "When Brutal Cathar enters the battlefield, exile target creature an opponent controls until Brutal Cathar leaves the battlefield. Daybound.", "power": "2", "toughness": "2"},
    "island": {"mana_cost": "", "type_line": "Basic Land — Island", "oracle_text": "{T}: Add {U}."},
    "plains": {"mana_cost": "", "type_line": "Basic Land — Plains", "oracle_text": "{T}: Add {W}."},
    "hallowed fountain": {"mana_cost": "", "type_line": "Land — Plains Island", "oracle_text": "{T}: Add {W} or {U}."},
    # Ramp
    "arboreal grazer": {"mana_cost": "{G}", "type_line": "Creature", "oracle_text": "When Arboreal Grazer enters, you may put a land card from your hand onto the battlefield tapped.", "power": "0", "toughness": "3"},
    "growth spiral": {"mana_cost": "{G}{U}", "type_line": "Instant", "oracle_text": "Draw a card. You may put a land card from your hand onto the battlefield."},
    "cultivate": {"mana_cost": "{2}{G}", "type_line": "Sorcery", "oracle_text": "Search your library for lands."},
    "migration path": {"mana_cost": "{3}{G}", "type_line": "Sorcery", "oracle_text": "Search your library for lands."},
    "topiary stomper": {"mana_cost": "{2}{G}", "type_line": "Creature", "oracle_text": "Vigilance.", "power": "4", "toughness": "4"},
    "nissa, who shakes the world": {"mana_cost": "{3}{G}{G}", "type_line": "Legendary Planeswalker", "oracle_text": "Lands you control have '{T}: Add two mana of any one color.'\n+1: Put a +1/+1 counter on up to one target land you control. Untap it. It becomes a 0/0 Elemental creature with haste that's still a land.\n-3: You may put a green creature card from your hand onto the battlefield.", "loyalty": "5"},
    "ugin, the spirit dragon": {"mana_cost": "{8}", "type_line": "Legendary Planeswalker", "oracle_text": "+2: Deal 3 damage to target.", "loyalty": "7"},
    "hydroid krasis": {"mana_cost": "{X}{G}{U}", "type_line": "Creature", "oracle_text": "Flying, trample. When cast, draw a card and gain life.", "power": "4", "toughness": "4"},
    "storm the festival": {"mana_cost": "{3}{G}{G}{G}", "type_line": "Sorcery", "oracle_text": "Look at the top cards of your library."},
    "forest": {"mana_cost": "", "type_line": "Basic Land — Forest", "oracle_text": "{T}: Add {G}."},
    # Dimir / black interaction
    "fatal push": {"mana_cost": "{B}", "type_line": "Instant", "oracle_text": "Destroy target creature."},
    "drown in the loch": {"mana_cost": "{U}{B}", "type_line": "Instant", "oracle_text": "Counter target spell."},
    "sheoldred, the apocalypse": {"mana_cost": "{2}{B}{B}", "type_line": "Legendary Creature", "oracle_text": "Deathtouch. Whenever you draw a card, you gain 2 life. Whenever an opponent draws a card, that player loses 2 life.", "power": "4", "toughness": "5"},
    "the meathook massacre": {"mana_cost": "{X}{B}{B}", "type_line": "Legendary Enchantment", "oracle_text": "Destroy all creatures."},
    "torrential gearhulk": {"mana_cost": "{4}{U}{U}", "type_line": "Artifact Creature", "oracle_text": "Flash. When Torrential Gearhulk enters the battlefield, you may cast target instant card from your graveyard without paying its mana cost.", "power": "5", "toughness": "6"},
    "swamp": {"mana_cost": "", "type_line": "Basic Land — Swamp", "oracle_text": "{T}: Add {B}."},
}


def fallback_card_payload(name: str) -> dict[str, Any] | None:
    normalized = _normalize_card_name(name)
    if normalized in _NORMALIZED_FALLBACK_CARD_DATA:
        return _NORMALIZED_FALLBACK_CARD_DATA[normalized]
    for alias in _fallback_name_aliases(name):
        payload = _NORMALIZED_FALLBACK_CARD_DATA.get(alias)
        if payload is not None:
            return payload
    return None


def _normalize_card_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (name or "").strip().lower()).strip()


def _fallback_name_aliases(name: str) -> list[str]:
    raw = (name or "").strip()
    aliases: list[str] = []
    if "//" in raw:
        aliases.append(_normalize_card_name(raw.split("//", 1)[0]))
    return [alias for alias in aliases if alias]


_NORMALIZED_FALLBACK_CARD_DATA = {_normalize_card_name(name): payload for name, payload in FALLBACK_CARD_DATA.items()}
