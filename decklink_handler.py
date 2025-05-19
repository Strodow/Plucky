import os
import ctypes
import sys
import time # Added for the test section
try:
    from PySide6.QtGui import QImage, QColor, Qt
    from PySide6.QtCore import QRect, Signal, QObject
    from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox, QCheckBox, QSlider, QTextEdit, QGroupBox, QGridLayout)
except ImportError:
    print("PySide6 library not found or QtGui/QtWidgets module missing. Please ensure PySide6 is installed.", file=sys.stderr)
    sys.exit(1)

# --- DeckLink DLL Configuration ---
DLL_NAME = "DeckLinkWraper.dll" # Updated to match the C++ project output
S_OK = 0  # HRESULT success code
DLL_WIDTH = 1920  # Match C++
DLL_HEIGHT = 1080 # Match C++
# Common frame rates (numerator, denominator)
# DeckLink API uses (TimeScale, Duration) which corresponds to (Numerator, Denominator)
TARGET_FRAME_RATE_NUM = 30000 # For 30 FPS
TARGET_FRAME_RATE_DEN = 1000  # For 30 FPS
PROGRAM_VERSION = "14.0" # Your program's version
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

decklink_dll = None
decklink_initialized_successfully = False # True if InitializeDevice was successful
sdk_initialized_successfully = False # True if InitializeDLL was successful
g_device_names = [] # Stores names of enumerated devices

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
    "GetAPIVersion": {"restype": HRESULT, "argtypes": [ctypes.POINTER(ctypes.c_longlong)]}
}

def get_project_root():
    return os.path.dirname(os.path.abspath(__file__))

def load_dll():
    global decklink_dll
    project_root = get_project_root()
            
    dll_path_found = os.path.join(project_root, DLL_NAME)
            
    if not os.path.exists(dll_path_found):
        print(f"Error: {DLL_NAME} not found in expected location: {dll_path_found}", file=sys.stderr)
        return False

    try:
        decklink_dll = ctypes.CDLL(dll_path_found)
        print(f"DeckLink DLL '{DLL_NAME}' loaded successfully from {dll_path_found}")

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

        return True
    except OSError as e:
        print(f"Error loading DLL from {dll_path_found}: {e}", file=sys.stderr)
        decklink_dll = None
        return False

def initialize_sdk():
    """Initializes the DeckLink SDK (DLL level, COM)."""
    global sdk_initialized_successfully
    if not decklink_dll:
        if not load_dll():
            print("DeckLink DLL not loaded and failed to load, cannot initialize SDK.", file=sys.stderr)
            return False
    
    if not hasattr(decklink_dll, "InitializeDLL"):
        print("Error: InitializeDLL function not found in DLL. Cannot initialize SDK.", file=sys.stderr)
        return False
    
    hr = decklink_dll.InitializeDLL()
    if hr != S_OK:
        print(f"DeckLink InitializeDLL failed with HRESULT: {format_hresult(hr)}", file=sys.stderr)
        sdk_initialized_successfully = False # Correct flag to set on failure
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
    sdk_initialized_successfully = True # This was missing!
    return True, api_version_str if hr_ver == S_OK else "N/A"

def enumerate_devices():
    """Enumerates available DeckLink devices. Assumes SDK is initialized."""
    global g_device_names
    if not sdk_initialized_successfully:
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
        name_buffer = ctypes.create_string_buffer(512) # Increased buffer size
        hr = decklink_dll.GetDeviceName(i, name_buffer, ctypes.sizeof(name_buffer))
        if hr == S_OK:
            device_name = name_buffer.value.decode('utf-8')
            current_device_names.append(device_name)
        else:
            current_device_names.append(f"Unknown Device {i} (Error: {format_hresult(hr)})")
    
    g_device_names = current_device_names
    print(f"Found {len(g_device_names)} DeckLink device(s):")
    for i, name in enumerate(g_device_names):
        print(f"  Device {i}: {name}")
    return g_device_names

