# tabs/tab_search.py
import os, re, threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Static, Button, Input, OptionList, TextArea
from textual.widgets.option_list import Option
from textual.screen import ModalScreen

import config
from database import connect_to_specific_database, check_patch_db
from settings_db import get_databases_list

class ConfirmDeleteScreen(ModalScreen[bool]):
    """Модальне вікно для підтвердження видалення."""
    
    def __init__(self, filename: str, **kwargs):
        super().__init__(**kwargs)
        self.filename = filename

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm_dialog"):
            # Використовуємо Static замість Label
            yield Static(f"Ви дійсно бажаєте видалити файл:\n{self.filename}?", id="confirm_msg")
            with Horizontal(id="confirm_buttons"):
                yield Button("Видалити", variant="error", id="btn_yes")
                yield Button("Скасувати", variant="primary", id="btn_no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "btn_yes")

class ResultsList(OptionList):
    BINDINGS = [
        ("j", "cursor_down", "Наступний"), ("k", "cursor_up", "Попередній"),
        ("о", "cursor_down", "Наступний"), ("л", "cursor_up", "Попередній"),
    ]

    def action_cursor_down(self):
        self.highlighted = 0 if self.highlighted is None else min(self.highlighted + 1, self.option_count - 1)

    def action_cursor_up(self):
        self.highlighted = 0 if self.highlighted is None else max(self.highlighted - 1, 0)


class SearchTab(Container):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.documents, self.matches, self.match_index, self.current_doc_header = {}, [], -1, ""
        self.search_cancel_event = threading.Event()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        with Vertical(id="search_main"):
            with Horizontal(id="search_bar"):
                yield Input(placeholder='"прізв* ім* бать*"', id="search_input")
                yield Button("Пошук", id="btn_search", variant="primary")
                yield Button("∞", id="btn_all")
                yield Static("Від:", id="date_label_start")
                yield Input(placeholder="РРРР-ММ-ДД", id="date_start", classes="date_in")
                yield Static("До:", id="date_label_end")
                yield Input(placeholder="РРРР-ММ-ДД", id="date_end", classes="date_in")
                yield Button("Видалити", id="btn_delete", variant="error")
                
            yield Static('(введіть запит, натисніть Enter, кнопка [∞] покаже документи підряд)', id="lbl_count")

            with Horizontal(id="search_content"):
                yield ResultsList(id="results_list")
                with Vertical(id="document_panel"):
                    yield Static("", id="doc_header")
                    yield TextArea(id="doc_content", read_only=True)
                    with Horizontal(id="search_inside"):
                        yield Input(placeholder="Знайти в тексті...", id="in_text_input")
                        yield Button("Шукати", id="btn_find_in_text")
                        yield Button("⬅ Назад", id="btn_prev_match")
                        yield Button("Вперед ➡", id="btn_next_match")

            yield Static("", id="search_status")

    # автофокус на поле ввода запроса
    def on_mount(self) -> None: self.call_after_refresh(self.focus_search_input)
    def on_show(self) -> None: self.call_after_refresh(self.focus_search_input)
    def focus_search_input(self) -> None: self.query_one("#search_input", Input).focus()

    # ------------------------------------------------------------------
    # Input / buttons
    # ------------------------------------------------------------------

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search_input": self.start_search()
        elif event.input.id == "in_text_input": self.search_in_text()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_map = {
            "btn_search": lambda: self.start_search(),
            "btn_all": lambda: self.start_search(all_documents=True),
            "btn_delete": self.delete_selected,
            "btn_find_in_text": self.search_in_text,
            "btn_prev_match": lambda: self.go_to_match(self.match_index - 1),
            "btn_next_match": lambda: self.go_to_match(self.match_index + 1)
        }
        if event.button.id in btn_map: btn_map[event.button.id]()

    # ------------------------------------------------------------------
    # Search start
    # ------------------------------------------------------------------

    def start_search(self, all_documents=False) -> None:
        if self.search_cancel_event.is_set(): self.search_cancel_event.clear()

        query = self.query_one("#search_input", Input).value.strip()

        if not all_documents and (not query or query == "*"):
            self.query_one("#lbl_count", Static).update("Введіть запит для пошуку.")
            return

        start_num, end_num = self.get_date_range()
        if start_num is None or end_num is None: return

        if end_num < start_num:
            self.query_one("#lbl_count", Static).update("Кінцева дата не може бути раніше початкової.")
            return

        if all_documents: query = ""

        formatted_query = self.format_date_for_fts3(query)

        # Аналог wx: оновити список БД перед пошуком
        self.update_database_state()
        self.search_cancel_event.clear()

        self.query_one("#btn_search", Button).label = "Стоп"
        self.query_one("#search_status", Static).update("Пошук...")

        self.run_worker(
            lambda: self.search_worker(formatted_query, query, start_num, end_num),
            thread=True, exclusive=True, name="search_worker"
        )

    # ------------------------------------------------------------------
    # Dates
    # ------------------------------------------------------------------

    def get_date_range(self):
        start_text = self.query_one("#date_start", Input).value.strip() or "1900-01-01"
        end_text = self.query_one("#date_end", Input).value.strip() or "2099-12-31"

        try:
            start_date = datetime.strptime(start_text, "%Y-%m-%d")
            end_date = datetime.strptime(end_text, "%Y-%m-%d")
        except ValueError:
            self.query_one("#lbl_count", Static).update("Невірний формат дати. Використовуйте РРРР-ММ-ДД.")
            return None, None

        if end_date < start_date:
            self.query_one("#lbl_count", Static).update("Кінцева дата не може бути раніше початкової.")
            return None, None

        return int(start_date.strftime("%Y%m%d")), int(end_date.strftime("%Y%m%d"))

    # ------------------------------------------------------------------
    # FTS query
    # ------------------------------------------------------------------

    def format_date_for_fts3(self, queries: str) -> str:
        return re.sub(r'(\d{2})\.(\d{2})\.(\d{2,4})', r'\1 NEAR/0 \2 NEAR/0 \3', queries)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search_worker(self, formatted_query, original_query, start_num, end_num):
        databases = get_databases_list(config.master_password) if hasattr(config, "master_password") else []
        all_results, warnings, filename_pattern = [], [], f"%{original_query}%"

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(
                    self.search_single_database, db, formatted_query, original_query, start_num, end_num, filename_pattern
                ): db for db in databases
            }

            for future in as_completed(futures):
                if self.search_cancel_event.is_set(): break
                try:
                    db_results, warning = future.result()
                    if db_results: all_results.extend(db_results)
                    if warning: warnings.append(warning)
                except Exception as e:
                    warnings.append(f"Помилка пошуку: {e}")

        if self.search_cancel_event.is_set():
            self.app.call_from_thread(self.finish_search, "Пошук зупинено користувачем.")
            return

        for warning in warnings:
            all_results.append((warning, "", "", 0, 0, 0))

        # Аналог wx
        all_results.sort(key=lambda x: (x[3] or 0, x[4] or 0, x[5] or 0), reverse=True)
        ui_results = [(r[0], r[1], r[2]) for r in all_results]

        self.app.call_from_thread(self.update_results_ui, ui_results)

    # ------------------------------------------------------------------
    # Search one DB
    # ------------------------------------------------------------------

    def search_single_database(self, db_info, formatted_query, original_query, start_num, end_num, filename_pattern):
        if self.search_cancel_event.is_set(): return [], None

        db_id, db_name, db_path, db_password, is_active = db_info
        if not is_active: return [], None
        if not os.path.exists(db_path): return [], f"База даних '{db_name}' недоступна (файл не знайдено)."

        conn = connect_to_specific_database(db_path, db_password)
        if not conn: return [], f"Не вдалося підключитися до бази '{db_name}'."

        results = []
        try:
            cursor = conn.cursor()
            # ----------------------------------------------------------
            # Показати всі документи
            # ----------------------------------------------------------
            if original_query == "":
                sql = """SELECT filename, content, created_at, year, month, day FROM documents 
                         WHERE year * 10000 + month * 100 + day BETWEEN ? AND ?"""
                params = (start_num, end_num)
            # ----------------------------------------------------------
            # Пошук
            # ----------------------------------------------------------
            else:
                # wx має два варіанти: одна дата -> "=" | діапазон -> BETWEEN
                cond = "BETWEEN ? AND ?" if start_num != end_num else "= ?"
                sql = f"""SELECT filename, content, created_at, year, month, day FROM (
                            SELECT DISTINCT d.filename, d.content, d.created_at, d.year, d.month, d.day
                            FROM documents AS d JOIN documents_fts AS fts ON d.id = fts.docid
                            WHERE fts.content MATCH ? {"AND d.year * 10000 + d.month * 100 + d.day " + cond if start_num != end_num else ""}
                            UNION
                            SELECT filename, content, created_at, year, month, day FROM documents
                            WHERE filename LIKE ? AND year * 10000 + month * 100 + day {cond}
                        )"""
                params = (formatted_query, start_num, end_num, filename_pattern, start_num, end_num) if start_num != end_num else (formatted_query, filename_pattern, start_num)

            cursor.execute(sql, params)
            for row in cursor.fetchall():
                if self.search_cancel_event.is_set(): break
                results.append((f"[{db_name}] {row[0]}", row[1], row[2], row[3], row[4], row[5]))

        except Exception as e:
            return [], f"Помилка пошуку в БД '{db_name}': {e}"
        finally:
            conn.close()

        return results, None

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------

    def update_results_ui(self, results):
        self.documents.clear()
        self.matches, self.match_index = [], -1

        option_list = self.query_one("#results_list", OptionList)
        option_list.clear_options()
        self.query_one("#doc_header", Static).update("")
        self.query_one("#doc_content", TextArea).load_text("")

        for filename, content, created_at in results:
            self.documents[filename] = (content, created_at)
            option_list.add_option(Option(filename, id=filename))

        if results:
            self.query_one("#lbl_count", Static).update(f"Знайдено записів: {len(results)}")
            # Автоматично показати перший документ
            option_list.highlighted = 0
            # Фокус одразу на список результатів
            option_list.focus()
            self.show_document(option_list.get_option_at_index(0))
        else:
            option_list.add_option(Option("Нічого не знайдено.", id="__no_results__"))
            self.query_one("#lbl_count", Static).update("Нічого не знайдено.")

        self.query_one("#btn_search", Button).label = "Пошук"
        self.query_one("#search_status", Static).update("")

        query = self.query_one("#search_input", Input).value
        if query:
            cleaned = re.sub(r'["\'`‘’“”*]', '', query)
            self.query_one("#in_text_input", Input).value = cleaned.split()[0] if cleaned.split() else ""

    # ------------------------------------------------------------------
    # Select document
    # ------------------------------------------------------------------

    def show_document(self, option):
        doc_key = str(option.id)
        if doc_key not in self.documents: return

        content, created_at = self.documents[doc_key]
        self.current_doc_header = f"{doc_key} (дані додано: {created_at})"
        self.query_one("#doc_header", Static).update(self.current_doc_header)
        self.query_one("#doc_content", TextArea).load_text(content or "")

        self.matches, self.match_index = [], -1
        if self.query_one("#in_text_input", Input).value.strip(): self.search_in_text()
        else: self.update_match_header(0)

    def on_option_list_option_highlighted(self, event): self.show_document(event.option)
    def on_option_list_option_selected(self, event): self.show_document(event.option)

    # ------------------------------------------------------------------
    # Search inside document
    # ------------------------------------------------------------------

    def search_in_text(self):
        query = self.query_one("#in_text_input", Input).value.strip()
        full_text = self.query_one("#doc_content", TextArea).text or ""
        self.matches, self.match_index = [], -1

        # Документ не выбран або Пустой запрос
        if not full_text or not query:
            self.update_match_header(0)
            return

        # Поиск без учёта регистра
        text_lower, query_lower, start = full_text.casefold(), query.casefold(), 0

        while True:
            index = text_lower.find(query_lower, start)
            if index == -1: break
            self.matches.append(index)
            start = index + len(query_lower)

        if self.matches:
            self.match_index = 0
            self.highlight_matches()

        self.update_match_header(len(self.matches))

    # ------------------------------------------------------------------
    # Match navigation
    # ------------------------------------------------------------------

    def go_to_match(self, index):
        if not self.matches: return
        self.match_index = index % len(self.matches)
        self.highlight_matches()

    def highlight_matches(self):
        text_area = self.query_one("#doc_content", TextArea)
        if not self.matches: return
        pos = self.matches[self.match_index]

        try:
            text = text_area.text
            line = text.count("\n", 0, pos)
            last_newline = text.rfind("\n", 0, pos)
            column = pos if last_newline == -1 else pos - last_newline - 1

            text_area.cursor_location = (line, column)
            text_area.scroll_cursor_visible()
        except Exception as e:
            self.app.notify(f"Помилка переходу до збігу: {e}", severity="error")

    def update_match_header(self, count):
        header = self.query_one("#doc_header", Static)
        if not self.current_doc_header: header.update("")
        elif count: header.update(f"{self.current_doc_header} - [ збігів: {count} ]")
        else: header.update(self.current_doc_header)

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------
    def delete_selected(self):
        if not check_patch_db():
            self.app.notify("Операція видалення недоступна.", severity="error")
            return

        option_list = self.query_one("#results_list", OptionList)
        if option_list.highlighted is None:
            self.app.notify("Файл не вибрано.", severity="warning")
            return

        index = option_list.highlighted
        filename = str(option_list.get_option_at_index(index).id)
        match = re.match(r'^\[(.*?)\]\s+(.*)$', filename)

        if not match:
            self.app.notify("Не вдалося визначити базу даних.", severity="error")
            return

        db_name, clean_filename = match.group(1), match.group(2)

        # Передаємо обробник закриття модального вікна
        def on_confirm(confirmed: bool) -> None:
            if confirmed:
                self._perform_deletion(index, filename, db_name, clean_filename)

        # Показуємо вікно підтвердження
        self.app.push_screen(ConfirmDeleteScreen(clean_filename), on_confirm)

    def _perform_deletion(self, index: int, filename: str, db_name: str, clean_filename: str):
        option_list = self.query_one("#results_list", OptionList)
        databases = get_databases_list(config.master_password)

        target_path, target_password = None, None
        for _, name, path, password, _ in databases:
            if name == db_name:
                target_path, target_password = path, password
                break

        if not target_path:
            self.app.notify(f"Не знайдено шлях до бази '{db_name}'.", severity="error")
            return

        conn = connect_to_specific_database(target_path, target_password)
        if not conn:
            self.app.notify(f"Не вдалося підключитися до бази '{db_name}'.", severity="error")
            return

        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM documents WHERE filename = ?", (clean_filename,))
            conn.commit()

            if cursor.rowcount == 0:
                self.app.notify(f"Файл {clean_filename} не знайдено.", severity="warning")
                return

            option_list.remove_option_at_index(index)
            self.documents.pop(filename, None)

            self.query_one("#doc_content", TextArea).load_text("")
            self.query_one("#doc_header", Static).update("")
            self.query_one("#lbl_count", Static).update(f"Знайдено записів: {option_list.option_count}")
            self.app.notify(f"Видалено: {clean_filename}")
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def update_database_state(self):
        """
        В wx тут викликається: tab_settings.load_databases_into_ui()
        В TUI це поки не потрібно, оскільки список БД читається непосредственно перед пошуком.
        """
        pass

    def update_start_date(self, date_obj):
        self.query_one("#date_start", Input).value = date_obj.strftime("%Y-%m-%d")

    def set_count_message(self, message):
        self.query_one("#lbl_count", Static).update(message)

    def finish_search(self, message):
        self.query_one("#btn_search", Button).label = "Пошук"
        self.query_one("#search_status", Static).update("")
        self.query_one("#lbl_count", Static).update(message)




