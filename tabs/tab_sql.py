# tab_sql.py
import csv
from datetime import datetime

from textual.app import ComposeResult
from textual.widgets import Static, Button, TextArea, DataTable, Select
from textual.containers import Container, Horizontal, Vertical

import config
from database import connect_to_specific_database
from settings_db import get_databases_list

class SqlTab(Container):
    def on_show(self) -> None:
        self.call_after_refresh(
            lambda: self.query_one("#sql_input", TextArea).focus()
        )

    def compose(self) -> ComposeResult:
        with Vertical(id="sql_main"):

            with Horizontal(id="sql_db_row"):
                yield Static("Цільова база даних:", classes="label")
                yield Select(
                    [],
                    prompt="Оберіть базу даних",
                    id="sql_db_select"
                )
                yield Static("", id="sql_db_selected")

            yield Static("SQL запит:", id="sql_label")

            yield TextArea(
                id="sql_input",
                language="sql"
            )

            with Horizontal(id="sql_buttons"):
                yield Button(
                    "Виконати",
                    id="btn_exec_sql",
                    variant="primary"
                )
                yield Button(
                    "EXPLAIN",
                    id="btn_explain"
                )
                yield Button(
                    "Експорт CSV",
                    id="btn_export_csv"
                )
                yield Button(
                    "Очистити",
                    id="btn_clear_sql"
                )

            yield DataTable(id="sql_grid")

    def on_mount(self) -> None:
        self.call_after_refresh(self.load_databases)

    # --------------------------------------------------------------
    # Завантаження всіх зареєстрованих БД
    # --------------------------------------------------------------

    def load_databases(self) -> None:
        select = self.query_one("#sql_db_select", Select)

        try:
            databases = get_databases_list(config.master_password)
        except Exception as e:
            self.app.notify(
                f"Помилка завантаження баз даних: {e}",
                severity="error"
            )
            return

        choices = []

        for db_id, db_name, db_path, db_password, is_active in databases:
            label = f"{db_name}"
            value = (db_path, db_password)
            choices.append((label, value))

        select.set_options(choices)

        if choices:
            select.value = choices[0][1]
            self.update_selected_database(choices[0][1])
        else:
            self.query_one("#sql_db_selected", Static).update(
                "Немає зареєстрованих баз даних"
            )

    # --------------------------------------------------------------
    # Вибір БД
    # --------------------------------------------------------------

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "sql_db_select":
            return

        if event.value is Select.BLANK or event.value is Select.NULL:
            self.query_one("#sql_db_selected", Static).update(
                "База не обрана"
            )
            return

        self.update_selected_database(event.value)

    def update_selected_database(self, db_data) -> None:
        db_path, _ = db_data

        self.query_one("#sql_db_selected", Static).update(
            f"Обрана: {db_path}"
        )

    def get_selected_database(self):
        db_data = self.query_one("#sql_db_select", Select).value

        if db_data is Select.BLANK or db_data is Select.NULL:
            self.app.notify(
                "Оберіть базу даних!",
                severity="error"
            )
            return None

        return db_data

    # --------------------------------------------------------------
    # Кнопки
    # --------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:

        if event.button.id == "btn_clear_sql":
            self.query_one("#sql_input", TextArea).text = ""
            return

        if event.button.id == "btn_export_csv":
            self.export_csv()
            return

        sql = self.query_one("#sql_input", TextArea).text.strip()

        if not sql:
            self.app.notify(
                "Введіть SQL-запит.",
                severity="warning"
            )
            return

        if event.button.id == "btn_exec_sql":
            self.run_sql(sql)

        elif event.button.id == "btn_explain":
            self.run_sql(f"EXPLAIN QUERY PLAN {sql}")

    # --------------------------------------------------------------
    # Виконання SQL
    # --------------------------------------------------------------

    def run_sql(self, sql: str) -> None:
        grid = self.query_one("#sql_grid", DataTable)
        grid.clear(columns=True)

        db_data = self.get_selected_database()

        if db_data is None:
            return

        db_path, db_password = db_data

        conn = connect_to_specific_database(
            db_path,
            db_password
        )

        if not conn:
            self.app.notify(
                "Помилка підключення до бази!",
                severity="error"
            )
            return

        try:
            cursor = conn.cursor()
            cursor.execute(sql)

            if cursor.description:
                rows = cursor.fetchall()
                cols = [column[0] for column in cursor.description]

                grid.add_columns(*cols)

                for row in rows:
                    grid.add_row(
                        *[
                            str(value) if value is not None else ""
                            for value in row
                        ]
                    )
            else:
                conn.commit()

                self.app.notify(
                    f"Успішно виконано. Змінено рядків: {cursor.rowcount}",
                    severity="information"
                )

        except Exception as e:
            self.app.notify(
                f"SQL Помилка: {e}",
                severity="error"
            )

        finally:
            conn.close()

    # --------------------------------------------------------------
    # Експорт CSV
    # --------------------------------------------------------------

    def export_csv(self) -> None:
        grid = self.query_one("#sql_grid", DataTable)

        if not grid.columns or not grid.rows:
            self.app.notify(
                "Немає даних для експорту!",
                severity="warning"
            )
            return

        headers = [
            str(column.label)
            for column in grid.columns.values()
        ]

        rows = [
            grid.get_row(row_key)
            for row_key in grid.rows
        ]

        # filename = "sql_export.csv"
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"sql_export_{timestamp}.csv"

        try:
            with open(
                filename,
                "w",
                newline="",
                encoding="utf-8-sig"
            ) as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(rows)

            self.app.notify(
                f"Експортовано: {filename}",
                severity="information"
            )

        except Exception as e:
            self.app.notify(
                f"Помилка експорту CSV: {e}",
                severity="error"
            )
