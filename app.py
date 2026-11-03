import tkinter as tk
import speech_recognition as sr
import threading
import queue
import re

from datetime import datetime
from commands import execute_command

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None
try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError:
    pystray = None

# =====================================================
# CONFIGURATION
# =====================================================

BG = "#0B1220"
PANEL = "#111C2E"
BORDER = "#253650"

TEXT = "#E6EDF7"
MUTED = "#93A4BD"

ACCENT = "#647FF0"
GREEN = "#36C98F"
RED = "#FF6B75"
YELLOW = "#F0BB5E"
WAKE_WORD_PATTERN = re.compile(
    r"^\s*hey[\s,]+friday\b[\s,.:;!?-]*",
    re.IGNORECASE
)

# =====================================================
# THREADING AND COMMUNICATION
# =====================================================

ui_queue = queue.Queue()
tts_queue = queue.Queue()

stop_event = threading.Event()
pause_event = threading.Event()
tts_pause_event = threading.Event()

tts_failed_event = threading.Event()
tts_lock = threading.Lock()
tray_ready_event = threading.Event()
tray_icon = None

listening_enabled = True

def post_ui(event, **data):
    """Send an event to the main Tkinter thread."""
    ui_queue.put((event, data))

def should_pause():
    return (
        stop_event.is_set()
        or pause_event.is_set()
        or tts_pause_event.is_set()
    )

def tray_icon_worker():
    global tray_icon
    if pystray is None:
        post_ui("notice", text="Install pystray and Pillow to use the system tray.")
        return
    image = Image.new("RGB", (64, 64), BG)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((24, 10, 40, 40), radius=8, fill=ACCENT)
    draw.arc((16, 22, 48, 50), 0, 180, fill=TEXT, width=4)
    draw.line((32, 49, 32, 57), fill=TEXT, width=4)
    draw.line((23, 57, 41, 57), fill=TEXT, width=4)
    menu = pystray.Menu(
        pystray.MenuItem("Show Voice Navigator", lambda icon, item: post_ui("restore")),
        pystray.MenuItem("Exit", lambda icon, item: post_ui("exit"))
    )
    tray_icon = pystray.Icon("Voice Navigator", image, "Voice Navigator", menu)

    def show_tray_icon(icon):
        icon.visible = True
        tray_ready_event.set()

    try:
        tray_icon.run(setup=show_tray_icon)
    except Exception as error:
        tray_ready_event.clear()
        post_ui("notice", text=f"System tray error: {error}")

# =====================================================
# TEXT TO SPEECH
# =====================================================

def queue_speech(message):
    """Queue a spoken response without blocking the UI."""
    with tts_lock:
        if tts_failed_event.is_set():
            return
        tts_pause_event.set()
        tts_queue.put(message)

def configure_speech_engine(engine):
    engine.setProperty("rate", 180)
    engine.setProperty("volume", 0.9)
    voices = engine.getProperty("voices")
    female_voice = next(
        (
            voice for voice in voices
            if (getattr(voice, "gender", None) or "").lower() == "female"
        ),
        None
    )
    if female_voice is None:
        female_names = (
            "zira", "hazel", "aria", "ava", "jenny", "michelle",
            "sonia", "natasha", "heera", "susan", "samantha", "laura"
        )
        female_voice = next(
            (
                voice for voice in voices
                if any(
                    name in f"{voice.name or ''} {voice.id}".lower()
                    for name in female_names
                )
            ),
            None
        )
    if female_voice is None:
        post_ui("notice", text="No female speech voice was found; using the default voice.")
    else:
        engine.setProperty("voice", female_voice.id)
        post_ui(
            "notice",
            text=f"Using voice: {female_voice.name or female_voice.id}"
        )

def speech_output_worker():
    if pyttsx3 is None:
        with tts_lock:
            tts_failed_event.set()
        post_ui(
            "notice",
            text="Text-to-speech is unavailable. Install pyttsx3."
        )
        return
    engine = None
    pythoncom_module = None
    try:
        import pythoncom
        pythoncom_module = pythoncom
        pythoncom_module.CoInitialize()
    except ImportError:
        pass
    except Exception as error:
        post_ui("notice", text=f"Could not initialize speech thread: {error}")
    try:
        while not stop_event.is_set():
            try:
                message = tts_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            for attempt in range(2):
                try:
                    if engine is None:
                        engine = pyttsx3.init()
                        configure_speech_engine(engine)
                    engine.say(message)
                    engine.runAndWait()
                    break
                except Exception as error:
                    if engine is not None:
                        try:
                            engine.stop()
                        except Exception:
                            pass
                    engine = None
                    if attempt == 1:
                        post_ui("notice", text=f"Speech output error: {error}")
            try:
                tts_queue.task_done()
                with tts_lock:
                    if tts_queue.empty():
                        tts_pause_event.clear()
            except Exception as error:
                post_ui("notice", text=f"Speech queue error: {error}")
    finally:
        if engine:
            try:
                engine.stop()
            except Exception:
                pass
        if pythoncom_module:
            pythoncom_module.CoUninitialize()

