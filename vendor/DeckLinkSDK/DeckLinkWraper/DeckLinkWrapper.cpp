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
static std::vector<IDeckLink*>          g_deckLinkDevices; // Stores discovered DeckLink devices (AddRef'd)
static std::vector<std::string>         g_deckLinkDeviceNames;

static IDeckLink* g_selectedDeckLink = nullptr; // Points to an item in g_deckLinkDevices, not separately AddRef'd here
static IDeckLinkOutput* g_deckLinkOutput = nullptr;
static IDeckLinkMutableVideoFrame* g_videoFrame = nullptr;
static IDeckLinkConfiguration* g_deckLinkConfiguration = nullptr;
static IDeckLinkKeyer* g_deckLinkKeyer = nullptr;

static long                             g_frameWidth = 0;
static long                             g_frameHeight = 0;
static BMDPixelFormat                   g_pixelFormat = bmdFormat8BitBGRA; // Python typically sends BGRA
static BMDTimeValue                     g_frameDuration = 0; // For selected display mode
static BMDTimeScale                     g_timeScale = 0;     // For selected display mode

static bool                             g_comInitialized = false;
static bool                             g_dllInitialized = false; // Tracks if InitializeDLL has been successfully called
static bool                             g_deviceInitialized = false; // Tracks if a specific device is initialized for output
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

void ReleaseSelectedDeviceResources() {
    if (g_keyerEnabled && g_deckLinkKeyer) {
        g_deckLinkKeyer->Disable(); // Best effort to disable
        g_keyerEnabled = false;
    }
    if (g_deckLinkKeyer) {
        g_deckLinkKeyer->Release();
        g_deckLinkKeyer = nullptr;
    }
    if (g_deckLinkConfiguration) {
        g_deckLinkConfiguration->Release();
        g_deckLinkConfiguration = nullptr;
    }
    if (g_deviceInitialized && g_deckLinkOutput) {
        g_deckLinkOutput->DisableVideoOutput(); // Best effort
    }
    if (g_videoFrame) {
        g_videoFrame->Release();
        g_videoFrame = nullptr;
    }
    if (g_deckLinkOutput) {
        g_deckLinkOutput->Release();
        g_deckLinkOutput = nullptr;
    }

    // g_selectedDeckLink is not AddRef'd separately beyond its existence in g_deckLinkDevices.
    // So, no Release() here. It's just a pointer.
    g_selectedDeckLink = nullptr;

    g_frameWidth = 0;
    g_frameHeight = 0;
    g_deviceInitialized = false;
    LogMessage("Selected device resources released.");
}
// Forward declaration for ShutdownDevice, as it's called by ShutdownDLL
DLL_EXPORT HRESULT ShutdownDevice();

// --- DLL Exported Functions ---

