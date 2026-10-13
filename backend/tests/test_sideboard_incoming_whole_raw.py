"""New fallback templates cover a whole raw surface, not one of its paragraphs."""
import pytest

from ai import sideboard_policy as policy
from tests.test_ai_knowledge_profile_consumer import RAW
from tests.test_sideboard_incoming_native_coverage import fault_row


@pytest.mark.parametrize('name', ['Negate', 'Go for the Throat'])
@pytest.mark.parametrize('extra', ['You gain 3 life.', 'Draw a card.'])
def test_new_whole_native_template_does_not_admit_extra_compiled_paragraph(name, extra):
    changed = RAW[name]['oracle_text'] + '\n' + extra
    assert policy._profile(fault_row(name, changed)) is None
