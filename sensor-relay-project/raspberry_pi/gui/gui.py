from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QGridLayout, QVBoxLayout, QSizePolicy, QDialog, QPushButton, QHBoxLayout, QStyle
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QPainterPath, QPixmap, QCursor  # <-- Add QPixmap here
import sys
import logging
import os
from gui.languages import LANGUAGES

logging.basicConfig(level=logging.INFO)

class OutlinedLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def paintEvent(self, event):
        painter = QPainter(self)
        font = self.font()
        painter.setFont(font)
        text = self.text()
        rect = self.rect()

        # Center the text
        metrics = painter.fontMetrics()
        text_width = metrics.horizontalAdvance(text)
        text_height = metrics.height()
        x = rect.x() + (rect.width() - text_width) / 2
        y = rect.y() + (rect.height() + text_height) / 2 - metrics.descent()

        # Create path for the text
        path = QPainterPath()
        path.addText(x, y, font, text)

        # Draw black outline (stroke)
        outline_width = 6  # Adjust for desired thickness
        painter.setPen(QPen(QColor("black"), outline_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        # Draw white fill
        painter.setPen(QPen(QColor("white"), 1))
        painter.setBrush(QColor("white"))
        painter.drawPath(path)

class StationWidget(QWidget):
    def __init__(self, station_number, bg_color, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.station_number = station_number

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Decide bar position: left for 0/1, right for 2/3
        bar_on_left = station_number in (1, 2)
        self.progress_bar = VerticalProgressBar(max_value=100, value=0, bar_color="#F6EB61")
        self.progress_bar.setFixedWidth(24)

        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.weight_label = OutlinedLabel("0.0 / 0.0 g")
        self.weight_label.setFont(QFont("Arial", 36, QFont.Weight.Bold))
        content_layout.addWidget(self.weight_label)

        if bar_on_left:
            main_layout.addWidget(self.progress_bar)
            main_layout.addLayout(content_layout)
        else:
            main_layout.addLayout(content_layout)
            main_layout.addWidget(self.progress_bar)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(f"background-color: {bg_color}; border: 2px solid #222;")

    def set_weight(self, current_weight, target_weight, unit="g"):
        if unit == "g":
            new_text = f"{int(round(current_weight))} / {int(round(target_weight))} g"
        else:  # "oz"
            new_text = f"{current_weight:.1f} / {target_weight:.1f} oz"
        if self.weight_label.text() != new_text:
            self.weight_label.setText(new_text)
        self.progress_bar.set_max(target_weight)
        self.progress_bar.set_value(current_weight)

    def set_active(self, active, bg_color=None, bg_color_deactivated=None):
        if active:
            color = bg_color if bg_color else "#FFFFFF"
        else:
            color = bg_color_deactivated if bg_color_deactivated else "#444444"
        self.setStyleSheet(f"background-color: {color}; border: 2px solid #222;")

    def set_offline(self, bg_color_deactivated="#444444"):
        self.weight_label.setText("OFFLINE")
        self.progress_bar.set_value(0)
        self.progress_bar.set_max(1)
        self.setStyleSheet(f"background-color: {bg_color_deactivated}; border: 2px solid #222;")

class MenuDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        print("MenuDialog: __init__ called")
        self.selected_index = 0
        self.menu_keys = [
            "SET TARGET WEIGHT",
            "SET TIME LIMIT",
            "SET LANGUAGE",
            "CHANGE UNITS",
            "EXIT"
        ]
        self.menu_items = [self.parent().tr(key) for key in self.menu_keys]
        layout = QVBoxLayout(self)
        self.labels = []
        for item in self.menu_items:
            label = OutlinedLabel(item)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setFixedSize(320, 64)
            self.labels.append(label)
            layout.addWidget(label)
        self.setLayout(layout)
        self.update_selection_box()

        # Make the dialog borderless and add a white border around the widget
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setStyleSheet("""
            QDialog {
                background-color: #222;
                border: 6px solid white;
                border-radius: 24px;
            }
        """)

    def update_selection_box(self):
        for i, label in enumerate(self.labels):
            if i == self.selected_index:
                label.setStyleSheet(
                    "font-size: 24px; border: 4px solid #F6EB61; border-radius: 16px; background: transparent;"
                )
            else:
                label.setStyleSheet(
                    "font-size: 24px; border: 4px solid transparent; border-radius: 16px; background: transparent;"
                )

    def select_next(self):
        self.selected_index = (self.selected_index + 1) % len(self.labels)
        self.update_selection_box()

    def select_prev(self):
        self.selected_index = (self.selected_index - 1) % len(self.labels)
        self.update_selection_box()

    def activate_selected(self):
        selected_key = self.menu_keys[self.selected_index]
        selected_label = self.menu_items[self.selected_index]
        print(f"Menu item selected: {selected_key} ({selected_label})")
        parent = self.parent()
        if selected_key == "EXIT":
            self.accept()
        elif selected_key == "SET TARGET WEIGHT":
            self.hide()
            parent.target_weight_dialog = SetTargetWeightDialog(parent)
            parent.target_weight_dialog.finished.connect(self.show_again)
            parent.target_weight_dialog.show()
        elif selected_key == "SET TIME LIMIT":
            self.hide()
            parent.time_limit_dialog = SetTimeLimitDialog(parent)
            parent.time_limit_dialog.finished.connect(self.show_again)
            parent.time_limit_dialog.show()
        elif selected_key == "SET LANGUAGE":
            self.hide()
            parent.language_dialog = SetLanguageDialog(parent)
            parent.language_dialog.finished.connect(self.show_again)
            parent.language_dialog.show()
        elif selected_key == "CHANGE UNITS":
            self.hide()
            parent.change_units_dialog = ChangeUnitsDialog(parent)
            parent.change_units_dialog.finished.connect(self.show_again)
            parent.change_units_dialog.show()

    def show_again(self):
        self.show()
        # Optionally clear dialog references in parent
        parent = self.parent()
        if hasattr(parent, "target_weight_dialog"):
            parent.target_weight_dialog = None
        if hasattr(parent, "time_limit_dialog"):
            parent.time_limit_dialog = None
        if hasattr(parent, "language_dialog"):
            parent.language_dialog = None
        if hasattr(parent, "change_units_dialog"):
            parent.change_units_dialog = None

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


    def show(self):
        print("MenuDialog: show() called")
        super().show()

class RelayControlApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Four Station Control")
        self.setStyleSheet("background-color: #222222;")

        # Define station colors
        self.bg_colors = ["#CB1212", "#2E4BA8", "#3f922e", "#EDE021"]  # Active: Red, Blue, Green, Yellow
        self.bg_colors_deactivated = ["#6c2222", "#22305a", "#2b4d2b", "#b1a93a"]  # Deactivated: darker shades

        # Main grid layout (2x2 for four stations)
        grid = QGridLayout()
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setSpacing(8)

        # Explicitly assign widgets to grid positions with color
        self.station_widgets = [None] * 4
        self.station_widgets[0] = StationWidget(1, self.bg_colors[0])  # Station 1
        self.station_widgets[1] = StationWidget(2, self.bg_colors[1])  # Station 2
        self.station_widgets[2] = StationWidget(3, self.bg_colors[2])  # Station 3
        self.station_widgets[3] = StationWidget(4, self.bg_colors[3])  # Station 4

        grid.addWidget(self.station_widgets[0], 0, 0)  # Top left
        grid.addWidget(self.station_widgets[1], 1, 0)  # Bottom left
        grid.addWidget(self.station_widgets[2], 0, 1)  # Top right
        grid.addWidget(self.station_widgets[3], 1, 1)  # Bottom right

        self.setLayout(grid)

        # Borderless fullscreen for kiosk mode
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.showFullScreen()

        self.target_weight = 0
        self.time_limit = 0
        self.language = "en"
        self.units = "g"  # "g" for grams, "oz" for ounces (default "g")

        self.menu_dialog = None
        self.language_dialog = None
        self.target_weight_dialog = None
        self.time_limit_dialog = None
        self.change_units_dialog = None

        self.setGeometry(
            QStyle.alignedRect(
                Qt.LayoutDirection.LeftToRight,
                Qt.AlignmentFlag.AlignCenter,
                self.size(),
                QApplication.primaryScreen().availableGeometry()
            )
        )
        self.setCursor(QCursor(Qt.CursorShape.BlankCursor))

    def show_menu(self):
        print("RelayControlApp: show_menu() called")
        if self.menu_dialog is None or not self.menu_dialog.isVisible():
            self.menu_dialog = MenuDialog(self)
            self.menu_dialog.show()

    def set_target_weight(self, value):
        self.target_weight = value
        for i, widget in enumerate(self.station_widgets):
            if widget.weight_label.text() != "OFFLINE":
                current_weight = 0  # Or use actual current weight if available
                widget.set_weight(current_weight, self.target_weight, self.units)

    def set_time_limit(self, value):
        self.time_limit = value

    def set_language(self, lang_code):
        self.language = lang_code

    def show_info_dialog(self, title, message):
        dialog = InfoDialog(title, message, self)
        dialog.exec()

    def update_station_weight(self, station_index, weight):
        self.station_widgets[station_index].set_weight(weight, self.target_weight, self.units)

    def refresh_ui(self):
        QApplication.processEvents()

    def update_station_states(self, station_enabled):
        for i, widget in enumerate(self.station_widgets):
            if station_enabled[i]:
                widget.set_active(True, self.bg_colors[i], self.bg_colors_deactivated[i])
            else:
                widget.set_active(False, self.bg_colors[i], self.bg_colors_deactivated[i])

    def set_units(self, units):
        self.units = units
        # Refresh all station widgets to update display
        for i, widget in enumerate(self.station_widgets):
            # Use actual current weight if available, else 0
            current_weight = 0
            widget.set_weight(current_weight, self.target_weight, self.units)

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

class VerticalProgressBar(QWidget):
    def __init__(self, max_value=100, value=0, bar_color="#F6EB61", parent=None):
        super().__init__(parent)
        self.max_value = max_value
        self.value = value
        self.bar_color = bar_color

    def set_value(self, value):
        self.value = value
        self.update()

    def set_max(self, max_value):
        self.max_value = max_value
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = self.rect()
        # Draw background
        painter.setBrush(QColor("#333"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(rect)
        # Draw bar
        if self.max_value > 0:
            fill_ratio = min(max(self.value / self.max_value, 0), 1)
        else:
            fill_ratio = 0
        bar_height = int(rect.height() * fill_ratio)
        bar_rect = rect.adjusted(4, rect.height() - bar_height + 4, -4, -4)
        painter.setBrush(QColor(self.bar_color))
        painter.drawRect(bar_rect)

class SetTargetWeightDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        tr = parent.tr if parent else (lambda k: LANGUAGES["en"].get(k, k))
        self.setWindowTitle(tr("SET_TARGET_WEIGHT"))
        layout = QVBoxLayout(self)
        label = QLabel(tr("ENTER_NEW_TARGET_WEIGHT"))
        layout.addWidget(label)
        # Add input widgets as needed (QLineEdit, buttons, etc.)
        self.setModal(True)

class SetTimeLimitDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        tr = parent.tr if parent else (lambda k: LANGUAGES["en"].get(k, k))
        self.setWindowTitle(tr("SET_TIME_LIMIT"))
        layout = QVBoxLayout(self)
        label = QLabel(tr("ENTER_NEW_TIME_LIMIT"))
        layout.addWidget(label)
        # Add input widgets as needed
        self.setModal(True)

class SetLanguageDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.parent_app = parent
        tr = parent.tr if parent else (lambda k: LANGUAGES["en"].get(k, k))
        self.languages = [("en", "English"), ("es", "Español")]
        self.selected_index = 0

        self.setWindowTitle(tr("SET_LANGUAGE_TITLE"))
        layout = QVBoxLayout(self)
        label = QLabel(tr("CHOOSE_LANGUAGE"))
        layout.addWidget(label)

        self.labels = []
        for code, name in self.languages:
            lang_label = OutlinedLabel(name)
            lang_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lang_label.setFixedSize(320, 64)
            self.labels.append(lang_label)
            layout.addWidget(lang_label)
        self.setLayout(layout)
        self.update_selection_box()
        self.setModal(True)

    def update_selection_box(self):
        for i, label in enumerate(self.labels):
            if i == self.selected_index:
                label.setStyleSheet(
                    "font-size: 24px; border: 4px solid #F6EB61; border-radius: 16px; background: transparent;"
                )
            else:
                label.setStyleSheet(
                    "font-size: 24px; border: 4px solid transparent; border-radius: 16px; background: transparent;"
                )

    def select_next(self):
        self.selected_index = (self.selected_index + 1) % len(self.labels)
        self.update_selection_box()

    def select_prev(self):
        self.selected_index = (self.selected_index - 1) % len(self.labels)
        self.update_selection_box()

    def activate_selected(self):
        lang_code = self.languages[self.selected_index][0]
        if self.parent_app:
            self.parent_app.set_language(lang_code)
        self.accept()

class ChangeUnitsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        tr = parent.tr if parent else (lambda k: LANGUAGES["en"].get(k, k))
        self.setWindowTitle(tr("CHANGE_UNITS"))
        layout = QVBoxLayout(self)
        label = QLabel(tr("CHOOSE_UNITS"))
        layout.addWidget(label)

        btn_g = QPushButton("g")
        btn_oz = QPushButton("oz")
        layout.addWidget(btn_g)
        layout.addWidget(btn_oz)

        btn_g.clicked.connect(lambda: self.set_units_and_close("g"))
        btn_oz.clicked.connect(lambda: self.set_units_and_close("oz"))

        self.setLayout(layout)
        self.setModal(True)

    def set_units_and_close(self, units):
        if self.parent():
            self.parent().set_units(units)
        self.accept()

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
            super().__init__(parent)
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