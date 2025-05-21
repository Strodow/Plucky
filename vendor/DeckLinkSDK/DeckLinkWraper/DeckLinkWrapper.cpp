// DeckLinkWrapper.cpp

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <objbase.h>    // For CoInitializeEx, CoUninitialize, CoCreateInstance
#include <comutil.h>    // For _bstr_t (requires linking comsuppw.lib or comsuppwd.lib)
#include <vector>
#include <string>
#include <strsafe.h> 
#include <iostream>     // For debug prints, consider replacing for release

#include "DeckLinkAPI_h.h" // DeckLink SDK header. Ensure this path is correct for your project.
                           // You will also need to include DeckLinkAPI_i.c or its compiled .obj
                           // in your project for the IID/CLSID definitions.

// Link with comsuppw.lib (or comsuppwd.lib for debug) for _bstr_t
#pragma comment(lib, "comsuppw.lib")

// Define for DLL export
#ifndef DLL_EXPORT
#define DLL_EXPORT extern "C" __declspec(dllexport)
#endif

// --- Global DeckLink SDK objects and state ---
static IDeckLinkIterator* g_deckLinkIterator = nullptr;
static IDeckLinkProfileManager* g_deckLinkProfileManager = nullptr; // For profile-aware enumeration
static IDeckLinkProfile*  g_activeCardProfile = nullptr;  // Active profile

static IDeckLinkAPIInformation* g_deckLinkAPIInformation = nullptr; // For API version
static std::vector<IDeckLink*>          g_deckLinkDevices; // Stores discovered DeckLink devices (AddRef'd)
static std::vector<std::string>         g_deckLinkDeviceNames;

// --- Profile Information Globals ---
static std::vector<IDeckLinkProfile*>   g_availableProfiles; // Stores all discoverable profiles (AddRef'd)
static std::vector<std::string>         g_availableProfileNames;

// --- Fill Output Globals ---
static IDeckLink* g_fillDeckLink = nullptr;
static IDeckLinkOutput* g_fillDeckLinkOutput = nullptr;
static IDeckLinkMutableVideoFrame* g_fillVideoFrame = nullptr;
static IDeckLinkConfiguration* g_fillDeckLinkConfiguration = nullptr; // Configuration for the fill device
static IDeckLinkKeyer* g_fillDeckLinkKeyer = nullptr;     // Keyer interface from the fill device

// --- Key Output Globals (for external keying) ---
static IDeckLink* g_keyDeckLink = nullptr;
static IDeckLinkOutput* g_keyDeckLinkOutput = nullptr;
static IDeckLinkMutableVideoFrame* g_keyVideoFrame = nullptr;
// Note: Key output typically doesn't need its own IDeckLinkKeyer or IDeckLinkConfiguration for this scenario.

static long                             g_commonFrameWidth = 0;
static long                             g_commonFrameHeight = 0;
static BMDPixelFormat                   g_commonPixelFormat = bmdFormat8BitBGRA; // For both fill and key
static BMDTimeValue                     g_commonFrameDuration = 0;
static BMDTimeScale                     g_commonTimeScale = 0;

static bool                             g_comInitialized = false;
static bool                             g_dllInitialized = false; // Tracks if InitializeDLL has been successfully called
static bool                             g_fillDeviceInitialized = false;
static bool                             g_keyDeviceInitialized = false; // For external key output
static bool                             g_keyerEnabled = false;

// --- Helper Functions ---
std::string BSTRToStdString(BSTR bstr) {
    if (!bstr) return "";
    // _bstr_t constructor with false means it will call SysFreeString on destruction
    // and does not AddRef the BSTR. This is correct for BSTRs returned by
    // methods like GetModelName where ownership is transferred.
    _bstr_t bstrWrapper(bstr, false);
    return std::string(static_cast<const char*>(bstrWrapper));
}

void LogMessage(const char* message) {
    // Simple console log. Replace with a more robust logging mechanism if needed.
    std::cout << "[DeckLinkWrapper] " << message << std::endl;
}

// Helper function to convert BMDProfileID to a human-readable string
std::string BMDProfileIDToString(BMDProfileID profileID) {
    switch (profileID) {
        case bmdProfileOneSubDeviceFullDuplex:
            return "1 SubDevice Full Duplex";
        case bmdProfileOneSubDeviceHalfDuplex:
            return "1 SubDevice Half Duplex";
        case bmdProfileTwoSubDevicesFullDuplex:
            return "2 SubDevices Full Duplex";
        case bmdProfileTwoSubDevicesHalfDuplex:
            return "2 SubDevices Half Duplex";
        case bmdProfileFourSubDevicesHalfDuplex:
            return "4 SubDevices Half Duplex";
        // Add any other BMDProfileID enum values defined in your DeckLinkAPI_h.h
        default:
            char buf[64];
            sprintf_s(buf, sizeof(buf), "Unknown Profile ID (0x%08X)", static_cast<unsigned int>(profileID));
            return std::string(buf);
    }
}
void ReleaseSelectedDeviceResources() {
    // --- Release Fill Device Resources ---
    if (g_keyerEnabled && g_fillDeckLinkKeyer) {
        g_fillDeckLinkKeyer->Disable(); // Best effort to disable
        g_keyerEnabled = false;
    }
    if (g_fillDeckLinkKeyer) {
        g_fillDeckLinkKeyer->Release();
        g_fillDeckLinkKeyer = nullptr;
    }
    if (g_fillDeckLinkConfiguration) {
        g_fillDeckLinkConfiguration->Release();
        g_fillDeckLinkConfiguration = nullptr;
    }
    if (g_fillDeviceInitialized && g_fillDeckLinkOutput) {
        g_fillDeckLinkOutput->DisableVideoOutput(); // Best effort
    }
    if (g_fillVideoFrame) {
        g_fillVideoFrame->Release();
        g_fillVideoFrame = nullptr;
    }
    if (g_fillDeckLinkOutput) {
        g_fillDeckLinkOutput->Release();
        g_fillDeckLinkOutput = nullptr;
    }
    g_fillDeckLink = nullptr; // Points to an item in g_deckLinkDevices
    g_fillDeviceInitialized = false;

    // --- Release Key Device Resources (if used for external keying) ---
    if (g_keyDeviceInitialized && g_keyDeckLinkOutput) {
        g_keyDeckLinkOutput->DisableVideoOutput(); // Best effort
    }
    if (g_keyVideoFrame) {
        g_keyVideoFrame->Release();
        g_keyVideoFrame = nullptr;
    }
    if (g_keyDeckLinkOutput) {
        g_keyDeckLinkOutput->Release();
        g_keyDeckLinkOutput = nullptr;
    }
    g_keyDeckLink = nullptr; // Points to an item in g_deckLinkDevices
    g_keyDeviceInitialized = false;

    // Reset common properties
    g_commonFrameWidth = 0;
    g_commonFrameHeight = 0;
    // g_commonPixelFormat remains bmdFormat8BitBGRA
    g_commonFrameDuration = 0;
    g_commonTimeScale = 0;

    LogMessage("Selected device resources released.");
}

