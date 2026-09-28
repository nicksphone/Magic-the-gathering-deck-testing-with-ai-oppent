from types import SimpleNamespace

from rules_engine.card_types import is_land_card


def card(name, *, types=(), type_line="", mana_cost="", oracle_text=""):
    return SimpleNamespace(name=name, types=list(types), type_line=type_line, mana_cost=mana_cost, oracle_text=oracle_text)


def test_printed_land_types_and_metadata_poor_basic_names_are_lands():
    assert is_land_card(card("Hallowed Fountain", types=["Land"], type_line="Land — Plains Island"))
    assert is_land_card(card("Forest", type_line="Basic Land — Forest"))
    assert is_land_card(card("Forest"))
    assert is_land_card(card("Wastes"))


def test_mana_production_and_name_substrings_do_not_create_land_type():
    assert not is_land_card(card("Llanowar Elves", types=["Creature"], type_line="Creature — Elf Druid", mana_cost="{G}", oracle_text="{T}: Add {G}."))
    assert not is_land_card(card("Llanowar Elves", oracle_text="{T}: Add {G}."))
    assert not is_land_card(card("Island Sanctuary", types=["Enchantment"], type_line="Enchantment", mana_cost="{1}{W}"))
    assert not is_land_card(card("Forest", types=["Sorcery"]))
    assert not is_land_card(card("Bala Ged Recovery // Bala Ged Sanctuary", types=["Sorcery"], type_line="Sorcery // Land"))
