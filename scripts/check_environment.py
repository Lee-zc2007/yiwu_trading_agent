from pathlib import Path
import shutil
import socket
import subprocess
import sys


def version(command: str) -> str:
    executable = shutil.which(command)
    if not executable:
        return "not installed"
    try:
        return subprocess.check_output([executable, "--version"], text=True, stderr=subprocess.STDOUT).strip()
    except Exception as exc:
        return f"error: {exc}"


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("127.0.0.1", port)) != 0


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    print(f"Project: {root}")
    print(f"Python: {sys.version.split()[0]}")
    for command in ("node", "npm", "git", "docker"):
        print(f"{command}: {version(command)}")
    for port in (5173, 8000):
        print(f"Port {port}: {'free' if port_free(port) else 'in use'}")