# =====================================================
# VOICE RECOGNITION
# =====================================================

def voice_recognition_worker():
    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True

    # A slightly longer pause helps keep "Hey Friday, [command]" together.
    recognizer.pause_threshold = 1.1
    microphone_error_announced = False
    while not stop_event.is_set():

        # Do not listen while paused or speaking.
        if should_pause():
            stop_event.wait(0.1)
            continue
        try:
            with sr.Microphone() as source:
                if should_pause():
                    continue
                post_ui(
                    "status",
                    text="Calibrating microphone...",
                    kind="starting"
                )
                recognizer.adjust_for_ambient_noise(
                    source,
                    duration=0.5
                )
                microphone_error_announced = False
                post_ui(
                    "status",
                    text="Listening...",
                    kind="listening"
                )

                # Require the wake phrase and command in the same utterance.
                while not should_pause():
                    try:
                        audio = recognizer.listen(
                            source,
                            timeout=1,
                            phrase_time_limit=8
                        )
                    except sr.WaitTimeoutError:

                        # No speech detected. Continue listening.
                        continue
                    if should_pause():
                        continue
                    # Convert speech into text.
                    try:
                        command = recognizer.recognize_google(audio)
                    except sr.UnknownValueError:
                        continue
                    except sr.RequestError:
                        if should_pause():
                            continue
                        message = (
                            "Speech recognition is unavailable. "
                            "Please check your internet connection."
                        )
                        post_ui(
                            "feedback",
                            text=message,
                            kind="error"
                        )
                        queue_speech(message)
                        post_ui(
                            "status",
                            text="Speaking response...",
                            kind="speaking"
                        )
                        continue
                    if should_pause():
                        continue
                    wake_match = WAKE_WORD_PATTERN.match(command)
                    if not wake_match:
                        continue
                    command = command[wake_match.end():].strip()
                    if not command:
                        continue

                    post_ui(
                        "status",
                        text="Processing command...",
                        kind="processing"
                    )

                    # Display recognized command.
                    post_ui(
                        "recognized",
                        command=command
                    )

                    # Execute the desktop action.
                    try:
                        success, response = execute_command(command)
                    except Exception as error:
                        success = False
                        response = (
                            "I couldn't complete that action. "
                            "Please try again."
                        )
                        post_ui(
                            "debug",
                            text=str(error)
                        )

                    # Display the result.
                    post_ui(
                        "feedback",
                        text=response,
                        kind="success" if success else "error"
                    )

                    # Speak the response.
                    queue_speech(response)
                    post_ui(
                        "status",
                        text="Speaking response...",
                        kind="speaking"
                    )
        except Exception as error:
            if stop_event.is_set():
                break

            # Avoid repeatedly speaking the same microphone error.
            if not microphone_error_announced:
                message = (
                    "I couldn't access the microphone. "
                    "Please check your microphone connection "
                    "and Windows microphone permissions."
                )
                post_ui(
                    "feedback",
                    text=message,
                    kind="error"
                )
                queue_speech(message)
                microphone_error_announced = True
            post_ui(
                "status",
                text="Microphone unavailable - retrying",
                kind="error"
            )
            post_ui(
                "debug",
                text=str(error)
            )
            stop_event.wait(3)

# =====================================================
# UI FUNCTIONS
# =====================================================

STATUS_COLORS = {
    "listening": GREEN,
    "processing": ACCENT,
    "starting": YELLOW,
    "speaking": ACCENT,
    "paused": MUTED,
    "error": RED,
    "success": GREEN
}

def set_status(message, kind="listening"):
    color = STATUS_COLORS.get(kind, MUTED)
    status_label.config(
        text=message,
        fg=color
    )
    status_dot.itemconfig(
        status_dot_id,
        fill=color
    )

