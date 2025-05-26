from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QFrame, QDialog, QStackedLayout, QGraphicsDropShadowEffect, QSizePolicy
)
from PyQt6.QtGui import QPixmap, QFont, QColor
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
import os
import random

COLOR_SCHEMES = [
    {"name": "Classic Blue", "bg": "#2e3192", "fg": "white", "splash": "red"},
    {"name": "Dark Mode", "bg": "#333333", "fg": "#FFFFFF", "splash": "#F6EB61"},
    {"name": "Light Mode", "bg": "#F5FFFA", "fg": "#000000", "splash": "#800020"},
    {"name": "Green Alert", "bg": "#1B9E3A", "fg": "#FFFFFF", "splash": "#FF6F61"},
]

class RelayControlApp(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        print("Initializing RelayControlApp (PyQt)...")
        self.color_scheme_index = 0
        scheme = COLOR_SCHEMES[self.color_scheme_index]
        self.bg = scheme["bg"]
        self.fg = scheme["fg"]
        self.splash = scheme["splash"]

        self.setWindowTitle("Relay Control")
        self.setStyleSheet(f"background-color: {self.bg};")
        self.showFullScreen()

        icon_files = [
                ("dumbell.png", "Dumbbell"),
                ("stopwatch.png", "Stopwatch"),
                ("color.png", "Color"),
                ]

        # Main vertical layout
        self.main_layout = QVBoxLayout(self)
        self.setLayout(self.main_layout)

        # Top label
        self.scale_label = QLabel("SCALE 1")
        self.scale_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scale_label.setFont(QFont("Cascadia Code SemiBold", 32))
        self.scale_label.setStyleSheet(f"color: {self.fg}; background-color: {self.bg};")
        self.main_layout.addWidget(self.scale_label)

        # --- Weight Label ---
        self.current_weight = 0.0
        self.target_weight = 100.0  # Default, update as needed

        self.weight_label = QLabel("0.0 g")
        self.weight_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.weight_label.setFont(QFont("Cascadia Code SemiBold", 28))
        self.weight_label.setStyleSheet(f"color: {self.fg}; background: transparent;")
        self.main_layout.insertWidget(1, self.weight_label)  # Below scale_label

        # Horizontal layout for main content (progress bar, center, icons)
        self.content_layout = QHBoxLayout()
        self.main_layout.addLayout(self.content_layout)

        # --- Selection Dot Column (left of icons) ---
        self.dot_column = QVBoxLayout()
        self.dot_widgets = []
        self.selected_index = 0  # Start with the first icon selected

        self.dot_column.addStretch(1)  # Top stretch for vertical centering
        for i in range(len(icon_files)):
            dot_label = QLabel()
            dot_label.setFixedSize(16, 40)  # 16px wide, 40px tall to match icon spacing
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
        self.dot_column.addStretch(1)  # Bottom stretch for vertical centering

        # --- Icon Column (rightmost) ---
        self.icon_column = QVBoxLayout()
        self.icon_labels = []
        self.icon_column.addStretch(1)
        for filename, alt in icon_files:
            icon_path = os.path.join(os.path.dirname(__file__), filename)
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(
                    40, 40,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                icon_label = QLabel()
                icon_label.setPixmap(pixmap)
            else:
                icon_label = QLabel(alt)
                icon_label.setFont(QFont("Arial", 32))
                icon_label.setStyleSheet(f"color: {self.fg}; background-color: {self.bg};")
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.icon_column.addWidget(icon_label)
            self.icon_labels.append(icon_label)
        self.icon_column.addStretch(1)

        # --- Progress Bar Column (leftmost) ---
        self.progress_bar_column = QVBoxLayout()
        self.progress_bar_column.addStretch(1)
        self.progress_bar = QProgressBar()
        self.progress_bar.setOrientation(Qt.Orientation.Vertical)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(50)
        self.progress_bar.setFixedHeight(300)
        self.progress_bar.setStyleSheet(f"QProgressBar {{background: {self.bg};}}")
        self.progress_bar_column.addWidget(self.progress_bar, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.progress_bar_column.addStretch(1)

        # --- Add columns to the main content layout in order: progress bar, center, dot, icon ---
        self.center_frame = QFrame()
        self.center_frame.setStyleSheet(f"background-color: {self.bg};")
        self.content_layout.addLayout(self.progress_bar_column)
        self.content_layout.addWidget(self.center_frame, stretch=1)
        self.content_layout.addLayout(self.dot_column)
        self.content_layout.addLayout(self.icon_column)

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

        # You can continue building out the UI here, mirroring your Tkinter structure.

        # At the end of __init__:
        QTimer.singleShot(0, self.adjust_progress_bar_height)

    def adjust_progress_bar_height(self):
        new_height = int(self.height() * 0.75)
        self.progress_bar.setFixedHeight(new_height)

    def refresh_ui(self):
        # Update weight label
        self.weight_label.setText(f"{self.current_weight:.1f} g")
        # Update progress bar
        self.progress_bar.setMaximum(int(self.target_weight))
        self.progress_bar.setValue(int(self.current_weight))

    def cycle_color_scheme(self):
        # Move to the next color scheme
        self.color_scheme_index = (self.color_scheme_index + 1) % len(COLOR_SCHEMES)
        scheme = COLOR_SCHEMES[self.color_scheme_index]
        self.bg = scheme["bg"]
        self.fg = scheme["fg"]
        self.splash = scheme["splash"]

        # Update styles for all widgets
        self.setStyleSheet(f"background-color: {self.bg};")
        self.scale_label.setStyleSheet(f"color: {self.fg}; background-color: {self.bg};")
        self.center_frame.setStyleSheet(f"background-color: {self.bg};")
        self.progress_bar.setStyleSheet(f"QProgressBar {{background: {self.bg};}}")
        for icon_label in self.icon_labels:
            icon_label.setStyleSheet(f"color: {self.fg}; background-color: {self.bg};")
        for dot_label in self.dot_widgets:
            dot_label.setStyleSheet(f"background: transparent; border-radius: 8px; color: {self.fg};")

    def handle_select(self):
        # If the color icon (last icon) is selected, cycle color scheme
        if self.selected_index == 2:  # index of color.png
            self.cycle_color_scheme()
        # Add other actions for other icons as needed

    # Example: call this method when the select button is pressed
    # self.handle_select()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Up:
            if self.selected_index > 0:
                self.update_selection_dot(self.selected_index - 1)
        elif event.key() == Qt.Key.Key_Down:
            if self.selected_index < len(self.dot_widgets) - 1:
                self.update_selection_dot(self.selected_index + 1)
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.handle_select()
        else:
            super().keyPressEvent(event)

    def resizeEvent(self, event):
        # Only set height if progress_bar exists
        if hasattr(self, "progress_bar"):
            new_height = int(self.height() * 0.75)
            self.progress_bar.setFixedHeight(new_height)
        super().resizeEvent(event)

    def show_overlay(self, main_message, sub_message=""):
        # Close any existing overlay
        if hasattr(self, "overlay") and self.overlay is not None:
            self.overlay.close()
        self.overlay = OverlayDialog(main_message, sub_message, COLOR_SCHEMES[self.color_scheme_index], parent=self)
        self.overlay.show()

    def close_overlay(self):
        if hasattr(self, "overlay") and self.overlay is not None:
            self.overlay.close()
            self.overlay = None

    def reload_main_screen(self):
        pass  # No longer needed in PyQt version. Once this gui is finished the calls can be removed from main.py

class OverlayDialog(QDialog):
    def __init__(self, main_message, sub_message, color_scheme, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent;")

        # Outer border (double border effect)
        outer = QFrame(self)
        outer.setStyleSheet(f"""
            QFrame {{
                background: {color_scheme['fg']};
                border-radius: 18px;
                border: 4px solid {color_scheme['fg']};
            }}
        """)
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(6, 6, 6, 6)

        # Inner border
        inner = QFrame(outer)
        inner.setStyleSheet(f"""
            QFrame {{
                background: {color_scheme['splash']};
                border-radius: 12px;
                border: 4px solid {color_scheme['fg']};
            }}
        """)
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(24, 24, 24, 24)
        inner_layout.setSpacing(12)

        # Main message
        main_label = QLabel(main_message)
        main_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_label.setFont(QFont("Cascadia Code SemiBold", 28))
        main_label.setStyleSheet(f"color: {color_scheme['fg']}; background: transparent;")
        inner_layout.addWidget(main_label)

        # Sub message
        sub_label = QLabel(sub_message)
        sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub_label.setFont(QFont("Cascadia Code SemiBold", 22))
        sub_label.setStyleSheet(f"color: {color_scheme['fg']}; background: transparent;")
        inner_layout.addWidget(sub_label)

        outer_layout.addWidget(inner)
        layout = QVBoxLayout(self)
        layout.addWidget(outer)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.adjustSize()
        self.center_on_parent()

    def center_on_parent(self):
        if self.parent():
            parent_rect = self.parent().geometry()
            self.move(
                parent_rect.x() + (parent_rect.width() - self.width()) // 2,
                parent_rect.y() + (parent_rect.height() - self.height()) // 2
            )

# Add these methods to RelayControlApp:

def show_overlay(self, main_message, sub_message=""):
    # Close any existing overlay
    if hasattr(self, "overlay") and self.overlay is not None:
        self.overlay.close()
    self.overlay = OverlayDialog(main_message, sub_message, COLOR_SCHEMES[self.color_scheme_index], parent=self)
    self.overlay.show()

def close_overlay(self):
    if hasattr(self, "overlay") and self.overlay is not None:
        self.overlay.close()
        self.overlay = None

# Add these methods to your RelayControlApp class.

if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    window = RelayControlApp()
    window.show()

    # Simulate progress bar going up and down
    def simulate_progress():
        value = random.randint(0, 100)
        window.progress_bar.setValue(value)

    progress_timer = QTimer()
    progress_timer.timeout.connect(simulate_progress)
    progress_timer.start(500)  # Update every 500ms

    # Simulate overlay opening and closing
    def show_estop_overlay():
        window.show_overlay("E-STOP ACTIVATED", "")
        # Close overlay after 2 seconds
        QTimer.singleShot(2000, window.close_overlay)

    # Show overlay every 5 seconds
    overlay_timer = QTimer()
    overlay_timer.timeout.connect(show_estop_overlay)
    overlay_timer.start(5000)

    sys.exit(app.exec_())