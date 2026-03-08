from dataclasses import dataclass

from classic.db_tools import Engine, ConnectionPool, Mapper, Value
from classic.domain import criteria, register
import psycopg


@dataclass
class Task:
    id: int
    payload: str

    @criteria
    def is_ready(self):
        pass

    @criteria
    def payload_greater_than(self, payload: int):
        pass


mapper = Mapper(task=Value(Task))

def test_():
    conn_pool = ConnectionPool(
        lambda: psycopg.connect('dbname=tasks user=variasov password=123')
    )
    engine = Engine('sql', conn_pool, mapper=mapper)
    register(engine)

    crit = Task.is_ready() & (
        Task.payload_greater_than(payload=1) |
        Task.payload_greater_than(payload=1)

    )
    with engine:
        objects = engine.query_from(
            'tasks/find.sql.tmpl'
        ).map_to(
            Task
        ).all(criteria=crit)

    assert objects == [Task(2, '12345')]
