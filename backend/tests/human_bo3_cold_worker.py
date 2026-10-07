"""Fixed owned read-only child: actual cold ASGI GET, without app lifespan."""
import json
import sys

from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine

import main
from game_state.serializers import serialize_match_snapshot
from persistence.db import DATABASE_PATH
from persistence.repository import Repository

assert not main.ACTIVE_MATCHES
engine = create_engine('sqlite:///file:' + str(DATABASE_PATH) + '?mode=ro&uri=true')
main.engine = engine
def repo():
    with Session(engine) as session:
        yield Repository(session)
main.app.dependency_overrides[main.get_repo] = repo
client = TestClient(main.app, raise_server_exceptions=True)
try:
    result = client.get('/matches/' + sys.argv[-1])
    assert result.status_code == 200, result.text
    match = main.ACTIVE_MATCHES[sys.argv[-1]]
    print(json.dumps({'view': result.json(), 'snapshot': serialize_match_snapshot(match.state),
                      'controller': main._controller_snapshot(match)}))
finally:
    client.close()
    main.app.dependency_overrides.clear()
    engine.dispose()
