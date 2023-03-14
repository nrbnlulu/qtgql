import copy
import uuid
import weakref
from typing import Optional, Type

import pytest
import pytestqt.exceptions
from qtgql.codegen.introspection import introspection_query
from qtgql.codegen.py.compiler.builtin_scalars import BuiltinScalar, BuiltinScalars
from qtgql.codegen.py.runtime.bases import QGraphQListModel, _BaseQGraphQLObject
from qtgql.codegen.py.runtime.custom_scalars import (
    BaseCustomScalar,
    DateTimeScalar,
)
from qtgql.codegen.py.runtime.queryhandler import SelectionConfig
from qtgql.utils.typingref import TypeHinter

from tests.mini_gql_server import schema
from tests.test_codegen.test_py.testcases import (
    DateTimeTestCase,
    EnumTestCase,
    InterfaceTestCase,
    NestedObjectTestCase,
    ObjectsThatReferenceEachOtherTestCase,
    ObjectWithListOfObjectTestCase,
    OptionalNestedObjectTestCase,
    QGQLObjectTestCase,
    RootListOfTestCase,
    ScalarsTestCase,
    TypeWithNoIDTestCase,
    TypeWithNullAbleIDTestCase,
    UnionTestCase,
    all_test_cases,
    custom_scalar_testcases,
)


@pytest.fixture
def introspected():
    return schema.execute_sync(introspection_query)


@pytest.mark.parametrize("testcase", all_test_cases, ids=lambda x: x.test_name)
def test_init_no_arguments(testcase: QGQLObjectTestCase):
    testcase = testcase.compile()
    assert isinstance(testcase.gql_type(None), _BaseQGraphQLObject)


class TestAnnotations:
    @pytest.mark.parametrize("scalar", BuiltinScalars, ids=lambda v: v.graphql_name)
    def test_scalars(self, scalar: BuiltinScalar):
        testcase = ScalarsTestCase.compile()
        field = testcase.get_field_by_type(scalar)
        assert field, f"field not found for {scalar.graphql_name}: {scalar}"
        klass = testcase.gql_type
        assert (
            scalar.tp
            == TypeHinter.from_string(
                getattr(klass, field.setter_name).__annotations__["v"], ns=field.type_map
            ).as_annotation()
        )
        assert (
            scalar.tp
            == TypeHinter.from_string(
                getattr(klass, field.name).fget.__annotations__["return"], ns=field.type_map
            ).as_annotation()
        )

    @pytest.mark.parametrize(("testcase", "scalar", "fname"), custom_scalar_testcases)
    def test_custom_scalars(
        self, testcase: QGQLObjectTestCase, scalar: Type[BaseCustomScalar], fname
    ):
        testcase = testcase.compile()
        field = testcase.get_field_by_type(scalar)
        assert field, f"field {field} not found"
        klass = testcase.gql_type
        assert field.annotation == f"SCALARS.{scalar.__name__}"
        assert getattr(klass, field.setter_name).__annotations__["v"] == field.annotation
        assert getattr(klass, field.name).fget.__annotations__["return"] == field.fget_annotation
        assert (
            TypeHinter.from_string(field.fget_annotation, ns={"Optional": Optional}).as_annotation()
            == scalar.to_qt.__annotations__["return"]
        )

    def test_list_of(self):
        testcase = ObjectWithListOfObjectTestCase.compile()
        field = testcase.get_field_by_name("persons")
        assert (
            field.annotation
            == f"{QGraphQListModel.__name__}[Optional[{field.type.is_model.is_object_type.name}]]"
        )
        assert (
            field.fget_annotation
            == f"{QGraphQListModel.__name__}[Optional[{field.type.is_model.is_object_type.name}]]"
        )

    def test_custom_scalar_property_type_is_to_qt_return_annotation(self):
        testcase = DateTimeTestCase.compile()
        to_qt = TypeHinter.from_annotations(DateTimeScalar.to_qt.__annotations__["return"])
        assert testcase.get_field_by_name("birth").property_type == to_qt.stringify()

    def test_enums(self):
        testcase = EnumTestCase.compile()
        enum_field = testcase.get_field_by_name("status")
        assert enum_field.property_type == "int"
        assert enum_field.fget_annotation == "int"
        assert enum_field.annotation == "Status"


class TestPropertyGetter:
    def default_test(self, testcase: QGQLObjectTestCase, field_name: str):
        testcase = testcase.compile()
        initialize_dict = testcase.initialize_dict
        handler = testcase.query_handler
        handler.on_data(initialize_dict)
        field = testcase.get_field_by_name(field_name)
        assert handler._data.property(field.name)

    def test_scalars(self, qtbot):
        testcase = ScalarsTestCase.compile()
        handler = testcase.query_handler
        initialize_dict = testcase.initialize_dict
        handler.on_data(initialize_dict)
        for field in testcase.tested_type.fields:
            v = handler._data.property(field.name)
            assert v == initialize_dict[testcase.first_field][field.name]

    def test_datetime_scalar(self, qtbot):
        self.default_test(DateTimeTestCase, "birth")

    def test_nested_object(self, qtbot):
        self.default_test(NestedObjectTestCase, "person")

    def test_list_of(self, qtbot):
        self.default_test(ObjectWithListOfObjectTestCase, "persons")

    def test_union(self, qtbot):
        testcase = UnionTestCase.compile()
        initialize_dict = testcase.initialize_dict

        handler = testcase.query_handler
        handler.on_data(initialize_dict)
        field = testcase.get_field_by_name("whoAmI")
        assert handler._data.property(field.name)
        data: _BaseQGraphQLObject = handler._data.property(field.name)
        if data.typename == "Person":
            assert data.name == "Nir"
        else:
            assert data.typename == "Frog"
            assert data.name == "Kermit"

    def test_enum(self, qtbot):
        testcase = EnumTestCase.compile()
        handler = testcase.query_handler
        handler.on_data(testcase.initialize_dict)
        f = testcase.get_field_by_name("status")
        assert handler._data.property(f.name) == testcase.module.Status.Connected.value


class TestDeserializers:
    @pytest.mark.parametrize("testcase", all_test_cases, ids=lambda x: x.test_name)
    def test_blank_dict_no_selections(self, testcase: QGQLObjectTestCase, qtbot):
        testcase = testcase.compile()
        assert isinstance(
            testcase.gql_type.from_dict(
                None,
                {"id": uuid.uuid4().hex},
                SelectionConfig(selections={"id": None}),
                testcase.query_handler.OPERATION_METADATA,
            ),
            testcase.gql_type,
        )

    def test_scalars(self, qtbot):
        testcase = ScalarsTestCase.compile()
        initialize_dict = testcase.initialize_dict
        handler = testcase.query_handler
        handler.on_data(initialize_dict)
        for field in testcase.tested_type.fields:
            v = getattr(handler._data, field.private_name)
            assert v == initialize_dict[testcase.first_field][field.name]

    def test_nested_object_from_dict(self, qtbot):
        testcase = NestedObjectTestCase.compile()
        handler = testcase.query_handler
        init_dict = testcase.initialize_dict
        person = init_dict[testcase.first_field]["person"]
        handler.on_data(init_dict)
        assert handler._data.person.name == person["name"]
        assert handler._data.person.age == person["age"]

    def test_nested_optional_object_is_null(self):
        testcase = OptionalNestedObjectTestCase.compile()
        handler = testcase.query_handler
        handler.on_data(testcase.initialize_dict)
        assert handler._data.person is None

    def test_object_with_list_of_object(self):
        testcase = ObjectWithListOfObjectTestCase.compile()
        handler = testcase.query_handler
        handler.on_data(testcase.initialize_dict)
        assert isinstance(handler._data.persons, QGraphQListModel)
        assert handler._data.persons._data[0].name

    def test_object_with_interface(self):
        testcase = InterfaceTestCase.compile()
        handler = testcase.query_handler
        handler.on_data(testcase.initialize_dict)
        assert handler._data.name

    @pytest.mark.parametrize(("testcase", "scalar", "fname"), custom_scalar_testcases)
    def test_custom_scalars(
        self, testcase: QGQLObjectTestCase, scalar: BaseCustomScalar, fname: str
    ):
        testcase = testcase.compile()
        initialize_dict = testcase.initialize_dict
        field = testcase.get_field_by_name(fname)
        raw_value = initialize_dict[testcase.first_field][field.name]
        expected = scalar.from_graphql(raw_value).to_qt()
        handler = testcase.query_handler
        handler.on_data(initialize_dict)
        assert handler._data.property(field.name) == expected

    def test_enum(self):
        testcase = EnumTestCase.compile()
        handler = testcase.query_handler
        handler.on_data(testcase.initialize_dict)
        f = testcase.get_field_by_name("status")
        assert getattr(handler._data, f.private_name) == testcase.module.Status.Connected

    def test_root_field_list_of_object(self):
        testcase = RootListOfTestCase.compile()
        handler = testcase.query_handler
        handler.on_data(testcase.initialize_dict)

    def test_type_with_optional_id_and_id_not_arrived(self):
        testcase = TypeWithNullAbleIDTestCase.compile()
        testcase.query_handler.on_data(testcase.initialize_dict)
        testcase.query_handler.on_data(testcase.initialize_dict)

    def test_type_with_no_id(self):
        testcase = TypeWithNoIDTestCase.compile()
        testcase.query_handler.on_data(testcase.initialize_dict)
        testcase.query_handler.on_data(testcase.initialize_dict)


