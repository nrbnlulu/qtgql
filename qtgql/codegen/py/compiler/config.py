from functools import cached_property
from pathlib import Path
from typing import Callable, Type

from attrs import define

from qtgql.codegen.introspection import SchemaEvaluator
from qtgql.codegen.py.compiler.template import TemplateContext, schema_types_template
from qtgql.codegen.py.runtime.bases import BaseGraphQLObject, _BaseQGraphQLObject
from qtgql.codegen.py.runtime.custom_scalars import CUSTOM_SCALARS, CustomScalarMap


@define(slots=False)
class QtGqlConfig:
    """Encapsulates configurations for a qtgql-codegen application per GraphQL
    schema."""

    graphql_dir: Path
    """A directory contains [schema.graphql, query.graphql, mutation.graphql,
    subscription.graphql] generated types come from the schema.

    and queries, mutations, subscription handlers would be generated
    from the corresponding `.graphql` files.
    """
    env_name: str = "QGqlEnv"
    """The generated types would find the environment by this name.

    Also the generated QML imports would fall under this namespace.
    """
    evaluator: Type[SchemaEvaluator] = SchemaEvaluator
    """evaluates the schema and generates types."""
    custom_scalars: CustomScalarMap = CUSTOM_SCALARS
    """mapping of custom scalars, respected by the schema evaluator."""
    template_class: Callable[[TemplateContext], str] = schema_types_template
    """jinja template."""
    base_object: Type[_BaseQGraphQLObject] = BaseGraphQLObject
    """base object to be extended by all generated types."""

    @property
    def schema_path(self) -> Path:
        return self.graphql_dir / "schema.graphql"

    @property
    def operations_dir(self) -> Path:
        return self.graphql_dir / "operations.graphql"

    @property
    def generated_types_dir(self) -> Path:
        return self.graphql_dir / "objecttypes.py"

    @property
    def generated_handlers_dir(self) -> Path:
        return self.graphql_dir / "handlers.py"

    @cached_property
    def _evaluator(self) -> SchemaEvaluator:
        return self.evaluator(self)

    def generate(self) -> None:
        self._evaluator.dump()

    def __attrs_post_init__(self):
        if self.custom_scalars != CUSTOM_SCALARS:
            self.custom_scalars.update(CUSTOM_SCALARS)