def initialize_selected_devices(fill_device_idx: int, key_device_idx: int, video_mode_details: dict) -> bool:
    global decklink_initialized_successfully
    if not sdk_initialized_successfully:
        print("SDK not initialized. Cannot initialize devices.", file=sys.stderr)
        return False
    
    if len(g_device_names) < 2: # Use global g_device_names
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
    if not (0 <= fill_device_idx < len(g_device_names) and \
            0 <= key_device_idx < len(g_device_names) and \
            fill_device_idx != key_device_idx):
        print(f"Error: Invalid device indices selected for fill ({fill_device_idx}) and key ({key_device_idx}). Available: {len(g_device_names)}", file=sys.stderr)
        # decklink_dll.ShutdownDLL() # Avoid shutting down entire SDK on this specific failure
        return False

    print(f"Attempting to initialize Fill on device {fill_device_idx}: {g_device_names[fill_device_idx]}")
    print(f"Attempting to initialize Key on device {key_device_idx}: {g_device_names[key_device_idx]}")

    if not hasattr(decklink_dll, "InitializeDevice") or not decklink_dll.InitializeDevice:
        print("Error: InitializeDevice function not found in DLL. Cannot initialize devices.", file=sys.stderr)
        decklink_dll.ShutdownDLL()
        decklink_initialized_successfully = False
        return False

    hr = decklink_dll.InitializeDevice(fill_device_idx, key_device_idx, width, height, fr_num, fr_den)
    
    if hr == S_OK:
        print(f"Successfully initialized Fill (Device {fill_device_idx}) and Key (Device {key_device_idx}) outputs.")
        print(f"Outputs configured for {DLL_WIDTH}x{DLL_HEIGHT}@{TARGET_FRAME_RATE_NUM}/{TARGET_FRAME_RATE_DEN} FPS.")
        decklink_initialized_successfully = True
        return True
    else:
        print(f"Failed to initialize devices for external keying. HRESULT: {format_hresult(hr)}", file=sys.stderr)
        decklink_initialized_successfully = False
        return False

def shutdown_selected_devices():
    """Shuts down the currently initialized DeckLink devices."""
    global decklink_initialized_successfully

    if decklink_dll and decklink_initialized_successfully:
        if hasattr(decklink_dll, "DisableKeyer"): # Attempt to disable keyer before shutdown if active
            print("Attempting to disable keyer before shutdown...") # Ensure keyer is off before device shutdown
            disable_keyer()
        else:
            print("DisableKeyer function not found, skipping explicit keyer disable on shutdown.")

        if hasattr(decklink_dll, "ShutdownDevice"):
            print("Shutting down active DeckLink device...")
            hr_dev_shutdown = decklink_dll.ShutdownDevice()
            if hr_dev_shutdown != S_OK:
                print(f"DeckLink ShutdownDevice failed with HRESULT: {format_hresult(hr_dev_shutdown)}", file=sys.stderr)
            else:
                print("DeckLink device shutdown complete.")
        else:
            print("Error: ShutdownDevice function not found in DLL. Cannot shutdown device properly.", file=sys.stderr)

        decklink_initialized_successfully = False # Mark devices as shut down

def shutdown_sdk():
    """Shuts down the DeckLink SDK (DLL level, COM)."""
    global sdk_initialized_successfully, decklink_initialized_successfully
    if decklink_dll:
        if decklink_initialized_successfully:
            
            print("Warning: Devices were initialized but not shut down before SDK shutdown. Attempting device shutdown.")
            shutdown_selected_devices()
        if not hasattr(decklink_dll, "ShutdownDLL"):
            print("Error: ShutdownDLL function not found in DLL. Cannot shutdown API properly.", file=sys.stderr)
            decklink_initialized_successfully = False # Still mark as not init
            return

        hr = decklink_dll.ShutdownDLL()
        if hr != S_OK:
            print(f"DeckLink ShutdownDLL failed with HRESULT: {format_hresult(hr)}", file=sys.stderr)
        else:
            print("DeckLink API (DLL level) Shutdown complete.")
    else:
        print("DeckLink DLL not loaded, nothing to shut down at SDK level.")
    sdk_initialized_successfully = False
    decklink_initialized_successfully = False



