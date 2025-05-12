import sys
import os
import json # Needed for saving/loading benchmark history
# import uuid # For generating unique slide IDs for testing - Unused

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QSlider, QMenuBar, # Added QMenuBar
    QMessageBox, QVBoxLayout, QWidget, QPushButton, QInputDialog, # QButtonGroup removed
    QComboBox, QLabel, QHBoxLayout, QSplitter, QScrollArea, QDialog # QButtonGroup removed
) #  QAction removed as it's not directly used
from PySide6.QtGui import QScreen, QPixmap
from PySide6.QtCore import Qt, QSize, Slot, QEvent # Added QEvent

from windows.settings_window import SettingsWindow # Import the new settings window
# --- Local Imports ---
# Make sure these paths are correct relative to where you run main.py
try:
    # Assuming running from the YourProject directory
    from windows.output_window import OutputWindow
    from data_models.slide_data import SlideData # DEFAULT_TEMPLATE is no longer used here
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
    from data_models.slide_data import SlideData # DEFAULT_TEMPLATE is no longer used here
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
import time

# Constants for button previews
# These are now BASE dimensions for calculating scaled preview sizes
BASE_PREVIEW_WIDTH = 160
BASE_PREVIEW_HEIGHT = 90

# Determine project root dynamically for benchmark history file
SCRIPT_DIR_MW = os.path.dirname(os.path.abspath(__file__)) # /windows
PROJECT_ROOT_MW = os.path.dirname(SCRIPT_DIR_MW) # /Plucky
BENCHMARK_TEMP_DIR_MW = os.path.join(PROJECT_ROOT_MW, "temp")
BENCHMARK_HISTORY_FILE_PATH_MW = os.path.join(BENCHMARK_TEMP_DIR_MW, ".pluckybenches.json")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        mw_init_start_time = time.perf_counter()
        self.mw_init_end_time = 0.0 # Will be set at the end of __init__

        self.setWindowTitle("Plucky Presentation")
        self.setGeometry(100, 100, 900, 700) # Adjusted size for more controls
        self.setMenuBar(self.create_menu_bar())

        # MainWindow can have focus, but scroll_area is more important for this.
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus) 

        # Initialize benchmark data store as an instance attribute
        # This will hold current session data + loaded history for the last presentation
        self.benchmark_data_store = {
            "app_init": 0.0,  # Time from app start until MainWindow is shown (calculated in showEvent)
            "mw_init": 0.0,   # Time for MainWindow.__init__ (calculated at end of __init__)
            "mw_show": 0.0,   # Time from MainWindow.__init__ end until it's shown (calculated in showEvent)
            "last_presentation_path": "None",
            "last_presentation_pm_load": 0.0,
            "last_presentation_ui_update": 0.0,
            "last_presentation_render_total": 0.0,
            "last_presentation_render_images": 0.0,
            "last_presentation_render_fonts": 0.0,
            "last_presentation_render_layout": 0.0,
            "last_presentation_render_draw": 0.0,
        }
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
        self.slide_buttons_list = [] # List to store ScaledSlideButton instances


        # --- UI Elements ---
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        # Top controls: Live button (Monitor selection moved to settings)
        self.go_live_button = QPushButton("Go Live")

        # Top controls: Undo/Redo (File ops moved to menu)
        self.undo_button = QPushButton("Undo") # New
        self.redo_button = QPushButton("Redo") # New

        # Edit Template button
        self.edit_template_button = QPushButton("Edit Templates")
        self.edit_template_button.setEnabled(True) # Re-enabled
        self.edit_template_button.setToolTip("Open the template editor.") # Updated tooltip

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

        # Monitor layout is removed as Go Live button is moved

        # File operations layout
        file_ops_layout = QHBoxLayout()
        file_ops_layout.addStretch(1) # Stretch to push buttons to the right
        file_ops_layout.addWidget(self.go_live_button) # Add Go Live button here
        file_ops_layout.addWidget(self.edit_template_button)
        # Keep Undo/Redo buttons on the main UI
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

        # --- Connections ---
        # Connections for load, save, save_as, add_song are now handled by menu actions
        self.edit_template_button.clicked.connect(self.handle_edit_template) # Connect signal
        self.undo_button.clicked.connect(self.handle_undo) # New
        self.redo_button.clicked.connect(self.handle_redo) # New
        self.button_size_slider.sliderReleased.connect(self.handle_button_size_change) # Changed signal

        self.go_live_button.clicked.connect(self.toggle_live)

        self.update_slide_display_and_selection() # Initial setup of slide display
        
        # Install event filter directly on the QScrollArea.
        self.scroll_area.installEventFilter(self)
        # Ensure QScrollArea can receive focus.
        self.scroll_area.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Store initial app benchmark data
        app_start_time = QApplication.instance().property("app_start_time")
        # Store app_start_time (timestamp) temporarily for calculation in showEvent
        self._app_start_time = app_start_time 

        mw_init_duration = time.perf_counter() - mw_init_start_time
        self.benchmark_data_store["mw_init"] = mw_init_duration
        self.mw_init_end_time = time.perf_counter() # Store for calculating mw_show in showEvent

        if app_start_time is not None: # Check if it was set
            # app_init and mw_show will be calculated and printed in showEvent, using self._app_start_time
            pass 
        else:
            print(f"[BENCHMARK] MainWindow.__init__ took: {self.benchmark_data_store['mw_init']:.4f} seconds (app_start_time not found)")
            
    def toggle_live(self):
        # The selected screen is now managed by SettingsWindow and communicated via a signal
        # For now, we'll assume self.output_window.screen() holds the target if set.
        # A more robust way would be to store the QScreen object selected from settings.
        target_screen = getattr(self, '_target_output_screen', None)

        if not target_screen and not self.output_window.isVisible(): # Only warn if trying to go live without selection
            QMessageBox.warning(self, "No Monitor Selected", "Please select a monitor to go live.")
            return

        if self.output_window.isVisible():
            self.go_live_button.setText("Go Live")
            self.go_live_button.setStyleSheet("")
            self._show_blank_on_output() # Good practice to blank it before hiding
            self.output_window.hide() # Explicitly hide the window
        else:
            if not target_screen: return # Should have been caught above
            self.go_live_button.setText("LIVE")
            self.go_live_button.setStyleSheet("background-color: red; color: white; font-weight: bold;")
            output_geometry = target_screen.geometry()
            self.output_resolution = output_geometry.size()
            self.output_window.setGeometry(output_geometry)
            self.output_window.showFullScreen()
            if 0 <= self.current_slide_index < len(self.presentation_manager.get_slides()):
                self._display_slide(self.current_slide_index)
            else:
                self._show_blank_on_output()

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
                # New songs will use the resolved "Default Master" template
                default_master_settings_for_song = self.template_manager.resolve_master_template_for_primary_text_box("Default Master")
                if not default_master_settings_for_song:
                    print("Warning: Could not resolve 'Default Master' template settings. Using empty settings for new song slide.")
                    default_master_settings_for_song = {}

                new_slide = SlideData(lyrics=stanza_lyrics, 
                                      song_title=cleaned_song_title,
                                      overlay_label="", # Default for new song slides
                                      template_settings=default_master_settings_for_song)
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
            # Reset presentation-specific benchmarks before loading
            self.benchmark_data_store["last_presentation_path"] = filepath
            self.benchmark_data_store["last_presentation_pm_load"] = 0.0
            self.benchmark_data_store["last_presentation_ui_update"] = 0.0
            self.benchmark_data_store["last_presentation_render_total"] = 0.0
            self.benchmark_data_store["last_presentation_render_images"] = 0.0
            self.benchmark_data_store["last_presentation_render_fonts"] = 0.0
            self.benchmark_data_store["last_presentation_render_layout"] = 0.0
            self.benchmark_data_store["last_presentation_render_draw"] = 0.0

            load_pm_start_time = time.perf_counter()
            self.presentation_manager.load_presentation(filepath)
            load_pm_duration = time.perf_counter() - load_pm_start_time
            self.benchmark_data_store["last_presentation_pm_load"] = load_pm_duration
            print(f"[BENCHMARK] PresentationManager.load_presentation() took: {load_pm_duration:.4f} seconds for {filepath}")
            # After UI update (triggered by presentation_changed), explicitly mark as not dirty
            # The actual UI update (update_slide_display_and_selection) will be benchmarked separately as it's triggered by a signal.
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
        # Connect the editor's save request signal to a handler in MainWindow
        editor.templates_save_requested.connect(self._handle_editor_save_request)
        
        if editor.exec() == QDialog.DialogCode.Accepted:
            updated_templates_collection = editor.get_updated_templates()
            self.template_manager.update_from_collection(updated_templates_collection)
            # The templates_changed signal from TemplateManager will call on_template_collection_changed
            # which in turn calls update_slide_display_and_selection to refresh UI.
        else:
            # If the user cancels, we might want to reload the templates from the manager
            # to discard any un-OK'd changes if they didn't use the intermediate "Save" button.
            # This depends on how "dirty" state is managed within TemplateEditorWindow itself.
            # For now, we'll assume TemplateManager holds the last saved state.
            # If the editor was complex and had its own dirty tracking, you might reload here.
            print("Template editor was cancelled.")

    @Slot()
    def _handle_manual_slide_selection(self, selected_slide_id: int):
        """
        Manages exclusive selection of ScaledSlideButtons and updates UI.
        This is connected to ScaledSlideButton.slide_selected signal.
        """
        print(f"MainWindow: _handle_manual_slide_selection for slide_id {selected_slide_id}")
        
        clicked_button_widget = None
        for button_widget in self.slide_buttons_list:
            if button_widget._slide_id == selected_slide_id:
                if not button_widget.isChecked(): # Ensure it's checked
                    button_widget.setChecked(True)
                clicked_button_widget = button_widget
            else:
                if button_widget.isChecked(): # Uncheck others
                    button_widget.setChecked(False)

        if clicked_button_widget:
            self.current_slide_index = selected_slide_id # Update our tracking variable
            if self.output_window.isVisible():
                self._display_slide(selected_slide_id)
            self.scroll_area.setFocus() # Important for keyboard navigation
            print(f"MainWindow: UI updated for slide {selected_slide_id}. Focus on scroll_area.")

    @Slot()
    def update_slide_display_and_selection(self):
        """
        Clears and repopulates slide buttons. Manages selection.
        Called when presentation_manager.presentation_changed is emitted.
        """
        print("MainWindow: update_slide_display_and_selection called")
        ui_update_start_time = time.perf_counter()
        
        # Initialize accumulators for detailed render timings
        total_aggregated_render_time = 0.0
        total_aggregated_image_time = 0.0
        total_aggregated_font_time = 0.0
        total_aggregated_layout_time = 0.0
        total_aggregated_draw_time = 0.0

        # --- 1. Rebuild Slide Buttons ---
        # ... (rest of the method remains the same)
        old_selected_slide_index = self.current_slide_index # Preserve current selection if possible
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
                            # No need to remove from QButtonGroup as we are not using it for these
                            # Disconnect signals if they were connected
                            try:
                                slide_button_widget.slide_selected.disconnect(self._handle_manual_slide_selection)
                            except (TypeError, RuntimeError): pass # If not connected or already gone
                            # Child widgets of widget_in_vbox will be deleted when widget_in_vbox is deleted
                            # No need to call deleteLater on slide_button_widget explicitly here
                            # as long as it's properly parented to widget_in_vbox or its layout.
                
                # For SongHeaderWidget, QLabel, or the container QWidget itself
                widget_in_vbox.setParent(None)
                widget_in_vbox.deleteLater()
        self.slide_buttons_list.clear() # Clear our manual list

        slides = self.presentation_manager.get_slides()

        if not slides:
            no_slides_label = QLabel("No slides. Use 'Load' or 'Add Song'.")
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
                # render_slide now returns (pixmap, has_font_error)
                full_res_pixmap, has_font_error, slide_benchmarks = self.slide_renderer.render_slide(
                    slide_data, preview_render_width, preview_render_height
                )
                # print(f"      Full-res pixmap for slide {index}: isNull={full_res_pixmap.isNull()}, size={full_res_pixmap.size()}") # DEBUG
                
                # Accumulate benchmark data
                total_aggregated_render_time += slide_benchmarks.get("total_render", 0.0)
                total_aggregated_image_time += slide_benchmarks.get("images", 0.0)
                total_aggregated_font_time += slide_benchmarks.get("fonts", 0.0)
                total_aggregated_layout_time += slide_benchmarks.get("layout", 0.0)
                total_aggregated_draw_time += slide_benchmarks.get("draw", 0.0)
                
                preview_pixmap = full_res_pixmap.scaled(current_dynamic_preview_width, current_dynamic_preview_height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                # print(f"      Preview pixmap for slide {index}: isNull={preview_pixmap.isNull()}, size={preview_pixmap.size()}") # DEBUG
            except TypeError as te: # Catch if render_slide doesn't return 3 values
                print(f"      ERROR unpacking render_slide result for slide {index} (ID {slide_data.id}): {te}. Assuming old renderer.")
                # Fallback to old behavior if render_slide only returns 2 values
                full_res_pixmap, has_font_error = self.slide_renderer.render_slide(
                    slide_data, preview_render_width, preview_render_height
                )
                preview_pixmap = full_res_pixmap.scaled(current_dynamic_preview_width, current_dynamic_preview_height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            except Exception as e: # Catch general rendering exceptions
                print(f"      ERROR rendering preview for slide {index} (ID {slide_data.id}): {e}")
                has_font_error = True # Treat general rendering errors as something to flag
                preview_pixmap = QPixmap(current_dynamic_preview_width, current_dynamic_preview_height) # Use dynamic size for placeholder
                preview_pixmap.fill(Qt.darkGray) # Corrected to Qt.darkGray
                # print(f"      Filled preview pixmap with darkGray due to error for slide {index}.") # DEBUG

            button = ScaledSlideButton(slide_id=index) # No longer needs scale_factor
            button.set_pixmap(preview_pixmap)
            # Set the slide number and label for the banner
            # Pass an empty string for the label if you only want the number
            button.set_slide_info(number=index + 1, label="")

            # print(f"      Set pixmap for button {index}.") # DEBUG

            button.setToolTip(f"Slide {index + 1}: {slide_data.lyrics.splitlines()[0] if slide_data.lyrics else 'Empty'}")
            button.slide_selected.connect(self._handle_manual_slide_selection) # Connect to our new manual handler
            button.edit_requested.connect(self.handle_edit_slide_requested)
            button.delete_requested.connect(self.handle_delete_slide_requested)
            button.set_available_templates(self.template_manager.get_master_template_names()) # Pass master template names
            button.apply_template_to_slide_requested.connect(self.handle_apply_template_to_slide)
            button.next_slide_requested_from_menu.connect(self.handle_next_slide_from_menu)
            button.previous_slide_requested_from_menu.connect(self.handle_previous_slide_from_menu)
            button.center_overlay_label_changed.connect(self.handle_slide_overlay_label_changed) # New connection

            if has_font_error:
                button.set_icon_state("error", True)
            
            if current_song_flow_layout: # Add button to the current song's FlowLayout
                current_song_flow_layout.addWidget(button)
            # self.slide_button_group.addButton(button, index) # DO NOT ADD TO QButtonGroup
            self.slide_buttons_list.append(button) # Add to our manual list
        
        # Add a stretch at the end of the main QVBoxLayout to push everything up
        self.slide_buttons_layout.addStretch(1)

        # After creating all buttons, set their overlay labels from SlideData
        self._update_all_button_overlay_labels()
        
        # --- 2. Manage Selection ---
        num_slides = len(slides)
        new_selection_target_index = old_selected_slide_index

        if new_selection_target_index >= num_slides: # If old selection is now out of bounds
            new_selection_target_index = num_slides - 1 if num_slides > 0 else -1
        
        if new_selection_target_index != -1:
            # Find the button in our list
            button_to_select = next((btn for btn in self.slide_buttons_list if btn._slide_id == new_selection_target_index), None)
            if button_to_select: # If found
                # Trigger our manual selection handler. It will check the button and uncheck others.
                self._handle_manual_slide_selection(new_selection_target_index)
                # Ensure it's visible
                self.scroll_area.ensureWidgetVisible(button_to_select, 50, 50)
            else: # Button for the target index not found (should not happen if list is consistent)
                self.current_slide_index = -1
                self._show_blank_on_output()
        elif num_slides > 0: # No previous selection, but slides exist, select the first one
            self._handle_manual_slide_selection(0) # Select the first slide (ID 0)
            if self.slide_buttons_list:
                 self.scroll_area.ensureWidgetVisible(self.slide_buttons_list[0], 50, 50)
        else: # No slides, no selection
            self.current_slide_index = -1
            self._show_blank_on_output()
        
        ui_update_duration = time.perf_counter() - ui_update_start_time
        # Store the UI update and aggregated render times in the global benchmark data
        self.benchmark_data_store["last_presentation_ui_update"] = ui_update_duration
        self.benchmark_data_store["last_presentation_render_total"] = total_aggregated_render_time
        self.benchmark_data_store["last_presentation_render_images"] = total_aggregated_image_time
        self.benchmark_data_store["last_presentation_render_fonts"] = total_aggregated_font_time
        self.benchmark_data_store["last_presentation_render_layout"] = total_aggregated_layout_time
        self.benchmark_data_store["last_presentation_render_draw"] = total_aggregated_draw_time

        print(f"[BENCHMARK] update_slide_display_and_selection() took: {ui_update_duration:.4f} seconds for {len(slides)} slides.")
        if slides: # Only print aggregated if there were slides to render
            print(f"  [BENCHMARK_AGGREGATE] Total time spent in SlideRenderer (all previews):")
            print(f"    Overall Render: {total_aggregated_render_time:.4f}s")
            print(f"    Image Processing: {total_aggregated_image_time:.4f}s")
            print(f"    Font Setup:     {total_aggregated_font_time:.4f}s")
            print(f"    Text Layout:    {total_aggregated_layout_time:.4f}s")
            print(f"    Text Drawing:   {total_aggregated_draw_time:.4f}s")


    def _update_all_button_overlay_labels(self):
        """Sets the overlay label on each button based on its corresponding SlideData."""
        slides = self.presentation_manager.get_slides()
        for index, slide_data in enumerate(slides):
            # Find button in our list
            button = next((btn for btn in self.slide_buttons_list if btn._slide_id == index), None)
            if button and isinstance(button, ScaledSlideButton):
                # Pass the overlay_label from SlideData to the button
                button.set_center_overlay_label(slide_data.overlay_label, emit_signal_on_change=False)

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
        # 'template_name' here refers to a Master Template name.
        # We need to resolve it to get the flat settings for SlideData.template_settings (interim step)
        chosen_template_settings = self.template_manager.resolve_master_template_for_primary_text_box(template_name)
        
        if not chosen_template_settings:
            self.show_error_message(f"Could not resolve Master Template '{template_name}'.")
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
        
        # Find button in our list
        button_to_select = next((btn for btn in self.slide_buttons_list if btn._slide_id == new_selection_index), None)
        if button_to_select:
            # Trigger the full selection logic
            self._handle_manual_slide_selection(new_selection_index)
            self.scroll_area.ensureWidgetVisible(button_to_select, 50, 50) # Ensure visibility

    @Slot(int)
    def handle_previous_slide_from_menu(self, current_slide_id: int):
        num_slides = len(self.presentation_manager.get_slides())
        if num_slides == 0:
            return

        new_selection_index = current_slide_id - 1
        if new_selection_index < 0: # Wrap to last
            new_selection_index = num_slides - 1
        
        # Find button in our list
        button_to_select = next((btn for btn in self.slide_buttons_list if btn._slide_id == new_selection_index), None)
        if button_to_select:
            # Trigger the full selection logic
            self._handle_manual_slide_selection(new_selection_index)
            self.scroll_area.ensureWidgetVisible(button_to_select, 50, 50) # Ensure visibility


    def _display_slide(self, index: int): # Original method starts here
        slides = self.presentation_manager.get_slides()
        if not (0 <= index < len(slides)):
            self._show_blank_on_output()
            return
        if not self.output_window.isVisible():
            return

        render_output_start_time = time.perf_counter()
        slide_data = slides[index]
        try:
            # render_slide now returns (pixmap, has_font_error)
            # For live output, we don't aggregate these individual timings here, but still need to unpack.
            render_result = self.slide_renderer.render_slide(
                 slide_data, self.output_resolution.width(), self.output_resolution.height()
            )
            if len(render_result) == 3: # New renderer with benchmarks
                output_pixmap, has_font_error_on_output, _ = render_result
            else: # Old renderer
                output_pixmap, has_font_error_on_output = render_result
            
            if not output_pixmap.isNull():
                self.output_window.set_pixmap(output_pixmap)
            
            # We don't directly use has_font_error_on_output here, but it's good practice
            # The button icon should already reflect this from the preview rendering.
        except Exception as e:
            print(f"Error rendering slide {index} (ID: {slide_data.id}) for output: {e}")
            error_slide = SlideData(lyrics=f"Error rendering slide:\n{e}", background_color="#AA0000", template_settings={"color": "#FFFFFF"})
            # Render error slide, ignore its font error status for this specific display
            error_pixmap, _ = self.slide_renderer.render_slide(error_slide, self.output_resolution.width(), self.output_resolution.height())
            if len(render_result) == 3: # New renderer with benchmarks
                error_pixmap, _, _ = self.slide_renderer.render_slide(error_slide, self.output_resolution.width(), self.output_resolution.height())
            else: # Old renderer
                error_pixmap, _ = self.slide_renderer.render_slide(error_slide, self.output_resolution.width(), self.output_resolution.height())
            if not error_pixmap.isNull():
                self.output_window.set_pixmap(error_pixmap)
            self.show_error_message(f"Error rendering slide {index} (ID: {slide_data.id}): {e}")
        render_output_duration = time.perf_counter() - render_output_start_time
        print(f"[BENCHMARK] _display_slide() for output took: {render_output_duration:.4f} seconds for slide {index}")

    def _show_blank_on_output(self):
        if self.output_window.isVisible():
            blank_slide = SlideData(lyrics="", background_color="#000000")
            # Render blank slide, ignore its font error status and benchmarks
            render_result = self.slide_renderer.render_slide(blank_slide, self.output_resolution.width(), self.output_resolution.height())
            if len(render_result) == 3: # New renderer
                blank_pixmap, _, _ = render_result
            else: # Old renderer
                blank_pixmap, _ = render_result
            
            if not blank_pixmap.isNull():
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
        self._save_benchmark_history() # Save benchmark history on close
        super().closeEvent(event)

    def showEvent(self, event):
        """Override showEvent to capture benchmark timings when the window is actually shown."""
        # Calculate app_init and mw_show times when the window is first shown
        if self._app_start_time is not None:
            app_start_time = self._app_start_time
            self.benchmark_data_store['app_init'] = time.perf_counter() - app_start_time
            self.benchmark_data_store['mw_show'] = time.perf_counter() - self.mw_init_end_time # Time from end of __init__ to show
            print(f"[BENCHMARK] Application ready (MainWindow.showEvent): {self.benchmark_data_store['app_init']:.4f}s")
            print(f"[BENCHMARK] MainWindow show (from init end to showEvent): {self.benchmark_data_store['mw_show']:.4f}s")
            self._app_start_time = None # Clear temporary storage
        
        # Load benchmark history when the window is shown
        self._load_benchmark_history()

        # Set a default target output screen if none is set yet
        if not hasattr(self, '_target_output_screen') or self._target_output_screen is None:
            screens = QApplication.screens()
            if screens:
                # Prefer primary screen if available
                primary_screen = QApplication.primaryScreen()
                if primary_screen and primary_screen in screens: # Check if primary_screen is not None
                    self._target_output_screen = primary_screen
                else:
                    self._target_output_screen = screens[0] # Fallback to first screen
                print(f"MainWindow: Defaulted target output screen to {self._target_output_screen.name()}")
            else:
                self._target_output_screen = None # Explicitly None if no screens
                print("MainWindow: No screens found to set a default output target.")

        super().showEvent(event)

    def _save_benchmark_history(self):
        """Saves the last presentation benchmark data to a file."""
        data_to_save = {key: self.benchmark_data_store[key] for key in self.benchmark_data_store if key.startswith("last_presentation_")}
        try:
            os.makedirs(BENCHMARK_TEMP_DIR_MW, exist_ok=True) # Ensure the temp directory exists
            with open(BENCHMARK_HISTORY_FILE_PATH_MW, 'w') as f:
                json.dump(data_to_save, f, indent=4)
            print(f"Saved benchmark history to {BENCHMARK_HISTORY_FILE_PATH_MW}")
        except IOError as e:
            print(f"Error saving benchmark history to {BENCHMARK_HISTORY_FILE_PATH_MW}: {e}")
        except Exception as e:
            print(f"Unexpected error saving benchmark history: {e}")

    def _load_benchmark_history(self):
        """Loads the last presentation benchmark data from a file."""
        if os.path.exists(BENCHMARK_HISTORY_FILE_PATH_MW):
            try:
                with open(BENCHMARK_HISTORY_FILE_PATH_MW, 'r') as f:
                    loaded_data = json.load(f)
                if not isinstance(loaded_data, dict): # Basic validation
                    print(f"Error: Benchmark history file {BENCHMARK_HISTORY_FILE_PATH_MW} does not contain a valid dictionary.")
                    return
                # Update only the relevant keys in the current store
                for key, value in loaded_data.items():
                    if key in self.benchmark_data_store:
                        self.benchmark_data_store[key] = value
                print(f"Loaded benchmark history from {BENCHMARK_HISTORY_FILE_PATH_MW}")
            except (IOError, json.JSONDecodeError) as e:
                print(f"Error loading benchmark history from {BENCHMARK_HISTORY_FILE_PATH_MW}: {e}")
            except Exception as e: # Catch any other unexpected errors during loading/processing
                 print(f"Unexpected error loading benchmark history: {e}")
        else:
            print(f"Benchmark history file not found: {BENCHMARK_HISTORY_FILE_PATH_MW}")

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
                # If current_slide_index is -1, it means no slide is selected.
                if current_selection_index == -1 and num_slides > 0: # If nothing selected, select last
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
                # Find button in our list
                button_to_select = next((btn for btn in self.slide_buttons_list if btn._slide_id == new_selection_index), None)
                if button_to_select:
                    print(f"EventFilter: Navigating to slide index {new_selection_index} from {current_selection_index}") # DEBUG
                    
                    # Directly call the method that handles all aspects of slide selection.
                    self._handle_manual_slide_selection(new_selection_index)
                    # The handler above already calls setChecked(True) on the target button.
                    self.scroll_area.ensureWidgetVisible(button_to_select, 50, 50)
                return True # Event handled

        return super().eventFilter(watched_object, event) # Pass on unhandled events/objects
    
    def create_menu_bar(self):
        menu_bar = QMenuBar(self)
        
        # File Menu
        file_menu = menu_bar.addMenu("File")
        load_action = file_menu.addAction("Load")
        load_action.triggered.connect(self.handle_load)
        save_action = file_menu.addAction("Save")
        save_action.triggered.connect(self.handle_save)
        save_as_action = file_menu.addAction("Save As...")
        save_as_action.triggered.connect(self.handle_save_as)
        
        new_action = file_menu.addAction("New")
        new_action.triggered.connect(self.handle_new)
        # Edit Menu
        edit_menu = menu_bar.addMenu("Edit")
        undo_action = edit_menu.addAction("Undo")
        undo_action.triggered.connect(self.handle_undo)
        undo_action.setShortcut("Ctrl+Z") # Add standard shortcut
        redo_action = edit_menu.addAction("Redo")
        redo_action.triggered.connect(self.handle_redo)
        
        # Presentation Menu
        presentation_menu = menu_bar.addMenu("Presentation")
        go_live_action = presentation_menu.addAction("Go Live")
        go_live_action.triggered.connect(self.toggle_live)
        
        add_song_action = presentation_menu.addAction("Add Song")
        add_song_action.triggered.connect(self.handle_add_song)
        # Keep it disabled as in the toolbar
        add_song_action.setEnabled(False)
        add_song_action.setToolTip("Temporarily disabled pending multi-textbox feature.")

        # Settings Menu (New)
        settings_menu = menu_bar.addMenu("Settings")
        open_settings_action = settings_menu.addAction("Open Settings...")
        open_settings_action.triggered.connect(self.handle_open_settings)

        return menu_bar
    def handle_new(self):
        """
        Starts a new presentation.  If there are unsaved changes, prompts the user to save.
        """
        if self.presentation_manager.is_dirty:
            reply = QMessageBox.question(self, 'Unsaved Changes',
                                         "You have unsaved changes. Save before starting a new presentation?",
                                         QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            if reply == QMessageBox.Save:
                if not self.handle_save():  # If save fails or is cancelled
                    return
            elif reply == QMessageBox.Cancel:
                return

        # Clear the current presentation (or load a blank one)
        self.presentation_manager.clear_presentation()
        # Reset the window title to reflect a new, unsaved presentation
        self.setWindowTitle("Plucky Presentation - New Presentation")
        # If you wish to force a save immediately to a new file you could do the following (uncomment).
        # But I do not recommend forcing it. Let the user decide when to save:

        # if not self.handle_save_as():
        #     # Optionally, warn the user if even the 'Save As...' was cancelled.
        #     QMessageBox.warning(self, "Action Cancelled", "New presentation cancelled.")

        # The event filter on QScrollArea should handle Left/Right.
        #super().keyPressEvent(event)

    @Slot()
    def handle_undo(self):
        print("MainWindow: Undo action triggered.")
        self.presentation_manager.undo()

    @Slot()
    def handle_redo(self):
        print("MainWindow: Redo action triggered.")
        self.presentation_manager.redo()
        
    @Slot()
    def handle_open_settings(self):
        """Opens the settings dialog."""
        current_target_screen = getattr(self, '_target_output_screen', None)
        settings_dialog = SettingsWindow(
            benchmark_data=self.benchmark_data_store,
            current_output_screen=current_target_screen,
            parent=self
        )
        settings_dialog.output_monitor_changed.connect(self._handle_settings_monitor_changed)
        settings_dialog.exec() # Use exec() for modal dialog
        # Disconnect after use to prevent issues if dialog is reopened or multiple instances exist
        settings_dialog.output_monitor_changed.disconnect(self._handle_settings_monitor_changed)

    @Slot(dict)
    def _handle_editor_save_request(self, templates_collection: dict):
        """
        Handles the templates_save_requested signal from the TemplateEditorWindow.
        This allows saving templates without closing the editor.
        """
        print(f"MainWindow: Received save request from template editor with data: {templates_collection.keys()}")
        self.template_manager.update_from_collection(templates_collection)
        # Optionally, provide feedback to the user, e.g., via a status bar or a brief message.
        # For now, the print statement and the TemplateManager's own save confirmation (if any) will suffice.

    @Slot(QScreen)
    def _handle_settings_monitor_changed(self, selected_screen: QScreen):
        """Handles the output_monitor_changed signal from the SettingsWindow."""
        self._target_output_screen = selected_screen # Store the selected screen
        print(f"MainWindow: Target output monitor updated to {selected_screen.name()} via settings.")
        # If already live, you might want to move the output window, or just apply on next "Go Live"

# Example of how to run this if it's the main entry point for testing
# (Your main.py would typically handle this)
if __name__ == '__main__': # This block is for direct testing of MainWindow
    # Simulate what main.py does for benchmarks
    app_start_time_for_mw_test = time.perf_counter()
    app = QApplication(sys.argv)
    QApplication.instance().setProperty("app_start_time", app_start_time_for_mw_test)

    main_win = MainWindow()
    main_win.show()

    app_ready_duration_for_mw_test = time.perf_counter() - app_start_time_for_mw_test
    print(f"[BENCHMARK_MW_TEST] Application ready (after show) took: {app_ready_duration_for_mw_test:.4f} seconds")
    sys.exit(app.exec())
