import os
import ctypes
import sys
import time # Added for the test section
try:
    import numpy as np
except ImportError:
    print("NumPy library not found. Please install it (pip install numpy) for optimized image processing.", file=sys.stderr)
    np = None # Allow script to run but optimized image loading will fail gracefully

try:
    from PySide6.QtGui import QImage, QColor, Qt, QPainter
    from PySide6.QtCore import QRect, Signal, QObject
    from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox, QCheckBox, QSlider, QTextEdit, QGroupBox, QGridLayout, QLineEdit)
except ImportError:
    print("PySide6 library not found or QtGui/QtWidgets module missing. Please ensure PySide6 is installed.", file=sys.stderr)
    sys.exit(1)

# --- DeckLink DLL Configuration ---
S_OK = 0  # HRESULT success code
S_FALSE = 1 # HRESULT success, but operation returned a false condition
DLL_WIDTH = 1920  # Match C++
DLL_HEIGHT = 1080 # Match C++
# Common frame rates (numerator, denominator)
# DeckLink API uses (TimeScale, Duration) which corresponds to (Numerator, Denominator)
TARGET_FRAME_RATE_NUM = 30000 # For 30 FPS
TARGET_FRAME_RATE_DEN = 1000  # For 30 FPS
PROGRAM_VERSION = "14.0" # Your program's version
DEBUG_SAVE_IMAGES = False # Set to True to save debug images from create_solid_color_fill_and_key_images

# Define expected DLL names for different SDK versions
# These should match the output names from your C++ project configurations.
DLL_NAME_14_4 = "DeckLinkWraper_Release_SDK14_4.dll"
DLL_NAME_14_2 = "DeckLinkWraper_Release_SDK14_2.dll"
# Add more here if you support other versions

AVAILABLE_DLL_VERSIONS = {
    "14.4 (Recommended)": DLL_NAME_14_4,
    "14.2": DLL_NAME_14_2,
    # Add more user-friendly names and corresponding DLL files here
}

FRAME_RATE_60 = (60, 1) # Or (60000, 1000)

# Define HRESULT type for convenience, typically a long int on Windows
HRESULT = ctypes.c_long

# --- HRESULT Definitions and Helper ---
# Common HRESULTs (add more as needed, especially DeckLink-specific ones if known)
HRESULT_DESCRIPTIONS = {
    0x00000000: "S_OK (Success)",
    0x00000001: "S_FALSE (Operation successful but returned a false condition)",
    0x8000FFFF: "E_UNEXPECTED (Catastrophic failure)",
    0x80004001: "E_NOTIMPL (Not implemented)",
    0x80004002: "E_NOINTERFACE (No such interface supported)",
    0x80004003: "E_POINTER (Invalid pointer)",
    0x80004004: "E_ABORT (Operation aborted)",
    0x80004005: "E_FAIL (Unspecified failure / Invalid Handle)", # E_FAIL and E_HANDLE share this value
    0x80070005: "E_ACCESSDENIED (Access denied)",
    0x8007000E: "E_OUTOFMEMORY (Out of memory)",
    # Example for a potential DeckLink-specific error (value is hypothetical)
    # 0x800A0001: "BMD_E_DEVICE_BUSY (DeckLink device is busy)",
}

def format_hresult(hr_code):
    """Formats an HRESULT code into a string with its hex value and description."""
    # HRESULTs are signed long in C, but often represented as unsigned hex.
    # We'll use the unsigned hex for display and dictionary keys.
    unsigned_hr_code = hr_code & 0xFFFFFFFF

    description = HRESULT_DESCRIPTIONS.get(unsigned_hr_code)

    if description is None:
        try:
            error_obj = ctypes.WinError(hr_code) # ctypes.WinError expects the original (possibly signed) code
            description = error_obj.strerror if error_obj.strerror else "Unknown HRESULT (WinError provided no description)"
        except OSError:
            description = "Unknown HRESULT (not recognized by WinError)"
    return f"{unsigned_hr_code:#010x} ({description})"

# --- Expected DLL Function Signatures ---
# Store expected functions and their ctypes setup
EXPECTED_FUNCTIONS = {
    "InitializeDLL": {"restype": HRESULT, "argtypes": []},
    "ShutdownDLL": {"restype": HRESULT, "argtypes": []},
    "GetDeviceCount": {"restype": HRESULT, "argtypes": [ctypes.POINTER(ctypes.c_int)]},
    "GetDeviceName": {"restype": HRESULT, "argtypes": [ctypes.c_int, ctypes.c_char_p, ctypes.c_int]},
    # InitializeDevice now takes fill_idx, key_idx, w, h, frNum, frDenom
    "InitializeDevice": {"restype": HRESULT, "argtypes": [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]},
    "ShutdownDevice": {"restype": HRESULT, "argtypes": []},
    # UpdateOutputFrame is now UpdateExternalKeyingFrames, taking two frame pointers
    "UpdateExternalKeyingFrames": {"restype": HRESULT, "argtypes": [ctypes.POINTER(ctypes.c_ubyte), ctypes.POINTER(ctypes.c_ubyte)]},
    # Keyer functions
    "EnableKeyer": {"restype": HRESULT, "argtypes": [ctypes.c_bool]},
    "DisableKeyer": {"restype": HRESULT, "argtypes": []},
    "SetKeyerLevel": {"restype": HRESULT, "argtypes": [ctypes.c_ubyte]},
    "IsKeyerActive": {"restype": HRESULT, "argtypes": [ctypes.POINTER(ctypes.c_bool)]},
    "GetAPIVersion": {"restype": HRESULT, "argtypes": [ctypes.POINTER(ctypes.c_longlong)]},
    # New profile functions
    "GetAvailableProfileCount": {"restype": HRESULT, "argtypes": [ctypes.POINTER(ctypes.c_int)]},
    "GetAvailableProfileName": {"restype": HRESULT, "argtypes": [ctypes.c_int, ctypes.c_char_p, ctypes.c_int]},
    "GetActiveProfileName": {"restype": HRESULT, "argtypes": [ctypes.c_char_p, ctypes.c_int]},
}

def get_project_root() -> str:
    return os.path.dirname(os.path.abspath(__file__))

def _load_specific_dll(dll_name_to_load: str) -> ctypes.CDLL | None:
    global decklink_dll
    project_root = get_project_root()
    dll_path_found = os.path.join(project_root, dll_name_to_load)

    if not os.path.exists(dll_path_found):
        print(f"Error: {dll_name_to_load} not found in expected location: {dll_path_found}", file=sys.stderr)
        return False

    try:
        decklink_dll = ctypes.CDLL(dll_path_found)
        # print(f"DeckLink DLL '{dll_name_to_load}' loaded successfully from {dll_path_found}") # Moved print to class

        # Dynamically set argtypes and restypes for expected functions
        print("\n--- Checking for expected DLL interfaces ---")
        all_expected_found = True
        for func_name, sig in EXPECTED_FUNCTIONS.items():
            try:
                func = getattr(decklink_dll, func_name)
                if "argtypes" in sig:
                    func.argtypes = sig["argtypes"]
                if "restype" in sig:
                    func.restype = sig["restype"]
                print(f"  [ OK ] Interface '{func_name}' found and configured.")
            except AttributeError:
                print(f"  [WARN] Interface '{func_name}' NOT FOUND in DLL.")
                all_expected_found = False # Or just a specific subset for critical functions
        
        # You might want to make this check stricter for essential functions
        # For now, we'll proceed even if some optional ones are missing.
        # if not all_expected_found:
        #     print("Warning: Not all expected DLL interfaces were found.", file=sys.stderr)

        return decklink_dll
    except OSError as e:
        print(f"Error loading DLL from {dll_path_found}: {e}", file=sys.stderr)
        return None

