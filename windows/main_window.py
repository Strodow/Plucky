import sys
import os
import uuid # For generating unique slide IDs for testing

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog,
    QMessageBox, QVBoxLayout, QWidget, QPushButton, QInputDialog,
    QComboBox, QLabel, QHBoxLayout, QSplitter, QScrollArea, QButtonGroup
)
from PySide6.QtGui import QScreen, QPixmap # QFont, QColor removed as not directly used here
from PySide6.QtCore import Qt, QSize, Slot

# --- Local Imports ---
# Make sure these paths are correct relative to where you run main.py
try:
    # Assuming running from the YourProject directory
    from windows.output_window import OutputWindow
    from data_models.slide_data import SlideData # DEFAULT_TEMPLATE not directly used here
    from rendering.slide_renderer import SlideRenderer
    from widgets.scaled_slide_button import ScaledSlideButton # This should already be there
    from widgets.song_header_widget import SongHeaderWidget # Import the new header widget
    from widgets.flow_layout import FlowLayout # Import the new FlowLayout
    from core.presentation_manager import PresentationManager
except ImportError:
    # Fallback if running directly from the windows directory (adjust as needed)
    # import sys, os # Already imported at top level
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from windows.output_window import OutputWindow
    from data_models.slide_data import SlideData
    from rendering.slide_renderer import SlideRenderer
    from widgets.scaled_slide_button import ScaledSlideButton # This should already be there
    from widgets.song_header_widget import SongHeaderWidget # Import the new header widget
    from widgets.flow_layout import FlowLayout # Import the new FlowLayout
    from core.presentation_manager import PresentationManager

# Constants for button previews
PREVIEW_WIDTH = 160
PREVIEW_HEIGHT = 90

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Plucky Presentation")
        self.setGeometry(100, 100, 900, 700) # Adjusted size for more controls

        # --- Core Components ---
        self.output_window = OutputWindow()
        self.slide_renderer = SlideRenderer()
        self.presentation_manager = PresentationManager()
        self.presentation_manager.presentation_changed.connect(self.update_slide_display_and_selection)
        self.presentation_manager.error_occurred.connect(self.show_error_message)

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
        file_ops_layout.addWidget(self.clear_button)
        left_layout.addLayout(file_ops_layout)
        
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

        self.refresh_monitors_button.clicked.connect(self.refresh_monitors)
        self.go_live_button.clicked.connect(self.toggle_live)
        # self.slide_button_group.buttonClicked[int].connect(self._on_slide_button_selected_by_index) # Alternative

        self.update_slide_display_and_selection() # Initial setup of slide display

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
            self._show_blank_on_output() # Show blank instead of hiding
            # self.output_window.hide() # Alternative: actually hide
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
        )
        self.presentation_manager.add_slide(new_slide)
        # presentation_changed signal will call update_slide_display_and_selection

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
                new_slide = SlideData(lyrics=stanza_lyrics, song_title=cleaned_song_title)
                new_slides_data.append(new_slide)
            self.presentation_manager.add_slides(new_slides_data) # Add all at once

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
            # presentation_changed signal handles UI update

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
            # Create a method in PresentationManager for this
            self.presentation_manager.slides.clear() 
            self.presentation_manager.is_dirty = True # Or False if cleared means "saved empty"
            self.presentation_manager.presentation_changed.emit()

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

        for index, slide_data in enumerate(slides):
            current_title = slide_data.song_title # This can be None or a string

            if current_title != last_processed_title:
                # This is a new song, or a transition to/from an untitled block of slides
                last_processed_title = current_title

                if current_title is not None: # It's a titled song
                    song_header = SongHeaderWidget(current_title)
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
            print(f"    Processing slide {index}, ID: {slide_data.id}, Lyrics: '{slide_data.lyrics[:30].replace('\n', ' ')}...'")
            # (Ensure current_song_flow_layout is valid before adding buttons to it)
            preview_render_width = self.output_resolution.width() if self.output_window.isVisible() else 1920
            preview_render_height = self.output_resolution.height() if self.output_window.isVisible() else 1080
            
            try:
                full_res_pixmap = self.slide_renderer.render_slide(slide_data, preview_render_width, preview_render_height)
                print(f"      Full-res pixmap for slide {index}: isNull={full_res_pixmap.isNull()}, size={full_res_pixmap.size()}")
                if full_res_pixmap.isNull():
                    print(f"      WARNING: Full-res pixmap is NULL for slide {index}. Renderer might have failed silently.")
                
                preview_pixmap = full_res_pixmap.scaled(PREVIEW_WIDTH, PREVIEW_HEIGHT, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                print(f"      Preview pixmap for slide {index}: isNull={preview_pixmap.isNull()}, size={preview_pixmap.size()}")
            except Exception as e:
                print(f"      ERROR rendering preview for slide {index} (ID {slide_data.id}): {e}")
                preview_pixmap = QPixmap(PREVIEW_WIDTH, PREVIEW_HEIGHT)
                preview_pixmap.fill(Qt.darkGray) # Corrected to Qt.darkGray
                print(f"      Filled preview pixmap with darkGray due to error for slide {index}.")

            button = ScaledSlideButton(slide_id=index) # Use index for QButtonGroup
            button.set_pixmap(preview_pixmap)
            print(f"      Set pixmap for button {index}.")
            # button.setFixedSize(PREVIEW_WIDTH + 10, PREVIEW_HEIGHT + 10) # Padding
            button.setToolTip(f"Slide {index + 1}: {slide_data.lyrics.splitlines()[0] if slide_data.lyrics else 'Empty'}")
            button.slide_selected.connect(self._on_slide_button_selected_by_index) # Connect to new slot
            
            if current_song_flow_layout: # Add button to the current song's FlowLayout
                current_song_flow_layout.addWidget(button)
            self.slide_button_group.addButton(button, index)
        
        # Add a stretch at the end of the main QVBoxLayout to push everything up
        self.slide_buttons_layout.addStretch(1)
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

    @Slot(int) # Receives slide_id (which is the index)
    def _on_slide_button_selected_by_index(self, slide_index: int):
        """Handles a slide button being clicked or programmatically selected."""
        slides = self.presentation_manager.get_slides()
        if 0 <= slide_index < len(slides):
            self.current_slide_index = slide_index
            print(f"Slide {slide_index} selected by button click/check.")
            if self.output_window.isVisible():
                self._display_slide(slide_index)
        else:
            print(f"Warning: Invalid slide index {slide_index} from button selection.")
            self.current_slide_index = -1
            self._show_blank_on_output()

    def _display_slide(self, index: int):
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

# Example of how to run this if it's the main entry point for testing
# (Your main.py would typically handle this)
if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec())
