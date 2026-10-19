"""Bounded exhaustive seed inventory. Contract recognition is not execution."""
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

from card_data.hydration import ready_for_match, is_playable_deck_card, hydrate_deck_cards
from game_state.state import CardInstance, Zone, MatchState, PlayerState
from rules_engine.card_types import printed_card_types
from rules_engine.ability_model import build_ability_spec, build_spell_spec
from rules_engine.conditional_instructions import parse_instruction
from rules_engine.oracle_effects import compile_optional_land_instruction
from rules_engine.linked_discard import linked_discard_effect
from rules_engine.oracle_text import without_reminder_text
from rules_engine.coverage import (known_unsupported_mechanics,
                                  combat_coverage_details, static_coverage_details)
from rules_engine.events import public_trigger_clause_coverage
from rules_engine.oracle_effects import complete_stack_instruction_coverage
from scripts.corpus_knowledge_readiness import fact_gaps, canonical_hash
from scripts.knowledge_engine_coverage import surface_status

ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / 'backend/card_data/builtin_oracle_seed.json'
PROVENANCE = ROOT / 'backend/tests/fixtures/builtin_face_colors/provenance.json'
MAX_SEED_BYTES = 4 * 1024**2
MAX_CARDS = 500
MAX_BULK_BYTES = 256 * 1024**2
MAX_LINE_BYTES = 2 * 1024**2
MAX_EXPANDED_BYTES = 2 * 1024**3
MAX_RECORDS = 100000

def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def load_inputs():
    if SEED.stat().st_size > MAX_SEED_BYTES:
        raise ValueError('Seed byte cap exceeded')
    seed = json.loads(SEED.read_bytes())['cards']
    if not isinstance(seed, dict) or not 0 < len(seed) <= MAX_CARDS:
        raise ValueError('Seed row cap or shape')
    proof = json.loads(PROVENANCE.read_bytes())
    path = Path(proof['source_bulk'])
    if path.stat().st_size > MAX_BULK_BYTES or sha(path) != proof['source_bulk_sha256']:
        raise ValueError('Canonical bulk byte cap or digest mismatch')
    wanted = {row['scryfall_id'] for row in seed.values()}
    selected = {}
    representatives = {}
    expanded = 0
    records = 0
    with gzip.open(path, 'rb') as stream:
        while True:
            line = stream.readline(MAX_LINE_BYTES + 1)
            if not line:
                break
            expanded += len(line)
            records += 1
            if len(line) > MAX_LINE_BYTES or expanded > MAX_EXPANDED_BYTES or records > MAX_RECORDS:
                raise ValueError('Canonical expanded/line/row cap exceeded')
            raw = json.loads(line)
            if raw.get('name') in seed:
                representatives.setdefault(raw['name'], []).append(raw)
            if raw.get('id') in wanted:
                if raw['id'] in selected:
                    raise ValueError('Duplicate exact printing in canonical source')
                selected[raw['id']] = raw
    if sha(path) != proof['source_bulk_sha256']:
        raise ValueError('Canonical source changed during read')
    for name, runtime in seed.items():
        if runtime['scryfall_id'] not in selected and name in representatives:
            candidates = [r for r in representatives[name] if is_playable_deck_card(r) and r.get('lang') == 'en']
            if len(candidates) != 1:
                raise ValueError('Ambiguous playable English representative: ' + name + ' ' +
                    str([(r['id'], r.get('layout'), r.get('oracle_id')) for r in candidates]))
            selected[runtime['scryfall_id']] = candidates[0]
    return seed, selected, {'seed_sha256': sha(SEED), 'bulk_path': str(path),
        'bulk_sha256': proof['source_bulk_sha256'], 'bulk_records': records,
        'bulk_expanded_bytes': expanded, 'provenance_sha256': sha(PROVENANCE),
        'representative_join_policy': 'unique exact root name, playable English; never a same-printing claim'}

def card_instance(raw):
    return CardInstance(id=raw.get('id', raw['name']), name=raw['name'], owner=1,
        controller=1, zone=Zone.STACK, oracle_text=raw.get('oracle_text', ''),
        type_line=raw.get('type_line', ''), mana_cost=raw.get('mana_cost', ''),
        types=sorted(printed_card_types(raw.get('type_line', ''))))

def compiler_preview(surface):
    card = card_instance(surface)
    state = MatchState(id='inventory-preview', players={
        p: PlayerState(id=p, name=str(p)) for p in (1, 2)}, cards={card.id: card}, stack=[])
    # Empty diagnostic context: no cost, target, condition or execution assertions.
    spec = build_spell_spec(state, card, 1, report_unsupported=False) if set(card.types) & {'Instant', 'Sorcery'} else build_ability_spec(state, card, 1, report_unsupported=False)
    return {'effect_key': spec.effect.key, 'used_fallback': spec.used_fallback,
            'event_supported': spec.event_supported,
            'unsupported_resolution': list(spec.unsupported_resolution),
            'modes': spec.modes, 'scope': 'unselected empty-state preview, not whole-clause support or execution'}

