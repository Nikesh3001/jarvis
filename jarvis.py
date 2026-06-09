#!/usr/bin/env python3
import os
import sys
import signal

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

VERSION = "3.5.0"


def main():
    mic_index = None
    mode = "wake"
    for arg in sys.argv[1:]:
        if arg in ("-c", "--continuous", "--always"):
            mode = "continuous"
        elif arg in ("-t", "--text", "--type"):
            mode = "text"
        elif arg in ("-w", "--web"):
            mode = "web"
        else:
            try:
                mic_index = int(arg)
            except ValueError:
                pass
    if any(a in sys.argv for a in ["-h", "--help", "--list"]):
        print(f"  Usage: python jarvis.py [options] [mic_index]")
        print(f"    -c, --continuous   Voice mode (no wake word)")
        print(f"    -t, --text         Text mode (type commands)")
        print(f"    -w, --web          Web dashboard mode")
        print(f"    -h, --help         This help")
        print(f"    mic_index          Microphone device index")
        sys.exit(0)

    from core.assistant import Assistant
    try:
        ai = Assistant(mic_index=mic_index, text_mode=(mode == "text"))
    except ValueError as e:
        print(f"\n  [ERROR] {e}")
        print(f"  [FIX]   Run: python setup_keys.py")
        print()
        sys.exit(1)
    if mode == "web":
        from web.server import main as web_main
        web_main()
    elif mode == "text":
        ai.run_text()
    elif mode == "continuous":
        ai.run()
    else:
        ai.run()


if __name__ == "__main__":
    signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))
    main()