// Forward declaration for ShutdownDevice, as it's called by ShutdownDLL
// Removed forward declaration, as definition appears before its call by ShutdownDLL

// --- DLL Exported Functions ---

DLL_EXPORT HRESULT InitializeDLL() {
    if (g_dllInitialized) {
        LogMessage("DLL already initialized.");
        return S_OK;
    }

    if (!g_comInitialized) {
        HRESULT hr_com = CoInitializeEx(NULL, COINIT_MULTITHREADED);
        if (hr_com == RPC_E_CHANGED_MODE) {
            // LogMessage("CoInitializeEx (MTA) failed: RPC_E_CHANGED_MODE. Thread likely already STA. Retrying with COINIT_APARTMENTTHREADED.");
            hr_com = CoInitializeEx(NULL, COINIT_APARTMENTTHREADED); // Try STA
            if (SUCCEEDED(hr_com)) {
                // LogMessage("COM Initialized (ApartmentThreaded on this thread) successfully as fallback.");
                // Note: DeckLink objects created on this thread will be STA.
                // This might have implications if they are accessed from other threads.
            } else {
                // LogMessage("CoInitializeEx (STA fallback) also failed.");
                // Log the specific HRESULT for the STA failure
                char err_msg[100];
                sprintf_s(err_msg, sizeof(err_msg), "STA CoInitializeEx failed with HRESULT: 0x%08X", static_cast<unsigned int>(hr_com));
                LogMessage(err_msg);
                return hr_com; // Return the error from the STA attempt
            }
        } else if (FAILED(hr_com)) {
            // LogMessage("CoInitializeEx (MTA) failed with a different error.");
            return hr_com;
        }
        g_comInitialized = true;
        // LogMessage("COM Initialized by DLL successfully.");
    }
    
    // First, ensure we have an iterator to find a physical card
    if (g_deckLinkIterator == nullptr) {
        HRESULT hr_iter_create = CoCreateInstance(CLSID_CDeckLinkIterator, NULL, CLSCTX_ALL, IID_IDeckLinkIterator, (void**)&g_deckLinkIterator);
        if (FAILED(hr_iter_create) || g_deckLinkIterator == nullptr) {
            LogMessage("Failed to create DeckLink Iterator instance in InitializeDLL.");
            return hr_iter_create;
        }
    }

    // Get the first physical DeckLink card
    IDeckLink* physicalCard = nullptr;
    HRESULT hr_card = g_deckLinkIterator->Next(&physicalCard);
    if (FAILED(hr_card) || physicalCard == nullptr) {
        LogMessage("No DeckLink cards found or failed to get the first card.");
        // g_deckLinkIterator->Release(); // Release iterator if no card found? Or keep for API info?
        // g_deckLinkIterator = nullptr; // Let's keep it for API info for now.
        // No card, so no profile manager from card, and no active profile.
        // GetDeviceCount will return 0. This isn't a fatal error for InitializeDLL itself.
    } else {
        // Log some attributes of the first physical card
        IDeckLinkProfileAttributes* profileAttributes = nullptr; // Corrected interface
        HRESULT hr_attr = physicalCard->QueryInterface(IID_IDeckLinkProfileAttributes, (void**)&profileAttributes); // Corrected IID
        if (SUCCEEDED(hr_attr) && profileAttributes != nullptr) {
            BSTR tempBSTR = nullptr;
            if (SUCCEEDED(physicalCard->GetDisplayName(&tempBSTR))) {
                LogMessage(("First physical card Display Name: " + BSTRToStdString(tempBSTR)).c_str());
                // BSTRToStdString with _bstr_t(bstr, false) handles SysFreeString, so no explicit SysFreeString(tempBSTR) needed here.
            }

            long long profileID_ll = 0; 
            if (SUCCEEDED(profileAttributes->GetInt(BMDDeckLinkProfileID, &profileID_ll))) { // Use profileAttributes
                char msg[100];
                sprintf_s(msg, sizeof(msg), "First physical card BMDDeckLinkProfileID: %lld", profileID_ll);
                LogMessage(msg);
            }

            BOOL internalKeying = FALSE;
            if (SUCCEEDED(profileAttributes->GetFlag(BMDDeckLinkSupportsInternalKeying, &internalKeying))) { // Use profileAttributes
                LogMessage(internalKeying ? "First physical card supports Internal Keying." : "First physical card does NOT support Internal Keying.");
            }
            BOOL externalKeying = FALSE;
            if (SUCCEEDED(profileAttributes->GetFlag(BMDDeckLinkSupportsExternalKeying, &externalKeying))) { // Use profileAttributes
                LogMessage(externalKeying ? "First physical card supports External Keying." : "First physical card does NOT support External Keying.");
            }

            profileAttributes->Release(); // Release the correct interface
        }

        // Now, obtain IDeckLinkProfileManager from the specific physicalCard
        if (g_deckLinkProfileManager == nullptr) {
            HRESULT hr_pm = physicalCard->QueryInterface(IID_IDeckLinkProfileManager, (void**)&g_deckLinkProfileManager);
            if (FAILED(hr_pm) || g_deckLinkProfileManager == nullptr) {
                LogMessage("Failed to query IDeckLinkProfileManager from the DeckLink card.");
                // Proceeding without profile manager means GetDeviceCount might not use profile-specific enumeration.
            }
        }
        physicalCard->Release(); // We're done with this specific card instance for now
    }

    // Populate available profiles and find the active one
    if (g_deckLinkProfileManager != nullptr) {
        // Clear previous profile lists
        for (IDeckLinkProfile* prof : g_availableProfiles) {
            if (prof) prof->Release();
        }
        g_availableProfiles.clear();
        g_availableProfileNames.clear();
        if (g_activeCardProfile) { // Release previous active if any
            g_activeCardProfile->Release();
            g_activeCardProfile = nullptr;
        }

        IDeckLinkProfileIterator* profileIterator = nullptr;
        HRESULT hr_iter = g_deckLinkProfileManager->GetProfiles(&profileIterator);
        if (SUCCEEDED(hr_iter) && profileIterator != nullptr) {
            IDeckLinkProfile* currentProfile = nullptr;
            while (profileIterator->Next(&currentProfile) == S_OK) {
                g_availableProfiles.push_back(currentProfile); // currentProfile is AddRef'd by Next(), store it
                
                std::string profileNameStr = "Profile (Name N/A)"; // Default
                IDeckLink* associatedDevice = nullptr;
                if (SUCCEEDED(currentProfile->GetDevice(&associatedDevice)) && associatedDevice != nullptr) {
                    IDeckLinkProfileAttributes* deviceAttributes = nullptr;
                    if (SUCCEEDED(associatedDevice->QueryInterface(IID_IDeckLinkProfileAttributes, (void**)&deviceAttributes)) && deviceAttributes != nullptr) {
                        LONGLONG profileID_ll = 0;
                        if (SUCCEEDED(deviceAttributes->GetInt(BMDDeckLinkProfileID, &profileID_ll))) {
                            profileNameStr = BMDProfileIDToString(static_cast<BMDProfileID>(profileID_ll));
                        } else {
                            LogMessage("Failed to get BMDDeckLinkProfileID attribute for a profile's device.");
                        }
                        deviceAttributes->Release();
                    } else {
                        LogMessage("Failed to QI for IDeckLinkProfileAttributes from profile's device.");
                    }
                    associatedDevice->Release();
                } else {
                    LogMessage("Failed to get device associated with a profile.");
                }
                g_availableProfileNames.push_back(profileNameStr);

                BOOL isActive = FALSE;
                // If g_activeCardProfile is not yet set and this one is active, mark it.
                if (g_activeCardProfile == nullptr && SUCCEEDED(currentProfile->IsActive(&isActive)) && isActive) {
                    g_activeCardProfile = currentProfile;
                    g_activeCardProfile->AddRef(); // AddRef specifically for g_activeCardProfile
                    // LogMessage("Found active DeckLink profile.");
                    // Don't break, continue to populate all available profiles
                }
                // currentProfile is now stored in g_availableProfiles, its ref count is managed there.
            }
            profileIterator->Release();
        } else {
            LogMessage("Failed to get profile iterator from DeckLink Profile Manager.");
        }
    }

    // Get API Information from the Profile Manager (or fallback to iterator if needed)
    if (g_deckLinkAPIInformation == nullptr) {
        if (g_deckLinkProfileManager) {
            HRESULT hr_api_info = g_deckLinkProfileManager->QueryInterface(IID_IDeckLinkAPIInformation, (void**)&g_deckLinkAPIInformation);
            if (SUCCEEDED(hr_api_info) && g_deckLinkAPIInformation != nullptr) {
                // LogMessage("Successfully queried IDeckLinkAPIInformation from Profile Manager.");
            }
        } else if (g_deckLinkIterator) { // Fallback to iterator if profile manager wasn't obtained
            HRESULT hr_api_info = g_deckLinkIterator->QueryInterface(IID_IDeckLinkAPIInformation, (void**)&g_deckLinkAPIInformation);
            if (SUCCEEDED(hr_api_info) && g_deckLinkAPIInformation != nullptr) {
                // LogMessage("Successfully queried IDeckLinkAPIInformation from Iterator (fallback).");
            }
        }
    }

    g_dllInitialized = true;
    // LogMessage("DeckLink DLL Initialized successfully."); // Python side will confirm
    return S_OK;
}

