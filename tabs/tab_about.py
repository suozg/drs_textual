# tabs/tab_about.py
from textual.app import ComposeResult
from textual.widgets import Static, Button, RichLog
from textual.containers import Vertical, Horizontal, Container
from textual import events, message

FLOOR, WALL, PLAYER, BOX, TARGET, BOXTARGET = 0, 1, 2, 3, 4, 5

LEVELS = [
    ["..111...", "..141...", "..1 1111", "1113 341", "14 32111", "111131..", "...141..", "...111.."],
    ["11111111", "1 4   21", "1   43 1", "111 3111", "..1  1..", "..1  1..", "..1111..", "........"],
    ["....1111", "..111  1", "111    1", "14  3121", "1443 3 1", "1114 3 1", "..111  1", "....1111"],
    ["..1111..", "111..1..", "123.41..", "1111.11.", "..14.31.", "..1.1.1.", "..143.1.", "..11111."],
]

class SokobanWidget(Static, can_focus=True):
    """Кастомний віджет гри Сокобан з підтримкою HJKL, WASD та Стрілок."""

    class LevelChanged(message.Message):
        """Повідомлення про зміну рівня"""
        pass

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.level_idx = 0
        self.map2 = []
        self.game_map = []
        self.px, self.py = 0, 0
        self.max_x, self.max_y = 0, 0

    def on_mount(self) -> None:
        self.load_level()

    def load_level(self):
        self.level_idx %= len(LEVELS)
        raw_map = LEVELS[self.level_idx]
        self.max_y = len(raw_map)
        self.max_x = len(raw_map[0])
        self.map2 = [[0] * self.max_x for _ in range(self.max_y)]
        self.game_map = [[0] * self.max_x for _ in range(self.max_y)]

        for y in range(self.max_y):
            for x in range(self.max_x):
                char = raw_map[y][x]
                val = FLOOR if char in ". " else int(char)
                self.map2[y][x] = val
                if val == PLAYER:
                    self.px, self.py = x, y
        self.reset_level()

    def reset_level(self):
        for y in range(self.max_y):
            for x in range(self.max_x):
                d = self.map2[y][x]
                if d in (TARGET, PLAYER):
                    d = FLOOR
                self.game_map[y][x] = d
        self.game_map[self.py][self.px] = PLAYER
        self.render_board()

    def render_board(self):
        lines = []
        for y in range(self.max_y):
            line = ""
            for x in range(self.max_x):
                c = self.game_map[y][x]
                if self.map2[y][x] == TARGET:
                    if c == FLOOR:
                        line += "[yellow]· [/yellow]"
                        continue
                    elif c == BOX:
                        c = BOXTARGET

                if c == FLOOR:
                    line += "  "
                elif c == WALL:
                    line += "[white on grey37]██[/white on grey37]"
                elif c == PLAYER:
                    line += "[bold bright_white on blue] P[/bold bright_white on blue]"
                elif c == BOX:
                    line += "[bold white on yellow] B[/bold white on yellow]"
                elif c == BOXTARGET:
                    line += "[bold white on green] X[/bold white on green]"
            lines.append(line)
        self.update("\n".join(lines))

    def on_key(self, event: events.Key) -> None:
        dx, dy = 0, 0
        key = event.key.lower()
        character = (event.character or "").lower()

        # Керування: Стрілки, HJKL (Vim), WASD та кириличні розкладки
        if key == "up" or key == "k" or key == "w" or character in ("k", "w", "л", "ц"):
            dy = -1
        elif key == "down" or key == "j" or key == "s" or character in ("j", "s", "о", "і"):
            dy = 1
        elif key == "left" or key == "h" or key == "a" or character in ("h", "a", "р", "ф"):
            dx = -1
        elif key == "right" or key == "l" or key == "d" or character in ("l", "d", "д", "в"):
            dx = 1
        elif key == "space" or key == "r" or character == "r":
            self.reset_level()
            return
        else:
            return

        px1, py1 = self.px + dx, self.py + dy
        if not (0 <= px1 < self.max_x and 0 <= py1 < self.max_y):
            return

        if self.game_map[py1][px1] == BOX:
            px2, py2 = px1 + dx, py1 + dy
            if 0 <= px2 < self.max_x and 0 <= py2 < self.max_y:
                if self.game_map[py2][px2] == FLOOR:
                    self.game_map[py2][px2] = BOX
                    self.game_map[py1][px1] = FLOOR

        if self.game_map[py1][px1] == FLOOR:
            self.game_map[self.py][self.px] = FLOOR
            self.px, self.py = px1, py1
            self.game_map[self.py][self.px] = PLAYER

        self.render_board()
        if all(self.map2[y][x] != TARGET or self.game_map[y][x] == BOX 
               for y in range(self.max_y) for x in range(self.max_x)):
            self.app.notify("Рівень пройдено!", title="Перемога!")
            self.level_idx += 1
            self.load_level()
            self.post_message(self.LevelChanged())


class AboutTab(Container):

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield RichLog(id="about_help_text", highlight=True, markup=True)
            with Vertical(id="sokoban_container"):
                yield Static("Сокобан (Керування: HJKL / WASD / Стрілки | R - скидання)", id="sokoban_label")
                yield SokobanWidget(id="sokoban_game")
                with Horizontal(id="level_controls"):
                    yield Button("◄", id="btn_prev_level")
                    yield Static(f"1/{len(LEVELS)}", id="lbl_level")
                    yield Button("►", id="btn_next_level")

    def on_mount(self) -> None:
        log = self.query_one("#about_help_text", RichLog)
        help_text = (
            "[bold cyan]Інструкція з пошуку:[/bold cyan]\n\n"
            "[bold]1. Пошук одного слова[/bold]\n\tsлово\n\n"
            "[bold]2. Пошук кількох слів (AND)[/bold]\n\tsлово1 слово2\n\n"
            "[bold]3. Пошук з OR[/bold]\n\tsлово1 OR слово2\n\n"
            "[bold]4. Пошук фрази[/bold]\n\t'точна фраза'\n\n"
            "[bold]5. Виключення слів[/bold]\n\tsлово1 -слово2\n\n"
            "[bold]6. Пошук за близькістю (NEAR)[/bold]\n\tsлово1 NEAR/5 слово2\n\n"
            "[bold]7. Пошук за префіксом[/bold]\n\tsло*"
        )
        log.write(help_text)
        self.query_one(SokobanWidget).focus()

    def update_level_label(self) -> None:
        game = self.query_one(SokobanWidget)
        self.query_one("#lbl_level", Static).update(f"{game.level_idx + 1}/{len(LEVELS)}")

    def on_sokoban_widget_level_changed(self, message: SokobanWidget.LevelChanged) -> None:
        self.update_level_label()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        game = self.query_one(SokobanWidget)
        if event.button.id == "btn_prev_level":
            game.level_idx = (game.level_idx - 1) % len(LEVELS)
            game.load_level()
        elif event.button.id == "btn_next_level":
            game.level_idx = (game.level_idx + 1) % len(LEVELS)
            game.load_level()
        self.update_level_label()
        game.focus()
