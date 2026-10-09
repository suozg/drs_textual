# main_frame.py
import os
from textual.app import App, ComposeResult
from textual.containers import Container, Grid
from textual.screen import ModalScreen
from textual.widgets import Header, Footer, TabbedContent, TabPane, Input, Button, Static, Select
from textual import events
from pathlib import Path
import sys

import config
from settings_db import init_settings_db, get_databases_list, add_database_to_settings, verify_database_password
from database import create_new_database
from tabs.tab_search import SearchTab
from tabs.tab_import import ImportTab
from tabs.tab_sql import SqlTab
from tabs.tab_about import AboutTab, SokobanWidget
from tabs.tab_settings import SettingsTab


# ============================================================================
# Пароль майстер-БД
# ============================================================================

class PasswordModal(ModalScreen[str | None]):
    """Запит майстер-пароля."""
    BINDINGS = [("ctrl+q", "quit_app", "Вихід")]

    def compose(self) -> ComposeResult:
        with Grid(id="dialog"):
            yield Static("Введіть Майстер-Пароль", id="password_prompt")
            yield Input(password=True, placeholder="Майстер-пароль", id="master_pwd_input")
            yield Button("Увійти", id="btn_login", variant="primary")

    def action_quit_app(self) -> None: self.app.exit()

    def _submit_password(self, password: str) -> None:
        if not password:
            self.app.notify("Пароль не може бути порожнім.", severity="error")
            return
        self.dismiss(password)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_login":
            self._submit_password(self.query_one("#master_pwd_input", Input).value.strip())

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "master_pwd_input":
            self._submit_password(event.value.strip())


# ============================================================================
# Створення / підключення робочої БД
# ============================================================================

class DatabaseChoiceModal(ModalScreen[str | None]):
    """Вибір: створити нову БД або підключити існуючу."""

    def compose(self) -> ComposeResult:
        with Grid(id="dialog"):
            yield Static("Базу даних не знайдено.\nЩо потрібно зробити?", id="db_choice_prompt")
            yield Button("Створити нову", id="btn_create_db", variant="primary")
            yield Button("Підключити існуючу", id="btn_connect_db")
            yield Button("Скасувати", id="btn_cancel_db")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        choice_map = {"btn_create_db": "create", "btn_connect_db": "connect", "btn_cancel_db": None}
        if event.button.id in choice_map:
            self.dismiss(choice_map[event.button.id])


# ============================================================================
# Створення нової БД
# ============================================================================