DLL_EXPORT HRESULT InitializeDLL() {
    if (g_dllInitialized) {
        LogMessage("DLL already initialized.");
        return S_OK;
    }

    if (!g_comInitialized) {
        HRESULT hr_com = CoInitializeEx(NULL, COINIT_MULTITHREADED);
        if (hr_com == RPC_E_CHANGED_MODE) {
            LogMessage("CoInitializeEx (MTA) failed: RPC_E_CHANGED_MODE. Thread likely already STA. Retrying with COINIT_APARTMENTTHREADED.");
            hr_com = CoInitializeEx(NULL, COINIT_APARTMENTTHREADED); // Try STA
            if (SUCCEEDED(hr_com)) {
                LogMessage("COM Initialized (ApartmentThreaded on this thread) successfully as fallback.");
                // Note: DeckLink objects created on this thread will be STA.
                // This might have implications if they are accessed from other threads.
            } else {
                LogMessage("CoInitializeEx (STA fallback) also failed.");
                // Log the specific HRESULT for the STA failure
                char err_msg[100];
                sprintf_s(err_msg, sizeof(err_msg), "STA CoInitializeEx failed with HRESULT: 0x%08X", static_cast<unsigned int>(hr_com));
                LogMessage(err_msg);
                return hr_com; // Return the error from the STA attempt
            }
        } else if (FAILED(hr_com)) {
            LogMessage("CoInitializeEx (MTA) failed with a different error.");
            return hr_com;
        }
        g_comInitialized = true;
        LogMessage("COM Initialized by DLL successfully."); // More general success message
    }

    // The iterator will now be created on demand by GetDeviceCount.
    // InitializeDLL just ensures COM is up.
    // if (g_deckLinkIterator == nullptr) {
    //     HRESULT hr = CoCreateInstance(CLSID_CDeckLinkIterator, NULL, CLSCTX_ALL, IID_IDeckLinkIterator, (void**)&g_deckLinkIterator);
    //     if (FAILED(hr) || g_deckLinkIterator == nullptr) {
    //         LogMessage("Failed to create DeckLink Iterator instance in InitializeDLL.");
    //         if (g_comInitialized) { 
    //             CoUninitialize();
    //             g_comInitialized = false;
    //         }
    //         return E_FAIL; 
    //     }

    g_dllInitialized = true;
    LogMessage("DeckLink DLL Initialized successfully.");
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
            LogMessage("COM Uninitialized (ShutdownDLL called when DLL not fully initialized).");
        }
        return S_OK;
    }

    ShutdownDevice(); // Ensure any active device is shut down first

    for (IDeckLink* dev : g_deckLinkDevices) {
        if (dev) dev->Release();
    }
    g_deckLinkDevices.clear();
    g_deckLinkDeviceNames.clear();

    if (g_deckLinkIterator) {
        g_deckLinkIterator->Release();
        g_deckLinkIterator = nullptr;
    }

    if (g_comInitialized) {
        CoUninitialize();
        g_comInitialized = false;
        LogMessage("COM Uninitialized.");
    }

    g_dllInitialized = false;
    LogMessage("DeckLink DLL Shutdown complete.");
    return S_OK;
}

DLL_EXPORT HRESULT GetDeviceCount(int* count) {
    if (!g_dllInitialized) { // Iterator is now managed within this function
        LogMessage("DLL not initialized. Call InitializeDLL first.");
        return E_FAIL;
    }
    if (!count) { LogMessage("GetDeviceCount: count pointer is null."); return E_POINTER; }


    // Clear previous enumeration results
    for (IDeckLink* dev : g_deckLinkDevices) {
        if (dev) dev->Release();
    }
    g_deckLinkDevices.clear();
    g_deckLinkDeviceNames.clear();
    // Release existing iterator and create a new one for a fresh enumeration
    if (g_deckLinkIterator != nullptr) {
        g_deckLinkIterator->Release();
        g_deckLinkIterator = nullptr;
    }

    HRESULT hr = CoCreateInstance(CLSID_CDeckLinkIterator, NULL, CLSCTX_ALL, IID_IDeckLinkIterator, (void**)&g_deckLinkIterator);
    if (FAILED(hr) || g_deckLinkIterator == nullptr) {
        LogMessage("Failed to create DeckLink Iterator instance in GetDeviceCount.");
        *count = 0;
        return hr; // Or E_FAIL
    }

    IDeckLink* tempDeckLink;

    int deviceIdx = 0;
    while ((hr = g_deckLinkIterator->Next(&tempDeckLink)) == S_OK) {
        BSTR deviceNameBSTR = nullptr;
        if (tempDeckLink->GetModelName(&deviceNameBSTR) == S_OK) {
            g_deckLinkDevices.push_back(tempDeckLink); // tempDeckLink is AddRef'd by Next(), store it
            g_deckLinkDeviceNames.push_back(BSTRToStdString(deviceNameBSTR));
            SysFreeString(deviceNameBSTR); // BSTRToStdString made a copy
            deviceIdx++;
        }
        else {
            tempDeckLink->Release(); // Release if we can't get name or don't store it
        }
    }
    // If hr is S_FALSE, it means no more items, which is normal.
    // If hr is a failure code, something went wrong.

    *count = static_cast<int>(g_deckLinkDevices.size());
    LogMessage(("Found " + std::to_string(*count) + " DeckLink devices.").c_str());
    return S_OK;
}

