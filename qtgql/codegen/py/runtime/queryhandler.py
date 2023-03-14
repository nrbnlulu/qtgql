from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    Dict,
    Generic,
    NamedTuple,
    Optional,
    TypeVar,
)

from PySide6.QtCore import QObject, Signal
from PySide6.QtQuick import QQuickItem

from qtgql.codegen.py.runtime.environment import get_gql_env
from qtgql.tools import qproperty, slot

if TYPE_CHECKING:
    from qtgql.gqltransport.client import GqlClientMessage

T_QObject = TypeVar("T_QObject", bound=QObject)


class SelectionConfig(NamedTuple):
    selections: Dict[str, Optional[SelectionConfig]] = {}
    choices: Dict[str, SelectionConfig] = {}


class OperationMetaData(NamedTuple):
    operation_name: str
    selections: SelectionConfig


T = TypeVar("T")


class BaseOperationHandler(QObject, Generic[T]):
    # class-vars
    ENV_NAME: ClassVar[str]
    OPERATION_METADATA: ClassVar[OperationMetaData]
    _message_template: ClassVar[GqlClientMessage]

    # signals
    dataChanged = Signal()
    completedChanged = Signal()
    operationOnFlightChanged = Signal()
    errorChanged = Signal()

    def __init__(self, parent: Optional[QObject]):
        super().__init__(parent)
        name = self.__class__.__name__
        self.setObjectName(name)
        self._completed: bool = False  # whether the graphql operation completed.
        self._operation_on_the_fly: bool = False
        self._data: Optional[T] = None
        self.environment = get_gql_env(self.ENV_NAME)

    def loose(self) -> None:
        """Releases retention from all children, real implementation is
        generated."""
        raise NotImplementedError

    @slot
    def fetch(self) -> None:
        if not self._operation_on_the_fly and not self._completed:
            self.set_operation_on_flight(True)
            self.environment.client.execute(self)  # type: ignore

    @slot
    def refetch(self) -> None:
        self.set_completed(False)
        self.fetch()

    @property
    def message(self) -> GqlClientMessage:
        return self._message_template

    @qproperty(QObject, notify=dataChanged)
    def data(self) -> Optional[T]:
        return self._data

    def set_completed(self, v: bool) -> None:
        self._completed = v
        self.completedChanged.emit()

    @qproperty(bool, notify=completedChanged)
    def completed(self):
        return self._completed

    def set_operation_on_flight(self, v: bool) -> None:
        self._operation_on_the_fly = v
        self.operationOnFlightChanged.emit()

    @qproperty(bool, notify=operationOnFlightChanged)
    def operationOnFlight(self) -> bool:
        return self._operation_on_the_fly

    def on_data(self, message: dict) -> None:  # pragma: no cover
        # real is on derived class.
        raise NotImplementedError

    def on_completed(self) -> None:
        self._completed = True
        self.completedChanged.emit()

    def on_error(self, message: list[dict[str, Any]]) -> None:  # pragma: no cover
        # This (unlike `on_data` is not implemented for real)
        raise NotImplementedError(message)

    @slot
    def dispose(self) -> None:
        """Get rid of ownership on related data and set data to null."""
        self.loose()

    def deleteLater(self) -> None:
        self.dispose()
        super().deleteLater()


class BaseQueryHandler(BaseOperationHandler[T]):
    """Each handler will be exposed to QML and."""

    ...


class BaseMutationHandler(BaseOperationHandler):
    commit: Callable


class UseQueryABC(QQuickItem, Generic[T]):
    """Concrete implementation in the template."""

    ENV_NAME: ClassVar[str]

    # signals
    operationNameChanged = Signal()

    def __init__(self, parent: Optional[QQuickItem] = None):
        super().__init__(parent)
        self.env = get_gql_env(self.ENV_NAME)
        self._handler: BaseQueryHandler[T] = self._get_handler()
        self.destroyed.connect(self._handler.dispose)  # type: ignore

    @qproperty()
    def handler(self) -> BaseQueryHandler[T]:
        return self._handler

    def componentComplete(self) -> None:
        self._handler.fetch()
        super().componentComplete()

    @classmethod
    def _get_handler(cls) -> BaseQueryHandler[T]:
        # real implementation is generated.
        raise NotImplementedError
