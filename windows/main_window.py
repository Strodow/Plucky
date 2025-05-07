import sys
import os
import uuid # For generating unique slide IDs for testing

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QSlider,
    QMessageBox, QVBoxLayout, QWidget, QPushButton, QInputDialog, QDialog,
    QComboBox, QLabel, QHBoxLayout, QSplitter, QScrollArea, QButtonGroup
)
from PySide6.QtGui import QScreen, QPixmap
from PySide6.QtCore import Qt, QSize, Slot, QEvent # Added QEvent

# --- Local Imports ---
# Make sure these paths are correct relative to where you run main.py
try:
    # Assuming running from the YourProject directory
    from windows.output_window import OutputWindow
    from data_models.slide_data import SlideData, DEFAULT_TEMPLATE # Import DEFAULT_TEMPLATE
    from rendering.slide_renderer import SlideRenderer
    from widgets.scaled_slide_button import ScaledSlideButton # This should already be there
    from windows.template_editor_window import TemplateEditorWindow # Import the new editor
    from widgets.song_header_widget import SongHeaderWidget # Import the new header widget
    from widgets.flow_layout import FlowLayout # Import the new FlowLayout
    from core.presentation_manager import PresentationManager
    from core.template_manager import TemplateManager # Import TemplateManager
    # --- Undo/Redo Command Imports ---
    from commands.slide_commands import (
        ChangeOverlayLabelCommand, EditLyricsCommand, AddSlideCommand, DeleteSlideCommand, ApplyTemplateCommand
    )
except ImportError:
    # Fallback if running directly from the windows directory (adjust as needed)
    # import sys, os # Already imported at top level
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from windows.output_window import OutputWindow
    from data_models.slide_data import SlideData, DEFAULT_TEMPLATE # Import DEFAULT_TEMPLATE
    from rendering.slide_renderer import SlideRenderer
    from widgets.scaled_slide_button import ScaledSlideButton # This should already be there
    from windows.template_editor_window import TemplateEditorWindow # Import the new editor
    from widgets.song_header_widget import SongHeaderWidget # Import the new header widget
    from widgets.flow_layout import FlowLayout # Import the new FlowLayout
    from core.presentation_manager import PresentationManager
    from core.template_manager import TemplateManager # Import TemplateManager
    # --- Undo/Redo Command Imports ---
    from commands.slide_commands import (
        ChangeOverlayLabelCommand, EditLyricsCommand, AddSlideCommand, DeleteSlideCommand, ApplyTemplateCommand
    )

