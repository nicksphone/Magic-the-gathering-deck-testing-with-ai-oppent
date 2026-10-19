"""Complete source admission through the unchanged mini-Factory callers.

RAW pins are independent printing-specific bulk pins, not hashes of a row
produced by the caller under test. Protocol corruptions are not card fixtures.
"""
from copy import deepcopy
import hashlib
import importlib
import json
import re

import pytest

from ai import sideboard_facts
from game_state.serializers import (
    deserialize_match_snapshot, serialize_match, serialize_match_snapshot,
)
from game_state.state import MatchFactory, Zone
from rules_engine.action_validation import ActionRejected
from rules_engine.copiable_values import values
from tests.browser_positive83_canonical import raw_card


# (name, printing ID, Oracle ID, canonical full-object SHA256, field count).
BINDINGS = {
    'wheel_draw': [
        ('Chandra Ablaze', '43da8995-77da-4ec4-94a5-5e7932a3c969', '3fae28e6-2ffc-460e-9dd3-e321e8a53ba9', 'c547447061f103c4ef8a2a1822055e53d687f28550aeabdf76e43d9861378734', 64),
        ('Char-Rumbler', '13f696f9-afa2-40c4-950a-e1e01c452017', '758aeca5-6ef3-4463-a65a-66b39289cc86', '9c8d34241e95ec52547f3d4ca14246d95c1eaed77a1fcb41dfdedc57835b3263', 66),
        ('Dark Deal', 'd6f0fcd5-232f-4e99-8cfc-ea0fe9c915a6', 'c527eb80-ccac-40b8-8377-c31121613128', '33fa795abe6542ed01641991fe75e86e87ad6892dbcda3759bd23ab2f54507b8', 64),
        ('Incendiary Command', '925d6ae9-deb8-41a4-99de-fd6fc6924d3b', 'd45a4924-daa0-4ac3-afd7-b66f636ce870', '05420910bb2dc694477c1bea7a6ba7fe91dfa22f5f06f811f480397eda1dddb7', 63),
        ('Maro', '9159e250-4eec-4ec4-80e1-42259331b3b9', 'ef32258a-d567-4fbc-ab85-8c00080f5b36', '039b8d7449910de813f30e6defc7a3527bde425f1b7ad5051f93219061b29bd6', 66),
        ('Megrim', '3b04fca4-b4de-4343-ba58-d8aea39edc19', '633ad9e2-9f55-4a1c-9248-661ad4b0e1dc', 'a76b42a5f71c1b73648f4b7f4be72e468443e052da08a655f2dc23c75decc4b6', 64),
        ('Sturmgeist', 'c409d1d0-fc45-40bf-adac-83b680209a38', 'b3045ee5-232b-4e63-8ea8-b5e46b49e71a', '17794b62b2b2466a7a395884b3fea471eb5ba3b35b6b5b263c1f1cb29fc9f32a', 65),
        ('Wheel of Fortune', '2597050f-6b1b-474e-aa16-33fd154628ca', 'a8abd966-de7b-46a3-8ac7-8747ab35653a', '8f0683b3a1c0e5351237163ab210343e2318190e60f30146e211bd313b82eb65', 61),
        ('Windfall', '9ce7113b-08f7-4584-b65f-a7b5caa90c2f', '08becc07-28bc-4a2f-a6b0-28a2998d2f50', 'd4713d964337380c92e0ac3bf74bb8e2e3a7fcf8ab897a72297b295f070301ee', 62),
    ],
    'conditional_static': [
        ('Abzan Kin-Guard', 'cec0ef55-57fd-404f-b9f6-b5d41e77b58c', 'b292d183-1ba9-40b4-9cba-bd70bf1380ef', '6bf19a15e9d1db09bfc1b4a1f607e6ba4e209f9d7652da494d9730bef3b77e07', 66),
        ('All Is Dust', '4210c54e-89fd-4971-ab6a-ca8f4e7fe97a', '14693689-d087-43b6-9c3f-63ab0648fc20', 'a6b9117eef0e56bf2ad95af46392257983c536c4182283095c6ec494f3369f12', 64),
        ('Ardent Recruit', '3a7f9bd7-7232-4956-873d-52ff82eabfb3', '9275108c-7eaf-4edd-aa6d-e5263d5ac7fd', '6c66469e14e97b874f20891e9817132ff61e4c5ae616a82fbff3cd0bf65ade78', 65),
        ('Auriok Sunchaser', 'e274a8b3-2d92-43d9-a436-d3f6f619ca95', '5e07d314-119f-4918-9105-77543ccae7e6', '0176769dabbbdf285071eae7509089a153d2d663d5ae3ebc49b2d62cb4f23382', 67),
        ('Carapace Forger', 'e9948e4c-d583-4fde-a305-df926cf00199', '9e623e0a-3c2d-4536-b12f-9437ef820499', 'b4e573ce3c8eab18850e858a732804c4797e904410282379f7baf5ace6756428', 67),
        ('Counterspell', '4f616706-ec97-4923-bb1e-11a69fbaa1f8', 'cc187110-1148-4090-bbb8-e205694a39f5', 'fe9513a8443f2f78ceb48e835c4e81d5b6d6eb995581683c73dfff9acecdb6b9', 62),
        ('Darksteel Citadel', '2ba7597d-6d76-45b8-b172-342999e401bd', '8dc067bf-f78f-4ac4-b6e7-b305c42cf0bc', 'a6ca5e5df1d81ab018919684c7c5a2a1e7115467ead1684ea09d01ae281f44fc', 64),
        ("Dragon's Rage Channeler", '4ced112a-e775-4f97-97b3-74877e9dce12', '0c016ccc-a341-4b76-87ba-69c639d2746d', 'f09ab0c063dd420bbbaa86ac56b352b87871f5540d108e908c7fe87f66e83a60', 64),
        ('Etched Champion', '30fe653b-956a-4e0e-981b-37e1a6b08c2c', '7cd7102d-6413-4f46-9434-9130aefa2f88', '02823839ba520c2003201e565e11c60c6eeca84f7c286e90288e2bbf48ec1146', 67),
        ('Forest', 'dce15387-4114-4b3e-91aa-5b42b45c44ac', 'b34bb2dc-c1af-4d77-b0b3-a0fb342a5fc6', 'f0e6aff0dd663be51328c1b6c07f9cec830d686cf543c66edcde5e5fa315b1e0', 60),
        ('Gathan Raiders', '58c232e5-54e2-44b7-85b1-ed039a8e5a73', '31ea0a21-9c47-4917-9df9-3469b6e5243d', '50b6404a57a7e363179d85c8cf055229e26c1459c4acf912319013ae592c8043', 66),
        ('Gnarlwood Dryad', '8eae5e38-49ee-49ef-87ca-7b570d9ca2b8', 'e823639f-1308-47f6-9b51-8fd9a682489a', 'fbd2c424b651527f9cee2d9e54266ce41cace224e32f9f65d3896dd33685b98e', 65),
        ('Grim Flayer', 'b29e5af4-feb6-485a-a631-bfc42fa1b13a', '21254bdb-7b1f-4ac6-8fdd-f0ac2c35f47d', '0358582f3605605c971bcfe190ff8a74967909605db639b6091a178d54a8aeca', 65),
        ('Grizzly Bears', '409f9b88-f03e-40b6-9883-68c14c37c0de', '14c8f55d-d177-4c25-a931-ebeb9e6062a0', '9512336fab43dd717c015655b9e5940d2aeea690795f11e4c16e9946565d465a', 66),
        ('Iymrith, Desert Doom', 'c3e6025d-d273-4ae4-9929-5e588612f1b3', 'd5efba91-8400-41a3-91c6-cb5e81f07976', '30f971644a120239d8838f05192f831be0d7cb1ecc6580bd8045be86f1801510', 68),
        ('Jor Kadeen, the Prevailer', '576d86b5-2541-4ebc-8992-73248af7c805', '7c4dbaa8-e24f-4126-81fe-3f218f520d8c', '09b070245f5c0ee56a8d2acc75fbb187e8ff81d125da02f3528502fb0026ecab', 67),
        ('K-9, Mark I', 'b2e46695-7bd3-448c-a5ea-6d544943ec5f', '413bc18b-1579-41b5-a778-3a29def52bb0', '7d73a100457b5360a817cee9b739ac15950de7e027abe2230ad8ba882031cb7e', 65),
        ('Krosan Beast', 'af822507-fd4c-454b-ab07-106c81c535bf', '042a665d-2f63-4f7e-ac89-0d560da68085', '8fc24945610090e458710299a49ce3de2b3008ff3177bd97c2e52d1134a1d1b8', 66),
        ('Lightning Bolt', '7673784e-db4b-43a1-8d55-1bb9fc1e284f', '4457ed35-7c10-48c8-9776-456485fdf070', 'faad8b64b05be249244f0fec337a2745c81e2cece5aae154536f5aa358e56f3e', 66),
        ('Moldgraf Scavenger', '76755763-7c02-451f-b799-2106a3a4973b', '558fe476-edbd-4f18-86ee-6d7f61331789', '9cf6e99dddf0e77b9bc26f6684fb6b1021da10b07d93054771a38c105a0fbab4', 66),
        ('Mountain', '2a844b96-6616-4c39-8f4f-5d14a3b2bd55', 'a3fb7228-e76b-4e96-a40e-20b5fed75685', 'b9dda46a4c5305f3ee220d17f93b150d284c0a43ddbdfa19d894523b0b7ab47d', 59),
        ('Mystic Enforcer', '187ebb67-1bdd-4a9c-aeeb-554e7580ce24', 'cf3b79cc-ce97-48e9-a578-625e323d1b62', '3edc5bc0789e4690611c6bf56cd20b6eec4f298d7c098d3cc65cb9d60a3d3f9e', 64),
        ('Mystic Zealot', '9bc955bd-b998-44b9-918f-84b96cf5e915', '5a47b99d-19dd-4830-89ee-35f4a74aa656', '270512861bc74e93f825c47c4709c5f6072a11701ef1a005f635319e8c22bd65', 64),
        ('Nimble Mongoose', '8a6374ad-71be-422e-bd76-4f08fbf43048', '1059f089-2693-4c89-92c5-39fe49beebb3', '17ba7e8f99590df9a74ec49f4d0564d0ea8e4d26e9b4b5c8369deaf8974792b6', 66),
        ('Plains', '8ab0f4c0-b331-4c57-b68f-2e24bb5ba06c', 'bc71ebf6-2056-41f7-be35-b2e5c34afa99', '96d267598e275ed64ad08a1390234dfc87cc50a29e14778c48d874b7344941b5', 59),
        ('Rakdos Pit Dragon', '6afb2e91-a864-4f77-9da5-2bae3f66a8a6', '63dd611e-1c36-4e5d-ba45-87c7f629cd54', '6c946cd149237ff9e33fb71cd86982be15dcbd0a9ebfc1bc283d9cd6fa81489a', 65),
        ('Savannah Lions', '9c9ac1bc-cdf3-4fa6-8319-a7ea164e9e47', '60ba93eb-39e6-4af2-9c66-cd38f72daff2', '4f63e62ecb0ea832696b9098cbfd7678fb14e1de31fedf0b143356c819ba9809', 68),
        ('Serra Ascendant', '0a22ee47-fc56-436d-8570-88fbff421027', '27ad3e00-6ffb-48f7-8469-8868d066d1e2', '8987267393587193536074204c175d449026be9e8f90c85392d1c80d7e8d3d56', 67),
        ('Werebear', '973310bb-ab32-46dc-8f59-8a5d3e1c58cc', '96cf3320-c730-4618-8768-28a179f4d9c0', 'e9f9571b5ef3b2508226d9bc8dc591f4d600d1e97d927d04566b1e921d069762', 66),
        ('Wild Nacatl', '5a3bb291-11d1-45e0-a60a-e75c7dc94b94', '35d3d96a-d303-4bf5-b972-f311331ec07a', '3e2d8b7b209431a75452f9d432de411e8bf058dc8d0a3ad986a069efdb10acf0', 66),
    ],
    'characteristic_stats': [
        ('All Is Dust', '4210c54e-89fd-4971-ab6a-ca8f4e7fe97a', '14693689-d087-43b6-9c3f-63ab0648fc20', 'a6b9117eef0e56bf2ad95af46392257983c536c4182283095c6ec494f3369f12', 64),
        ('Boneyard Wurm', '605038e9-2840-4c2d-bd7a-1004ae210e2a', '6e5f908a-f4f1-4718-ac39-34176e401756', '13d5fce7339ee0857855a5e9d6123e4294f9c882265a6a9c2b429d194a755568', 65),
        ('Consuming Aberration', '497fba45-201d-4688-b420-d093beb4e8f4', '9b55fb72-237d-4935-b645-8ebc6eb4140e', '28a126a338c503a2b1d2150591db7173140d0b344708190aae653c6404bb3336', 65),
        ('Counterspell', '4f616706-ec97-4923-bb1e-11a69fbaa1f8', 'cc187110-1148-4090-bbb8-e205694a39f5', 'fe9513a8443f2f78ceb48e835c4e81d5b6d6eb995581683c73dfff9acecdb6b9', 62),
        ('Darksteel Citadel', '2ba7597d-6d76-45b8-b172-342999e401bd', '8dc067bf-f78f-4ac4-b6e7-b305c42cf0bc', 'a6ca5e5df1d81ab018919684c7c5a2a1e7115467ead1684ea09d01ae281f44fc', 64),
        ("Death's Shadow", '5526ff6e-c079-4ad4-ac8d-5e26ecacf50d', 'e08722b3-0f79-4c82-b298-603e04a37857', '760d0369d25697ef3a4e01939fc753331467da56c2447c772001656d7c070a72', 67),
        ('Dryad Arbor', 'e3ddbebf-72cd-4d1b-ba0d-d94934654ab7', 'e996cd67-739c-40f4-b276-0042acf26c71', 'bb6228089ad901172d7b44a6733ef6df7048cc04b5bbb715a9d0ded54d5654a5', 67),
        ('Forest', 'dce15387-4114-4b3e-91aa-5b42b45c44ac', 'b34bb2dc-c1af-4d77-b0b3-a0fb342a5fc6', 'f0e6aff0dd663be51328c1b6c07f9cec830d686cf543c66edcde5e5fa315b1e0', 60),
        ('Grizzly Bears', '409f9b88-f03e-40b6-9883-68c14c37c0de', '14c8f55d-d177-4c25-a931-ebeb9e6062a0', '9512336fab43dd717c015655b9e5940d2aeea690795f11e4c16e9946565d465a', 66),
        ('Lhurgoyf', 'ea5d550a-bd8b-4f9e-ac7d-c35ebbe313e6', '0fe76004-b2f4-4b11-abce-75fd76f68b4d', 'e6ba8e38bbbbe53ba04b9f7df348cdb1e6cad2df9fa44fd42baf3b506aa3c888', 65),
        ('Lord of Extinction', '4aaf4d64-b5ef-44ae-b25a-7a5ea8f72170', 'ea5e3401-bd6c-47bb-a52a-8eec5f09455d', 'f07b25da404f61d7eab3cde63e4c1664aa28638465b0da4b135dafe5ef1e72f9', 66),
        ('Mortivore', 'beeaaef1-5cd9-402a-982e-2cb4e69cfaca', '2f554218-2072-4d9b-b4d4-34f161f1f2a9', '91a809cc60368adf6ef18ce8b3ab889f067ad385548b4e9b7dc838aadec92118', 65),
        ('Multani, Maro-Sorcerer', '0d6cc98b-b376-40af-8308-198bab00b2b1', 'bce5b327-7da1-4136-b76f-069e2fef5d2a', '9621bc276a7666f6726c8aac2f9979dacd7c56b67df290634c9334f12c04ee1b', 65),
        ("Multani, Yavimaya's Avatar", 'c37a0136-1c40-4cd1-8787-a25c377c1741', '4b8bf64b-4800-45ff-81c6-2857f34999b5', '19df60af068bcea90aad54e76d2530f0dd8f81efd821e9d7edf325f4354a5c36', 68),
        ('Nighthawk Scavenger', '47433ce9-1ac6-4359-a5e4-4ec68490cb0c', '379ed4ec-8f2e-448b-9ed2-a3181e2f877e', 'f7993d263d7617f843f016ec460410eed5949d8a6d33add4e7439e124b3f8397', 66),
        ('Overbeing of Myth', '11bbc404-a456-4a4b-af88-23921d80d671', '5391f601-b778-413f-a31f-9f8b23b40f5c', 'e742de6b37362c20e8fdd734f89c1b637649fc8d206f7220fc7a1480f7b90882', 66),
        ('Rubblehulk', 'e3bfd66f-8269-4765-87f3-38fcc25435be', '063960e0-3f9c-4697-ba5e-81c56ac1b5d2', 'b1c6ae9c1db97139d89d9cd3cd2cf378c65505fbcb007208bd8bb366c7342f91', 64),
        ('Tarmogoyf', '8be5ee47-8f8a-4e3c-b1a1-9ca0e1fdec7f', '45900b2f-f6a9-4c42-9642-008f3c1cf6dd', '214b12a777d137410686cc7b8d9226978f429b622c9e4724d5d3ad34de7c2ec0', 65),
        ('Terravore', 'b70fbe1c-d3f4-4e28-a830-2072dee1b7b5', 'f44fb61a-9aa5-4178-b958-5115d62a7f50', '1d42c104bcb58ea2007984b106b924be6d1370eae75f73eb226567bc0d1666ec', 63),
    ],
}
CALLERS = {
    'wheel_draw': 'canonical',
    'conditional_static': 'add',
    'characteristic_stats': 'add',
}
CASES = [(table, binding) for table, rows in BINDINGS.items() for binding in rows]

