import sys
import os
import copy # For deep copying template settings
# Import QVBoxLayout, which is needed for the fix
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QWidget, QComboBox, QFormLayout, QVBoxLayout, QSizePolicy
from PySide6.QtUiTools import QUiLoader
from PySide6.QtGui import QPixmap
from PySide6.QtCore import QSize, Qt, QTimer 
# QWidget will be derived from the .ui file's base class via loadUiType

# Attempt to import TemplateManager from the core directory
try:
    from ..core.template_manager import TemplateManager
    # from ..data_models.slide_data import SlideData # SlideData might not be directly needed for CompositionRenderer previews
    from ..rendering.composition_renderer import CompositionRenderer # Changed
    # from ..core.image_cache_manager import ImageCacheManager # Not used by CompositionRenderer directly
except ImportError:
    # Fallback for running the script directly for testing
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from core.template_manager import TemplateManager
    # from data_models.slide_data import SlideData
    from rendering.composition_renderer import CompositionRenderer # Changed
    # from core.image_cache_manager import ImageCacheManager

# --- Dynamically load the UI file ---
# Construct the path to the UI file relative to this script's location
# IMPORTANT: Make sure this path points to the corrected .ui file I provided earlier.
_UI_FILE_RELATIVE_PATH = "template_pair_window.ui"
_UI_FILE_ABSOLUTE_FALLBACK = r"c:\Users\Logan\Documents\Plucky\Plucky\windows\template_pair_window.ui"
LOREM_IPSUM_LONG = "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum."

PREVIEW_RENDER_WIDTH = 640  # Intermediate render width for 16:9 aspect
PREVIEW_RENDER_HEIGHT = 360 # Intermediate render height

ui_file_path = os.path.join(os.path.dirname(__file__), _UI_FILE_RELATIVE_PATH)

if not os.path.exists(ui_file_path):
    print(f"Warning: UI file not found at '{ui_file_path}'. Trying fallback")
    # Fallback to the absolute path if the relative one isn't found
    # This is useful if the script is run from a different working directory
    ui_file_path = _UI_FILE_ABSOLUTE_FALLBACK
    
if not os.path.exists(ui_file_path):
    print(f"Error: UI file not found at '{ui_file_path}' or fallback '{_UI_FILE_ABSOLUTE_FALLBACK}'.")
    sys.exit(1)

