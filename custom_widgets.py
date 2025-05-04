# c:\Users\Logan\Documents\Plucky\custom_widgets.py

from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QPushButton, QApplication, QSizePolicy
)
from PySide6.QtGui import (
    QPainter, QColor, QFont, QFontMetrics, QPen, QDrag, QMouseEvent, QPixmap, QBrush
)
from PySide6.QtCore import Qt, QMimeData, QRect, Signal

# --- Lyric Preview Widget ---
class LyricPreviewWidget(QWidget):
    """ A widget to display a small preview of the lyric text. """
    def __init__(self, lyric_text, template_settings, parent=None):
        super().__init__(parent)
        self.lyric_text = lyric_text
        # Make a copy to avoid modifying the original dict if needed later
        self.template_settings = template_settings.copy() if template_settings else {}
        self.setMinimumSize(100, 50) # Ensure it has some minimum size
        # Let's allow it to expand, especially vertically if needed
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setStyleSheet("background-color: #222; border: 1px solid #444;") # Dark background

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Basic styling from template (simplified)
        font_settings = self.template_settings.get("font", {})
        color_setting = self.template_settings.get("color", "#FFFFFF")
        alignment_setting = self.template_settings.get("alignment", "center")

        vertical_alignment_setting = self.template_settings.get("vertical_alignment", "bottom") # Get vertical align
        max_width_setting = self.template_settings.get("max_width", "100%") # Get max width
        outline_settings = self.template_settings.get("outline", {"enabled": False})
        shadow_settings = self.template_settings.get("shadow", {"enabled": False})
        force_caps = self.template_settings.get("force_caps", False) # Get force_caps setting

        widget_width = self.width()
        widget_height = self.height()
        margin = 3 # Small margin inside the preview box

        # --- Set Full Font Properties ---
        font = QFont()
        font.setFamily(font_settings.get("family", "Arial"))
        original_font_size = font_settings.get("size", 48)
        preview_font_size = max(6, original_font_size // 5) # Adjust divisor (e.g., 5) as needed
        font.setPointSize(max(8, preview_font_size)) # Ensure minimum size
        font.setBold(font_settings.get("bold", False))
        font.setItalic(font_settings.get("italic", False))
        font.setUnderline(font_settings.get("underline", False))
        painter.setFont(font)

        font_metrics = QFontMetrics(font)

        # --- Calculate Scaled Max Width for Wrapping ---
        preview_max_width = widget_width - (2 * margin) # Max width is inner width of preview
        if isinstance(max_width_setting, str) and max_width_setting.endswith('%'):
            try:
                percentage = float(max_width_setting[:-1]) / 100.0
                preview_max_width = int((widget_width - 2 * margin) * percentage)
            except ValueError:
                pass # Use default preview_max_width

        # --- Apply Force Caps ---
        text_to_draw = self.lyric_text.upper() if force_caps else self.lyric_text
        # --- End Apply Force Caps ---

        # --- Calculate Text Bounding Rect based on Wrapping ---
        text_rect_size = font_metrics.boundingRect(0, 0, preview_max_width, widget_height * 5, Qt.TextFlag.TextWordWrap, text_to_draw) # Use text_to_draw

        # --- Calculate Drawing Position based on Alignment ---
        draw_rect_x = margin
        draw_rect_y = margin
        available_width = widget_width - 2 * margin
        available_height = widget_height - 2 * margin

        if alignment_setting == "center":
            draw_rect_x = margin + (available_width - text_rect_size.width()) // 2
        elif alignment_setting == "right":
            draw_rect_x = widget_width - margin - text_rect_size.width()

        if vertical_alignment_setting == "center":
            draw_rect_y = margin + (available_height - text_rect_size.height()) // 2
        elif vertical_alignment_setting == "top":
            draw_rect_y = margin
        elif vertical_alignment_setting == "bottom":
            draw_rect_y = widget_height - margin - text_rect_size.height()

        drawing_rect = QRect(draw_rect_x, draw_rect_y, text_rect_size.width(), text_rect_size.height())

        # --- Set Text Color ---
        color = QColor(color_setting)

        text_alignment_flags = Qt.TextFlag.TextWordWrap
        if alignment_setting == "center":
            text_alignment_flags |= Qt.AlignmentFlag.AlignHCenter
        elif alignment_setting == "right":
            text_alignment_flags |= Qt.AlignmentFlag.AlignRight
        else: # Default left
            text_alignment_flags |= Qt.AlignmentFlag.AlignLeft

        # --- Draw Shadow (Simplified) ---
        if shadow_settings.get("enabled", False):
            shadow_color = QColor(shadow_settings.get("color", "#000000"))
            shadow_offset_x = max(1, shadow_settings.get("offset_x", 3) // 2)
            shadow_offset_y = max(1, shadow_settings.get("offset_y", 3) // 2)
            painter.setPen(shadow_color)
            shadow_rect = QRect(drawing_rect).translated(shadow_offset_x, shadow_offset_y)
            painter.drawText(shadow_rect, text_alignment_flags, text_to_draw) # Use text_to_draw

        # --- Draw Outline (Simplified) ---
        if outline_settings.get("enabled", False):
            outline_color = QColor(outline_settings.get("color", "#000000"))
            outline_width = max(1, outline_settings.get("width", 2) // 2)
            original_pen = painter.pen()
            outline_pen = QPen(outline_color, outline_width * 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(outline_pen)
            painter.drawText(drawing_rect, text_alignment_flags, text_to_draw) # Use text_to_draw
            painter.setPen(original_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)

        # --- Draw Main Text ---
        painter.setPen(color)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawText(drawing_rect, text_alignment_flags, text_to_draw) # Use text_to_draw


# --- Draggable Button Class ---
class DraggableButton(QWidget):
    """ A QWidget containing a title and lyric preview, which can be dragged. """
    clicked = Signal(object) # Define signal to accept one 'object' argument

    _default_title_style = "background-color: #555; color: white; padding: 3px; border-radius: 3px;"
    _highlighted_title_style = "background-color: #0078D7; color: white; padding: 3px; border-radius: 3px; border: 1px solid #FFF;"

    def __init__(self, button_id, text, lyric, template_settings, parent=None):
        super().__init__(parent)
        self.button_id = button_id
        self.lyric_text = lyric
        self.drag_start_position = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(1)

        self.title_label = QLabel(text)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet(self._default_title_style)

        self.preview_widget = LyricPreviewWidget(lyric, template_settings, self)

        layout.addWidget(self.title_label)
        layout.addWidget(self.preview_widget, stretch=1)

        self.setLayout(layout)
        self.setMinimumWidth(120)
        self.setMinimumHeight(80)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_position = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if not (event.buttons() & Qt.MouseButton.LeftButton) or self.drag_start_position is None:
            return
        if (event.position().toPoint() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance():
            return

        drag = QDrag(self)
        mime_data = QMimeData()
        if not self.objectName():
            print("Warning: DraggableButton has no objectName set. Drag might fail.")
            return
        mime_data.setText(self.objectName())
        drag.setMimeData(mime_data)

        pixmap = QPixmap(self.size())
        self.render(pixmap)
        drag.setPixmap(pixmap)
        drag.setHotSpot(event.position().toPoint() - self.rect().topLeft())

        print(f"Starting drag for button: {self.objectName()}")
        drop_action = drag.exec(Qt.DropAction.MoveAction | Qt.DropAction.CopyAction, Qt.DropAction.MoveAction)

        if drop_action == Qt.DropAction.MoveAction:
            print(f"Button {self.objectName()} move action completed.")
        else:
            print(f"Drag for {self.objectName()} cancelled or resulted in non-move action.")
        self.drag_start_position = None

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self.drag_start_position is not None:
            if (event.position().toPoint() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance():
                self.clicked.emit(self)
        super().mouseReleaseEvent(event)

    def set_highlight(self, highlight_on: bool):
        style = self._highlighted_title_style if highlight_on else self._default_title_style
        self.title_label.setStyleSheet(style)