class CreateDatabaseModal(ModalScreen[tuple[str, str] | None]):
    """Введення шляху та пароля нової БД."""

    def compose(self) -> ComposeResult:
        with Grid(id="dialog"):
            yield Static("Створення нової бази даних", id="create_db_title")
            yield Input(placeholder="Шлях до файлу .db", id="db_path_input")
            yield Input(placeholder="Пароль бази даних", password=True, id="db_password_input")
            yield Input(placeholder="Підтвердження пароля", password=True, id="db_password_confirm")
            yield Button("Створити", id="btn_create", variant="primary")
            yield Button("Скасувати", id="btn_cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_cancel":
            self.dismiss(None)
            return
        if event.button.id != "btn_create": return

        db_path = self.query_one("#db_path_input", Input).value.strip()
        pwd = self.query_one("#db_password_input", Input).value.strip()
        pwd_confirm = self.query_one("#db_password_confirm", Input).value.strip()

        if not db_path:
            self.app.notify("Вкажіть шлях до бази даних.", severity="error")
            return
        if not db_path.endswith(".db"): db_path += ".db"
        if not pwd:
            self.app.notify("Пароль бази даних не може бути порожнім.", severity="error")
            return
        if pwd != pwd_confirm:
            self.app.notify("Паролі не збігаються.", severity="error")
            return

        self.dismiss((db_path, pwd))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "db_password_confirm":
            self.query_one("#btn_create", Button).press()


# ============================================================================
# Підключення існуючої БД
# ============================================================================

class ConnectDatabaseModal(ModalScreen[tuple[str, str] | None]):
    """Введення шляху та пароля існуючої БД."""

    def compose(self) -> ComposeResult:
        with Grid(id="dialog"):
            yield Static("Підключення існуючої бази даних", id="connect_db_title")
            yield Input(placeholder="Шлях до файлу .db", id="db_path_input")
            yield Input(placeholder="Пароль бази даних", password=True, id="db_password_input")
            yield Button("Підключити", id="btn_connect", variant="primary")
            yield Button("Скасувати", id="btn_cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_cancel":
            self.dismiss(None)
            return
        if event.button.id != "btn_connect": return

        db_path = self.query_one("#db_path_input", Input).value.strip()
        pwd = self.query_one("#db_password_input", Input).value.strip()

        if not db_path:
            self.app.notify("Вкажіть шлях до бази даних.", severity="error")
            return
        if not os.path.exists(db_path):
            self.app.notify("Файл бази даних не знайдено.", severity="error")
            return
        if not pwd:
            self.app.notify("Пароль бази даних не може бути порожнім.", severity="error")
            return

        self.dismiss((db_path, pwd))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "db_password_input":
            self.query_one("#btn_connect", Button).press()


# ============================================================================
# Основний інтерфейс
# ============================================================================

class MainScreen(Container):
    """Основний інтерфейс програми."""

    def compose(self) -> ComposeResult:
        with TabbedContent(id="main_tabs"):
            with TabPane("Пошук (F1)", id="tab_search"): yield SearchTab()
            with TabPane("Імпорт (F2)", id="tab_import"): yield ImportTab()
            with TabPane("SQL (F3)", id="tab_sql"): yield SqlTab()
            with TabPane("Налаштування (F4)", id="tab_settings"): yield SettingsTab()
            with TabPane("Про програму (F5)", id="tab_about"): yield AboutTab()

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        """Передача фокусу під час активації конкретної вкладки."""
        if event.tabbed_content.active == "tab_about":
            try:
                self.query_one(SokobanWidget).focus()
            except Exception:
                pass


# ============================================================================
# Application
# ============================================================================

class DrsApp(App):
    TITLE = "Document Retrieval System"
    CSS_PATH = "styles.tcss"

    BINDINGS = [
        ("ctrl+q", "quit", "Вихід"),
        ("f6", "toggle_theme", "Змінити тему"),
    ]

    # ПРІОРИТЕТНИЙ ОБРОБНИК КЛАВІШ (Перехоплює F1-F5 до полів ввода)
    def on_key(self, event: events.Key) -> None:
        tab_map = {
            "f1": "tab_search",
            "f2": "tab_import",
            "f3": "tab_sql",
            "f4": "tab_settings",
            "f5": "tab_about",
        }
        
        key = event.key.lower()
       
        if key in tab_map:
            # Скинути поточний фокус, щоб поля ввода не блокували інтерфейс
            self.set_focus(None)
            
            try:
                tabs = self.query_one("#main_tabs", TabbedContent)
                tabs.active = tab_map[key]
            except Exception:
                pass
            
            # Зупинити подальшу обробку клавіші у системі
            event.stop()
            event.prevent_default()

    def is_lightmode_enabled(self) -> bool:
        return (
            sys.platform.startswith("linux")
            and (Path.home() / ".lightmode").exists()
        )

    def get_initial_theme(self) -> str:
        return (
            "textual-light"
            if self.is_lightmode_enabled()
            else "textual-dark"
            )

    def action_toggle_theme(self) -> None:
        self.theme = (
            "textual-dark"
            if self.theme == "textual-light"
            else "textual-light"
        )

    def check_system_theme(self) -> None:
        current_state = self.is_lightmode_enabled()

        if current_state == self._last_lightmode_state:
            return

        self._last_lightmode_state = current_state
        self.theme = (
            "textual-light"
            if current_state
            else "textual-dark"
        )

    def on_mount(self) -> None:
        self.theme = self.get_initial_theme()
        self._last_lightmode_state = self.is_lightmode_enabled()
        self.set_interval(5, self.check_system_theme)

        self.push_screen(
            PasswordModal(),
            self.on_password_entered,
        )

    def on_password_entered(self, master_password: str | None) -> None:
        if not master_password:
            self.exit()
            return

        config.master_password = master_password
        first_run = not os.path.exists(config.SETTINGS_DB_PATH)

        try:
            init_settings_db(master_password)
        except Exception as e:
            self.notify(f"Помилка ініціалізації налаштувань: {e}", severity="error")
            config.master_password = ""
            self.push_screen(PasswordModal(), self.on_password_entered)
            return

        if first_run:
            self.push_screen(DatabaseChoiceModal(), self.on_database_choice)
            return

        self.load_registered_databases(master_password)

    def on_database_choice(self, choice: str | None) -> None:
        if choice is None: self.exit()
        elif choice == "create": self.push_screen(CreateDatabaseModal(), self.on_create_database)
        elif choice == "connect": self.push_screen(ConnectDatabaseModal(), self.on_connect_database)

    def on_create_database(self, result: tuple[str, str] | None) -> None:
        if result is None:
            self.exit()
            return

        db_path, db_password = result
        try:
            create_new_database(db_path, db_password)
            add_database_to_settings(config.master_password, os.path.basename(db_path), db_path, db_password)
            config.db_path, config.password = db_path, db_password
        except Exception as e:
            self.notify(f"Не вдалося створити базу даних: {e}", severity="error")
            self.push_screen(DatabaseChoiceModal(), self.on_database_choice)
            return

        self.start_main_screen()

    def on_connect_database(self, result: tuple[str, str] | None) -> None:
        if result is None:
            self.exit()
            return

        db_path, db_password = result
        success, error_message = verify_database_password(db_path, db_password)

        if not success:
            self.notify(f"Не вдалося підключити БД: {error_message}", severity="error")
            self.push_screen(ConnectDatabaseModal(), self.on_connect_database)
            return

        try:
            add_database_to_settings(config.master_password, os.path.basename(db_path), db_path, db_password)
            config.db_path, config.password = db_path, db_password
        except Exception as e:
            self.notify(f"Не вдалося зберегти БД у налаштуваннях: {e}", severity="error")
            return

        self.start_main_screen()

    def load_registered_databases(self, master_password: str) -> None:
        try:
            databases = get_databases_list(master_password)
        except Exception as e:
            self.notify(f"Помилка авторизації: {e}", severity="error")
            config.master_password = ""
            self.push_screen(PasswordModal(), self.on_password_entered)
            return

        active_databases = [row for row in databases if row[4]]

        if not active_databases:
            self.push_screen(DatabaseChoiceModal(), self.on_database_choice)
            return

        _, _, db_path, db_password, _ = active_databases[0]

        if not os.path.exists(db_path):
            self.notify(f"Файл БД не знайдено:\n{db_path}", severity="error")
            self.push_screen(DatabaseChoiceModal(), self.on_database_choice)
            return

        success, error_message = verify_database_password(db_path, db_password)
        if not success:
            self.notify(f"Не вдалося відкрити БД:\n{error_message}", severity="error")
            return

        config.db_path, config.password = db_path, db_password
        self.start_main_screen()

    def start_main_screen(self) -> None: self.mount(MainScreen())

    def action_quit(self) -> None: self.exit()


if __name__ == "__main__":
    app = DrsApp()
    app.run()
