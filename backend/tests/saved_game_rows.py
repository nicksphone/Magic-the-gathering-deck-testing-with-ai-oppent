"""Light helper shared by the backup test and its fresh-process worker."""
from contextlib import closing
import sqlite3


def saved_rows(path):
    """Application records only; capacity epochs legitimately change on startup."""
    queries = {'activematchrecord': 'SELECT * FROM activematchrecord ORDER BY id',
               'matchstartreceipt': 'SELECT * FROM matchstartreceipt ORDER BY key'}
    with closing(sqlite3.connect(path)) as conn:
        return {name: conn.execute(query).fetchall() for name, query in queries.items()}
