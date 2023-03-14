from __future__ import annotations

import contextlib
import importlib
import sys
import tempfile
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from qtgql.codegen.py.compiler.config import QtGqlConfig
from qtgql.exceptions import QtGqlException

from tests.test_codegen.test_py.testcases import ScalarsTestCase

if TYPE_CHECKING:
    from types import ModuleType


@contextlib.contextmanager
def get_fake_module() -> ModuleType:
    with tempfile.TemporaryDirectory() as tmp_path:
        id_ = uuid.uuid4().hex
        file = Path(tmp_path) / f"{id_}.py"
        with file.open("w") as f:
            f.write("")

        spec = importlib.util.spec_from_file_location(id_, file)
        foo = importlib.util.module_from_spec(spec)
        sys.modules[id_] = foo
        spec.loader.exec_module(foo)
        yield foo


@pytest.fixture()
def fake_module(tmp_path) -> ModuleType:
    with get_fake_module() as m:
        yield m


@pytest.fixture()
def pseudo_config(tmp_path) -> QtGqlConfig:
    return QtGqlConfig(graphql_dir=tmp_path)


def test_generate_from_schema(pseudo_config):
    pseudo_config.schema_path.write_text(str(ScalarsTestCase.schema))
    pseudo_config.operations_dir.write_text(ScalarsTestCase.query)
    pseudo_config.generate()
    assert pseudo_config.generated_types_dir.read_text()
    assert pseudo_config.generated_handlers_dir.read_text()


def test_invalid_operation_raises(pseudo_config):
    pseudo_config.schema_path.write_text(str(ScalarsTestCase.schema))
    pseudo_config.operations_dir.write_text("query OpName{NoSuchField}")
    with pytest.raises(QtGqlException):
        pseudo_config.generate()


def test_get_mutation_operations(pseudo_config):
    pseudo_config.schema_path.write_text(str(ScalarsTestCase.schema))
    pseudo_config.operations_dir.write_text(
        """mutation CreateUserNoArgs{createUserNoArgs{
    name
    age
    agePoint
    uuid
    male
    }}"""
    )
    pseudo_config.generate()
    assert pseudo_config._evaluator._mutation_handlers != {}
