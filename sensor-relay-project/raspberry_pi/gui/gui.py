from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QGridLayout, QVBoxLayout, QSizePolicy, QDialog, QPushButton, QHBoxLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QPainterPath, QPixmap  # <-- Add QPixmap here
import sys
import logging
import os

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
        new_text = f"{current_weight:.1f} / {target_weight:.1f} {unit}"
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
        self.selected_index = 0
        self.setWindowTitle("Menu")
        self.setModal(True)
        # Use hardcoded colors
        fg = "#fff"
        splash = "#F6EB61"
        self.setStyleSheet(f"""
            QDialog {{
                background-color: #222;
                color: {fg};
                border: 6px solid {fg};
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
                color: {fg};
            """)
            self.icon_labels.append(icon_label)
            layout.addWidget(icon_label)
        self.update_selection_box()

        self.setFixedSize((112 + 32) * len(icon_files) + 32, 176)  # Width: icon+spacing, Height: icon+padding

    def update_selection_box(self):
        fg = "#fff"
        splash = "#F6EB61"
        for i, label in enumerate(self.icon_labels):
            if i == self.selected_index:
                label.setStyleSheet(f"""
                    border: 6px solid {splash};
                    border-radius: 24px;
                    background: transparent;
                    color: {fg};
                """)
            else:
                label.setStyleSheet(f"""
                    border: 6px solid transparent;
                    border-radius: 24px;
                    background: transparent;
                    color: {fg};
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
        self.showMaximized()

        self.target_weight = 0
        self.time_limit = 0
        self.language = "en"

    def show_menu(self):
        menu = MenuDialog(self)
        menu.exec()

    def set_target_weight(self, value):
        self.target_weight = value

    def set_time_limit(self, value):
        self.time_limit = value

    def set_language(self, lang_code):
        self.language = lang_code

    def show_info_dialog(self, title, message):
        dialog = InfoDialog(title, message, self)
        dialog.exec()

    def update_station_weight(self, station_index, weight):
        self.station_widgets[station_index].set_weight(weight, self.target_weight)

    def refresh_ui(self):
        QApplication.processEvents()

    def update_station_states(self, station_enabled):
        for i, widget in enumerate(self.station_widgets):
            if station_enabled[i]:
                widget.set_active(True, self.bg_colors[i], self.bg_colors_deactivated[i])
            else:
                widget.set_active(False, self.bg_colors[i], self.bg_colors_deactivated[i])

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