def initialize_sdk(dll_handle: ctypes.CDLL) -> tuple[bool, str]:
    """Initializes the DeckLink SDK (DLL level, COM)."""
    if not dll_handle:
        print("DeckLink DLL handle is None. Cannot initialize SDK.", file=sys.stderr)
        return False, "N/A"
    decklink_dll = dll_handle # Use the passed handle
    
    if not hasattr(decklink_dll, "InitializeDLL"):
        print("Error: InitializeDLL function not found in DLL. Cannot initialize SDK.", file=sys.stderr)
        return False
    
    hr = decklink_dll.InitializeDLL()
    if hr != S_OK:
        print(f"DeckLink InitializeDLL failed with HRESULT: {format_hresult(hr)}", file=sys.stderr)
        return False
    
    # Attempt to get and display API version
    if hasattr(decklink_dll, "GetAPIVersion"):
        print("[Python] Attempting to call GetAPIVersion...") # Python-side log
        api_version_ll = ctypes.c_longlong(0)
        hr_ver = decklink_dll.GetAPIVersion(ctypes.byref(api_version_ll))
        print(f"[Python] GetAPIVersion HRESULT: {format_hresult(hr_ver)}") # Python-side log

        if hr_ver == S_OK:
            # Decode the version: Byte4=Major, Byte3=Minor, Byte2=Sub, Byte1=Extra (least significant)
            # The BMDDeckLinkAPIVersion is a 64-bit integer, but the doc shows 4 bytes.
            # Let's assume it's packed into the lower 32 bits of the long long for now.
            # If it's truly 64-bit, the packing might be different or more complex.
            # For now, let's treat it as if the relevant part is in the lower 32 bits.
            print(f"[Python] GetAPIVersion returned S_OK. Raw version value: {api_version_ll.value}") # Python-side log
            version_val = api_version_ll.value
            major = (version_val >> 24) & 0xFF
            minor = (version_val >> 16) & 0xFF
            sub = (version_val >> 8) & 0xFF
            # extra = version_val & 0xFF # Not typically displayed
            api_version_str = f"{major}.{minor}.{sub}"
            print(f"DeckLink API Version: {api_version_str} (Raw: {version_val:#010x})")
            print("[Python] Finished processing GetAPIVersion success.") # Python-side log
        else:
            print(f"Could not retrieve DeckLink API Version. GetAPIVersion HRESULT: {format_hresult(hr_ver)}")
            print("[Python] Finished processing GetAPIVersion failure.") # Python-side log

    print("DeckLink DLL (API level) Initialized successfully.")
    return True, api_version_str if hr_ver == S_OK else "N/A"

def get_profile_info(dll_handle: ctypes.CDLL) -> tuple[list[str], str]:
    """Gets available and active profile information from the DLL."""
    if not dll_handle:
        print("SDK not initialized. Cannot get profile info.", file=sys.stderr)

    available_profiles = []
    active_profile_name = "N/A"

    # Get available profiles
    if hasattr(decklink_dll, "GetAvailableProfileCount") and hasattr(decklink_dll, "GetAvailableProfileName"):
        profile_count = ctypes.c_int(0)
        hr = decklink_dll.GetAvailableProfileCount(ctypes.byref(profile_count))
        if hr == S_OK and profile_count.value > 0:
            print(f"Found {profile_count.value} available profile(s):")
            for i in range(profile_count.value):
                name_buffer = ctypes.create_string_buffer(256)
                hr_name = decklink_dll.GetAvailableProfileName(i, name_buffer, ctypes.sizeof(name_buffer))
                if hr_name == S_OK:
                    prof_name = name_buffer.value.decode('utf-8')
                    available_profiles.append(prof_name)
                    print(f"  - {prof_name}")
                else:
                    print(f"  - Error getting name for profile {i}: {format_hresult(hr_name)}")
        elif hr != S_OK:
            print(f"GetAvailableProfileCount failed: {format_hresult(hr)}", file=sys.stderr)
        else:
            print("No available profiles found or GetAvailableProfileCount returned 0.")

    # Get active profile name
    if hasattr(dll_handle, "GetActiveProfileName"):
        name_buffer = ctypes.create_string_buffer(256)
        hr = dll_handle.GetActiveProfileName(name_buffer, ctypes.sizeof(name_buffer))
        if hr == S_OK:
            active_profile_name = name_buffer.value.decode('utf-8')
            print(f"Active Profile: {active_profile_name}")
        elif hr == S_FALSE: 
            print("No active profile identified by the DLL.")
            active_profile_name = "N/A (or not identified)"
        else:
            print(f"GetActiveProfileName failed: {format_hresult(hr)}", file=sys.stderr)
    return available_profiles, active_profile_name

def enumerate_devices(dll_handle: ctypes.CDLL) -> list[str]:
    """Enumerates available DeckLink devices. Assumes SDK is initialized."""
    if not dll_handle:
        print("SDK not initialized. Cannot enumerate devices.", file=sys.stderr)
        return []
    if not hasattr(decklink_dll, "GetDeviceCount") or not hasattr(decklink_dll, "GetDeviceName"):
        print("Error: GetDeviceCount or GetDeviceName not found in DLL. Cannot enumerate devices.", file=sys.stderr)
        return []

    device_count = ctypes.c_int(0) # Ensure this is reset or local
    hr = decklink_dll.GetDeviceCount(ctypes.byref(device_count))
    if hr != S_OK:
        print(f"GetDeviceCount failed with HRESULT: {format_hresult(hr)}", file=sys.stderr)
        # decklink_dll.ShutdownDLL() # Consider if shutting down entire SDK is desired here
        return [] # Return empty list on failure, consistent with other paths
    
    if device_count.value == 0:
        print("No DeckLink devices found.")
        g_device_names = []
        return []

    current_device_names = []
    for i in range(device_count.value):
        name_buffer = ctypes.create_string_buffer(512)
        hr = decklink_dll.GetDeviceName(i, name_buffer, ctypes.sizeof(name_buffer))
        device_name = name_buffer.value.decode('utf-8') if hr == S_OK else f"Unknown Device {i} (Error: {format_hresult(hr)})"
        current_device_names.append(device_name)
    
    g_device_names = current_device_names
    print(f"Found {len(g_device_names)} DeckLink device(s):")
    for i, name in enumerate(g_device_names):
        print(f"  Device {i}: {name}")
    return g_device_names

