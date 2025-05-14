import sys
import os
import time

# Ensure the main project directory is in the Python path
# This helps ensure that imports like 'from windows.main_window import MainWindow' work correctly
# regardless of how the script is run (e.g., from the project root or a subdirectory).
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon # Import QIcon

# Import the main window class
from windows.main_window import MainWindow

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

    mw_show_start_time = time.perf_counter()
    main_window.show()
    mw_show_duration = time.perf_counter() - mw_show_start_time
    print(f"[BENCHMARK] MainWindow.show() took: {mw_show_duration:.4f} seconds")

    app_ready_duration = time.perf_counter() - app_start_time
    print(f"[BENCHMARK] Application ready (after show) took: {app_ready_duration:.4f} seconds")
    sys.exit(app.exec())