class TestUpdates:
    def test_scalars_update(self, qtbot):
        testcase = ScalarsTestCase.compile()
        initialize_dict1 = testcase.initialize_dict

        handler = testcase.query_handler
        handler.on_data(initialize_dict1)
        initialize_dict2 = testcase.initialize_dict
        initialize_dict2[testcase.first_field]["id"] = handler.data.id
        initialize_dict2[testcase.first_field]["male"] = not initialize_dict1[testcase.first_field][
            "male"
        ]
        assert initialize_dict1 != initialize_dict2
        previous = handler.data
        signals = testcase.get_signals()
        signals.pop("idChanged")
        signals = list(signals.values())
        with qtbot.wait_signals(signals):
            handler.on_data(initialize_dict2)
        after = handler.data
        assert after is previous
        for k, v in initialize_dict2[testcase.first_field].items():
            assert handler.data.property(k) == v

    def tests_scalars_no_update(self, qtbot):
        testcase = ScalarsTestCase.compile()
        initialize_dict1 = testcase.initialize_dict
        handler = testcase.query_handler
        handler.on_data(initialize_dict1)
        with pytest.raises(pytestqt.exceptions.TimeoutError):
            signals = testcase.get_signals()
            signals = list(signals.values())
            with qtbot.wait_signals(
                signals,
                timeout=1000,
            ):
                handler.on_data(initialize_dict1)

    @pytest.mark.parametrize(("testcase", "scalar", "fname"), custom_scalar_testcases)
    def test_custom_scalars_no_update(
        self, testcase: QGQLObjectTestCase, scalar: BaseCustomScalar, fname: str, qtbot
    ):
        testcase = testcase.compile()
        initialized_dict = testcase.initialize_dict
        handler = testcase.query_handler
        handler.on_data(initialized_dict)
        signal = getattr(handler.data, testcase.get_field_by_name(fname).signal_name)
        with pytest.raises(pytestqt.exceptions.TimeoutError):
            with qtbot.wait_signal(signal, timeout=1000):
                handler.on_data(initialized_dict)

    @pytest.mark.parametrize(("testcase", "scalar", "fname"), custom_scalar_testcases)
    def test_custom_scalars_update(
        self, testcase: QGQLObjectTestCase, scalar: BaseCustomScalar, fname: str, qtbot
    ):
        testcase = testcase.compile()
        initialize_dict1 = testcase.initialize_dict
        handler = testcase.query_handler
        handler.on_data(initialize_dict1)
        initialize_dict2 = testcase.initialize_dict
        initialize_dict2[testcase.first_field]["id"] = handler.data.id
        assert (
            initialize_dict2[testcase.first_field][fname]
            != initialize_dict1[testcase.first_field][fname]
        )
        previous = handler.data
        signal = getattr(handler.data, testcase.get_field_by_name(fname).signal_name)
        with qtbot.wait_signal(signal):
            handler.on_data(initialize_dict2)
        after = handler.data
        assert after is previous
        raw_new_val = initialize_dict2[testcase.first_field][fname]
        assert handler.data.property(fname) == scalar.from_graphql(raw_new_val).to_qt()

    def test_object_in_object_no_update(self, qtbot):
        testcase = NestedObjectTestCase.compile()
        initialized_dict = testcase.initialize_dict
        handler = testcase.query_handler
        handler.on_data(initialized_dict)
        person_type = testcase.tested_type.fields_dict["person"].type.is_object_type
        person_signals = [
            getattr(handler.data.person, field.signal_name) for field in person_type.fields
        ]
        with pytest.raises(pytestqt.exceptions.TimeoutError):
            with qtbot.wait_signals(person_signals, timeout=1000):
                handler.on_data(initialized_dict)

    @staticmethod
    def _get_nested_obj_dict_same_id_diff_val(initialized_dict1: dict) -> dict:
        initialized_dict2 = copy.deepcopy(initialized_dict1)
        person_dict1 = initialized_dict1["user"]["person"]
        person_dict2 = initialized_dict2["user"]["person"]
        person_dict2["name"] = "this is not a name"
        person_dict2["age"] = person_dict1["age"] + 1
        assert person_dict1 != person_dict2
        assert person_dict1["id"] == person_dict2["id"]
        return initialized_dict2

    def test_nested_object_same_id_update(self, qtbot):
        testcase = NestedObjectTestCase.compile()
        initialized_dict1 = testcase.initialize_dict
        handler = testcase.query_handler
        handler.on_data(initialized_dict1)
        person_type = testcase.tested_type.fields_dict["person"].type.is_object_type
        person_signals = [
            getattr(handler.data.person, field.signal_name)
            for field in person_type.fields
            if field.name != "id"
        ]
        initialized_dict2 = self._get_nested_obj_dict_same_id_diff_val(initialized_dict1)
        with qtbot.wait_signals(person_signals, timeout=500):
            handler.on_data(initialized_dict2)

    def test_nested_object_wont_emit_signal_if_id_is_the_same(self, qtbot):
        testcase = NestedObjectTestCase.compile()
        initialized_dict1 = testcase.initialize_dict
        handler = testcase.query_handler
        handler.on_data(initialized_dict1)
        initialized_dict2 = self._get_nested_obj_dict_same_id_diff_val(initialized_dict1)
        with pytest.raises(pytestqt.exceptions.TimeoutError):
            with qtbot.wait_signal(handler.data.personChanged, timeout=500):
                handler.on_data(initialized_dict2)

    def test_nested_optional_object_null_update_with_object(self, qtbot):
        testcase = OptionalNestedObjectTestCase.compile()
        initialized_dict = testcase.initialize_dict
        handler = testcase.query_handler
        handler.on_data(initialized_dict)
        assert not handler.data.person
        prev = handler.data
        dict_with_person = NestedObjectTestCase.compile().initialize_dict
        dict_with_person[testcase.first_field]["id"] = handler.data._id
        with qtbot.wait_signal(handler.data.personChanged):
            handler.on_data(dict_with_person)
        assert prev is not handler.data.person

    def test_nested_optional_object_update_with_null(self, qtbot):
        testcase = NestedObjectTestCase.compile()
        initialized_dict = testcase.initialize_dict
        handler = testcase.query_handler
        handler.on_data(initialized_dict)
        assert handler.data.person
        dict_without_person = OptionalNestedObjectTestCase.compile().initialize_dict
        dict_without_person["user"]["id"] = initialized_dict["user"]["id"]
        with qtbot.wait_signal(handler.data.personChanged):
            handler.on_data(dict_without_person)
        assert not handler.data.person

    def test_union_no_update(self, qtbot):
        testcase = UnionTestCase.compile()
        handler = testcase.query_handler
        query = testcase.evaluator._query_handlers[testcase.query_operationName].query
        frog_dict = testcase.schema.execute_sync(query).data
        testcase.query_handler.on_data(frog_dict)
        same_frog_new_name = copy.deepcopy(frog_dict)
        new_name = "Same same, new name!"
        same_frog_new_name["user"]["whoAmI"]["name"] = new_name
        with pytest.raises(pytestqt.exceptions.TimeoutError):
            with qtbot.wait_signal(handler.data.whoAmIChanged, timeout=500):
                handler.on_data(same_frog_new_name)
        assert handler.data.whoAmI.name == new_name

    def test_union_update_same_type(self, qtbot):
        testcase = UnionTestCase.compile()
        handler = testcase.query_handler
        query = testcase.evaluator._query_handlers[testcase.query_operationName].query
        frog_dict = testcase.schema.execute_sync(query).data
        testcase.query_handler.on_data(frog_dict)
        frog_dict2 = testcase.schema.execute_sync(query).data
        frog_dict2[testcase.first_field]["id"] = handler.data.id
        with qtbot.wait_signal(handler.data.whoAmIChanged, timeout=500):
            handler.on_data(frog_dict2)
        assert handler.data.whoAmI.name == frog_dict2[testcase.first_field]["whoAmI"]["name"]

    def test_union_update_different_type(self, qtbot):
        testcase = UnionTestCase.compile()
        handler = testcase.query_handler
        query = testcase.evaluator._query_handlers[testcase.query_operationName].query
        frog_dict = testcase.schema.execute_sync(query).data
        testcase.query_handler.on_data(frog_dict)
        person_dict = testcase.schema.execute_sync(
            query.replace("choice: FROG", "choice: PERSON")
        ).data
        person_dict[testcase.first_field]["id"] = handler.data.id
        with qtbot.wait_signal(handler.data.whoAmIChanged, timeout=500):
            handler.on_data(person_dict)
        assert handler.data.whoAmI.age

    def test_enum_no_update(self, qtbot):
        testcase = EnumTestCase.compile()
        handler = testcase.query_handler
        d = testcase.initialize_dict
        handler.on_data(d)
        with pytest.raises(pytestqt.exceptions.TimeoutError):
            with qtbot.wait_signal(handler.data.statusChanged, timeout=500):
                handler.on_data(d)

    def test_enum_update(self, qtbot):
        testcase = EnumTestCase.compile()
        handler = testcase.query_handler
        d = testcase.initialize_dict
        handler.on_data(d)
        from tests.test_codegen.schemas.object_with_enum import Status

        assert handler.data.status != Status.Disconnected.name
        d[testcase.first_field]["status"] = Status.Disconnected.name
        with qtbot.wait_signal(handler.data.statusChanged, timeout=500):
            handler.on_data(d)
        assert handler.data.status == Status.Disconnected.value

    def test_list_no_update(self, qtbot):
        testcase = ObjectWithListOfObjectTestCase.compile()
        init_dict = testcase.initialize_dict
        handler = testcase.query_handler
        handler.on_data(init_dict)
        model: QGraphQListModel = handler.data.persons
        with pytest.raises(
            pytestqt.exceptions.TimeoutError, match="Received 0 of the 2 expected signals."
        ):
            with qtbot.wait_signals(
                [model.rowsAboutToBeRemoved, model.rowsAboutToBeInserted], timeout=500
            ):
                handler.on_data(init_dict)

    def test_list_update_insert(self, qtbot):
        testcase = ObjectWithListOfObjectTestCase.compile()
        init_dict = testcase.initialize_dict
        init_dict2 = testcase.initialize_dict
        handler = testcase.query_handler
        handler.on_data(init_dict)
        model: QGraphQListModel = handler.data.persons
        init_dict2[testcase.first_field]["id"] = handler.data.id
        with qtbot.wait_signal(model.rowsAboutToBeInserted, timeout=500):
            handler.on_data(init_dict2)

    def test_list_update_crop(self, qtbot):
        testcase = ObjectWithListOfObjectTestCase.compile()
        init_dict = testcase.initialize_dict
        init_dict2 = testcase.initialize_dict
        init_dict[testcase.first_field]["persons"].extend(
            testcase.initialize_dict[testcase.first_field]["persons"]
        )
        handler = testcase.query_handler
        handler.on_data(init_dict)
        model: QGraphQListModel = handler.data.persons
        init_dict2[testcase.first_field]["id"] = handler.data.id
        with qtbot.wait_signals(
            [model.rowsAboutToBeRemoved, model.rowsAboutToBeInserted], timeout=500
        ):
            handler.on_data(init_dict2)


