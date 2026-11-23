"""Portapapeles de Windows: copia un archivo de texto UTF-8 conservando tildes y emojis."""
import subprocess
import sys
from pathlib import Path


def copy_file_to_clipboard(path: Path) -> bool:
    """Copia el contenido de un archivo UTF-8 al portapapeles de Windows. False si no se pudo (o no es Windows)."""
    if sys.platform != "win32":
        return False
    safe = str(path).replace("'", "''")
    cmd = f"Set-Clipboard -Value ((Get-Content -Raw -Encoding UTF8 -LiteralPath '{safe}').TrimEnd())"
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", cmd], check=True, timeout=20, capture_output=True)
        return True
    except (OSError, subprocess.SubprocessError):
        return False
