import os
import ctypes
import sys
import time # Added for the test section

# --- DeckLink DLL Configuration ---
DLL_NAME = "DeckLinkWraper.dll" # Updated to match the C++ project output
S_OK = 0  # HRESULT success code
DLL_WIDTH = 1920  # Match C++
DLL_HEIGHT = 1080 # Match C++
# Common frame rates (numerator, denominator)
# DeckLink API uses (TimeScale, Duration) which corresponds to (Numerator, Denominator)
FRAME_RATE_5994 = (60000, 1001)
FRAME_RATE_60 = (60, 1) # Or (60000, 1000)

# Define HRESULT type for convenience, typically a long int on Windows
HRESULT = ctypes.c_long

decklink_dll = None
decklink_initialized_successfully = False

# --- Expected DLL Function Signatures ---
# Store expected functions and their ctypes setup
EXPECTED_FUNCTIONS = {
    "InitializeDLL": {"restype": HRESULT, "argtypes": []},
    "ShutdownDLL": {"restype": HRESULT, "argtypes": []},
    "GetDeviceCount": {"restype": HRESULT, "argtypes": [ctypes.POINTER(ctypes.c_int)]},
    "GetDeviceName": {"restype": HRESULT, "argtypes": [ctypes.c_int, ctypes.c_char_p, ctypes.c_int]},
    "InitializeDevice": {"restype": HRESULT, "argtypes": [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]}, # index, w, h, frNum, frDenom
    "ShutdownDevice": {"restype": HRESULT, "argtypes": []},
    "UpdateOutputFrame": {"restype": HRESULT, "argtypes": [ctypes.POINTER(ctypes.c_ubyte)]},
    # Keyer functions (adjust names if your DLL uses different ones)
    "EnableKeyer": {"restype": HRESULT, "argtypes": [ctypes.c_bool]},
    "DisableKeyer": {"restype": HRESULT, "argtypes": []},
    "SetKeyerLevel": {"restype": HRESULT, "argtypes": [ctypes.c_ubyte]},
    "IsKeyerActive": {"restype": HRESULT, "argtypes": [ctypes.POINTER(ctypes.c_bool)]}
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

def initialize_output():
    global decklink_initialized_successfully
    if not decklink_dll:
        if not load_dll():
            print("DeckLink DLL not loaded and failed to load, cannot initialize.", file=sys.stderr)
            return False
    
    if not hasattr(decklink_dll, "InitializeDLL"):
        print("Error: InitializeDLL function not found in DLL. Cannot initialize.", file=sys.stderr)
        return False
    
    # --- 1. Initialize the DLL itself (COM, DeckLink Iterator) ---
    hr = decklink_dll.InitializeDLL()
    if hr != S_OK:
        print(f"DeckLink InitializeDLL failed with HRESULT: {hr:#010x}", file=sys.stderr)
        decklink_initialized_successfully = False
        return False
    print("DeckLink DLL (API level) Initialized successfully.")

    # --- 2. Enumerate Devices ---
    if not hasattr(decklink_dll, "GetDeviceCount") or not hasattr(decklink_dll, "GetDeviceName"):
        print("Error: GetDeviceCount or GetDeviceName not found in DLL. Cannot enumerate devices.", file=sys.stderr)
        # Consider shutting down DLL here if this is critical
        decklink_dll.ShutdownDLL()
        return False

    device_count = ctypes.c_int(0)
    hr = decklink_dll.GetDeviceCount(ctypes.byref(device_count))
    if hr != S_OK:
        print(f"GetDeviceCount failed with HRESULT: {hr:#010x}", file=sys.stderr)
        decklink_dll.ShutdownDLL()
        return False
    
    if device_count.value == 0:
        print("No DeckLink devices found.")
        decklink_dll.ShutdownDLL() # No devices, so shut down the API level too
        return False

    print(f"Found {device_count.value} DeckLink device(s):")
    device_names = []
    for i in range(device_count.value):
        name_buffer = ctypes.create_string_buffer(256) # Max length for device name
        hr = decklink_dll.GetDeviceName(i, name_buffer, ctypes.sizeof(name_buffer))
        if hr == S_OK:
            device_name = name_buffer.value.decode('utf-8')
            print(f"  Device {i}: {device_name}")
            device_names.append(device_name)
        else:
            print(f"  Device {i}: Failed to get name (HRESULT: {hr:#010x})")
            device_names.append(f"Unknown Device {i}")

    # --- 3. Initialize a specific device (e.g., the first one) ---
    # In a real app, you'd let the user choose or have a config.
    selected_device_index = 0 # For simplicity, pick the first one
    print(f"Attempting to initialize device {selected_device_index}: {device_names[selected_device_index]} for output...")
    
    if not hasattr(decklink_dll, "InitializeDevice"):
        print("Error: InitializeDevice function not found in DLL.", file=sys.stderr)
        decklink_dll.ShutdownDLL()
        return False

    # Using 1920x1080 @ 59.94 fps as an example
    hr = decklink_dll.InitializeDevice(selected_device_index, DLL_WIDTH, DLL_HEIGHT, FRAME_RATE_5994[0], FRAME_RATE_5994[1])
    if hr != S_OK:
        print(f"InitializeDevice failed for device {selected_device_index} with HRESULT: {hr:#010x}", file=sys.stderr)
        decklink_dll.ShutdownDLL()
        return False

    print(f"DeckLink device '{device_names[selected_device_index]}' initialized successfully for {DLL_WIDTH}x{DLL_HEIGHT}@{FRAME_RATE_5994[0]}/{FRAME_RATE_5994[1]} FPS.")
    decklink_initialized_successfully = True # This now means a device is ready for output
    return True

def shutdown_output():
    global decklink_initialized_successfully
    if decklink_dll and decklink_initialized_successfully:
        if hasattr(decklink_dll, "DisableKeyer"): # Attempt to disable keyer before shutdown if active
            print("Attempting to disable keyer before shutdown...") # Ensure keyer is off before device shutdown
            disable_keyer()
        else:
            print("DisableKeyer function not found, skipping explicit keyer disable on shutdown.")

        # --- 1. Shutdown the initialized device ---
        if hasattr(decklink_dll, "ShutdownDevice"):
            print("Shutting down active DeckLink device...")
            hr_dev_shutdown = decklink_dll.ShutdownDevice()
            if hr_dev_shutdown != S_OK:
                print(f"DeckLink ShutdownDevice failed with HRESULT: {hr_dev_shutdown:#010x}", file=sys.stderr)
            else:
                print("DeckLink device shutdown complete.")
        else:
            print("Error: ShutdownDevice function not found in DLL. Cannot shutdown device properly.", file=sys.stderr)

        # --- 2. Shutdown the DLL (API level) ---
        if not hasattr(decklink_dll, "ShutdownDLL"):
            print("Error: ShutdownDLL function not found in DLL. Cannot shutdown API properly.", file=sys.stderr)
            decklink_initialized_successfully = False # Still mark as not init
            return

        hr = decklink_dll.ShutdownDLL()
        if hr != S_OK:
            print(f"DeckLink ShutdownDLL failed with HRESULT: {hr:#010x}", file=sys.stderr)
        else:
            print("DeckLink API (DLL level) Shutdown complete.")
    elif decklink_dll: # DLL loaded but device init might have failed or not attempted
        print("DeckLink device was not successfully initialized or DLL was loaded but not fully initialized. Attempting API level shutdown if possible.")
        if hasattr(decklink_dll, "ShutdownDLL"):
            decklink_dll.ShutdownDLL()
            print("DeckLink API (DLL level) Shutdown attempted.")
    else:
        print("DeckLink DLL not loaded, nothing to shut down.")
    decklink_initialized_successfully = False # Always reset this flag



def send_frame(image_bgra_bytes):
    if not decklink_dll or not decklink_initialized_successfully:
        return False
    
    if not hasattr(decklink_dll, "UpdateOutputFrame"):
        print("Error: UpdateOutputFrame function not found in DLL.", file=sys.stderr)
        return False
        
    if len(image_bgra_bytes) != DLL_WIDTH * DLL_HEIGHT * 4:
        print(f"Error: Frame size mismatch. Expected {DLL_WIDTH * DLL_HEIGHT * 4} bytes, got {len(image_bgra_bytes)} bytes.", file=sys.stderr)
        return False

    c_image_data = (ctypes.c_ubyte * len(image_bgra_bytes)).from_buffer_copy(image_bgra_bytes)
    hr = decklink_dll.UpdateOutputFrame(c_image_data)
    if hr != S_OK:
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
        print(f"EnableKeyer failed with HRESULT: {hr:#010x}", file=sys.stderr)
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
        print(f"DisableKeyer failed with HRESULT: {hr:#010x}", file=sys.stderr)
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
        print(f"SetKeyerLevel failed with HRESULT: {hr:#010x}", file=sys.stderr)
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
        print(f"IsKeyerActive failed with HRESULT: {hr:#010x}", file=sys.stderr)
        return None # Undetermined
    
    status = is_active_ptr.contents.value
    print(f"Keyer is currently {'active' if status else 'inactive'}.")
    return status

if __name__ == "__main__":
    print("--- Starting DeckLink Handler Test ---")

    if load_dll():
        # DLL loaded, interfaces checked within load_dll()
        if initialize_output():
            print("\nDeckLink initialization successful.")
            print(f"Output should be active at {DLL_WIDTH}x{DLL_HEIGHT} {FRAME_RATE_5994[0]}/{FRAME_RATE_5994[1]} FPS.")

            
            frame_size = DLL_WIDTH * DLL_HEIGHT * 4
            
            # --- Send some test frames ---
            print("\n--- Sending Test Frames ---")
            black_frame_bytes = bytearray(frame_size)
            for i in range(DLL_WIDTH * DLL_HEIGHT):
                black_frame_bytes[i*4 + 0] = 0   # B
                black_frame_bytes[i*4 + 1] = 0   # G
                black_frame_bytes[i*4 + 2] = 0   # R
                black_frame_bytes[i*4 + 3] = 255 # A (opaque)

            print("Sending a black frame...")
            if send_frame(black_frame_bytes):
                print("Black frame sent successfully. Check your DeckLink output.")
            else:
                print("Failed to send black frame.")

            time.sleep(3)
            
            white_frame_bytes = bytearray(frame_size)
            for i in range(DLL_WIDTH * DLL_HEIGHT):
                white_frame_bytes[i*4 + 0] = 255 # B
                white_frame_bytes[i*4 + 1] = 255 # G
                white_frame_bytes[i*4 + 2] = 255 # R
                white_frame_bytes[i*4 + 3] = 255 # A (opaque)
            
            print("Sending a white frame...")
            if send_frame(white_frame_bytes):
                print("White frame sent. Check DeckLink output.")
            else:
                print("Failed to send white frame.")
            time.sleep(3)

            # --- Test External Keying ---
            print("\n--- Testing External Keyer ---")
            if hasattr(decklink_dll, "EnableKeyer") and \
               hasattr(decklink_dll, "SetKeyerLevel") and \
               hasattr(decklink_dll, "DisableKeyer"):

                if is_keyer_active() is not None: # Check initial state if function exists
                    pass 

                if enable_keyer(is_external=True):
                    print("External keyer enabled. Waiting for 5 seconds...")
                    time.sleep(2) # Short sleep to see if it's on

                    if set_keyer_level(128): # 50% opacity
                        print("Keyer level set to 128 (50%). Waiting for 5 seconds...")
                        print("You should see the key applied over your external source if connected.")
                        time.sleep(5)
                    
                    if is_keyer_active() is not None: # Check state again
                        pass

                    if set_keyer_level(255): # 100% opacity (fully keyed image)
                        print("Keyer level set to 255 (100%). Waiting for 5 seconds...")
                        time.sleep(5)

                    if disable_keyer():
                        print("External keyer disabled. Waiting for 3 seconds...")
                        time.sleep(3)
                    else:
                        print("Failed to disable keyer.")
                else:
                    print("Failed to enable keyer.")
            else:
                print("One or more keyer functions (EnableKeyer, SetKeyerLevel, DisableKeyer) not found in DLL. Skipping keyer test.")

            shutdown_output()
        else:
            print("DeckLink initialization failed.")
            shutdown_output() # Attempt cleanup even if init failed but DLL loaded
    else:
        print("DLL failed to load. Cannot proceed with DeckLink tests.")

    print("\n--- DeckLink Handler Test Finished ---")