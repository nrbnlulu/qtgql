import uuid
from uuid import UUID

import strawberry

from tests.conftest import fake
from tests.test_codegen.schemas.node_interface import Node


@strawberry.type
class User(Node):
    name: str = strawberry.field(default_factory=fake.name)
    age: int = strawberry.field(default_factory=fake.pyint)
    age_point: float = strawberry.field(default_factory=fake.pyfloat)
    male: bool = strawberry.field(default_factory=fake.pybool)
    id: strawberry.ID = strawberry.field(default_factory=lambda: strawberry.ID(fake.pystr()))
    uuid: UUID = strawberry.field(default_factory=uuid.uuid4)


@strawberry.type
class Query:
    @strawberry.field
    def user(self) -> User:
        return User()


@strawberry.type
class Mutation:
    @strawberry.mutation
    def createUserNoArgs(self) -> User:
        return User()


schema = strawberry.Schema(query=Query, mutation=Mutation)
