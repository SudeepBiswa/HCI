import os
import re
import subprocess
import webbrowser
from urllib.parse import quote_plus


POLITE_PHRASES = (
    "hey friday", "can you", "could you", "would you", "will you",
    "can we", "could we", "would you mind", "please", "i want you to",
    "i want to", "i need you to", "i need to", "i would like you to",
    "i would like to", "i'd like you to", "i'd like to", "just"
)
OPEN_ACTION = re.compile(
    r"\b(?:open(?:ing)?(?: up)?|launch(?:ing)?|start(?:ing)?|run(?:ning)?|"
    r"show(?:ing)?(?: me)?|bring(?:ing)? up|pull(?:ing)? up|go to|visit|"
    r"navigate to|take me to|switch to|use)\b",
    re.IGNORECASE
)
SEARCH_PATTERNS = (
    re.compile(r"\bsearch(?:\s+(?:google|the web))?(?:\s+for)?\s+(.+)$", re.I),
    re.compile(r"\b(?:look up|look for|search up|find)(?: me)?\s+(?:for\s+)?(.+)$", re.I),
    re.compile(r"\bgoogle\s+(?:for\s+)?(.+)$", re.I),
    re.compile(r"\bwhat(?:\s+is|'s)\s+(.+)$", re.I),
    re.compile(r"\btell me about\s+(.+)$", re.I),
)
TARGETS = (
    ("chrome", ("google chrome", "chrome", "chrome browser", "web browser", "browser")),
    ("file explorer", ("file explorer", "explorer", "file manager", "files")),
    ("downloads", ("downloads", "download folder", "downloads folder")),
    ("youtube", ("youtube", "youtube website")),
    ("google", ("google", "google website", "google home page")),
)


def _clean_command(command):
    text = re.sub(r"[^\w\s'-]", " ", str(command), flags=re.UNICODE)
    for phrase in POLITE_PHRASES:
        text = re.sub(
            rf"^(?:{re.escape(phrase)}\b\s*)+", "", text, flags=re.I
        )
    text = re.sub(r"\s+(?:please|for me|thanks|thank you|now)$", "", text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip()


def _search_query(command):
    for pattern in SEARCH_PATTERNS:
        match = pattern.search(command)
        if match:
            query = re.sub(
                r"\s+(?:on google|on the web)$", "", match.group(1), flags=re.I
            ).strip(" \'\"")
            return query
    if re.fullmatch(r"(?:search|look up|find)(?: google)?", command, re.I):
        return ""
    return None


def _open_target(command):
    action = OPEN_ACTION.search(command)
    if not action:
        return None
    target = re.sub(r"^(?:the|my|a|an)\s+", "", command[action.end():], flags=re.I)
    target = re.sub(r"\s+(?:app|application|website|webpage|page|folder)$", "", target, flags=re.I)
    target = re.sub(r"\s+", " ", target).strip().lower()
    for result, aliases in TARGETS:
        if target in aliases:
            return result
    return None


def execute_command(command):
    """Interpret a natural phrasing and return (success, response)."""
    text = _clean_command(command)
    query = _search_query(text)
    if query is not None:
        if not query:
            return False, "What would you like me to search for?"
        webbrowser.open(f"https://www.google.com/search?q={quote_plus(query)}")
        return True, f"Searching Google for {query}"

    target = _open_target(text)
    if target == "chrome":
        subprocess.Popen(["cmd", "/c", "start", "", "chrome"], shell=False)
        return True, "Opening Chrome"
    if target == "file explorer":
        subprocess.Popen(["explorer"])
        return True, "Opening File Explorer"
    if target == "downloads":
        downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        os.startfile(downloads)
        return True, "Opening Downloads"
    if target == "youtube":
        webbrowser.open("https://www.youtube.com")
        return True, "Opening YouTube"
    if target == "google":
        webbrowser.open("https://www.google.com")
        return True, "Opening Google"
    return False, (
        "I can open Chrome, File Explorer, Downloads, YouTube, or Google, "
        "and search Google. What would you like?"
    )