class AspectRatioLabel(QLabel):
    def __init__(self, parent=None, aspect_w=16, aspect_h=9):
        super().__init__(parent)
        self.setScaledContents(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._aspect_ratio = aspect_w / aspect_h

    def set_aspect_ratio(self, ratio_w, ratio_h):
        self._aspect_ratio = ratio_w / ratio_h
        self.updateGeometry() 

    def heightForWidth(self, width: int) -> int:
        return int(width / self._aspect_ratio)

    def sizeHint(self) -> QSize:
        # Use a common preview width or the globally defined one as a base
        # Ensure the hint respects the aspect ratio.
        # PREVIEW_RENDER_WIDTH is defined globally in this file.
        base_width = PREVIEW_RENDER_WIDTH 
        return QSize(base_width, self.heightForWidth(base_width))

    def hasHeightForWidth(self) -> bool:
        return True

    # Override resizeEvent if absolutely necessary, but setScaledContents(True)
    # and proper size policy + heightForWidth usually suffice.


class TemplatePairingWindow(QWidget): # Inherit directly from QWidget

    def __init__(self, template_manager: TemplateManager, parent=None):
        super().__init__(parent)
        
        # --- THE CORE FIX for a RESIZABLE UI ---
        # 1. Load the UI from the file. The loader returns the top-level widget from the .ui file.
        #    By passing `self` as the parent, this new widget becomes a child of our TemplatePairingWindow.
        loader = QUiLoader()
        loaded_ui_widget = loader.load(ui_file_path, self)

        # 2. Create a layout for THIS window (TemplatePairingWindow). A QWidget needs its own
        #    layout to manage its children and respond to resizing. This was the missing piece.
        layout = QVBoxLayout(self) 
        layout.setContentsMargins(0, 0, 0, 0) # Use the full window space.

        # 3. Add the widget we just loaded into this window's layout. Now, when TemplatePairingWindow
        #    is resized, its layout will automatically resize the UI content within it.
        layout.addWidget(loaded_ui_widget)
        # --- END FIX ---

        self.template_manager = template_manager
        # self.image_cache_manager = ImageCacheManager() # Not directly used by CompositionRenderer
        self.slide_renderer = CompositionRenderer() # Use new renderer
        
        # Find original labels and their layouts to replace them
        original_template1_preview_label = self.findChild(QLabel, "template1PreviewLabel")
        original_template2_preview_label = self.findChild(QLabel, "template2PreviewLabel")

        output1_layout = self.findChild(QVBoxLayout, "output1VerticalLayout")
        output2_layout = self.findChild(QVBoxLayout, "output2VerticalLayout")

        if original_template1_preview_label and output1_layout:
            self.template1PreviewLabel = AspectRatioLabel()
            self.template1PreviewLabel.setObjectName(original_template1_preview_label.objectName())
            self.template1PreviewLabel.setFrameShape(original_template1_preview_label.frameShape())
            self.template1PreviewLabel.setAlignment(original_template1_preview_label.alignment())
            self.template1PreviewLabel.setMinimumSize(original_template1_preview_label.minimumSize())

            idx = output1_layout.indexOf(original_template1_preview_label)
            output1_layout.takeAt(idx) 
            original_template1_preview_label.deleteLater()
            output1_layout.insertWidget(idx, self.template1PreviewLabel)
        else:
            print("Error: Could not replace template1PreviewLabel. Using fallback.")
            self.template1PreviewLabel = AspectRatioLabel() # Fallback

        if original_template2_preview_label and output2_layout:
            self.template2PreviewLabel = AspectRatioLabel()
            self.template2PreviewLabel.setObjectName(original_template2_preview_label.objectName())
            self.template2PreviewLabel.setFrameShape(original_template2_preview_label.frameShape())
            self.template2PreviewLabel.setAlignment(original_template2_preview_label.alignment())
            self.template2PreviewLabel.setMinimumSize(original_template2_preview_label.minimumSize())

            idx = output2_layout.indexOf(original_template2_preview_label)
            output2_layout.takeAt(idx)
            original_template2_preview_label.deleteLater()
            output2_layout.insertWidget(idx, self.template2PreviewLabel)
        else:
            print("Error: Could not replace template2PreviewLabel. Using fallback.")
            self.template2PreviewLabel = AspectRatioLabel() # Fallback

        # Access other UI elements
        self.template1ComboBox: QComboBox = self.findChild(QComboBox, "template1ComboBox")
        self.template2ComboBox: QComboBox = self.findChild(QComboBox, "template2ComboBox")

        # Find the container for dynamic text box UI elements for Output 1
        self.output1TextBoxesContainer: QWidget = self.findChild(QWidget, "output1TextBoxesContainer")
        
        # Create a QFormLayout and set it on the container for Output 1
        self.output1TextBoxesLayout = QFormLayout(self.output1TextBoxesContainer)
        self.output1TextBoxesLayout.setContentsMargins(0, 0, 0, 0)
        self.output1TextBoxesLayout.setSpacing(5) 
        self.output1_text_edits = {} # To store QLineEdit instances for Output 1

        if self.output1TextBoxesContainer: self.output1TextBoxesContainer.setVisible(False) 

        # Find the container for dynamic mapping UI elements for Output 2
        self.output2MappingContainer: QWidget = self.findChild(QWidget, "output2MappingContainer")
        # Create a QFormLayout and set it on the container for Output 2
        self.output2MappingLayout = QFormLayout(self.output2MappingContainer)
        self.output2MappingLayout.setContentsMargins(0, 0, 0, 0)
        self.output2MappingLayout.setSpacing(5)
        self.output2_mapping_combos = {} # To store references to mapping QComboBoxes

        if self.output2MappingContainer: self.output2MappingContainer.setVisible(False)

        # Check if main UI elements were found before proceeding
        # Note: self.template1PreviewLabel and self.template2PreviewLabel are now guaranteed to be AspectRatioLabel instances
        if not all([self.template1ComboBox, self.template2ComboBox, 
                     self.output1TextBoxesContainer, self.output2MappingContainer]):
            print("Error: One or more main UI elements (ComboBoxes, PreviewLabels, Containers) not found. Check .ui file object names.")
            return
        else:
            self._populate_template_comboboxes()

            self.template1ComboBox.currentTextChanged.connect(self._on_template1_selection_changed)
            self.template2ComboBox.currentTextChanged.connect(self._on_template2_selection_changed)

            # Schedule initial preview updates after layout has a chance to settle
            QTimer.singleShot(0, lambda: self._on_template1_selection_changed(self.template1ComboBox.currentText()))
            QTimer.singleShot(0, lambda: self._on_template2_selection_changed(self.template2ComboBox.currentText()))

    def _populate_template_comboboxes(self):
        """Populates the template selection comboboxes."""
        if not self.template_manager:
            print("Error: TemplateManager not available to populate comboboxes.")
            return

        layout_names = self.template_manager.get_layout_names()
        
        self.template1ComboBox.blockSignals(True)
        self.template2ComboBox.blockSignals(True)

        self.template1ComboBox.clear() 
        if not layout_names:
            self.template1ComboBox.addItem("No Layouts Found")
            self.template1ComboBox.setEnabled(False)
        else:
            sorted_layouts = sorted(layout_names)
            self.template1ComboBox.addItems(sorted_layouts)
            self.template1ComboBox.setEnabled(True)
            if sorted_layouts: 
                self.template1ComboBox.setCurrentIndex(0)

        self.template2ComboBox.clear() 
        if not layout_names:
            self.template2ComboBox.addItem("No Layouts Found") 
            self.template2ComboBox.setEnabled(False)
        else:
            sorted_layouts_for_t2 = sorted(layout_names)
            self.template2ComboBox.addItem("(None)", userData=None)
            for layout_name in sorted_layouts_for_t2:  
                self.template2ComboBox.addItem(layout_name, userData=layout_name) 
            self.template2ComboBox.setEnabled(True)
            self.template2ComboBox.setCurrentIndex(0) 

        self.template1ComboBox.blockSignals(False)
        self.template2ComboBox.blockSignals(False)

    def _on_template1_selection_changed(self, template_name: str):
        self._update_preview(template_name, self.template1PreviewLabel)
        self._update_output1_text_fields(template_name)
        
        if self.template2ComboBox.currentData() is not None:
            self._update_output2_text_mappings(self.template2ComboBox.currentText())
            self._update_preview(self.template2ComboBox.currentText(), self.template2PreviewLabel)
        elif self.template2ComboBox.currentData() is None: 
            self._update_preview(template_name, self.template2PreviewLabel)

    def _on_template2_selection_changed(self, template_name_from_combo: str):
        selected_data = self.template2ComboBox.currentData()
        if selected_data is None: 
            self.output2MappingContainer.setVisible(False)
            while self.output2MappingLayout.count():
                item = self.output2MappingLayout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            self.output2_mapping_combos.clear()
            template1_name = self.template1ComboBox.currentText()
            self._update_preview(template1_name, self.template2PreviewLabel)
        else: 
            self._update_output2_text_mappings(selected_data)
            self._update_preview(selected_data, self.template2PreviewLabel)

    def _update_preview(self, template_name: str, preview_label: QLabel):
        if not template_name or "No Layouts Found" in template_name :
            preview_label.clear()
            preview_label.setText("No Template Selected")
            return

        template_definition_for_preview = self.template_manager.resolve_layout_template(template_name)
        if not template_definition_for_preview:
            preview_label.clear()
            preview_label.setText(f"Template '{template_name}' not found.")
            return

        # --- Construct scene_data for CompositionRenderer ---
        scene_data = {
            "width": PREVIEW_RENDER_WIDTH,
            "height": PREVIEW_RENDER_HEIGHT,
            "layers": []
        }

        # 1. Background Layer (from template)
        bg_color_hex = template_definition_for_preview.get("background_color")
        bg_image_path = template_definition_for_preview.get("background_image_path") 

        if bg_image_path and os.path.exists(bg_image_path):
            scene_data["layers"].append({
                "id": "template_bg_image",
                "type": "image",
                "position": {"x_pc": 0, "y_pc": 0, "width_pc": 100, "height_pc": 100},
                "properties": {"path": bg_image_path, "scaling_mode": "fill"}
            })
        elif bg_color_hex and bg_color_hex != "#00000000": # Only add if not fully transparent
            scene_data["layers"].append({
                "id": "template_bg_color",
                "type": "solid_color",
                "position": {"x_pc": 0, "y_pc": 0, "width_pc": 100, "height_pc": 100},
                "properties": {"color": bg_color_hex}
            })

        # 2. Text Layers
        defined_text_boxes = template_definition_for_preview.get("text_boxes", [])
        text_content_map = {}

        # Determine text content based on which preview label is being updated
        if preview_label is self.template1PreviewLabel:
            for tb_def in defined_text_boxes:
                tb_id = tb_def.get("id")
                if tb_id:
                    line_edit_widget = self.output1_text_edits.get(tb_id)
                    text_content_map[tb_id] = line_edit_widget.text() if line_edit_widget else LOREM_IPSUM_LONG
        elif preview_label is self.template2PreviewLabel:
            if self.template2ComboBox.currentData() is None:
                # defined_text_boxes are from Output 1's template (passed as template_name)
                for tb_def in defined_text_boxes:
                    tb_id = tb_def.get("id")
                    if tb_id:
                        line_edit_widget = self.output1_text_edits.get(tb_id)
                        text_content_map[tb_id] = line_edit_widget.text() if line_edit_widget else LOREM_IPSUM_LONG
            else: # Output 2 showing its own selected template
                # defined_text_boxes are from Output 2's template
                for tb_def_out2 in defined_text_boxes:
                    out2_tb_id = tb_def_out2.get("id")
                    if out2_tb_id:
                        mapping_combo = self.output2_mapping_combos.get(out2_tb_id)
                        mapped_out1_tb_id = mapping_combo.currentData() if mapping_combo else None
                        if mapped_out1_tb_id:
                            line_edit_widget_out1 = self.output1_text_edits.get(mapped_out1_tb_id)
                            text_content_map[out2_tb_id] = line_edit_widget_out1.text() if line_edit_widget_out1 else LOREM_IPSUM_LONG
                        else: # Not mapped or no source
                            text_content_map[out2_tb_id] = LOREM_IPSUM_LONG # Fallback to Lorem Ipsum

        for tb_def in defined_text_boxes:
            tb_id = tb_def.get("id")
            text_to_draw = text_content_map.get(tb_id, LOREM_IPSUM_LONG)

            style_name = tb_def.get("style_name")
            style_props = self.template_manager.get_style_definition(style_name) if style_name else {}
            style_props = style_props or {} # Ensure style_props is a dict

            text_layer_properties = {
                "content": text_to_draw,
                "font_family": tb_def.get("font_family", style_props.get("font_family", "Arial")),
                "font_size": tb_def.get("font_size", style_props.get("font_size", 32)),
                "font_color": tb_def.get("font_color", style_props.get("font_color", "#FFFFFFFF")),
                "h_align": tb_def.get("h_align", style_props.get("h_align", "center")),
                "v_align": tb_def.get("v_align", style_props.get("v_align", "center")),
                "force_all_caps": tb_def.get("force_all_caps", style_props.get("force_all_caps", False)),
                "shadow": {
                    "enabled": tb_def.get("shadow_enabled", style_props.get("text_shadow", False)),
                    "color": tb_def.get("shadow_color", style_props.get("shadow_color", "#00000080")),
                    "offset_x": tb_def.get("shadow_offset_x", style_props.get("shadow_x", 2)),
                    "offset_y": tb_def.get("shadow_offset_y", style_props.get("shadow_y", 2))
                },
                "outline": {
                    "enabled": tb_def.get("outline_enabled", style_props.get("text_outline", False)),
                    "color": tb_def.get("outline_color", style_props.get("outline_color", "#000000FF")),
                    "width": tb_def.get("outline_width", style_props.get("outline_thickness", 1))
                }
            }
            scene_data["layers"].append({
                "id": f"text_{tb_id}", "type": "text",
                "position": {"x_pc": tb_def.get("x_pc",0), "y_pc": tb_def.get("y_pc",0), "width_pc": tb_def.get("width_pc",100), "height_pc": tb_def.get("height_pc",100)},
                "properties": text_layer_properties
            })

        rendered_pixmap = self.slide_renderer.render_scene(scene_data)

        if rendered_pixmap and not rendered_pixmap.isNull():
            preview_label.setPixmap(rendered_pixmap)
        else:
            preview_label.clear()
            preview_label.setText("Render Failed")
            
    def _update_output1_text_fields(self, template_name: str):
        if not self.output1TextBoxesContainer or not self.output1TextBoxesLayout:
            return

        while self.output1TextBoxesLayout.count():
            item = self.output1TextBoxesLayout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.output1_text_edits.clear()

        if not template_name or "No Layouts Found" in template_name:
            self.output1TextBoxesContainer.setVisible(False)
            return

        template_definition = self.template_manager.resolve_layout_template(template_name)
        if not template_definition or "text_boxes" not in template_definition:
            self.output1TextBoxesContainer.setVisible(False)
            return

        defined_text_boxes = template_definition.get("text_boxes", [])
        
        if not defined_text_boxes:
            self.output1TextBoxesContainer.setVisible(False)
            return

        for i, tb_def in enumerate(defined_text_boxes):
            tb_id = tb_def.get("id", f"field_{i+1}")
            tb_display_label = tb_def.get("label", tb_id) 

            label_widget = QLabel(f"{tb_display_label}:")
            edit_widget = QLineEdit(LOREM_IPSUM_LONG) 
            edit_widget.setReadOnly(False)
            self.output1_text_edits[tb_id] = edit_widget
            edit_widget.textChanged.connect(self._on_output1_text_edit_changed)

            self.output1TextBoxesLayout.addRow(label_widget, edit_widget)

        self.output1TextBoxesContainer.setVisible(True)
        
    def _on_output1_text_edit_changed(self):
        self._update_preview(self.template1ComboBox.currentText(), self.template1PreviewLabel)
        
        if self.template2ComboBox.currentData() is None:
            self._update_preview(self.template1ComboBox.currentText(), self.template2PreviewLabel)
        else:
            self._update_preview(self.template2ComboBox.currentText(), self.template2PreviewLabel)

    def _update_output2_text_mappings(self, output2_template_name: str):
        if not self.output2MappingContainer or not self.output2MappingLayout:
            return

        while self.output2MappingLayout.count():
            item = self.output2MappingLayout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.output2_mapping_combos.clear()

        if not output2_template_name or "No Layouts Found" in output2_template_name:
            self.output2MappingContainer.setVisible(False)
            return

        output2_template_def = self.template_manager.resolve_layout_template(output2_template_name)
        if not output2_template_def or "text_boxes" not in output2_template_def:
            self.output2MappingContainer.setVisible(False)
            return

        output2_text_boxes = output2_template_def.get("text_boxes", [])
        if not output2_text_boxes:
            self.output2MappingContainer.setVisible(False)
            return

        output1_template_name = self.template1ComboBox.currentText()
        output1_text_boxes_data = []
        if output1_template_name and "No Layouts Found" not in output1_template_name:
            output1_template_def = self.template_manager.resolve_layout_template(output1_template_name)
            if output1_template_def and "text_boxes" in output1_template_def:
                output1_text_boxes_data = output1_template_def.get("text_boxes", [])
        
        for tb_def_out2 in output2_text_boxes:
            out2_tb_id = tb_def_out2.get("id")
            out2_tb_display_label = tb_def_out2.get("label", out2_tb_id)
            label_widget = QLabel(f"Map '{out2_tb_display_label}' (O2) to:")
            mapping_combo = QComboBox()
            mapping_combo.addItem("(Do Not Map)", userData=None)
            for tb_def_out1 in output1_text_boxes_data:
                out1_tb_id = tb_def_out1.get("id")
                out1_tb_display_label = tb_def_out1.get("label", out1_tb_id)
                mapping_combo.addItem(f"'{out1_tb_display_label}' (O1)", userData=out1_tb_id)
            
            if out2_tb_id:
                self.output2_mapping_combos[out2_tb_id] = mapping_combo
            mapping_combo.currentIndexChanged.connect(self._on_output2_mapping_combo_changed)

            self.output2MappingLayout.addRow(label_widget, mapping_combo)

        self.output2MappingContainer.setVisible(True)

    def _on_output2_mapping_combo_changed(self):
        if self.template2ComboBox.currentData() is not None:
            self._update_preview(self.template2ComboBox.currentText(), self.template2PreviewLabel)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # This is a placeholder for your actual TemplateManager instance
    mock_template_manager = TemplateManager()
    window = TemplatePairingWindow(template_manager=mock_template_manager)
    window.show()
    sys.exit(app.exec())
