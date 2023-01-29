import uuid
from types import ModuleType
from typing import NamedTuple

import pytest
from qtgql.codegen.introspection import SchemaEvaluator, introspection_query
from qtgql.codegen.py.bases import BaseModel, _BaseQGraphQLObject
from qtgql.codegen.py.config import QtGqlConfig
from qtgql.codegen.py.objecttype import GqlType
from qtgql.codegen.py.scalars import DateTimeScalar
from strawberry import Schema

from tests.mini_gql_server import schema
from tests.test_codegen import schemas
from tests.test_codegen.conftest import get_introspection_for


@pytest.fixture
def introspected():
    return schema.execute_sync(introspection_query)


class ObjectTesterHelper(NamedTuple):
    mod: ModuleType
    tested_type: GqlType


class ObjectTestCaseMixin:
    schema: Schema
    initialize_dict: dict
    type_name = "User"

    @classmethod
    def compiled(cls) -> ObjectTesterHelper:
        tmp_mod = cls.get_tmp_mod()
        type_name = cls.type_name
        introspection = get_introspection_for(cls.schema)
        res = SchemaEvaluator(introspection, config=QtGqlConfig(url=None, output=None))
        generated = res.generate()
        compiled = compile(generated, "schema", "exec")
        exec(compiled, tmp_mod.__dict__)
        return ObjectTesterHelper(mod=tmp_mod, tested_type=res._generated_types[type_name])

    @classmethod
    def get_tmp_mod(cls):
        return ModuleType(uuid.uuid4().hex)

    def test_has_correct_annotations(self):
        compiled = self.compiled()
        klass = getattr(compiled.mod, compiled.tested_type.name)
        for field in compiled.tested_type.fields:
            annotation = field.annotation
            assert klass.__init__.__annotations__[field.name] == annotation
            assert getattr(klass, field.setter_name).__annotations__["v"] == annotation
            assert getattr(klass, field.name).fget.__annotations__["return"] == field.property_type

    def test_init(self):
        compiled = self.compiled()
        klass = getattr(compiled.mod, compiled.tested_type.name)
        klass()

    def test_property_getter(self):
        compiled = self.compiled()

        klass = getattr(compiled.mod, compiled.tested_type.name)
        inst = klass.from_dict(None, self.initialize_dict)
        for field in compiled.tested_type.fields:
            v = getattr(inst, field.name)
            if scalar := field.is_custom_scalar:
                assert scalar.from_graphql(self.initialize_dict[field.name]).to_qt() == v
            else:
                assert v == self.initialize_dict[field.name]

    def test_property_setter_emits(self, qtbot):
        compiled = self.compiled()
        klass = getattr(compiled.mod, compiled.tested_type.name)
        inst = klass.from_dict(None, self.initialize_dict)
        for field in compiled.tested_type.fields:
            signal = getattr(inst, field.signal_name)
            v = self.initialize_dict[field.name]
            with qtbot.wait_signal(signal):
                if scalar := field.is_custom_scalar:
                    setattr(inst, field.private_name, scalar.from_graphql(None))
                else:
                    setattr(inst, field.private_name, None)
                assert not getattr(inst, field.name)
                if scalar := field.is_custom_scalar:
                    v = scalar.from_graphql(v)
                getattr(inst, field.setter_name)(v)
                if field.is_custom_scalar:
                    assert getattr(inst, field.name) == v.to_qt()
                else:
                    assert getattr(inst, field.name) == v

    def test_from_dict(self, qtbot):
        compiled = self.compiled()
        klass = getattr(compiled.mod, compiled.tested_type.name)
        klass.from_dict(None, self.initialize_dict)


class TestSimpleObjectWithScalar(ObjectTestCaseMixin):
    schema = schemas.object_with_scalar.schema
    initialize_dict = schema.execute_sync(
        query="""
        {
          user {
            name
            age
            agePoint
            male
            id
          }
        }
        """
    ).data["user"]


class TestObjectWithDateTimeScalar(ObjectTestCaseMixin):
    schema = schemas.object_with_datetime.schema
    initialize_dict = schema.execute_sync(
        query="""
        {
          user {
            name
            age
            birth
          }
        }
        """
    ).data["user"]

    def test_from_dict(self, qtbot):
        compiled = self.compiled()
        klass = getattr(compiled.mod, compiled.tested_type.name)
        inst = klass.from_dict(None, self.initialize_dict)
        assert inst.birth == DateTimeScalar.from_graphql(self.initialize_dict["birth"]).to_qt()


class TestObjectWithOptionalScalar(ObjectTestCaseMixin):
    schema = schemas.object_with_optional_scalar.schema
    initialize_dict = schema.execute_sync(
        query="""
        query {
            user{
                name
                age
            }
        }
        """
    ).data["user"]


class TestObjectWithObject(ObjectTestCaseMixin):
    schema = schemas.object_with_object.schema
    initialize_dict = schema.execute_sync(
        query="""
        query {
            user{
                person{
                    name
                    age
                }
            }
        }
        """
    ).data["user"]

    def test_from_dict(self, qtbot):
        compiled = self.compiled()
        klass = getattr(compiled.mod, compiled.tested_type.name)
        inst = klass.from_dict(None, self.initialize_dict)
        assert inst.person.name == "Patrick"
        assert inst.person.age == 100


class TestObjectWithOptionalObjectField(ObjectTestCaseMixin):
    schema = schemas.object_with_optional_object.schema
    initialize_dict = schema.execute_sync(
        query="""
        query {
            user{
                person{
                    name
                    age
                }
            }
        }
        """
    ).data["user"]

    def test_from_dict(self, qtbot):
        compiled = self.compiled()
        klass = getattr(compiled.mod, compiled.tested_type.name)
        inst = klass.from_dict(None, self.initialize_dict)
        assert inst.person is None


# TODO: TestObjectWithListOfScalar
class TestObjectWithListOfObject(ObjectTestCaseMixin):
    schema = schemas.object_with_list_of_object.schema
    initialize_dict = schema.execute_sync(
        query="""
        query {
            user{
                persons{
                    name
                    age
                }
            }
        }
        """
    ).data["user"]

    def test_from_dict(self, qtbot):
        compiled = self.compiled()
        klass = getattr(compiled.mod, compiled.tested_type.name)
        inst: _BaseQGraphQLObject = klass.from_dict(None, self.initialize_dict)
        assert isinstance(inst.persons, BaseModel)


# TODO: test for optional list.


class TestObjectWithInterface(ObjectTestCaseMixin):
    schema = schemas.object_with_interface.schema
    initialize_dict = schema.execute_sync(
        query="""
        query {
            user{
                name
                age
            }
        }
        """
    ).data["user"]


class TestObjectWithUnion(ObjectTestCaseMixin):
    schema = schemas.object_with_union.schema
    initialize_dict = schema.execute_sync(
        query="""
            {
              user {
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
        """
    ).data["user"]


class TestObjectWithListOfTypeWithUnion(ObjectTestCaseMixin):
    schema = schemas.object_with_list_of_type_with_union.schema
    initialize_dict = schema.execute_sync(
        query="""
            {
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

        """
    ).data["userManager"]