def initialize_selected_devices(dll_handle: ctypes.CDLL, device_names: list[str], fill_device_idx: int, key_device_idx: int, video_mode_details: dict) -> bool:
    if not dll_handle:
        print("DeckLink DLL handle is None. Cannot initialize devices.", file=sys.stderr)
        return False
    
    if len(device_names) < 2: # Use the device_names parameter
        print("Error: Need at least 2 DeckLink devices/ports for external keying.", file=sys.stderr)
        # decklink_dll.ShutdownDLL() # Avoid shutting down entire SDK on this specific failure

        return False
        
    if not video_mode_details:
        print("Error: Video mode details not provided for device initialization.", file=sys.stderr)
        return False

    width = video_mode_details.get("width")
    height = video_mode_details.get("height")
    fr_num = video_mode_details.get("fr_num")
    fr_den = video_mode_details.get("fr_den")

    # Ensure selected indices are valid (though device_count.value < 2 check helps)
    if not (0 <= fill_device_idx < len(device_names) and \
            0 <= key_device_idx < len(device_names) and \
            fill_device_idx != key_device_idx):
        print(f"Error: Invalid device indices selected for fill ({fill_device_idx}) and key ({key_device_idx}). Available: {len(device_names)}", file=sys.stderr)
        # decklink_dll.ShutdownDLL() # Avoid shutting down entire SDK on this specific failure
        return False

    print(f"Attempting to initialize Fill on device {fill_device_idx}: {device_names[fill_device_idx]}")
    print(f"Attempting to initialize Key on device {key_device_idx}: {device_names[key_device_idx]}")

    if not hasattr(dll_handle, "InitializeDevice") or not dll_handle.InitializeDevice:
        print("Error: InitializeDevice function not found in DLL. Cannot initialize devices.", file=sys.stderr)
        # decklink_initialized_successfully = False # This global is removed
        return False

    hr = decklink_dll.InitializeDevice(fill_device_idx, key_device_idx, width, height, fr_num, fr_den)
    
    if hr == S_OK:
        print(f"Successfully initialized Fill (Device {fill_device_idx}) and Key (Device {key_device_idx}) outputs.")
        print(f"Outputs configured for {DLL_WIDTH}x{DLL_HEIGHT}@{TARGET_FRAME_RATE_NUM}/{TARGET_FRAME_RATE_DEN} FPS.")
        return True
    else:
        print(f"Failed to initialize devices for external keying. HRESULT: {format_hresult(hr)}", file=sys.stderr)
        return False

def shutdown_selected_devices(dll_handle: ctypes.CDLL):
    """Shuts down the currently initialized DeckLink devices."""
    if not dll_handle:
        print("DeckLink DLL handle is None. Cannot shutdown devices.", file=sys.stderr)
        return
    # This block should be at the same indentation level as the check above
    if hasattr(dll_handle, "DisableKeyer"): # Attempt to disable keyer before shutdown if active
        print("Attempting to disable keyer before shutdown...") # Ensure keyer is off before device shutdown
        disable_keyer(dll_handle) # Pass the handle
    else:
        print("DisableKeyer function not found, skipping explicit keyer disable on shutdown.")

    if hasattr(dll_handle, "ShutdownDevice"): # Use dll_handle here
        print("Shutting down active DeckLink device...")
        hr_dev_shutdown = dll_handle.ShutdownDevice() # Use dll_handle here
        if hr_dev_shutdown != S_OK:
            print(f"DeckLink ShutdownDevice failed with HRESULT: {format_hresult(hr_dev_shutdown)}", file=sys.stderr)
        else:
            print("DeckLink device shutdown complete.")
    else:
        print("Error: ShutdownDevice function not found in DLL. Cannot shutdown device properly.", file=sys.stderr)

def shutdown_sdk(dll_handle: ctypes.CDLL):
    """Shuts down the DeckLink SDK (DLL level, COM)."""
    if not dll_handle:
        print("DeckLink DLL handle is None. Cannot shutdown SDK.", file=sys.stderr)
        return

    if hasattr(dll_handle, "ShutdownDLL"):
        hr = dll_handle.ShutdownDLL()
        if hr != S_OK:
            print(f"DeckLink ShutdownDLL failed with HRESULT: {format_hresult(hr)}", file=sys.stderr)
        else:
            print("DeckLink API (DLL level) Shutdown complete.")
    else:
            print("Error: ShutdownDLL function not found in DLL. Cannot shutdown API properly.", file=sys.stderr)

def send_external_keying_frames(dll_handle: ctypes.CDLL, fill_bgra_bytes: bytearray, key_bgra_bytes: bytearray) -> bool:
    if not dll_handle:
        print("Cannot send frames: DeckLink not initialized.", file=sys.stderr)
        return False
    
    if not hasattr(dll_handle, "UpdateExternalKeyingFrames"):
        print("Error: UpdateExternalKeyingFrames function not found in DLL.", file=sys.stderr)
        return False
        
    expected_frame_size = DLL_WIDTH * DLL_HEIGHT * 4
    if len(fill_bgra_bytes) != expected_frame_size:
        print(f"Error: Fill frame size mismatch. Expected {expected_frame_size} bytes, got {len(fill_bgra_bytes)} bytes.", file=sys.stderr)
        return False
    if len(key_bgra_bytes) != expected_frame_size:
        print(f"Error: Key frame size mismatch. Expected {expected_frame_size} bytes, got {len(key_bgra_bytes)} bytes.", file=sys.stderr)
        return False

    c_fill_data = (ctypes.c_ubyte * len(fill_bgra_bytes)).from_buffer_copy(fill_bgra_bytes)
    c_key_data = (ctypes.c_ubyte * len(key_bgra_bytes)).from_buffer_copy(key_bgra_bytes)
    
    hr = dll_handle.UpdateExternalKeyingFrames(c_fill_data, c_key_data)
    if hr != S_OK:
        print(f"UpdateExternalKeyingFrames failed with HRESULT: {format_hresult(hr)}", file=sys.stderr)
        return False
    return True

# --- Keyer Control Functions ---
def enable_keyer(dll_handle: ctypes.CDLL, is_external: bool) -> bool:
    if not dll_handle: # Check dll_handle directly
        print("Cannot enable keyer: DeckLink not initialized.", file=sys.stderr)
        return False
    if not hasattr(dll_handle, "EnableKeyer"):
        print("EnableKeyer function not found in DLL.", file=sys.stderr)
        return False
        
    hr = dll_handle.EnableKeyer(is_external)
    if hr != S_OK:
        print(f"EnableKeyer failed with HRESULT: {format_hresult(hr)}", file=sys.stderr)
        return False
    print("Keyer enabled successfully.")
    return True
    
def disable_keyer(dll_handle: ctypes.CDLL) -> bool: # Added dll_handle parameter
    if not dll_handle: 
        print("Cannot disable keyer: DeckLink DLL not loaded.", file=sys.stderr)
        return False
    if not hasattr(dll_handle, "DisableKeyer"):
        print("DisableKeyer function not found in DLL.", file=sys.stderr)
        return False

    hr = dll_handle.DisableKeyer()
    if hr != S_OK:
        print(f"DisableKeyer failed with HRESULT: {format_hresult(hr)}", file=sys.stderr)
        return False
    print("Keyer disabled successfully.")
    return True
    
def set_keyer_level(dll_handle: ctypes.CDLL, level: int) -> bool: # Added dll_handle parameter
    if not dll_handle:
        print("Cannot set keyer level: DeckLink not initialized.", file=sys.stderr)
        return False
    if not hasattr(dll_handle, "SetKeyerLevel"):
        print("SetKeyerLevel function not found in DLL.", file=sys.stderr)
        return False

    if not 0 <= level <= 255:
        print(f"Error: Keyer level must be between 0 and 255. Got {level}", file=sys.stderr)
        return False
    
    hr = dll_handle.SetKeyerLevel(ctypes.c_ubyte(level))
    if hr != S_OK:
        print(f"SetKeyerLevel failed with HRESULT: {format_hresult(hr)}", file=sys.stderr)
        return False
    print(f"Keyer level set to {level} successfully.")
    return True
    
