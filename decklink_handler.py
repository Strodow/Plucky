import os
import ctypes
import sys

# --- DeckLink DLL Configuration ---
DLL_NAME = "DeckLinkLib.dll" # Or whatever your DLL is named
S_OK = 0  # HRESULT success code
DLL_WIDTH = 1920  # Match C++
DLL_HEIGHT = 1080 # Match C++

# Define HRESULT type for convenience, typically a long int on Windows
HRESULT = ctypes.c_long

decklink_dll = None
decklink_initialized_successfully = False

def get_project_root():
    # Assuming this file (decklink_handler.py) is in the project root
    # c:\Users\Logan\Documents\Plucky\Plucky\
    return os.path.dirname(os.path.abspath(__file__))

def load_dll():
    global decklink_dll
    project_root = get_project_root()
    
    possible_dll_paths = [
        os.path.join(project_root, "DLLs", DLL_NAME),
        os.path.join(project_root, DLL_NAME),
        # os.path.join(project_root, "x64", "Debug", DLL_NAME), # If built there
        # os.path.join(project_root, "x64", "Release", DLL_NAME), # If built there
    ]
    
    dll_path_found = None
    for p_path in possible_dll_paths:
        if os.path.exists(p_path):
            dll_path_found = p_path
            break
            
    if not dll_path_found:
        print(f"Error: {DLL_NAME} not found in expected locations: {possible_dll_paths}", file=sys.stderr)
        return False

    try:
        decklink_dll = ctypes.CDLL(dll_path_found)

        decklink_dll.InitializeDLL.restype = HRESULT
        decklink_dll.ShutdownDLL.restype = HRESULT
        decklink_dll.UpdateOutputFrame.argtypes = [ctypes.POINTER(ctypes.c_ubyte)]
        decklink_dll.UpdateOutputFrame.restype = HRESULT
        
        print(f"DeckLink DLL '{DLL_NAME}' loaded successfully from {dll_path_found}")
        return True
    except OSError as e:
        print(f"Error loading DLL from {dll_path_found}: {e}", file=sys.stderr)
        decklink_dll = None
        return False

def initialize_output():
    global decklink_initialized_successfully
    if not decklink_dll:
        if not load_dll(): # Attempt to load if not already loaded
            print("DeckLink DLL not loaded and failed to load, cannot initialize.", file=sys.stderr)
            return False
    
    hr = decklink_dll.InitializeDLL()
    if hr != S_OK:
        print(f"DeckLink InitializeDLL failed with HRESULT: {hr:#010x}", file=sys.stderr)
        decklink_initialized_successfully = False
        return False
    print("DeckLink Initialized successfully via DLL.")
    decklink_initialized_successfully = True
    return True

def shutdown_output():
    global decklink_initialized_successfully
    if decklink_dll and decklink_initialized_successfully:
        print("Shutting down DeckLink via DLL...")
        hr = decklink_dll.ShutdownDLL()
        if hr != S_OK:
            print(f"DeckLink ShutdownDLL failed with HRESULT: {hr:#010x}", file=sys.stderr)
        else:
            print("DeckLink Shutdown complete via DLL.")
        decklink_initialized_successfully = False # Mark as not initialized

def send_frame(image_bgra_bytes):
    if not decklink_dll or not decklink_initialized_successfully:
        return False
    
    c_image_data = (ctypes.c_ubyte * len(image_bgra_bytes)).from_buffer_copy(image_bgra_bytes)
    hr = decklink_dll.UpdateOutputFrame(c_image_data)
    if hr != S_OK:
        # This can be noisy if called every frame on error, consider logging strategy
        # print(f"DeckLink UpdateOutputFrame failed with HRESULT: {hr:#010x}", file=sys.stderr)
        return False
    return True