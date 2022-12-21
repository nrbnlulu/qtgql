import glob
import os
from pathlib import Path
import sys

from qtpy import QtCore, QtGui, QtQml, QtQuick
from qtpy.QtCore import QObject, Signal
from qtpy.QtQml import QQmlApplicationEngine

from qtier import slot
from qtier.gql.client import GqlClientMessage, GqlWsTransportClient, HandlerProto
from qtier.itemsystem import GenericModel
from tests.test_sample_ui.models import Apple

DEV = not os.environ.get("IS_GITHUB_ACTION", False)


class EntryPoint(QObject):
    if DEV:
        qmlFileChanged = Signal()

    class AppleHandler(HandlerProto):
        message = GqlClientMessage.from_query(
            """
            query MyQuery {
              apples {
                color
                owner
                size
                worms {
                  family
                  name
                  size
                }
              }
            }
            """
        )

        def __init__(self, app: "EntryPoint"):
            self.app = app

        def on_data(self, message: dict) -> None:
            self.app.apple_model.initialize_data(message["apples"])

        def on_error(self, message: dict) -> None:
            print(message)

        def on_completed(self, message: dict) -> None:
            print(message)

    def __init__(self, parent=None):
        super().__init__(parent)
        main_qml = Path(__file__).parent / "qml" / "main.qml"
        QtGui.QFontDatabase.addApplicationFont(
            str(main_qml.parent / "materialdesignicons-webfont.ttf")
        )
        self.qml_engine = QQmlApplicationEngine()
        self.gql_client = GqlWsTransportClient(url="ws://localhost:8080/graphql")
        self.apple_query_handler = self.AppleHandler(self)
        self.gql_client.query(self.apple_query_handler)
        self.apple_model: GenericModel[Apple] = Apple.Model()
        QtQml.qmlRegisterSingletonInstance(EntryPoint, "com.props", 1, 0, "EntryPoint", self)  # type: ignore
        # for some reason the app won't initialize without this event processing here.
        QtCore.QEventLoop().processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 1000)
        self.qml_engine.load(str(main_qml.resolve()))

        if DEV:
            qml_files = []
            for file in glob.iglob("**/*.qml", root_dir=main_qml.parent, recursive=True):
                qml_files.append(str((main_qml.parent / file).resolve()))
            self.file_watcher = QtCore.QFileSystemWatcher(self)
            self.file_watcher.addPaths(qml_files)
            self.file_watcher.fileChanged.connect(self.on_qml_file_changed)  # type: ignore

    @QtCore.Property(QtCore.QObject, constant=True)
    def appleModel(self) -> GenericModel[Apple]:
        return self.apple_model

    if DEV:  # pragma: no cover

        @slot
        def on_qml_file_changed(self) -> None:
            self.qml_engine.clearComponentCache()
            for window in self.qml_engine.rootObjects():  # type: ignore
                window: QtQuick.QQuickWindow
                loader: QtQuick.QQuickItem = window.findChild(QtQuick.QQuickItem, "debug_loader")  # type: ignore
                QtCore.QEventLoop().processEvents(
                    QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 1000
                )
                prev = loader.property("source")
                loader.setProperty("source", "")
                loader.setProperty("source", prev)

    def deleteLater(self) -> None:
        # Deleting the engine before it goes out of scope is required to make sure
        # all child QML instances are destroyed in the correct order.
        del self.qml_engine
        super().deleteLater()


def main():  # pragma: no cover
    app = QtGui.QGuiApplication(sys.argv)
    ep = EntryPoint()  # noqa: F841, this collected by the gc otherwise.
    ret = app.exec()
    sys.exit(ret)


if __name__ == "__main__":
    main()