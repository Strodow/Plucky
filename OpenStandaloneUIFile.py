import sys
from PySide6.QtWidgets import QApplication, QMainWindow

# --- Import the generated UI class ---
# This assumes you have compiled "main_window.ui" into "ui_main_window.py" using pyside6-uic.
# The command would be: pyside6-uic main_window.ui -o ui_main_window.py
# The generated file contains a class, typically named Ui_MainWindow.
try:
    # Correctly import the CLASS 'Ui_MainWindow' from the MODULE 'main_window_ui'
    from windows.main_window_ui import Ui_MainWindow
except ImportError:
    print("Error: Could not import 'Ui_MainWindow' from 'windows/main_window_ui.py'.")
    print("Please make sure you have compiled the .ui file into a .py file and it is in the correct location.")
    print("Example command: pyside6-uic main_window.ui -o windows/main_window_ui.py")
    sys.exit(1)


class MainWindow(QMainWindow):
    """
    Main application window that inherits from QMainWindow.
    It uses the generated Ui_MainWindow class to set up its user interface.
    """
    def __init__(self):
        # Call the constructor of the parent class (QMainWindow).
        super().__init__()

        # Create an instance of the imported UI class.
        self.ui = Ui_MainWindow()

        # Call the setupUi method to create and lay out all the widgets
        # onto this QMainWindow. 'self' is passed as the container.
        self.ui.setupUi(self)

        # You can now access all the UI elements via self.ui
        # For example: self.ui.go_live_button.clicked.connect(self.my_function)
        # You would add all your signal/slot connections and application logic here.


def main():
    """
    The main function to initialize the application, create the main window,
    and run the event loop.
    """
    # 1. Create the QApplication instance.
    app = QApplication(sys.argv)

    # 2. Create an instance of our custom MainWindow class.
    window = MainWindow()

    # 3. Show the main window.
    window.show()

    # 4. Start the application's event loop.
    sys.exit(app.exec())


if __name__ == '__main__':
    # This standard Python construct ensures that the main() function is called
    # only when the script is executed directly.
    main()
