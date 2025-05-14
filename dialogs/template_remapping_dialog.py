import copy
from typing import Dict, List, Any, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QDialogButtonBox,
    QComboBox, QWidget, QScrollArea, QFormLayout, QTextEdit
)
from PySide6.QtCore import Qt


class TemplateRemappingDialog(QDialog):
    def __init__(self,
                 old_text_content: Dict[str, str],
                 new_layout_text_box_ids: List[str],
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Remap Text Box Content")
        self.setMinimumWidth(500)

        self.old_text_content = old_text_content
        self.new_layout_text_box_ids = new_layout_text_box_ids
        self.mapping_combos: Dict[str, QComboBox] = {}

        main_layout = QVBoxLayout(self)

        # --- Instructions ---
        instructions = QLabel(
            "The new layout has different text boxes. "
            "Please map the existing text content to the new text boxes."
        )
        instructions.setWordWrap(True)
        main_layout.addWidget(instructions)

        # --- Scroll Area for Mappings ---
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        self.form_layout = QFormLayout(scroll_widget)
        scroll_area.setWidget(scroll_widget)
        main_layout.addWidget(scroll_area)

        # --- Populate Mappings ---
        self._populate_mapping_options()

        # --- Dialog Buttons ---
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

        self.setLayout(main_layout)

    def _populate_mapping_options(self):
        source_options = ["< Leave Empty >"] # Option to not map anything
        if self.old_text_content:
            source_options.append("--- Existing Content ---") # Separator
            for old_tb_id, old_text in self.old_text_content.items():
                preview = old_text[:30].replace("\n", " ") + ("..." if len(old_text) > 30 else "")
                source_options.append(f"{old_tb_id}: \"{preview}\"")

        for new_tb_id in self.new_layout_text_box_ids:
            label = QLabel(f"Content for new box '{new_tb_id}':")
            combo = QComboBox()
            combo.addItem("< Leave Empty >", userData=None) # UserData is None for empty

            if self.old_text_content:
                # Add a non-selectable separator
                combo.insertSeparator(combo.count())

                for old_tb_id, old_text in self.old_text_content.items():
                    preview = old_text[:30].replace("\n", " ") + ("..." if len(old_text) > 30 else "")
                    combo.addItem(f"Use content from '{old_tb_id}' (\" {preview} \")", userData=old_tb_id)

            # Attempt a smart default: if a new_tb_id matches an old_tb_id, select it.
            if new_tb_id in self.old_text_content:
                index_to_select = -1
                for i in range(combo.count()):
                    if combo.itemData(i) == new_tb_id:
                        index_to_select = i
                        break
                if index_to_select != -1:
                    combo.setCurrentIndex(index_to_select)
            elif not self.mapping_combos and self.old_text_content: # For the very first new box, if no direct match, map first old content
                first_old_id = next(iter(self.old_text_content.keys()), None)
                if first_old_id:
                    index_to_select = -1
                    for i in range(combo.count()):
                        if combo.itemData(i) == first_old_id:
                            index_to_select = i
                            break
                    if index_to_select != -1:
                         combo.setCurrentIndex(index_to_select)

            self.form_layout.addRow(label, combo)
            self.mapping_combos[new_tb_id] = combo

    def get_remapping(self) -> Dict[str, Optional[str]]:
        """
        Returns a dictionary mapping new_text_box_id to the old_text_box_id
        from which content should be sourced, or None if it should be left empty.
        """
        remapping = {}
        for new_tb_id, combo in self.mapping_combos.items():
            selected_old_tb_id = combo.currentData() # This will be the old_tb_id or None
            remapping[new_tb_id] = selected_old_tb_id
        return remapping

if __name__ == '__main__': # Basic test
    from PySide6.QtWidgets import QApplication
    import sys
    app = QApplication(sys.argv)
    old_content = {"title": "Old Title Text", "body": "This is the old body content that is quite long and should be truncated.", "footer": "Old Footer"}
    new_ids = ["header_area", "main_content_area", "footer_area", "caption_area"]
    dialog = TemplateRemappingDialog(old_content, new_ids)
    if dialog.exec():
        print("Accepted Remapping:", dialog.get_remapping())
    else:
        print("Cancelled")
    sys.exit()