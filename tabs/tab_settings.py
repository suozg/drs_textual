import os

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Grid
from textual.screen import ModalScreen
from textual.widgets import (
    Static,
    Button,
    DataTable,
    Input,
    RadioButton,
    RadioSet,
    RichLog,
)

import config
from sqlcipher3 import dbapi2 as sqlite3

from settings_db import (
    get_databases_list,
    remove_database_from_settings,
    add_database_to_settings,
    verify_database_password,
    update_database_password,
    change_master_password,
)

from database import create_new_database


# ============================================================================
# Модальне вікно створення БД
# ============================================================================

class CreateDatabaseScreen(ModalScreen[tuple[str, str] | None]):

    def compose(self) -> ComposeResult:
        with Grid(id="settings_dialog"):
            yield Static(
                "Створення нової бази даних",
                id="settings_dialog_title",
            )

            yield Input(
                placeholder="Шлях до файлу .db",
                id="settings_db_path",
            )

            yield Input(
                placeholder="Пароль бази даних",
                password=True,
                id="settings_db_password",
            )

            yield Input(
                placeholder="Підтвердження пароля",
                password=True,
                id="settings_db_password_confirm",
            )

            with Horizontal():
                yield Button(
                    "Створити",
                    id="settings_create",
                    variant="primary",
                )
                yield Button(
                    "Скасувати",
                    id="settings_create_cancel",
                )

    def on_button_pressed(self, event: Button.Pressed) -> None:

        if event.button.id == "settings_create_cancel":
            self.dismiss(None)
            return

        if event.button.id != "settings_create":
            return

        self.create_database()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "settings_db_password_confirm":
            self.create_database()

    def create_database(self) -> None:

        db_path = self.query_one(
            "#settings_db_path",
            Input,
        ).value.strip()

        password = self.query_one(
            "#settings_db_password",
            Input,
        ).value.strip()

        password_confirm = self.query_one(
            "#settings_db_password_confirm",
            Input,
        ).value.strip()

        if not db_path:
            self.app.notify(
                "Вкажіть шлях до бази даних.",
                severity="error",
            )
            return

        if not db_path.lower().endswith(".db"):
            db_path += ".db"

        if os.path.exists(db_path):
            self.app.notify(
                "Файл бази даних вже існує.",
                severity="error",
            )
            return

        if not password:
            self.app.notify(
                "Пароль бази даних не може бути порожнім.",
                severity="error",
            )
            return

        if password != password_confirm:
            self.app.notify(
                "Паролі не збігаються.",
                severity="error",
            )
            return

        self.dismiss((db_path, password))


# ============================================================================
# Модальне вікно підключення існуючої БД
# ============================================================================

class AddDatabaseScreen(ModalScreen[tuple[str, str] | None]):

    def compose(self) -> ComposeResult:
        with Grid(id="settings_dialog"):
            yield Static(
                "Підключення існуючої бази даних",
                id="settings_dialog_title",
            )

            yield Input(
                placeholder="Шлях до файлу .db",
                id="settings_add_path",
            )

            yield Input(
                placeholder="Пароль бази даних",
                password=True,
                id="settings_add_password",
            )

            with Horizontal():
                yield Button(
                    "Підключити",
                    id="settings_add",
                    variant="primary",
                )
                yield Button(
                    "Скасувати",
                    id="settings_add_cancel",
                )

    def on_button_pressed(self, event: Button.Pressed) -> None:

        if event.button.id == "settings_add_cancel":
            self.dismiss(None)
            return

        if event.button.id != "settings_add":
            return

        self.connect_database()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "settings_add_password":
            self.connect_database()

    def connect_database(self) -> None:

        db_path = self.query_one(
            "#settings_add_path",
            Input,
        ).value.strip()

        password = self.query_one(
            "#settings_add_password",
            Input,
        ).value.strip()

        if not db_path:
            self.app.notify(
                "Вкажіть шлях до бази даних.",
                severity="error",
            )
            return

        if not os.path.exists(db_path):
            self.app.notify(
                "Файл бази даних не знайдено.",
                severity="error",
            )
            return

        if not password:
            self.app.notify(
                "Пароль бази даних не може бути порожнім.",
                severity="error",
            )
            return

        success, message = verify_database_password(
            db_path,
            password,
        )

        if not success:
            self.app.notify(
                f"Не вдалося відкрити базу: {message}",
                severity="error",
            )
            return

        self.dismiss((db_path, password))