def is_keyer_active(dll_handle: ctypes.CDLL) -> bool | None: # Added dll_handle parameter
    if not dll_handle:
        print("Cannot check keyer status: DeckLink not initialized.", file=sys.stderr)
        return None # Undetermined
    if not hasattr(dll_handle, "IsKeyerActive"):
        print("IsKeyerActive function not found in DLL. Cannot determine keyer status.", file=sys.stderr)
        return None # Undetermined

    is_active_ptr = ctypes.pointer(ctypes.c_bool(False))
    hr = dll_handle.IsKeyerActive(is_active_ptr)
    if hr != S_OK:
        print(f"IsKeyerActive failed with HRESULT: {format_hresult(hr)}", file=sys.stderr)
        return None # Undetermined
    
    status = is_active_ptr.contents.value
    print(f"Keyer is currently {'active' if status else 'inactive'}.")


def create_solid_color_fill_and_key_images(target_width, target_height, fill_qcolor: QColor, key_qcolor: QColor):
    """
    Creates Fill (BGRA) and Key (BGRA) QImages, each filled with a solid color.
    then converts them to bytearrays.
    Returns: (fill_bytearray, key_bytearray) or (None, None) on error.
    """
    try:
        # --- Create Fill Image ---
        fill_image = QImage(target_width, target_height, QImage.Format_ARGB32_Premultiplied)
        if fill_image.isNull():
            print(f"Error: Could not create fill_image.", file=sys.stderr)
            return None, None
        fill_image.fill(fill_qcolor)

        # --- Create Key Image ---
        key_image = QImage(target_width, target_height, QImage.Format_ARGB32_Premultiplied)
        if key_image.isNull():
            print(f"Error: Could not create key_image.", file=sys.stderr)
            return None, None
        key_image.fill(key_qcolor)
        
        if DEBUG_SAVE_IMAGES:
            project_root = get_project_root()
            fill_save_path = os.path.join(project_root, "debug_fill_image.png")
            key_save_path = os.path.join(project_root, "debug_key_image.png")
            if not fill_image.save(fill_save_path):
                print(f"Warning: Could not save debug_fill_image.png to {fill_save_path}")
            if not key_image.save(key_save_path):
                print(f"Warning: Could not save debug_key_image.png to {key_save_path}")

        fill_bytearray = get_image_bytes_from_qimage(fill_image)
        key_bytearray = get_image_bytes_from_qimage(key_image)

        if not fill_bytearray or not key_bytearray: # Check if conversion failed
            return None, None # Errors would have been printed by get_image_bytes_from_qimage

        return fill_bytearray, key_bytearray

    except Exception as e:
        print(f"Error creating solid color fill/key images: {e}", file=sys.stderr)
        return None, None

def get_image_bytes_from_qimage(q_image: QImage):
    """Helper to convert a QImage (expected to be ARGB32_Premultiplied) to BGRA bytearray."""
    if q_image.isNull():
        print("decklink_handler.get_image_bytes_from_qimage: ERROR - QImage is null.", file=sys.stderr)
        return None
    if q_image.format() != QImage.Format_ARGB32_Premultiplied:
        print(f"decklink_handler.get_image_bytes_from_qimage: ERROR - QImage format is {q_image.format()}, not ARGB32_Premultiplied.", file=sys.stderr)
        return None
    
    # q_image.constBits() in PySide6 can return a memoryview directly
    # which is suitable for creating a bytearray.
    # The memoryview already knows its size.
    mem_view = q_image.constBits() 

    if not mem_view: 
        print("decklink_handler.get_image_bytes_from_qimage: ERROR - q_image.constBits() returned an invalid pointer.", file=sys.stderr)
        return None
    
    # print(f"decklink_handler.get_image_bytes_from_qimage: Type of object from constBits(): {type(mem_view)}") # Keep for debug if needed

    # Create a bytearray directly from the buffer
    try:
        # A memoryview can be directly converted to a bytearray (which makes a copy)
        return bytearray(mem_view)
    except Exception as e:
        print(f"decklink_handler.get_image_bytes_from_qimage: ERROR - Exception during bytearray conversion: {e}", file=sys.stderr)
        return None