// Define ShutdownDevice before ShutdownDLL because ShutdownDLL calls it.
DLL_EXPORT HRESULT ShutdownDevice() {
    if (!g_dllInitialized && !g_comInitialized) {
        // LogMessage("ShutdownDevice called when DLL/COM not initialized.");
        return S_OK;
    }
    if (!g_dllInitialized && g_comInitialized && !g_fillDeviceInitialized && !g_keyDeviceInitialized) {
         // LogMessage("ShutdownDevice called when DLL not initialized but COM was; no devices active.");
         return S_OK;
    }
    if (!g_dllInitialized && (g_fillDeviceInitialized || g_keyDeviceInitialized)){
        LogMessage("Error: Devices appear initialized but DLL is not. This is an inconsistent state.");
        // Attempt cleanup anyway
    }

    if (!g_fillDeviceInitialized && !g_keyDeviceInitialized && !g_fillDeckLink && !g_keyDeckLink) {
        // LogMessage("Device already shut down or not initialized.");
        return S_OK;
    }
    ReleaseSelectedDeviceResources(); // This handles disabling output, keyer, and releasing interfaces
    // LogMessage("Selected device has been shut down."); // Python side will confirm
    return S_OK;
}

DLL_EXPORT HRESULT ShutdownDLL() {
    if (!g_dllInitialized) {
        LogMessage("DLL not initialized or already shut down.");
        // If COM was initialized independently, we might still want to CoUninitialize if we were the last user.
        // However, strict pairing of InitializeDLL/ShutdownDLL is better.
        // If only COM was initialized but not the DLL, CoUninitialize if g_comInitialized is true.
        if (g_comInitialized && !g_dllInitialized) { // Edge case: COM init but DLL init failed or was never called
            CoUninitialize();
            g_comInitialized = false;
            // LogMessage("COM Uninitialized (ShutdownDLL called when DLL not fully initialized).");
        }
        return S_OK;
    }

    // Call ShutdownDevice only if it appears a device might still be active.
    // This avoids the "already shut down" log if the caller (e.g., Python)
    // has already explicitly called ShutdownDevice().
    if (g_fillDeviceInitialized || g_keyDeviceInitialized || g_fillDeckLink || g_keyDeckLink) {
        // LogMessage("ShutdownDLL: An active device was detected; ensuring it is shut down.");
        ShutdownDevice();
    }

    for (IDeckLink* dev : g_deckLinkDevices) {
        if (dev) dev->Release();
    }
    g_deckLinkDevices.clear();
    g_deckLinkDeviceNames.clear();

    // Release available profiles
    for (IDeckLinkProfile* prof : g_availableProfiles) {
        if (prof) prof->Release();
    }
    g_availableProfiles.clear();
    g_availableProfileNames.clear();

    if (g_activeCardProfile) {
        g_activeCardProfile->Release();
        g_activeCardProfile = nullptr;
    }
    if (g_deckLinkIterator) {
        g_deckLinkIterator->Release();
        g_deckLinkIterator = nullptr;
    }

    if (g_deckLinkAPIInformation) {
        g_deckLinkAPIInformation->Release();
        g_deckLinkAPIInformation = nullptr;
    }

    if (g_deckLinkProfileManager) {
        g_deckLinkProfileManager->Release();
        g_deckLinkProfileManager = nullptr;
    }

    if (g_comInitialized) {
        CoUninitialize();
        g_comInitialized = false;
        // LogMessage("COM Uninitialized.");
    }

    g_dllInitialized = false;
    // LogMessage("DeckLink DLL Shutdown complete."); // Python side will confirm
    return S_OK;
}

DLL_EXPORT HRESULT GetDeviceCount(int* count_out) { // Changed parameter name for clarity
    if (!g_dllInitialized) { // Iterator is now managed within this function
        LogMessage("GetDeviceCount: DLL not initialized. Call InitializeDLL first.");
        return E_FAIL;
    }
    if (!count_out) { LogMessage("GetDeviceCount: count_out pointer is null."); return E_POINTER; }

    *count_out = 0; // Default to zero

    // Clear previous enumeration results
    for (IDeckLink* dev : g_deckLinkDevices) {
        if (dev) dev->Release();
    }
    g_deckLinkDevices.clear();
    g_deckLinkDeviceNames.clear();

    // Use IDeckLinkIterator to enumerate available devices.
    // This iterator will list devices active under the current profile.
    if (g_deckLinkIterator == nullptr) {
        // This case should ideally not be hit if InitializeDLL was successful,
        // but as a safeguard, try to create it.
        HRESULT hr_iter_create = CoCreateInstance(CLSID_CDeckLinkIterator, NULL, CLSCTX_ALL, IID_IDeckLinkIterator, (void**)&g_deckLinkIterator);
        if (FAILED(hr_iter_create) || g_deckLinkIterator == nullptr) {
            LogMessage("GetDeviceCount: Failed to create DeckLink Iterator (was null).");
            return hr_iter_create;
        }
    } else {
        // If iterator exists, we need to "reset" it to enumerate from the beginning.
        // IDeckLinkIterator doesn't have a Reset(). Release and recreate.
        g_deckLinkIterator->Release();
        g_deckLinkIterator = nullptr; // Nullify before CoCreateInstance
        HRESULT hr_iter_recreate = CoCreateInstance(CLSID_CDeckLinkIterator, NULL, CLSCTX_ALL, IID_IDeckLinkIterator, (void**)&g_deckLinkIterator);
        if (FAILED(hr_iter_recreate) || g_deckLinkIterator == nullptr) {
            LogMessage("GetDeviceCount: Failed to re-create DeckLink Iterator.");
            return hr_iter_recreate;
        }
    }

    IDeckLink* tempDeckLink = nullptr;
    HRESULT hr_next;
    while ((hr_next = g_deckLinkIterator->Next(&tempDeckLink)) == S_OK) {
        if (tempDeckLink != nullptr) { // Should always be non-null if S_OK
            BSTR deviceNameBSTR = nullptr;
            // GetModelName or GetDisplayName can be used. GetDisplayName might be more specific for sub-devices.
            if (tempDeckLink->GetDisplayName(&deviceNameBSTR) == S_OK) {
                g_deckLinkDevices.push_back(tempDeckLink); // tempDeckLink is AddRef'd by Next(), store it
                g_deckLinkDeviceNames.push_back(BSTRToStdString(deviceNameBSTR)); // BSTRToStdString handles freeing deviceNameBSTR
                // SysFreeString(deviceNameBSTR); // REMOVE: BSTRToStdString handles freeing deviceNameBSTR
            } else {
                LogMessage("Failed to get device name during enumeration via IDeckLinkIterator.");
                tempDeckLink->Release(); // Release if not stored
            }
            // tempDeckLink is now stored or released.
        }
    }
    // If hr_next is S_FALSE, it means no more items, which is normal.
    // If hr_next is a failure HRESULT, it will be returned by the caller of GetDeviceCount.

    *count_out = static_cast<int>(g_deckLinkDevices.size());
    // LogMessage(("Found " + std::to_string(*count) + " DeckLink devices.").c_str()); // Python side will log this
    return S_OK;
}

DLL_EXPORT HRESULT GetDeviceName(int index, char* nameBuffer, int bufferLength) {
    if (!g_dllInitialized) return E_FAIL;
    if (!nameBuffer) {
        LogMessage("GetDeviceName: nameBuffer is null.");
        return E_POINTER;
    }
    if (index < 0 || index >= static_cast<int>(g_deckLinkDeviceNames.size())) {
        return E_INVALIDARG;
    }

    const std::string& name = g_deckLinkDeviceNames[index];
    if (strncpy_s(nameBuffer, bufferLength, name.c_str(), _TRUNCATE) != 0) {
        if (bufferLength > 0) nameBuffer[0] = '\0'; // Ensure null termination on error
        return STRSAFE_E_INSUFFICIENT_BUFFER; // More specific error
    }
    return S_OK;
}

DLL_EXPORT HRESULT GetAvailableProfileCount(int* count_out) {
    if (!g_dllInitialized) {
        LogMessage("GetAvailableProfileCount: DLL not initialized.");
        return E_FAIL;
    }
    if (!count_out) return E_POINTER;

    *count_out = static_cast<int>(g_availableProfileNames.size());
    return S_OK;
}

DLL_EXPORT HRESULT GetAvailableProfileName(int index, char* nameBuffer, int bufferLength) {
    if (!g_dllInitialized) return E_FAIL;
    if (!nameBuffer) return E_POINTER;

    if (index < 0 || index >= static_cast<int>(g_availableProfileNames.size())) {
        return E_INVALIDARG;
    }

    const std::string& name = g_availableProfileNames[index];
    if (strncpy_s(nameBuffer, bufferLength, name.c_str(), _TRUNCATE) != 0) {
        if (bufferLength > 0) nameBuffer[0] = '\0';
        return STRSAFE_E_INSUFFICIENT_BUFFER;
    }
    return S_OK;
}

