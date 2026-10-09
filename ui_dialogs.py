from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Input, Button, Static, Label
from textual.containers import Grid, Vertical

class ConfirmPasswordModal(ModalScreen[str]):
    """Модальне вікно встановлення/підтвердження пароля"""

    def __init__(self, title: str = "Встановлення пароля", **kwargs):
        super().__init__(**kwargs)
        self.dialog_title = title

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog_container"):
            yield Label(f"[bold]{self.dialog_title}[/bold]")
            yield Static("Введіть пароль:")
            yield Input(password=True, id="pass1")
            yield Static("Повторіть пароль:")
            yield Input(password=True, id="pass2")
            yield Label("", id="err_msg", classes="error_label")
            with Grid(id="button_grid"):
                yield Button("ОК", id="btn_ok", variant="primary")
                yield Button("Скасувати", id="btn_cancel", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_cancel":
            self.dismiss(None)
            return

        p1 = self.query_one("#pass1", Input).value
        p2 = self.query_one("#pass2", Input).value
        err_lbl = self.query_one("#err_msg", Label)

        if not p1:
            err_lbl.update("[red]Пароль не може бути порожнім![/red]")
            return

        if p1 != p2:
            err_lbl.update("[red]Паролі не збігаються![/red]")
            self.query_one("#pass1", Input).value = ""
            self.query_one("#pass2", Input).value = ""
            self.query_one("#pass1", Input).focus()
            return

        self.dismiss(p1)


class PasswordModal(ModalScreen[str]):
    """Модальне вікно швидкого запиту одного пароля"""

    def __init__(self, message: str = "Введіть пароль:", title: str = "Пароль", **kwargs):
        super().__init__(**kwargs)
        self.message = message
        self.dialog_title = title

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog_container"):
            yield Label(f"[bold]{self.dialog_title}[/bold]")
            yield Static(self.message)
            yield Input(password=True, id="pwd_input")
            with Grid(id="button_grid"):
                yield Button("ОК", id="btn_ok", variant="primary")
                yield Button("Скасувати", id="btn_cancel", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_cancel":
            self.dismiss(None)
        else:
            self.dismiss(self.query_one("#pwd_input", Input).value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)