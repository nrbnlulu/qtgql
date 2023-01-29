from __future__ import annotations

import inspect
from typing import TYPE_CHECKING

from attrs import define
from jinja2 import Environment, PackageLoader, select_autoescape

if TYPE_CHECKING:
    from qtgql.codegen.py.config import QtGqlConfig
    from qtgql.codegen.py.objecttype import GqlType

env = Environment(loader=PackageLoader("qtgql.codegen.py"), autoescape=select_autoescape())

SchemaTemplate = env.get_template("schema.jinja.py")


@define
class TemplateContext:
    types: list[GqlType]
    config: QtGqlConfig

    @property
    def dependencies(self) -> list[str]:
        def build_import_statement(obj) -> str:
            return f"from {inspect.getmodule(obj).__name__} import {obj.__name__}"

        ret = [build_import_statement(scalar) for scalar in self.config.custom_scalars.values()]
        ret.append(build_import_statement(self.config.base_object))
        return ret

    @property
    def config_name(self) -> str:
        return self.config._self_import_name()[1]

    @property
    def custom_scalars(self) -> list[str]:
        return [scalar.__name__ for scalar in self.config.custom_scalars.values()]

    @property
    def base_object_name(self) -> str:
        return self.config.base_object.__name__


def py_template(context: TemplateContext) -> str:
    return SchemaTemplate.render(context=context)
