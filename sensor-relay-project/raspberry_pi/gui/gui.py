from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QGridLayout, QVBoxLayout, QSizePolicy, QDialog, QPushButton, QHBoxLayout, QStyle
)
from PyQt6.QtCore import Qt, QTimer
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

        # Add these lines to create the labels
        self.final_weight_label = QLabel("Final: --")
        self.final_weight_label.setFont(QFont("Arial", 18))
        self.final_weight_label.setStyleSheet("color: #fff;")
        content_layout.addWidget(self.final_weight_label)

        self.fill_time_label = QLabel("Fill Time: -- ms")
        self.fill_time_label.setFont(QFont("Arial", 18))
        self.fill_time_label.setStyleSheet("color: #fff;")
        content_layout.addWidget(self.fill_time_label)

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

    # Example methods for your StationWidget class
    def set_final_weight(self, value):
        # Display or store the final weight value
        self.final_weight_label.setText(f"Final: {value}")

    def set_fill_time(self, value):
        # Display or store the fill time value
        self.fill_time_label.setText(f"Fill Time: {value} ms")

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
            parent.active_dialog = parent.time_limit_dialog
            parent.time_limit_dialog.finished.connect(lambda: setattr(parent, "active_dialog", None))
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
        self.active_menu = None  # e.g., "main_menu", "settings", "language_dialog", etc.
        self.active_dialog = None

    def show_menu(self):
        self.active_menu = "main_menu"
        print("RelayControlApp: show_menu() called")
        if self.menu_dialog is None or not self.menu_dialog.isVisible():
            self.menu_dialog = MenuDialog(self)
            self.active_dialog = self.menu_dialog  # <-- Set active_dialog here!
            self.menu_dialog.finished.connect(lambda: setattr(self, "active_dialog", None))
            self.menu_dialog.show()

    def set_target_weight(self, value):
        self.target_weight = value
        for i, widget in enumerate(self.station_widgets):
            if widget.weight_label.text() != "OFFLINE":
                current_weight = 0  # Or use actual current weight if available
                widget.set_weight(current_weight, self.target_weight, self.units)

    def set_time_limit(self, value):
        self.time_limit = value
        print(f"[RelayControlApp] Time limit set to {value} ms")
        # Optionally update UI here

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

    def show_timed_info(self, title, message, timeout_ms=2000):
        dialog = InfoDialog(title, message, self)
        dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        dialog.show()
        QTimer.singleShot(timeout_ms, dialog.accept)

class InfoDialog(QDialog):
    def __init__(self, title, message, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setStyleSheet("""
            QDialog {
                background-color: #222;
                border: none;
                border-radius: 24px;
            }
            QLabel#titleLabel {
                color: #fff;
                font-size: 32px;
                font-weight: bold;
                padding: 12px;
            }
            QLabel#valueLabel {
                color: #fff;
                font-size: 48px;
                font-weight: bold;
                padding: 12px;
            }
        """)
        layout = QVBoxLayout(self)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("titleLabel")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)
        self.value_label = QLabel(message)
        self.value_label.setObjectName("valueLabel")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.value_label)
        self.setLayout(layout)
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
        # Example: simple numeric value with up/down
        self.value = parent.target_weight if parent else 500
        self.min_value = 1
        self.max_value = 10000
        self.step = 10
        self.value_label = QLabel(str(self.value))
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_label.setFont(QFont("Arial", 32))
        layout.addWidget(self.value_label)
        self.setLayout(layout)
        self.setModal(True)

    def update_display(self):
        self.value_label.setText(str(self.value))

    def select_prev(self):
        self.value = max(self.min_value, self.value - self.step)
        self.update_display()

    def select_next(self):
        self.value = min(self.max_value, self.value + self.step)
        self.update_display()

    def activate_selected(self):
        if self.parent():
            self.parent().set_target_weight(self.value)
        self.accept()

class SetTimeLimitDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        tr = parent.tr if parent else (lambda k: LANGUAGES["en"].get(k, k))
        self.setWindowTitle(tr("SET_TIME_LIMIT"))
        layout = QVBoxLayout(self)
        label = QLabel(tr("ENTER_NEW_TIME_LIMIT"))
        layout.addWidget(label)

        # Start with parent's time_limit or 3000 ms, clamp to 5 digits
        initial = parent.time_limit if parent else 3000
        initial = max(0, min(initial, 99999))
        digits = f"{initial:05d}"[-5:]  # Always 5 digits

        self.digits = [int(d) for d in digits]
        self.current_digit = 0  # Start editing the leftmost digit

        # --- Add up arrows ---
        up_arrows_layout = QHBoxLayout()
        self.up_labels = []
        for i in range(5):
            up = QLabel("▲")
            up.setFont(QFont("Arial", 28, QFont.Weight.Bold))
            up.setAlignment(Qt.AlignmentFlag.AlignCenter)
            up.setFixedWidth(48)
            self.up_labels.append(up)
            up_arrows_layout.addWidget(up)
        layout.addLayout(up_arrows_layout)

        # --- Digits ---
        self.digit_labels = []
        digits_layout = QHBoxLayout()
        for i in range(5):
            lbl = QLabel(str(self.digits[i]))
            lbl.setFont(QFont("Arial", 48, QFont.Weight.Bold))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setFixedWidth(48)
            self.digit_labels.append(lbl)
            digits_layout.addWidget(lbl)
        layout.addLayout(digits_layout)

        # --- Add down arrows ---
        down_arrows_layout = QHBoxLayout()
        self.down_labels = []
        for i in range(5):
            down = QLabel("▼")
            down.setFont(QFont("Arial", 28, QFont.Weight.Bold))
            down.setAlignment(Qt.AlignmentFlag.AlignCenter)
            down.setFixedWidth(48)
            self.down_labels.append(down)
            down_arrows_layout.addWidget(down)
        layout.addLayout(down_arrows_layout)

        self.setLayout(layout)
        self.setModal(True)
        self.update_display()

    def flash_arrow(self, direction):
        """Flash the current up or down arrow green briefly."""
        if direction == "up":
            self.up_labels[self.current_digit].setStyleSheet("color: #00FF00;")
            QTimer.singleShot(100, lambda: self.up_labels[self.current_digit].setStyleSheet("color: #fff;"))
        elif direction == "down":
            self.down_labels[self.current_digit].setStyleSheet("color: #00FF00;")
            QTimer.singleShot(100, lambda: self.down_labels[self.current_digit].setStyleSheet("color: #fff;"))

    def select_prev(self):
        # UP button should increment
        self.digits[self.current_digit] = (self.digits[self.current_digit] + 1) % 10
        self.flash_arrow("up")
        self.update_display()

    def select_next(self):
        # DOWN button should decrement
        self.digits[self.current_digit] = (self.digits[self.current_digit] - 1) % 10
        self.flash_arrow("down")
        self.update_display()

    def update_display(self):
        for i, lbl in enumerate(self.digit_labels):
            if i == self.current_digit:
                lbl.setStyleSheet("color: #F6EB61; border: 2px solid #F6EB61; border-radius: 8px; background: #222;")
            else:
                lbl.setStyleSheet("color: #fff; border: 2px solid transparent; background: #222;")
            lbl.setText(str(self.digits[i]))
        # Set all arrows to white by default
        for i in range(5):
            self.up_labels[i].setStyleSheet("color: #fff;")
            self.down_labels[i].setStyleSheet("color: #fff;")

    def activate_selected(self):
        print(f"[SetTimeLimitDialog] activate_selected called. current_digit={self.current_digit}, digits={self.digits}")
        if self.current_digit < 4:  # Now 5 digits, so index 0-4
            self.current_digit += 1
            print(f"[SetTimeLimitDialog] Moving to next digit: {self.current_digit}")
            self.update_display()
        else:
            value = int("".join(str(d) for d in self.digits))
            print(f"[SetTimeLimitDialog] Final value to set: {value}")
            parent = self.parent()
            print(f"[SetTimeLimitDialog] parent: {parent}")
            if parent and hasattr(parent, "set_time_limit"):
                print(f"[SetTimeLimitDialog] Calling parent.set_time_limit({value})")
                parent.set_time_limit(value)
                # Show info dialog for 2 seconds, displaying seconds with one decimal
                if hasattr(parent, "show_timed_info"):
                    seconds = value / 1000
                    parent.show_timed_info("TIME LIMIT SAVED:", f"{seconds:.1f} sec", timeout_ms=2000)
            else:
                print("[SetTimeLimitDialog] Parent missing or has no set_time_limit method!")
            self.accept()
            # Optionally, also close the menu dialog if you want to return to main screen:
            if parent and hasattr(parent, "menu_dialog") and parent.menu_dialog is not None:
                print("[SetTimeLimitDialog] Closing parent.menu_dialog")
                parent.menu_dialog.accept()

class SelectionDialog(QDialog):
    def __init__(self, options, parent=None, title="", label_text="", outlined=True):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.selected_index = 0
        self.options = options  # List of (value, display_text) tuples
        layout = QVBoxLayout(self)
        if label_text:
            label = QLabel(label_text)
            layout.addWidget(label)
        self.labels = []
        for _, display_text in self.options:
            if outlined:
                item_label = OutlinedLabel(display_text)
            else:
                item_label = QLabel(display_text)
            item_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            item_label.setFixedSize(320, 64)
            self.labels.append(item_label)
            layout.addWidget(item_label)
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
        self.on_select(self.options[self.selected_index][0])
        self.accept()

    def on_select(self, value):
        """Override this in subclasses to handle selection."""
        pass

class SetLanguageDialog(SelectionDialog):
    def __init__(self, parent=None):
        tr = parent.tr if parent else (lambda k: LANGUAGES["en"].get(k, k))
        options = [("en", "English"), ("es", "Español")]
        super().__init__(options, parent, title=tr("SET_LANGUAGE_TITLE"), label_text=tr("CHOOSE_LANGUAGE"))
        self.parent_app = parent

    def on_select(self, lang_code):
        if self.parent_app:
            self.parent_app.set_language(lang_code)

class ChangeUnitsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        tr = parent.tr if parent else (lambda k: LANGUAGES["en"].get(k, k))
        self.setWindowTitle(tr("CHANGE_UNITS"))
        layout = QVBoxLayout(self)
        label = QLabel(tr("CHOOSE_UNITS"))
        layout.addWidget(label)

        self.units_options = ["g", "oz"]
        self.selected_index = 0

        self.labels = []
        for unit in self.units_options:
            unit_label = OutlinedLabel(unit)
            unit_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            unit_label.setFixedSize(320, 64)
            self.labels.append(unit_label)
            layout.addWidget(unit_label)
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
        units = self.units_options[self.selected_index]
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