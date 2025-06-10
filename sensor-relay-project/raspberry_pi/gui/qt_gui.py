from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QFrame, QDialog, QStackedLayout, QGraphicsDropShadowEffect, QSizePolicy
)
from PyQt6.QtGui import QPixmap, QFont, QColor, QPainter
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
import os
import random
import logging

COLOR_SCHEMES = [
    {"name": "Classic Blue", "bg": "#2e3192", "fg": "#FFFFFF", "splash": "#CB1212"},
    {"name": "Dark Mode", "bg": "#333333", "fg": "#FFFFFF", "splash": "#F6EB61"},
    {"name": "Light Mode", "bg": "#F5FFFA", "fg": "#000000", "splash": "#800020"},
    {"name": "Green Alert", "bg": "#1B9E3A", "fg": "#FFFFFF", "splash": "#FF6F61"},
]

def tint_pixmap(pixmap, color):
    """Return a new QPixmap tinted with the given color."""
    tinted = QPixmap(pixmap.size())
    tinted.fill(Qt.GlobalColor.transparent)
    painter = QPainter(tinted)
    painter.drawPixmap(0, 0, pixmap)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(tinted.rect(), QColor(color))
    painter.end()
    return tinted

class RelayControlApp(QWidget):
    def __init__(self, parent=None, set_target_weight_callback=None, set_time_limit_callback=None):
        super().__init__(parent)
        self.set_target_weight_callback = set_target_weight_callback
        self.set_time_limit_callback = set_time_limit_callback
        print("Initializing RelayControlApp (PyQt)...")
        self.color_scheme_index = 0
        scheme = COLOR_SCHEMES[self.color_scheme_index]
        self.bg = scheme["bg"]
        self.fg = scheme["fg"]
        self.splash = scheme["splash"]

        self.setWindowTitle("Relay Control")
        self.setStyleSheet(f"background-color: {self.bg};")

        icon_files = [
                ("dumbell.png", "Dumbbell"),
                ("stopwatch.png", "Stopwatch"),
                ("color.png", "Color"),
                ]

        # Main vertical layout
        self.main_layout = QVBoxLayout(self)
        self.setLayout(self.main_layout)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # --- Main display labels in the center ---
        self.main_label = QLabel("CURRENT WEIGHT")
        self.main_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_label.setFont(QFont("Cascadia Code SemiBold", 40))
        self.main_label.setStyleSheet(f"color: {self.fg}; background: transparent;")
        self.main_layout.addWidget(self.main_label)

        self.value_row = QHBoxLayout()
        self.value_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.current_weight_label = QLabel("0.0 g")
        self.current_weight_label.setFont(QFont("Cascadia Code SemiBold", 28))
        self.current_weight_label.setStyleSheet(f"color: {self.fg}; background: transparent;")

        self.slash_label = QLabel("/")
        self.slash_label.setFont(QFont("Cascadia Code SemiBold", 28))
        self.slash_label.setStyleSheet(f"color: {self.fg}; background: transparent;")

        self.target_weight_label = QLabel("0.0 g")
        self.target_weight_label.setFont(QFont("Cascadia Code SemiBold", 28))
        self.target_weight_label.setStyleSheet(f"color: {self.fg}; background: transparent;")

        self.value_row.addWidget(self.current_weight_label)
        self.value_row.addWidget(self.slash_label)
        self.value_row.addWidget(self.target_weight_label)
        self.main_layout.addLayout(self.value_row)

        # Horizontal layout for main content (progress bar, center, icons)
        self.content_layout = QHBoxLayout()
        self.main_layout.addLayout(self.content_layout)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)

        # --- Selection Dot Column (left of icons) ---
        self.dot_column = QVBoxLayout()
        self.dot_column.setContentsMargins(0, 0, 0, 0)
        self.dot_column.setSpacing(0)
        self.dot_widgets = []
        self.selected_index = 0  # Start with the first icon selected

        self.dot_column.addStretch(1)  # Top stretch for vertical centering
        for i in range(len(icon_files)):
            dot_label = QLabel()
            dot_label.setFixedSize(80, 80)  # 80px wide, 80px tall to match icon size
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
            if i < len(icon_files) - 1:
                self.dot_column.addSpacing(32)  # Match icon spacing
        self.dot_column.addStretch(1)  # Bottom stretch for vertical centering

        # --- Icon Column (rightmost) ---
        self.icon_column = QVBoxLayout()
        self.icon_column.setContentsMargins(0, 0, 0, 0)
        self.icon_column.setSpacing(32)  # Increase spacing between icons
        self.icon_labels = []
        self.icon_column.addStretch(1)
        for filename, alt in icon_files:
            icon_path = os.path.join(os.path.dirname(__file__), filename)
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(
                    80, 80,  # Double the previous 40x40 size
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                # Only recolor the weight and time icons (not the color icon)
                if i in (0, 1):
                    pixmap = tint_pixmap(pixmap, self.fg)
                self.icon_labels[i].setPixmap(pixmap)
                self.icon_labels[i].setText("")
            else:
                self.icon_labels[i].setText(alt)
                self.icon_labels[i].setFont(QFont("Arial", 64))
                self.icon_labels[i].setStyleSheet(f"color: {self.fg}; background-color: {self.bg};")
            self.icon_labels.append(icon_label)
        self.icon_column.addStretch(1)

        # --- Progress Bar Column (leftmost) ---
        self.progress_bar_column = QVBoxLayout()
        self.progress_bar_column.setContentsMargins(0, 0, 0, 0)
        self.progress_bar_column.setSpacing(0)
        self.progress_bar_column.addStretch(1)  # Top stretch

        # Make the progress bar 20% larger (width)
        progress_bar_width = 36  # original was likely 30, increase by 20%
        self.progress_bar = QProgressBar()
        self.progress_bar.setOrientation(Qt.Orientation.Vertical)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(50)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedWidth(progress_bar_width)
        # Set the background to foreground color and the bar to splash color
        self.progress_bar.setStyleSheet(
            f"""
            QProgressBar {{
                background: {self.fg};
                border: 2px solid {self.fg};
                border-radius: 5px;
            }}
            QProgressBar::chunk {{
                background-color: {self.splash};
                border-radius: 5px;
            }}
            """
        )
        self.progress_bar_column.addWidget(self.progress_bar, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.progress_bar_column.addStretch(1)  # Bottom stretch

        # --- Add columns to the main content layout in order: progress bar, center, dot, icon ---
        self.center_frame = QFrame()
        self.center_frame.setStyleSheet(f"background-color: {self.bg};")
        self.center_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # Add left buffer before the progress bar

        self.content_layout.addSpacing(25)  # Add 25px buffer to the left of the progress bar
        self.content_layout.addLayout(self.progress_bar_column)
        self.content_layout.addWidget(self.center_frame, stretch=1)
        self.content_layout.addLayout(self.dot_column)
        self.content_layout.addLayout(self.icon_column)
        self.content_layout.addSpacing(25)  # Add 25px buffer to the right of the icons

        # Add right buffer after the icons
        self.right_buffer = QVBoxLayout()
        self.right_buffer.addSpacing(25)
        self.content_layout.addLayout(self.right_buffer)

        # --- To move the selection dot in code ---
        # Call this function when you want to update the selected icon
        def update_selection_dot(new_index):
            for i, dot_label in enumerate(self.dot_widgets):
                if i == new_index:
                    dot_label.setText('<span style="font-size:20px;">●</span>')
                else:
                    dot_label.setText("")
            self.selected_index = new_index

        self.update_selection_dot = update_selection_dot  # Expose for external use

        # At the end of __init__:
        QTimer.singleShot(0, self.adjust_progress_bar_height)

        # Move this to the end:
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)
        self.showFullScreen()

        self.overlay_widget = OverlayWidget(self)
        self.overlay_widget.resize(self.size())
        self.overlay_widget.raise_()
        self.overlay_widget.hide()

    def adjust_progress_bar_height(self):
        # Use the available height in the progress bar column, minus some margin for the percent label
        parent_height = self.progress_bar.parentWidget().height() if self.progress_bar.parentWidget() else self.height()
        new_height = int(parent_height * 0.6)
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
        self.current_weight_label.setStyleSheet(f"color: {self.fg}; background: transparent;")
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
        # 0 = dumbell, 1 = stopwatch, 2 = color
        if self.selected_index == 0 and self.set_target_weight_callback:
            self.set_target_weight_callback(self)
        elif self.selected_index == 1 and self.set_time_limit_callback:
            self.set_time_limit_callback(self)
        elif self.selected_index == 2:
            self.cycle_color_scheme()

    # Example: call this method when the select button is pressed
    # self.handle_select()

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

class ValueInputDialog(QDialog):
    def __init__(self, title, initial_value, unit, color_scheme, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.value = initial_value
        self.unit = unit
        self.color_scheme = color_scheme

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Use the background color for the dialog and a border with the foreground color
        self.setStyleSheet(
            f"""
            background: {color_scheme['bg']};
            """
        )

        self.label = QLabel(f"{self.value} {self.unit}")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setFont(QFont("Cascadia Code SemiBold", 48))
        self.label.setStyleSheet(
            f"color: {color_scheme['fg']}; background: transparent; padding: 32px;"
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