DLL_EXPORT HRESULT GetDeviceName(int index, char* nameBuffer, int bufferLength) {
    if (!g_dllInitialized) return E_FAIL;
    if (!nameBuffer) return E_POINTER;
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

DLL_EXPORT HRESULT InitializeDevice(int deviceIndex, int width, int height, int frameRateNum, int frameRateDenom) {
    if (!g_dllInitialized) {
        LogMessage("DLL not initialized. Call InitializeDLL first.");
        return E_FAIL;
    }
    if (g_deviceInitialized) {
        LogMessage("A device is already initialized. Call ShutdownDevice first.");
        return E_FAIL; // Or S_FALSE to indicate already initialized with potentially different params
    }
    if (deviceIndex < 0 || deviceIndex >= static_cast<int>(g_deckLinkDevices.size())) {
        LogMessage("Invalid device index.");
        return E_INVALIDARG;
    }

    ReleaseSelectedDeviceResources(); // Clear any prior (stale) selected device info, though g_deviceInitialized should prevent this path

    g_selectedDeckLink = g_deckLinkDevices[deviceIndex]; // This IDeckLink* was AddRef'd when put into vector

    HRESULT hr = g_selectedDeckLink->QueryInterface(IID_IDeckLinkOutput, (void**)&g_deckLinkOutput);
    if (FAILED(hr) || g_deckLinkOutput == nullptr) {
        LogMessage("Failed to get IDeckLinkOutput interface for the selected device.");
        g_selectedDeckLink = nullptr;
        return hr;
    }

    IDeckLinkDisplayModeIterator* displayModeIterator = nullptr;
    hr = g_deckLinkOutput->GetDisplayModeIterator(&displayModeIterator);
    if (FAILED(hr) || displayModeIterator == nullptr) {
        LogMessage("Failed to get display mode iterator.");
        ReleaseSelectedDeviceResources(); // Cleans up g_deckLinkOutput
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

            // Note: DeckLink GetFrameRate gives duration (like 1001) and scale (like 60000 for 59.94)
            // Python provides num (like 60000) and den (like 1001)
            if (modeFrameDuration == frameRateDenom && modeTimeScale == frameRateNum) {
                BOOL supportedWithKeying = FALSE;
                hr = g_deckLinkOutput->DoesSupportVideoMode(
                    bmdVideoConnectionUnspecified, // Check all connections, or specify if known
                    currentDisplayMode->GetDisplayMode(),
                    g_pixelFormat, // bmdFormat8BitBGRA
                    bmdNoVideoOutputConversion,
                    bmdSupportedVideoModeKeying, // Crucial: check for keying support
                    nullptr,
                    &supportedWithKeying
                );

                if (hr == S_OK && supportedWithKeying) {
                    selectedDisplayModeObj = currentDisplayMode;
                    selectedDisplayModeObj->AddRef(); // Keep this display mode object
                    targetBMDMode = selectedDisplayModeObj->GetDisplayMode();
                    g_frameDuration = modeFrameDuration; // Store for reference
                    g_timeScale = modeTimeScale;         // Store for reference
                    break;
                }
            }
        }
        currentDisplayMode->Release(); // Release the iterated display mode if not selected
    }
    displayModeIterator->Release();

    if (!selectedDisplayModeObj || targetBMDMode == bmdModeUnknown) {
        LogMessage("Failed to find a supported display mode with specified resolution, frame rate, and keying capability.");
        ReleaseSelectedDeviceResources();
        return E_FAIL;
    }

    g_frameWidth = width;
    g_frameHeight = height;

    hr = g_deckLinkOutput->EnableVideoOutput(targetBMDMode, bmdVideoOutputFlagDefault);
    if (FAILED(hr)) {
        LogMessage("Failed to enable video output on the device.");
        selectedDisplayModeObj->Release();
        ReleaseSelectedDeviceResources();
        return hr;
    }

    long rowBytes = g_frameWidth * 4; // For bmdFormat8BitBGRA (4 bytes per pixel)
    hr = g_deckLinkOutput->CreateVideoFrame(g_frameWidth, g_frameHeight, rowBytes,
        g_pixelFormat, bmdFrameFlagDefault, &g_videoFrame);
    if (FAILED(hr) || g_videoFrame == nullptr) {
        LogMessage("Failed to create video frame for output.");
        g_deckLinkOutput->DisableVideoOutput(); // Clean up enabled output
        selectedDisplayModeObj->Release();
        ReleaseSelectedDeviceResources();
        return hr;
    }

    // Get Configuration and Keyer interfaces (optional for config, required for keyer if used)
    g_selectedDeckLink->QueryInterface(IID_IDeckLinkConfiguration, (void**)&g_deckLinkConfiguration); // Optional, so don't fail if NULL
    if (!g_deckLinkConfiguration) LogMessage("Warning: Could not get IDeckLinkConfiguration. Keyer mode setting might be limited.");

    hr = g_selectedDeckLink->QueryInterface(IID_IDeckLinkKeyer, (void**)&g_deckLinkKeyer);
    if (FAILED(hr) || g_deckLinkKeyer == nullptr) {
        LogMessage("Failed to get IDeckLinkKeyer interface. Keying will not be available.");
        // This is critical if keying is a primary feature.
        g_videoFrame->Release(); g_videoFrame = nullptr;
        g_deckLinkOutput->DisableVideoOutput();
        selectedDisplayModeObj->Release();
        ReleaseSelectedDeviceResources(); // Full cleanup
        return E_FAIL;
    }

    selectedDisplayModeObj->Release(); // We're done with this specific display mode object
    g_deviceInitialized = true;
    LogMessage(("Device '" + g_deckLinkDeviceNames[deviceIndex] + "' initialized for output: " +
        std::to_string(width) + "x" + std::to_string(height) + " @ " +
        std::to_string(frameRateNum) + "/" + std::to_string(frameRateDenom) + " FPS, PixelFormat: BGRA").c_str());
    return S_OK;
}