# Innate printed abilities only. Conditional grants and ability words remain
# in full RAW and are exercised by the original gameplay tests, not promoted
# to permanent keywords here. These goldens come from the printed clauses.
INNATE = {
    'Char-Rumbler': {'double strike'},
    'Darksteel Citadel': {'indestructible'},
    'Gnarlwood Dryad': {'deathtouch'},
    'Grim Flayer': {'trample'},
    'Iymrith, Desert Doom': {'flying'},
    'Jor Kadeen, the Prevailer': {'first strike'},
    'Multani, Maro-Sorcerer': {'shroud'},
    "Multani, Yavimaya's Avatar": {'reach', 'trample'},
    'Mystic Enforcer': {'protection from black'},
    'Nighthawk Scavenger': {'flying', 'deathtouch', 'lifelink'},
    'Nimble Mongoose': {'shroud'},
    'Serra Ascendant': {'lifelink'},
    'Sturmgeist': {'flying'},
    'Terravore': {'trample'},
}


def _digest(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
    ).encode()).hexdigest()


def _admitted(item, binding):
    name, printing_id, oracle_id, digest, fields = binding
    assert item['card_name'] == name and item['quantity'] == 1
    raw = {key: value for key, value in item.items()
           if key not in {'card_name', 'quantity'}}
    assert _digest(raw) == digest, 'Full printing-specific RAW must reach Factory'
    assert len(raw) == fields and raw['object'] == 'card'
    assert raw['name'] == name and raw['id'] == printing_id
    assert raw['oracle_id'] == oracle_id
    return raw


