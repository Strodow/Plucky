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

# Import the main window class
from windows.main_window import MainWindow

if __name__ == "__main__":
    app_start_time = time.perf_counter()
    app = QApplication(sys.argv)

    mw_init_start_time = time.perf_counter()
    main_window = MainWindow()
    mw_init_duration = time.perf_counter() - mw_init_start_time
    print(f"[BENCHMARK] MainWindow.__init__ took: {mw_init_duration:.4f} seconds")

    mw_show_start_time = time.perf_counter()
    main_window.show()
    mw_show_duration = time.perf_counter() - mw_show_start_time
    print(f"[BENCHMARK] MainWindow.show() took: {mw_show_duration:.4f} seconds")

    app_ready_duration = time.perf_counter() - app_start_time
    print(f"[BENCHMARK] Application ready (after show) took: {app_ready_duration:.4f} seconds")
    sys.exit(app.exec())