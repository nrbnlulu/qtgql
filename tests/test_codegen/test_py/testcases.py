import sys
import tempfile
import uuid
from functools import cached_property
from pathlib import Path
from textwrap import dedent
from types import ModuleType
from typing import TYPE_CHECKING, Optional, Type

import attrs
import strawberry.utils
from attr import define
from qtgql.codegen.introspection import SchemaEvaluator
from qtgql.codegen.py.compiler.config import QtGqlConfig
from qtgql.codegen.py.objecttype import GqlTypeDefinition
from qtgql.codegen.py.runtime.custom_scalars import (
    BaseCustomScalar,
    DateScalar,
    DateTimeScalar,
    DecimalScalar,
    TimeScalar,
)
from qtgql.codegen.py.runtime.environment import QtGqlEnvironment, set_gql_env
from qtgql.codegen.py.runtime.queryhandler import BaseQueryHandler
from qtgql.gqltransport.client import GqlWsTransportClient
from strawberry import Schema

from tests.conftest import QmlBot, hash_schema
from tests.test_codegen import schemas

if TYPE_CHECKING:
    from PySide6 import QtCore
    from qtgql.codegen.py.runtime.bases import _BaseQGraphQLObject


@define(slots=False, kw_only=True)
class QGQLObjectTestCase:
    query: str
    schema: Schema
    test_name: str
    type_name: str = "User"
    qmlbot: Optional[QmlBot] = None
    config: QtGqlConfig = attrs.field(
        factory=lambda: QtGqlConfig(graphql_dir=Path(__file__).parent, env_name="TestEnv")
    )
    query_operationName: str = "MainQuery"
    first_field: str = "user"
    qml_file: str = ""

    def __attrs_post_init__(self):
        self.query = dedent(self.query)
        if not self.qml_file:
            self.qml_file = dedent(
                """
                    import QtQuick
                    import generated.TestEnv as Env

                     Env.Require%s{
                        objectName: "rootObject"
                        anchors.fill: parent;

                    }
                """
                % self.query_operationName
            )

    @cached_property
    def evaluator(self) -> SchemaEvaluator:
        return SchemaEvaluator(config=self.config)

    @property
    def initialize_dict(self) -> dict:
        res = self.schema.execute_sync(
            self.evaluator._query_handlers[self.query_operationName].query
        )
        if res.errors:
            raise Exception("graphql operations failed", res.errors)
        else:
            return res.data

    def compile(self, url: Optional[str] = "") -> "CompiledTestCase":
        url = url.replace("graphql", f"{hash_schema(self.schema)}")
        env = QtGqlEnvironment(client=GqlWsTransportClient(url=url), name=self.config.env_name)
        set_gql_env(env)
        with tempfile.TemporaryDirectory() as raw_tmp_dir:
            tmp_dir = Path(raw_tmp_dir)
            self.config.graphql_dir = tmp_dir
            with (tmp_dir / "operations.graphql").open("w") as f:
                f.write(self.query)
            with (tmp_dir / "schema.graphql").open("w") as f:
                f.write(str(self.schema))

            generated = self.evaluator.dumps()
            types_module = ModuleType(uuid.uuid4().hex)
        handlers_mod = ModuleType(uuid.uuid4().hex)
        try:
            exec(compile(generated["objecttypes"], "gen_schema", "exec"), types_module.__dict__)
        except BaseException as e:
            raise RuntimeError(generated["objecttypes"]) from e

        sys.modules["objecttypes"] = types_module
        exec(compile(generated["handlers"], "gen_handlers", "exec"), handlers_mod.__dict__)
        return CompiledTestCase(
            evaluator=self.evaluator,
            objecttypes_mod=types_module,
            handlers_mod=handlers_mod,
            config=self.config,
            query=self.query,
            schema=self.schema,
            qml_file=self.qml_file,
            query_operationName=self.query_operationName,
            first_field=self.first_field,
            test_name=self.test_name,
            tested_type=self.evaluator._generated_types[self.type_name],
        )


