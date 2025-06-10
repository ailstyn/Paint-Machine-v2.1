from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QFrame, QDialog, QStackedLayout, QGraphicsDropShadowEffect, QSizePolicy
)
from PyQt6.QtGui import QPixmap, QFont, QColor, QPainter
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
import os
import random
import logging
import psutil

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

        # --- CREATE SYSINFO LABEL FIRST ---
        self.sysinfo_label = QLabel()
        self.sysinfo_label.setFont(QFont("Cascadia Code", 10))
        self.sysinfo_label.setStyleSheet("color: #888; background: rgba(255,255,255,0.7); border-radius: 4px; padding: 2px;")
        self.sysinfo_label.setFixedWidth(220)
        self.sysinfo_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

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

        # --- Main horizontal layout ---
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(8, 8, 8, 8)
        self.setLayout(self.main_layout)
        self.main_layout.setSpacing(0)

        # --- Progress bar column ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setOrientation(Qt.Orientation.Vertical)
        self.progress_bar.setStyleSheet(
            f"""
            QProgressBar {{
                background: {self.bg};
                border: 2px solid {self.fg};
                border-radius: 5px;
            }}
            QProgressBar::chunk {{
                background-color: {self.fg};
                border-radius: 5px;
            }}
            """
        )
        self.progress_bar_column = QVBoxLayout()
        self.progress_bar_column.addStretch(1)
        self.progress_bar_column.addWidget(self.progress_bar, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.progress_bar_column.addStretch(1)

        # --- Labels column ---
        self.main_label = QLabel("CURRENT WEIGHT")
        self.main_label.setFont(QFont("Cascadia Code SemiBold", 32))
        self.main_label.setStyleSheet(f"color: {self.fg}; background: transparent;")
        self.main_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.current_weight_label = QLabel("0.0 g")
        self.current_weight_label.setFont(QFont("Cascadia Code", 48))
        self.current_weight_label.setStyleSheet(f"color: {self.fg}; background: transparent;")
        self.current_weight_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.target_weight_label = QLabel("")
        self.target_weight_label.setFont(QFont("Cascadia Code", 48))
        self.target_weight_label.setStyleSheet(f"color: {self.fg}; background: transparent;")
        self.target_weight_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.slash_label = QLabel("")
        self.slash_label.setFont(QFont("Cascadia Code", 48))
        self.slash_label.setStyleSheet(f"color: {self.fg}; background: transparent;")
        self.slash_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.labels_column = QVBoxLayout()
        self.labels_column.setSpacing(0)

        # Add a buffer above the main label
        self.labels_column.addSpacing(24)

        # --- Add a buffer to the left of the main label ---
        main_label_row = QHBoxLayout()
        main_label_row.addWidget(self.main_label, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.labels_column.addLayout(main_label_row)

        # --- Add a buffer to the left of the value row ---
        self.value_row = QHBoxLayout()
        self.value_row.addWidget(self.current_weight_label)
        self.value_row.addWidget(self.slash_label)
        self.value_row.addWidget(self.target_weight_label)
        self.value_row.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.value_row_widget = QWidget()
        self.value_row_widget.setLayout(self.value_row)

        value_row_outer = QHBoxLayout()
        value_row_outer.addWidget(self.value_row_widget, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.labels_column.addLayout(value_row_outer)

        # Add stretch to push sysinfo label to the bottom
        self.labels_column.addStretch(1)
        self.labels_column.addWidget(self.sysinfo_label, alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)

        # --- Dot column ---
        self.dot_widgets = []
        self.dot_column = QVBoxLayout()
        self.dot_column.addStretch(1)
        for i in range(len(self.icon_files)):
            dot_label = QLabel()
            dot_label.setFixedSize(80, 80)
            dot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dot_label.setStyleSheet(
                "background: transparent;"
                "border-radius: 8px;"
                f"color: {self.fg};"
            )
            if i == self.selected_index:
                dot_label.setText('<span style="font-size:20px;">●</span>')
            else:
                dot_label.setText("")
            self.dot_column.addWidget(dot_label)
            self.dot_widgets.append(dot_label)
            if i < len(self.icon_files) - 1:
                self.dot_column.addSpacing(32)
        self.dot_column.addStretch(1)

        # --- Icon column ---
        self.icon_labels = []
        self.icon_column = QVBoxLayout()
        self.icon_column.addStretch(1)
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
            self.icon_column.addWidget(icon_label)
            if i < len(self.icon_files) - 1:
                self.icon_column.addSpacing(32)
        self.icon_column.addStretch(1)

        # --- Combine dot and icon columns into a QWidget ---
        self.dot_icon_container = QWidget()
        dot_icon_layout = QHBoxLayout()
        dot_icon_layout.setContentsMargins(0, 0, 0, 0)
        dot_icon_layout.setSpacing(0)
        dot_icon_layout.addLayout(self.dot_column)
        dot_icon_layout.addLayout(self.icon_column)
        self.dot_icon_container.setLayout(dot_icon_layout)

        # Calculate the combined width (adjust as needed)
        dot_icon_width = 80 + 80 + 32  # 80px per column + 32px spacing between
        self.dot_icon_container.setFixedWidth(dot_icon_width)

        # --- Progress bar in a QWidget with matching width ---
        self.progress_bar_container = QWidget()
        progress_bar_layout = QVBoxLayout()
        progress_bar_layout.setContentsMargins(0, 0, 0, 0)
        progress_bar_layout.addStretch(1)
        progress_bar_layout.addWidget(self.progress_bar, alignment=Qt.AlignmentFlag.AlignHCenter)
        progress_bar_layout.addStretch(1)
        self.progress_bar_container.setLayout(progress_bar_layout)
        self.progress_bar_container.setFixedWidth(dot_icon_width)

        # --- Add all columns to the main horizontal layout with left/right buffer ---
        self.main_layout.insertSpacing(0, 24)  # Buffer to the left of progress bar
        self.main_layout.addWidget(self.progress_bar_container)
        self.main_layout.addLayout(self.labels_column, stretch=1)
        self.main_layout.addWidget(self.dot_icon_container)
        self.main_layout.addSpacing(24)  # Buffer to the right of icon column

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

        self.center_frame = QWidget()
        self.center_frame.setStyleSheet("background: transparent;")

    def adjust_progress_bar_height(self):
        parent_height = self.progress_bar.parentWidget().height() if self.progress_bar.parentWidget() else self.height()
        new_height = int(parent_height * 0.9)  # Increase from 0.6 to 0.9
        self.progress_bar.setFixedHeight(new_height)

    def refresh_ui(self):
        try:
            self.current_weight_label.setText(f"{self.current_weight:.1f} g")
            # Only show slash and target if in fill mode
            if self.main_label.text() == "FILLING":
                self.slash_label.setText("/")
                self.target_weight_label.setText(f"{self.target_weight:.1f} g")
            else:
                self.slash_label.setText("")
                self.target_weight_label.setText("")
            # Update progress bar
            self.progress_bar.setMaximum(int(self.target_weight))
            self.progress_bar.setValue(int(self.current_weight))
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
        self.main_label.setStyleSheet(f"color: {self.fg}; background: transparent;")
        self.current_weight_label.setStyleSheet(f"color: {self.fg}; background: black;")  # TEMP: black background
        self.target_weight_label.setStyleSheet(f"color: {self.fg}; background: black;")    # TEMP: black background
        self.slash_label.setStyleSheet(f"color: {self.fg}; background: black;")            # TEMP: black background
        self.center_frame.setStyleSheet("background: transparent;")
        for icon_label in self.icon_labels:
            icon_label.setStyleSheet(f"color: {self.fg}; background-color: {self.bg};")
        for dot_label in self.dot_widgets:
            dot_label.setStyleSheet(f"background: transparent; border-radius: 8px; color: {self.fg};")
        # Update progress bar color
        self.progress_bar.setStyleSheet(
            f"""
            QProgressBar {{
                background: {self.bg};
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


    def create_value_input_dialog(self, title, initial_value, unit):
        dialog = ValueInputDialog(
            title=title,
            initial_value=initial_value,
            unit=unit,
            color_scheme=COLOR_SCHEMES[self.color_scheme_index],
            parent=self
        )
        dialog.show()
        return dialog

    def set_current_weight_mode(self, weight):
        self.main_label.setText("CURRENT WEIGHT")
        self.current_weight_label.setText(f"{weight:.1f} g")
        self.slash_label.setText("")  # Hide slash
        self.target_weight_label.setText("")  # Hide target

    def set_target_weight_mode(self, target_weight):
        self.main_label.setText("SET TARGET WEIGHT")
        self.target_weight_label.setText(f"{target_weight:.1f} g")
        self.slash_label.setText("")  # Hide slash
        self.current_weight_label.setText("")  # Hide current

    def set_fill_mode(self, current_weight, target_weight):
        self.main_label.setText("FILLING")
        self.current_weight_label.setText(f"{current_weight:.1f} g")
        self.slash_label.setText("/")
        self.target_weight_label.setText(f"{target_weight:.1f} g")

    def update_sysinfo(self):
        try:
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory()
            ram_used = ram.used // (1024 * 1024)
            ram_total = ram.total // (1024 * 1024)
            # Pi temperature (if available)
            temp = "N/A"
            try:
                with open("/sys/class/thermal/thermal_zone0/temp") as f:
                    temp = f"{int(f.read())/1000:.1f}°C"
            except Exception:
                pass
            self.sysinfo_label.setText(
                f"CPU: {cpu:.1f}%\n"
                f"RAM: {ram_used} / {ram_total} MB\n"
                f"Temp: {temp}"
            )
        except Exception as e:
            self.sysinfo_label.setText("SysInfo error")

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
            background: {color_scheme['bg']};
            border: 4px solid {color_scheme['fg']};
            border-radius: 8px;
            """
        )

        self.label = QLabel(f"{self.value} {self.unit}")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setFont(QFont("Cascadia Code SemiBold", 48))
        self.label.setStyleSheet(
            f"""color: {color_scheme['fg']};
            background: transparent;
            padding: 32px;"""
                                )
        layout.addWidget(self.label)

        # Dynamically size dialog to 60% width, 40% height of the screen, max 500x300
        screen = QApplication.primaryScreen().availableGeometry()
        w = min(500, int(screen.width() * 0.6))
        h = min(300, int(screen.height() * 0.4))
        self.resize(w, h)
        # Center the dialog
        self.move(
            screen.left() + (screen.width() - w) // 2,
            screen.top() + (screen.height() - h) // 2
        )

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