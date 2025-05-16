import sys
import os
import time

# Ensure the main project directory is in the Python path
# This helps ensure that imports like 'from windows.main_window import MainWindow' work correctly
# regardless of how the script is run (e.g., from the project root or a subdirectory).
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from PySide6.QtWidgets import QApplication # QMessageBox no longer needed here
from PySide6.QtGui import QIcon, QImage, QColor # Import QIcon, QImage, QColor for example

# Import the main window class
from windows.main_window import MainWindow

# Import our new DeckLink handler
import decklink_handler 


if __name__ == "__main__":
    app_start_time = time.perf_counter()
    app = QApplication(sys.argv)
    app_icon_object = None # To store the QIcon object

    # Set the application icon
    # The 'project_root' is already defined as os.path.dirname(os.path.abspath(__file__))
    # which is c:\Users\Logan\Documents\Plucky\Plucky
    icon_path = os.path.join(project_root, "resources", "icons", "icon.ico")
    if os.path.exists(icon_path):
        app_icon_object = QIcon(icon_path)
        app.setWindowIcon(app_icon_object)
    else:
        print(f"Warning: Icon file not found at {icon_path}", file=sys.stderr)

    mw_init_start_time = time.perf_counter()
    main_window = MainWindow()
    mw_init_duration = time.perf_counter() - mw_init_start_time
    print(f"[BENCHMARK] MainWindow.__init__ took: {mw_init_duration:.4f} seconds")

    # If the icon was loaded, also set it explicitly on the main window.
    # This is often redundant if app.setWindowIcon() is used,
    # but can sometimes help ensure the taskbar icon is updated.
    if app_icon_object:
        main_window.setWindowIcon(app_icon_object)

    # --- Load and initialize DeckLink DLL using the handler ---
    if decklink_handler.initialize_output():
        # Register shutdown_decklink_output to be called on Qt application exit
        app.aboutToQuit.connect(decklink_handler.shutdown_output)
        print("DeckLink output initialized via handler. Shutdown scheduled on app quit.")
    else:
        # decklink_handler.initialize_output() will print its own error messages
        # Display the message on MainWindow's status bar
        main_window.set_status_message(
            "DeckLink Error: Could not initialize. No card detected or driver issue.",
            0 # Persistent message
        )
        print("Proceeding without DeckLink output (status bar updated).")
    # --- End DeckLink Load and Init ---

    mw_show_start_time = time.perf_counter()
    main_window.show()
    mw_show_duration = time.perf_counter() - mw_show_start_time
    print(f"[BENCHMARK] MainWindow.show() took: {mw_show_duration:.4f} seconds")

    app_ready_duration = time.perf_counter() - app_start_time
    print(f"[BENCHMARK] Application ready (after show) took: {app_ready_duration:.4f} seconds")
    sys.exit(app.exec())