def _number(value):
    return int(value) if value is not None and re.fullmatch(r'[+-]?\d+', str(value)) else None


def _native_facts(card, raw):
    # All selected physical parents have independently verified normal layout.
    assert raw['layout'] == 'normal' and raw.get('card_faces', []) == []
    prefix = raw['type_line'].split('\u2014', 1)[0].split()
    types = [word for word in prefix if word in {
        'Artifact', 'Battle', 'Creature', 'Enchantment', 'Instant', 'Kindred',
        'Land', 'Planeswalker', 'Sorcery',
    }]
    expected = {
        'name': raw['name'], 'type_line': raw['type_line'], 'types': types,
        'mana_cost': raw.get('mana_cost') or '',
        'oracle_text': raw.get('oracle_text') or '', 'colors': raw['colors'],
        'power': _number(raw.get('power')), 'toughness': _number(raw.get('toughness')),
        'printed_power': raw.get('power'), 'printed_toughness': raw.get('toughness'),
        'loyalty': _number(raw.get('loyalty')),
    }
    for key, golden in expected.items():
        actual = getattr(card, key)
        assert type(actual) is type(golden), f'Live scalar/list type: {key}'
        if type(golden) is list:
            assert all(type(item) is str for item in actual), f'Live list item type: {key}'
    assert {key: getattr(card, key) for key in expected} == expected
    innate = INNATE.get(raw['name'], set())
    assert type(card.keywords) is list and all(type(item) is str for item in card.keywords)
    assert set(card.keywords) == innate and len(card.keywords) == len(innate)
    record = card.characteristic_record
    assert type(record) is dict, 'Retained record must be an exact dict'
    assert type(record.get('version')) is int, 'Retained record version must be an exact int'
    assert set(record) == {'version', 'physical', 'values'} and record['version'] == 1
    for section in ('physical', 'values'):
        assert type(record[section]) is dict, f'Retained {section} must be an exact dict'
        for key, golden in expected.items():
            actual = record[section][key]
            assert type(actual) is type(golden), f'Retained {section} scalar/list type: {key}'
            if type(golden) is list:
                assert all(type(item) is str for item in actual), f'Retained {section} list item type: {key}'
        assert {key: record[section][key] for key in expected} == expected
        assert type(record[section]['keywords']) is list
        assert all(type(item) is str for item in record[section]['keywords'])
        assert set(record[section]['keywords']) == innate
        assert len(record[section]['keywords']) == len(innate)
    for key, golden in {'card_faces': [], 'layout': 'normal',
                        'selected_face_index': None, 'image_uri': None}.items():
        assert type(record['physical'][key]) is type(golden), f'Retained physical type: {key}'
    assert {key: record['physical'][key] for key in (
        'card_faces', 'layout', 'selected_face_index', 'image_uri',
    )} == {'card_faces': [], 'layout': 'normal', 'selected_face_index': None,
          'image_uri': None}
    assert type(card.card_faces) is list and type(card.layout) is str
    assert card.card_faces == [] and card.layout == 'normal'
    assert card.selected_face_index is None
    assert card.image_uri is None