def load_image_and_create_key_matte(image_path, target_width, target_height):
    """
    Loads an image, prepares it as fill (ARGB32_Premultiplied),
    and creates a corresponding key matte (alpha of original image used for R,G,B,A).
    Returns (fill_bgra_bytearray, key_bgra_bytearray) or (None, None).
    """
    try:
        t_start_total = time.perf_counter()

        # 1. Load the original image
        t_start_load = time.perf_counter()
        original_image = QImage(image_path)
        t_end_load = time.perf_counter()
        if original_image.isNull():
            print(f"Error: QImage could not load image from '{image_path}'", file=sys.stderr)
            return None, None
        print(f"Debug Step 1: Image '{image_path}' loaded. Original format: {original_image.format()}, size: {original_image.size()}, hasAlphaChannel: {original_image.hasAlphaChannel()} (Took: {t_end_load - t_start_load:.4f}s)")
        if original_image.width() > 0 and original_image.height() > 0: # Check if image has valid dimensions
            print(f"Debug Step 1: Sample pixel (0,0) alpha (raw load): {QColor(original_image.pixel(0,0)).alpha()}")
        # Save the raw loaded image for inspection
        # original_image.save(os.path.join(get_project_root(), "debug_loaded_raw.png"))
        # print("Debug Step 1: Saved raw loaded image to debug_loaded_raw.png")

        # 2. Ensure it has an alpha channel and convert to ARGB32 for consistent alpha access
        t_start_convert = time.perf_counter()
        print(f"Debug Step 2: Before ARGB32 conversion - hasAlphaChannel: {original_image.hasAlphaChannel()}, format: {original_image.format()}")
        if not original_image.hasAlphaChannel():
            print(f"Warning: Image '{image_path}' has no alpha channel. Converting to ARGB32 (will be opaque).")
            original_image = original_image.convertToFormat(QImage.Format_ARGB32) # Will add opaque alpha
            print(f"Debug Step 2a: Converted to ARGB32 because no alpha. New format: {original_image.format()}, hasAlphaChannel: {original_image.hasAlphaChannel()}")
        elif original_image.format() != QImage.Format_ARGB32:
            print(f"Debug Step 2b: Format is not ARGB32 (it's {original_image.format()}). Converting to ARGB32.")
            original_image = original_image.convertToFormat(QImage.Format_ARGB32)
            print(f"Debug Step 2b: Converted to ARGB32 from other format. New format: {original_image.format()}, hasAlphaChannel: {original_image.hasAlphaChannel()}")
        else:
            print(f"Debug Step 2c: Image already ARGB32 or has alpha and is suitable.")
        t_end_convert = time.perf_counter()

        if original_image.width() > 0 and original_image.height() > 0: # Check again after potential conversion
            print(f"Debug Step 2: Sample pixel (0,0) alpha (after ARGB32 conversion attempt): {QColor(original_image.pixel(0,0)).alpha()}")
        # Save the image after ARGB32 conversion attempt for inspection
        # original_image.save(os.path.join(get_project_root(), "debug_loaded_converted_to_argb32.png"))
        # print("Debug Step 2: Saved image after ARGB32 conversion to debug_loaded_converted_to_argb32.png")

        print(f"Debug: Format conversion/check (Step 2) took: {t_end_convert - t_start_convert:.4f}s")

        # 3. Resize if necessary
        t_start_resize = time.perf_counter()
        if original_image.width() != target_width or original_image.height() != target_height:
            print(f"Resizing image from {original_image.size()} to {target_width}x{target_height}.")
            original_image = original_image.scaled(target_width, target_height, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
            print(f"Debug Step 3: Image resized. New format: {original_image.format()}, hasAlphaChannel: {original_image.hasAlphaChannel()}")
            if original_image.width() > 0 and original_image.height() > 0:
                 print(f"Debug Step 3: Sample pixel (0,0) alpha (after resize): {QColor(original_image.pixel(0,0)).alpha()}")
        t_end_resize = time.perf_counter()
        print(f"Debug: Resizing (Step 3) took: {t_end_resize - t_start_resize:.4f}s")

        # 4. Create Fill Image (Premultiplied ARGB32)
        t_start_fill_create = time.perf_counter()
        fill_image = QImage(original_image.size(), QImage.Format_ARGB32_Premultiplied)
        fill_image.fill(Qt.GlobalColor.transparent) # Fill with transparent before drawing
        painter_fill = QPainter(fill_image)
        painter_fill.drawImage(0, 0, original_image) # Draws original_image (ARGB32) onto premultiplied surface
        painter_fill.end()
        t_end_fill_create = time.perf_counter()
        print(f"Debug: Fill image creation (Step 4) took: {t_end_fill_create - t_start_fill_create:.4f}s")
        
        # Optional: Save fill_image for debugging
        # fill_image.save(os.path.join(get_project_root(), "debug_loaded_fill_out.png"))

        # 5. Create Key Matte Image (from original_image's alpha)
        t_start_key_matte = time.perf_counter()
        key_matte_image = QImage(target_width, target_height, QImage.Format_ARGB32_Premultiplied)
        # No need to fill with transparent if all pixels are set.
        key_matte_image.fill(Qt.GlobalColor.transparent) # Explicitly fill, good practice

        min_alpha_read = 255
        max_alpha_read = 0
        # To avoid flooding logs, we'll check a few pixels and summarize
        pixels_to_check_coords = [(0,0), (target_width//2, target_height//2), (target_width-1, target_height-1)]
        if target_width == 0 or target_height == 0: # Prevent division by zero if target size is invalid
            print("Error: Target width or height is zero, cannot process image for key matte.")
            return None, None

        if np: # Use NumPy optimization if available
            # Get the entire buffer of original_image (ARGB32)
            original_buffer_view = original_image.constBits()
            original_np = np.frombuffer(original_buffer_view, dtype=np.uint32).reshape((target_height, target_width))

            # Direct extraction of alpha from ARGB32 pixel value (Alpha is the most significant byte)
            alpha_val_np = ((original_np >> 24) & 0xFF).astype(np.uint32) # Ensure uint32 for calculations

            min_alpha_read = int(np.min(alpha_val_np))
            max_alpha_read = int(np.max(alpha_val_np))

            # For key_matte_image (Format_ARGB32_Premultiplied)
            # Color is (alpha_val, alpha_val, alpha_val) with alpha=alpha_val.
            # Premultiplied R, G, B components are p_comp = (alpha_val * alpha_val) // 255.
            p_comp_np = (alpha_val_np * alpha_val_np) // 255
            
            # Construct the premultiplied ARGB32 values for the key matte
            key_matte_data_np = (alpha_val_np << 24) | (p_comp_np << 16) | (p_comp_np << 8) | p_comp_np

            # Create key_matte_image and copy data into its buffer
            # QImage constructor from data requires bytes, so we'll create an empty image and fill its buffer
            key_matte_image.bits()[:] = key_matte_data_np.tobytes()

            # Debug prints for a few pixels (optional, can be slow for very frequent calls)
            for y_coord, x_coord in pixels_to_check_coords:
                if 0 <= y_coord < target_height and 0 <= x_coord < target_width:
                    original_pixel_value = original_np[y_coord, x_coord]
                    extracted_alpha = alpha_val_np[y_coord, x_coord]
                    print(f"Debug (NumPy): original_image pixel({x_coord},{y_coord}) - QRgb: {original_pixel_value:#010x}, Extracted Alpha for Key: {extracted_alpha}")

        else: # Fallback to ctypes scanLine method if NumPy is not available
            print("Warning: NumPy not available. Falling back to slower ctypes-based key matte generation.")
            for y in range(target_height):
                original_scanline_ptr_raw = original_image.scanLine(y)
                key_matte_scanline_ptr_raw = key_matte_image.scanLine(y)
                original_pixels = (ctypes.c_uint32 * target_width).from_buffer(original_scanline_ptr_raw)
                key_matte_pixels = (ctypes.c_uint32 * target_width).from_buffer(key_matte_scanline_ptr_raw)

                for x in range(target_width):
                    original_pixel_value = original_pixels[x]
                    alpha_val = (original_pixel_value >> 24) & 0xFF
                    if (x,y) in pixels_to_check_coords: print(f"Debug (ctypes): original_image pixel({x},{y}) - QRgb: {original_pixel_value:#010x}, Extracted Alpha for Key: {alpha_val}")
                    if alpha_val < min_alpha_read: min_alpha_read = alpha_val
                    if alpha_val > max_alpha_read: max_alpha_read = alpha_val
                    p_comp = (alpha_val * alpha_val) // 255
                    key_matte_pixels[x] = (alpha_val << 24) | (p_comp << 16) | (p_comp << 8) | p_comp
                
        t_end_key_matte = time.perf_counter()
        print(f"Debug: Alpha values summary from original_image for key matte generation: Min={min_alpha_read}, Max={max_alpha_read}")
        print(f"Debug: Key matte generation (Step 5) took: {t_end_key_matte - t_start_key_matte:.4f}s")
        # Optional: Save key_matte_image for debugging
        # key_matte_image.save(os.path.join(get_project_root(), "debug_loaded_key_matte_out.png"))

        # 6. Convert both to BGRA bytearrays
        t_start_convert_bytes = time.perf_counter()
        fill_bgra_bytes = get_image_bytes_from_qimage(fill_image)
        key_bgra_bytes = get_image_bytes_from_qimage(key_matte_image)
        t_end_convert_bytes = time.perf_counter()
        print(f"Debug: Conversion to bytearrays (Step 6) took: {t_end_convert_bytes - t_start_convert_bytes:.4f}s")

        if not fill_bgra_bytes or not key_bgra_bytes:
            return None, None
        
        t_end_total = time.perf_counter()
        print(f"Debug: Total time for load_image_and_create_key_matte: {t_end_total - t_start_total:.4f}s")
        return fill_bgra_bytes, key_bgra_bytes
    except Exception as e:
        print(f"Error in load_image_and_create_key_matte for '{image_path}': {e}", file=sys.stderr)
        return None, None    

# --- DeckLink Controller Class ---
class DeckLinkController:
    def __init__(self):
        self._decklink_dll: ctypes.CDLL | None = None
        self._sdk_initialized: bool = False
        self._decklink_initialized: bool = False # True if InitializeDevice was successful
        self._current_dll_wrapper_version: str = "N/A"
        self._g_device_names: list[str] = [] # Stores names of enumerated devices
        self._api_version_str: str = "N/A"
        self._active_profile_name: str = "N/A"

    def is_sdk_initialized(self) -> bool:
        return self._sdk_initialized

    def is_device_initialized(self) -> bool:
        return self._decklink_initialized

    def get_device_names(self) -> list[str]:
        return self._g_device_names

    def get_device_count(self) -> int:
        return len(self._g_device_names)

    def get_wrapper_version(self) -> str:
        return self._current_dll_wrapper_version

    def get_api_version(self) -> str:
        return self._api_version_str

    def get_active_profile_name(self) -> str:
        return self._active_profile_name

    def initialize_sdk(self, dll_name_to_load: str) -> bool:
        if self._sdk_initialized:
            print("SDK already initialized. Please shutdown first if you want to re-initialize with a different DLL.")
            return True # Already initialized is considered success for this call

        print(f"Attempting to load and initialize with DLL: {dll_name_to_load}")
        self._decklink_dll = _load_specific_dll(dll_name_to_load)

        if not self._decklink_dll:
            print(f"Failed to load DLL: {dll_name_to_load}")
            self._current_dll_wrapper_version = "N/A (Load Failed)"
            return False

        print(f"Successfully loaded {dll_name_to_load}. Attempting SDK initialization...")
        sdk_init_success, api_version_str = initialize_sdk(self._decklink_dll)

        if sdk_init_success:
            print(f"SDK initialized successfully using {dll_name_to_load}. Reported API version: {api_version_str}")
            self._sdk_initialized = True
            self._api_version_str = api_version_str
            # Find the version string (key) corresponding to the loaded DLL file
            loaded_version_key = "N/A"
            for key, value in AVAILABLE_DLL_VERSIONS.items():
                if value == dll_name_to_load:
                    loaded_version_key = key.split(" ")[0] # e.g., "14.4" from "14.4 (Recommended)"
                    break
            self._current_dll_wrapper_version = loaded_version_key
            # Get and display profile info
            _, self._active_profile_name = get_profile_info(self._decklink_dll)
            return True
        else:
            print(f"Failed to initialize SDK using {dll_name_to_load}.")
            self._decklink_dll = None # Nullify our reference
            self._current_dll_wrapper_version = "N/A (Init Failed)"
            self._sdk_initialized = False
            self._api_version_str = "Failed to retrieve"
            self._active_profile_name = "N/A"
            return False

    def shutdown_sdk(self):
        if self._decklink_initialized:
            print("Warning: Devices were initialized but not shut down before SDK shutdown. Attempting device shutdown.")
            self.shutdown_devices() # Use the instance method

        if self._sdk_initialized and self._decklink_dll:
            shutdown_sdk(self._decklink_dll) # Call the standalone shutdown function
        else:
            print("DeckLink SDK not initialized or DLL not loaded, nothing to shut down.")

        self._sdk_initialized = False
        self._decklink_initialized = False
        self._decklink_dll = None # Ensure we release the DLL handle from Python's side
        self._current_dll_wrapper_version = "N/A"
        self._g_device_names = []
        self._api_version_str = "N/A"
        self._active_profile_name = "N/A"

    def enumerate_devices(self) -> list[str]:
        if not self._sdk_initialized or not self._decklink_dll:
            print("SDK not initialized. Cannot enumerate devices.", file=sys.stderr)
            self._g_device_names = []
            return []
        self._g_device_names = enumerate_devices(self._decklink_dll) # Call the standalone enumerate function
        return self._g_device_names

    def initialize_devices(self, fill_device_idx: int, key_device_idx: int, video_mode_details: dict) -> bool:
        if not self._sdk_initialized or not self._decklink_dll:
            print("SDK not initialized. Cannot initialize devices.", file=sys.stderr)
            return False

        init_success = initialize_selected_devices(self._decklink_dll, self._g_device_names, fill_device_idx, key_device_idx, video_mode_details)
        self._decklink_initialized = init_success
        return init_success

    def shutdown_devices(self):
        if self._decklink_initialized and self._decklink_dll:
            shutdown_selected_devices(self._decklink_dll) # Call the standalone shutdown function
        else:
            print("DeckLink devices not initialized, nothing to shut down.")
        self._decklink_initialized = False

    def send_frames(self, fill_bgra_bytes: bytearray, key_bgra_bytes: bytearray) -> bool:
        if not self._decklink_initialized or not self._decklink_dll:
            print("DeckLink devices not initialized. Cannot send frames.", file=sys.stderr)
            return False
        return send_external_keying_frames(self._decklink_dll, fill_bgra_bytes, key_bgra_bytes)

    # Keyer Control methods - these will call the standalone functions, passing the DLL handle
    def enable_keyer(self, is_external: bool) -> bool:
        if not self._decklink_initialized or not self._decklink_dll:
            print("DeckLink devices not initialized. Cannot enable keyer.", file=sys.stderr)
            return False
        print(f"Attempting to enable keyer (external: {is_external})...")
        return enable_keyer(self._decklink_dll, is_external)

    def disable_keyer(self) -> bool:
        # Allow disabling even if devices aren't marked initialized, for cleanup
        if not self._sdk_initialized or not self._decklink_dll:
             print("SDK not initialized. Cannot disable keyer.", file=sys.stderr)
             return False
        print("Attempting to disable keyer...")
        return disable_keyer(self._decklink_dll)

    def set_keyer_level(self, level: int) -> bool:
        if not self._decklink_initialized or not self._decklink_dll:
            print("DeckLink devices not initialized. Cannot set keyer level.", file=sys.stderr)
            return False
        print(f"Attempting to set keyer level to {level}...")
        return set_keyer_level(self._decklink_dll, level)

    def is_keyer_active(self) -> bool | None:
        if not self._decklink_initialized or not self._decklink_dll:
            print("DeckLink devices not initialized. Cannot check keyer status.", file=sys.stderr)
            return None
        return is_keyer_active(self._decklink_dll)

# --- GUI Application ---
class QTextEditLogger(QObject):
    messageWritten = Signal(str)
    def write(self, msg):
        self.messageWritten.emit(str(msg))
    def flush(self): # QPlainTextEdit is auto-flushing
        pass

class DeckLinkGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DeckLink Control Panel")
        self.setGeometry(100, 100, 800, 600)
        self._init_ui()
        self._connect_signals()
        

        self.decklink_controller = DeckLinkController() # Create an instance of the controller
        self.current_image_path = None # For storing the path of the loaded image



        # Redirect stdout/stderr to the log_output QTextEdit
        self.log_handler = QTextEditLogger()
        self.log_handler.messageWritten.connect(self.log_output.append)
        sys.stdout = self.log_handler
        sys.stderr = self.log_handler

        self._update_ui_state()


    def _init_ui(self):
        main_layout = QVBoxLayout(self)

        # --- SDK and Device Initialization Group ---
        sdk_group = QGroupBox("SDK & Device Control")
        sdk_layout = QGridLayout()

        self.combo_dll_selection = QComboBox()
        for display_name, dll_file in AVAILABLE_DLL_VERSIONS.items():
            self.combo_dll_selection.addItem(display_name, dll_file) # Store filename as item data

        self.btn_init_sdk = QPushButton("1. Initialize SDK (using selected DLL)")
        self.btn_enum_devices = QPushButton("2. Enumerate Devices")
        self.btn_init_devices = QPushButton("4. Initialize Selected Devices") # Numbering might need review based on flow
        self.btn_shutdown_devices = QPushButton("Shutdown Devices")
        self.btn_shutdown_sdk = QPushButton("Shutdown SDK (and Devices)")

        self.lbl_program_version = QLabel(f"Program Version: {PROGRAM_VERSION}")
        self.lbl_api_version = QLabel("DeckLink API Version: N/A")
        self.lbl_wrapper_version = QLabel("Wrapper DLL Version: N/A")
        self.lbl_active_profile = QLabel("Active Profile: N/A") # New label for active profile

        self.combo_fill_device = QComboBox()
        self.combo_key_device = QComboBox()

        # Updated layout:
        row = 0
        sdk_layout.addWidget(QLabel("Select DLL Version:"), row, 0)
        sdk_layout.addWidget(self.combo_dll_selection, row, 1)
        row += 1
        sdk_layout.addWidget(self.btn_init_sdk, row, 0)
        sdk_layout.addWidget(self.btn_enum_devices, row, 1)
        row += 1
        sdk_layout.addWidget(QLabel("3. Select Fill Device:"), row, 0) # Adjusted label
        sdk_layout.addWidget(self.combo_fill_device, row, 1)
        row += 1
        sdk_layout.addWidget(QLabel("   Select Key Device:"), row, 0) # Adjusted label
        sdk_layout.addWidget(self.combo_key_device, row, 1)
        row += 1
        sdk_layout.addWidget(self.lbl_wrapper_version, row, 0, 1, 2)
        sdk_layout.addWidget(self.btn_init_devices, row + 1, 0, 1, 2)
        sdk_layout.addWidget(self.lbl_program_version, row + 2, 0, 1, 2)
        sdk_layout.addWidget(self.lbl_api_version, row + 3, 0)
        sdk_layout.addWidget(self.lbl_active_profile, row + 3, 1) # Add active profile label
        sdk_layout.addWidget(self.btn_shutdown_devices, row + 4, 0) # Adjusted row
        sdk_layout.addWidget(self.btn_shutdown_sdk, row + 4, 1)   # Adjusted row
        sdk_group.setLayout(sdk_layout)
        main_layout.addWidget(sdk_group)

        # --- Color Output Group ---
        color_group = QGroupBox("Source Color Input (RGBA for Fill, A for Key Matte)")
        color_layout = QHBoxLayout()

        color_layout.addWidget(QLabel("R:"))
        self.le_source_r = QLineEdit("0") # Default to transparent black
        color_layout.addWidget(self.le_source_r)
        color_layout.addWidget(QLabel("G:"))
        self.le_source_g = QLineEdit("0")
        color_layout.addWidget(self.le_source_g)
        color_layout.addWidget(QLabel("B:"))
        self.le_source_b = QLineEdit("0")
        color_layout.addWidget(self.le_source_b)
        color_layout.addWidget(QLabel("A:"))
        self.le_source_a = QLineEdit("0") # Default alpha to 0 (transparent)
        color_layout.addWidget(self.le_source_a)
        self.btn_send_source_color = QPushButton("Send Source Color")
        color_layout.addWidget(self.btn_send_source_color)

        color_group.setLayout(color_layout)
        main_layout.addWidget(color_group)

        # Store references to new input elements for easier state updates
        self.source_color_widgets = [self.le_source_r, self.le_source_g, self.le_source_b, self.le_source_a,
                                     self.btn_send_source_color]
        # --- Image File Output Group ---
        image_file_group = QGroupBox("Image File Output (Alpha for Key Matte)")
        image_file_layout = QHBoxLayout()
        self.le_image_path = QLineEdit()
        self.le_image_path.setPlaceholderText("No image selected...")
        self.le_image_path.setReadOnly(True)
        self.btn_browse_image = QPushButton("Browse Image...")
        self.btn_send_image = QPushButton("Send Image to Output")
        image_file_layout.addWidget(self.le_image_path)
        image_file_layout.addWidget(self.btn_browse_image)
        image_file_layout.addWidget(self.btn_send_image)
        image_file_group.setLayout(image_file_layout)
        main_layout.addWidget(image_file_group)
        # --- Keyer Control Group ---
        keyer_group = QGroupBox("Keyer Control")
        keyer_layout = QHBoxLayout()
        self.chk_enable_keyer = QCheckBox("Enable External Keyer")
        self.slider_keyer_level = QSlider(Qt.Orientation.Horizontal)
        self.slider_keyer_level.setRange(0, 255)
        self.slider_keyer_level.setValue(255) # Default to opaque
        self.lbl_keyer_level = QLabel(f"Level: {self.slider_keyer_level.value()}")
        keyer_layout.addWidget(self.chk_enable_keyer)
        keyer_layout.addWidget(self.slider_keyer_level)
        keyer_layout.addWidget(self.lbl_keyer_level)
        keyer_group.setLayout(keyer_layout)
        main_layout.addWidget(keyer_group)

        # --- Log Output ---
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        main_layout.addWidget(self.log_output)

    def _connect_signals(self):
        self.btn_init_sdk.clicked.connect(self.on_init_sdk)
        self.btn_enum_devices.clicked.connect(self.on_enum_devices)
        self.btn_init_devices.clicked.connect(self.on_init_devices)
        self.btn_shutdown_devices.clicked.connect(self.on_shutdown_devices)
        self.btn_shutdown_sdk.clicked.connect(self.on_shutdown_sdk)

        self.btn_send_source_color.clicked.connect(self.on_send_source_color)

        self.chk_enable_keyer.toggled.connect(self.on_toggle_keyer)
        self.slider_keyer_level.valueChanged.connect(self.on_set_keyer_level)
        self.btn_browse_image.clicked.connect(self.on_browse_image)
        self.btn_send_image.clicked.connect(self.on_send_image_to_output)


    def _update_ui_state(self):
        # SDK Level
        # "Initialize SDK" button should be enabled if the SDK is not currently initialized (via the controller).
        self.combo_dll_selection.setEnabled(not self.decklink_controller.is_sdk_initialized())
        self.btn_init_sdk.setEnabled(not self.decklink_controller.is_sdk_initialized() and self.combo_dll_selection.count() > 0)
        self.btn_enum_devices.setEnabled(self.decklink_controller.is_sdk_initialized())
        self.btn_shutdown_sdk.setEnabled(self.decklink_controller.is_sdk_initialized())

        # Device Level (depends on SDK and device enumeration)
        can_init_devices = self.decklink_controller.is_sdk_initialized() and self.decklink_controller.get_device_count() >= 2
        self.combo_fill_device.setEnabled(can_init_devices and not self.decklink_controller.is_device_initialized())
        self.combo_key_device.setEnabled(can_init_devices and not self.decklink_controller.is_device_initialized())
        self.btn_init_devices.setEnabled(can_init_devices and not self.decklink_controller.is_device_initialized())
        self.btn_shutdown_devices.setEnabled(self.decklink_controller.is_device_initialized())

        # Output/Keyer Level (depends on devices initialized)
        for widget in self.source_color_widgets:
            widget.setEnabled(self.decklink_controller.is_device_initialized())
        self.le_image_path.setEnabled(self.decklink_controller.is_device_initialized())
        self.btn_browse_image.setEnabled(self.decklink_controller.is_device_initialized())
        self.btn_send_image.setEnabled(self.decklink_controller.is_device_initialized() and self.current_image_path is not None)

        # --- Disable SDK Keyer Controls as we are focusing on external hardware keying ---
        self.chk_enable_keyer.setEnabled(self.decklink_controller.is_device_initialized()) # Enable if devices are up
        self.chk_enable_keyer.setToolTip("SDK-controlled keyer features are disabled in this version.")
        self.slider_keyer_level.setEnabled(self.decklink_controller.is_device_initialized() and self.chk_enable_keyer.isChecked()) # Enable if devices up and keyer checked

        # Update labels from controller state
        self.lbl_api_version.setText(f"DeckLink API Version: {self.decklink_controller.get_api_version()}")
        self.lbl_wrapper_version.setText(f"Wrapper DLL Version: {self.decklink_controller.get_wrapper_version()}")
        self.lbl_active_profile.setText(f"Active Profile: {self.decklink_controller.get_active_profile_name()}")

    def on_init_sdk(self):
        selected_dll_file = self.combo_dll_selection.currentData()
        selected_display_name = self.combo_dll_selection.currentText()

        if not selected_dll_file:
            print("No DLL selected from the dropdown.")
            return

        # Call the controller's method
        self.decklink_controller.initialize_sdk(selected_dll_file)
        self._update_ui_state() # Update UI based on controller state

    def on_enum_devices(self): # This method was duplicated, removing the first one.
        # Call the controller's method
        names = self.decklink_controller.enumerate_devices()
        self.combo_fill_device.clear()
        self.combo_key_device.clear()
        if names:
            for i, name in enumerate(names):
                self.combo_fill_device.addItem(f"{i}: {name}", i)
                self.combo_key_device.addItem(f"{i}: {name}", i)
            if len(names) >= 2: # Default selection if possible
                self.combo_fill_device.setCurrentIndex(0) # Default to device 0 for fill
                self.combo_key_device.setCurrentIndex(1) # Default to device 1 for key                
        self._update_ui_state()
        
    def on_init_devices(self): 
        fill_idx = self.combo_fill_device.currentData()
        key_idx = self.combo_key_device.currentData()

        if fill_idx is None or key_idx is None:
            print("Please select valid Fill and Key devices.")
            return
        if fill_idx == key_idx:
            print("Fill and Key devices cannot be the same.")
            return
        
        # Create a default video_mode_details for the test GUI
        test_video_mode_details = {
            "name": f"{DLL_WIDTH}x{DLL_HEIGHT} @ {TARGET_FRAME_RATE_NUM/TARGET_FRAME_RATE_DEN:.2f} (Test GUI Default)",
            "width": DLL_WIDTH,
            "height": DLL_HEIGHT,
            "fr_num": TARGET_FRAME_RATE_NUM,
            "fr_den": TARGET_FRAME_RATE_DEN
        }
        # Call the controller's method
        if self.decklink_controller.initialize_devices(fill_idx, key_idx, test_video_mode_details):
            print("Devices initialized successfully.")
        self._update_ui_state()

    def on_shutdown_devices(self):
        # Call the controller's method
        self.decklink_controller.shutdown_devices()
        print("Devices shut down.")
        self._update_ui_state()

    def on_shutdown_sdk(self):
        # Call the controller's method
        self.decklink_controller.shutdown_sdk()
        self._update_ui_state()

    def _parse_rgba_inputs(self, r_le, g_le, b_le, a_le) -> QColor | None:
        """Helper to parse RGBA QLineEdits and return a QColor or None on error."""
        try:
            r = int(r_le.text())
            g = int(g_le.text())
            b = int(b_le.text())
            a = int(a_le.text())
            if not (0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255 and 0 <= a <= 255):
                print("Error: RGBA values must be between 0 and 255.")
                return None
            return QColor(r, g, b, a)
        except ValueError:
            print("Error: RGBA values must be valid integers.")
            return None

    def _send_fill_and_key_to_decklink(self, fill_color: QColor, key_color: QColor):
        """Core logic to generate and send frames using the controller."""
        # Generate images (this part remains outside the controller for now)
        fill_data, key_data = create_solid_color_fill_and_key_images(DLL_WIDTH, DLL_HEIGHT, fill_color, key_color)
        if fill_data and key_data:
            # Use the controller to send the frames
            if self.decklink_controller.send_frames(fill_data, key_data):
                print(f"Sent Fill ({fill_color.name()}) and Key ({key_color.name()}) to outputs.")
            else:
                print(f"Failed to send frames.")
        else:
            print(f"Failed to generate image data.")

    def on_send_source_color(self):
        source_r_le = self.le_source_r
        source_g_le = self.le_source_g
        source_b_le = self.le_source_b
        source_a_le = self.le_source_a

        source_color_components = self._parse_rgba_inputs(source_r_le, source_g_le, source_b_le, source_a_le)
        if source_color_components is None:
            return # Error already printed by _parse_rgba_inputs

        # Create fill color directly from source components
        r, g, b, a = source_color_components.red(), source_color_components.green(), source_color_components.blue(), source_color_components.alpha()
        
        fill_c = QColor(r, g, b, a)
        # Create key color where R, G, B, and A are all set to the source alpha
        key_c = QColor(a, a, a, a)

        # No longer need last_fill/key_color state in GUI, controller handles sending
        print(f"Sending Source Color. Fill: {fill_c.name()}, Key: {key_c.name()}")
        self._send_fill_and_key_to_decklink(fill_c, key_c)
    def on_browse_image(self):
        # PySide6.QtWidgets.QFileDialog
        from PySide6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Image", "", "Image Files (*.png *.jpg *.bmp *.jpeg *.gif *.tif *.tiff)")
        if file_path: self.current_image_path = file_path
        self.le_image_path.setText(file_path if file_path else "No image selected...")
        print(f"Image selected: {file_path}" if file_path else "Image selection cancelled.")
        self._update_ui_state() # Update send button state

    def on_send_image_to_output(self):
        if not self.current_image_path:
            print("No image selected to send.")
            return

        print(f"Attempting to load and send image: {self.current_image_path}")
        fill_data, key_data = load_image_and_create_key_matte(self.current_image_path, DLL_WIDTH, DLL_HEIGHT)

        if fill_data and key_data:
            # Use the controller to send the frames
            if self.decklink_controller.send_frames(fill_data, key_data):
                print(f"Successfully sent image '{os.path.basename(self.current_image_path)}' to output.")
            else:
                print(f"Failed to send image '{os.path.basename(self.current_image_path)}' to output.")
        else:
            print(f"Failed to load or prepare image '{self.current_image_path}' for output.")


    def on_toggle_keyer(self, checked):
        if checked:
            self.decklink_controller.enable_keyer(is_external=True)
        else:
            self.decklink_controller.disable_keyer()
        self._update_ui_state() # Slider enable state depends on this

    def on_set_keyer_level(self, value):
        self.lbl_keyer_level.setText(f"Level: {value}")
        self.decklink_controller.set_keyer_level(value)

    def closeEvent(self, event):
        """Ensure SDK is shut down when GUI closes."""
        print("Closing application, ensuring DeckLink SDK is shut down...")
        self.decklink_controller.shutdown_sdk() # Use the controller's shutdown
        super().closeEvent(event)

if __name__ == "__main__":
    print("--- Starting DeckLink Handler Test ---")

    # Ensure QApplication instance exists for QImage and other Qt components
    # This needs to be done *before* any QImage or QColor objects are created if they
    # are used globally or before the app.exec_() call.
    # The DeckLinkGUI will handle its own QApplication instance.

    # Ensure QApplication is created first
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    main_window = DeckLinkGUI() # Create the main window instance
    main_window.show()

    print("\n--- DeckLink Handler Test Finished ---")
    sys.exit(app.exec())