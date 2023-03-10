from decimal import Decimal

import strawberry

from tests.conftest import fake
from tests.test_codegen.schemas.node_interface import Node


@strawberry.type
class User(Node):
    name: str
    age: int
    balance: Decimal


@strawberry.type
class Query:
    @strawberry.field
    def user(self) -> User:
        return User(name="Patrick", age=100, balance=Decimal(fake.pyfloat()))


schema = strawberry.Schema(query=Query)
