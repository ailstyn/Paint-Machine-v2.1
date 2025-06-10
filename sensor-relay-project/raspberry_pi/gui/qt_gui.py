from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QFrame, QDialog, QStackedLayout, QGraphicsDropShadowEffect, QSizePolicy,
    QGridLayout
)
from PyQt6.QtGui import QPixmap, QFont, QColor, QPainter
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
import os
import random
import logging
import sys
from PyQt6.QtWidgets import QApplication

COLOR_SCHEMES = [
    {"name": "Classic Blue", "bg": "#2e3192", "fg": "#FFFFFF", "splash": "#CB1212"},
    {"name": "Dark Mode", "bg": "#333333", "fg": "#FFFFFF", "splash": "#F6EB61"},
    {"name": "Light Mode", "bg": "#F5FFFA", "fg": "#000000", "splash": "#800020"},
    {"name": "Green Alert", "bg": "#1B9E3A", "fg": "#FFFFFF", "splash": "#FF6F61"},
]

class RelayControlApp(QWidget):
    def __init__(self, parent=None, set_target_weight_callback=None, set_time_limit_callback=None, set_calibrate_callback=None):
        super().__init__(parent)
        self.set_target_weight_callback = set_target_weight_callback
        self.set_time_limit_callback = set_time_limit_callback
        self.set_calibrate_callback = set_calibrate_callback

        self.selected_index = 0
        self.color_scheme_index = 0
        scheme = COLOR_SCHEMES[self.color_scheme_index]
        self.bg = scheme["bg"]
        self.fg = scheme["fg"]
        self.splash = scheme["splash"]

        self.setWindowTitle("Relay Control")
        self.setStyleSheet(f"background-color: {self.bg};")

        self.icon_files = [
            ("dumbell.png", "Dumbbell"),
            ("stopwatch.png", "Stopwatch"),
            ("geometric-tool.png", "Calibrate"),
            ("color.png", "Color"),
        ]

        # --- Section 1: Progress Bar (left) ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setOrientation(Qt.Orientation.Vertical)
        self.progress_bar.setStyleSheet(
            f"""
            QProgressBar {{
                background: transparent;
                border: 2px solid {self.fg};
                border-radius: 5px;
            }}
            QProgressBar::chunk {{
                background-color: {self.fg};
                border-radius: 5px;
            }}
            """
        )
        progress_bar_container = QWidget()
        progress_bar_layout = QVBoxLayout(progress_bar_container)
        progress_bar_layout.addWidget(self.progress_bar, alignment=Qt.AlignmentFlag.AlignHCenter)
        progress_bar_layout.addStretch(1)
        progress_bar_layout.setContentsMargins(16, 16, 16, 16)
        progress_bar_container.setFixedWidth(150)  # Adjust this value as needed (was likely 200 before)

        # --- Section 2: Weight label (top center) ---

        self.current_weight_label = QLabel("0.0 g")
        self.current_weight_label.setFont(QFont("Cascadia Code", 48))
        self.current_weight_label.setStyleSheet(f"color: {self.fg}; background: transparent;")
        self.current_weight_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.target_weight_label = QLabel("")
        self.target_weight_label.setFont(QFont("Cascadia Code", 48))
        self.target_weight_label.setStyleSheet(f"color: {self.fg}; background: transparent;")
        self.target_weight_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.slash_label = QLabel("/")
        self.slash_label.setFont(QFont("Cascadia Code", 48))
        self.slash_label.setStyleSheet(f"color: {self.fg}; background: transparent;")
        self.slash_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        top_center_container = QWidget()
        top_center_layout = QVBoxLayout(top_center_container)
        top_center_layout.setContentsMargins(16, 16, 16, 16)
        # Weight row
        weight_row = QHBoxLayout()
        weight_row.addWidget(self.current_weight_label)
        weight_row.addWidget(self.slash_label)
        weight_row.addWidget(self.target_weight_label)
        weight_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_center_layout.addLayout(weight_row)

        # --- Section 3: Dialog/message area (center) ---
        self.dialog_area = QWidget()
        self.dialog_area_layout = QVBoxLayout(self.dialog_area)
        self.dialog_area_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dialog_area.setStyleSheet("border: 2px solid white;")  # <-- Added border style here

        # --- Section 4: Selection dot and icon columns (right) ---
        self.dot_widgets = []
        dot_column = QVBoxLayout()
        dot_column.addStretch(1)
        for i in range(len(self.icon_files)):
            dot_label = QLabel()
            dot_label.setFixedSize(80, 80)
            dot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dot_label.setStyleSheet(
                "background: transparent;"
                f"color: {self.fg};"
            )
            if i == self.selected_index:
                dot_label.setText('<span style="font-size:20px;">●</span>')
            else:
                dot_label.setText("")
            dot_column.addWidget(dot_label)
            self.dot_widgets.append(dot_label)
            if i < len(self.icon_files) - 1:
                dot_column.addSpacing(32)
        dot_column.addStretch(1)

        icon_column = QVBoxLayout()
        icon_column.addStretch(1)
        self.icon_labels = []
        for i, (filename, alt) in enumerate(self.icon_files):
            icon_label = QLabel()
            icon_path = os.path.join(os.path.dirname(__file__), filename)
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(
                    80, 80,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                icon_label.setPixmap(pixmap)
                icon_label.setText("")
            else:
                icon_label.setText(alt)
                icon_label.setFont(QFont("Arial", 64))
                icon_label.setStyleSheet(f"color: {self.fg}; background-color: {self.bg};")
            self.icon_labels.append(icon_label)
            icon_column.addWidget(icon_label)
            if i < len(self.icon_files) - 1:
                icon_column.addSpacing(32)
        icon_column.addStretch(1)

        dot_icon_container = QWidget()
        dot_icon_layout = QHBoxLayout(dot_icon_container)  # <-- Use QHBoxLayout here!
        dot_icon_layout.setContentsMargins(0, 0, 0, 0)
        dot_icon_layout.setSpacing(0)
        dot_icon_layout.addLayout(dot_column)
        dot_icon_layout.addLayout(icon_column)
        dot_icon_container.setFixedWidth(150)  # Adjust this value as needed (was likely 200 before)

        # --- Main grid layout ---
        grid = QGridLayout(self)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setSpacing(8)
        grid.addWidget(progress_bar_container, 0, 0, 2, 1)   # Section 1: left, spans 2 rows
        grid.addWidget(top_center_container, 0, 1, 1, 1)     # Section 2: top center
        grid.addWidget(self.dialog_area, 1, 1, 1, 1)         # Section 3: center
        grid.addWidget(dot_icon_container, 0, 2, 2, 1)       # Section 4: right, spans 2 rows

        self.setLayout(grid)

        # --- To move the selection dot in code ---
        def update_selection_dot(new_index):
            for i, dot_label in enumerate(self.dot_widgets):
                if i == new_index:
                    dot_label.setText('<span style="font-size:20px;">●</span>')
                else:
                    dot_label.setText("")
            self.selected_index = new_index

        self.update_selection_dot = update_selection_dot  # Expose for external use

        QTimer.singleShot(0, self.adjust_progress_bar_height)

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.showFullScreen()

        self.overlay_widget = OverlayWidget(self)
        self.overlay_widget.resize(self.size())
        self.overlay_widget.raise_()
        self.overlay_widget.hide()

    def adjust_progress_bar_height(self):
        parent_height = self.progress_bar.parentWidget().height() if self.progress_bar.parentWidget() else self.height()
        new_height = int(parent_height * 0.9)  # Increase from 0.6 to 0.9
        self.progress_bar.setFixedHeight(new_height)

    def refresh_ui(self):
        try:
            self.current_weight_label.setText(f"{self.current_weight:.1f} g")
            self.progress_bar.setValue(int(self.current_weight))
            # If you have a target weight, update that too:
            self.target_weight_label.setText(f"{getattr(self, 'target_weight', 0):.1f} g")
            self.progress_bar.setMaximum(int(getattr(self, 'target_weight', 100)))
            # Update any other widgets as needed
        except Exception as e:
            logging.error(f"Error in refresh_ui: {e}")

    def cycle_color_scheme(self):
        # Move to the next color scheme
        self.color_scheme_index = (self.color_scheme_index + 1) % len(COLOR_SCHEMES)
        scheme = COLOR_SCHEMES[self.color_scheme_index]
        self.bg = scheme["bg"]
        self.fg = scheme["fg"]
        self.splash = scheme["splash"]

        # Update styles for all widgets
        self.setStyleSheet(f"background-color: {self.bg};")
        self.current_weight_label.setStyleSheet(f"color: {self.fg}; background: transparent;")
        self.target_weight_label.setStyleSheet(f"color: {self.fg}; background: transparent;")
        self.slash_label.setStyleSheet(f"color: {self.fg}; background: transparent;")
        for icon_label, (filename, alt) in zip(self.icon_labels, self.icon_files):
            if icon_label.pixmap() is None or icon_label.pixmap().isNull():
                icon_label.setStyleSheet(f"color: {self.fg}; background-color: {self.bg};")
            # If you want to update the pixmap for a different color scheme, reload it here
        for dot_label in self.dot_widgets:
            dot_label.setStyleSheet(f"background: transparent; border-radius: 8px; color: {self.fg};")
        # Update progress bar color
        self.progress_bar.setStyleSheet(
            f"""
            QProgressBar {{
                background: transparent;
                border: 2px solid {self.fg};
                border-radius: 5px;
            }}
            QProgressBar::chunk {{
                background-color: {self.fg};
                border-radius: 5px;
            }}
            """
        )

    def handle_select(self):
        if self.selected_index == 0:
            if self.set_target_weight_callback:
                self.set_target_weight_callback(self)
        elif self.selected_index == 1:
            if self.set_time_limit_callback:
                self.set_time_limit_callback(self)
        elif self.selected_index == 2:
            print("Calibrate selected")
            if self.set_calibrate_callback:
                self.set_calibrate_callback(0, self)
        elif self.selected_index == 3:
            self.cycle_color_scheme()


    def keyPressEvent(self, event):
        try:
            if event.key() == Qt.Key.Key_Up:
                if self.selected_index > 0:
                    self.update_selection_dot(self.selected_index - 1)
            elif event.key() == Qt.Key.Key_Down:
                if self.selected_index < len(self.dot_widgets) - 1:
                    self.update_selection_dot(self.selected_index + 1)
            elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.handle_select()
            elif event.key() == Qt.Key.Key_Escape:
                self.showNormal()
            else:
                super().keyPressEvent(event)
        except Exception as e:
            logging.error(f"Error in keyPressEvent: {e}")

    def resizeEvent(self, event):
        try:
            if hasattr(self, "progress_bar"):
                self.adjust_progress_bar_height()
            if hasattr(self, "overlay_widget"):
                self.overlay_widget.resize(self.size())
            super().resizeEvent(event)
        except Exception as e:
            logging.error(f"Error in resizeEvent: {e}")


    def set_current_weight_mode(self, weight):
        self.current_weight_label.setText(f"{weight:.1f} g")

    def set_target_weight_mode(self, target_weight):
        self.target_weight_label.setText(f"{target_weight:.1f} g")

    def set_fill_mode(self, current_weight, target_weight):
        self.current_weight_label.setText(f"{current_weight:.1f} g")

    def show_dialog_content(self, title, message, input_widget=None, on_accept=None):
        # Clear previous content
        for i in reversed(range(self.dialog_area_layout.count())):
            widget = self.dialog_area_layout.itemAt(i).widget()
            if widget is not None:
                widget.setParent(None)

        # Title
        title_label = QLabel(title)
        title_label.setFont(QFont("Cascadia Code SemiBold", 32))
        title_label.setStyleSheet(f"color: {self.fg}; background: transparent;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dialog_area_layout.addWidget(title_label)

        # Message
        message_label = QLabel(message)
        message_label.setFont(QFont("Cascadia Code", 24))
        message_label.setStyleSheet(f"color: {self.fg}; background: transparent;")
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dialog_area_layout.addWidget(message_label)

        # Optional input widget (e.g., QSpinBox, QLineEdit, etc.)
        if input_widget:
            self.dialog_area_layout.addWidget(input_widget)

        # Optional accept button
        if on_accept:
            accept_btn = QPushButton("OK")
            accept_btn.setFont(QFont("Cascadia Code", 20))
            accept_btn.clicked.connect(on_accept)
            self.dialog_area_layout.addWidget(accept_btn)

    def clear_dialog_content(self):
        for i in reversed(range(self.dialog_area_layout.count())):
            widget = self.dialog_area_layout.itemAt(i).widget()
            if widget is not None:
                widget.setParent(None)

class ValueInputDialog(QDialog):
    def __init__(self, title, initial_value, unit, color_scheme, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)
        self.setModal(True)
        self.value = initial_value
        self.unit = unit
        self.color_scheme = color_scheme

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Add border with foreground color
        self.setStyleSheet(
            f"""
            background: {color_scheme['fg']};
            border-radius: 24px;
            """
        )

        self.label = QLabel(f"{self.value} {self.unit}")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setFont(QFont("Cascadia Code SemiBold", 48))
        self.label.setStyleSheet(
            f"""color: {color_scheme['bg']};
            background: transparent;
            padding: 32px;"""
        )
        layout.addWidget(self.label)

        self.setFixedSize(600, 325)  # Set your preferred size here

    def update_value(self, value):
        try:
            self.value = value
            self.label.setText(f"{self.value} {self.unit}")
        except Exception as e:
            logging.error(f"Error in ValueInputDialog.update_value: {e}")

    @classmethod
    def message_only(cls, title, message, color_scheme, parent=None):
        dlg = cls(title, "", "", color_scheme, parent)
        dlg.label.setText(message)
        dlg.label.setFont(QFont("Cascadia Code SemiBold", 32))
        dlg.label.setStyleSheet(f"color: {color_scheme['fg']}; background: transparent; padding: 32px;")
        dlg.label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # Ensure label text is centered
        dlg.layout().setAlignment(Qt.AlignmentFlag.AlignCenter)  # Ensure layout is centered
        dlg.setFixedSize(600, 325)  # Ensure message-only dialogs are also fixed size
        return dlg

class OverlayWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setStyleSheet("background: rgba(0,0,0,0%);")
        self.label = QLabel("", self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("color: white; font-size: 32px; background: transparent;")
        self.hide()

    def show_overlay(self, message, color=None, fg="#fff"):
        # Use splash color if color is not provided
        if color is None and hasattr(self.parent(), "splash"):
            color = self.parent().splash
        elif color is None:
            color = "#800020"
        self.setStyleSheet(f"background: rgba(0,0,0,128);")
        self.label.setText(message)
        self.label.setStyleSheet(
            f"color: {fg}; font-size: 32px; background: {color}; border-radius: 18px; padding: 24px;"
        )
        self.label.resize(int(self.width() * 0.7), 120)
        self.label.move((self.width() - self.label.width()) // 2, (self.height() - self.label.height()) // 2)
        self.show()

    def resizeEvent(self, event):
        # Keep label centered on resize
        self.label.resize(int(self.width() * 0.7), 120)
        self.label.move((self.width() - self.label.width()) // 2, (self.height() - self.label.height()) // 2)
        super().resizeEvent(event)

    def hide_overlay(self):
        self.hide()

def create_message_dialog(self, title, message):
    return ValueInputDialog.message_only(
        title=title,
        message=message,
        color_scheme=COLOR_SCHEMES[self.color_scheme_index],
        parent=self
    )
RelayControlApp.create_message_dialog = create_message_dialog

if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = RelayControlApp()
    # window.show()

    # Simulate progress bar going up and down
    def simulate_progress():
        value = random.randint(0, 100)
        window.progress_bar.setValue(value)

    progress_timer = QTimer()
    progress_timer.timeout.connect(simulate_progress)
    progress_timer.start(500)  # Update every 500ms

    # Simulate overlay opening and closing
    def show_estop_overlay():
        window.overlay_widget.show_overlay("E-STOP ACTIVATED", color=window.splash)
        QTimer.singleShot(2000, window.overlay_widget.hide_overlay)

    # Show overlay every 5 seconds
    overlay_timer = QTimer()
    overlay_timer.timeout.connect(show_estop_overlay)
    overlay_timer.start(5000)

    sys.exit(app.exec())