def _instrument(monkeypatch, binding):
    real_factory, real_capture = MatchFactory.from_decks, sideboard_facts.initialize
    forwarded, captures = [], []

    def capture(state, inventory):
        assert len(forwarded) == 1
        raw = forwarded[0]
        assert inventory == {'p1-001': {'owner': 1, 'stock_key': raw['name']}}
        assert state.starting_decks == {
            1: [{**raw, 'card_name': raw['name'], 'quantity': 1}], 2: [],
        }
        card = state.cards['p1-001']
        assert card.owner == card.controller == 1 and card.zone == Zone.LIBRARY
        _native_facts(card, raw)
        captures.append(deepcopy(card.characteristic_record))
        return real_capture(state, inventory)

    def factory(a, b, *args, **kwargs):
        assert len(a) == 1 and b == [] and args == () and kwargs == {'seed': 7}
        raw = _admitted(a[0], binding)
        forwarded.append(deepcopy(raw))
        return real_factory(a, b, *args, **kwargs)

    monkeypatch.setattr(MatchFactory, 'from_decks', staticmethod(factory))
    monkeypatch.setattr(sideboard_facts, 'initialize', capture)
    return forwarded, captures


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('table,binding', CASES,
                         ids=[f'{table}:{binding[0]}' for table, binding in CASES])
