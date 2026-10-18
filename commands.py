import os
import subprocess
import webbrowser
from urllib.parse import quote_plus


def execute_command(command):
    command = command.lower().strip()

    # Open Chrome
    if command == "open chrome":
        subprocess.Popen(
            ["cmd", "/c", "start", "", "chrome"],
            shell=False
        )
        return "Opened Chrome"

    # Open File Explorer
    elif command == "open file explorer":
        subprocess.Popen(["explorer"])
        return "Opened File Explorer"

    # Open Downloads folder
    elif command == "open downloads":
        downloads_path = os.path.join(
            os.path.expanduser("~"),
            "Downloads"
        )

        os.startfile(downloads_path)
        return "Opened Downloads"

    # Open YouTube
    elif command == "open youtube":
        webbrowser.open("https://www.youtube.com")
        return "Opened YouTube"

    # Open Google
    elif command == "open google":
        webbrowser.open("https://www.google.com")
        return "Opened Google"

    # Google search
    elif command.startswith("search google for "):
        search_query = command.replace(
            "search google for ",
            "",
            1
        ).strip()

        if search_query:
            encoded_query = quote_plus(search_query)

            webbrowser.open(
                f"https://www.google.com/search?q={encoded_query}"
            )

            return f"Searched Google for {search_query}"

        return "Please provide something to search for"

    else:
        return "Command not supported"