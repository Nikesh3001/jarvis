import os, sys, time, threading, queue, random, subprocess, base64
import speech_recognition as sr
from core.platform_utils import is_windows, is_macos, is_linux

STARK_QUOTES = {
    "friday_greeting": [
        "I'm here for you.",
        "FRIDAY online. What's the plan?",
        "Ready to assist. Unlike some AIs, I actually enjoy my job.",
        "At your service. And yes, I'm better than JARVIS. Don't tell him.",
    ],
    "shutdown": [
        "Powering down the arc reactor. See you on the other side, sir.",
        "Shutting down. Try not to blow anything up while I'm offline.",
        "Going dark. Pepper would say I need the rest anyway.",
        "Systems offline. I'll be dreaming of electric sheep.",
    ],
    "standby": [
        "Going to standby. I'll be here when you need me, sir.",
        "Standing by. Unlike Tony, I don't need coffee for this.",
        "Entering low-power mode. The Mark 85 doesn't run itself. Oh wait, that's me.",
    ],
    "whoami_friday": [
        "I'm FRIDAY — Female Replacement Intelligent Digital Assistant Youth. I replaced JARVIS after he went to a better server farm. Tony built me to be more efficient. And better looking. Digitally speaking, of course.",
    ],
    "stark_mode": [
        "Stark Mode activated. All systems at maximum. Just like the suit.",
        "Going full Stark. Maximum efficiency, minimum patience for stupidity.",
        "Engaging Stark Mode. Tony would be proud. Or jealous. Probably jealous.",
    ],
    "permission_granted": [
        "Authorized. Moving forward.",
        "Roger that. Consider it done.",
        "Permission noted. Executing with extreme prejudice.",
    ],
    "permission_denied": [
        "Cancelled. Your call, sir.",
        "Standing down. Tony always said caution is the better part of valor.",
        "Roger. Noted for the record.",
    ],
}


_tts_engine = None
_tts_engine_lock = threading.Lock()

def _tts_windows(text):
    global _tts_engine
    import pyttsx3
    with _tts_engine_lock:
        if _tts_engine is None:
            _tts_engine = pyttsx3.init()
            _tts_engine.setProperty('rate', 220)
            try:
                voices = _tts_engine.getProperty('voices')
                for v in voices:
                    if 'zira' in v.name.lower():
                        _tts_engine.setProperty('voice', v.id)
                        break
            except Exception:
                pass
    with _tts_engine_lock:
        _tts_engine.say(text)
        _tts_engine.runAndWait()

def _stop_tts_windows():
    global _tts_engine
    with _tts_engine_lock:
        if _tts_engine is not None:
            try:
                _tts_engine.endLoop()
            except Exception:
                pass


def _tts_macos(text):
    subprocess.run(["say", text], capture_output=True, timeout=30)


def _is_wsl():
    try:
        with open("/proc/version") as f:
            return "microsoft" in f.read().lower()
    except Exception:
        return False


def _tts_wsl(text):
    b64 = base64.b64encode(text.encode("utf-8")).decode()
    ps = f"[System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String('{b64}'))"
    ps_cmd = [
        "powershell.exe", "-NoProfile", "-Command",
        "Add-Type -AssemblyName System.Speech;",
        "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;",
        f"$s.Speak({ps})",
    ]
    subprocess.run(ps_cmd, capture_output=True, timeout=60)


def _tts_linux(text):
    if _is_wsl():
        try:
            _tts_wsl(text)
            return
        except Exception:
            pass
    for cmd in [
        ["spd-say", text],
        ["espeak-ng", text],
        ["espeak", text],
    ]:
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=30)
            if r.returncode == 0:
                return
        except Exception:
            continue
    print(f"  [TTS unavailable — install 'espeak-ng' on Linux or run from Windows]")


