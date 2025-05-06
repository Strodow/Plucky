import sys
import os

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
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec())