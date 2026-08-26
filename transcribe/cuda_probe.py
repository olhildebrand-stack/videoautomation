#!/usr/bin/env python3
"""Report whether CTranslate2 can actually use CUDA on this machine.

Run by setup.ps1. Kept as a file rather than a -c one-liner because PowerShell
mangles quoting when passing multi-line source to a native executable.

Checks three separate things, because a machine can pass one and fail the next:

  1. a CUDA device is visible
  2. float16 is a supported compute type
  3. the cuBLAS and cuDNN DLLs actually load

Step 3 is the one that matters most on Windows. The nvidia-*-cu12 wheels put
their DLLs inside site-packages, and a device can be perfectly visible while
those libraries remain unloadable.
"""

import ctypes
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from transcribe import register_cuda_dll_dirs  # noqa: E402

# Loaded by name, exactly as CTranslate2 asks for them.
REQUIRED_WINDOWS_DLLS = ("cublas64_12.dll", "cudnn_ops64_9.dll")


def main() -> int:
    registered = register_cuda_dll_dirs()
    for directory in registered:
        print(f"dll_dir={directory}")

    try:
        import ctranslate2
    except Exception as exc:  # noqa: BLE001
        print(f"error: cannot import ctranslate2: {exc}")
        return 1

    count = ctranslate2.get_cuda_device_count()
    device = "cuda" if count else "cpu"
    types = sorted(ctranslate2.get_supported_compute_types(device))
    print(f"cuda_devices={count}")
    print(f"compute_types[{device}]={','.join(types)}")
    print(f"python={sys.version.split()[0]} ctranslate2={ctranslate2.__version__}")

    if not count:
        print("verdict=cpu_only")
        return 0

    if "float16" not in types:
        print("verdict=no_float16")
        return 0

    if sys.platform == "win32":
        missing = []
        for name in REQUIRED_WINDOWS_DLLS:
            try:
                ctypes.WinDLL(name)
                print(f"dll_ok={name}")
            except OSError as exc:
                print(f"dll_missing={name} ({exc})")
                missing.append(name)
        if missing:
            print(f"verdict=dll_missing:{','.join(missing)}")
            return 0

    print("verdict=cuda_ready")
    return 0


if __name__ == "__main__":
    sys.exit(main())