def inspect_surfaces(raw):
    if surface_status(raw) != 'valid':
        raise ValueError('Malformed canonical surface')
    variants = [(None, raw)] + list(enumerate(raw.get('card_faces', [])))
    surfaces = []
    for index, surface in variants:
        card = card_instance(surface)
        whole = (complete_stack_instruction_coverage(card)
                 if surface.get('type_line') in {'Instant', 'Sorcery'} else None)
        lines = []
        # Printed lines are lossless inventory units, not invented Oracle clauses.
        for line_index, line in enumerate(surface.get('oracle_text', '').splitlines()):
            if not line.strip():
                continue
            trigger = public_trigger_clause_coverage(card, line)
            conditional = parse_instruction(surface.get('oracle_text', ''), surface['name']) if surface.get('type_line') in {'Instant', 'Sorcery'} else None
            optional_land = compile_optional_land_instruction(without_reminder_text(line))
            discard = linked_discard_effect(line)
            contract = whole or trigger or conditional or optional_land or discard
            lines.append({'line_index': line_index, 'printed_text': line,
                'printed_sha256': hashlib.sha256(line.encode()).hexdigest(),
                'contract': contract,
                'contract_function': ('complete_stack_instruction_coverage' if whole else
                    'public_trigger_clause_coverage' if trigger else 'conditional_instructions.parse_instruction' if conditional
                    else 'compile_optional_land_instruction' if optional_land else 'linked_discard_effect' if discard else None),
                'status': 'structural_contract_only' if contract else 'uncovered_by_positive_contracts',
                'execution_evidence': []})
        surfaces.append({'face_index': index, 'name': surface['name'],
                         'type_line': surface.get('type_line'),
                         'oracle_text': surface.get('oracle_text'), 'lines': lines,
                         'compiler_preview': compiler_preview(surface),
                         'whole_stack_contract': whole})
    return surfaces

def inspect_card(requested, runtime, raw):
    if raw is None:
        return {'name': requested, 'canonical_join': 'missing_exact_printing',
                'scryfall_id': runtime['scryfall_id'], 'execution_evidence': [],
                'complete_card_semantics': 'unverified'}
    surfaces = inspect_surfaces(raw)
    reasons = sorted(set(known_unsupported_mechanics(raw.get('oracle_text', ''),
        raw.get('card_faces'), card_name=raw['name'], canonical_context=raw)))
    mismatches = [key for key in ('name', 'oracle_text', 'mana_cost', 'type_line',
        'power', 'toughness', 'loyalty') if key in runtime and key in raw and runtime[key] != raw[key]]
    hydrated = hydrate_deck_cards(None, [{'card_name': requested, 'quantity': 1}])[0]
    runtime_gaps = sorted(set(known_unsupported_mechanics(hydrated.get('oracle_text', ''),
        hydrated.get('card_faces'), card_name=hydrated['card_name'], canonical_context=hydrated)))
    return {'name': requested, 'canonical_join': ('exact_printing' if raw['id'] == runtime['scryfall_id']
        else 'exact_name_representative_oracle_not_same_printing'),
        'runtime_printing_id': runtime['scryfall_id'],
        'scryfall_id': raw['id'], 'oracle_id': raw['oracle_id'],
        'raw_sha256': canonical_hash(raw), 'runtime_sha256': canonical_hash(runtime),
        'runtime_fact_mismatches': mismatches, 'canonical_fact_gaps': fact_gaps(raw),
        'canonical_metadata_ready': ready_for_match(raw),
        'runtime_metadata_ready': ready_for_match(runtime), 'layout': raw.get('layout'),
        'hydrated_metadata_ready': ready_for_match(hydrated),
        'hydrated_known_admission_gaps': runtime_gaps,
        'known_admission_gaps': reasons,
        'clause_gap_details': combat_coverage_details(raw.get('oracle_text', ''),
            raw.get('card_faces'), card_name=raw['name']) + static_coverage_details(
            raw.get('oracle_text', ''), raw.get('card_faces'), card_name=raw['name']),
        'legalities_present': isinstance(raw.get('legalities'), dict),
        'images_present': bool(raw.get('image_uris') or any(f.get('image_uris') for f in raw.get('card_faces', []))),
        'related_parts': raw.get('all_parts', []),
        'rulings_status': 'URI_only_content_not_audited',
        'surfaces': surfaces, 'execution_evidence': [],
        'runtime_surfaces': inspect_surfaces(runtime),
        'runtime_known_admission_gaps': sorted(set(known_unsupported_mechanics(runtime.get('oracle_text', ''),
            runtime.get('card_faces'), card_name=runtime['name'], canonical_context=runtime))),
        'complete_card_semantics': 'unverified'}

