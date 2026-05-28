try:
    import sounddevice as sd
    HAS_SD = True
except ImportError:
    HAS_SD = False

try:
    import pyaudio
    HAS_PA = True
except ImportError:
    HAS_PA = False

def list_devices():
    print("========== AUDIO DEVICES LIST ==========")
    if HAS_PA:
        print("[PyAudio Detected]")
        p = pyaudio.PyAudio()
        for i in range(p.get_device_count()):
            dev_info = p.get_device_info_by_index(i)
            max_in = dev_info.get("maxInputChannels", 0)
            name = dev_info.get('name', 'Unknown')
            # Safe print encoding
            print(f"Index {i}: {name} (In: {max_in}, Out: {dev_info.get('maxOutputChannels')})")
        p.terminate()
    elif HAS_SD:
        print("[sounddevice Detected]")
        devices = sd.query_devices()
        for i, dev in enumerate(devices):
            max_in = dev.get("max_input_channels", 0)
            name = dev.get('name', 'Unknown')
            print(f"Index {i}: {name} (In: {max_in}, Out: {dev.get('max_output_channels')})")
    else:
        print("[ERROR: No sounddevice or pyaudio installed]")

if __name__ == "__main__":
    list_devices()
