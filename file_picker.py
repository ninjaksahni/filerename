from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_MACOS_SCRIPT = """
try
    set fileList to choose file with prompt "Select challan PDFs" with multiple selections allowed of type {"pdf", "PDF", "com.adobe.pdf"}
    set pathList to {}
    repeat with f in fileList
        set end of pathList to POSIX path of f
    end repeat
    set AppleScript's text item delimiters to linefeed
    return pathList as text
on error number -128
    return ""
end try
"""

_TK_SCRIPT = """
import json
import tkinter as tk
from tkinter import filedialog

root = tk.Tk()
root.withdraw()
root.attributes("-topmost", True)
try:
    files = filedialog.askopenfilenames(
        title="Select challan PDFs",
        filetypes=[("PDF files", "*.pdf")],
    )
finally:
    root.destroy()
print(json.dumps(list(files)))
"""


def pick_pdfs() -> list[Path]:
    if sys.platform == "darwin":
        return _pick_pdfs_macos()
    return _pick_pdfs_tk_subprocess()


def _pick_pdfs_macos() -> list[Path]:
    result = subprocess.run(
        ["osascript", "-e", _MACOS_SCRIPT],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    if result.returncode != 0 and result.stderr.strip():
        raise RuntimeError(result.stderr.strip())
    raw = result.stdout.strip()
    if not raw:
        return []
    return [Path(line) for line in raw.splitlines() if line.strip()]


def _pick_pdfs_tk_subprocess() -> list[Path]:
    result = subprocess.run(
        [sys.executable, "-c", _TK_SCRIPT],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "File picker failed")
    chosen = json.loads(result.stdout.strip() or "[]")
    return [Path(item) for item in chosen if item]
