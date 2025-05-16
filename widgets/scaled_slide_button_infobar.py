import sys
import os
from PySide6.QtWidgets import QWidget, QSizePolicy
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QFontMetrics
from PySide6.QtCore import Qt, QRectF
from typing import Optional

class InfoBannerWidget(QWidget):
    def __init__(self, banner_height=25, parent=None):
        super().__init__(parent)
        self._banner_height = banner_height
        self.setFixedHeight(self._banner_height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._slide_number: Optional[int] = None
        self._slide_label: Optional[str] = ""
        self._section_label: Optional[str] = "" # For "Verse 1", "Chorus", etc.
        self._custom_banner_color: Optional[QColor] = None
        self._icon_states = {"error": False, "warning": False}
        self._icon_pixmaps = {} 
        self._icon_size = max(5, self._banner_height - 10) 
        self._icon_spacing = 5
        
        # --- Dynamically locate the resources directory ---
        # Get the directory of the current script (scaled_slide_button_infobar.py)
        current_script_dir = os.path.dirname(os.path.abspath(__file__))
        # Navigate up to the project root (e.g., Plucky/)
        # Assuming widgets/ is directly under Plucky/, so project_root is one level up.
        project_root = os.path.dirname(current_script_dir) 
        
        resources_dir = os.path.join(project_root, "resources")
        error_icon_path = os.path.join(resources_dir, "error_icon.png")
        error_pixmap_icon = QPixmap(error_icon_path)
        if not error_pixmap_icon.isNull():
            self._icon_pixmaps["error"] = error_pixmap_icon.scaled(self._icon_size, self._icon_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        else:
            print(f"WARNING: InfoBannerWidget could not load error icon from: {error_icon_path}")
        
        # Placeholder for warning icon
        warning_pixmap_icon = QPixmap(self._icon_size, self._icon_size)
        warning_pixmap_icon.fill(QColor("orange"))
        self._icon_pixmaps["warning"] = warning_pixmap_icon

    def set_info(self, number: Optional[int], label: Optional[str]):
        self._slide_number = number
        self._slide_label = label if label is not None else ""
        self.update()
        
    def set_section_label(self, label: Optional[str]):
        self._section_label = label if label is not None else ""
        self.update()

    def set_icon_state(self, icon_name: str, visible: bool):
        if icon_name in self._icon_states and self._icon_states[icon_name] != visible:
            self._icon_states[icon_name] = visible
            self.update()

    def set_custom_color(self, color: Optional[QColor]):
        if self._custom_banner_color != color:
            self._custom_banner_color = color
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        banner_rect = self.rect()

        if not banner_rect.isValid() or banner_rect.height() <= 0:
            painter.end()
            return

        current_banner_color = self._custom_banner_color if self._custom_banner_color is not None else QColor("#202020")
        painter.fillRect(banner_rect, current_banner_color)

        painter.setPen(QColor(Qt.GlobalColor.white))
        banner_content_font = QFont(self.font())
        banner_content_font.setPointSize(max(8, int(banner_content_font.pointSize() * 0.85)))
        painter.setFont(banner_content_font)
        font_metrics_banner = QFontMetrics(painter.font())
        text_padding_horizontal = 5
        
        total_icon_area_width_banner = 0
        visible_icons_banner = []
        icon_order = ["error", "warning"] 
        for icon_name in icon_order:
            if self._icon_states.get(icon_name, False) and icon_name in self._icon_pixmaps:
                visible_icons_banner.append(icon_name)
                total_icon_area_width_banner += self._icon_size + self._icon_spacing
        if total_icon_area_width_banner > 0 and visible_icons_banner:
            total_icon_area_width_banner -= self._icon_spacing 

        num_str = str(self._slide_number if self._slide_number is not None else "?") 
        num_str_width = font_metrics_banner.horizontalAdvance(num_str)
        number_draw_rect = QRectF(banner_rect.left() + text_padding_horizontal, banner_rect.top(), num_str_width, banner_rect.height())
        painter.drawText(number_draw_rect, Qt.AlignLeft | Qt.AlignVCenter, num_str)

        current_icon_x = banner_rect.right() - text_padding_horizontal
        for icon_name in visible_icons_banner: 
            current_icon_x -= self._icon_size
            icon_pixmap = self._icon_pixmaps[icon_name]
            icon_y = banner_rect.top() + (banner_rect.height() - icon_pixmap.height()) / 2
            painter.drawPixmap(int(current_icon_x), int(icon_y), icon_pixmap)
            current_icon_x -= self._icon_spacing

        # Display section_label if available, otherwise slide_label (which is currently empty)
        label_to_display = self._section_label if self._section_label else self._slide_label
        
        if label_to_display:            
            label_area_left = number_draw_rect.right() + text_padding_horizontal
            label_area_right = (banner_rect.right() - text_padding_horizontal - total_icon_area_width_banner) - text_padding_horizontal
            if not visible_icons_banner: 
                label_area_right = banner_rect.right() - text_padding_horizontal
            slide_label_rect = QRectF(label_area_left, banner_rect.top(), max(0, label_area_right - label_area_left), banner_rect.height())
            
            elided_label_for_debug = "N/A"
            if slide_label_rect.width() > 0:
                elided_label = font_metrics_banner.elidedText(label_to_display, Qt.TextElideMode.ElideRight, slide_label_rect.width())
                # Original drawing call for the label
                painter.drawText(slide_label_rect, Qt.AlignCenter | Qt.AlignVCenter, elided_label)
                elided_label_for_debug = elided_label
        
        painter.end()