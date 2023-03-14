from qtgql.codegen.py.runtime.queryhandler import BaseOperationHandler, UseQueryABC

from tests.test_codegen.test_py.testcases import ScalarsTestCase


def test_data_fetched(qmlbot, schemas_server):
    testcase = ScalarsTestCase.compile(schemas_server.address).load_qml(qmlbot)
    handler = testcase.get_qml_query_handler(qmlbot)

    with qmlbot.bot.wait_signal(handler.dataChanged):
        ...
    assert isinstance(handler.property("data"), testcase.gql_type)


def test_disposes_operation_when_component_is_deleted(qmlbot, schemas_server):
    testcase = ScalarsTestCase.compile(schemas_server.address).load_qml(qmlbot)
    handler = testcase.get_qml_query_handler(qmlbot)
    with qmlbot.bot.wait_signal(handler.completedChanged):
        ...
    assert handler._data
    qmlbot.cleanup()
    qmlbot.bot.wait_until(lambda: not handler._data)


def test_on_completed_emits(qmlbot, schemas_server):
    testcase = ScalarsTestCase.compile(schemas_server.address).load_qml(qmlbot)
    handler = testcase.get_qml_query_handler(qmlbot)
    with qmlbot.bot.wait_signal(handler.completedChanged):
        ...
    assert handler._data
    assert handler.completed


class TestQQuickOperationComp:
    def test_has_handler_prop(self, qmlbot, schemas_server):
        testcase = ScalarsTestCase.compile(schemas_server.address).load_qml(qmlbot)
        operation_wraper = qmlbot.qquickiew.findChildren(UseQueryABC)[0]
        assert isinstance(operation_wraper.property("handler"), BaseOperationHandler)
        qmlbot.cleanup()
