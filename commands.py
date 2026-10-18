import os
import subprocess


def execute_command(command):
    command = command.lower().strip()

    if command == "open chrome":
        subprocess.Popen(
            ["cmd", "/c", "start", "", "chrome"],
            shell=False
        )
        return "Opened Chrome"

    elif command == "open file explorer":
        subprocess.Popen(["explorer"])
        return "Opened File Explorer"

    elif command == "open downloads":
        downloads_path = os.path.join(
            os.path.expanduser("~"),
            "Downloads"
        )

        os.startfile(downloads_path)
        return "Opened Downloads"

    else:
        return "Command not supported"