@define
class CompiledTestCase(QGQLObjectTestCase):
    objecttypes_mod: ModuleType
    handlers_mod: ModuleType
    config: QtGqlConfig
    tested_type: GqlTypeDefinition
    evaluator: SchemaEvaluator

    @property
    def module(self) -> ModuleType:
        return self.objecttypes_mod

    @property
    def gql_type(self) -> Type["_BaseQGraphQLObject"]:
        assert self.tested_type
        return getattr(self.objecttypes_mod, self.tested_type.name)

    @cached_property
    def query_handler(self) -> "BaseQueryHandler":
        return getattr(self.handlers_mod, self.query_operationName)(None)

    def get_signals(self) -> dict[str, "QtCore.Signal"]:
        return {
            field.signal_name: getattr(self.query_handler.data, field.signal_name)
            for field in self.tested_type.fields
        }

    def get_field_by_type(self, t):
        for field in self.tested_type.fields:
            if field.type.type == t:
                return field

    def get_field_by_name(self, name: str):
        for field in self.tested_type.fields:
            if field.name == name:
                return field

        raise Exception(f"field {name} not found in {self.tested_type}")

    def strawberry_field_by_name(self, field_name: str, klass_name: Optional[str] = None):
        if not klass_name:
            klass_name = self.gql_type.__name__

        stawberry_definition = self.schema.get_type_by_name(klass_name)
        for sf in stawberry_definition.fields:
            if field_name == strawberry.utils.str_converters.to_camel_case(sf.name):
                return sf

    def load_qml(self, qmlbot: QmlBot):
        qmlbot.loads(self.qml_file)
        return self

    def get_qml_query_handler(self, bot: QmlBot) -> BaseQueryHandler:
        return bot.qquickiew.findChildren(BaseQueryHandler)[0]


ScalarsTestCase = QGQLObjectTestCase(
    schema=schemas.object_with_scalar.schema,
    query="""
        query MainQuery {
          user {
            id
            name
            age
            agePoint
            male
            id
            uuid
          }
        }
        """,
    test_name="ScalarsTestCase",
)
OptionalScalarTestCase = QGQLObjectTestCase(
    schema=schemas.object_with_optional_scalar.schema,
    query="""
    query MainQuery {
        user{
            name
            age
        }
    }
    """,
    test_name="OptionalScalarTestCase",
)
NestedObjectTestCase = QGQLObjectTestCase(
    schema=schemas.object_with_object.schema,
    query="""
    query MainQuery {
        user{
            person{
                name
                age
            }
        }
    }
    """,
    test_name="NestedObjectTestCase",
)
OptionalNestedObjectTestCase = QGQLObjectTestCase(
    schema=schemas.object_with_optional_object.schema,
    query="""
    query MainQuery {
        user{
            person{
                name
                age
            }
        }
    }
    """,
    test_name="OptionalNestedObjectTestCase",
)
ObjectWithListOfObjectTestCase = QGQLObjectTestCase(
    schema=schemas.object_with_list_of_object.schema,
    query="""
    query MainQuery {
        user{
            persons{
                name
                age
            }
        }
    }
    """,
    test_name="ObjectWithListOfObjectTestCase",
)

RootListOfTestCase = QGQLObjectTestCase(
    schema=schemas.root_list_of_object.schema,
    query="""
    query MainQuery {
        users{
            name
            age
        }
    }
    """,
    test_name="RootListOfTestCase",
)

