import os
import sys
import subprocess

def compile_ui_files(start_dir):
    """
    Recursively finds and compiles .ui files to .py files using pyside6-uic.

    This function walks through all directories starting from 'start_dir'.
    For each .ui file found, it runs the 'pyside6-uic' command to generate
    a corresponding .py file. The output file will be named based on the
    input file (e.g., 'widget.ui' becomes 'widget_ui.py').

    Args:
        start_dir (str): The path to the directory to start the search from.
    """
    # Ensure the starting directory exists
    if not os.path.isdir(start_dir):
        print(f"Error: The specified directory does not exist: {start_dir}")
        return

    print(f"Starting UI compilation in directory: {os.path.abspath(start_dir)}\n")

    # Walk through the directory tree
    for root, _, files in os.walk(start_dir):
        for filename in files:
            # Check if the file is a .ui file
            if filename.endswith(".ui"):
                ui_file_path = os.path.join(root, filename)
                
                # Construct the output Python file name
                # e.g., 'main_window.ui' -> 'main_window_ui.py'
                base_name = filename[:-3]  # Remove '.ui'
                py_file_name = f"{base_name}_ui.py"
                py_file_path = os.path.join(root, py_file_name)

                print(f"Found UI file: {ui_file_path}")
                print(f"  -> Outputting to: {py_file_path}")

                # Construct the command to be executed
                command = [
                    "pyside6-uic",
                    ui_file_path,
                    "-o",
                    py_file_path
                ]

                try:
                    # Execute the command
                    subprocess.run(command, check=True, capture_output=True, text=True)
                    print("  -> Compilation successful!")
                except FileNotFoundError:
                    print("\nERROR: 'pyside6-uic' command not found.")
                    print("Please ensure that PySide6 is installed and that the 'pyside6-uic' executable is in your system's PATH.")
                    return # Exit the function
                except subprocess.CalledProcessError as e:
                    # This error occurs if pyside6-uic returns a non-zero exit code
                    print(f"  -> ERROR during compilation for {ui_file_path}:")
                    print(e.stderr)
                except Exception as e:
                    print(f"  -> An unexpected error occurred: {e}")
                
                print("-" * 30)

if __name__ == "__main__":
    # The script expects one argument: the directory to scan.
    # If no argument is provided, it defaults to the current working directory.
    if len(sys.argv) > 1:
        target_directory = sys.argv[1]
    else:
        # Fallback to the current directory if no path is given
        target_directory = "."
        print("No directory provided. Defaulting to the current directory.")

    compile_ui_files(target_directory)
    print("\nUI compilation process finished.")
