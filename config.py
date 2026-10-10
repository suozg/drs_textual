import os
from pathlib import Path
import re

password = None
frame_title = "Document Retrieval System"
master_password = ""
db_path = ""

def get_config_dir(app_name="drs"):
    if os.name == "nt":
        base_dir = os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")
    else:
        base_dir = os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
    
    config_dir = Path(base_dir) / app_name
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir

SETTINGS_DB_PATH = str(get_config_dir("drs") / "settings.db")

filename_date_pattern = re.compile(r'(?:від\s?)?(\d{1,2})\.(\d{1,2})\.(\d{4}|\d{2})')
document_number_pattern = re.compile(r'(?:№|\s|^)(\d+)')
path_date_pattern = re.compile(r"[/\\](\d{4})[/\\](\d{1,2})[/\\]?")