class TestDefaultConstructor:
    @pytest.mark.parametrize("scalar", BuiltinScalars, ids=lambda v: v.graphql_name)
    def test_builtin_scalars(self, scalar: BuiltinScalar):
        testcase = ScalarsTestCase.compile()
        klass = testcase.gql_type
        inst = klass()
        f = testcase.get_field_by_type(scalar)
        assert getattr(inst, f.private_name) == scalar.default_value

    def test_nested_object(self, qtbot):
        # types that refer each-other can cause recursion error
        # This is why we set object types to null.
        testcase = NestedObjectTestCase.compile()
        klass = testcase.gql_type
        inst = klass()
        assert inst.person is None

    def test_object_with_list_of_object(self):
        testcase = ObjectWithListOfObjectTestCase.compile()
        inst = testcase.gql_type()
        assert inst.persons == []  # default of model is empty list atm.

    @pytest.mark.parametrize(("testcase", "scalar", "fname"), custom_scalar_testcases)
    def test_custom_scalars(
        self, testcase: QGQLObjectTestCase, scalar: BaseCustomScalar, fname: str
    ):
        testcase = testcase.compile()
        inst = testcase.gql_type()
        field = testcase.get_field_by_name(fname)
        assert getattr(inst, field.private_name).to_qt() == scalar().to_qt()

    def test_enum(self):
        testcase = EnumTestCase.compile()
        inst = testcase.gql_type()
        f = testcase.get_field_by_name("status")
        assert (
            getattr(inst, f.private_name)
            == testcase.module.Status(1)
            == testcase.module.Status.Connected
        )

    def test_union(self):
        testcase = UnionTestCase.compile()
        testcase.gql_type()

    def test_wont_recursive(self):
        testcase = ObjectsThatReferenceEachOtherTestCase.compile()
        testcase.gql_type()


