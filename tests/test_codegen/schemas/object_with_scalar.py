import uuid
from uuid import UUID

import strawberry

from tests.test_codegen.schemas.node_interface import Node


@strawberry.type
class User(Node):
    name: str
    age: int
    age_point: float
    male: bool
    id: strawberry.ID
    uuid: UUID


@strawberry.type
class Query:
    @strawberry.field
    def user(self) -> User:
        return User(
            name="Patrick",
            age=100,
            age_point=100.0,
            male=True,
            id=strawberry.ID("unique"),
            uuid=uuid.uuid4(),
        )


schema = strawberry.Schema(query=Query)