def test_full_raw_reaches_original_factory_capture_and_snapshot(monkeypatch, table, binding, seat):
    module = importlib.import_module('tests.test_' + table)
    state = module.board(seat)
    stock, decks = deepcopy(state.sideboard_facts), deepcopy(state.starting_decks)
    old_cards, pool = set(state.cards), deepcopy(state.players[seat].mana_pool)
    forwarded, captures = _instrument(monkeypatch, binding)
    card = getattr(module, CALLERS[table])(state, binding[0], seat, Zone.HAND)
    assert len(forwarded) == len(captures) == 1
    _native_facts(card, forwarded[0])
    assert card.characteristic_record == captures[0]
    assert set(state.cards) - old_cards == {card.id}
    assert card is state.cards[card.id] and card.id in state.players[seat].hand
    assert card.owner == card.controller == seat and card.zone == Zone.HAND
    assert state.players[seat].mana_pool == pool
    # Appended mini-Factory cards do NOT become original match stock.
    assert state.sideboard_facts == stock and state.starting_decks == decks
    before = deepcopy(serialize_match_snapshot(state))
    restored = deserialize_match_snapshot(deepcopy(before))
    assert serialize_match_snapshot(restored) == before
    assert serialize_match_snapshot(state) == before
    _native_facts(restored.cards[card.id], forwarded[0])
    assert restored.sideboard_facts == stock and restored.starting_decks == decks
    public = serialize_match(restored)
    assert 'sideboard_facts' not in public and 'starting_decks' not in public
    restored.cards[card.id].characteristic_record['values']['keywords'].append(
        'explicit-invalid-protocol-mutation')
    assert serialize_match_snapshot(state) == before
    assert _digest(module.ROWS[binding[0]]) == binding[3]