DLL_EXPORT HRESULT ShutdownDevice() {
    if (!g_dllInitialized) return E_FAIL; // Should not happen if called correctly
    if (!g_deviceInitialized && !g_selectedDeckLink && !g_deckLinkOutput) { // Check if already effectively shut down
        LogMessage("Device already shut down or not initialized.");
        return S_OK;
    }
    ReleaseSelectedDeviceResources(); // This handles disabling output, keyer, and releasing interfaces
    LogMessage("Selected device has been shut down.");
    return S_OK;
}

DLL_EXPORT HRESULT UpdateOutputFrame(const unsigned char* bgraData) {
    if (!g_deviceInitialized || !g_videoFrame || !g_deckLinkOutput) {
        LogMessage("Device not initialized or frame not ready for update.");
        return E_FAIL;
    }
    if (!bgraData) return E_POINTER;

    IDeckLinkVideoBuffer* videoBuffer = nullptr;

    void* frameBytes = nullptr;
    bool bufferAccessed = false;

    // Query for the IDeckLinkVideoBuffer interface
    HRESULT hr = g_videoFrame->QueryInterface(IID_IDeckLinkVideoBuffer, (void**)&videoBuffer);
    if (FAILED(hr) || videoBuffer == nullptr) {
        LogMessage("Failed to query IDeckLinkVideoBuffer interface from video frame.");
        return E_FAIL;
    }

    // Lock the buffer for writing
    hr = videoBuffer->StartAccess(bmdBufferAccessWrite);
    if (FAILED(hr)) {
        LogMessage("Failed to start access to video buffer for writing.");
        videoBuffer->Release();
        return E_FAIL;
    }
    bufferAccessed = true;

    // Get the pointer to the buffer
    hr = videoBuffer->GetBytes(&frameBytes);
    if (FAILED(hr) || !frameBytes) {
        LogMessage("Failed to get frame buffer pointer from IDeckLinkVideoBuffer.");
        // EndAccess must still be called if StartAccess succeeded
    }
    else {
        memcpy(frameBytes, bgraData, g_frameWidth * g_frameHeight * 4); // 4 bytes for BGRA

        // Display the frame
        hr = g_deckLinkOutput->DisplayVideoFrameSync(g_videoFrame);
        if (FAILED(hr)) {
            LogMessage("DisplayVideoFrameSync failed.");
            // hr will be returned below
        }
    }

    // Unlock the buffer
    videoBuffer->EndAccess(bmdBufferAccessWrite); // Always call EndAccess if StartAccess was successful
    videoBuffer->Release(); // Release the IDeckLinkVideoBuffer interface
    return S_OK;
}

