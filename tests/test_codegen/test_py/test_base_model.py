from unittest.mock import patch

import pytest
from PySide6.QtCore import QByteArray, QObject, Qt
from qtgql.codegen.py.runtime.bases import QGraphQListModel

from tests.test_codegen.test_py.testcases import ObjectWithListOfObjectTestCase


@pytest.fixture()
def sample_model_initialized() -> QGraphQListModel:
    testcase = ObjectWithListOfObjectTestCase.compile()
    handler = testcase.query_handler
    handler.fetch()
    handler.on_data(testcase.initialize_dict)
    return handler._data.persons


def test_returns_object_role(sample_model_initialized):
    assert sample_model_initialized.roleNames() == {
        Qt.ItemDataRole.UserRole + 1: QByteArray("object")
    }


def test_row_count(sample_model_initialized):
    count = len(sample_model_initialized._data)
    assert count == sample_model_initialized.rowCount()


def test_returns_data(sample_model_initialized):
    sample_model_initialized._data[0] = 2
    assert (
        sample_model_initialized.data(
            sample_model_initialized.index(0), QGraphQListModel.OBJECT_ROLE
        )
        == 2
    )


def test_pop(qtbot, sample_model_initialized):
    original_data = sample_model_initialized._data.copy()
    with qtbot.wait_signal(sample_model_initialized.rowsAboutToBeRemoved):
        sample_model_initialized.pop(0)
    assert original_data != sample_model_initialized._data
    original_data.pop(0)
    assert original_data == sample_model_initialized._data


@patch("PySide6.QtCore.QAbstractListModel.endRemoveRows")
def test_clear(mock, qtbot, sample_model_initialized):
    assert sample_model_initialized.rowCount() > 0
    with qtbot.wait_signal(sample_model_initialized.rowsAboutToBeRemoved):
        sample_model_initialized.clear()

    assert sample_model_initialized.rowCount() == 0
    assert mock.called


def test_append(qtbot, sample_model_initialized):
    with qtbot.wait_signal(sample_model_initialized.rowsAboutToBeInserted):
        sample_model_initialized.append("foo")
    assert sample_model_initialized._data[-1] == "foo"


def test_insert(qtbot, sample_model_initialized):
    with qtbot.wait_signal(sample_model_initialized.rowsAboutToBeInserted):
        sample_model_initialized.insert(2, "foo")
    assert sample_model_initialized.data(sample_model_initialized.index(2), 257) == "foo"


def test_insert_after_max_index(qtbot, sample_model_initialized):
    with qtbot.wait_signal(sample_model_initialized.rowsAboutToBeInserted):
        sample_model_initialized.insert(sample_model_initialized.rowCount() + 200, "foo")
    assert (
        sample_model_initialized.data(
            sample_model_initialized.index(sample_model_initialized.rowCount() - 1), 257
        )
        == "foo"
    )


def test_remove_rows(qtbot, sample_model_initialized):
    sample_model_initialized.append(2)
    sample_model_initialized.append(3)
    prev_data = sample_model_initialized._data
    sample_model_initialized.removeRows(2, 0)
    assert sample_model_initialized._data == prev_data
    sample_model_initialized.removeRows(0, sample_model_initialized.rowCount())
    assert not sample_model_initialized._data


def test_remove_rows_inside(qtbot, sample_model_initialized):
    sample_model_initialized.clear()
    assert not sample_model_initialized._data
    sample_model_initialized.append(2)
    sample_model_initialized.append(3)
    sample_model_initialized.append(4)
    assert 3 in sample_model_initialized._data
    sample_model_initialized.removeRows(1, 2)
    assert 3 not in sample_model_initialized._data


class TestCurrentIndexProp:
    def test_is_0_on_init(self, qtbot, sample_model_initialized):
        assert sample_model_initialized.property("currentIndex") == 0

    def test_setter_emits(self, qtbot, sample_model_initialized):
        with qtbot.wait_signal(sample_model_initialized.currentIndexChanged):
            sample_model_initialized.set_current_index(2)
            assert sample_model_initialized.property("currentIndex") == 2


class TestCurrentObject:
    def test_getter(self, qtbot, sample_model_initialized):
        expected = QObject()
        sample_model_initialized._data.insert(0, expected)
        sample_model_initialized.set_current_index(0)
        assert sample_model_initialized.property("currentObject") is expected

    def test_setter(self, qtbot, sample_model_initialized):
        first = sample_model_initialized._data[0]
        second = QObject()
        sample_model_initialized._data.insert(1, second)
        assert sample_model_initialized.currentObject is first
        with qtbot.wait_signal(sample_model_initialized.currentIndexChanged):
            sample_model_initialized.set_current_index(1)
            assert sample_model_initialized.currentObject is second

    def test_is_first_element_when_initialized(self, sample_model_initialized):
        first = sample_model_initialized._data[0]
        assert sample_model_initialized.currentObject is first
        assert sample_model_initialized.property("currentObject") is first
