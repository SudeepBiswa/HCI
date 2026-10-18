import tkinter as tk
from tkinter import ttk
import speech_recognition as sr

from commands import execute_command

recognizer = sr.Recognizer()


def listen_for_command():
    status_label.config(text="Listening...")
    recognized_label.config(text="")
    root.update()

    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)

            audio = recognizer.listen(
                source,
                timeout=5,
                phrase_time_limit=5
            )

        status_label.config(text="Recognizing...")
        root.update()

        command = recognizer.recognize_google(audio)

        recognized_label.config(text=f'"{command}"')

        result = execute_command(command)

        status_label.config(text=result)

    except sr.WaitTimeoutError:
        status_label.config(text="No speech detected")

    except sr.UnknownValueError:
        status_label.config(text="Could not understand command")

    except sr.RequestError:
        status_label.config(text="Speech recognition service unavailable")

    except Exception as error:
        status_label.config(text=f"Error: {error}")


# Main window
root = tk.Tk()
root.title("Voice Desktop Navigation")
root.geometry("600x400")
root.resizable(False, False)


# Title
title_label = ttk.Label(
    root,
    text="Voice Desktop Navigation",
    font=("Segoe UI", 24, "bold")
)
title_label.pack(pady=(45, 10))


# Instructions
instruction_label = ttk.Label(
    root,
    text="Press the button and speak a desktop command.",
    font=("Segoe UI", 11)
)
instruction_label.pack(pady=5)


# Listen button
listen_button = ttk.Button(
    root,
    text="Start Listening",
    command=listen_for_command
)
listen_button.pack(pady=30, ipadx=20, ipady=10)


# Status
status_label = ttk.Label(
    root,
    text="Ready",
    font=("Segoe UI", 12, "bold")
)
status_label.pack(pady=10)


# Recognized speech
recognized_label = ttk.Label(
    root,
    text="",
    font=("Segoe UI", 16),
    wraplength=500
)
recognized_label.pack(pady=15)


# Example commands
example_label = ttk.Label(
    root,
    text="Example: \"Open Chrome\"",
    font=("Segoe UI", 10)
)
example_label.pack(pady=10)


root.mainloop()