def report(seed, raws, provenance):
    cards = [inspect_card(name, runtime, raws.get(runtime['scryfall_id']))
             for name, runtime in sorted(seed.items())]
    lines = [line for c in cards for s in c.get('surfaces', []) for line in s['lines']]
    runtime_lines = [line for c in cards for s in c.get('runtime_surfaces', []) for line in s['lines']]
    from decks.builtin_decks import BUILTIN_DECKS
    from decks.parser import DeckParser
    from types import SimpleNamespace
    class SeedNames:
        def list_cards(self):
            return [SimpleNamespace(name=name) for name in seed]
    frequencies = Counter()
    appearances = Counter()
    for text in BUILTIN_DECKS.values():
        parsed = DeckParser(SeedNames()).parse(text)
        if parsed.errors:
            raise ValueError('Builtin deck parse failed: ' + str(parsed.errors))
        entries = parsed.mainboard + parsed.sideboard
        frequencies.update({name: sum(e['quantity'] for e in entries if e['card_name'] == name)
                            for name in {e['card_name'] for e in entries}})
        appearances.update({e['card_name'] for e in entries})
    for card in cards:
        card['builtin_deck_copies'] = frequencies[card['name']]
        card['builtin_deck_appearances'] = appearances[card['name']]
    gaps = Counter(reason for card in cards for reason in card.get('known_admission_gaps', []))
    return {'schema_version': 1, 'source_data': provenance,
        'counts': {'seed_names': len(cards), 'exact_printing_joins': sum(c['canonical_join'] == 'exact_printing' for c in cards),
            'surfaces': sum(len(c.get('surfaces', [])) for c in cards),
            'printed_lines': len(lines), 'positive_contract_lines': sum(bool(l['contract']) for l in lines),
            'unsatisfied_positive_contract_lines': sum(not l['contract'] for l in lines),
            'known_admission_gap_cards': sum(bool(c.get('known_admission_gaps')) for c in cards),
            'representative_oracle_joins': sum(c['canonical_join'] == 'exact_name_representative_oracle_not_same_printing' for c in cards),
            'no_known_gap_not_certified_cards': sum('known_admission_gaps' in c and not c['known_admission_gaps'] for c in cards),
            'metadata_ready_cards': sum(c.get('canonical_metadata_ready', False) for c in cards)},
        'actual_offline_preflight': {
            'builtin_decks': len(BUILTIN_DECKS),
            'runtime_surfaces': sum(len(c.get('runtime_surfaces', [])) for c in cards),
            'runtime_printed_lines': len(runtime_lines),
            'runtime_positive_contract_lines': sum(bool(l['contract']) for l in runtime_lines),
            'runtime_unsatisfied_positive_contract_lines': sum(not l['contract'] for l in runtime_lines),
            'metadata_ready_cards': sum(c.get('hydrated_metadata_ready', False) for c in cards),
            'gap_cards': sum(bool(c.get('hydrated_known_admission_gaps')) for c in cards),
            'no_known_gap_not_certified_cards': sum(not c.get('hydrated_known_admission_gaps') for c in cards),
            'reason_card_counts': dict(sorted(Counter(r for c in cards for r in c.get('hydrated_known_admission_gaps', [])).items()))},
        'layouts': dict(sorted(Counter(c.get('layout', 'unknown') for c in cards).items())),
        'known_admission_gap_counts': dict(sorted(gaps.items())), 'cards': cards,
        'limits': {'seed_bytes': MAX_SEED_BYTES, 'seed_names': MAX_CARDS,
            'bulk_compressed_bytes': MAX_BULK_BYTES, 'bulk_expanded_bytes': MAX_EXPANDED_BYTES,
            'line_bytes': MAX_LINE_BYTES, 'bulk_records': MAX_RECORDS},
        'interpretation': ['Every printed root/face line retained; multi-sentence lines are not split into fabricated clauses.',
            'Known admission gaps can be conservative; not demonstrated runtime failures.',
            'Positive public contracts are bounded; residual lines need contract/semantic evidence, not necessarily new handlers.',
            'No known gap, compiler detection or absent offered moves never proves semantic execution or inertness.',
            'Rulings content, fetched images/tokens, upstream freshness and publisher authenticity are not established here.',
            'No full rules, whole-card, expert AI, SQL/HTTP/browser or release certification.'],
        'rules_support_certified': False, 'expert_ai_certified': False}

if __name__ == '__main__':
    seed, raws, provenance = load_inputs()
    print(json.dumps(report(seed, raws, provenance), indent=2, sort_keys=True))