DLL_EXPORT HRESULT GetActiveProfileName(char* nameBuffer, int bufferLength) {
    if (!g_dllInitialized) return E_FAIL;
    if (!nameBuffer) return E_POINTER;

    if (!g_activeCardProfile) {
        LogMessage("GetActiveProfileName: No active profile found or identified.");
        if (bufferLength > 0) nameBuffer[0] = '\0'; // Return empty string
        return S_FALSE; // Indicate not found but not a hard error
    }

    std::string activeProfileNameStr = "Active Profile (Name N/A)"; // Default
    IDeckLink* associatedDevice = nullptr;
    if (SUCCEEDED(g_activeCardProfile->GetDevice(&associatedDevice)) && associatedDevice != nullptr) {
        IDeckLinkProfileAttributes* deviceAttributes = nullptr;
        if (SUCCEEDED(associatedDevice->QueryInterface(IID_IDeckLinkProfileAttributes, (void**)&deviceAttributes)) && deviceAttributes != nullptr) {
            LONGLONG profileID_ll = 0;
            if (SUCCEEDED(deviceAttributes->GetInt(BMDDeckLinkProfileID, &profileID_ll))) {
                activeProfileNameStr = BMDProfileIDToString(static_cast<BMDProfileID>(profileID_ll));
            } else {
                LogMessage("GetActiveProfileName: Failed to get BMDDeckLinkProfileID attribute for active profile's device.");
            }
            deviceAttributes->Release();
        } else {
            LogMessage("GetActiveProfileName: Failed to QI for IDeckLinkProfileAttributes from active profile's device.");
        }
        associatedDevice->Release();
    } else {
        LogMessage("GetActiveProfileName: Failed to get device associated with active profile.");
    }

    if (strncpy_s(nameBuffer, bufferLength, activeProfileNameStr.c_str(), _TRUNCATE) == 0) {
        return S_OK;
    } else {
        if (bufferLength > 0) nameBuffer[0] = '\0'; // Ensure null termination
        return STRSAFE_E_INSUFFICIENT_BUFFER;
    }
}

DLL_EXPORT HRESULT GetAPIVersion(long long* version) { // Use long long for the packed version
    if (!g_dllInitialized) {
        LogMessage("DLL not initialized. Call InitializeDLL first.");
        return E_FAIL;
    }
    if (!version) {
        LogMessage("GetAPIVersion: version pointer is null.");
        return E_POINTER;
    }
    if (!g_deckLinkAPIInformation) {
        LogMessage("IDeckLinkAPIInformation interface not available. Cannot get API version.");
        *version = 0; // Indicate unavailable
        return E_NOINTERFACE; // Or S_FALSE if "not available" is a valid non-error state
    }

    // Get the integer version
    // BMDDeckLinkAPIVersion is the enum value for the integer version
    HRESULT hr = g_deckLinkAPIInformation->GetInt(BMDDeckLinkAPIVersion, version); // BMDDeckLinkAPIVersion is the ID for the integer version
    if (FAILED(hr)) {
        LogMessage("Failed to get API version (GetInt).");
        *version = 0; // Reset on failure
        return hr;
    }

    // Optional: Log the version from C++ side
    // char msg[100];
    // sprintf_s(msg, "API Version (raw int): %lld", *version); LogMessage(msg);
    return S_OK;
}