@pytest.mark.parametrize('field,bad', [
    ('oracle_text', 'Explicit invalid protocol suffix.'),
    ('mana_cost', '{R}'), ('type_line', 'Creature'), ('colors', ['R']),
    ('keywords', ['Flying']), ('id', 'explicit-invalid-printing'),
    ('layout', 'transform'), ('card_faces', [{'invalid_protocol': True}]),
])
def test_corrupted_full_control_is_rejected_before_real_factory(monkeypatch, field, bad):
    from tests import test_conditional_static as module
    binding = next(row for row in BINDINGS['conditional_static'] if row[0] == 'Counterspell')
    # Reuse independently pinned, committed full RAW in BOTH source stages.
    raw = raw_card('Counterspell')
    assert _admitted({**raw, 'card_name': raw['name'], 'quantity': 1}, binding) == raw
    corrupt = deepcopy(raw)
    assert corrupt.get(field) != bad
    corrupt[field] = bad
    state = module.board()
    before = deepcopy(serialize_match_snapshot(state))
    monkeypatch.setitem(module.ROWS, raw['name'], corrupt)
    forwarded, captures = _instrument(monkeypatch, binding)
    with pytest.raises(AssertionError, match='Full printing-specific RAW'):
        module.add(state, raw['name'])
    assert forwarded == captures == []
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('fault', ['version', 'missing_value', 'bool_stat'])
def test_malformed_retained_records_fail_closed_at_native_consumer(monkeypatch, seat, fault):
    from tests import test_conditional_static as module
    binding = next(row for row in BINDINGS['conditional_static'] if row[0] == 'Counterspell')
    raw = raw_card('Counterspell')
    _admitted({**raw, 'card_name': raw['name'], 'quantity': 1}, binding)
    state = module.board(seat)
    monkeypatch.setitem(module.ROWS, raw['name'], deepcopy(raw))
    card = module.add(state, raw['name'], seat, Zone.HAND)
    assert values(card)['name'] == raw['name']
    if fault == 'version':
        card.characteristic_record['version'] = 2
    elif fault == 'missing_value':
        del card.characteristic_record['values']['mana_cost']
    else:
        card.characteristic_record['values']['power'] = True
    before = deepcopy(card.__dict__)
    stock = deepcopy(state.sideboard_facts)
    with pytest.raises(ActionRejected, match='retained physical and copiable'):
        values(card)
    assert card.__dict__ == before and state.sideboard_facts == stock


