import sys
from PySide6.QtWidgets import ( # type: ignore
    QDialog, QVBoxLayout, QFormLayout, QLabel, QTextEdit,
    QDialogButtonBox, QScrollArea, QWidget
)
from PySide6.QtCore import Qt
from typing import Dict, List, Optional, Any

from data_models.slide_data import SlideData # Assuming this path is correct from dialogs folder

class EditSlideContentDialog(QDialog):
    def __init__(self, slide_data: SlideData, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Slide Content")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        self._slide_data = slide_data
        self._text_edits: Dict[str, QTextEdit] = {}

        main_layout = QVBoxLayout(self)

        # Scroll Area for text edits if there are many
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        form_layout = QFormLayout(scroll_widget)

        template_settings = self._slide_data.template_settings
        text_boxes_config: List[Dict[str, Any]] = []
        if template_settings and isinstance(template_settings.get("text_boxes"), list):
            text_boxes_config = template_settings["text_boxes"]

        current_text_content: Dict[str, str] = {}
        if template_settings and isinstance(template_settings.get("text_content"), dict):
            current_text_content = template_settings["text_content"]

        if not text_boxes_config:
            # Fallback if no text boxes are defined in the template
            # This case should ideally be handled by ensuring templates are valid
            # or by disabling the edit option for slides with such templates.
            legacy_lyrics_label = QLabel("Lyrics (Legacy):")
            legacy_lyrics_edit = QTextEdit()
            legacy_lyrics_edit.setPlainText(self._slide_data.lyrics) # Use the old lyrics field
            self._text_edits["legacy_lyrics"] = legacy_lyrics_edit # Use a special key
            form_layout.addRow(legacy_lyrics_label, legacy_lyrics_edit)
        else:
            for tb_config in text_boxes_config:
                tb_id = tb_config.get("id")
                tb_name = tb_config.get("name", tb_id) # Use name if available, else ID
                if not tb_id:
                    continue # Skip text boxes without an ID

                label = QLabel(f"{tb_name}:")
                text_edit = QTextEdit()
                text_edit.setPlainText(current_text_content.get(tb_id, ""))
                self._text_edits[tb_id] = text_edit
                form_layout.addRow(label, text_edit)

        scroll_widget.setLayout(form_layout)
        scroll_area.setWidget(scroll_widget)
        main_layout.addWidget(scroll_area)

        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

        self.setLayout(main_layout)

    def get_updated_content(self) -> Dict[str, str]:
        updated_content: Dict[str, str] = {}
        for tb_id, text_edit_widget in self._text_edits.items():
            updated_content[tb_id] = text_edit_widget.toPlainText()
        return updated_content