from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont # type: ignore
from PySide6.QtCore import QRegularExpression # type: ignore
from spellchecker import SpellChecker # pip install pyspellchecker

class SpellCheckHighlighter(QSyntaxHighlighter):
    def __init__(self, parent_document, spell_checker_instance: SpellChecker):
        """
        Args:
            parent_document: The QTextDocument of the QTextEdit to highlight.
            spell_checker_instance: An instance of spellchecker.SpellChecker
        """
        super().__init__(parent_document)
        self.spell_checker = spell_checker_instance

        self.misspelled_format = QTextCharFormat()
        self.misspelled_format.setUnderlineColor(QColor("red"))
        # Use SpellCheckUnderline for a dotted underline, or WavyUnderline for wavy.
        self.misspelled_format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SpellCheckUnderline)

        # Regex to find words. \b matches word boundaries.
        # \w+ matches one or more word characters (letters, numbers, underscore).
        # We'll refine this to better handle apostrophes if needed, but this is a good start.
        self.word_pattern = QRegularExpression(r"\b[a-zA-Z']+\b") # Matches words with optional apostrophes

    def highlightBlock(self, text: str):
        """This method is called by Qt whenever a block of text needs re-highlighting."""
        iterator = self.word_pattern.globalMatch(text)
        while iterator.hasNext():
            match = iterator.next()
            word = match.captured(0)

            if self.spell_checker.unknown([word]): # spell.unknown returns a set of misspelled words
                start_index = match.capturedStart(0)
                length = match.capturedLength(0)
                self.setFormat(start_index, length, self.misspelled_format)