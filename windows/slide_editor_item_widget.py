import sys
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTextEdit, QPushButton, QApplication, QFrame, QComboBox
)
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import Qt, QFileInfo, QDir, Slot, QTimer, QRectF, QSize # Added QSize
from PySide6.QtGui import QPixmap, QPainter, QShowEvent # For displaying rendered pixmaps, drawing, and showEvent

# Adjust path to import TemplateManager if necessary
try:
    from core.template_manager import TemplateManager
    from data_models.slide_data import SlideData
    from rendering.slide_renderer import LayeredSlideRenderer
except ImportError:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from core.template_manager import TemplateManager
    from data_models.slide_data import SlideData
    from rendering.slide_renderer import LayeredSlideRenderer

# Define a standard resolution for rendering previews
PREVIEW_RENDER_WIDTH = 1920
PREVIEW_RENDER_HEIGHT = 1080

# Define the fixed display size for the preview label in the UI
TARGET_PREVIEW_DISPLAY_WIDTH = 320
TARGET_PREVIEW_DISPLAY_HEIGHT = 180

class SlideEditorItemWidget(QWidget):
    def __init__(self, slide_data: SlideData, template_manager: TemplateManager, slide_renderer: LayeredSlideRenderer, parent: QWidget = None):
        super().__init__(parent)
        self.slide_data = slide_data
        self.template_manager = template_manager
        self.slide_renderer = slide_renderer

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
        # self.slide_preview_frame: QFrame = self.findChild(QFrame, "slide_preview_frame") # Removed
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
            self.slide_name_banner_label.setText(f"Editing: {self.slide_data.id} ({self.slide_data.overlay_label or 'No Label'})")

        # Populate and set the template combo box
        self._populate_and_set_template_combobox()

        if self.templates_combo_box_per_slide:
            self.templates_combo_box_per_slide.currentTextChanged.connect(self.on_template_selected)
            # Initialize text box visibility based on the default template
            # This is now called at the end of _populate_and_set_template_combobox

        # Connect signals for dynamic text edit resizing and perform initial adjustment
        text_edits = [self.text_box_one_edit, self.text_box_two_edit, self.text_box_three_edit]
        for text_edit in text_edits:
            if text_edit:
                text_edit.textChanged.connect(self._adjust_text_edit_height_on_signal)
                text_edit.textChanged.connect(self._handle_text_edit_changed) # For content update & preview
                self._adjust_specific_text_edit_height(text_edit) # Initial adjustment
        
        self.update_slide_preview() # Initial render

    def showEvent(self, event: QShowEvent):
        """Override showEvent to trigger initial resize after layout is settled."""
        super().showEvent(event)
        # Use QTimer.singleShot to ensure this runs after the current event processing
        # and initial layout adjustments are complete.
        QTimer.singleShot(0, self._perform_initial_resize_of_text_edits)

    def _perform_initial_resize_of_text_edits(self):
        """Forces a resize calculation for all visible text edits."""
        text_edits_to_adjust = [self.text_box_one_edit, self.text_box_two_edit, self.text_box_three_edit]
        for text_edit in text_edits_to_adjust:
            if text_edit and text_edit.isVisible():
                self._adjust_specific_text_edit_height(text_edit)

    def _populate_and_set_template_combobox(self):
        if not self.templates_combo_box_per_slide or not self.template_manager:
            print(f"SlideEditorItemWidget ({self.slide_data.id}): ComboBox or TemplateManager not found.")
            return
        self.templates_combo_box_per_slide.clear()  # Clear default items from .ui file
        
        try:
            available_template_names = self.template_manager.get_layout_names()
            if not available_template_names: # Ensure there's at least the default if TM is empty
                 available_template_names = [self.template_manager.get_system_default_fallback_layout_name()]

        except Exception as e:
            print(f"Error getting template names from TemplateManager: {e}")
            available_template_names = ["Error Loading Templates"] # Fallback

        self.templates_combo_box_per_slide.addItems(available_template_names)

        # Try to set the current template based on self.template_id
        current_layout_name = self.slide_data.template_settings.get('layout_name')
        if current_layout_name and current_layout_name in available_template_names:
            self.templates_combo_box_per_slide.setCurrentText(current_layout_name)
            # print(f"SlideEditorItemWidget ({self.slide_data.id}): Set template to '{current_layout_name}'.")
        elif available_template_names:
            # print(f"SlideEditorItemWidget ({self.slide_data.id}): Template ID '{current_layout_name}' not found. Defaulting to '{available_template_names[0]}'.")
            self.templates_combo_box_per_slide.setCurrentIndex(0) # Default to first if specific not found
        else:
            print(f"SlideEditorItemWidget ({self.slide_data.id}): No templates available, and '{current_layout_name}' not found.")

        # After populating and setting, call on_template_selected to set initial visibility
        self.on_template_selected(self.templates_combo_box_per_slide.currentText(), initial_load=True)

        # TODO: Connect self.templates_combo_box.currentTextChanged to a method
        # that handles template changes for this slide (e.g., updates text box visibility/labels)

    def on_template_selected(self, template_name: str, initial_load: bool = False):
        """Handles changes in the per-slide template selection."""
        # print(f"Slide '{self.slide_data.id}': Template selected '{template_name}', initial_load={initial_load}")

        # More robust: Get template definition from TemplateManager
        new_template_settings = self.template_manager.resolve_layout_template(template_name)
        if not new_template_settings:
            print(f"Error: Could not resolve template '{template_name}' for slide {self.slide_data.id}")
            return

        # Remap content from old text_content to new text_content structure
        old_text_content = self.slide_data.template_settings.get("text_content", {})
        new_text_content = {}
        
        new_tb_defs = new_template_settings.get("text_boxes", [])
        old_tb_ids_ordered = list(old_text_content.keys()) 

        for i, new_tb_def in enumerate(new_tb_defs):
            new_tb_id = new_tb_def.get("id")
            if new_tb_id:
                if new_tb_id in old_text_content: # Direct match by ID
                    new_text_content[new_tb_id] = old_text_content[new_tb_id]
                elif i < len(old_tb_ids_ordered) and not initial_load : 
                    old_content_key_by_pos = old_tb_ids_ordered[i]
                    new_text_content[new_tb_id] = old_text_content.get(old_content_key_by_pos, "")
                else:
                    new_text_content[new_tb_id] = "" 
        
        new_template_settings["text_content"] = new_text_content
        # Update SlideData directly. This is important.
        self.slide_data.template_settings = new_template_settings
    
        text_box_widgets = [
            (self.text_box_one_label, self.text_box_one_edit),
            (self.text_box_two_label, self.text_box_two_edit),
            (self.text_box_three_label, self.text_box_three_edit)
        ]

        defined_text_boxes = []
        if self.slide_data.template_settings and "text_boxes" in self.slide_data.template_settings:
            defined_text_boxes = self.slide_data.template_settings["text_boxes"]

        for i, (label_widget, edit_widget) in enumerate(text_box_widgets):
            if i < len(defined_text_boxes):
                tb_def = defined_text_boxes[i]
                tb_id = tb_def.get("id")
                # Use template's "label", then "id", then fallback to "Field X"
                tb_label_from_template = tb_def.get("label")
                if tb_label_from_template:
                    tb_label_text = tb_label_from_template
                else:
                    tb_label_text = tb_def.get("id", f"Field {i+1}")

                if label_widget:
                    label_widget.setText(f"{tb_label_text}:")
                    label_widget.setVisible(True)
                if edit_widget:
                    content_value = ""
                    if tb_id and self.slide_data.template_settings.get("text_content"):
                        content_value = self.slide_data.template_settings["text_content"].get(tb_id, "")
                    
                    if initial_load:
                        if edit_widget.toPlainText() != content_value: edit_widget.setPlainText(content_value)
                    else:
                        edit_widget.setPlainText(content_value)

                    edit_widget.setVisible(True)
                    self._adjust_specific_text_edit_height(edit_widget) # Adjust height after setting content
            else:
                # Hide unused text box widgets
                if label_widget:
                    label_widget.setVisible(False)
                if edit_widget:
                    edit_widget.setVisible(False)
                    edit_widget.clear() # Clear content of hidden boxes
        
        if not initial_load:
            self.update_slide_preview()

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

    @Slot()
    def _adjust_text_edit_height_on_signal(self):
        text_edit = self.sender()
        if isinstance(text_edit, QTextEdit):
            self._adjust_specific_text_edit_height(text_edit)

    def _adjust_specific_text_edit_height(self, text_edit: QTextEdit):
        if not text_edit or not text_edit.isVisible(): # Don't adjust if not visible
            return

        document = text_edit.document()
        doc_layout_height = document.documentLayout().documentSize().height()

        margins = text_edit.contentsMargins()
        frame_width = text_edit.frameWidth() * 2 
        
        content_height = doc_layout_height + margins.top() + margins.bottom() + frame_width
        
        font_metrics = text_edit.fontMetrics()
        min_height_for_one_line = font_metrics.height() + margins.top() + margins.bottom() + frame_width
        
        padding = 6
        
        final_height = max(content_height, min_height_for_one_line) + padding

        current_height = text_edit.height()
        if abs(current_height - int(final_height)) > 1:
            text_edit.setFixedHeight(int(final_height))
            
            # Force the widget's own layout to update immediately
            if self.layout() is not None:
                self.layout().activate()
            # Then, notify the parent layout system that this widget's sizeHint might have changed.
            self.updateGeometry() 

    @Slot()
    def _handle_text_edit_changed(self):
        sender_edit = self.sender()
        text_box_map = {
            self.text_box_one_edit: 0,
            self.text_box_two_edit: 1,
            self.text_box_three_edit: 2
        }
        if sender_edit in text_box_map and self.slide_data and self.slide_data.template_settings:
            text_box_index = text_box_map[sender_edit]
            template_text_boxes = self.slide_data.template_settings.get("text_boxes", [])
            if text_box_index < len(template_text_boxes):
                tb_id = template_text_boxes[text_box_index].get("id")
                if tb_id:
                    if "text_content" not in self.slide_data.template_settings:
                        self.slide_data.template_settings["text_content"] = {}
                    self.slide_data.template_settings["text_content"][tb_id] = sender_edit.toPlainText()
                    self.update_slide_preview()

    def update_slide_preview(self):
        if not self.slide_renderer or not self.slide_data or not self.slide_preview_label:
            if self.slide_preview_label: self.slide_preview_label.setText("Preview N/A")
            return

        # Check if the label has at least its minimum/target size before proceeding.
        # This QTimer helps wait for the layout to settle initially.
        label_display_width = self.slide_preview_label.width()
        label_display_height = self.slide_preview_label.height()

        if label_display_width < TARGET_PREVIEW_DISPLAY_WIDTH -1 or label_display_height < TARGET_PREVIEW_DISPLAY_HEIGHT -1: 
            # self.slide_preview_label.setText("Sizing...") # Can be noisy
            QTimer.singleShot(50, self.update_slide_preview) # Try again shortly
            return

        try:
            # 1. Render the slide at the defined high resolution
            rendered_pixmap, _, _ = self.slide_renderer.render_slide(
                slide_data=self.slide_data,
                width=PREVIEW_RENDER_WIDTH,   # Render at fixed high-res width
                height=PREVIEW_RENDER_HEIGHT, # Render at fixed high-res height
                is_final_output=False 
            )

            if rendered_pixmap and not rendered_pixmap.isNull():
                # 2. Create a new pixmap with the TARGET fixed display dimensions
                final_display_pixmap = QPixmap(TARGET_PREVIEW_DISPLAY_WIDTH, TARGET_PREVIEW_DISPLAY_HEIGHT)
                if final_display_pixmap.isNull(): # Should not happen if label size is valid
                    self.slide_preview_label.setText("Preview Error (Pixmap)")
                    return
                final_display_pixmap.fill(Qt.GlobalColor.transparent) # Start with a transparent background

                # 3. Scale the high-res rendered_pixmap to fit the TARGET fixed display dimensions, keeping aspect ratio
                image_to_draw_on_label = rendered_pixmap.scaled(
                    QSize(TARGET_PREVIEW_DISPLAY_WIDTH, TARGET_PREVIEW_DISPLAY_HEIGHT), # Scale to fit target display
                    Qt.AspectRatioMode.KeepAspectRatio, # Added aspectMode argument
                    Qt.TransformationMode.SmoothTransformation
                )

                # 4. Draw the scaled image onto the center of final_display_pixmap
                painter = QPainter(final_display_pixmap)
                if painter.isActive():
                    x_offset = (final_display_pixmap.width() - image_to_draw_on_label.width()) / 2
                    y_offset = (final_display_pixmap.height() - image_to_draw_on_label.height()) / 2
                    draw_rect = QRectF(x_offset, y_offset, image_to_draw_on_label.width(), image_to_draw_on_label.height())
                    painter.drawPixmap(draw_rect.toRect(), image_to_draw_on_label)
                    painter.end()
                    self.slide_preview_label.setPixmap(final_display_pixmap)
                else:
                    self.slide_preview_label.setText("Preview Error (Painter)")
            else:
                self.slide_preview_label.setText("Render Failed")
        except Exception as e:
            print(f"Error rendering slide preview for {self.slide_data.id}: {e}")
            self.slide_preview_label.setText(f"Render Err") # Keep it short

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # Mock TemplateManager for basic testing
    class MockTemplateManager:
        def get_layout_names(self):
            return ["TestLyrics", "TestTitle", "Default Layout", "Image Only"]
        def get_system_default_fallback_layout_name(self):
            return "Default Layout"
        def get_layout_template_by_name(self, name):
            if name == "TestLyrics": return {"text_boxes": [{}, {}, {}]} # 3 boxes
            if name == "TestTitle": return {"text_boxes": [{}]} # 1 box
            if name == "Image Only": return {"text_boxes": []} # 0 boxes
            return {"layout_name": name, "text_boxes": [{"id": "tb1", "label":"TB1"}, {"id": "tb2", "label":"TB2"}]} # Default Layout
        def resolve_layout_template(self, name): # Mock this too
            # Simplified version for mock
            if name == "TestTitle":
                return {"layout_name": "TestTitle", "text_boxes": [{"id": "main_text", "label": "Title"}], "text_content": {}}
            return {"layout_name": name, "text_boxes": [{"id": "default_tb", "label": "Content"}], "text_content": {}}

    # Mock SlideRenderer
    class MockSlideRenderer:
        # Adjusted mock to match the expected signature (width, height)
        def render_slide(self, slide_data, width, height, is_final_output): # Removed force_render_transparent_background
            target_width = width
            target_height = height
            pix = QPixmap(target_width, target_height)
            pix.fill(Qt.GlobalColor.lightGray)
            # In a real test, you might draw some text from slide_data.template_settings['text_content']
            return pix, None, None

    mock_tm = MockTemplateManager()
    mock_renderer = MockSlideRenderer()
    # Example content_data for testing
    test_content_data_lyrics = {"main_text": "Verse 1 lyrics", "secondary_text": "Chorus lyrics"}
    test_content_data_title = {"main_text": "My Awesome Title", "Player": "John Doe"}
    test_slide_data = SlideData(id="test_slide_01", template_settings=mock_tm.resolve_layout_template("TestTitle"))
    test_slide_data.template_settings["text_content"] = test_content_data_title

    slide_item_widget = SlideEditorItemWidget(slide_id="test_slide_01", 
                                            slide_data=test_slide_data,
                                            template_manager=mock_tm,
                                            slide_renderer=mock_renderer)
    slide_item_widget.setWindowTitle("Slide Editor Item Test")
    slide_item_widget.set_slide_name("My Awesome Test Slide (ID: test_slide_01)")

    slide_item_widget.set_text_content({
        "text_box_one": "Hello from Text Box 1!",
        "text_box_two": "This is the second text box."
    })
    # slide_item_widget.update_preview(text="Custom Preview Text") # Preview update logic is basic
    slide_item_widget.show()
    
    sys.exit(app.exec())
