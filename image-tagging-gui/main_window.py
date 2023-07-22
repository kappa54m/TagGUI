from pathlib import Path

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (QApplication, QFileDialog, QMainWindow,
                               QPushButton, QStackedWidget, QVBoxLayout,
                               QWidget)

from image_list import ImageList, ImageListModel
from image_tag_list_model import ImageTagListModel
from image_tags_editor import ImageTagsEditor
from image_viewer import ImageViewer
from key_press_forwarder import KeyPressForwarder
from settings import get_settings
from settings_dialog import SettingsDialog
from tag_counter_model import TagCounterModel


class MainWindow(QMainWindow):
    def __init__(self, app: QApplication):
        super().__init__()
        self.app = app
        self.settings = get_settings()
        self.image_list_model = ImageListModel(self.settings)
        self.tag_counter_model = TagCounterModel()
        self.image_tag_list_model = ImageTagListModel()

        self.setWindowTitle('Image Tagging GUI')
        # Not setting this results in some ugly colors.
        self.setPalette(self.app.style().standardPalette())
        self.create_menus()
        self.image_viewer = ImageViewer(image_list_model=self.image_list_model)
        self.create_central_widget()
        self.image_list = ImageList(settings=self.settings,
                                    image_list_model=self.image_list_model)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.image_list)
        self.image_tags_editor = ImageTagsEditor(
            settings=self.settings, image_list_model=self.image_list_model,
            tag_counter_model=self.tag_counter_model,
            image_tag_list_model=self.image_tag_list_model)
        self.addDockWidget(Qt.RightDockWidgetArea, self.image_tags_editor)

        key_press_forwarder = KeyPressForwarder(
            parent=self, target=self.image_list.list_view,
            keys_to_forward=(Qt.Key_Up, Qt.Key_Down, Qt.Key_PageUp,
                             Qt.Key_PageDown))
        self.image_tags_editor.tag_input_box.installEventFilter(
            key_press_forwarder)
        self.image_list_selection_model = (self.image_list.list_view
                                           .selectionModel())
        self.image_list_selection_model.currentChanged.connect(
            self.image_viewer.load_image)
        self.image_list_selection_model.currentChanged.connect(
            self.image_tags_editor.load_image_tags)
        self.image_list_selection_model.currentChanged.connect(
            lambda index: self.settings.setValue('image_index', index.row()))
        self.image_list_model.dataChanged.connect(
            lambda: self.tag_counter_model.count_tags(
                self.image_list_model.images))
        # `rowsInserted` does not have to be connected because `dataChanged`
        # is emitted when a tag is added.
        self.image_tag_list_model.dataChanged.connect(
            self.update_image_list_model_tags)
        self.image_tag_list_model.rowsRemoved.connect(
            self.update_image_list_model_tags)
        self.image_tag_list_model.rowsMoved.connect(
            self.update_image_list_model_tags)

        self.restore()

    def closeEvent(self, event: QCloseEvent):
        """Save the window geometry and state before closing."""
        self.settings.setValue('geometry', self.saveGeometry())
        self.settings.setValue('window_state', self.saveState())
        super().closeEvent(event)

    def load_directory(self, path: Path, select_index: int = 0):
        self.settings.setValue('directory_path', str(path))
        self.image_list_model.load_directory(path)
        # Clear the current index first to make sure that the `currentChanged`
        # signal is emitted even if the image at the index is already selected.
        self.image_list_selection_model.clearCurrentIndex()
        self.image_list.list_view.setCurrentIndex(
            self.image_list_model.index(select_index))
        self.centralWidget().setCurrentWidget(self.image_viewer)

    @Slot()
    def select_and_load_directory(self):
        # Use the last loaded directory as the initial directory.
        if self.settings.contains('directory_path'):
            initial_directory_path = self.settings.value('directory_path')
        else:
            initial_directory_path = ''
        load_directory_path = QFileDialog.getExistingDirectory(
            parent=self, caption='Select directory to load images from',
            dir=initial_directory_path)
        if not load_directory_path:
            return
        self.load_directory(Path(load_directory_path))

    @Slot()
    def show_settings_dialog(self):
        settings_dialog = SettingsDialog(parent=self, settings=self.settings)
        settings_dialog.exec()

    def create_menus(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu('File')
        load_directory_action = QAction('Load directory', self)
        load_directory_action.setShortcut(QKeySequence('Ctrl+L'))
        load_directory_action.triggered.connect(self.select_and_load_directory)
        file_menu.addAction(load_directory_action)
        settings_action = QAction('Settings', self)
        settings_action.setShortcut(QKeySequence('Ctrl+Alt+S'))
        settings_action.triggered.connect(self.show_settings_dialog)
        file_menu.addAction(settings_action)

    def create_central_widget(self):
        central_widget = QStackedWidget()
        # Put the button inside a widget so that it will not fill up the entire
        # space.
        load_directory_widget = QWidget()
        load_directory_button = QPushButton('Load directory')
        load_directory_button.clicked.connect(self.select_and_load_directory)
        QVBoxLayout(load_directory_widget).addWidget(load_directory_button,
                                                     alignment=Qt.AlignCenter)
        central_widget.addWidget(load_directory_widget)
        central_widget.addWidget(self.image_viewer)
        self.setCentralWidget(central_widget)

    @Slot()
    def update_image_list_model_tags(self):
        self.image_list_model.update_tags(
            self.image_tags_editor.image_index,
            self.image_tag_list_model.stringList())

    @Slot()
    def set_font_size(self):
        font = self.app.font()
        font_size = int(self.settings.value('font_size'))
        font.setPointSize(font_size)
        self.app.setFont(font)

    def restore(self):
        # Restore the window geometry and state.
        if self.settings.contains('geometry'):
            self.restoreGeometry(self.settings.value('geometry'))
        else:
            self.showMaximized()
        self.restoreState(self.settings.value('window_state'))
        # Get the last index of the last selected image.
        if self.settings.contains('image_index'):
            image_index = int(self.settings.value('image_index'))
        else:
            image_index = 0
        # Load the last loaded directory.
        if self.settings.contains('directory_path'):
            self.load_directory(Path(self.settings.value('directory_path')),
                                select_index=image_index)
        self.set_font_size()