# ============================================================================
# Settings
# ============================================================================

class SettingsTab(Container):

    def on_show(self) -> None:
        self.call_after_refresh(
            lambda: self.query_one("#old_pass", Input).focus()
        )

    def compose(self) -> ComposeResult:

        yield Static(
            "[bold]Підключені бази даних[/bold]"
        )

        yield DataTable(
            id="db_table",
            cursor_type="row",
        )

        with Horizontal(id="settings_db_buttons"):
            yield Button(
                "Створити базу",
                id="btn_create_db",
            )

            yield Button(
                "Додати базу",
                id="btn_add_db",
            )

            yield Button(
                "Зробити активною",
                id="btn_activate_db",
                variant="primary",
            )

            yield Button(
                "Оновити",
                id="btn_refresh_db",
            )

            yield Button(
                "Видалити",
                id="btn_delete_db",
                variant="error",
            )

        yield Static(
            "\n[bold]Керування паролями[/bold]"
        )

        yield Static(
            "Активна база для зміни пароля: не обрана",
            id="active_db_label",
        )
        
        with RadioSet(id="pass_target"):

            yield RadioButton(
                "Змінити Майстер-пароль",
                value=True,
                id="target_master",
            )

            yield RadioButton(
                "Змінити пароль активної бази даних",
                id="target_db",
            )

        yield Input(
            placeholder="Старий пароль",
            password=True,
            id="old_pass",
        )

        yield Input(
            placeholder="Новий пароль",
            password=True,
            id="new_pass1",
        )

        yield Input(
            placeholder="Повторіть новий пароль",
            password=True,
            id="new_pass2",
        )

        yield Button(
            "Змінити пароль",
            id="btn_change_pass",
            variant="primary",
        )

        yield RichLog(
            id="settings_log",
        )


    def update_active_database_label(self) -> None:
        label = self.query_one("#active_db_label", Static)
        active_path = getattr(config, "db_path", None)

        if not active_path:
            label.update("Активна база для зміни пароля: не обрана")
            return

        try:
            databases = get_databases_list(config.master_password)
        except Exception:
            label.update("Активна база для зміни пароля: не визначена")
            return

        for db_id, name, path, password, is_active in databases:
            if path == active_path:
                label.update(
                    f"Активна база для зміни пароля: {name}"
                )
                return

        label.update("Активна база для зміни пароля: не зареєстрована")

    # ------------------------------------------------------------------
    # Mount
    # ------------------------------------------------------------------

    def on_mount(self) -> None:

        table = self.query_one(
            "#db_table",
            DataTable,
        )

        table.add_columns(
            "Назва",
            "Шлях",
            "Статус",
        )

        self.load_databases()

    # ------------------------------------------------------------------
    # Завантаження БД
    # ------------------------------------------------------------------

    def load_databases(self) -> None:

        table = self.query_one(
            "#db_table",
            DataTable,
        )

        table.clear()

        if not getattr(config, "master_password", None):
            return

        try:
            databases = get_databases_list(
                config.master_password
            )
        except Exception as e:
            self.app.notify(
                f"Помилка читання списку БД: {e}",
                severity="error",
            )
            return

        for row in databases:

            db_id, name, path, password, is_active = row

            if not os.path.exists(path):
                status = "[red]Недоступна[/red]"
            
            elif getattr(config, "db_path", None) == path:
                status = "Активна"

            elif is_active:
                status = "Підключена"

            else:
                status = "Вимкнена"

            table.add_row(
                name,
                path,
                status,
                key=str(db_id),
            )

        self.update_active_database_label()

    # ------------------------------------------------------------------
    # Отримання вибраного рядка
    # ------------------------------------------------------------------

    def get_selected_database(self):

        table = self.query_one(
            "#db_table",
            DataTable,
        )

        if table.row_count == 0:
            self.app.notify(
                "Список баз даних порожній.",
                severity="warning",
            )
            return None

        if table.cursor_row is None:
            self.app.notify(
                "Оберіть базу даних.",
                severity="warning",
            )
            return None

        cell_key = table.coordinate_to_cell_key(
            table.cursor_coordinate
        )

        db_id = int(cell_key.row_key.value)

        for row in get_databases_list(
            config.master_password
        ):
            if row[0] == db_id:
                return row

        self.app.notify(
            "Базу даних не знайдено.",
            severity="error",
        )

        return None

    # ------------------------------------------------------------------
    # Кнопки
    # ------------------------------------------------------------------

    def on_button_pressed(
        self,
        event: Button.Pressed,
    ) -> None:

        button_id = event.button.id

        if button_id == "btn_refresh_db":
            self.load_databases()
            return

        if button_id == "btn_create_db":
            self.app.push_screen(
                CreateDatabaseScreen(),
                self.on_database_created,
            )
            return

        if button_id == "btn_add_db":
            self.app.push_screen(
                AddDatabaseScreen(),
                self.on_database_added,
            )
            return

        if button_id == "btn_activate_db":
            self.activate_selected_database()
            return

        if button_id == "btn_delete_db":
            self.delete_selected_database()
            return

        if button_id == "btn_change_pass":
            self.change_password()
            return

    # ------------------------------------------------------------------
    # Створення БД
    # ------------------------------------------------------------------

    def on_database_created(
        self,
        result: tuple[str, str] | None,
    ) -> None:

        if result is None:
            return

        db_path, password = result

        try:

            create_new_database(
                db_path,
                password,
            )

            db_name = os.path.basename(db_path)

            add_database_to_settings(
                config.master_password,
                db_name,
                db_path,
                password,
            )

            # Робимо нову БД поточною
            config.db_path = db_path
            config.password = password

            self.load_databases()

            self.app.notify(
                f"Базу створено: {db_name}",
                severity="information",
            )

        except Exception as e:

            self.app.notify(
                f"Помилка створення БД: {e}",
                severity="error",
            )

    # ------------------------------------------------------------------
    # Підключення БД
    # ------------------------------------------------------------------

    def on_database_added(
        self,
        result: tuple[str, str] | None,
    ) -> None:

        if result is None:
            return

        db_path, password = result

        try:

            db_name = os.path.basename(db_path)

            add_database_to_settings(
                config.master_password,
                db_name,
                db_path,
                password,
            )

            # Робимо підключену БД поточною
            config.db_path = db_path
            config.password = password

            self.load_databases()

            self.app.notify(
                f"Базу підключено: {db_name}",
                severity="information",
            )

        except Exception as e:

            self.app.notify(
                f"Помилка підключення БД: {e}",
                severity="error",
            )

    # ------------------------------------------------------------------
    # Зробити вибрану БД активною
    # ------------------------------------------------------------------

    def activate_selected_database(self) -> None:

        row = self.get_selected_database()

        if row is None:
            return

        db_id, name, path, password, is_active = row

        if not os.path.exists(path):
            self.app.notify(
                "Файл бази даних недоступний.",
                severity="error",
            )
            return

        success, message = verify_database_password(
            path,
            password,
        )

        if not success:

            self.app.notify(
                f"Помилка відкриття БД: {message}",
                severity="error",
            )

            return

        config.db_path = path
        config.password = password

        self.load_databases()

        self.app.notify(
            f"Активна база: {name}",
            severity="information",
        )

    # ------------------------------------------------------------------
    # Видалення з реєстру
    # ------------------------------------------------------------------

    def delete_selected_database(self) -> None:

        table = self.query_one(
            "#db_table",
            DataTable,
        )

        # ВАЖНО:
        # cursor_coordinate може бути (0, 0), навіть коли таблиця порожня.
        if table.row_count == 0:
            self.app.notify(
                "Немає баз даних для видалення.",
                severity="warning",
            )
            return

        if table.cursor_row is None:
            self.app.notify(
                "Оберіть базу даних.",
                severity="warning",
            )
            return

        cell_key = table.coordinate_to_cell_key(
            table.cursor_coordinate
        )

        db_id = int(cell_key.row_key.value)

        try:

            remove_database_from_settings(
                config.master_password,
                db_id,
            )

            self.load_databases()

            self.app.notify(
                "Базу видалено зі списку.",
                severity="information",
            )

        except Exception as e:

            self.app.notify(
                f"Помилка видалення: {e}",
                severity="error",
            )

    # ------------------------------------------------------------------
    # Паролі
    # ------------------------------------------------------------------

    def change_password(self) -> None:

        old_p = self.query_one(
            "#old_pass",
            Input,
        ).value

        p1 = self.query_one(
            "#new_pass1",
            Input,
        ).value

        p2 = self.query_one(
            "#new_pass2",
            Input,
        ).value

        is_master = self.query_one(
            "#target_master",
            RadioButton,
        ).value

        log = self.query_one(
            "#settings_log",
            RichLog,
        )

        if not old_p or not p1 or p1 != p2:

            log.write(
                "Помилка введення паролів!"
            )

            return

        if not is_master:
            self.change_active_database_password(old_p, p1)
            return

        success, message = change_master_password(
            old_p,
            p1,
        )

        if not success:
            log.write(f"Помилка: {message}")
            self.app.notify(message, severity="error")
            return

        # Оновлюємо пароль у конфігурації лише після успіху.
        config.master_password = p1

        self.query_one("#old_pass", Input).value = ""
        self.query_one("#new_pass1", Input).value = ""
        self.query_one("#new_pass2", Input).value = ""

        log.write(message)
        self.app.notify(message, severity="information")


    def change_active_database_password(
        self,
        old_password: str,
        new_password: str,
    ) -> None:
        db_path = getattr(config, "db_path", None)

        if not db_path:
            self.app.notify(
                "Спочатку зробіть потрібну базу активною.",
                severity="error",
            )
            return

        if not os.path.exists(db_path):
            self.app.notify(
                "Файл активної бази не знайдено.",
                severity="error",
            )
            return

        try:
            databases = get_databases_list(config.master_password)
        except Exception as e:
            self.app.notify(
                f"Помилка читання реєстру БД: {e}",
                severity="error",
            )
            return

        target = next(
            (row for row in databases if row[2] == db_path),
            None,
        )

        if target is None:
            self.app.notify(
                "Активна база відсутня в реєстрі.",
                severity="error",
            )
            return

        db_id, name, path, stored_password, is_active = target

        conn = None

        try:
            conn = sqlite3.connect(path)
            cursor = conn.cursor()

            # Проверяем старый пароль.
            cursor.execute(
                f"PRAGMA key = '{old_password.replace(chr(39), chr(39) * 2)}';"
            )
            cursor.execute("PRAGMA cipher_compatibility = 3;")
            cursor.execute("SELECT name FROM sqlite_master LIMIT 1;")
            cursor.fetchone()

            # Меняем пароль самого файла базы.
            safe_new_password = new_password.replace("'", "''")
            cursor.execute(f"PRAGMA rekey = '{safe_new_password}';")

            conn.close()
            conn = None

            # Проверяем, что новый пароль действительно работает.
            success, message = verify_database_password(
                path,
                new_password,
            )

            if not success:
                self.app.notify(
                    "Новий пароль не пройшов перевірку. "
                    f"Реєстр не оновлено: {message}",
                    severity="error",
                )
                return

            # Обновляем пароль в реестре только после проверки файла.
            update_database_password(
                config.master_password,
                db_id,
                new_password,
            )

            config.password = new_password

            self.query_one("#old_pass", Input).value = ""
            self.query_one("#new_pass1", Input).value = ""
            self.query_one("#new_pass2", Input).value = ""

            self.query_one("#settings_log", RichLog).write(
                f"Пароль активної бази «{name}» успішно змінено."
            )

            self.app.notify(
                f"Пароль бази «{name}» змінено.",
                severity="information",
            )

        except Exception as e:
            self.app.notify(
                f"Помилка зміни пароля: {e}",
                severity="error",
            )

        finally:
            if conn is not None:
                conn.close()