# Constants for button previews
# These are now BASE dimensions for calculating scaled preview sizes
BASE_PREVIEW_WIDTH = 160
BASE_PREVIEW_HEIGHT = 90

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Plucky Presentation")
        self.setGeometry(100, 100, 900, 700) # Adjusted size for more controls

        # MainWindow can have focus, but scroll_area is more important for this.
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus) 
        # self.setFocus() # Attempt to give focus to MainWindow initially

        # Instantiate the TemplateManager
        self.template_manager = TemplateManager()
        self.template_manager.templates_changed.connect(self.on_template_collection_changed)

        # --- Core Components ---
        self.output_window = OutputWindow()
        self.slide_renderer = SlideRenderer()
        self.presentation_manager = PresentationManager() # Assuming this is already here
        self.presentation_manager.presentation_changed.connect(self.update_slide_display_and_selection)
        self.presentation_manager.error_occurred.connect(self.show_error_message)
        self.button_scale_factor = 1.0 # Default scale

        self.current_slide_index = -1 # Tracks the selected slide button's index
        self.output_resolution = QSize(1920, 1080) # Default, updated on monitor select
        self.slide_button_group = QButtonGroup(self)
        self.slide_button_group.setExclusive(True)

        # --- UI Elements ---
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        # Top controls: Monitor and Live
        self.monitor_combo = QComboBox()
        self.refresh_monitors_button = QPushButton("Refresh Monitors")
        self.go_live_button = QPushButton("Go Live")

        # Top controls: File Operations
        self.load_button = QPushButton("Load")
        self.save_button = QPushButton("Save")
        self.save_as_button = QPushButton("Save As...")
        self.add_song_button = QPushButton("Add Song") # New button
        self.add_test_slide_button = QPushButton("Add Test Slide")
        self.clear_button = QPushButton("Clear All Slides")
        self.edit_template_button = QPushButton("Edit Template") # New button
        self.undo_button = QPushButton("Undo") # New
        self.redo_button = QPushButton("Redo") # New

        # Template Selector ComboBox - REMOVED
        # self.template_selector_combo = QComboBox()

        # Button Size Slider
        self.button_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.button_size_slider.setMinimum(100) # Represents 1.0x scale (base size)
        self.button_size_slider.setMaximum(300) # Represents 3.0x scale (allows for larger previews)
        self.button_size_slider.setValue(100)   # Default to 1.0x scale
        self.button_size_slider.setToolTip("Adjust Slide Preview Size")

        # Slide Button Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.slide_buttons_widget = QWidget()
        # This is now the main vertical layout for song headers and their slide containers
        self.slide_buttons_layout = QVBoxLayout(self.slide_buttons_widget)
        self.slide_buttons_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.slide_buttons_layout.setSpacing(0) # Let widgets/layouts inside manage their own margins/spacing
        self.scroll_area.setWidget(self.slide_buttons_widget)

        # --- Layouts ---
        main_layout = QHBoxLayout(self.central_widget)
        left_panel_widget = QWidget()
        left_layout = QVBoxLayout(left_panel_widget)

        # Monitor controls layout
        monitor_layout = QHBoxLayout()
        monitor_layout.addWidget(QLabel("Output Monitor:"))
        monitor_layout.addWidget(self.monitor_combo, 1) # Add stretch factor
        monitor_layout.addWidget(self.refresh_monitors_button)
        monitor_layout.addWidget(self.go_live_button)
        left_layout.addLayout(monitor_layout)

        # File operations layout
        file_ops_layout = QHBoxLayout()
        file_ops_layout.addWidget(self.load_button)
        file_ops_layout.addWidget(self.save_button)
        file_ops_layout.addWidget(self.save_as_button)
        file_ops_layout.addWidget(self.add_song_button) # Add to layout
        file_ops_layout.addStretch(1)
        file_ops_layout.addWidget(self.add_test_slide_button)
        file_ops_layout.addWidget(self.edit_template_button) # Add to layout
        file_ops_layout.addWidget(self.clear_button)
        file_ops_layout.addWidget(self.undo_button) # Add Undo button
        file_ops_layout.addWidget(self.redo_button) # Add Redo button
        left_layout.addLayout(file_ops_layout)
        
        # Template selector layout - REMOVED
        
        # Button size slider layout
        slider_layout = QHBoxLayout()
        slider_layout.addWidget(QLabel("Preview Size:"))
        slider_layout.addWidget(self.button_size_slider)
        left_layout.addLayout(slider_layout)

        left_layout.addSpacing(10)
        left_layout.addWidget(QLabel("Slides:"))
        left_layout.addWidget(self.scroll_area)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_panel_widget)
        # splitter.addWidget(right_panel_widget) # If you add a right panel later
        splitter.setSizes([350]) # Adjust initial size of left panel
        main_layout.addWidget(splitter)

        self.refresh_monitors()

        # --- Connections ---
        self.load_button.clicked.connect(self.handle_load)
        self.save_button.clicked.connect(self.handle_save)
        self.save_as_button.clicked.connect(self.handle_save_as)
        self.add_song_button.clicked.connect(self.handle_add_song) # Connect signal
        self.add_test_slide_button.clicked.connect(self.add_test_slide)
        self.clear_button.clicked.connect(self.handle_clear_all_slides)
        self.edit_template_button.clicked.connect(self.handle_edit_template) # Connect signal
        self.undo_button.clicked.connect(self.handle_undo) # New
        self.redo_button.clicked.connect(self.handle_redo) # New
        self.button_size_slider.sliderReleased.connect(self.handle_button_size_change) # Changed signal
        # self.template_selector_combo.currentTextChanged.connect(self.handle_active_template_changed) # REMOVED

        self.refresh_monitors_button.clicked.connect(self.refresh_monitors)
        self.go_live_button.clicked.connect(self.toggle_live)
        # self.slide_button_group.buttonClicked[int].connect(self._on_slide_button_selected_by_index) # Alternative

        self.update_slide_display_and_selection() # Initial setup of slide display
        
        # Install event filter directly on the QScrollArea.
        self.scroll_area.installEventFilter(self)
        # Ensure QScrollArea can receive focus.
        self.scroll_area.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            
    def refresh_monitors(self):
        self.monitor_combo.clear()
        screens = QApplication.screens()
        if not screens:
            self.monitor_combo.addItem("No monitors found")
            self.monitor_combo.setEnabled(False)
            return
        self.monitor_combo.setEnabled(True)
        for i, screen in enumerate(screens):
            geometry = screen.geometry()
            self.monitor_combo.addItem(f"Monitor {i+1}: {screen.name()} ({geometry.width()}x{geometry.height()})", screen)

    def toggle_live(self):
        selected_data = self.monitor_combo.currentData()
        if not selected_data and not self.output_window.isVisible(): # Only warn if trying to go live without selection
            QMessageBox.warning(self, "No Monitor Selected", "Please select a monitor to go live.")
            return

        if self.output_window.isVisible():
            self.go_live_button.setText("Go Live")
            self.go_live_button.setStyleSheet("")
            self._show_blank_on_output() # Good practice to blank it before hiding
            self.output_window.hide() # Explicitly hide the window
        else:
            if not selected_data: return # Should have been caught above
            self.go_live_button.setText("LIVE")
            self.go_live_button.setStyleSheet("background-color: red; color: white; font-weight: bold;")
            screen = selected_data
            output_geometry = screen.geometry()
            self.output_resolution = output_geometry.size()
            self.output_window.setGeometry(output_geometry)
            self.output_window.showFullScreen()
            if 0 <= self.current_slide_index < len(self.presentation_manager.get_slides()):
                self._display_slide(self.current_slide_index)
            else:
                self._show_blank_on_output() # Show blank if no valid slide selected

    def add_test_slide(self):
        slide_count = len(self.presentation_manager.get_slides())
        new_slide = SlideData(
            lyrics=f"Test Slide {slide_count + 1}\nAdded via button.",
            background_color=f"#{slide_count % 3 * 40:02X}{slide_count % 5 * 30:02X}{slide_count % 7 * 25:02X}" # pseudo-random color
        ) # Test slides will use the current default template from SlideData class, overlay_label defaults to ""
        # To use the MainWindow's current_default_template:
        test_slide_template = self.template_manager.get_template_settings("Default") or DEFAULT_TEMPLATE.copy()
        new_slide = SlideData(lyrics=new_slide.lyrics, template_settings=test_slide_template)
        
        # Use Command for adding slide
        cmd = AddSlideCommand(self.presentation_manager, new_slide)
        self.presentation_manager.do_command(cmd)

    def handle_add_song(self):
        """
        Prompts the user for song lyrics and adds them as new slides.
        Lyrics are split into slides by double newlines.
        """
        song_title_text, ok_title = QInputDialog.getText(
            self,
            "Add New Song - Title",
            "Enter the song title:"
        )

        if not ok_title or not song_title_text.strip():
            # User cancelled or entered an empty title
            if ok_title and not song_title_text.strip(): # User pressed OK but title was empty
                QMessageBox.warning(self, "Empty Title", "Song title cannot be empty.")
            return
        
        cleaned_song_title = song_title_text.strip()

        lyrics_text, ok_lyrics = QInputDialog.getMultiLineText(
            self,
            f"Add Lyrics for \"{cleaned_song_title}\"",
            "Paste or type song lyrics below.\n"
            "Use a blank line (press Enter twice) to separate slides/stanzas."
        )

        if ok_lyrics and lyrics_text:
            # Split by one or more blank lines (effectively \n\n or more \n's)
            stanzas = [s.strip() for s in lyrics_text.split('\n\n') if s.strip()]

            if not stanzas:
                QMessageBox.information(self, "No Stanzas", "No stanzas found. Ensure you use blank lines to separate them.")
                return
            new_slides_data = []
            for stanza_lyrics in stanzas:
                # New songs will use the "Default" template from the TemplateManager
                default_tpl_for_new_song = self.template_manager.get_template_settings("Default") or DEFAULT_TEMPLATE.copy()
                new_slide = SlideData(lyrics=stanza_lyrics, 
                                      song_title=cleaned_song_title,
                                      overlay_label="", # Default for new song slides
                                      template_settings=default_tpl_for_new_song)
                new_slides_data.append(new_slide)
            
            # For multiple slides, you might create a "MacroCommand" or execute individual AddSlideCommands
            # For simplicity now, let's assume add_slides is not directly undoable as one step,
            # or we create multiple commands. Here, we'll just call the PM method.
            self.presentation_manager.add_slides(new_slides_data) # This won't be a single undo step

    def handle_load(self):
        if self.presentation_manager.is_dirty:
            reply = QMessageBox.question(self, 'Unsaved Changes',
                                         "You have unsaved changes. Save before loading new file?",
                                         QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            if reply == QMessageBox.Save:
                if not self.handle_save(): # If save fails or is cancelled
                    return
            elif reply == QMessageBox.Cancel:
                return
        
        filepath, _ = QFileDialog.getOpenFileName(self, "Load Presentation", "", "Plucky Files (*.plucky *.json);;All Files (*)")
        if filepath:
            self.presentation_manager.load_presentation(filepath)
            # After UI update (triggered by presentation_changed), explicitly mark as not dirty
            self.presentation_manager.is_dirty = False

    def handle_save(self) -> bool:
        if not self.presentation_manager.current_filepath:
            return self.handle_save_as()
        else:
            if self.presentation_manager.save_presentation():
                # Optionally add status bar message: "Presentation saved."
                return True
            # Error message handled by show_error_message via signal
            return False

    def handle_save_as(self) -> bool:
        filepath, _ = QFileDialog.getSaveFileName(self, "Save Presentation As...", self.presentation_manager.current_filepath or os.getcwd(), "Plucky Files (*.plucky *.json);;All Files (*)")
        if filepath:
            if self.presentation_manager.save_presentation(filepath):
                # Optionally add status bar message: "Presentation saved to {filepath}."
                return True
            return False
        return False # User cancelled dialog

    def handle_clear_all_slides(self):
        reply = QMessageBox.question(self, 'Clear All Slides',
                                     "Are you sure you want to clear all slides? This cannot be undone.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.current_slide_index = -1 # Reset UI selection state
            # This is a destructive operation, might need a "ClearAllCommand"
            # For now, directly clear and mark dirty. Undo stack will be cleared by new actions.
            self.presentation_manager.slides.clear()
            self.presentation_manager.is_dirty = True
            self.presentation_manager.presentation_changed.emit()

    @Slot() # No longer receives an int directly from the signal
    def handle_button_size_change(self):
        value = self.button_size_slider.value() # Get the current value from the slider
        self.button_scale_factor = value / 100.0  # Convert slider value (50-200) to scale (0.5-2.0)
        # This will trigger a full rebuild of the slide buttons with the new scale
        self.update_slide_display_and_selection()

    def handle_edit_template(self):
        # TemplateManager ensures "Default" always exists, so no need for the "No Templates" check here.

        # Pass all current named templates to the editor
        current_templates_snapshot = self.template_manager.get_all_templates()
        editor = TemplateEditorWindow(all_templates=current_templates_snapshot, parent=self)
        
        if editor.exec() == QDialog.DialogCode.Accepted:
            updated_templates_collection = editor.get_updated_templates()
            self.template_manager.update_from_collection(updated_templates_collection)
            # The templates_changed signal from TemplateManager will call on_template_collection_changed
            # which in turn calls update_slide_display_and_selection to refresh UI.

    @Slot()
    def update_slide_display_and_selection(self):
        """
        Clears and repopulates slide buttons. Manages selection.
        Called when presentation_manager.presentation_changed is emitted.
        """
        print("MainWindow: update_slide_display_and_selection called")
        
        # --- 1. Rebuild Slide Buttons ---
        # Clear existing buttons first
        while self.slide_buttons_layout.count():
            item = self.slide_buttons_layout.takeAt(0) # Item from the main QVBoxLayout
            widget_in_vbox = item.widget()
            if widget_in_vbox:
                # If it's a container QWidget holding a FlowLayout for slides
                if isinstance(widget_in_vbox.layout(), FlowLayout):
                    flow_layout_inside = widget_in_vbox.layout()
                    while flow_layout_inside.count():
                        flow_item = flow_layout_inside.takeAt(0)
                        slide_button_widget = flow_item.widget()
                        if slide_button_widget:
                            if isinstance(slide_button_widget, ScaledSlideButton):
                                self.slide_button_group.removeButton(slide_button_widget)
                            # Child widgets of widget_in_vbox will be deleted when widget_in_vbox is deleted
                            # No need to call deleteLater on slide_button_widget explicitly here
                            # as long as it's properly parented to widget_in_vbox or its layout.
                
                # For SongHeaderWidget, QLabel, or the container QWidget itself
                widget_in_vbox.setParent(None)
                widget_in_vbox.deleteLater()

        slides = self.presentation_manager.get_slides()

        if not slides:
            no_slides_label = QLabel("No slides. Use 'Load' or 'Add Test Slide'.")
            no_slides_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.slide_buttons_layout.addWidget(no_slides_label)
            self.current_slide_index = -1
            self._show_blank_on_output()
            return

        # Use a sentinel that's guaranteed not to match any actual title (including None)
        last_processed_title: Optional[str] = object() 
        current_song_flow_layout: Optional[FlowLayout] = None

        print(f"  update_slide_display_and_selection: Found {len(slides)} slides to process.")

        # Calculate dynamic preview dimensions based on scale factor
        current_dynamic_preview_width = int(BASE_PREVIEW_WIDTH * self.button_scale_factor)
        current_dynamic_preview_height = int(BASE_PREVIEW_HEIGHT * self.button_scale_factor)

        for index, slide_data in enumerate(slides):
            current_title = slide_data.song_title # This can be None or a string

            if current_title != last_processed_title:
                # This is a new song, or a transition to/from an untitled block of slides
                last_processed_title = current_title
                
                if current_title is not None: # It's a titled song
                    song_header = SongHeaderWidget(current_title, current_button_width=current_dynamic_preview_width)
                    song_header.edit_song_requested.connect(self.handle_edit_entire_song_requested)
                    self.slide_buttons_layout.addWidget(song_header) # Add header to main VBox
                # else:
                    # If current_title is None, we don't add a specific header for "untitled"
                    # but we still create a new FlowLayout container below.

                # Create a new container QWidget and FlowLayout for this group of slides
                song_slides_container = QWidget()
                # Pass the container as the parent to FlowLayout, it will set itself as layout
                current_song_flow_layout = FlowLayout(song_slides_container, margin=5, hSpacing=5, vSpacing=5)
                # song_slides_container.setLayout(current_song_flow_layout) # Not needed if parent passed to FlowLayout
                self.slide_buttons_layout.addWidget(song_slides_container) # Add container to main VBox

            # --- Process and create the ScaledSlideButton ---
            # print(f"    Processing slide {index}, ID: {slide_data.id}, Lyrics: '{slide_data.lyrics[:30].replace('\n', ' ')}...'") # DEBUG
            # (Ensure current_song_flow_layout is valid before adding buttons to it)
            preview_render_width = self.output_resolution.width() if self.output_window.isVisible() else 1920
            preview_render_height = self.output_resolution.height() if self.output_window.isVisible() else 1080
            
            try:
                full_res_pixmap = self.slide_renderer.render_slide(slide_data, preview_render_width, preview_render_height)
                # print(f"      Full-res pixmap for slide {index}: isNull={full_res_pixmap.isNull()}, size={full_res_pixmap.size()}") # DEBUG
                # if full_res_pixmap.isNull(): # DEBUG
                    # print(f"      WARNING: Full-res pixmap is NULL for slide {index}. Renderer might have failed silently.") # DEBUG
                
                preview_pixmap = full_res_pixmap.scaled(current_dynamic_preview_width, current_dynamic_preview_height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                # print(f"      Preview pixmap for slide {index}: isNull={preview_pixmap.isNull()}, size={preview_pixmap.size()}") # DEBUG
            except Exception as e:
                print(f"      ERROR rendering preview for slide {index} (ID {slide_data.id}): {e}")
                preview_pixmap = QPixmap(current_dynamic_preview_width, current_dynamic_preview_height) # Use dynamic size for placeholder
                preview_pixmap.fill(Qt.darkGray) # Corrected to Qt.darkGray
                # print(f"      Filled preview pixmap with darkGray due to error for slide {index}.") # DEBUG

            button = ScaledSlideButton(slide_id=index) # No longer needs scale_factor
            button.set_pixmap(preview_pixmap)
            # print(f"      Set pixmap for button {index}.") # DEBUG
            # button.setFixedSize(PREVIEW_WIDTH + 10, PREVIEW_HEIGHT + 10) # Padding
            button.setToolTip(f"Slide {index + 1}: {slide_data.lyrics.splitlines()[0] if slide_data.lyrics else 'Empty'}")
            button.slide_selected.connect(self._on_slide_button_selected_by_index) # Connect to new slot
            button.edit_requested.connect(self.handle_edit_slide_requested)
            button.delete_requested.connect(self.handle_delete_slide_requested)
            button.set_available_templates(self.template_manager.get_template_names()) # Pass template names
            button.apply_template_to_slide_requested.connect(self.handle_apply_template_to_slide)
            button.next_slide_requested_from_menu.connect(self.handle_next_slide_from_menu)
            button.previous_slide_requested_from_menu.connect(self.handle_previous_slide_from_menu)
            button.center_overlay_label_changed.connect(self.handle_slide_overlay_label_changed) # New connection
            
            if current_song_flow_layout: # Add button to the current song's FlowLayout
                current_song_flow_layout.addWidget(button)
            self.slide_button_group.addButton(button, index)
        
        # Add a stretch at the end of the main QVBoxLayout to push everything up
        self.slide_buttons_layout.addStretch(1)

        # After creating all buttons, set their overlay labels from SlideData
        self._update_all_button_overlay_labels()

        # --- 2. Manage Selection ---
        num_slides = len(slides)
        if self.current_slide_index >= num_slides: # If selected index is now out of bounds
            self.current_slide_index = num_slides - 1 if num_slides > 0 else -1
        
        if self.current_slide_index != -1:
            button_to_select = self.slide_button_group.button(self.current_slide_index)
            if button_to_select:
                if not button_to_select.isChecked(): # Check if not already checked to avoid signal loops
                    button_to_select.setChecked(True)
                # If it was already checked, and output is live, ensure it's displayed (content might have changed)
                if self.output_window.isVisible():
                     self._display_slide(self.current_slide_index)
            else: # Should not happen if index is valid
                self.current_slide_index = -1 
                self._show_blank_on_output()
        elif num_slides > 0: # No selection, but slides exist, select first one
            self.current_slide_index = 0
            button_to_select = self.slide_button_group.button(0)
            if button_to_select and not button_to_select.isChecked():
                button_to_select.setChecked(True) 
            # _on_slide_button_selected_by_index will handle display if output is live
        else: # No slides, no selection
            self._show_blank_on_output()

    def _update_all_button_overlay_labels(self):
        """Sets the overlay label on each button based on its corresponding SlideData."""
        slides = self.presentation_manager.get_slides()
        for index, slide_data in enumerate(slides):
            button = self.slide_button_group.button(index)
            if button and isinstance(button, ScaledSlideButton):
                # Pass the overlay_label from SlideData to the button
                button.set_center_overlay_label(slide_data.overlay_label, emit_signal_on_change=False)

    @Slot(int) # Receives slide_id (which is the index)
    def _on_slide_button_selected_by_index(self, slide_index: int):
        """Handles a slide button being clicked or programmatically selected."""
        slides = self.presentation_manager.get_slides()
        if 0 <= slide_index < len(slides):
            self.current_slide_index = slide_index
            print(f"_on_slide_button_selected_by_index: Slide {slide_index} selected. Current focus: {QApplication.focusWidget()}") # DEBUG
            if self.output_window.isVisible():
                self._display_slide(slide_index)
            # CRITICAL: After a slide is selected, set focus to the QScrollArea
            self.scroll_area.setFocus()
            print(f"_on_slide_button_selected_by_index: Focus set to scroll_area. New focus: {QApplication.focusWidget()}") # DEBUG

        else:
            print(f"Warning: Invalid slide index {slide_index} from button selection.")
            self.current_slide_index = -1
            self._show_blank_on_output()

    @Slot(int)
    def handle_edit_slide_requested(self, slide_index: int):
        slides = self.presentation_manager.get_slides()
        if not (0 <= slide_index < len(slides)):
            self.show_error_message(f"Cannot edit slide: Index {slide_index} is invalid.")
            return

        slide_data = slides[slide_index]
        current_lyrics = slide_data.lyrics
        song_title_info = f"for \"{slide_data.song_title}\" " if slide_data.song_title else ""

        new_lyrics, ok = QInputDialog.getMultiLineText(
            self,
            f"Edit Lyrics {song_title_info}(Slide {slide_index + 1})",
            "Modify the lyrics below:",
            current_lyrics
        )

        if ok and new_lyrics != current_lyrics:
            cmd = EditLyricsCommand(self.presentation_manager, slide_index, current_lyrics, new_lyrics)
            self.presentation_manager.do_command(cmd)
            # The presentation_changed signal from do_command will update UI.
            # If current slide was edited, it will be re-rendered by update_slide_display_and_selection.
            if self.current_slide_index == slide_index and self.output_window.isVisible():
                self._display_slide(slide_index)

    @Slot(int)
    def handle_delete_slide_requested(self, slide_index: int):
        slides = self.presentation_manager.get_slides()
        if not (0 <= slide_index < len(slides)):
            self.show_error_message(f"Cannot delete slide: Index {slide_index} is invalid.")
            return

        slide_data = slides[slide_index]
        reply = QMessageBox.question(self, 'Delete Slide',
                                     f"Are you sure you want to delete this slide?\n\nLyrics: \"{slide_data.lyrics[:50]}...\"",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            cmd = DeleteSlideCommand(self.presentation_manager, slide_index)
            self.presentation_manager.do_command(cmd)

    @Slot(str)
    def handle_edit_entire_song_requested(self, song_title_to_edit: str):
        """Handles request to edit an entire song (title and all lyrics)."""
        
        current_slides_for_song = [
            s.lyrics for s in self.presentation_manager.get_slides() if s.song_title == song_title_to_edit
        ]

        if not current_slides_for_song:
            self.show_error_message(f"Could not find slides for song: \"{song_title_to_edit}\" to edit.")
            return

        current_full_lyrics = "\n\n".join(current_slides_for_song)

        new_title, ok_title = QInputDialog.getText(
            self,
            "Edit Song Title",
            f"Current title: \"{song_title_to_edit}\"\nEnter new title (leave blank for no title):",
            text=song_title_to_edit
        )

        if not ok_title:
            return # User cancelled title edit

        new_full_lyrics, ok_lyrics = QInputDialog.getMultiLineText(
            self,
            f"Edit Lyrics for \"{new_title or 'Untitled Song'}\"",
            "Modify the lyrics below (use blank lines to separate slides/stanzas):",
            current_full_lyrics
        )

        if ok_lyrics: # User might have pressed OK without changing lyrics, or even deleted all lyrics
            new_stanzas = [s.strip() for s in new_full_lyrics.split('\n\n') if s.strip()]
            # This is a complex operation, potentially multiple commands or a macro command.
            # For now, not making it undoable as a single step.
            self.presentation_manager.update_entire_song(song_title_to_edit, new_title, new_stanzas)

    @Slot(int, str)
    def handle_apply_template_to_slide(self, slide_index: int, template_name: str):
        """Applies a named template to a specific slide."""
        chosen_template_settings = self.template_manager.get_template_settings(template_name)
        if not chosen_template_settings:
            self.show_error_message(f"Template '{template_name}' not found.")
            return
        
        slides = self.presentation_manager.get_slides()
        if not (0 <= slide_index < len(slides)):
            self.show_error_message(f"Cannot apply template: Slide index {slide_index} is invalid.")
            return
        
        old_settings = slides[slide_index].template_settings
        cmd = ApplyTemplateCommand(self.presentation_manager, slide_index, old_settings, chosen_template_settings.copy())
        self.presentation_manager.do_command(cmd)

    @Slot(int)
    def handle_slide_overlay_label_changed(self, slide_index: int, new_label: str):
        """Handles the center_overlay_label_changed signal from a ScaledSlideButton."""
        slides = self.presentation_manager.get_slides()
        if 0 <= slide_index < len(slides):
            # Update the SlideData object directly
            old_label = slides[slide_index].overlay_label
            cmd = ChangeOverlayLabelCommand(self.presentation_manager, slide_index, old_label, new_label)
            self.presentation_manager.do_command(cmd)
            print(f"MainWindow: Overlay label for slide {slide_index} changed to '{new_label}'. Presentation marked dirty.")
    @Slot(int)
    def handle_next_slide_from_menu(self, current_slide_id: int):
        num_slides = len(self.presentation_manager.get_slides())
        if num_slides == 0:
            return

        new_selection_index = current_slide_id + 1
        if new_selection_index >= num_slides: # Wrap to first
            new_selection_index = 0
        
        button_to_select = self.slide_button_group.button(new_selection_index)
        if button_to_select:
            self.setFocus()
            button_to_select.setChecked(True)
            self.scroll_area.ensureWidgetVisible(button_to_select, 50, 50)

    @Slot(int)
    def handle_previous_slide_from_menu(self, current_slide_id: int):
        num_slides = len(self.presentation_manager.get_slides())
        if num_slides == 0:
            return

        new_selection_index = current_slide_id - 1
        if new_selection_index < 0: # Wrap to last
            new_selection_index = num_slides - 1
        
        button_to_select = self.slide_button_group.button(new_selection_index)
        if button_to_select:
            self.setFocus()
            button_to_select.setChecked(True)
            self.scroll_area.ensureWidgetVisible(button_to_select, 50, 50)


    def _display_slide(self, index: int): # Original method starts here
        slides = self.presentation_manager.get_slides()
        if not (0 <= index < len(slides)):
            self._show_blank_on_output()
            return
        if not self.output_window.isVisible():
            return

        slide_data = slides[index]
        try:
            output_pixmap = self.slide_renderer.render_slide(
                slide_data, self.output_resolution.width(), self.output_resolution.height()
            )
            self.output_window.set_pixmap(output_pixmap)
        except Exception as e:
            print(f"Error rendering slide {index} for output: {e}")
            error_slide = SlideData(lyrics=f"Error rendering slide:\n{e}", background_color="#AA0000", template_settings={"color": "#FFFFFF"})
            error_pixmap = self.slide_renderer.render_slide(error_slide, self.output_resolution.width(), self.output_resolution.height())
            self.output_window.set_pixmap(error_pixmap)
            self.show_error_message(f"Error rendering slide {index} (ID: {slide_data.id}): {e}")

    def _show_blank_on_output(self):
        if self.output_window.isVisible():
            blank_slide = SlideData(lyrics="", background_color="#000000")
            blank_pixmap = self.slide_renderer.render_slide(blank_slide, self.output_resolution.width(), self.output_resolution.height())
            self.output_window.set_pixmap(blank_pixmap)

    def show_error_message(self, message: str):
        QMessageBox.critical(self, "Error", message)

    def closeEvent(self, event):
        if self.presentation_manager.is_dirty:
            reply = QMessageBox.question(self, 'Unsaved Changes',
                                         "You have unsaved changes. Do you want to save before exiting?",
                                         QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                                         QMessageBox.Save)
            if reply == QMessageBox.Save:
                if not self.handle_save(): # handle_save calls handle_save_as if needed
                    event.ignore() # Save failed or was cancelled
                    return
            elif reply == QMessageBox.Cancel:
                event.ignore()
                return
        
        self.output_window.close()
        super().closeEvent(event)

    @Slot()
    def on_template_collection_changed(self):
        """
        Called when the TemplateManager signals that the collection of templates has changed.
        This ensures ScaledSlideButtons get the new list of template names for their context menus.
        """
        print("MainWindow: Template collection changed, refreshing slide display.")
        self.update_slide_display_and_selection()

    def eventFilter(self, watched_object, event):
        # This is where key events will go if a child (like a button) doesn't handle them
        # and focus is on the QScrollArea.
        if watched_object == self.scroll_area and event.type() == QEvent.Type.KeyPress:
            # print(f"EventFilter: KeyPress on {watched_object}. Focus: {QApplication.focusWidget()}, Key: {event.key()}") # Can be noisy
            
            if event.isAutoRepeat():
                return True # Consume auto-repeat events for our navigation keys, do nothing

            key = event.key()

            num_slides = len(self.presentation_manager.get_slides())

            if num_slides == 0:
                return super().eventFilter(watched_object, event) # Pass on if no slides

            current_selection_index = self.current_slide_index
            new_selection_index = current_selection_index

            if key == Qt.Key_Right:
                if current_selection_index == -1 and num_slides > 0:
                    new_selection_index = 0
                    print(f"EventFilter ArrowKeyDebug: Right - Was: None, Next: {new_selection_index}")
                elif current_selection_index < num_slides - 1:
                    new_selection_index = current_selection_index + 1
                    print(f"EventFilter ArrowKeyDebug: Right - Was: {current_selection_index}, Next: {new_selection_index}")
                elif current_selection_index == num_slides - 1: # Wrap
                    new_selection_index = 0
                    print(f"EventFilter ArrowKeyDebug: Right - Was: {current_selection_index} (last), Next: {new_selection_index} (wrap)")
                else: # No change in selection logic based on this key, let default happen
                    return super().eventFilter(watched_object, event)
            elif key == Qt.Key_Left:
                if current_selection_index == -1 and num_slides > 0:
                    new_selection_index = num_slides - 1
                    print(f"EventFilter ArrowKeyDebug: Left - Was: None, Next: {new_selection_index}")
                elif current_selection_index > 0:
                    new_selection_index = current_selection_index - 1
                    print(f"EventFilter ArrowKeyDebug: Left - Was: {current_selection_index}, Next: {new_selection_index}")
                elif current_selection_index == 0 and num_slides > 0: # Wrap
                    new_selection_index = num_slides - 1
                    print(f"EventFilter ArrowKeyDebug: Left - Was: {current_selection_index} (first), Next: {new_selection_index} (wrap)")
                else: # No change
                    return super().eventFilter(watched_object, event)
            else:
                # For other keys (like Up/Down for scrolling, Tab), let the scroll area handle them
                return super().eventFilter(watched_object, event)

            if new_selection_index != current_selection_index or \
               (current_selection_index == -1 and new_selection_index != -1): # Ensure selection actually changes or initializes
                button_to_select = self.slide_button_group.button(new_selection_index)
                if button_to_select:
                    print(f"EventFilter: Navigating to slide index {new_selection_index} from {current_selection_index}") # DEBUG
                    
                    # Directly call the method that handles all aspects of slide selection.
                    # This method will update self.current_slide_index, update live output, and set focus.
                    self._on_slide_button_selected_by_index(new_selection_index)
                    
                    # Ensure the button's visual state is checked and QButtonGroup is updated.
                    button_to_select.setChecked(True) # This will trigger _on_slide_button_selected_by_index
                    self.scroll_area.ensureWidgetVisible(button_to_select, 50, 50)
                return True # Event handled

        return super().eventFilter(watched_object, event) # Pass on unhandled events/objects
    def keyPressEvent(self, event):
        num_slides = len(self.presentation_manager.get_slides())
        if num_slides == 0:
            return super().keyPressEvent(event) # No slides, nothing to navigate

        # This method is now a last resort. If arrow keys get here, it means the event filter
        # on the scroll_area.viewport() didn't catch them, which implies focus is
        # directly on the MainWindow or another widget that doesn't filter.
        print(f"MainWindow.keyPressEvent: Key {event.key()} received. Focus: {QApplication.focusWidget()}. THIS IS A FALLBACK.")
        # The event filter on QScrollArea should handle Left/Right.
        super().keyPressEvent(event)
    # handle_active_template_changed method REMOVED

    @Slot()
    def handle_undo(self):
        print("MainWindow: Undo action triggered.")
        self.presentation_manager.undo()

    @Slot()
    def handle_redo(self):
        print("MainWindow: Redo action triggered.")
        self.presentation_manager.redo()

# Example of how to run this if it's the main entry point for testing
# (Your main.py would typically handle this)
if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec())