HRESULT InitializeSingleDeckLinkOutput(IDeckLink* deckLink, int width, int height, int frameRateNum, int frameRateDenom,
                                       IDeckLinkOutput** deckLinkOutput, IDeckLinkMutableVideoFrame** videoFrame,
                                       IDeckLinkConfiguration** deckLinkConfig, IDeckLinkKeyer** deckLinkKeyer, /* Optional for key device */
                                       bool checkKeyingSupport, const std::string& deviceNameForLog) {
    if (!g_dllInitialized) {
        LogMessage("DLL not initialized. Call InitializeDLL first.");
        return E_FAIL;
    }
    if (!deckLink || !deckLinkOutput || !videoFrame) {
        return E_POINTER;
    }

    // Dereference and nullify output pointers to ensure clean state if function fails midway
    *deckLinkOutput = nullptr;
    *videoFrame = nullptr;
    if (deckLinkConfig) *deckLinkConfig = nullptr;
    if (deckLinkKeyer) *deckLinkKeyer = nullptr;

    HRESULT hr = deckLink->QueryInterface(IID_IDeckLinkOutput, (void**)deckLinkOutput);
    if (FAILED(hr) || *deckLinkOutput == nullptr) {
        LogMessage(("Failed to get IDeckLinkOutput interface for " + deviceNameForLog).c_str());
        return hr;
    }

    IDeckLinkDisplayModeIterator* displayModeIterator = nullptr;
    hr = (*deckLinkOutput)->GetDisplayModeIterator(&displayModeIterator);
    if (FAILED(hr) || displayModeIterator == nullptr) {
        LogMessage("Failed to get display mode iterator.");
        if (*deckLinkOutput) {
            (*deckLinkOutput)->Release();
            *deckLinkOutput = nullptr;
        }
        return hr;
    }

    IDeckLinkDisplayMode* selectedDisplayModeObj = nullptr;
    IDeckLinkDisplayMode* currentDisplayMode = nullptr;
    BMDDisplayMode   targetBMDMode = bmdModeUnknown;

    while (displayModeIterator->Next(&currentDisplayMode) == S_OK) {
        if (currentDisplayMode->GetWidth() == width && currentDisplayMode->GetHeight() == height) {
            BMDTimeValue modeFrameDuration;
            BMDTimeScale modeTimeScale;
            currentDisplayMode->GetFrameRate(&modeFrameDuration, &modeTimeScale);

            // Note: DeckLink GetFrameRate gives duration (like 1000 for 30fps) and scale (like 30000 for 30fps)
            // Python provides num (like 30000) and den (like 1000)
            if (modeFrameDuration == frameRateDenom && modeTimeScale == frameRateNum) {
                BOOL modeIsSupported = FALSE; // General support flag
                // Always use bmdSupportedVideoModeDefault for the DoesSupportVideoMode check
                // to ensure we can at least find a basic output mode.
                BMDSupportedVideoModeFlags flagsForDoesSupportCheck = bmdSupportedVideoModeDefault;
                
                // --- DEBUG LOG for supportedFlags ---
                char flagLog[256]; // Increased size
                // sprintf_s(flagLog, sizeof(flagLog), "Device: '%s', (Intended keying: %s), using flagsForDoesSupportCheck value: %d for DoesSupportVideoMode", deviceNameForLog.c_str(), checkKeyingSupport ? "true" : "false", static_cast<int>(flagsForDoesSupportCheck));
                // LogMessage(flagLog); // This was very verbose, remove for now

                hr = (*deckLinkOutput)->DoesSupportVideoMode(
                    bmdVideoConnectionUnspecified, // Check all connections, or specify if known
                    currentDisplayMode->GetDisplayMode(),
                    g_commonPixelFormat, // bmdFormat8BitBGRA
                    bmdNoVideoOutputConversion,
                    flagsForDoesSupportCheck, nullptr, &modeIsSupported
                );

                if (hr == S_OK && modeIsSupported) {
                    selectedDisplayModeObj = currentDisplayMode;
                    selectedDisplayModeObj->AddRef(); // Keep this display mode object
                    targetBMDMode = selectedDisplayModeObj->GetDisplayMode();
                    // Store common mode properties if this is the first successful device init
                    if (g_commonFrameWidth == 0) { // Assuming this is called for fill first
                        g_commonFrameDuration = modeFrameDuration;
                        g_commonTimeScale = modeTimeScale;
                        g_commonFrameWidth = width;
                        g_commonFrameHeight = height;
                    }
                    break;
                }
            }
        }
        currentDisplayMode->Release(); // Release the iterated display mode if not selected
    }
    displayModeIterator->Release();

    if (!selectedDisplayModeObj || targetBMDMode == bmdModeUnknown) {
        LogMessage(("Failed to find a matching display mode for " + deviceNameForLog +
                    (checkKeyingSupport ? " with keying." : ".")).c_str());
        if (*deckLinkOutput) { (*deckLinkOutput)->Release(); *deckLinkOutput = nullptr; }
        return E_FAIL;
    }

    hr = (*deckLinkOutput)->EnableVideoOutput(targetBMDMode, bmdVideoOutputFlagDefault);
    if (FAILED(hr)) {
        LogMessage(("Failed to enable video output on " + deviceNameForLog).c_str());
        selectedDisplayModeObj->Release();
        if (*deckLinkOutput) { (*deckLinkOutput)->Release(); *deckLinkOutput = nullptr; }
        return hr;
    }

    long rowBytes = width * 4; // For bmdFormat8BitBGRA (4 bytes per pixel)
    hr = (*deckLinkOutput)->CreateVideoFrame(width, height, rowBytes,
        g_commonPixelFormat, bmdFrameFlagDefault, videoFrame);
    if (FAILED(hr) || *videoFrame == nullptr) {
        LogMessage(("Failed to create video frame for " + deviceNameForLog).c_str());
        (*deckLinkOutput)->DisableVideoOutput(); // Clean up enabled output
        selectedDisplayModeObj->Release();
        if (*deckLinkOutput) { (*deckLinkOutput)->Release(); *deckLinkOutput = nullptr; }
        return hr;
    }

    // Get Configuration and Keyer interfaces if requested (typically for fill device)
    if (deckLinkConfig) {
        deckLink->QueryInterface(IID_IDeckLinkConfiguration, (void**)deckLinkConfig);
        if (!*deckLinkConfig) LogMessage(("Warning: Could not get IDeckLinkConfiguration for " + deviceNameForLog).c_str());
    }
    if (deckLinkKeyer) {
        if (checkKeyingSupport) { 
            hr = deckLink->QueryInterface(IID_IDeckLinkKeyer, (void**)deckLinkKeyer);
            if (FAILED(hr) || *deckLinkKeyer == nullptr) {
                LogMessage(("Warning: Failed to get IDeckLinkKeyer interface for " + deviceNameForLog + ". SDK-controlled keying will not be available.").c_str());
                // Do NOT fail the entire initialization here for the "full compromise".
                // Allow output to proceed, but SDK keying won't work.
                if (*deckLinkKeyer) { (*deckLinkKeyer)->Release(); *deckLinkKeyer = nullptr; } // Ensure it's null
            } else {
                // LogMessage(("Successfully queried IDeckLinkKeyer for " + deviceNameForLog).c_str());
            }
        }
    }

    selectedDisplayModeObj->Release(); // Release the mode we AddRef'd earlier
    // LogMessage((deviceNameForLog + " initialized for output: " + ... ).c_str()); // Python side will confirm
    return S_OK; // Success
}

DLL_EXPORT HRESULT InitializeDevice(int fillDeviceIndex, int keyDeviceIndex, int width, int height, int frameRateNum, int frameRateDenom) {
    if (!g_dllInitialized) {
        LogMessage("DLL not initialized. Call InitializeDLL first.");
        return E_FAIL;
    }
    if (g_fillDeviceInitialized || g_keyDeviceInitialized) {
        LogMessage("A device is already initialized. Call ShutdownDevice first.");
        return E_FAIL;
    }
    if (fillDeviceIndex < 0 || fillDeviceIndex >= static_cast<int>(g_deckLinkDevices.size()) ||
        keyDeviceIndex < 0 || keyDeviceIndex >= static_cast<int>(g_deckLinkDevices.size())) {
        LogMessage("Invalid device index for fill or key.");
        return E_INVALIDARG;
    }
    if (fillDeviceIndex == keyDeviceIndex) {
        LogMessage("Fill and Key device indices cannot be the same for external keying.");
        return E_INVALIDARG;
    }

    ReleaseSelectedDeviceResources(); // Clear any prior state

    g_fillDeckLink = g_deckLinkDevices[fillDeviceIndex];
    HRESULT hr = InitializeSingleDeckLinkOutput(g_fillDeckLink, width, height, frameRateNum, frameRateDenom,
                                              &g_fillDeckLinkOutput, &g_fillVideoFrame,
                                              &g_fillDeckLinkConfiguration, &g_fillDeckLinkKeyer,
                                              true, g_deckLinkDeviceNames[fillDeviceIndex] + " (Fill)");
    if (FAILED(hr)) {
        LogMessage("Failed to initialize Fill device.");
        ReleaseSelectedDeviceResources(); // Full cleanup
        return hr;
    }
    g_fillDeviceInitialized = true;

    // Initialize Key Device (no keying support check needed for the key output itself, no IDeckLinkKeyer needed for it)
    g_keyDeckLink = g_deckLinkDevices[keyDeviceIndex];
    hr = InitializeSingleDeckLinkOutput(g_keyDeckLink, width, height, frameRateNum, frameRateDenom,
                                          &g_keyDeckLinkOutput, &g_keyVideoFrame,
                                          nullptr, nullptr, // No config or keyer interface needed for the key output device
                                          false, g_deckLinkDeviceNames[keyDeviceIndex] + " (Key)");
    if (FAILED(hr)) {
        LogMessage("Failed to initialize Key device.");
        ReleaseSelectedDeviceResources(); // Full cleanup
        return hr;
    }
    g_keyDeviceInitialized = true;

    return S_OK;
}

