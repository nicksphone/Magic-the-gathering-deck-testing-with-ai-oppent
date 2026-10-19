"""Stdlib-only exact source boundary check against retained proposal preimage."""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = Path((ROOT.parent / 'evidence/preimage-root.txt').read_text().strip()) / 'source'
ALLOWED = {
    'backend/rules_engine/events.py': {'_trigger_from_oracle', '_append_trigger_groups', '_targeted_trigger_clause',
        'trigger_target_options', '_remember_trigger_target', '_publish_ordered_triggers'},
    'backend/rules_engine/counter_placement.py': {'counter_placement_forbidden'},
    'backend/rules_engine/keyword_actions.py': {'finish_mechanic_choice'},
    'backend/rules_engine/action_validation.py': {'validate_action'},
    'backend/rules_engine/move_generator.py': {'legal_moves'},
    'backend/rules_engine/optional_reveal.py': {'public_choice'},
    'backend/game_state/serializers.py': {'serialize_match_snapshot', 'deserialize_match_snapshot'},
    'backend/rules_engine/entry_counters.py': {'begin_spell_entry'},
    'backend/training/environment.py': {'_require_choices'},
}
NEW = {'backend/rules_engine/modal_entry.py', 'backend/rules_engine/retained_counter_prohibition.py'}


def outside(raw, names):
    tree = ast.parse(raw)
    class Strip(ast.NodeTransformer):
        def visit_FunctionDef(self, node):
            return None if node.name in names else node
        def visit_ClassDef(self, node):
            return self.generic_visit(node)
    return ast.dump(Strip().visit(tree), include_attributes=False)


def check():
    originals = {str(p.relative_to(BASE)): p for p in (BASE / 'backend').rglob('*')
                 if p.is_file() and p.suffix in ('.py', '.json')}
    current = {str(p.relative_to(ROOT)): p for p in (ROOT / 'backend').rglob('*')
               if p.is_file() and p.suffix in ('.py', '.json')}
    assert set(current) - set(originals) == NEW
    assert not set(originals) - set(current)
    changed = []
    unchanged = 0
    for relative, path in originals.items():
        pre, post = path.read_bytes(), current[relative].read_bytes()
        if pre == post:
            unchanged += 1
            continue
        changed.append(relative)
        if relative in ALLOWED:
            assert outside(pre, ALLOWED[relative]) == outside(post, ALLOWED[relative]), relative
        elif relative == 'backend/game_state/state.py':
            tree = ast.parse(post)
            match = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'MatchState')
            matches = [n for n in match.body if isinstance(n, ast.AnnAssign) and ast.unparse(n.target) == 'retained_counter_prohibitions']
            assert len(matches) == 1
            match.body.remove(matches[0])
            assert ast.dump(tree, include_attributes=False) == ast.dump(ast.parse(pre), include_attributes=False)
        elif relative == 'backend/effects/registry.py':
            tree = ast.parse(post)
            tree.body = [n for n in tree.body if not isinstance(n, ast.ImportFrom) or n.module != 'rules_engine.retained_counter_prohibition']
            assignment = next(n for n in tree.body if isinstance(n, ast.AnnAssign) and ast.unparse(n.target) == 'EFFECT_HANDLERS')
            index = next(i for i, key in enumerate(assignment.value.keys) if ast.literal_eval(key) == 'retained_counter_prohibition')
            del assignment.value.keys[index]
            del assignment.value.values[index]
            assert ast.dump(tree, include_attributes=False) == ast.dump(ast.parse(pre), include_attributes=False)
        else:
            raise AssertionError('Unowned file changed: ' + relative)
    assert set(changed) == set(ALLOWED) | {'backend/game_state/state.py', 'backend/effects/registry.py'}
    original_tests = [p for p in (BASE / 'backend/tests').rglob('*') if p.is_file()]
    assert all(p.read_bytes() == (ROOT / p.relative_to(BASE)).read_bytes() for p in original_tests)
    original32 = 'audit/gate2-suncleanser/test_suncleanser_desired.py'
    assert (ROOT / original32).read_bytes() == (BASE / original32).read_bytes()
    # The consumer seam is exactly one literal; not permission for a rewrite.
    pre = (BASE / 'backend/training/environment.py').read_text()
    post = (ROOT / 'backend/training/environment.py').read_text()
    assert post.replace("'saga_entry', 'note_creature_type', 'entry_mode'", "'saga_entry', 'note_creature_type'") == pre
    return {'base': str(BASE), 'source': str(ROOT), 'original_files': len(originals),
            'original_files_byte_identical': unchanged, 'changed_owned_files': sorted(changed),
            'new_product_modules': sorted(NEW), 'original_test_fixture_files_byte_identical': len(original_tests),
            'outside_owned_ast_equal': True, 'original32_byte_identical': True,
            'training_literal_inverse_byte_equal': True}


if __name__ == '__main__':
    print(json.dumps(check(), indent=2, sort_keys=True))
