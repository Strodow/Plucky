import sys
import os # For path manipulation if needed for imports
from PySide6.QtWidgets import ( # type: ignore
    QDialog, QVBoxLayout, QFormLayout, QLabel, QTextEdit,
    QDialogButtonBox, QScrollArea, QWidget, QMenu, QApplication
)
from PySide6.QtGui import QAction, QTextCursor # type: ignore
from PySide6.QtCore import Qt, Slot # type: ignore
from typing import Dict, List, Optional, Any

from data_models.slide_data import SlideData # Assuming this path is correct from dialogs folder
from spellchecker import SpellChecker # pip install pyspellchecker

# Assuming ui_utils is a sibling directory to dialogs within a Plucky package structure
try:
    from ..ui_utils.spell_check_highlighter import SpellCheckHighlighter
except ImportError: # Fallback for different execution contexts or if structure is flatter
    sys.path.append(os.path.join(os.path.dirname(__file__), '..')) # Add Plucky parent to path
    from ui_utils.spell_check_highlighter import SpellCheckHighlighter

class EditSlideContentDialog(QDialog):
    def __init__(self, slide_data: SlideData, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Slide Content")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        self._slide_data = slide_data
        self._text_edits_map: Dict[str, QTextEdit] = {} # Renamed for clarity

        # --- Spell Checker Setup ---
        self.spell_checker = SpellChecker()
        self._highlighters_map: Dict[QTextEdit, SpellCheckHighlighter] = {} # To store highlighters for each text edit

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
            # For a "no template" slide, we'll treat it as having one main text box.
            main_text_label = QLabel("Main Text:")
            main_text_edit = QTextEdit()
            # Initialize from slide_data.lyrics OR slide_data.template_settings["text_content"]["main_text"]
            initial_main_text = current_text_content.get("main_text", self._slide_data.lyrics)
            main_text_edit.setPlainText(initial_main_text)
            self._text_edits_map["main_text"] = main_text_edit # Use "main_text" as the key
            
            # Add spell checking for this legacy text edit
            main_text_edit.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            main_text_edit.customContextMenuRequested.connect(
                lambda pos, te=main_text_edit: self._show_text_edit_context_menu(pos, te)
            )
            self._highlighters_map[main_text_edit] = SpellCheckHighlighter(main_text_edit.document(), self.spell_checker)
            form_layout.addRow(main_text_label, main_text_edit)
        else:
            for tb_config in text_boxes_config:
                tb_id = tb_config.get("id")
                tb_name = tb_config.get("name", tb_id) # Use name if available, else ID
                if not tb_id:
                    continue # Skip text boxes without an ID

                label = QLabel(f"{tb_name}:")
                text_edit = QTextEdit()
                text_edit.setPlainText(current_text_content.get(tb_id, ""))
                self._text_edits_map[tb_id] = text_edit

                # Add spell checking for this text edit
                text_edit.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                text_edit.customContextMenuRequested.connect(
                    lambda pos, te=text_edit: self._show_text_edit_context_menu(pos, te)
                )
                self._highlighters_map[text_edit] = SpellCheckHighlighter(text_edit.document(), self.spell_checker)
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
        for tb_id, text_edit_widget in self._text_edits_map.items():
            updated_content[tb_id] = text_edit_widget.toPlainText()
        return updated_content

    @Slot(object, QTextEdit) # position is QPoint, but object for simplicity with lambda
    def _show_text_edit_context_menu(self, position, text_edit_widget: QTextEdit):
        """Shows a custom context menu for the given QTextEdit, including spell check suggestions."""
        menu = text_edit_widget.createStandardContextMenu() # Start with the default menu

        cursor = text_edit_widget.cursorForPosition(position)
        cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        selected_word_raw = cursor.selectedText()

        # Clean the word: remove leading/trailing non-alphanumeric, keep internal apostrophes
        # This regex finds the core word part.
        import re
        match = re.search(r"\b([a-zA-Z']+[a-zA-Z]?)\b", selected_word_raw)
        cleaned_word = match.group(1) if match else ""

        if cleaned_word and self.spell_checker.unknown([cleaned_word]):
            suggestions = self.spell_checker.candidates(cleaned_word)
            if suggestions:
                menu.addSeparator()
                # Limit number of suggestions to keep menu manageable
                for suggestion in list(suggestions)[:7]: # Show top 7 suggestions
                    action = QAction(f"Correct to: {suggestion}", self)
                    action.triggered.connect(
                        lambda checked=False, s=suggestion, c=cursor, w=cleaned_word, te=text_edit_widget:
                        self._correct_word(c, w, s, te)
                    )
                    menu.addAction(action)
                menu.addSeparator()

            add_to_dict_action = QAction(f"Add \"{cleaned_word}\" to Dictionary", self)
            add_to_dict_action.triggered.connect(
                lambda checked=False, w=cleaned_word, te=text_edit_widget: self._add_word_to_dictionary(w, te)
            )
            menu.addAction(add_to_dict_action)

        menu.exec(text_edit_widget.mapToGlobal(position))

    def _correct_word(self, cursor: QTextCursor, original_word: str, replacement_word: str, text_edit_widget: QTextEdit):
        """Replaces the misspelled word with the selected suggestion."""
        # Ensure the cursor is still selecting the intended word or a close approximation.
        # For simplicity, we assume the original cursor selection is still valid enough.
        # A more robust check might involve re-finding the word if text changed significantly.
        if cursor.selectedText().strip() == original_word.strip() or original_word in cursor.selectedText():
            cursor.beginEditBlock()
            cursor.removeSelectedText()
            cursor.insertText(replacement_word)
            cursor.endEditBlock()
        else:
            print(f"Could not apply correction for '{original_word}'. Selection might have changed.")
            QApplication.beep()

    def _add_word_to_dictionary(self, word: str, text_edit_widget: QTextEdit):
        """Adds the word to the spell checker's dictionary and re-highlights."""
        self.spell_checker.add(word)
        highlighter = self._highlighters_map.get(text_edit_widget)
        if highlighter:
            highlighter.rehighlight() # Re-check the entire document for this highlighter
        print(f"Added '{word}' to dictionary.")