import sys
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTextEdit, QPushButton, QApplication, QFrame, QComboBox
)
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import Qt, QFileInfo, QDir

class SlideEditorItemWidget(QWidget):
    def __init__(self, slide_id: str = "default_id", parent: QWidget = None):
        super().__init__(parent)
        self.slide_id = slide_id

        # Load the UI file
        loader = QUiLoader()
        script_dir = QFileInfo(__file__).absolutePath()
        ui_file_path = QDir(script_dir).filePath("slide_editor_item.ui")
        
        # The loaded_ui will be the QWidget "SlideEditorItem" from the .ui file
        loaded_ui = loader.load(ui_file_path, self) 

        if not loaded_ui:
            print(f"Failed to load UI file: {ui_file_path}")
            # Fallback: Create a simple layout if UI fails to load
            fallback_layout = QVBoxLayout(self)
            fallback_layout.addWidget(QLabel("Error: Could not load slide_editor_item.ui"))
            return

        # Take the layout from the loaded UI's root widget and apply it to this QWidget instance
        # This makes this instance (self) effectively become the widget defined in the .ui file.
        self.setLayout(loaded_ui.layout())

        # Now, find the child widgets using self.findChild()
        # (as they are now part of this widget's layout)
        self.slide_name_banner_label: QLabel = self.findChild(QLabel, "slide_name_banner_label")
        self.slide_preview_frame: QFrame = self.findChild(QFrame, "slide_preview_frame")
        self.templates_combo_box_per_slide: QComboBox = self.findChild(QComboBox, "templates_combo_box_per_slide")
        self.slide_preview_label: QLabel = self.findChild(QLabel, "slide_preview_label")
        self.plus_button: QPushButton = self.findChild(QPushButton, "plus_button")
        self.minus_button: QPushButton = self.findChild(QPushButton, "minus_button")

        self.text_box_one_label: QLabel = self.findChild(QLabel, "text_box_one_label")
        self.text_box_one_edit: QTextEdit = self.findChild(QTextEdit, "text_box_one_edit")
        self.text_box_two_label: QLabel = self.findChild(QLabel, "text_box_two_label")
        self.text_box_two_edit: QTextEdit = self.findChild(QTextEdit, "text_box_two_edit")
        self.text_box_three_label: QLabel = self.findChild(QLabel, "text_box_three_label")
        self.text_box_three_edit: QTextEdit = self.findChild(QTextEdit, "text_box_three_edit")

        # Example: Set initial text or connect signals
        if self.slide_name_banner_label:
            self.slide_name_banner_label.setText(f"Editing: {self.slide_id}") # Or a more descriptive name

        if self.slide_preview_label:
            self.slide_preview_label.setText(f"Preview for Slide: {self.slide_id}")
        
        if self.templates_combo_box_per_slide:
            self.templates_combo_box_per_slide.currentTextChanged.connect(self.on_template_selected)
            # Initialize text box visibility based on the default template
            self.on_template_selected(self.templates_combo_box_per_slide.currentText())

    def on_template_selected(self, template_name: str):
        """Handles changes in the per-slide template selection."""
        print(f"Slide '{self.slide_id}': Template selected '{template_name}'")

        # Basic logic to show/hide text boxes based on template name
        # This should be made more robust, perhaps by querying template definitions
        show_one = True
        show_two = True
        show_three = True

        if template_name == "Title Only":
            show_two = False
            show_three = False
        elif template_name == "2 Text Boxes":
            show_three = False
        # Add more conditions for "Image + Text" or other templates

        for widget in [self.text_box_one_label, self.text_box_one_edit]:
            if widget: widget.setVisible(show_one)
        for widget in [self.text_box_two_label, self.text_box_two_edit]:
            if widget: widget.setVisible(show_two)
        for widget in [self.text_box_three_label, self.text_box_three_edit]:
            if widget: widget.setVisible(show_three)

    def get_text_content(self) -> dict:
        """Returns the content of the text boxes."""
        content = {}
        if self.text_box_one_edit:
            content["text_box_one"] = self.text_box_one_edit.toPlainText()
        if self.text_box_two_edit:
            content["text_box_two"] = self.text_box_two_edit.toPlainText()
        if self.text_box_three_edit:
            content["text_box_three"] = self.text_box_three_edit.toPlainText()
        return content

    def set_text_content(self, content: dict):
        """Sets the content of the text boxes."""
        if self.text_box_one_edit and "text_box_one" in content:
            self.text_box_one_edit.setPlainText(content["text_box_one"])
        if self.text_box_two_edit and "text_box_two" in content:
            self.text_box_two_edit.setPlainText(content["text_box_two"])
        if self.text_box_three_edit and "text_box_three" in content:
            self.text_box_three_edit.setPlainText(content["text_box_three"])

    def update_preview(self, image_path: str = None, text: str = None):
        """Updates the slide preview label."""
        if self.slide_preview_label:
            if image_path:
                # For actual image display, you'd use QPixmap and self.slide_preview_label.setPixmap()
                self.slide_preview_label.setText(f"Image: {os.path.basename(image_path)}")
            elif text:
                self.slide_preview_label.setText(text)
            else:
                self.slide_preview_label.setText(f"Preview for Slide: {self.slide_id}")

    def set_slide_name(self, name: str):
        """Updates the slide name banner label."""
        if self.slide_name_banner_label:
            self.slide_name_banner_label.setText(name)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # Test SlideEditorItemWidget
    slide_item_widget = SlideEditorItemWidget("test_slide_01")
    slide_item_widget.setWindowTitle("Slide Editor Item Test")
    slide_item_widget.set_slide_name("My Awesome Test Slide (ID: test_slide_01)")

    slide_item_widget.set_text_content({
        "text_box_one": "Hello from Text Box 1!",
        "text_box_two": "This is the second text box."
    })
    slide_item_widget.update_preview(text="Custom Preview Text")
    slide_item_widget.show()
    
    sys.exit(app.exec())
