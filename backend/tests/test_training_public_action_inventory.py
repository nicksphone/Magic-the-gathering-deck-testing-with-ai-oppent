"""A new public action family must not bypass the intent boundary's guards."""
import ast
import inspect
import textwrap

from pydantic import TypeAdapter

from api_contracts import Action
from training.environment import TrainingEnvironment


def test_every_public_action_type_has_an_explicit_intent_model():
    public_types = set(TypeAdapter(Action).json_schema()['discriminator']['mapping'])
    tree = ast.parse(textwrap.dedent(inspect.getsource(TrainingEnvironment.lookup_intent)))
    maps = [node.value for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == 'models'
                    for target in node.targets)]
    assert len(maps) == 1 and isinstance(maps[0], ast.Dict)
    guarded_types = {key.value for key in maps[0].keys}
    assert guarded_types == public_types
