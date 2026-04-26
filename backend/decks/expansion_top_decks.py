from __future__ import annotations

from decks.builtin_decks import BUILTIN_DECKS


def _entry(
    code: str,
    expansion: str,
    release_year: int,
    builtin_name: str,
    archetype: str,
) -> dict:
    return {
        "code": code.upper(),
        "expansion": expansion,
        "release_year": int(release_year),
        "deck_name": f"{expansion} Top {archetype}",
        "archetype": archetype,
        "deck_text": BUILTIN_DECKS[builtin_name].strip(),
        "reference_builtin": builtin_name,
    }


# Curated expansion-testing catalog.
# Each expansion points to a strong archetype profile that is currently supported
# by the simulator rules/AI and can be run in large regression suites.
EXPANSION_TOP_DECKS: list[dict] = [
    _entry("LEA", "Limited Edition Alpha", 1993, "Mono Red Aggro", "Aggro"),
    _entry("ARN", "Arabian Nights", 1993, "Tempo", "Tempo"),
    _entry("ATQ", "Antiquities", 1994, "Blue Control", "Control"),
    _entry("LEG", "Legends", 1994, "Midrange", "Midrange"),
    _entry("DRK", "The Dark", 1994, "Dimir Control", "Control"),
    _entry("ICE", "Ice Age", 1995, "Blue Control", "Control"),
    _entry("MIR", "Mirage", 1996, "Tempo", "Tempo"),
    _entry("TMP", "Tempest", 1997, "Burn", "Burn"),
    _entry("USG", "Urza's Saga", 1998, "Ramp", "Ramp"),
    _entry("INV", "Invasion", 2000, "Midrange", "Midrange"),
    _entry("ODY", "Odyssey", 2001, "Dimir Control", "Control"),
    _entry("ONS", "Onslaught", 2002, "Tribal", "Tribal"),
    _entry("MRD", "Mirrodin", 2003, "Drain Deck", "Aristocrats"),
    _entry("RAV", "Ravnica: City of Guilds", 2005, "Dimir Control", "Control"),
    _entry("TSP", "Time Spiral", 2006, "Blue Control", "Control"),
    _entry("LRW", "Lorwyn", 2007, "Tribal", "Tribal"),
    _entry("ALA", "Shards of Alara", 2008, "Midrange", "Midrange"),
    _entry("ZEN", "Zendikar", 2009, "Burn", "Aggro"),
    _entry("SOM", "Scars of Mirrodin", 2010, "Tempo", "Tempo"),
    _entry("ISD", "Innistrad", 2011, "Midrange", "Midrange"),
    _entry("RTR", "Return to Ravnica", 2012, "Blue Control", "Control"),
    _entry("THS", "Theros", 2013, "White Weenie", "Aggro"),
    _entry("KTK", "Khans of Tarkir", 2014, "Midrange", "Midrange"),
    _entry("BFZ", "Battle for Zendikar", 2015, "Ramp", "Ramp"),
    _entry("SOI", "Shadows over Innistrad", 2016, "Tempo", "Tempo"),
    _entry("KLD", "Kaladesh", 2016, "Tokens", "Tokens"),
    _entry("AKH", "Amonkhet", 2017, "Mono Red Aggro", "Aggro"),
    _entry("XLN", "Ixalan", 2017, "Tribal", "Tribal"),
    _entry("DOM", "Dominaria", 2018, "Blue Control", "Control"),
    _entry("GRN", "Guilds of Ravnica", 2018, "Dimir Control", "Control"),
    _entry("WAR", "War of the Spark", 2019, "Blue Control", "Control"),
    _entry("ELD", "Throne of Eldraine", 2019, "Midrange", "Midrange"),
    _entry("THB", "Theros Beyond Death", 2020, "White Weenie", "Aggro"),
    _entry("IKO", "Ikoria: Lair of Behemoths", 2020, "Tempo", "Tempo"),
    _entry("ZNR", "Zendikar Rising", 2020, "Ramp", "Ramp"),
    _entry("KHM", "Kaldheim", 2021, "Midrange", "Midrange"),
    _entry("STX", "Strixhaven: School of Mages", 2021, "Blue Control", "Control"),
    _entry("MID", "Innistrad: Midnight Hunt", 2021, "Tempo", "Tempo"),
    _entry("NEO", "Kamigawa: Neon Dynasty", 2022, "White Weenie", "Aggro"),
    _entry("SNC", "Streets of New Capenna", 2022, "Midrange", "Midrange"),
    _entry("DMU", "Dominaria United", 2022, "Dimir Control", "Control"),
    _entry("BRO", "The Brothers' War", 2022, "Ramp", "Ramp"),
    _entry("ONE", "Phyrexia: All Will Be One", 2023, "Mono Red Aggro", "Aggro"),
    _entry("MOM", "March of the Machine", 2023, "Tokens", "Tokens"),
    _entry("WOE", "Wilds of Eldraine", 2023, "Tempo", "Tempo"),
    _entry("LCI", "The Lost Caverns of Ixalan", 2023, "Tribal", "Tribal"),
    _entry("MKM", "Murders at Karlov Manor", 2024, "Dimir Control", "Control"),
    _entry("OTJ", "Outlaws of Thunder Junction", 2024, "Midrange", "Midrange"),
    _entry("BLB", "Bloomburrow", 2024, "Tokens", "Tokens"),
    _entry("DSK", "Duskmourn: House of Horror", 2024, "Tempo", "Tempo"),
    _entry("FDN", "Foundations", 2024, "White Weenie", "Aggro"),
    _entry("DFT", "Aetherdrift", 2025, "Mono Red Aggro", "Aggro"),
]


EXPANSION_TOP_DECKS_BY_CODE: dict[str, dict] = {d["code"]: d for d in EXPANSION_TOP_DECKS}
