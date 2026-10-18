import speech_recognition as sr

recognizer = sr.Recognizer()

with sr.Microphone() as source:
    print("Adjusting for background noise...")
    recognizer.adjust_for_ambient_noise(source, duration=1)

    print("Say something...")
    audio = recognizer.listen(source)

print("Recognizing...")

try:
    text = recognizer.recognize_google(audio)
    print("You said:", text)

except sr.UnknownValueError:
    print("Could not understand the audio.")

except sr.RequestError as error:
    print("Recognition service error:", error)