def add_activity(message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    activity_log.config(state="normal")
    activity_log.insert(
        "end",
        f"{timestamp}  {message}\n"
    )
    activity_log.see("end")
    activity_log.config(state="disabled")

def toggle_listening():
    global listening_enabled
    if listening_enabled:
        listening_enabled = False
        pause_event.set()
        toggle_button.config(
            text="Resume Listening",
            bg=GREEN,
            activebackground="#279F72"
        )
        set_status("Paused", "paused")
        status_hint.config(
            text="Microphone is currently disabled."
        )
        add_activity("Listening paused.")
    else:
        listening_enabled = True
        pause_event.clear()
        toggle_button.config(
            text="Pause Listening",
            bg=ACCENT,
            activebackground="#5069D4"
        )
        set_status("Starting microphone...", "starting")
        status_hint.config(
            text="Say ‘Hey Friday’ and the command in one phrase."
        )
        add_activity("Listening resumed.")

# =====================================================
# UI EVENT PROCESSING
# =====================================================

def process_ui_events():
    try:
        while True:
            event, data = ui_queue.get_nowait()
            if event == "status":
                set_status(
                    data["text"],
                    data.get("kind", "listening")
                )
                if data.get("kind") == "listening":
                    status_hint.config(
                        text=(
                            "Say ‘Hey Friday’ and the command in one phrase."
                            if "Hey Friday" in data["text"]
                            else "Microphone is ready."
                        )
                    )
            elif event == "restore":
                root.deiconify()
                root.state("normal")
                root.lift()
                root.focus_force()
            elif event == "exit":
                on_close()
                return
            elif event == "recognized":
                command = data["command"]
                command_label.config(
                    text=f"“{command}”"
                )
                add_activity(f"You: {command}")
            elif event == "feedback":
                message = data["text"]
                kind = data["kind"]
                response_label.config(
                    text=message,
                    fg=GREEN if kind == "success" else RED
                )
                add_activity(f"Assistant: {message}")
            elif event == "notice":
                add_activity(f"Notice: {data['text']}")
            elif event == "debug":
                add_activity(f"Technical detail: {data['text']}")
    except queue.Empty:
        pass
    root.after(100, process_ui_events)

# =====================================================
# MAIN WINDOW
# =====================================================

root = tk.Tk()

root.title("Voice Navigator")
root.geometry("900x760")
root.minsize(760, 650)

root.configure(bg=BG)

def on_window_unmap(event):
    if event.widget is root and root.state() == "iconic" and tray_ready_event.is_set():
        root.withdraw()

root.bind("<Unmap>", on_window_unmap)

# Main container
container = tk.Frame(
    root,
    bg=BG
)

container.pack(
    fill="both",
    expand=True,
    padx=30,
    pady=25
)

# =====================================================
# HEADER
# =====================================================

header = tk.Frame(
    container,
    bg=BG
)

header.pack(
    fill="x",
    pady=(0, 22)
)
title_label = tk.Label(
    header,
    text="Voice Navigator",
    font=("Segoe UI", 25, "bold"),
    fg=TEXT,
    bg=BG
)

title_label.pack(anchor="w")

# =====================================================
# MICROPHONE PANEL
# =====================================================

hero = tk.Frame(
    container,
    bg=PANEL,
    highlightbackground=BORDER,
    highlightthickness=1
)

hero.pack(
    fill="x",
    pady=(0, 18)
)
tk.Label(
    hero,
    text="VOICE CONTROL",
    font=("Segoe UI", 10, "bold"),
    fg=MUTED,
    bg=PANEL
).pack(
    anchor="w",
    padx=25,
    pady=(22, 15)
)
status_row = tk.Frame(
    hero,
    bg=PANEL
)

status_row.pack(
    anchor="center",
    pady=5
)
status_dot = tk.Canvas(
    status_row,
    width=18,
    height=18,
    bg=PANEL,
    highlightthickness=0
)

status_dot.pack(
    side="left",
    padx=(0, 10)
)

status_dot_id = status_dot.create_oval(
    3, 3, 15, 15,
    fill=GREEN,
    outline=""
)
status_label = tk.Label(
    status_row,
    text="Starting microphone...",
    font=("Segoe UI", 19, "bold"),
    fg=GREEN,
    bg=PANEL
)

status_label.pack(side="left")
status_hint = tk.Label(
    hero,
    text="Say ‘Hey Friday’ and the command in one phrase.",
    font=("Segoe UI", 10),
    fg=MUTED,
    bg=PANEL
)

status_hint.pack(pady=(8, 20))
toggle_button = tk.Button(
    hero,
    text="Pause Listening",
    command=toggle_listening,
    font=("Segoe UI", 11, "bold"),
    fg="white",
    bg=ACCENT,
    activebackground="#5069D4",
    activeforeground="white",
    relief="flat",
    cursor="hand2",
    padx=35,
    pady=13
)

toggle_button.pack(pady=(0, 24))

# =====================================================
# COMMAND AND RESPONSE PANELS
# =====================================================

cards = tk.Frame(
    container,
    bg=BG
)

cards.pack(
    fill="x",
    pady=(0, 18)
)

cards.grid_columnconfigure(0, weight=1)
cards.grid_columnconfigure(1, weight=1)

# Last command
command_card = tk.Frame(
    cards,
    bg=PANEL,
    highlightbackground=BORDER,
    highlightthickness=1
)

command_card.grid(
    row=0,
    column=0,
    sticky="nsew",
    padx=(0, 8)
)
tk.Label(
    command_card,
    text="LAST COMMAND",
    font=("Segoe UI", 9, "bold"),
    fg=MUTED,
    bg=PANEL
).pack(
    anchor="w",
    padx=18,
    pady=(17, 10)
)
command_label = tk.Label(
    command_card,
    text="Waiting for speech...",
    font=("Segoe UI", 13),
    fg=TEXT,
    bg=PANEL,
    wraplength=330,
    justify="left"
)

command_label.pack(
    anchor="w",
    padx=18,
    pady=(0, 22)
)

# Assistant response
response_card = tk.Frame(
    cards,
    bg=PANEL,
    highlightbackground=BORDER,
    highlightthickness=1
)

response_card.grid(
    row=0,
    column=1,
    sticky="nsew",
    padx=(8, 0)
)
tk.Label(
    response_card,
    text="ASSISTANT RESPONSE",
    font=("Segoe UI", 9, "bold"),
    fg=MUTED,
    bg=PANEL
).pack(
    anchor="w",
    padx=18,
    pady=(17, 10)
)
response_label = tk.Label(
    response_card,
    text="Ready to assist.",
    font=("Segoe UI", 13),
    fg=GREEN,
    bg=PANEL,
    wraplength=330,
    justify="left"
)

response_label.pack(
    anchor="w",
    padx=18,
    pady=(0, 22)
)

# =====================================================
# ACTIVITY HISTORY
# =====================================================

activity_panel = tk.Frame(
    container,
    bg=PANEL,
    highlightbackground=BORDER,
    highlightthickness=1
)

activity_panel.pack(
    fill="both",
    expand=True
)
tk.Label(
    activity_panel,
    text="ACTIVITY HISTORY",
    font=("Segoe UI", 10, "bold"),
    fg=MUTED,
    bg=PANEL
).pack(
    anchor="w",
    padx=20,
    pady=(17, 10)
)
log_container = tk.Frame(
    activity_panel,
    bg=PANEL
)

log_container.pack(
    fill="both",
    expand=True,
    padx=18,
    pady=(0, 18)
)
scrollbar = tk.Scrollbar(
    log_container
)

scrollbar.pack(
    side="right",
    fill="y"
)
activity_log = tk.Text(
    log_container,
    height=8,
    bg="#0A1220",
    fg=TEXT,
    font=("Consolas", 10),
    relief="flat",
    wrap="word",
    padx=12,
    pady=10,
    yscrollcommand=scrollbar.set,
    state="disabled"
)

activity_log.pack(
    fill="both",
    expand=True
)

scrollbar.config(
    command=activity_log.yview
)

# =====================================================
# APPLICATION SHUTDOWN
# =====================================================

def on_close():
    stop_event.set()
    pause_event.set()
    tts_pause_event.set()
    if tray_icon is not None:
        try:
            tray_icon.stop()
        except Exception:
            pass
    root.destroy()
root.protocol(
    "WM_DELETE_WINDOW",
    on_close
)

# =====================================================
# START BACKGROUND THREADS
# =====================================================

speech_thread = threading.Thread(
    target=speech_output_worker,
    daemon=True
)

voice_thread = threading.Thread(
    target=voice_recognition_worker,
    daemon=True
)

speech_thread.start()
voice_thread.start()
tray_thread = threading.Thread(target=tray_icon_worker, daemon=True)
tray_thread.start()

root.after(100, process_ui_events)

add_activity("Voice Navigator started.")

root.mainloop()
