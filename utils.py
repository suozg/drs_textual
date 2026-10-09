import os
import sys
import subprocess
from datetime import datetime, date, timedelta

import config
from settings_db import get_databases_list
from config import filename_date_pattern, path_date_pattern


def populate_databases_choice(select_widget):
    """
    Заповнює варіанти для віджета Textual Select.
    Повертає список кортежів вида: [("Назва (шлях)", (path, password)), ...]
    """
    options = []
    if not hasattr(config, 'master_password') or not config.master_password:
        return options

    databases = get_databases_list(config.master_password)
    for row in databases:
        db_id, db_name, db_path, db_password, is_active = row
        if is_active:
            label = f"{db_name} ({db_path})"
            options.append((label, (db_path, db_password)))

    if select_widget and hasattr(select_widget, "set_options"):
        select_widget.set_options(options)

    return options


def get_document_date(filename, root_path):
    """
    Витягує дату документа, використовуючи назву файлу, потім шлях.
    """
    date_obj_from_filename = None

    match_filename = filename_date_pattern.search(filename)
    if match_filename:
        day_str, month_str, year_str = match_filename.groups()
        try:
            full_date_str = f"{day_str}.{month_str}.{year_str}"
            if len(year_str) == 2:
                date_obj_from_filename = datetime.strptime(full_date_str, "%d.%m.%y").date()
            else:
                date_obj_from_filename = datetime.strptime(full_date_str, "%d.%m.%Y").date()
        except ValueError:
            pass

    year_from_path, month_from_path = None, None
    if date_obj_from_filename is None:
        match_path = path_date_pattern.search(root_path)
        if match_path:
            year_from_path_str, month_from_path_str = match_path.groups()
            try:
                year_from_path = int(year_from_path_str)
                month_from_path = int(month_from_path_str)
                if not (1 <= month_from_path <= 12):
                    year_from_path, month_from_path = None, None
            except ValueError:
                pass

    current_date = date.today()

    if date_obj_from_filename:
        final_year = date_obj_from_filename.year
        final_month = date_obj_from_filename.month
        final_day = date_obj_from_filename.day
    elif year_from_path is not None and month_from_path is not None:
        final_year = year_from_path
        final_month = month_from_path
        final_day = current_date.day
        try:
            date(final_year, final_month, final_day)
        except ValueError:
            if final_month == 12:
                final_day = (date(final_year + 1, 1, 1) - timedelta(days=1)).day
            else:
                final_day = (date(final_year, final_month + 1, 1) - timedelta(days=1)).day
    else:
        # Безпечний лог у консоль замість wx.CallAfter
        print(f"Попередження: Не вдалося витягнути дату з назви '{filename}' або шляху '{root_path}'.")
        final_year = current_date.year
        final_month = current_date.month
        final_day = current_date.day

    return final_year, final_month, final_day


def normalize_text(text):
    if not text:
        return text
    # Замінюємо всі можливі варіанти апострофів на єдиний стандартний
    bad_apostrophes = ["`", "´", "‘", "’", "ʼ", "ʻ"]
    for bad in bad_apostrophes:
        text = text.replace(bad, "'")
    return text


def extract_text_libreoffice(filepath):
    try:
        output_dir = "/tmp" if os.name != "nt" else os.environ.get("TEMP", "C:\\Temp")
        result = subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "txt:Text", "--outdir", output_dir, filepath],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            raise Exception(f"Помилка при конвертації {filepath}: {result.stderr}")

        converted_filename = os.path.basename(filepath).rsplit(".", 1)[0] + ".txt"
        converted_filepath = os.path.join(output_dir, converted_filename)

        with open(converted_filepath, "r", encoding="utf-8") as file:
            text = file.read().strip()

        if os.path.exists(converted_filepath):
            os.remove(converted_filepath)
        return text
    except Exception:
        return ""


def get_full_db_path(db_path):
    current_directory = os.getcwd()
    full_db_path = os.path.join(current_directory, db_path)
    script_path = sys.argv[0]
    full_absolute_path = os.path.abspath(script_path)
    return full_db_path, full_absolute_path