DLL_EXPORT HRESULT UpdateExternalKeyingFrames(const unsigned char* fillBgraData, const unsigned char* keyBgraData) {
    if (!g_fillDeviceInitialized || !g_fillVideoFrame || !g_fillDeckLinkOutput ||
        !g_keyDeviceInitialized || !g_keyVideoFrame || !g_keyDeckLinkOutput) {
        LogMessage("Fill or Key device not initialized, or frames not ready for update.");
        return E_FAIL;
    }
    if (!fillBgraData || !keyBgraData) return E_POINTER;

    // --- DIAGNOSTIC LOGGING ---
    // LogMessage(("UpdateExternalKeyingFrames: Common WxH: " + std::to_string(g_commonFrameWidth) + "x" + std::to_string(g_commonFrameHeight)).c_str());
    // char tempLog[200]; // Keep this if you want to debug pixel data issues
    // sprintf_s(tempLog, sizeof(tempLog), "First 4 bytes of fillBgraData: %02X %02X %02X %02X", fillBgraData[0], fillBgraData[1], fillBgraData[2], fillBgraData[3]);
    // LogMessage(tempLog);
    // sprintf_s(tempLog, sizeof(tempLog), "First 4 bytes of keyBgraData: %02X %02X %02X %02X", keyBgraData[0], keyBgraData[1], keyBgraData[2], keyBgraData[3]);
    // LogMessage(tempLog);
    // --- END DIAGNOSTIC LOGGING ---
    void* frameBytes = nullptr;
    HRESULT hr;

    // --- Update Fill Frame ---
    hr = g_fillVideoFrame->GetBytes(&frameBytes);
    if (FAILED(hr) || !frameBytes) {
        LogMessage("Failed to get fill frame buffer pointer.");
        return hr; // Or E_FAIL
    }
    if (frameBytes) {
        memcpy(frameBytes, fillBgraData, g_commonFrameWidth * g_commonFrameHeight * 4);
        // --- DIAGNOSTIC: Read back from fill frame buffer ---
        // unsigned char* pFillBufferBytes = static_cast<unsigned char*>(frameBytes);
        // sprintf_s(tempLog, sizeof(tempLog), "First 4 bytes FROM g_fillVideoFrame after memcpy: %02X %02X %02X %02X", pFillBufferBytes[0], pFillBufferBytes[1], pFillBufferBytes[2], pFillBufferBytes[3]);
        // LogMessage(tempLog);
        // --- END DIAGNOSTIC ---
    } else {
        LogMessage("Fill frame buffer pointer was null."); return E_POINTER;
    }

    // Important: GetBytes for key frame might return the same frameBytes pointer if the SDK optimizes
    // or if there's an issue. For safety, re-nullify or be aware.
    frameBytes = nullptr; 
    // --- Update Key Frame ---
    // Key frame also uses BGRA format where R=G=B=Alpha for grayscale key
    hr = g_keyVideoFrame->GetBytes(&frameBytes);
    if (FAILED(hr) || !frameBytes) {
        LogMessage("Failed to get key frame buffer pointer.");
        return hr;
    }
    if (frameBytes) {
        memcpy(frameBytes, keyBgraData, g_commonFrameWidth * g_commonFrameHeight * 4);
        // --- DIAGNOSTIC: Read back from key frame buffer ---
        // unsigned char* pKeyBufferBytes = static_cast<unsigned char*>(frameBytes);
        // sprintf_s(tempLog, sizeof(tempLog), "First 4 bytes FROM g_keyVideoFrame after memcpy: %02X %02X %02X %02X", pKeyBufferBytes[0], pKeyBufferBytes[1], pKeyBufferBytes[2], pKeyBufferBytes[3]);
        // LogMessage(tempLog);
        // --- END DIAGNOSTIC ---

    } else {
        LogMessage("Key frame buffer pointer was null."); return E_POINTER;
    }

    // --- Schedule Frames ---
    // For external keying, it's crucial these are scheduled as close together as possible.
    // DisplayVideoFrameSync might introduce too much variability if called sequentially.
    // A more robust approach for perfect sync would involve ScheduleVideoFrame.
    // For simplicity in this example, we'll use DisplayVideoFrameSync sequentially.
    // This might be "good enough" for many cases but isn't guaranteed genlock-perfect.

    char tempLog[200]; // Moved here for reuse
    hr = g_fillDeckLinkOutput->DisplayVideoFrameSync(g_fillVideoFrame);
    if (FAILED(hr)) {
        sprintf_s(tempLog, sizeof(tempLog), "DisplayVideoFrameSync failed for Fill frame. HRESULT: 0x%08X", static_cast<unsigned int>(hr));
        LogMessage(tempLog);
        return hr;
    }
    LogMessage("DisplayVideoFrameSync successful for Fill frame.");

    // Re-declare hr for clarity, or just reuse.
    hr = g_keyDeckLinkOutput->DisplayVideoFrameSync(g_keyVideoFrame);
    if (FAILED(hr)) {
        sprintf_s(tempLog, sizeof(tempLog), "DisplayVideoFrameSync failed for Key frame. HRESULT: 0x%08X", static_cast<unsigned int>(hr));
        LogMessage(tempLog);
        // Note: Fill frame was already displayed. State is now a bit inconsistent.
        if (FAILED(hr)) {
            return hr;
        }
    }
    LogMessage("DisplayVideoFrameSync successful for Key frame.");
    return S_OK;
}


