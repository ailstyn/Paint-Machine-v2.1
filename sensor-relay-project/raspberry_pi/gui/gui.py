from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QGridLayout, QVBoxLayout, QSizePolicy, QDialog, QPushButton, QHBoxLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPixmap
import sys
import logging
import os

logging.basicConfig(level=logging.INFO)

COLOR_SCHEMES = [
    {"name": "Classic Blue", "bg": "#2e3192", "fg": "#FFFFFF", "splash": "#CB1212", "highlight": "#FFFFFF"},
    {"name": "Dark Mode", "bg": "#333333", "fg": "#FFFFFF", "splash": "#F6EB61", "highlight": "#FFFFFF"},
    {"name": "Light Mode", "bg": "#F5FFFA", "fg": "#000000", "splash": "#800020", "highlight": "#FFFFFF"},
    {"name": "Green Alert", "bg": "#1B7B31", "fg": "#FFFFFF", "splash": "#B84E44", "highlight": "#FFFFFF"},
]

class StationWidget(QWidget):
    def __init__(self, station_number, color_scheme, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.station_number = station_number
        self.color_scheme = color_scheme
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Station number label
        self.number_label = QLabel(str(station_number))
        self.number_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.number_label.setFont(QFont("Arial", 48, QFont.Weight.Bold))
        layout.addWidget(self.number_label)

        # Weight display label (current / target)
        self.weight_label = QLabel("0.0 / 0.0 g")
        self.weight_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.weight_label.setFont(QFont("Arial", 36, QFont.Weight.Normal))
        layout.addWidget(self.weight_label)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.update_colors(self.color_scheme)

    def set_weight(self, current_weight, target_weight, unit="g"):
        new_text = f"{current_weight:.1f} / {target_weight:.1f} {unit}"
        if self.weight_label.text() != new_text:
            self.weight_label.setText(new_text)

    def update_colors(self, color_scheme):
        self.color_scheme = color_scheme
        fg = color_scheme["fg"]
        self.setStyleSheet(f"border: 1px solid {fg}; background: transparent;")
        self.number_label.setStyleSheet(f"color: {fg}; background: transparent;")
        self.weight_label.setStyleSheet(f"color: {fg}; background: transparent;")


class MenuDialog(QDialog):
    def __init__(self, color_scheme, parent=None):
        super().__init__(parent)
        self.selected_index = 0
        self.color_scheme = color_scheme
        self.setWindowTitle("Menu")
        self.setModal(True)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: #222;
                color: {color_scheme['fg']};
                border: 6px solid {color_scheme['fg']};
                border-radius: 24px;
            }}
        """)

        # Icon files: (filename, alt text)
        icon_files = [
            ("dumbell.png", "Dumbbell"),
            ("stopwatch.png", "Stopwatch"),
            ("color.png", "Color"),
            ("language.png", "Language"),
            ("ruler.png", "Ruler"),
            ("geometric-tool.png", "Calibrate"),
        ]

        layout = QHBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(32)

        self.icon_labels = []
        for filename, alt in icon_files:
            icon_label = QLabel()
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_path = os.path.join(os.path.dirname(__file__), filename)
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(96, 96, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                icon_label.setPixmap(pixmap)
            icon_label.setFixedSize(112, 112)
            icon_label.setStyleSheet(f"""
                border: 6px solid transparent;
                border-radius: 24px;
                background: transparent;
                color: {color_scheme['fg']};
            """)
            self.icon_labels.append(icon_label)
            layout.addWidget(icon_label)
        self.update_selection_box()

        self.setFixedSize((112 + 32) * len(icon_files) + 32, 176)  # Width: icon+spacing, Height: icon+padding

    def update_selection_box(self):
        for i, label in enumerate(self.icon_labels):
            if i == self.selected_index:
                label.setStyleSheet(f"""
                    border: 6px solid {self.color_scheme['splash']};
                    border-radius: 24px;
                    background: transparent;
                    color: {self.color_scheme['fg']};
                """)
            else:
                label.setStyleSheet(f"""
                    border: 6px solid transparent;
                    border-radius: 24px;
                    background: transparent;
                    color: {self.color_scheme['fg']};
                """)

    def select_next(self):
        self.selected_index = (self.selected_index + 1) % len(self.icon_labels)
        self.update_selection_box()

    def select_prev(self):
        self.selected_index = (self.selected_index - 1) % len(self.icon_labels)
        self.update_selection_box()

    def activate_selected(self):
        # ... your activation logic ...
        self.accept()

    def update_colors(self, color_scheme):
        self.color_scheme = color_scheme
        self.setStyleSheet(f"""
            QDialog {{
                background-color: #222;
                color: {color_scheme['fg']};
                border: 6px solid {color_scheme['fg']};
                border-radius: 24px;
            }}
        """)
        self.update_selection_box()


class RelayControlApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Four Station Control")
        self.color_scheme_index = 0
        self.color_scheme = COLOR_SCHEMES[self.color_scheme_index]
        self.setStyleSheet(f"background-color: {self.color_scheme['bg']};")

        # Main grid layout (2x2 for four stations)
        grid = QGridLayout()
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setSpacing(8)

        # Create station widgets (1-4) with identifying numbers
        self.station_widgets = []
        for i in range(4):
            station = StationWidget(i + 1, self.color_scheme)
            self.station_widgets.append(station)
            grid.addWidget(station, i // 2, i % 2)

        self.setLayout(grid)
        self.showMaximized()

        self.target_weight = 0
        self.time_limit = 0
        self.language = "en"

    def show_menu(self):
        menu = MenuDialog(self.color_scheme, self)
        menu.exec()

    def set_target_weight(self, value):
        self.target_weight = value

    def set_time_limit(self, value):
        self.time_limit = value

    def set_language(self, lang_code):
        self.language = lang_code

    def set_color_scheme(self, index):
        self.color_scheme_index = index
        self.color_scheme = COLOR_SCHEMES[self.color_scheme_index]
        self.setStyleSheet(f"background-color: {self.color_scheme['bg']};")
        # Update all station widgets
        for station in self.station_widgets:
            station.update_colors(self.color_scheme)
        # Optionally update other dialogs/menus if open

    def show_info_dialog(self, title, message):
        dialog = InfoDialog(title, message, self)
        dialog.exec()

class InfoDialog(QDialog):
    def __init__(self, title, message, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        layout = QVBoxLayout(self)
        self.label = QLabel(message)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        layout.addWidget(self.ok_button)
        self.setModal(True)

if __name__ == "__main__":
    class TestableRelayControlApp(RelayControlApp):
        def keyPressEvent(self, event):
            # Open menu with 'm' key for testing
            if event.key() == Qt.Key.Key_M:
                self.show_menu()
            else:
                super().keyPressEvent(event)

    class TestableMenuDialog(MenuDialog):
        def __init__(self, parent=None):
            super().__init__(parent.color_scheme, parent)
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self.setFocus()

        def keyPressEvent(self, event):
            if event.key() == Qt.Key.Key_Right:
                self.select_next()
            elif event.key() == Qt.Key.Key_Left:
                self.select_prev()
            elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                # Simulate selection (for now just close the dialog)
                self.accept()
            else:
                super().keyPressEvent(event)

    app = QApplication(sys.argv)
    # Use the testable versions for desktop testing
    window = TestableRelayControlApp()
    # Patch show_menu to use the testable dialog
    def show_test_menu(self):
        menu = TestableMenuDialog(self)
        menu.exec()
    window.show_menu = show_test_menu.__get__(window)
    window.show()
    print("Press 'm' to open the menu, left/right arrows to move selection, enter to select.")
    sys.exit(app.exec())