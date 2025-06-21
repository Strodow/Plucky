import sys
import logging
from PySide6.QtWidgets import (
    QWidget, QApplication, QSizePolicy
)
from PySide6.QtGui import QPainter, QColor, QPixmap, QFont
from PySide6.QtCore import Qt, Slot


class OutputWindow(QWidget):
    """
    A simple window designed to display a pre-rendered QPixmap,
    typically on a secondary monitor fullscreen.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Plucky Output")
        # Set flags for a borderless window, typical for fullscreen output
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        # Set attribute for potential transparency effects if needed later
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Store the pixmap to be displayed
        self._pixmap_to_display = QPixmap(self.size())
        self._pixmap_to_display.fill(Qt.GlobalColor.transparent) # Start transparent
        # Ensure the window doesn't try to resize based on content
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    @Slot(QPixmap)
    def set_pixmap(self, pixmap: QPixmap):
        """Sets the pixmap to be displayed and triggers a repaint."""
        if pixmap.isNull(): # If a null pixmap is received (e.g., from clear_program)
            logging.warning("OutputWindow received a null pixmap. Displaying transparent.")
            # Create a transparent pixmap of the window's current size
            self._pixmap_to_display = QPixmap(self.size())
            self._pixmap_to_display.fill(Qt.GlobalColor.transparent) # Ensure it's transparent
        else:
            # Store the received pixmap
            self._pixmap_to_display = pixmap
        logging.debug(f"OutputWindow.set_pixmap called. Pixmap size: {self._pixmap_to_display.size()}, isNull: {self._pixmap_to_display.isNull()}")
        self.update() # Request a repaint

    def paintEvent(self, event):
        """Handles the painting of the window content."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        if not self._pixmap_to_display.isNull():
            # Draw the provided pixmap, scaled to fit the window
            painter.drawPixmap(self.rect(), self._pixmap_to_display)
        # No 'else' needed here. If _pixmap_to_display is null, it means it's transparent,
        # and WA_TranslucentBackground will handle the rest.


        painter.end() # End painting session

if __name__ == '__main__':
    # --- Basic Test ---
    app = QApplication(sys.argv)
    window = OutputWindow()
    # Create a simple test pixmap
    test_pixmap = QPixmap(800, 600)
    test_pixmap.fill(QColor("cornflowerblue"))
    p = QPainter(test_pixmap)
    p.setPen(Qt.GlobalColor.white)
    p.setFont(QFont("Arial", 40))
    p.drawText(test_pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "Output Window Test")
    p.end()

    window.set_pixmap(test_pixmap)
    window.resize(800, 600) # Set initial size for testing
    window.show()
    sys.exit(app.exec())