import sys
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTextEdit, QPushButton, QApplication, QFrame, QComboBox, QColorDialog, QDialogButtonBox, QDialog # Added QColorDialog
)
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import Qt, QFileInfo, QDir, Slot, QTimer, QRectF, QSize, Signal # Added Signal
from PySide6.QtGui import QPixmap, QPainter, QShowEvent, QColor # Added QColor

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
    # Signal to emit the updated preview pixmap (the one displayed on the label)
    preview_updated = Signal(str, QPixmap) # Emits slide_data.id and the pixmap
    banner_color_change_requested = Signal(str, QColor) # Emits slide_id, new_color
    add_slide_after_requested = Signal(str) # Emits instance_id of the current slide
    remove_slide_requested = Signal(str)    # Emits instance_id of the current slide
    content_changed = Signal() # New signal to indicate content (like text) has changed


    def __init__(self, slide_data: SlideData, template_manager: TemplateManager, slide_renderer: LayeredSlideRenderer, main_editor_ref, parent: QWidget = None):
        super().__init__(parent)
        self.slide_data = slide_data
        self.template_manager = template_manager
        self.slide_renderer = slide_renderer
        self.main_editor_ref = main_editor_ref # Store reference to MainEditorWindow
        self._initial_preview_emitted = False # Flag to track initial signal emission

        self._is_template_missing: bool = False # New: Track if the template is missing
        self._original_template_name: Optional[str] = None # New: Store original name if missing


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
        self.banner_color_picker_button: QPushButton = self.findChild(QPushButton, "banner_color_picker_button")


        self.text_box_one_label: QLabel = self.findChild(QLabel, "text_box_one_label")
        self.text_box_one_edit: QTextEdit = self.findChild(QTextEdit, "text_box_one_edit")
        self.text_box_two_label: QLabel = self.findChild(QLabel, "text_box_two_label")
        self.text_box_two_edit: QTextEdit = self.findChild(QTextEdit, "text_box_two_edit")
        self.text_box_three_label: QLabel = self.findChild(QLabel, "text_box_three_label")
        self.text_box_three_edit: QTextEdit = self.findChild(QTextEdit, "text_box_three_edit")

        # Example: Set initial text or connect signals
        if self.slide_name_banner_label:
            # self.slide_data.id is now the instance_id. For display, slide_block_id or overlay_label is better.
            display_id_for_banner = self.slide_data.slide_block_id or self.slide_data.id # Fallback to instance_id if block_id is missing
            self.slide_name_banner_label.setText(f"Editing: {display_id_for_banner} ({self.slide_data.overlay_label or 'No Label'})")

            self.refresh_ui_appearance() # Initial call to set banner color etc.

        # Populate and set the template combo box
        self._populate_and_set_template_combobox()

        if self.templates_combo_box_per_slide:
            self.templates_combo_box_per_slide.currentTextChanged.connect(self.on_template_selected)
            # Initialize text box visibility based on the default template
            # This is now called at the end of _populate_and_set_template_combobox
        if self.banner_color_picker_button:
            self.banner_color_picker_button.clicked.connect(self._handle_banner_color_button_clicked)

        if self.plus_button:
            self.plus_button.clicked.connect(self._handle_plus_button_clicked)
        
        if self.minus_button:
            self.minus_button.clicked.connect(self._handle_minus_button_clicked)


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

        # Add a special entry for the "Template Missing" state if the slide is in that state
        if self.slide_data.template_settings.get('layout_name') == "MISSING_LAYOUT_ERROR":
            self.templates_combo_box_per_slide.addItem("Template Missing", userData="MISSING_LAYOUT_ERROR")
        
        try:
            available_template_names = self.template_manager.get_layout_names()
            if not available_template_names: # Ensure there's at least the default if TM is empty
                 available_template_names = [self.template_manager.get_system_default_fallback_layout_name()]

        except Exception as e:
            print(f"Error getting template names from TemplateManager: {e}")
            available_template_names = ["Error Loading Templates"] # Fallback

        # Add actual available template names, skipping the error state if it was added
        for name in available_template_names:
            if name != "MISSING_LAYOUT_ERROR": # Ensure we don't add this as a selectable option
                 self.templates_combo_box_per_slide.addItem(name, userData=name)

        # Try to set the current template based on self.template_id
        current_layout_name = self.slide_data.template_settings.get('layout_name')
        if current_layout_name == "MISSING_LAYOUT_ERROR":
            # If the slide is in the error state, select the special "Template Missing" item
            self.templates_combo_box_per_slide.setCurrentText("Template Missing")
            self.templates_combo_box_per_slide.setEnabled(False) # Disable changing template if missing
        elif current_layout_name and current_layout_name in available_template_names: # Check against available names
            self.templates_combo_box_per_slide.setCurrentText(current_layout_name)
            # print(f"SlideEditorItemWidget ({self.slide_data.id}): Set template to '{current_layout_name}'.")
        elif available_template_names:
            # print(f"SlideEditorItemWidget ({self.slide_data.id}): Template ID '{current_layout_name}' not found. Defaulting to '{available_template_names[0]}'.")
            self.templates_combo_box_per_slide.setCurrentIndex(0) # Default to first if specific not found
        else:
            print(f"SlideEditorItemWidget ({self.slide_data.id}): No templates available, and '{current_layout_name}' not found.")

        # Ensure the combo box is enabled if it wasn't set to "Template Missing"
        if current_layout_name != "MISSING_LAYOUT_ERROR":
             self.templates_combo_box_per_slide.setEnabled(True)

        # After populating and setting, call on_template_selected to set initial visibility
        # Pass the actual template name or the error state string
        self.on_template_selected(current_layout_name, initial_load=True)

    def on_template_selected(self, template_name: str, initial_load: bool = False):
        """Handles changes in the per-slide template selection."""
        # print(f"Slide '{self.slide_data.id}': Template selected '{template_name}', initial_load={initial_load}")

        # --- Handle "Template Missing" State ---
        if template_name == "MISSING_LAYOUT_ERROR":
            self._is_template_missing = True
            self._original_template_name = self.slide_data.template_settings.get('original_template_name') # Get from stored data
            self.refresh_ui_appearance() # Update banner etc.
            self.update_slide_preview() # Preview renderer will draw error
            self._hide_all_text_box_widgets() # Hide text box controls
            return # Stop processing here for missing template
        # --- End Handle "Template Missing" State ---

        # More robust: Get template definition from TemplateManager
        new_template_settings = self.template_manager.resolve_layout_template(template_name) # This should NOT return MISSING_LAYOUT_ERROR
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
        
        # Clear any previous error state if a valid template was selected
        self._is_template_missing = False
        self._original_template_name = None

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
        
        # Ensure text box containers are visible if there are defined text boxes
        if defined_text_boxes:
            if self.text_box_one_edit: self.text_box_one_edit.parentWidget().setVisible(True)
            if self.text_box_two_edit: self.text_box_two_edit.parentWidget().setVisible(True)
            if self.text_box_three_edit: self.text_box_three_edit.parentWidget().setVisible(True)
        else: # No text boxes defined in the template
            self._hide_all_text_box_widgets()

        self.refresh_ui_appearance() # Update banner etc.
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

    def _hide_all_text_box_widgets(self):
        """Hides all text box labels and edits."""
        text_box_widgets = [self.text_box_one_label, self.text_box_one_edit,
                            self.text_box_two_label, self.text_box_two_edit,
                            self.text_box_three_label, self.text_box_three_edit]
        for widget in text_box_widgets: widget.setVisible(False)

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
                    self.content_changed.emit() # Emit signal that content has changed
                    self.update_slide_preview()

    def update_slide_preview(self):
        if not self.slide_renderer or not self.slide_data or not self.slide_preview_label:
            if self.slide_preview_label: self.slide_preview_label.setText("Preview N/A")
            return

        # Check if the label has at least its minimum/target size before proceeding.
        # This QTimer helps wait for the layout to settle initially.
        label_display_width = self.slide_preview_label.width()
        label_display_height = self.slide_preview_label.height()

        print(f"DEBUG ({self.slide_data.id}): update_slide_preview called. Label size: {label_display_width}x{label_display_height}") # DEBUG

        if label_display_width < TARGET_PREVIEW_DISPLAY_WIDTH -1 or label_display_height < TARGET_PREVIEW_DISPLAY_HEIGHT -1: 
            print(f"DEBUG ({self.slide_data.id}): Label too small, scheduling QTimer.") # DEBUG
            QTimer.singleShot(50, self.update_slide_preview) # Try again shortly
            return
        print(f"DEBUG ({self.slide_data.id}): Proceeding with render. Target display: {TARGET_PREVIEW_DISPLAY_WIDTH}x{TARGET_PREVIEW_DISPLAY_HEIGHT}") # DEBUG
        
        # Fetch section metadata via the main_editor_ref
        section_metadata = None
        if self.main_editor_ref and hasattr(self.main_editor_ref, 'get_current_section_metadata'):
            section_metadata = self.main_editor_ref.get_current_section_metadata()
        
        section_title = None
        if self.main_editor_ref and hasattr(self.main_editor_ref, 'get_current_section_title'):
            section_title = self.main_editor_ref.get_current_section_title()

        try:
            # 1. Render the slide at the defined high resolution
            rendered_pixmap, _, _ = self.slide_renderer.render_slide(
                slide_data=self.slide_data,
                width=PREVIEW_RENDER_WIDTH,   # Render at fixed high-res width
                height=PREVIEW_RENDER_HEIGHT, # Render at fixed high-res height
                is_final_output=False,
                section_metadata=section_metadata, # Pass the fetched metadata
                section_title=section_title # Pass the fetched section title
            )

            print(f"DEBUG ({self.slide_data.id}): High-res render complete. Rendered pixmap size: {rendered_pixmap.size() if rendered_pixmap else 'None'}") # DEBUG

            if rendered_pixmap and not rendered_pixmap.isNull():
                # 2. Create a new pixmap with the TARGET fixed display dimensions
                final_display_pixmap = QPixmap(TARGET_PREVIEW_DISPLAY_WIDTH, TARGET_PREVIEW_DISPLAY_HEIGHT)
                if final_display_pixmap.isNull(): # Should not happen if label size is valid
                    print(f"DEBUG ({self.slide_data.id}): ERROR - final_display_pixmap is Null.") # DEBUG
                    self.slide_preview_label.setText("Preview Error (Pixmap)")
                    return
                final_display_pixmap.fill(Qt.GlobalColor.transparent) # Start with a transparent background
                print(f"DEBUG ({self.slide_data.id}): final_display_pixmap created. Size: {final_display_pixmap.size()}") # DEBUG

                # 3. Scale the high-res rendered_pixmap to fit the TARGET fixed display dimensions, keeping aspect ratio
                image_to_draw_on_label = rendered_pixmap.scaled(
                    QSize(TARGET_PREVIEW_DISPLAY_WIDTH, TARGET_PREVIEW_DISPLAY_HEIGHT), # Scale to fit target display
                    Qt.AspectRatioMode.KeepAspectRatio, # Added aspectMode argument
                    Qt.TransformationMode.SmoothTransformation
                )
                print(f"DEBUG ({self.slide_data.id}): image_to_draw_on_label (scaled from high-res). Size: {image_to_draw_on_label.size()}") # DEBUG

                # 4. Draw the scaled image onto the center of final_display_pixmap
                painter = QPainter(final_display_pixmap)
                if painter.isActive():
                    x_offset = (final_display_pixmap.width() - image_to_draw_on_label.width()) / 2
                    y_offset = (final_display_pixmap.height() - image_to_draw_on_label.height()) / 2
                    draw_rect = QRectF(x_offset, y_offset, image_to_draw_on_label.width(), image_to_draw_on_label.height())
                    print(f"DEBUG ({self.slide_data.id}): Drawing image_to_draw_on_label into rect: {draw_rect} on final_display_pixmap.") # DEBUG
                    painter.drawPixmap(draw_rect.toRect(), image_to_draw_on_label)
                    painter.end()
                    self._initial_preview_emitted = True # Mark that we've successfully rendered and emitted at least once
                    # Emit the final pixmap that is being displayed on the label
                    self.preview_updated.emit(self.slide_data.id, final_display_pixmap.copy())
                    self.slide_preview_label.setPixmap(final_display_pixmap)
                else:
                    self.slide_preview_label.setText("Preview Error (Painter)")
                    print(f"DEBUG ({self.slide_data.id}): ERROR - QPainter not active for final_display_pixmap.") # DEBUG
            else:
                self.slide_preview_label.setText("Render Failed")
                print(f"DEBUG ({self.slide_data.id}): Render failed or high-res rendered_pixmap is Null.") # DEBUG
        except Exception as e:
            print(f"Error rendering slide preview for {self.slide_data.id}: {e}")
            self.slide_preview_label.setText(f"Render Err") # Keep it short
            import traceback; traceback.print_exc() # Print full traceback for exceptions

    def get_current_preview_pixmap(self) -> QPixmap | None:
        """Returns the current pixmap displayed on the preview label, if any."""
        if self.slide_preview_label:
            return self.slide_preview_label.pixmap()
        return None
    
    @Slot()
    def _handle_banner_color_button_clicked(self):
        if not self.slide_data:
            return
        
        initial_color = self.slide_data.banner_color if self.slide_data.banner_color and self.slide_data.banner_color.isValid() else QColor(Qt.GlobalColor.white)
        
        dialog = QColorDialog(self)
        dialog.setWindowTitle("Select Banner Color")
        dialog.setCurrentColor(initial_color)
        dialog.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, True) # Allow alpha selection

        # Add a "No Color" button
        no_color_button = dialog.findChild(QDialogButtonBox).addButton("No Color", QDialogButtonBox.ResetRole)

        # Revised logic for clarity with the custom button:
        
        # We need to know if "No Color" was clicked.
        # One way is to connect the button's clicked signal to a slot that sets a flag.
        
        # Ensure _no_color_selected_flag is an instance variable if not already defined in __init__
        if not hasattr(self, '_no_color_selected_flag'):
            self._no_color_selected_flag = False
        else:
            self._no_color_selected_flag = False # Reset flag before each dialog
            
        def on_no_color_clicked():
            self._no_color_selected_flag = True
            dialog.accept() # Close the dialog as if "OK" was pressed, but we'll use the flag

        no_color_button.clicked.connect(on_no_color_clicked)

        result = dialog.exec() # Call exec() once and store the result

        chosen_color: Optional[QColor] = None # Initialize chosen_color

        if result == QDialog.DialogCode.Accepted:
            if self._no_color_selected_flag:
                chosen_color = None # Represent "no color" as None
            else:
                chosen_color = dialog.selectedColor()
                if not chosen_color.isValid(): # If user clicked OK but didn't pick a valid color
                    chosen_color = None # Treat as no color or keep initial? For now, treat as no change.
                                        # Or, if OK means "use current selection", then it's dialog.selectedColor()
                                        # Let's assume if OK is pressed, a valid color is expected unless "No Color" was used.
                    # If OK is pressed and color is invalid, we probably shouldn't emit.
                    # Let's only emit if chosen_color is a valid QColor or explicitly None (from "No Color" button)
                    if not dialog.selectedColor().isValid(): # If OK was pressed but color is invalid
                        return # Don't emit anything, effectively a cancel or no change


            # Emit regardless of whether chosen_color is a QColor or None
            # Emit the slide_block_id, as MainEditorWindow uses this to find the global index in PM
            block_id_to_emit = self.slide_data.slide_block_id or self.slide_data.id # Fallback if slide_block_id is None
            self.banner_color_change_requested.emit(block_id_to_emit, chosen_color) 
            # MainEditorWindow._handle_slide_item_banner_color_changed needs to handle chosen_color being None

    def refresh_ui_appearance(self):
        """Updates visual elements like banner color based on current slide_data."""
        # Update Banner Color
        if not self.slide_name_banner_label or not self.slide_data:
            return

        # --- Handle Template Missing Error in Banner ---
        if self._is_template_missing:
            original_name = self._original_template_name or 'Unknown'
            self.slide_name_banner_label.setText(f"ERROR: Template Missing ('{original_name}')")
            self.slide_name_banner_label.setStyleSheet("font-weight: bold; background-color: red; color: white;")
            self.slide_name_banner_label.setAutoFillBackground(True)
            return # Stop here if template is missing
        # --- End Handle Template Missing Error ---

        # Normal Banner Appearance
        # self.slide_data.id is now the instance_id. For display, slide_block_id or overlay_label is better.
        display_id_for_banner = self.slide_data.slide_block_id or self.slide_data.id # Fallback to instance_id if block_id is missing
        self.slide_name_banner_label.setText(f"Editing: {display_id_for_banner} ({self.slide_data.overlay_label or 'No Label'})")

        # Get the base style from the UI file for the label (font-weight: bold;)
        base_font_style = "font-weight: bold;" # From UI
        current_banner_color = self.slide_data.banner_color

        if current_banner_color and current_banner_color.isValid():
            self.slide_name_banner_label.setStyleSheet(f"{base_font_style} background-color: {current_banner_color.name()};")
            self.slide_name_banner_label.setAutoFillBackground(True) # Ensure background is painted
        else:
            # Explicitly set background to transparent for "no color"
            self.slide_name_banner_label.setStyleSheet(f"{base_font_style} background-color: transparent;")
            self.slide_name_banner_label.setAutoFillBackground(True) # Needs to be true for transparent to work correctly with stylesheets

    @Slot()
    def _handle_plus_button_clicked(self):
        if self.slide_data and self.slide_data.id:
            self.add_slide_after_requested.emit(self.slide_data.id)

    @Slot()
    def _handle_minus_button_clicked(self):
        if self.slide_data and self.slide_data.id:
            # TODO: Add a confirmation dialog here?
            # reply = QMessageBox.question(self, "Remove Slide", "Are you sure you want to remove this slide?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            # if reply == QMessageBox.Yes:
            self.remove_slide_requested.emit(self.slide_data.id)

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

    slide_item_widget = SlideEditorItemWidget(slide_data=test_slide_data, # Pass SlideData, remove slide_id kwarg
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
