import os
import hashlib
from datetime import datetime
from textual.app import ComposeResult
from textual.widgets import Static, Button, Select, RichLog, Input
from textual.containers import Container, Horizontal, Vertical
from textual.worker import Worker, WorkerState
from docx import Document

import config
from database import connect_to_specific_database, populate_databases_choice
from config import document_number_pattern
from utils import extract_text_libreoffice, get_document_date, normalize_text

class ImportTab(Container):
    def compose(self) -> ComposeResult:
        with Vertical(id="import_main"):
            yield Static("[bold red]УВАГА![/bold red] Дозволені тільки .doc, .docx, .rtf.")

            with Horizontal(id="import_db_row"):
                yield Static("Цільова база даних:", classes="label")
                yield Select(
                    [],
                    prompt="Оберіть базу даних",
                    id="import_db_select"
                )
                yield Static("", id="import_db_selected")

            yield Input(
                placeholder="Введіть шлях до папки з документами...",
                id="import_folder_input"
            )

            with Horizontal(id="import_buttons"):
                yield Button("Сканувати папку", id="btn_start_scan", variant="success")
                yield Button("Зупинити", id="btn_stop_scan", variant="error", disabled=True)

            yield Static("", id="import_status_label")

            yield RichLog(id="import_log", highlight=True)

    def on_mount(self) -> None:
        self.call_after_refresh(self.load_databases)

    def on_show(self) -> None:
        """Передаємо фокус на поле введення папки при переключенні на вкладку"""
        self.call_after_refresh(self._focus_input)

    def _focus_input(self) -> None:
        try:
            self.query_one("#import_folder_input", Input).focus()
        except Exception:
            pass

    def load_databases(self) -> None:
        select = self.query_one("#import_db_select", Select)
        choices = populate_databases_choice()

        self.app.notify(
            f"Баз знайдено: {len(choices)}",
            severity="information"
        )

        # Вимикаємо автоматичне реагування під час заповнення
        select.set_options([
            (label, value)
            for label, value in choices
        ])

        if choices:
            select.value = choices[0][1]
            db_path, _ = choices[0][1]
            self.query_one("#import_db_selected", Static).update(
                f"Обрана: {os.path.basename(db_path)}"
            )

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "import_db_select":
            return

        if event.value is Select.BLANK or event.value is Select.NULL:
            self.query_one("#import_db_selected", Static).update(
                "База не обрана"
            )
            return

        db_path, _ = event.value
        self.query_one("#import_db_selected", Static).update(
            f"Обрана: {os.path.basename(db_path)}"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_start_scan":
            folder = self.query_one("#import_folder_input", Input).value.strip()
            db_data = self.query_one("#import_db_select", Select).value
            
            if db_data is Select.NULL or db_data is Select.BLANK:
                self.app.notify("Оберіть базу даних!", severity="error")
                return
            if not folder or not os.path.exists(folder):
                self.app.notify("Вкажіть існуючу папку!", severity="error")
                return

            db_path, db_password = db_data
            self.query_one("#btn_start_scan").disabled = True
            self.query_one("#btn_stop_scan").disabled = False
            self.stop_processing = False

            self.run_worker(
                lambda: self.process_documents_worker(folder, db_path, db_password),
                exclusive=True,
                thread=True,
                name="import_worker"
            )

        elif event.button.id == "btn_stop_scan":
            self.stop_processing = True
            self.query_one("#import_status_label", Static).update("Зупинка після поточного файлу...")

    def process_documents_worker(self, doc_folder: str, db_path: str, db_password: str) -> None:
        log = self.query_one("#import_log", RichLog)
        status = self.query_one("#import_status_label", Static)

        conn = connect_to_specific_database(db_path, db_password)
        if not conn:
            self.app.call_from_thread(status.update, "Помилка підключення до бази")
            return

        try:
            cursor = conn.cursor()
            files_to_process = []
            allowed_extensions = ('.doc', '.docx', '.rtf')

            for root, _, files in os.walk(doc_folder):
                for file in files:
                    ext = os.path.splitext(file.lower())[1]
                    if ext in allowed_extensions and not file.startswith(('~', '.')):
                        files_to_process.append(os.path.join(root, file))

            total = len(files_to_process)
            new_records, skipped = 0, 0

            for i, filepath in enumerate(files_to_process):
                if getattr(self, "stop_processing", False):
                    break

                filename = os.path.basename(filepath)
                ext = os.path.splitext(filename.lower())[1]
                content = ""

                if ext == '.docx':
                    try:
                        doc = Document(filepath)
                        content = "\n".join([p.text for p in doc.paragraphs])
                    except Exception as e:
                        self.app.call_from_thread(log.write, f"Помилка {filename}: {e}")
                else:
                    content = extract_text_libreoffice(filepath)

                if not content or not content.strip():
                    skipped += 1
                    continue

                filename = normalize_text(filename)
                content = normalize_text(content)
                doc_year, doc_month, doc_day = get_document_date(filename, os.path.dirname(filepath))
                
                doc_num_match = document_number_pattern.search(filename)
                doc_num = int(doc_num_match.group(1)) if doc_num_match else None
                created_at_str = datetime.fromtimestamp(os.path.getctime(filepath)).strftime('%Y-%m-%d %H:%M:%S')
                text_hash = hashlib.md5(content.encode('utf-8')).hexdigest()

                cursor.execute("SELECT content_hash FROM documents WHERE filename = ?", (filename,))
                existing = cursor.fetchone()

                if existing:
                    if existing[0] != text_hash:
                        cursor.execute("""
                            UPDATE documents SET year=?, month=?, day=?, content=?, 
                            document_number=?, created_at=?, content_hash=? WHERE filename=?
                        """, (doc_year, doc_month, doc_day, content, doc_num, created_at_str, text_hash, filename))
                        new_records += 1
                        self.app.call_from_thread(log.write, f"Оновлено: {filename}")
                    else:
                        skipped += 1
                else:
                    cursor.execute("""
                        INSERT INTO documents (filename, year, month, day, content, document_number, created_at, content_hash)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (filename, doc_year, doc_month, doc_day, content, doc_num, created_at_str, text_hash))
                    new_records += 1
                    self.app.call_from_thread(log.write, f"Додано: {filename}")

                self.app.call_from_thread(status.update, f"Обробка... ({i+1}/{total})")

            conn.commit()
            cursor.execute("INSERT INTO documents_fts(documents_fts) VALUES('optimize');")
            conn.commit()
            self.app.call_from_thread(status.update, f"Завершено. Додано/оновлено: {new_records}, пропущено: {skipped}")

        finally:
            conn.close()

            def reset_buttons():
                self.query_one("#btn_start_scan").disabled = False
                self.query_one("#btn_stop_scan").disabled = True

            self.app.call_from_thread(reset_buttons)