def send_external_keying_frames(fill_bgra_bytes, key_bgra_bytes):
    if not decklink_dll or not decklink_initialized_successfully:
        print("Cannot send frames: DeckLink not initialized.", file=sys.stderr)
        return False
    
    if not hasattr(decklink_dll, "UpdateExternalKeyingFrames"):
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
    
    hr = decklink_dll.UpdateExternalKeyingFrames(c_fill_data, c_key_data)
    if hr != S_OK:
        print(f"UpdateExternalKeyingFrames failed with HRESULT: {format_hresult(hr)}", file=sys.stderr)
        return False
    return True


# --- Keyer Control Functions ---
def enable_keyer(is_external: bool):
    if not decklink_dll or not decklink_initialized_successfully:
        print("Cannot enable keyer: DeckLink not initialized.", file=sys.stderr)
        return False
    if not hasattr(decklink_dll, "EnableKeyer"):
        print("EnableKeyer function not found in DLL.", file=sys.stderr)
        return False
        
    print(f"Attempting to enable keyer (external: {is_external})...")
    hr = decklink_dll.EnableKeyer(is_external)
    if hr != S_OK:
        print(f"EnableKeyer failed with HRESULT: {format_hresult(hr)}", file=sys.stderr)
        return False
    print("Keyer enabled successfully.")
    return True

def disable_keyer():
    if not decklink_dll: # Don't check initialized_successfully here, might be called during shutdown cleanup
        print("Cannot disable keyer: DeckLink DLL not loaded.", file=sys.stderr)
        return False
    if not hasattr(decklink_dll, "DisableKeyer"):
        print("DisableKeyer function not found in DLL.", file=sys.stderr)
        return False

    print("Attempting to disable keyer...")
    hr = decklink_dll.DisableKeyer()
    if hr != S_OK:
        print(f"DisableKeyer failed with HRESULT: {format_hresult(hr)}", file=sys.stderr)
        return False
    print("Keyer disabled successfully.")
    return True

def set_keyer_level(level: int):
    if not decklink_dll or not decklink_initialized_successfully:
        print("Cannot set keyer level: DeckLink not initialized.", file=sys.stderr)
        return False
    if not hasattr(decklink_dll, "SetKeyerLevel"):
        print("SetKeyerLevel function not found in DLL.", file=sys.stderr)
        return False

    if not 0 <= level <= 255:
        print(f"Error: Keyer level must be between 0 and 255. Got {level}", file=sys.stderr)
        return False
    
    print(f"Attempting to set keyer level to {level}...")
    hr = decklink_dll.SetKeyerLevel(ctypes.c_ubyte(level))
    if hr != S_OK:
        print(f"SetKeyerLevel failed with HRESULT: {format_hresult(hr)}", file=sys.stderr)
        return False
    print(f"Keyer level set to {level} successfully.")
    return True

def is_keyer_active():
    if not decklink_dll or not decklink_initialized_successfully:
        print("Cannot check keyer status: DeckLink not initialized.", file=sys.stderr)
        return None # Undetermined
    if not hasattr(decklink_dll, "IsKeyerActive"):
        print("IsKeyerActive function not found in DLL. Cannot determine keyer status.", file=sys.stderr)
        return None # Undetermined

    is_active_ptr = ctypes.pointer(ctypes.c_bool(False))
    hr = decklink_dll.IsKeyerActive(is_active_ptr)
    if hr != S_OK:
        print(f"IsKeyerActive failed with HRESULT: {format_hresult(hr)}", file=sys.stderr)
        return None # Undetermined
    
    status = is_active_ptr.contents.value
    print(f"Keyer is currently {'active' if status else 'inactive'}.")
    return status