InterfaceTestCase = QGQLObjectTestCase(
    schema=schemas.object_with_interface.schema,
    query="""
    query MainQuery {
        user{
            name
            age
        }
    }
    """,
    test_name="InterfaceTestCase",
)
UnionTestCase = QGQLObjectTestCase(
    schema=schemas.object_with_union.schema,
    query="""
        query MainQuery {
          user (choice: FROG){
            whoAmI {
              ... on Frog {
                __typename
                name
                color
              }
              ... on Person {
                __typename
                name
                age
              }
            }
          }
        }
    """,
    test_name="UnionTestCase",
)
ListOfObjectWithUnionTestCase = QGQLObjectTestCase(
    schema=schemas.object_with_list_of_type_with_union.schema,
    query="""
        query MainQuery {
          userManager {
            users {
              whoAmI {
                ... on Frog {
                  __typename
                  name
                  color
                }
                ... on Person {
                  __typename
                  name
                  age
                }
              }
            }
          }
        }

    """,
    test_name="ListOfUnionTestCase",
)
EnumTestCase = QGQLObjectTestCase(
    schema=schemas.object_with_enum.schema,
    query="""
        query MainQuery {
          user {
            name
            age
            status
          }
        }
        """,
    test_name="EnumTestCase",
)
DateTimeTestCase = QGQLObjectTestCase(
    schema=schemas.object_with_datetime.schema,
    query="""
       query MainQuery {
          user {
            name
            age
            birth
          }
        }
        """,
    test_name="DateTimeTestCase",
)
DecimalTestCase = QGQLObjectTestCase(
    schema=schemas.object_with_decimal.schema,
    query="""
       query MainQuery {
          user {
            name
            age
            balance
          }
        }
    """,
    test_name="DecimalTestCase",
)
DateTestCase = QGQLObjectTestCase(
    schema=schemas.object_with_date.schema,
    query="""
       query MainQuery {
          user {
            name
            age
            birth
          }
        }
        """,
    test_name="DateTestCase",
)
TimeTestCase = QGQLObjectTestCase(
    schema=schemas.object_with_time_scalar.schema,
    query="""
      query MainQuery {
          user {
            name
            age
            whatTimeIsIt
          }
        }
        """,
    test_name="TimeTestCase",
)
ObjectsThatReferenceEachOtherTestCase = QGQLObjectTestCase(
    schema=schemas.object_reference_each_other.schema,
    test_name="ObjectsThatReferenceEachOtherTestCase",
    query="""
  query MainQuery {
      user {
        password
        person {
          name
          age
        }
      }
    }
""",
)


class CountryScalar(BaseCustomScalar[Optional[str], str]):
    countrymap = schemas.object_with_user_defined_scalar.countrymap
    GRAPHQL_NAME = "Country"
    DEFAULT_VALUE = "isr"

    @classmethod
    def from_graphql(cls, v=None) -> "BaseCustomScalar":
        if v:
            return cls(cls.countrymap[v])
        return cls()

    def to_qt(self) -> str:
        return self._value


CustomUserScalarTestCase = QGQLObjectTestCase(
    schema=schemas.object_with_user_defined_scalar.schema,
    config=QtGqlConfig(
        graphql_dir=None, custom_scalars={CountryScalar.GRAPHQL_NAME: CountryScalar}
    ),
    test_name="CustomUserScalarTestCase",
    query="""
     query MainQuery {
          user {
            name
            age
            country
          }
        }
    """,
)

TypeWithNoIDTestCase = QGQLObjectTestCase(
    schema=schemas.type_with_no_id.schema,
    query="""query MainQuery {users{name}}""",
    test_name="TypeWithNoIDTestCase",
)
TypeWithNullAbleIDTestCase = QGQLObjectTestCase(
    schema=schemas.type_with_nullable_id.schema,
    query="""query MainQuery {users{name}}""",
    test_name="TypeWithNullAbleIDTestCase",
)

ListOfUnionTestCase = QGQLObjectTestCase(
    schema=schemas.list_of_union.schema,
    query="""
       query MainQuery {
          usersAndFrogs {
            ... on User {
              name
              age
            }
            ... on Frog {
              name
              color
            }
          }
        }""",
    test_name="ListOfUnionTestCase",
)

all_test_cases = [
    ScalarsTestCase,
    DateTimeTestCase,
    DateTestCase,
    DecimalTestCase,
    OptionalScalarTestCase,
    NestedObjectTestCase,
    OptionalNestedObjectTestCase,
    ObjectWithListOfObjectTestCase,
    InterfaceTestCase,
    UnionTestCase,
    ListOfObjectWithUnionTestCase,
    TimeTestCase,
    EnumTestCase,
    CustomUserScalarTestCase,
    ObjectsThatReferenceEachOtherTestCase,
    RootListOfTestCase,
    TypeWithNoIDTestCase,
    TypeWithNullAbleIDTestCase,
    ListOfUnionTestCase,
]
custom_scalar_testcases = [
    (DateTimeTestCase, DateTimeScalar, "birth"),
    (DateTestCase, DateScalar, "birth"),
    (DecimalTestCase, DecimalScalar, "balance"),
    (TimeTestCase, TimeScalar, "whatTimeIsIt"),
    (CustomUserScalarTestCase, CountryScalar, "country"),
]