DLL_EXPORT HRESULT EnableKeyer(bool useExternalMode) {
    if (!g_deviceInitialized || !g_deckLinkKeyer) {
        LogMessage("Cannot enable keyer: Device not initialized or keyer interface not available.");
        return E_FAIL;
    }

    // The IDeckLinkKeyer::Enable method directly takes a boolean to specify
    // whether to use external keying (TRUE) or internal keying (FALSE).
    // This makes the IDeckLinkConfiguration step for setting the mode redundant for this call.
    HRESULT hr = g_deckLinkKeyer->Enable(useExternalMode); 
    if (FAILED(hr)) {
        LogMessage(useExternalMode ? "IDeckLinkKeyer->Enable(TRUE) for external keying failed." : "IDeckLinkKeyer->Enable(FALSE) for internal keying failed.");
        g_keyerEnabled = false;
        return hr;
    }
    g_keyerEnabled = true;
    LogMessage(useExternalMode ? "External keyer enabled." : "Internal keyer enabled.");
    return S_OK;
}

DLL_EXPORT HRESULT DisableKeyer() {
    if (!g_deviceInitialized || !g_deckLinkKeyer) {
        // If device isn't init, keyer shouldn't be active. If keyer interface is null, can't disable.
        LogMessage("Cannot disable keyer: Device not initialized or keyer interface not available.");
        if (!g_deckLinkKeyer && g_keyerEnabled) g_keyerEnabled = false; // Correct state if interface is gone
        return E_FAIL; // Or S_OK if "already disabled" is acceptable.
    }
    if (!g_keyerEnabled) {
        LogMessage("Keyer is already disabled.");
        return S_OK;
    }

    HRESULT hr = g_deckLinkKeyer->Disable();
    if (FAILED(hr)) {
        LogMessage("IDeckLinkKeyer->Disable() failed.");
        // State of g_keyerEnabled might be uncertain here, but typically it would be considered disabled.
        return hr;
    }
    g_keyerEnabled = false;
    LogMessage("Keyer disabled.");
    return S_OK;
}

DLL_EXPORT HRESULT SetKeyerLevel(unsigned char level) {
    if (!g_deviceInitialized || !g_deckLinkKeyer) {
        LogMessage("Cannot set keyer level: Device not initialized or keyer interface not available.");
        return E_FAIL;
    }
    if (!g_keyerEnabled) {
        LogMessage("Keyer is not enabled. Enable keyer before setting level.");
        return E_FAIL;
    }

    HRESULT hr = g_deckLinkKeyer->SetLevel(static_cast<UINT8>(level)); // API expects UINT8
    if (FAILED(hr)) {
        LogMessage("IDeckLinkKeyer->SetLevel() failed.");
        return hr;
    }
    LogMessage(("Keyer level set to " + std::to_string(level)).c_str());
    return S_OK;
}

DLL_EXPORT HRESULT IsKeyerActive(bool* isActive) {
    if (!isActive) return E_POINTER;
    if (!g_deviceInitialized || !g_deckLinkKeyer) {
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
        // DisableThreadLibraryCalls(hModule);
        LogMessage("DLL_PROCESS_ATTACH");
        break;
    case DLL_THREAD_ATTACH:
        LogMessage("DLL_THREAD_ATTACH");
        break;
    case DLL_THREAD_DETACH:
        LogMessage("DLL_THREAD_DETACH");
        break;
    case DLL_PROCESS_DETACH:
        LogMessage("DLL_PROCESS_DETACH");
        // This is a last resort. Explicit call to ShutdownDLL() is highly preferred.
        if (g_dllInitialized) {
            LogMessage("Warning: DLL_PROCESS_DETACH called while DLL still initialized. Attempting cleanup.");
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