def load_image_for_decklink_pyside(image_path, target_width, target_height):
    """
    Loads an image using QImage, ensures it's RGBA, resizes if necessary,
    and converts it to BGRA bytearray for DeckLink.
    """
    try:
        q_image = QImage(image_path)
        if q_image.isNull():
            print(f"Error: QImage could not load image from '{image_path}'", file=sys.stderr)
            return None
        
        print(f"Image '{image_path}' loaded with QImage. Original format: {q_image.format()}, size: {q_image.size()}")

        # Ensure image is RGBA (or a format easily convertible)
        # QImage.Format_ARGB32_Premultiplied is good as it has alpha and is common.
        # DeckLink often expects BGRA, so we'll handle that.
        if q_image.format() != QImage.Format_ARGB32_Premultiplied and q_image.format() != QImage.Format_RGBA8888:
            q_image = q_image.convertToFormat(QImage.Format_ARGB32_Premultiplied)
            print(f"Image converted to QImage.Format_ARGB32_Premultiplied.")

        # Resize if necessary
        if q_image.width() != target_width or q_image.height() != target_height:
            print(f"Warning: Image size {q_image.width()}x{q_image.height()} does not match target {target_width}x{target_height}. Resizing.")
            q_image = q_image.scaled(target_width, target_height, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)

        # QImage stores ARGB32 as 0xAARRGGBB (little-endian) or BGRA (big-endian) depending on system.
        # For DeckLink, we need BGRA.
        # QImage.rgbSwapped() converts ARGB <-> ABGR. So if it's ARGB32, it becomes ABGR32.
        # If it was RGBA8888, it becomes BGRA8888.
        # Let's ensure it's in a format where bytes() gives us BGRA or something close.
        # Format_ARGB32_Premultiplied on little-endian systems is BGRA in memory.
        # Format_RGBA8888 is RGBA in memory.
        # We need BGRA. If current format is RGBA8888, swap R and B.
        # If it's ARGB32 (which is BGRA in memory on Windows/little-endian), it's fine.
        if q_image.format() == QImage.Format_RGBA8888: # Explicitly RGBA
            q_image = q_image.rgbSwapped() # Swaps R and B -> BGRA

        # For QImage.Format_ARGB32_Premultiplied (and similar 32bpp formats),
        # constBits() or bits() returns a pointer to the data.
        # We need to ensure we read the correct number of bytes.
        # Create a memoryview from the QImage's constBits
        # This provides a read-only view into the QImage's buffer.
        mem_view = memoryview(q_image.constBits()).cast('B') # Cast to bytes (unsigned char)
        return bytearray(mem_view) # Create a bytearray (copy) from the memoryview

    except FileNotFoundError: # QImage constructor handles this by returning isNull()
        print(f"Error: Image file not found at '{image_path}' (QImage reported isNull)", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Error processing image '{image_path}' with QImage: {e}", file=sys.stderr)
        return None

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
        
        # --- DIAGNOSTIC: Save images to disk before sending ---
        project_root = get_project_root()
        fill_save_path = os.path.join(project_root, "debug_fill_image.png")
        key_save_path = os.path.join(project_root, "debug_key_image.png")
        if not fill_image.save(fill_save_path):
            print(f"Warning: Could not save debug_fill_image.png to {fill_save_path}")
        if not key_image.save(key_save_path):
            print(f"Warning: Could not save debug_key_image.png to {key_save_path}")

        # Convert fill_image to bytearray (BGRA)
        fill_mem_view = memoryview(fill_image.constBits()).cast('B')
        fill_bytearray = bytearray(fill_mem_view)

        # Convert key_image to bytearray (BGRA)
        key_mem_view = memoryview(key_image.constBits()).cast('B')
        key_bytearray = bytearray(key_mem_view)

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
        self._update_ui_state()

        self.last_fill_color = QColor(0,0,0) # Default to black
        self.last_key_color = QColor(0,0,0)  # Default to black

        # Redirect stdout/stderr to the log_output QTextEdit
        self.log_handler = QTextEditLogger()
        self.log_handler.messageWritten.connect(self.log_output.append)
        sys.stdout = self.log_handler
        sys.stderr = self.log_handler

        if not load_dll():
            print("Failed to load DeckLinkWraper.dll. GUI may not function.")
        else:
            print(f"DeckLinkWraper.dll loaded.") # SDK version will be printed by initialize_sdk
        self._update_ui_state() # Call again after load_dll attempt


    def _init_ui(self):
        main_layout = QVBoxLayout(self)

        # --- SDK and Device Initialization Group ---
        sdk_group = QGroupBox("SDK & Device Control")
        sdk_layout = QGridLayout()

        self.btn_init_sdk = QPushButton("1. Initialize SDK")
        self.btn_enum_devices = QPushButton("2. Enumerate Devices")
        self.btn_init_devices = QPushButton("4. Initialize Selected Devices")
        self.btn_shutdown_devices = QPushButton("Shutdown Devices")
        self.btn_shutdown_sdk = QPushButton("Shutdown SDK (and Devices)")

        self.lbl_program_version = QLabel(f"Program Version: {PROGRAM_VERSION}")
        self.lbl_api_version = QLabel("DeckLink API Version: N/A")

        self.combo_fill_device = QComboBox()
        self.combo_key_device = QComboBox()

        sdk_layout.addWidget(self.btn_init_sdk, 0, 0)
        sdk_layout.addWidget(self.btn_enum_devices, 0, 1)
        sdk_layout.addWidget(QLabel("3. Fill Device:"), 1, 0)
        sdk_layout.addWidget(self.combo_fill_device, 1, 1)
        sdk_layout.addWidget(QLabel("   Key Device:"), 2, 0)
        sdk_layout.addWidget(self.combo_key_device, 2, 1)
        sdk_layout.addWidget(self.btn_init_devices, 3, 0, 1, 2)
        sdk_layout.addWidget(self.lbl_program_version, 4, 0, 1, 2)
        sdk_layout.addWidget(self.lbl_api_version, 5, 0, 1, 2)
        sdk_layout.addWidget(self.btn_shutdown_devices, 6, 0)
        sdk_layout.addWidget(self.btn_shutdown_sdk, 6, 1)
        sdk_group.setLayout(sdk_layout)
        main_layout.addWidget(sdk_group)

        # --- Color Output Group ---
        color_group = QGroupBox("Color Output (BGRA)")
        color_layout = QGridLayout()
        self.color_buttons = {}
        colors = {"Black": QColor(0,0,0), "Red": QColor(255,0,0), "Green": QColor(0,255,0), "Blue": QColor(0,0,255), "White": QColor(255,255,255)}
        row = 0
        for name, qcolor in colors.items():
            btn_fill = QPushButton(f"Fill {name}")
            btn_key = QPushButton(f"Key {name}")
            color_layout.addWidget(btn_fill, row, 0)
            color_layout.addWidget(btn_key, row, 1)
            self.color_buttons[f"fill_{name.lower()}"] = (btn_fill, qcolor, True) # True for fill
            self.color_buttons[f"key_{name.lower()}"] = (btn_key, qcolor, False) # False for key
            row += 1
        color_group.setLayout(color_layout)
        main_layout.addWidget(color_group)

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

        for btn_id, (button, qcolor, is_fill) in self.color_buttons.items():
            button.clicked.connect(lambda checked=False, qc=qcolor, fill=is_fill: self.on_send_color(qc, fill))

        self.chk_enable_keyer.toggled.connect(self.on_toggle_keyer)
        self.slider_keyer_level.valueChanged.connect(self.on_set_keyer_level)

    def _update_ui_state(self):
        # SDK Level
        self.btn_init_sdk.setEnabled(decklink_dll is not None and not sdk_initialized_successfully)
        self.btn_enum_devices.setEnabled(sdk_initialized_successfully)
        self.btn_shutdown_sdk.setEnabled(sdk_initialized_successfully)

        # Device Level (depends on SDK and device enumeration)
        can_init_devices = sdk_initialized_successfully and len(g_device_names) >= 2
        self.combo_fill_device.setEnabled(can_init_devices and not decklink_initialized_successfully)
        self.combo_key_device.setEnabled(can_init_devices and not decklink_initialized_successfully)
        self.btn_init_devices.setEnabled(can_init_devices and not decklink_initialized_successfully)
        self.btn_shutdown_devices.setEnabled(decklink_initialized_successfully)

        # Output/Keyer Level (depends on devices initialized)
        for btn_id, (button, _, _) in self.color_buttons.items():
            button.setEnabled(decklink_initialized_successfully)
        # --- Disable SDK Keyer Controls as we are focusing on external hardware keying ---
        self.chk_enable_keyer.setEnabled(False) #decklink_initialized_successfully)
        self.chk_enable_keyer.setToolTip("SDK-controlled keyer features are disabled in this version.")
        self.slider_keyer_level.setEnabled(False) #decklink_initialized_successfully and self.chk_enable_keyer.isChecked())

    def on_init_sdk(self):
        success, api_version_str = initialize_sdk()
        if success:
            print("SDK Initialized. Please enumerate devices.")
            self.lbl_api_version.setText(f"DeckLink API Version: {api_version_str}")
        else:
            self.lbl_api_version.setText("DeckLink API Version: Failed to retrieve")
        self._update_ui_state()
    def on_enum_devices(self):
        global g_device_names
        names = enumerate_devices()
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
        if initialize_selected_devices(fill_idx, key_idx, test_video_mode_details):
            print("Devices initialized successfully.")
        self._update_ui_state()

    def on_shutdown_devices(self):
        shutdown_selected_devices()
        print("Devices shut down.")
        self._update_ui_state()

    def on_shutdown_sdk(self):
        shutdown_sdk() # This will also attempt to shut down devices if they are active
        print("SDK (and any active devices) shut down.")
        self.lbl_api_version.setText("DeckLink API Version: N/A") # Reset on SDK shutdown
        self._update_ui_state()

    def on_send_color(self, qcolor: QColor, is_fill_target: bool):
        if not decklink_initialized_successfully:
            print("Devices not initialized. Cannot send color.")
            return

        if is_fill_target:
            fill_c = qcolor
            key_c = self.last_key_color # Use last known key color
            self.last_fill_color = fill_c # Update last fill color
        else: # is_key_target
            key_c = qcolor
            fill_c = self.last_fill_color # Use last known fill color
            self.last_key_color = key_c # Update last key color


        fill_data, key_data = create_solid_color_fill_and_key_images(DLL_WIDTH, DLL_HEIGHT, fill_c, key_c)
        if fill_data and key_data:
            if send_external_keying_frames(fill_data, key_data):
                target_name = "Fill" if is_fill_target else "Key"
                print(f"Sent {qcolor.name()} to {target_name} output.")
            else:
                print(f"Failed to send color frame.")
        else:
            print(f"Failed to generate image data for color.")

    def on_toggle_keyer(self, checked):
        if checked:
            enable_keyer(is_external=True)
        else:
            disable_keyer()
        self._update_ui_state() # Slider enable state depends on this

    def on_set_keyer_level(self, value):
        self.lbl_keyer_level.setText(f"Level: {value}")
        set_keyer_level(value)

    def closeEvent(self, event):
        """Ensure SDK is shut down when GUI closes."""
        print("Closing application, ensuring DeckLink SDK is shut down...")
        shutdown_sdk()
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