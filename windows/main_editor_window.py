import sys
import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QScrollArea, QComboBox, 
    QListWidget, QApplication, QLabel, QFrame
)
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import Qt, QFileInfo, QDir

# Import the custom slide item widget
from slide_editor_item_widget import SlideEditorItemWidget

class MainEditorWindow(QMainWindow):
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)

        # Load the UI file
        loader = QUiLoader()
        script_dir = QFileInfo(__file__).absolutePath()
        ui_file_path = QDir(script_dir).filePath("main_editor_window.ui")

        # Load the .ui file. This will return the QMainWindow instance defined in the .ui file.
        # We load it without a specific Qt parent first, or pass self if self should be its Qt parent.
        # Let's call the loaded instance 'loaded_ui_window'.
        loaded_ui_window = loader.load(ui_file_path, self) # self will be the Qt parent

        if not loaded_ui_window:
            print(f"Failed to load UI file: {ui_file_path}")
            # Fallback: Set a central widget with an error message
            error_label = QLabel("Error: Could not load main_editor_window.ui")
            error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setCentralWidget(error_label) # 'self' is the QMainWindow we are configuring
            self.setWindowTitle("Error Loading UI")
            return

        # 'self' (this instance of MainEditorWindow) is the QMainWindow we want to use.
        # We will take the central widget and properties from 'loaded_ui_window'.

        try:
            # Transfer window title and other QMainWindow properties from loaded_ui_window to self FIRST.
            # This is done before altering loaded_ui_window's structure (like taking its central widget),
            # which might lead to its premature cleanup if self is its parent.
            self.setWindowTitle(loaded_ui_window.windowTitle())
            self.setGeometry(loaded_ui_window.geometry())

            # Transfer the central widget from loaded_ui_window to self.
            # This also handles reparenting of the central widget.
            central_widget_from_ui = loaded_ui_window.centralWidget()
            if central_widget_from_ui:
                self.setCentralWidget(central_widget_from_ui)
            else:
                print("Warning: loaded_ui_window has no central widget.")
                # Set a default central widget for 'self' if needed
                self.setCentralWidget(QWidget(self)) 

            # TODO: Transfer MenuBar, ToolBars, StatusBar if they exist in loaded_ui_window
            # and you want them on 'self'. Example:
            # if loaded_ui_window.menuBar(): self.setMenuBar(loaded_ui_window.menuBar())

        except RuntimeError as e:
            print(f"RuntimeError during UI setup from loaded_ui_window: {e}")
            # Fallback or re-raise if critical
            error_label = QLabel(f"Error during UI setup: {e}\nLoaded UI might be incomplete.")
            self.setCentralWidget(error_label)
            return # Stop further initialization if basic setup failed

        # Child widgets (like templates_combo_box) are now part of self.centralWidget(),
        # or directly part of 'self' if they are dock widgets, toolbars, etc.
        # Therefore, self.findChild() should work correctly on 'self' to find them.
        #self.templates_combo_box: QComboBox = self.findChild(QComboBox, "templates_combo_box")
        self.main_slides_scroll_area: QScrollArea = self.findChild(QScrollArea, "main_slides_scroll_area")
        self.scroll_area_content_widget: QWidget = self.findChild(QWidget, "scrollAreaContentWidget")
        self.slides_container_layout: QVBoxLayout = None

        if self.scroll_area_content_widget:
            self.slides_container_layout = self.scroll_area_content_widget.layout()
            if not self.slides_container_layout: # If layout wasn't set in Qt Designer
                 self.slides_container_layout = QVBoxLayout(self.scroll_area_content_widget)
                 print("Warning: slides_container_layout was not set in UI, created dynamically.")
        else:
            print("Error: scrollAreaContentWidget not found!")

        self.slide_thumbnails_list_widget: QListWidget = self.findChild(QListWidget, "slide_thumbnails_list_widget")

        # Connect signals or add initial items
        # The global templates_combo_box is removed, so this connection is also removed.
        # if self.templates_combo_box:
        #     self.templates_combo_box.currentTextChanged.connect(self.on_template_changed)

        # The 'loaded_ui_window' instance has served its purpose of providing the initial structure.
        # Since its central widget (and potentially menubar etc.) has been reparented to 'self',
        # 'loaded_ui_window' is now an empty shell. It's also a child of 'self' due to the parent argument in load().
        # Qt's parent-child system should manage its lifecycle. Or, you could explicitly:
        # loaded_ui_window.deleteLater() # If you want to be sure it's cleaned up and not lingering.

        # Example: Add a few slide items
        self.add_slide_item("slide_001")
        self.add_slide_item("slide_002")

    def add_slide_item(self, slide_id: str):
        if not self.slides_container_layout:
            print("Error: Cannot add slide item, slides_container_layout is not available.")
            return

        new_slide_widget = SlideEditorItemWidget(slide_id=slide_id, parent=self.scroll_area_content_widget)
        self.slides_container_layout.addWidget(new_slide_widget)
        
        # Add a separator line
        separator = QFrame(self.scroll_area_content_widget)
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        # separator.setStyleSheet("background-color: #c0c0c0;") # Optional: for a specific color
        self.slides_container_layout.addWidget(separator)

        # Add to thumbnails (placeholder)
        if self.slide_thumbnails_list_widget:
            self.slide_thumbnails_list_widget.addItem(f"Thumbnail for {slide_id}")

        print(f"Added slide item: {slide_id}")

    # This method is no longer needed as template selection is per-slide.
    # def on_template_changed(self, template_name: str):
    #     print(f"Global template changed to: {template_name}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    main_editor = MainEditorWindow()
    main_editor.show()
    
    sys.exit(app.exec())