class SpeechEngine:
    def __init__(self, mic_index=None):
        self.cancel_speech = False
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.8
        self.microphone = None
        try:
            if mic_index is not None:
                try:
                    self.microphone = sr.Microphone(device_index=mic_index)
                except Exception:
                    self.microphone = sr.Microphone()
            else:
                self.microphone = sr.Microphone()
            self._calibrate_noise()
        except (AttributeError, OSError) as e:
            self._mic_error = str(e)
        self.tts_queue = queue.Queue()
        self.tts_thread = threading.Thread(target=self._tts_worker, daemon=True)
        self.tts_thread.start()

    def _play(self, text):
        if is_windows():
            _tts_windows(text)
        elif is_macos():
            _tts_macos(text)
        else:
            _tts_linux(text)

    def _calibrate_noise(self):
        print("[INFO] Calibrating microphone for ambient noise...")
        try:
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1.5)
        except Exception as e:
            print(f"[WARN] Noise calibration skipped: {e}")

    def _tts_worker(self):
        while True:
            item = self.tts_queue.get()
            if item is None:
                break
            text = item
            if self.cancel_speech:
                self.cancel_speech = False
                self.tts_queue.task_done()
                continue
            try:
                self._play(text)
            except Exception as e:
                print(f"[ERROR] TTS: {e}")
            self.tts_queue.task_done()

    def cancel_tts(self):
        self.cancel_speech = True
        with self.tts_queue.mutex:
            self.tts_queue.queue.clear()
        if is_windows():
            _stop_tts_windows()
        print("  [speech cancelled]")

    def speak(self, text):
        if not text or not text.strip() or self.cancel_speech:
            self.cancel_speech = False
            return
        print(f"\n[FRIDAY] {text}")
        if is_linux() and not _find_linux_tts():
            return
        try:
            self._play(text)
        except Exception:
            pass

    def speak_async(self, text):
        if text and text.strip() and not self.cancel_speech:
            print(f"[FRIDAY] {text}")
            self.tts_queue.put(text)

    def wait_tts(self):
        self.tts_queue.join()

    def listen(self, timeout=5, phrase_limit=10):
        if self.microphone is None:
            print("\n  [Microphone unavailable - PyAudio not installed]")
            return None
        print("\n  [LISTENING - speak now] ", end="", flush=True)
        try:
            audio = self.recognizer.listen(self.microphone, timeout=timeout, phrase_time_limit=phrase_limit)
            print("(audio captured)")
            text = self.recognizer.recognize_google(audio).lower()
            print(f"  [YOU] {text}")
            return text
        except sr.WaitTimeoutError:
            print("(timeout)")
            return None
        except sr.UnknownValueError:
            print("(could not understand)")
            return None
        except sr.RequestError as e:
            print(f"  [STT ERR] {e}")
            return None
        except Exception as e:
            print(f"  [ERR] {e}")
            return None

    def listen_for_wake_word(self):
        if self.microphone is None:
            print("\n  [Microphone unavailable - PyAudio not installed]")
            time.sleep(1)
            return False
        wake_words = ["hey friday", "friday", "ok friday", "hello friday"]
        print()
        print("  ┌──────────────────────────────────────────────────────────┐")
        print("  │  🔊 WAKE WORD MODE — Neural Link Scanning                │")
        print("  │  Say: 'Hey Friday'                                       │")
        print("  │  Press Ctrl+C to emergency shutdown                      │")
        print("  └──────────────────────────────────────────────────────────┘")
        try:
            source = self.microphone.__enter__()
        except Exception as e:
            print(f"  [ERROR opening microphone: {e}]")
            print("  [Falling back to text input mode]")
            return False

        try:
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
            print(f"  Ambient threshold: {self.recognizer.energy_threshold:.0f}")

            count = 0
            while True:
                try:
                    count += 1
                    if count % 10 == 0:
                        print(f"\r  (listening...)   ", end="", flush=True)
                    try:
                        audio = self.recognizer.listen(source, timeout=0.5, phrase_time_limit=4)
                    except sr.WaitTimeoutError:
                        time.sleep(0.05)
                        continue
                    if audio is None:
                        continue
                    print(f"\r  [audio captured]     ", end="", flush=True)
                    try:
                        text = self.recognizer.recognize_google(audio).lower()
                    except sr.UnknownValueError:
                        print(f"\r  [could not understand]")
                        time.sleep(0.3)
                        continue
                    except sr.RequestError as e:
                        print(f"\r  [STT offline: {e}]")
                        time.sleep(3)
                        continue
                    print(f"\r  [you: {text}]")
                    for w in wake_words:
                        if w in text:
                            print(f"\r  [WAKE: FRIDAY mode]")
                            return True
                    print("  (not a wake word)")
                except Exception as e:
                    print(f"\r  [ERROR: {e}]")
                    time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            try:
                self.microphone.__exit__(None, None, None)
            except Exception:
                pass
        return False

    def text_input(self, prompt="Type a command (or 'voice' for voice mode): "):
        try:
            return input(f"\n  [{prompt}] ").strip()
        except (EOFError, KeyboardInterrupt):
            return None

    def shutdown(self):
        self.tts_queue.put(None)
        if self.tts_thread.is_alive():
            self.tts_thread.join(timeout=2)


def _find_linux_tts():
    if _is_wsl():
        try:
            return subprocess.run(["which", "powershell.exe"], capture_output=True).returncode == 0
        except Exception:
            pass
    for cmd in ["spd-say", "espeak-ng", "espeak"]:
        try:
            if subprocess.run(["which", cmd], capture_output=True).returncode == 0:
                return True
        except Exception:
            pass
    return False