class TestGarbageCollection:
    def test_root_object_with_scalars_cleanup_when_no_subscribers(self, qtbot, schemas_server):
        testcase = ScalarsTestCase.compile(url=schemas_server.address)
        testcase.query_handler.fetch()
        qtbot.wait_until(lambda: testcase.query_handler.completed)
        node = testcase.query_handler.data
        node_id = node.id
        assert node is testcase.gql_type.__store__.get_node(node_id)
        testcase.query_handler.deleteLater()
        assert not testcase.gql_type.__store__.get_node(node_id)
        assert not testcase.query_handler.data

    def test_refetch(self, qtbot, schemas_server):
        testcase = ScalarsTestCase.compile(url=schemas_server.address)
        testcase.query_handler.fetch()
        qtbot.wait_until(lambda: testcase.query_handler.completed)
        node = testcase.query_handler.data
        node_id = node.id
        assert node is testcase.gql_type.__store__.get_node(node_id)
        testcase.query_handler.dispose()
        assert not testcase.gql_type.__store__.get_node(node_id)
        assert not testcase.query_handler.data
        testcase.query_handler.refetch()
        qtbot.wait_until(lambda: bool(testcase.query_handler._data))

    def test_nested_object(self, qtbot, schemas_server):
        testcase = NestedObjectTestCase.compile(url=schemas_server.address)
        testcase.query_handler.fetch()
        qtbot.wait_until(lambda: testcase.query_handler.completed)
        node = testcase.query_handler.data.person
        node_id = node.id
        assert node is node.__store__.get_node(node_id)
        testcase.query_handler.deleteLater()
        assert not testcase.gql_type.__store__.get_node(node_id)
        assert not testcase.query_handler.data

    def test_object_with_list_of_object(self, qtbot, schemas_server):
        testcase = ObjectWithListOfObjectTestCase.compile(url=schemas_server.address)
        testcase.query_handler.fetch()
        qtbot.wait_until(lambda: testcase.query_handler.completed)
        persons = testcase.query_handler.data.persons._data
        testcase.query_handler.deleteLater()
        for person in persons:
            assert not person.__store__.get_node(person.id)
        assert not testcase.query_handler.data

    def test_root_field_list_of_object(self, qtbot, schemas_server):
        testcase = RootListOfTestCase.compile(url=schemas_server.address)
        testcase.query_handler.fetch()
        qtbot.wait_until(lambda: testcase.query_handler.completed)
        users = testcase.query_handler.data._data
        testcase.query_handler.deleteLater()
        for user in users:
            assert not user.__store__.get_node(user.id)
        assert not testcase.query_handler.data

    def test_type_with_no_id(self, qtbot):
        testcase = TypeWithNoIDTestCase.compile()
        testcase.query_handler.on_data(testcase.initialize_dict)
        user = weakref.ref(testcase.query_handler.data._data[0])
        assert user()._name
        testcase.query_handler.loose()
        qtbot.wait_until(lambda: not user())
        assert not testcase.query_handler.data

    def test_union(self, qtbot):
        testcase = UnionTestCase.compile()
        handler = testcase.query_handler

        handler.on_data(testcase.initialize_dict)
        union_node = weakref.ref(handler.data.whoAmI)
        assert union_node()
        handler.loose()
        qtbot.wait_until(lambda: not union_node())

    def test_duplicate_object_on_same_handler(self, qtbot, monkeypatch):
        monkeypatch.setattr(
            ObjectWithListOfObjectTestCase,
            "query",
            ObjectWithListOfObjectTestCase.query.replace("user", "userWithSamePerson"),
        )
        testcase = ObjectWithListOfObjectTestCase.compile()
        handler = testcase.query_handler
        handler.on_data(testcase.initialize_dict)
        p1 = weakref.ref(handler._data.persons._data[0])
        for person in handler.data.persons._data:
            assert person.id == p1().id
        del person
        handler.loose()
        qtbot.wait_until(lambda: not p1())