DLL_EXPORT HRESULT EnableKeyer(bool useExternalMode) {
    if (!g_fillDeviceInitialized || !g_fillDeckLinkKeyer) { // Keyer is on the fill device
        LogMessage("Cannot enable keyer: Device not initialized or keyer interface not available.");
        return E_FAIL;
    }

    HRESULT hr_conf = S_OK;
    if (g_fillDeckLinkConfiguration) {
        // LogMessage("Attempting to configure keying via IDeckLinkConfiguration..."); // Not currently used

        // Try to set the video output connection to one that supports keying.
        // For SDI, this might be bmdVideoConnectionSDI or a specific one if the card has multiple.
        // This step might not always be necessary or might not change behavior if the output
        // is already implicitly set up by EnableVideoOutput.
        // hr_conf = g_fillDeckLinkConfiguration->SetInt(bmdDeckLinkConfigVideoOutputConnection, bmdVideoConnectionSDI);
        // if (FAILED(hr_conf)) {
        //     char confLog[150];
        //     sprintf_s(confLog, sizeof(confLog), "Failed to set bmdDeckLinkConfigVideoOutputConnection. HRESULT: 0x%08X", static_cast<unsigned int>(hr_conf));
        //     LogMessage(confLog);
        // } else {
        //     LogMessage("Set bmdDeckLinkConfigVideoOutputConnection successfully (or it was already set).");
        // }

        // More importantly, try to set the keying mode if such an option exists.
        // BMDDeckLinkOutputKeyingMode is not a standard config ID.
        // The keyer is typically controlled directly via IDeckLinkKeyer::Enable.
        // However, some older APIs or specific card configurations might have used this.
        // For modern external keying, IDeckLinkKeyer::Enable(true) is the primary method.
        // We'll leave this commented unless specific documentation for Duo 2 suggests it.
        // hr_conf = g_fillDeckLinkConfiguration->SetInt(bmdDeckLinkConfigurationKeyingMode, useExternalMode ? bmdExternalKeying : bmdInternalKeying); // Fictional example
    }

    // The IDeckLinkKeyer::Enable method directly takes a boolean to specify
    // whether to use external keying (TRUE) or internal keying (FALSE).
    HRESULT hr = g_fillDeckLinkKeyer->Enable(useExternalMode); 
    char tempLog[200];
    // sprintf_s(tempLog, sizeof(tempLog), "IDeckLinkKeyer->Enable(useExternalMode=%s) called. HRESULT: 0x%08X", useExternalMode ? "true" : "false", static_cast<unsigned int>(hr));
    // LogMessage(tempLog); // Python side will log success/failure of the call

    if (FAILED(hr)) {
        g_keyerEnabled = false;
        return hr;
    }
    g_keyerEnabled = true;
    return S_OK;
}

DLL_EXPORT HRESULT DisableKeyer() {
    if (!g_fillDeviceInitialized || !g_fillDeckLinkKeyer) {
        // If device isn't init, keyer shouldn't be active. If keyer interface is null, can't disable.
        LogMessage("Cannot disable keyer: Device not initialized or keyer interface not available.");
        if (!g_fillDeckLinkKeyer && g_keyerEnabled) g_keyerEnabled = false; // Correct state if interface is gone
        return E_FAIL; // Or S_OK if "already disabled" is acceptable.
    }
    if (!g_keyerEnabled) {
        LogMessage("Keyer is already disabled.");
        return S_OK;
    }

    HRESULT hr = g_fillDeckLinkKeyer->Disable();
    if (FAILED(hr)) {
        LogMessage("IDeckLinkKeyer->Disable() failed.");
        // State of g_keyerEnabled might be uncertain here, but typically it would be considered disabled.
        return hr;
    }
    g_keyerEnabled = false;
    // LogMessage("Keyer disabled."); // Python side will confirm
    return S_OK;
}

DLL_EXPORT HRESULT SetKeyerLevel(unsigned char level) {
    if (!g_fillDeviceInitialized || !g_fillDeckLinkKeyer) {
        LogMessage("Cannot set keyer level: Device not initialized or keyer interface not available.");
        return E_FAIL;
    }
    if (!g_keyerEnabled) {
        LogMessage("Keyer is not enabled. Enable keyer before setting level.");
        return E_FAIL;
    }

    HRESULT hr = g_fillDeckLinkKeyer->SetLevel(static_cast<UINT8>(level)); // API expects UINT8
    if (FAILED(hr)) {
        LogMessage("IDeckLinkKeyer->SetLevel() failed.");
        return hr;
    }
    // LogMessage(("Keyer level set to " + std::to_string(level)).c_str()); // Python side will confirm
    return S_OK;
}

DLL_EXPORT HRESULT IsKeyerActive(bool* isActive) {
    if (!isActive) return E_POINTER;
    if (!g_fillDeviceInitialized || !g_fillDeckLinkKeyer) {
        *isActive = false; // If device/keyer not ready, it's not active.
        return S_OK; // Or E_FAIL if strict "must be initialized"
    }
    // We rely on our internal g_keyerEnabled flag, which is updated by EnableKeyer/DisableKeyer.
    // IDeckLinkKeyer itself doesn't have a GetEnabled() or similar.
    *isActive = g_keyerEnabled;
    return S_OK;
}

// --- DllMain ---
BOOL APIENTRY DllMain(HMODULE hModule,
    DWORD  ul_reason_for_call,
    LPVOID lpReserved) {
    switch (ul_reason_for_call) {
    case DLL_PROCESS_ATTACH:
        // Optional: Disable thread library calls for performance if not using TLS or thread-local COM objects
        DisableThreadLibraryCalls(hModule); // Good practice if not using per-thread features
        // LogMessage("DLL_PROCESS_ATTACH");
        break;
    case DLL_THREAD_ATTACH:
        // LogMessage("DLL_THREAD_ATTACH"); // Can be very noisy
        break;
    case DLL_THREAD_DETACH:
        // LogMessage("DLL_THREAD_DETACH"); // Can be very noisy
        break;
    case DLL_PROCESS_DETACH:
        // LogMessage("DLL_PROCESS_DETACH");
        // This is a last resort. Explicit call to ShutdownDLL() is highly preferred.
        if (g_dllInitialized) {
            // LogMessage("Warning: DLL_PROCESS_DETACH called while DLL still initialized. Attempting cleanup.");
            ShutdownDLL();
        }
        else if (g_comInitialized) { // If only COM was initialized (e.g. InitializeDLL failed partway)
            LogMessage("Warning: DLL_PROCESS_DETACH called while COM still initialized. Attempting COM cleanup.");
            CoUninitialize();
            g_comInitialized = false;
        }
        break;
    }
    return TRUE;
}