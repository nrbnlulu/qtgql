from __future__ import annotations

from collections import defaultdict
from textwrap import dedent
from typing import List, NamedTuple, Optional

import attrs
from graphql import language as gql_lang

from qtgql.codegen.graphql_ref import is_field_node, is_inline_fragment
from qtgql.codegen.py.compiler.template import (
    ConfigContext,
    config_template,
)
from qtgql.codegen.py.objecttype import GqlFieldDefinition, GqlTypeDefinition
from qtgql.codegen.utils import AntiForwardRef


def get_field_from_field_node(
    selection: gql_lang.FieldNode, field_type: GqlTypeDefinition
) -> QtGqlQueriedField:
    field_node = is_field_node(selection)
    assert field_node
    return QtGqlQueriedField.from_field(
        field_type.fields_dict[field_node.name.value], selection_set=field_node.selection_set
    )


ID_SELECTION_NODE = (
    gql_lang.FieldNode(name=gql_lang.NameNode(value="id"), arguments=(), directives=()),
)


def inject_id_selection(selection_set: gql_lang.SelectionSetNode) -> None:
    selection_set.selections += ID_SELECTION_NODE


def has_id_field(selection_set: gql_lang.SelectionSetNode) -> bool:
    for field in selection_set.selections:
        assert isinstance(field, gql_lang.FieldNode)
        if field.name.value == "id":
            return True
    return False


@attrs.define
class QtGqlQueriedField(GqlFieldDefinition):
    selections: List[QtGqlQueriedField] = attrs.Factory(list)
    choices: dict[str, List[QtGqlQueriedField]] = attrs.Factory(lambda: defaultdict(list))

    @classmethod
    def from_field(
        cls, f: GqlFieldDefinition, selection_set: Optional[gql_lang.SelectionSetNode]
    ) -> QtGqlQueriedField:
        ret = cls(**attrs.asdict(f, recurse=False))
        if not hasattr(selection_set, "selections"):
            return ret
        assert selection_set
        # inject ID field for types that supports it. unions are handled below.
        if f.can_select_id and not has_id_field(selection_set):
            inject_id_selection(selection_set)

        for selection in selection_set.selections:
            if inline_frag := is_inline_fragment(selection):
                tp = ret.type
                if tp.is_model:  # list of unions.
                    tp = tp.is_model
                assert tp.is_union()  # ATM supported fragments are unions only.
                type_name = inline_frag.type_condition.name.value
                concrete = next(t for t in tp.of_type if t.type.name == type_name)
                assert issubclass(concrete.type, AntiForwardRef)
                concrete = concrete.type.resolve()
                assert isinstance(concrete, GqlTypeDefinition)
                if not has_id_field(inline_frag.selection_set) and concrete.has_id_field:
                    inject_id_selection(inline_frag.selection_set)

                for selection_node in inline_frag.selection_set.selections:
                    field_node = is_field_node(selection_node)
                    assert field_node
                    if field_node.name.value == "__typename":
                        continue
                    ret.choices[type_name].append(get_field_from_field_node(field_node, concrete))
            else:
                # unions have inline fragments so this should be either
                f_type = f.type.is_object_type
                if not f_type and f.type.is_model:
                    f_type = f.type.is_model.is_object_type
                assert f_type
                field_node = is_field_node(selection)
                assert field_node
                ret.selections.append(get_field_from_field_node(field_node, f_type))
        return ret

    def as_conf_string(self) -> str:
        return dedent(
            config_template(
                context=ConfigContext(self),
            )
        )


class QtGqlOperationDefinition(NamedTuple):
    query: str
    name: str
    field: QtGqlQueriedField
    directives: list[str] = []
    fragments: list[str] = []

    @property
    def operation_config(self) -> str:
        return self.field.as_conf_string()
