import sys
import os
import re # Import regular expressions for word splitting
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QTextEdit, QPushButton,
    QLabel, QHBoxLayout, QFileDialog, QMenu # Added QMenu
)
from PySide6.QtCore import Signal, Slot, Qt # Added Qt
from PySide6.QtGui import (
    QSyntaxHighlighter, QTextCharFormat, QColor, QTextCursor, QAction # Added imports
)

# --- Spell Checking Integration ---
try:
    from spellchecker import SpellChecker
except ImportError:
    SpellChecker = None
    print("Warning: pyspellchecker not found. Install it with 'pip install pyspellchecker' for spell checking.")

class SpellCheckHighlighter(QSyntaxHighlighter):
    """Highlights misspelled words in a QTextDocument."""
    def __init__(self, parent, spell_checker):
        super().__init__(parent)
        self.spell_checker = spell_checker
        self.misspelled_format = QTextCharFormat()
        self.misspelled_format.setUnderlineColor(QColor("red"))
        self.misspelled_format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SpellCheckUnderline)
        # Regex to find words (sequences of letters, possibly with internal apostrophes)
        self.word_pattern = re.compile(r"\b[a-zA-Z']+\b")

    def highlightBlock(self, text):
        if not self.spell_checker:
            return # Do nothing if spellchecker isn't available

        # Find all words in the current block using regex
        for match in self.word_pattern.finditer(text):
            word = match.group()
            # Check spelling (convert to lowercase for checking)
            if word.lower() not in self.spell_checker:
                start_index = match.start()
                length = match.end() - start_index
                self.setFormat(start_index, length, self.misspelled_format)

class SectionEditorWidget(QWidget):
    """
    A widget containing fields to edit the details of a song section.
    Emits a signal whenever the data is changed by the user.
    """
    # Signal arguments: button_id (str), current_section_data (dict)
    data_changed = Signal(str, dict)

    def __init__(self, button_id, section_data, parent=None):
        super().__init__(parent)
        self.button_id = button_id
        # --- Spell Checker Setup ---
        self.spell = None
        if SpellChecker:
            self.spell = SpellChecker()
        # --- End Spell Checker Setup ---
        # Store a copy of the initial data to work with
        self._current_data = section_data.copy()

        # --- UI Elements ---
        self.name_input = QLineEdit()
        self.lyrics_input = QTextEdit()
        self.background_input = QLineEdit()
        self.browse_button = QPushButton("Browse...")

        # --- Apply Spell Check Highlighter ---
        if self.spell:
            self.highlighter = SpellCheckHighlighter(self.lyrics_input.document(), self.spell)
        # --- End Apply Spell Check Highlighter ---

        # --- Layout ---
        form_layout = QFormLayout()
        form_layout.addRow("Section Name:", self.name_input)
        form_layout.addRow("Lyrics:", self.lyrics_input)

        background_layout = QHBoxLayout()
        background_layout.addWidget(self.background_input)
        background_layout.addWidget(self.browse_button)
        form_layout.addRow("Background Image:", background_layout)

        main_layout = QVBoxLayout(self)
        main_layout.addLayout(form_layout)
        self.setLayout(main_layout)

        # --- Load Initial Data ---
        self.name_input.setText(self._current_data.get("name", ""))
        self.lyrics_input.setPlainText(self._current_data.get("lyrics", ""))
        self.background_input.setText(self._current_data.get("background_image", ""))

        # --- Connections ---
        self.name_input.textChanged.connect(self._emit_data_changed)
        self.lyrics_input.textChanged.connect(self._emit_data_changed)
        self.background_input.textChanged.connect(self._emit_data_changed)
        self.browse_button.clicked.connect(self._browse_for_background)
        # --- Connect Context Menu ---
        self.lyrics_input.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.lyrics_input.customContextMenuRequested.connect(self._show_lyrics_context_menu)
        # --- End Connect Context Menu ---

    def get_section_data(self):
        """Returns the current data from the input fields."""
        self._current_data["name"] = self.name_input.text()
        self._current_data["lyrics"] = self.lyrics_input.toPlainText()
        self._current_data["background_image"] = self.background_input.text() or None # Store None if empty
        # template_name is not edited here, but should be preserved in _current_data
        return self._current_data.copy() # Return a copy

    def _emit_data_changed(self):
        """Gathers current data and emits the data_changed signal."""
        current_data = self.get_section_data()
        self.data_changed.emit(self.button_id, current_data)

    def _browse_for_background(self):
        """Opens a file dialog to select a background image."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Background Image", "", "Image Files (*.png *.jpg *.jpeg *.bmp)")
        if file_path:
            self.background_input.setText(file_path)
            # _emit_data_changed will be called automatically due to textChanged connection

    # --- Spell Check Context Menu Methods ---
    def _show_lyrics_context_menu(self, position):
        """Shows a context menu with spelling suggestions if applicable."""
        if not self.spell:
            return # No spellchecker available

        cursor = self.lyrics_input.cursorForPosition(position)
        cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        selected_word = cursor.selectedText()

        # Basic cleaning: remove leading/trailing punctuation (might need refinement)
        cleaned_word = selected_word.strip('.,!?;:"()[]{}')

        if cleaned_word and cleaned_word.lower() not in self.spell:
            menu = QMenu(self)
            menu.addAction(f"'{selected_word}' is misspelled").setEnabled(False) # Show the word
            menu.addSeparator()

            suggestions = self.spell.candidates(cleaned_word)
            if suggestions:
                for suggestion in sorted(list(suggestions))[:10]: # Limit suggestions
                    action = QAction(suggestion, self)
                    # Use lambda to capture the current cursor and suggestion
                    action.triggered.connect(lambda checked=False, c=cursor, s=suggestion: self._correct_word(c, s))
                    menu.addAction(action)
            else:
                menu.addAction("No suggestions found").setEnabled(False)

            # Optional: Add "Add to Dictionary" functionality here if needed
            # menu.addSeparator()
            # add_action = QAction("Add to Dictionary", self)
            # add_action.triggered.connect(lambda: self.spell.word_frequency.add(cleaned_word.lower()))
            # menu.addAction(add_action)

            menu.exec(self.lyrics_input.mapToGlobal(position))

    def _correct_word(self, cursor, correction):
        """Replaces the selected word in the cursor with the correction."""
        cursor.beginEditBlock() # Group action for undo/redo
        cursor.removeSelectedText()
        cursor.insertText(correction)
        cursor.endEditBlock()
