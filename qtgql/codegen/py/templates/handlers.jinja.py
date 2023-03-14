from qtgql.tools import slot

{% import "macros.jinja.py" as macros %}

from typing import Optional, Union
from PySide6.QtCore import Signal, QObject
from PySide6.QtQml import QmlElement, QmlSingleton
from qtgql.codegen.py.runtime.queryhandler import BaseQueryHandler, UseQueryABC, SelectionConfig, OperationMetaData, BaseMutationHandler
from qtgql.gqltransport.client import  GqlClientMessage, QueryPayload
from qtgql.codegen.py.runtime.bases import QGraphQListModel
from objecttypes import * # noqa


QML_IMPORT_NAME = "generated.{{context.config.env_name}}"
QML_IMPORT_MAJOR_VERSION = 1


{% macro operation_classvars(operation_def) %}
    ENV_NAME = "{{context.config.env_name}}"
    OPERATION_METADATA = OperationMetaData(
        operation_name="{{operation_def.name}}",
        selections={{operation_def.operation_config}}
    )
    _message_template = GqlClientMessage(payload=QueryPayload(query="""{{operation_def.query}}""", operationName="{{operation_def.name}}"))
{% endmacro %}

{% macro operation_common(operation_def) %}
    def set_data(self, d: {{operation_def.field.annotation}}) -> None:
        self._data = d
        self.dataChanged.emit()

    def update(self, data: dict) -> None:
        parent = self
        metadata = self.OPERATION_METADATA
        config = self.OPERATION_METADATA.selections

        {{macros.update_field(operation_def.field, fset_name='self.dataChanged', private_name='self._data',
                              include_selection_check=False) | indent(4, True)}}

    def loose(self) -> None:
        metadata = self.OPERATION_METADATA
        {% set private_name %}self._data{% endset %}
        {{macros.loose_field(operation_def.field, private_name)}}


    def deserialize(self, data: dict) -> None:
        metadata = self.OPERATION_METADATA
        config = self.OPERATION_METADATA.selections
        parent = self
        {% set assign_to %}self._data{% endset %}
        {{macros.deserialize_field(operation_def.field, assign_to, include_selection_check=False) | indent(4)}}
        self.dataChanged.emit()
    def on_data(self, message: dict) -> None:
        self._operation_on_the_fly = False

        if not self._data:
            self.deserialize(message)

        # data existed and arrived data was null, empty data.
        elif not message.get('{{operation_def.field.name}}', None):
            self._data = None
            self.dataChanged.emit()
        # data existed already, update the data
        else:
            self.update(message)
{% endmacro %}


{% for query in context.queries %}

class {{query.name}}(BaseQueryHandler[{{query.field.annotation}}]):

    {{operation_classvars(query)}}
    {{operation_common(query)}}

@QmlElement
class Require{{query.name}}(UseQueryABC):
    ENV_NAME = "{{context.config.env_name}}"

    def _get_handler(self) -> BaseQueryHandler[{{query.field.annotation}}]:
        return {{query.name}}(self)
{% endfor %}

{% for mutation in context.mutations %}
class {{query.name}}(BaseMutationHandler[{{query.field.annotation}}]):
    @slot
    def commit(self) -> None:
        self.refetch()

{% endfor %}

