import subprocess

def open_tray():
    result = subprocess.run(["eject"])
    if result.returncode != 0:
        raise Exception("Failed to open tray")


def close_tray():
    result = subprocess.run(["eject", "-t"])
    if result.returncode != 0:
        raise Exception("Failed to close tray")
    