def _real_scalar_control(name, seat):
    # Existing printing-specific loader verifies full RAW and its source manifest.
    raw = raw_card(name)
    deck = [{**deepcopy(raw), 'card_name': raw['name'], 'quantity': 1}]
    state = MatchFactory.from_decks(deck if seat == 1 else [],
                                    deck if seat == 2 else [], seed=7)
    return state, state.cards[f'p{seat}-001'], raw


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Grizzly Bears', 'Llanowar Elves'])
def test_exact_typed_oracle_accepts_real_unmodified_full_raw_factory_control(seat, name):
    state, card, raw = _real_scalar_control(name, seat)
    before = deepcopy(serialize_match_snapshot(state))
    _native_facts(card, raw)
    assert values(card) == card.characteristic_record['values']
    assert (card.owner, card.controller) == (seat, seat)
    assert (raw['power'], raw['toughness']) == (('2', '2') if name == 'Grizzly Bears' else ('1', '1'))
    assert type(card.power) is type(card.toughness) is int
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,fault', [
    ('Grizzly Bears', 'bool_version'), ('Grizzly Bears', 'float_version'),
    ('Grizzly Bears', 'float_power'), ('Grizzly Bears', 'float_toughness'),
    ('Llanowar Elves', 'bool_power'), ('Llanowar Elves', 'bool_toughness'),
    ('Grizzly Bears', 'record_dict_subclass'),
    ('Grizzly Bears', 'physical_dict_subclass'), ('Grizzly Bears', 'values_dict_subclass'),
    ('Grizzly Bears', 'types_item_subclass'), ('Grizzly Bears', 'colors_item_subclass'),
    ('Grizzly Bears', 'keywords_tuple'), ('Grizzly Bears', 'layout_subclass'),
])
def test_typed_oracle_rejects_equal_valued_protocol_mutants_without_repair(seat, name, fault):
    # These are explicit negative protocol mutations AFTER genuine Factory birth.
    class ProtocolDict(dict):
        pass

    class ProtocolText(str):
        pass

    state, card, raw = _real_scalar_control(name, seat)
    _native_facts(card, raw)
    if fault.endswith('_version'):
        card.characteristic_record['version'] = True if fault == 'bool_version' else 1.0
    elif fault.startswith(('float_', 'bool_')):
        kind, field = fault.split('_', 1)
        bad = float(getattr(card, field)) if kind == 'float' else True
        assert bad == getattr(card, field) and type(bad) is not type(getattr(card, field))
        setattr(card, field, bad)
        for section in ('physical', 'values'):
            card.characteristic_record[section][field] = bad
    elif fault == 'record_dict_subclass':
        card.characteristic_record = ProtocolDict(card.characteristic_record)
    elif fault.endswith('_dict_subclass'):
        section = fault.split('_', 1)[0]
        card.characteristic_record[section] = ProtocolDict(card.characteristic_record[section])
    elif fault.endswith('_item_subclass'):
        field = fault.split('_', 1)[0]
        bad = [ProtocolText(value) for value in getattr(card, field)]
        assert bad and bad == getattr(card, field)
        setattr(card, field, deepcopy(bad))
        for section in ('physical', 'values'):
            card.characteristic_record[section][field] = deepcopy(bad)
    elif fault == 'keywords_tuple':
        assert card.keywords == []
        card.keywords = ()
        for section in ('physical', 'values'):
            card.characteristic_record[section]['keywords'] = ()
    else:
        assert fault == 'layout_subclass'
        card.layout = ProtocolText(card.layout)
        card.characteristic_record['physical']['layout'] = ProtocolText(card.layout)
    before, stock, raw_before = deepcopy(card.__dict__), deepcopy(state.sideboard_facts), deepcopy(raw)
    with pytest.raises(AssertionError):
        _native_facts(card, raw)
    assert card.__dict__ == before and state.sideboard_facts == stock and raw == raw_before
