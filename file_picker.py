from __future__ import annotations

import subprocess
from pathlib import Path

from deployment import supports_native_picker

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


def pick_pdfs() -> list[Path]:
    if not supports_native_picker():
        return []
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
