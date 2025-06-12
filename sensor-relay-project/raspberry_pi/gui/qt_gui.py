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
from gui.languages import LANGUAGES

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
            ("color.png", "Color"),
            ("language.png", "Language"),
            ("ruler.png", "Ruler"),
            ("geometric-tool.png", "Calibrate"),
        ]

        # --- Section 1: Progress Bar (left) ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setOrientation(Qt.Orientation.Vertical)
        self.progress_bar.setFixedSize(60, 500)  # Or another value that fits your display
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
        progress_bar_layout.setContentsMargins(16, 16, 16, 16)
        progress_bar_layout.addStretch(1)  # Add stretch above
        progress_bar_layout.addWidget(self.progress_bar, alignment=Qt.AlignmentFlag.AlignHCenter)
        progress_bar_layout.addStretch(1)  # Add stretch below
        progress_bar_container.setFixedWidth(90)  # Adjust to match or slightly exceed progress bar width

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
        self.dialog_area.setObjectName("DialogArea")
        self.dialog_area_layout = QVBoxLayout(self.dialog_area)
        self.dialog_area_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dialog_area.setStyleSheet("#DialogArea { border: 2px solid white; }")
        self.dialog_area.setMaximumWidth(700)  # Adjust as needed

        # --- Section 4: Selection dot and icon columns (right) ---
        self.dot_widgets = []
        dot_column = QVBoxLayout()
        dot_column.addStretch(1)
        for i in range(len(self.icon_files)):
            dot_label = QLabel()
            dot_label.setFixedSize(60, 60)  # Changed from 80x80 to 60x60
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
                dot_column.addSpacing(24)  # Optionally reduce spacing for more icons
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
                    60, 60,  # Changed from 80x80 to 60x60
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                icon_label.setPixmap(pixmap)
                icon_label.setText("")
            else:
                icon_label.setText(alt)
                icon_label.setFont(QFont("Arial", 48))  # Adjust font size for smaller icon
                icon_label.setStyleSheet(f"color: {self.fg}; background-color: {self.bg};")
            self.icon_labels.append(icon_label)
            icon_column.addWidget(icon_label)
            if i < len(self.icon_files) - 1:
                icon_column.addSpacing(24)  # Optionally reduce spacing for more icons
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

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.showFullScreen()

        self.overlay_widget = OverlayWidget(self)
        self.overlay_widget.resize(self.size())
        self.overlay_widget.hide()

        self.display_unit = "g"  # or "oz"
        self.language = "en"

    def refresh_ui(self):
        try:
            self.set_current_weight_mode(self.current_weight)
            self.set_target_weight_mode(self.target_weight)
            self.progress_bar.setValue(int(self.current_weight))
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
            self.cycle_color_scheme()
        elif self.selected_index == 3:
            # Language button: toggle between English and Spanish
            self.language = "es" if self.language == "en" else "en"
            print(f"Switched language to {self.language}")
            self.change_language()
        elif self.selected_index == 4:
            # Toggle between grams and ounces
            self.display_unit = "oz" if self.display_unit == "g" else "g"
            print(f"Switched display unit to {self.display_unit}")
            self.refresh_ui()  # <-- Add this line
        elif self.selected_index == 5:
            print("Calibrate selected")
            if self.set_calibrate_callback:
                self.set_calibrate_callback(0, self)


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
        if hasattr(self, "overlay_widget"):
            self.overlay_widget.resize(self.size())
        super().resizeEvent(event)


    def set_current_weight_mode(self, weight):
        if self.display_unit == "g":
            self.current_weight_label.setText(f"{weight:.1f} g")
        else:
            ounces = weight * 0.03527
            self.current_weight_label.setText(f"{ounces:.1f} oz")  # Changed to .1f

    def set_target_weight_mode(self, target_weight):
        if self.display_unit == "g":
            self.target_weight_label.setText(f"{target_weight:.1f} g")
        else:
            ounces = target_weight * 0.03527
            self.target_weight_label.setText(f"{ounces:.1f} oz")  # Changed to .1f

    def set_fill_mode(self, current_weight, target_weight):
        self.current_weight_label.setText(f"{current_weight:.1f} g")

    def show_dialog_content(self, title, message, input_widget=None, on_accept=None, bg_color=None):
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
        fg = self.fg
        if bg_color:
            message_label.setStyleSheet(f"color: {fg}; background: {bg_color}; border-radius: 12px;")
        else:
            message_label.setStyleSheet(f"color: {fg}; background: transparent;")
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message_label.setWordWrap(True)
        message_label.setMaximumWidth(700)
        message_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
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

    def change_language(self):
        if self.language == "en":
            self.show_dialog_content("Language", "English")
        elif self.language == "es":
            self.show_dialog_content("Idioma", "Español")
        # Hide the dialog content after 2 seconds
        QTimer.singleShot(2000, self.clear_dialog_content)

    def update_dialog_colors(self):
        # Update dialog area border
        self.dialog_area.setStyleSheet(f"#DialogArea {{ border: 2px solid {self.fg}; }}")
        # Update all labels/buttons in the dialog area
        for i in range(self.dialog_area_layout.count()):
            widget = self.dialog_area_layout.itemAt(i).widget()
            if isinstance(widget, QLabel):
                widget.setStyleSheet(f"color: {self.fg}; background: transparent;")
            elif isinstance(widget, QPushButton):
                widget.setStyleSheet(f"color: {self.fg}; background: {self.bg};")

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
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.label = QLabel("", self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setWordWrap(True)
        self.label.setStyleSheet("color: white; font-size: 48px; background: transparent;")
        self.hide()

    def show_overlay(self, message, color=None, fg=None):
        if self.parent():
            self.resize(self.parent().size())  # Ensure overlay fills the window
        if self.parent() and hasattr(self.parent(), "splash"):
            if color is None:
                color = self.parent().splash
            if fg is None and hasattr(self.parent(), "fg"):
                fg = self.parent().fg
        if fg is None:
            fg = "#ffffff"
        self.label.setText(message)
        self.label.setStyleSheet(
            f"color: {fg}; font-size: 64px; font-weight: bold; background: transparent; padding: 32px;"
        )
        self.setStyleSheet(
            f"background-color: {color};"
        )
        self.show()
        self.raise_()

    def resizeEvent(self, event):
        self.label.resize(int(self.width() * 0.9), int(self.height() * 0.8))
        self.label.move(
            (self.width() - self.label.width()) // 2,
            (self.height() - self.label.height()) // 2
        )
        super().resizeEvent(event)

    def hide_overlay(self):
        self.hide()

    def paintEvent(self, event):
        # Explicitly fill the background with the current color
        p = QPainter(self)
        bg = self.palette().color(self.backgroundRole())
        p.fillRect(self.rect(), bg)
        super().paintEvent(event)

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
    from PyQt6.QtCore import QTimer
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = RelayControlApp()
    window.show()

    # Set initial colors
    window.fg = "#000000"  # or whatever your new foreground color is
    window.bg = "#ffffff"  # or whatever your new background color is
    window.update_dialog_colors()

    def show_and_hide_overlay():
        lang = window.language if hasattr(window, "language") else "en"
        window.overlay_widget.show_overlay(
            f"<b>{LANGUAGES[lang]['ESTOP_TITLE']}</b><br>{LANGUAGES[lang]['ESTOP_MSG'].replace(chr(10), '<br>')}",
            color=window.splash
        )
        # Hide overlay after 6 seconds
        QTimer.singleShot(6000, window.overlay_widget.hide_overlay)

    # Show overlay after 2 seconds
    QTimer.singleShot(2000, show_and_hide_overlay)

    sys.exit(app.exec())