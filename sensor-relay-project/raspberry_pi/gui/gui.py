from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QGridLayout, QVBoxLayout, QSizePolicy, QDialog, QPushButton, QHBoxLayout, QStyle, QSpacerItem, QFrame
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRectF
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QPainterPath, QPixmap, QCursor  # <-- Add QPixmap here
import sys
import logging
import os
from gui.languages import LANGUAGES
from app_config import DEBUG, NUM_STATIONS, target_weight, time_limit

logging.basicConfig(level=logging.INFO)

STATION_COLORS = [
    "#CB1212",  # Station 1: Red
    "#2E4BA8",  # Station 2: Blue
    "#3f922e",  # Station 3: Green
    "#EDE021",  # Station 4: Yellow
]

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

class StationBoxWidget(QWidget):
    def __init__(self, station_index, name, color, connected=None, enabled=None, weight_text=None, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Station name label
        name_label = QLabel(name)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        name_label.setStyleSheet(f"background: {color}; color: #fff; border-radius: 8px; padding: 4px;")
        layout.addWidget(name_label)

        # Connected/Enabled labels (optional)
        if connected is not None:
            connected_label = QLabel("CONNECTED" if connected else "DISCONNECTED")
            connected_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            connected_label.setFont(QFont("Arial", 16))
            connected_label.setStyleSheet(
                f"background: {color if connected else '#000'}; color: #fff; border-radius: 8px; padding: 4px;"
            )
            layout.addWidget(connected_label)
        else:
            connected_label = None

        if enabled is not None:
            enabled_label = QLabel("ENABLED" if enabled else "DISABLED")
            enabled_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            enabled_label.setFont(QFont("Arial", 16))
            enabled_label.setStyleSheet(
                f"background: {color if enabled else '#000'}; color: #fff; border-radius: 8px; padding: 4px;"
            )
            layout.addWidget(enabled_label)
        else:
            enabled_label = None

        # Weight label (optional, for calibration)
        if weight_text is not None:
            weight_label = QLabel(weight_text)
            weight_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            weight_label.setFont(QFont("Arial", 28, QFont.Weight.Bold))
            weight_label.setStyleSheet("color: #0f0;" if enabled else "color: #888;")
            layout.addWidget(weight_label)
        else:
            weight_label = None

        self.name_label = name_label
        self.connected_label = connected_label
        self.enabled_label = enabled_label
        self.weight_label = weight_label

        # Reduce the fixed size:
        self.setFixedSize(180, 160)

class StationWidget(QWidget):
    def __init__(self, station_number, bg_color, enabled=True, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.station_number = station_number

        # Use parent's tr if available, else fallback to English
        if hasattr(self.parent(), "tr"):
            self.tr = self.parent().tr
        else:
            self.tr = lambda k: LANGUAGES["en"].get(k, k)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(f"background-color: {bg_color}; border: 2px solid #222;")

        # Always define these attributes
        self.weight_label = None
        self.final_weight_label = None
        self.fill_time_label = None
        self.progress_bar = None
        self.offline_label = None

        if enabled:
            main_layout = QHBoxLayout(self)
            main_layout.setContentsMargins(0, 0, 0, 0)
            main_layout.setSpacing(0)

            bar_on_left = station_number in (1, 2)
            self.progress_bar = BottleProgressBar(max_value=100, value=0, bar_color="#4FC3F7")
            self.progress_bar.setFixedWidth(64)

            content_layout = QVBoxLayout()
            content_layout.setContentsMargins(0, 0, 0, 0)
            content_layout.setSpacing(0)

            self.weight_label = OutlinedLabel("0.0 / 0.0 g")
            self.weight_label.setFont(QFont("Arial", 36, QFont.Weight.Bold))
            content_layout.addWidget(self.weight_label)

            self.final_weight_label = QLabel(self.tr("FINAL_WEIGHT").format("--"))
            self.final_weight_label.setFont(QFont("Arial", 18))
            self.final_weight_label.setStyleSheet("color: #fff;")
            content_layout.addWidget(self.final_weight_label)

            self.fill_time_label = QLabel(self.tr("FILL_TIME").format("--"))
            self.fill_time_label.setFont(QFont("Arial", 18))
            self.fill_time_label.setStyleSheet("color: #fff;")
            content_layout.addWidget(self.fill_time_label)

            if bar_on_left:
                main_layout.addWidget(self.progress_bar)
                main_layout.addLayout(content_layout)
            else:
                main_layout.addLayout(content_layout)
                main_layout.addWidget(self.progress_bar)
            self.setLayout(main_layout)
        else:
            offline_layout = QVBoxLayout(self)
            offline_layout.setContentsMargins(0, 0, 0, 0)
            offline_layout.setSpacing(0)
            self.offline_label = OutlinedLabel(self.tr("STATION_OFFLINE"))
            self.offline_label.setFont(QFont("Arial", 32, QFont.Weight.Bold))
            self.offline_label.setStyleSheet("color: #fff;")
            self.offline_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            offline_layout.addWidget(self.offline_label)
            self.setLayout(offline_layout)

    def set_weight(self, current_weight, target_weight, unit="g"):
        if self.weight_label is not None:
            if unit == "g":
                new_text = f"{int(round(current_weight))} / {int(round(target_weight))} g"
            else:  # "oz"
                # Convert grams to ounces (1 oz = 28.3495 g)
                current_oz = current_weight / 28.3495
                target_oz = target_weight / 28.3495
                new_text = f"{current_oz:.1f} / {target_oz:.1f} oz"
            if self.weight_label.text() != new_text:
                self.weight_label.setText(new_text)
        if self.progress_bar is not None:
            # Always use grams for the progress bar fill math
            self.progress_bar.set_max(target_weight)
            self.progress_bar.set_value(current_weight)

    def set_final_weight(self, value):
        if self.final_weight_label is not None:
            tr = self.tr if hasattr(self, "tr") else (
                self.parent().tr if self.parent() and hasattr(self.parent(), "tr") else (lambda k: LANGUAGES["en"].get(k, k))
            )
            self.final_weight_label.setText(self.tr("FINAL_WEIGHT").format(value))

    def set_fill_time(self, value):
        if self.fill_time_label is not None:
            tr = self.tr if hasattr(self, "tr") else (
                self.parent().tr if self.parent() and hasattr(self.parent(), "tr") else (lambda k: LANGUAGES["en"].get(k, k))
            )
            self.fill_time_label.setText(self.tr("FILL_TIME").format(value))

    def update_language(self):
        parent = self.parent()
        tr = parent.tr if parent and hasattr(parent, "tr") else (lambda k: LANGUAGES["en"].get(k, k))
        if self.final_weight_label is not None:
            self.final_weight_label.setText(tr("FINAL_WEIGHT").format("--"))
        if self.fill_time_label is not None:
            self.fill_time_label.setText(tr("FILL_TIME").format("--"))
        if self.offline_label is not None:
            self.offline_label.setText(tr("STATION_OFFLINE"))

class MenuDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        print("MenuDialog: __init__ called")
        self.selected_index = 0
        self.menu_keys = [
            "STATION STATUS",
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
        parent = self.parent()
        if selected_key == "EXIT":
            self.accept()
            # Do NOT call self.show_again() here
        elif selected_key == "STATION STATUS":
            self.hide()
            parent.station_status_dialog = StationStatusDialog(
                parent,
                station_enabled=getattr(parent, "station_enabled", None),
                bg_colors=getattr(parent, "bg_colors", None),
            )
            parent.active_dialog = parent.station_status_dialog
            parent.station_status_dialog.station_selected.connect(parent.handle_station_selected)  # Connect the signal
            parent.station_status_dialog.finished.connect(lambda: setattr(parent, "active_dialog", None))
            parent.station_status_dialog.show()
        elif selected_key == "SET TARGET WEIGHT":
            self.hide()
            parent.target_weight_dialog = SetTargetWeightDialog(parent)
            parent.active_dialog = parent.target_weight_dialog  # <-- Add this line!
            parent.target_weight_dialog.finished.connect(lambda: setattr(parent, "active_dialog", None))
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
            parent.active_dialog = parent.language_dialog  # <-- Make it the active dialog
            parent.language_dialog.finished.connect(lambda: setattr(parent, "active_dialog", None))  # <-- Reset on close
            parent.language_dialog.show()
        elif selected_key == "CHANGE UNITS":
            self.hide()
            parent.change_units_dialog = ChangeUnitsDialog(parent)
            parent.active_dialog = parent.change_units_dialog
            parent.change_units_dialog.finished.connect(lambda: setattr(parent, "active_dialog", None))  # <-- Add this line
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
        if DEBUG:
            print("MenuDialog: show() called")
        super().show()

    def update_menu_language(self):
        self.menu_items = [self.parent().tr(key) for key in self.menu_keys]
        for label, text in zip(self.labels, self.menu_items):
            label.setText(text)

class RelayControlApp(QWidget):
    def __init__(self, station_enabled=None):
        super().__init__()
        if DEBUG:
            print(f"[DEBUG] RelayControlApp.__init__ called with station_enabled={station_enabled}")
        self.setWindowTitle("Four Station Control")
        self.setStyleSheet("background-color: #222222;")

        # Define station colors
        self.bg_colors = STATION_COLORS

        # Example enabled state (replace with your actual config loading)
        if station_enabled is not None:
            if DEBUG:
                print("[DEBUG] Using provided station_enabled list.")
            self.station_enabled = station_enabled
        else:
            if DEBUG:
                print("[DEBUG] No station_enabled provided, defaulting to all False.")
            self.station_enabled = [False, False, False, False]

        # Main grid layout (2x2 for four stations)
        grid = QGridLayout()
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setSpacing(8)

        # Explicitly assign widgets to grid positions with color and opacity
        self.station_widgets = [None] * 4
        for i in range(4):
            widget = StationWidget(i + 1, self.bg_colors[i], enabled=self.station_enabled[i])
            # Set initial color with opacity based on enabled state
            if self.station_enabled[i]:
                color = self.bg_colors[i]
            else:
                # Convert hex to rgba with 25% opacity
                hex_color = self.bg_colors[i]
                if hex_color.startswith("#") and len(hex_color) == 7:
                    r = int(hex_color[1:3], 16)
                    g = int(hex_color[3:5], 16)
                    b = int(hex_color[5:7], 16)
                    color = f"rgba({r},{g},{b},0.25)"
                else:
                    color = "rgba(68,68,68,0.25)"
            widget.setStyleSheet(f"background-color: {color}; border: 2px solid #222;")
            self.station_widgets[i] = widget

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
        self.station_status_dialog = None

        self.setGeometry(
            QStyle.alignedRect(
                Qt.LayoutDirection.LeftToRight,
                Qt.AlignmentFlag.AlignCenter,
                self.size(),
                QApplication.primaryScreen().availableGeometry()
            )
        )
        self.setCursor(QCursor(Qt.CursorShape.BlankCursor))
        self.active_menu = None
        self.active_dialog = None

        # Overlay widget for messages
        self.overlay_widget = OverlayWidget(self)
        self.overlay_widget.resize(self.size())
        self.overlay_widget.hide()

    def show_menu(self):
        self.active_menu = "main_menu"
        if DEBUG:
            print("RelayControlApp: show_menu() called")
        if self.menu_dialog is None or not self.menu_dialog.isVisible():
            self.menu_dialog = MenuDialog(self)
            self.active_dialog = self.menu_dialog
            self.menu_dialog.finished.connect(lambda: setattr(self, "active_dialog", None))
            self.menu_dialog.show()

    def set_target_weight(self, value):
        self.target_weight = value
        for i, widget in enumerate(self.station_widgets):
            if widget.weight_label is not None and widget.weight_label.text() != "OFFLINE":
                current_weight = 0  # Or use actual current weight if available
                widget.set_weight(current_weight, self.target_weight, self.units)

    def set_time_limit(self, value):
        self.time_limit = value
        if DEBUG:
            print(f"[RelayControlApp] Time limit set to {value} ms")
        # Optionally update UI here

    def tr(self, key):
        lang = getattr(self, "language", "en")
        return LANGUAGES.get(lang, LANGUAGES["en"]).get(key, key)

    def set_language(self, lang_code):
        self.language = lang_code
        # Update menu dialog
        if self.menu_dialog is not None:
            self.menu_dialog.update_menu_language()
        # Update all station widgets
        for widget in self.station_widgets:
            widget.update_language()

    def show_info_dialog(self, title, message):
        dialog = InfoDialog(title, message, self)
        dialog.exec()

    def update_station_weight(self, station_index, weight):
        self.station_widgets[station_index].set_weight(weight, self.target_weight, self.units)
        # If CalibrationDialog is active, update its weight display too
        if hasattr(self, "active_dialog") and isinstance(self.active_dialog, CalibrationDialog):
            self.active_dialog.set_weight(station_index, weight)

    def refresh_ui(self):
        QApplication.processEvents()

    def update_station_states(self, station_enabled):
        if DEBUG:
            print(f"[update_station_states] station_enabled={station_enabled}")
        for i, widget in enumerate(self.station_widgets):
            if DEBUG:
                print(f"[update_station_states] Setting Station {i+1} active={station_enabled[i]}, color={self.bg_colors[i]}")
            widget.set_active(station_enabled[i], self.bg_colors[i])

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

    def handle_station_selected(self, station_index):
        if DEBUG:
            print(f"StationStatusDialog: Station {station_index+1} selected for (re)connect")
        # Call a function in main.py to attempt (re)connect
        try:
            from main import try_connect_station  # Import your connect function
            success = try_connect_station(station_index)
            if success:
                if DEBUG:
                    print(f"Station {station_index+1} connected and enabled.")
                self.station_enabled[station_index] = True
                self.update_station_states(self.station_enabled)
            else:
                if DEBUG:
                    print(f"Station {station_index+1} connection failed.")
        except Exception as e:
            if DEBUG:
                print(f"Error connecting to station {station_index+1}: {e}")

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

    def set_message(self, message):
        self.label.setText(message)

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

class BottleProgressBar(QWidget):
    def __init__(self, max_value=100, value=0, bar_color="#4FC3F7", parent=None):
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
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Bottle geometry
        margin = 8
        neck_width = rect.width() * 0.3
        body_width = rect.width() * 0.7
        neck_height = rect.height() * 0.05
        body_height = rect.height() - neck_height - margin
        corner_radius = body_width * 0.18  # Adjust for roundness

        neck_left = rect.center().x() - neck_width / 2
        neck_right = rect.center().x() + neck_width / 2
        body_left = rect.center().x() - body_width / 2
        body_right = rect.center().x() + body_width / 2

        bottle_path = QPainterPath()
        # Start at left neck
        bottle_path.moveTo(neck_left, margin)
        bottle_path.lineTo(neck_right, margin)
        bottle_path.lineTo(neck_right, neck_height + margin)

        # Top right arc (neck to body)
        bottle_path.arcTo(
            body_right - 2 * corner_radius, neck_height + margin,
            2 * corner_radius, 2 * corner_radius,
            90, -90
        )

        # Body right
        bottle_path.lineTo(body_right, neck_height + margin + corner_radius)
        bottle_path.lineTo(body_right, neck_height + body_height)

        # Bottom curve
        bottle_path.arcTo(
            body_left, neck_height + body_height - body_width / 2,
            body_width, body_width,
            0, -180
        )

        # Body left
        bottle_path.lineTo(body_left, neck_height + margin + corner_radius)

        # Top left arc (body to neck)
        bottle_path.arcTo(
            body_left, neck_height + margin,
            2 * corner_radius, 2 * corner_radius,
            180, -90
        )

        bottle_path.lineTo(neck_left, neck_height + margin)
        bottle_path.closeSubpath()

        # Draw outline
        painter.setPen(QPen(QColor("#fff"), 3))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(bottle_path)

        # Draw fill (water)
        if self.max_value > 0:
            fill_ratio = min(max(self.value / self.max_value, 0), 1)
        else:
            fill_ratio = 0
        fill_height = (body_height + neck_height) * fill_ratio
        fill_rect = QRectF(
            body_left + 3,
            neck_height + margin + body_height + neck_height - fill_height,
            body_width - 6,
            fill_height
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self.bar_color))
        painter.setClipPath(bottle_path)
        painter.drawRect(fill_rect)
        painter.setClipping(False)

class SetTargetWeightDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        tr = parent.tr if parent else (lambda k: LANGUAGES["en"].get(k, k))
        self.setWindowTitle(self.tr("SET_TARGET_WEIGHT"))
        layout = QVBoxLayout(self)
        label = QLabel(self.tr("ENTER_NEW_TARGET_WEIGHT"))
        layout.addWidget(label)

        # Start with parent's target_weight or 500, clamp to 5 digits
        initial = parent.target_weight if parent else 500
        initial = max(0, min(initial, 99999))
        digits = f"{int(initial):04d}"[-4:]  # Always 4 digits, initial as int

        self.digits = [int(d) for d in digits]
        self.current_digit = 0  # Start editing the leftmost digit

        # --- Add up arrows ---
        up_arrows_layout = QHBoxLayout()
        self.up_labels = []
        for i in range(4):
            up = QLabel("▲")
            up.setFont(QFont("Arial", 28, QFont.Weight.Bold))
            up.setAlignment(Qt.AlignmentFlag.AlignCenter)
            up.setFixedWidth(48)
            up.setStyleSheet("color: #fff;")  # <-- Make arrow white initially
            self.up_labels.append(up)
            up_arrows_layout.addWidget(up)
        layout.addLayout(up_arrows_layout)

        # --- Digits ---
        self.digit_labels = []
        digits_layout = QHBoxLayout()
        for i in range(4):
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
        for i in range(4):
            down = QLabel("▼")
            down.setFont(QFont("Arial", 28, QFont.Weight.Bold))
            down.setAlignment(Qt.AlignmentFlag.AlignCenter)
            down.setFixedWidth(48)
            down.setStyleSheet("color: #fff;")  # <-- Make arrow white initially
            self.down_labels.append(down)
            down_arrows_layout.addWidget(down)
        layout.addLayout(down_arrows_layout)

        self.setLayout(layout)
        self.setModal(True)
        self.update_display()

    def set_arrow_active(self, direction):
        if direction == "up":
            self.up_labels[self.current_digit].setStyleSheet("color: #00FF00;")
        elif direction == "down":
            self.down_labels[self.current_digit].setStyleSheet("color: #00FF00;")

    def set_arrow_inactive(self, direction):
        if direction == "up":
            self.up_labels[self.current_digit].setStyleSheet("color: #fff;")
        elif direction == "down":
            self.down_labels[self.current_digit].setStyleSheet("color: #fff;")

    def select_prev(self):
        # UP button should increment
        self.digits[self.current_digit] = (self.digits[self.current_digit] + 1) % 10
        self.update_display()

    def select_next(self):
        # DOWN button should decrement
        self.digits[self.current_digit] = (self.digits[self.current_digit] - 1) % 10
        self.update_display()

    def update_display(self):
        for i, lbl in enumerate(self.digit_labels):
            if i == self.current_digit:
                lbl.setStyleSheet("color: #F6EB61; border: 2px solid #F6EB61; border-radius: 8px; background: #222;")
            else:
                lbl.setStyleSheet("color: #fff; border: 2px solid transparent; background: #222;")
            lbl.setText(str(self.digits[i]))

    def activate_selected(self):
        if self.current_digit < 3:  # 4 digits, so index 0-3
            self.current_digit += 1
            self.update_display()
        else:
            value = int("".join(str(d) for d in self.digits))
            parent = self.parent()
            if parent and hasattr(parent, "set_target_weight"):
                parent.set_target_weight(value)
                # Show info dialog for 2 seconds
                if hasattr(parent, "show_timed_info"):
                    parent.show_timed_info("TARGET WEIGHT SAVED:", f"{value} g", timeout_ms=2000)
            self.accept()
            # Optionally, also close the menu dialog if you want to return to main screen:
            if parent and hasattr(parent, "menu_dialog") and parent.menu_dialog is not None:
                parent.menu_dialog.accept()

class SetTimeLimitDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        tr = parent.tr if parent else (lambda k: LANGUAGES["en"].get(k, k))
        self.setWindowTitle(self.tr("SET_TIME_LIMIT"))
        layout = QVBoxLayout(self)
        label = QLabel(self.tr("ENTER_NEW_TIME_LIMIT"))
        layout.addWidget(label)

        # Start with parent's time_limit or 3.0 seconds, clamp to 1 decimal
        initial = parent.time_limit if parent else 3000
        initial_tenths = int(round(initial / 100))  # tenths of a second

        # Always 4 digits: e.g. 0300 = 30.0s, 0015 = 1.5s
        digits = f"{initial_tenths:04d}"[-4:]
        self.digits = [int(d) for d in digits]
        self.current_digit = 0  # Start editing the leftmost digit

        # --- Add up arrows ---
        up_arrows_layout = QHBoxLayout()
        self.up_labels = []
        for i in range(4):
            up = QLabel("▲")
            up.setFont(QFont("Arial", 28, QFont.Weight.Bold))
            up.setAlignment(Qt.AlignmentFlag.AlignCenter)
            up.setFixedWidth(48)
            up.setStyleSheet("color: #fff;")
            self.up_labels.append(up)
            up_arrows_layout.addWidget(up)
            if i == 2:  # After the third arrow, add a spacer for the decimal point
                spacer = QSpacerItem(24, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
                up_arrows_layout.addItem(spacer)
        layout.addLayout(up_arrows_layout)

        # --- Digits ---
        self.digit_labels = []
        digits_layout = QHBoxLayout()
        for i in range(4):
            lbl = QLabel(str(self.digits[i]))
            lbl.setFont(QFont("Arial", 48, QFont.Weight.Bold))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setFixedWidth(48)
            self.digit_labels.append(lbl)
            digits_layout.addWidget(lbl)
            if i == 2:  # After the third digit, add the decimal point
                dot = QLabel(".")
                dot.setFont(QFont("Arial", 48, QFont.Weight.Bold))
                dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
                dot.setFixedWidth(24)
                dot.setStyleSheet("color: #fff;")
                digits_layout.addWidget(dot)
        layout.addLayout(digits_layout)

        # --- Add down arrows ---
        down_arrows_layout = QHBoxLayout()
        self.down_labels = []
        for i in range(4):
            down = QLabel("▼")
            down.setFont(QFont("Arial", 28, QFont.Weight.Bold))
            down.setAlignment(Qt.AlignmentFlag.AlignCenter)
            down.setFixedWidth(48)
            down.setStyleSheet("color: #fff;")
            self.down_labels.append(down)
            down_arrows_layout.addWidget(down)
            if i == 2:  # After the third arrow, add a spacer for the decimal point
                spacer = QSpacerItem(24, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
                down_arrows_layout.addItem(spacer)
        layout.addLayout(down_arrows_layout)

        self.setLayout(layout)
        self.setModal(True)
        self.update_display()

    def set_arrow_active(self, direction):
        if direction == "up":
            self.up_labels[self.current_digit].setStyleSheet("color: #00FF00;")
        elif direction == "down":
            self.down_labels[self.current_digit].setStyleSheet("color: #00FF00;")

    def set_arrow_inactive(self, direction):
        if direction == "up":
            self.up_labels[self.current_digit].setStyleSheet("color: #fff;")
        elif direction == "down":
            self.down_labels[self.current_digit].setStyleSheet("color: #fff;")

    def select_prev(self):
        self.digits[self.current_digit] = (self.digits[self.current_digit] + 1) % 10
        self.update_display()

    def select_next(self):
        self.digits[self.current_digit] = (self.digits[self.current_digit] - 1) % 10
        self.update_display()

    def update_display(self):
        for i, lbl in enumerate(self.digit_labels):
            if i == self.current_digit:
                lbl.setStyleSheet("color: #F6EB61; border: 2px solid #F6EB61; border-radius: 8px; background: #222;")
            else:
                lbl.setStyleSheet("color: #fff; border: 2px solid transparent; background: #222;")
            lbl.setText(str(self.digits[i]))

    def activate_selected(self):
        if self.current_digit < 3:  # 4 digits, so index 0-3
            self.current_digit += 1
            self.update_display()
        else:
            tenths = int("".join(str(d) for d in self.digits))
            value_ms = tenths * 100  # Convert tenths of a second to ms
            parent = self.parent()
            if parent and hasattr(parent, "set_time_limit"):
                parent.set_time_limit(value_ms)
                if hasattr(parent, "show_timed_info"):
                    seconds = tenths / 10.0
                    parent.show_timed_info("TIME LIMIT SAVED:", f"{seconds:.1f} sec", timeout_ms=2000)
            self.accept()
            if parent and hasattr(parent, "menu_dialog") and parent.menu_dialog is not None:
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
        super().__init__(options, parent, title=self.tr("SET_LANGUAGE_TITLE"), label_text=tr("CHOOSE_LANGUAGE"))
        self.parent_app = parent

    def on_select(self, lang_code):
        if self.parent_app:
            self.parent_app.set_language(lang_code)
        for widget in self.parent_app.station_widgets:
            widget.update_language()

class ChangeUnitsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        tr = parent.tr if parent else (lambda k: LANGUAGES["en"].get(k, k))
        self.setWindowTitle(self.tr("CHANGE_UNITS"))
        layout = QVBoxLayout(self)
        label = QLabel(self.tr("CHOOSE_UNITS"))
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

class StationStatusDialog(QDialog):
    station_selected = pyqtSignal(int)

    def __init__(self, parent=None, station_enabled=None, bg_colors=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setStyleSheet("""
            QDialog {
                background-color: #222;
                border: 6px solid white;
                border-radius: 24px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(24)

        # Use parent's station colors if not provided
        if bg_colors is None and parent and hasattr(parent, "bg_colors"):
            bg_colors = parent.bg_colors
        if station_enabled is None and parent and hasattr(parent, "station_enabled"):
            station_enabled = parent.station_enabled

        self.bg_colors = bg_colors
        self.station_enabled = station_enabled

        # Selection: 0-3 for stations, 4 for accept
        self.selected_index = 0
        self.num_stations = 4

        # Create frames and widgets
        self.station_frames = []
        self.station_boxes = []
        stations_layout = QHBoxLayout()
        stations_layout.setSpacing(24)
        for i in range(self.num_stations):
            box_widget = StationBoxWidget(
                station_index=i,
                name=f"Station {i+1}",
                color=bg_colors[i],
                connected=station_enabled[i],
                enabled=station_enabled[i],
                weight_text=None
            )
            self.station_boxes.append(box_widget)

            frame = QFrame()
            frame.setFrameShape(QFrame.Shape.StyledPanel)
            frame.setLineWidth(0)
            frame.setStyleSheet("border: 2px solid #444; border-radius: 14px; background: transparent;")
            frame.setLayout(QVBoxLayout())
            frame.layout().setContentsMargins(0, 0, 0, 0)
            frame.layout().setAlignment(Qt.AlignmentFlag.AlignCenter)
            frame.layout().addWidget(box_widget)
            frame.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            frame.setFixedSize(box_widget.width() + 8, box_widget.height() + 8)
            self.grid.addWidget(frame)
            self.station_frames.append(frame)
        layout.addLayout(stations_layout)

        # Accept button
        self.accept_label = QLabel("ACCEPT")
        self.accept_label.setFont(QFont("Arial", 28, QFont.Weight.Bold))
        self.accept_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.accept_label.setFixedWidth(220)
        accept_layout = QHBoxLayout()
        accept_layout.addWidget(self.accept_label)
        layout.addLayout(accept_layout)

        self.setLayout(layout)
        self.setModal(True)
        self.update_selection_box()

    def update_selection_box(self):
        # Highlight station frames
        for i, frame in enumerate(self.station_frames):
            if self.selected_index == i:
                frame.setStyleSheet("border: 4px solid #F6EB61; border-radius: 14px; background: transparent;")
            else:
                frame.setStyleSheet("border: 2px solid #444; border-radius: 14px; background: transparent;")
        # Highlight accept button
        if self.selected_index == self.num_stations:
            self.accept_label.setStyleSheet("color: #F6EB61; border: 4px solid #F6EB61; border-radius: 12px;")
        else:
            self.accept_label.setStyleSheet("color: #fff; border: 4px solid transparent; border-radius: 12px;")

    def select_prev(self):
        self.selected_index = (self.selected_index - 1) % (self.num_stations + 1)
        self.update_selection_box()

    def select_next(self):
        self.selected_index = (self.selected_index + 1) % (self.num_stations + 1)
        self.update_selection_box()

    def activate_selected(self):
        if self.selected_index == self.num_stations:
            self.accept()
        else:
            self.station_selected.emit(self.selected_index)

class OverlayWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setStyleSheet("background: rgba(0,0,0,180);")
        self.label = QLabel("", self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("color: #fff; font-size: 64px; font-weight: bold;")
        layout = QVBoxLayout(self)
        layout.addWidget(self.label)
        self.setLayout(layout)
        self.hide()

    def show_overlay(self, html, color="#CD0A0A"):
        self.label.setText(html)
        self.label.setStyleSheet(f"color: #fff; font-size: 64px; font-weight: bold; background: transparent;")
        self.setStyleSheet(f"background: rgba(0,0,0,180); border: 8px solid {color}; border-radius: 32px;")
        self.resize(self.parent().size())
        self.move(0, 0)
        self.show()
        self.raise_()

    def hide_overlay(self):
        self.hide()

class StartupDialog(QDialog):
    def __init__(self, message, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.setStyleSheet("background-color: #222; color: #fff;")
        self.station_names = []
        self.statuses = []
        self.colors = []
        self.station_connected = []
        self.selection_indices = []
        self.selected_index = 0

        self.layout = QVBoxLayout(self)
        self.label = QLabel(message)
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        self.layout.addWidget(self.label)

        # StationBoxWidgets for each station, each inside a QFrame
        self.station_boxes = []
        self.station_frames = []
        self.grid = QHBoxLayout()
        self.grid.setSpacing(24)
        for i in range(4):
            box_widget = StationBoxWidget(
                station_index=i,
                name=f"Station {i+1}",
                color=STATION_COLORS[i],
                connected=False,
                enabled=False,
                weight_text=None
            )
            self.station_boxes.append(box_widget)

            frame = QFrame()
            frame.setFrameShape(QFrame.Shape.StyledPanel)
            frame.setLineWidth(0)
            frame.setStyleSheet("border: 2px solid #444; border-radius: 14px; background: transparent;")
            frame.setLayout(QVBoxLayout())
            frame.layout().setContentsMargins(0, 0, 0, 0)
            frame.layout().setAlignment(Qt.AlignmentFlag.AlignCenter)
            frame.layout().addWidget(box_widget)
            frame.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            frame.setFixedSize(box_widget.width() + 8, box_widget.height() + 8)
            self.grid.addWidget(frame)
            self.station_frames.append(frame)
        self.layout.addLayout(self.grid)

        # Accept button
        self.accept_label = QLabel("ACCEPT")
        self.accept_label.setFont(QFont("Arial", 28, QFont.Weight.Bold))
        self.accept_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.accept_label.setFixedWidth(220)
        accept_layout = QHBoxLayout()
        accept_layout.addWidget(self.accept_label)
        self.layout.addLayout(accept_layout)

        self.setLayout(self.layout)

    def show_station_verification(self, station_names, statuses, colors, station_connected=None):
        self.station_names = station_names
        self.statuses = statuses
        self.colors = colors
        if station_connected is not None:
            self.station_connected = station_connected

        # Build selection_indices: all connected stations + "accept" at the end
        self.selection_indices = [i for i, c in enumerate(self.station_connected) if c]
        self.selection_indices.append("accept")
        if self.selected_index >= len(self.selection_indices):
            self.selected_index = 0

        # Update each StationBoxWidget and its frame
        for i, (box_widget, frame) in enumerate(zip(self.station_boxes, self.station_frames)):
            # Name and color
            name = self.station_names[i] if i < len(self.station_names) else f"Station {i+1}"
            color = self.colors[i] if i < len(self.colors) else "#444"
            is_connected = self.station_connected[i] if self.station_connected and i < len(self.station_connected) else False
            is_enabled = False
            if i < len(self.statuses):
                status = self.statuses[i]
                is_enabled = "ENABLED" in status

            # Update name label
            box_widget.name_label.setText(name)
            box_widget.name_label.setStyleSheet(
                f"background: {color}; color: #fff; border-radius: 8px; padding: 4px;"
            )

            # Update connected label
            if box_widget.connected_label is not None:
                box_widget.connected_label.setText("CONNECTED" if is_connected else "DISCONNECTED")
                box_widget.connected_label.setStyleSheet(
                    f"background: {color if is_connected else '#000'}; color: #fff; border-radius: 8px; padding: 4px;"
                )
            else:
                connected_label = QLabel("CONNECTED" if is_connected else "DISCONNECTED")
                connected_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                connected_label.setFont(QFont("Arial", 16))
                connected_label.setStyleSheet(
                    f"background: {color if is_connected else '#000'}; color: #fff; border-radius: 8px; padding: 4px;"
                )
                box_widget.layout().insertWidget(1, connected_label)
                box_widget.connected_label = connected_label

            # Update enabled label
            if box_widget.enabled_label is not None:
                box_widget.enabled_label.setText("ENABLED" if is_enabled else "DISABLED")
                box_widget.enabled_label.setStyleSheet(
                    f"background: {color if is_enabled else '#000'}; color: #fff; border-radius: 8px; padding: 4px;"
                )
            else:
                enabled_label = QLabel("ENABLED" if is_enabled else "DISABLED")
                enabled_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                enabled_label.setFont(QFont("Arial", 16))
                enabled_label.setStyleSheet(
                    f"background: {color if is_enabled else '#000'}; color: #fff; border-radius: 8px; padding: 4px;"
                )
                box_widget.layout().insertWidget(2, enabled_label)
                box_widget.enabled_label = enabled_label

            # Highlight selection (frame border)
            if self.selection_indices[self.selected_index] == i:
                border = "6px solid #F6EB61"
            else:
                border = "2px solid #444"
            frame.setStyleSheet(
                f"border: {border}; border-radius: 14px; background: transparent;"
            )

        # Accept button highlight
        if self.selection_indices[self.selected_index] == "accept":
            self.accept_label.setStyleSheet("color: #F6EB61; border: 4px solid #F6EB61; border-radius: 12px;")
        else:
            self.accept_label.setStyleSheet("color: #fff; border: 4px solid transparent; border-radius: 12px;")

    def select_prev(self):
        self.selected_index = (self.selected_index - 1) % len(self.selection_indices)
        self.show_station_verification(self.station_names, self.statuses, self.colors, self.station_connected)

    def select_next(self):
        self.selected_index = (self.selected_index + 1) % len(self.selection_indices)
        self.show_station_verification(self.station_names, self.statuses, self.colors, self.station_connected)

    def activate_selected(self):
        sel = self.selection_indices[self.selected_index]
        parent = self.parent()
        if sel == "accept":
            self.accept()
        else:
            if self.station_connected[sel]:
                if hasattr(parent, "station_enabled") and hasattr(parent, "save_station_enabled"):
                    parent.station_enabled[sel] = not parent.station_enabled[sel]
                    parent.save_station_enabled(parent.config_file, parent.station_enabled)
                    # Update statuses/colors for UI
                    statuses = []
                    for i in range(len(parent.station_enabled)):
                        if parent.station_enabled[i] and parent.station_connected[i]:
                            statuses.append("ENABLED & CONNECTED")
                        elif parent.station_enabled[i] and not parent.station_connected[i]:
                            statuses.append("ENABLED & DISCONNECTED")
                        elif not parent.station_enabled[i] and parent.station_connected[i]:
                            statuses.append("DISABLED & CONNECTED")
                        else:
                            statuses.append("DISABLED & DISCONNECTED")
                    self.statuses = statuses
                    self.show_station_verification(self.station_names, self.statuses, self.colors, self.station_connected)
                    message = "Station {} is now {}".format(
                        sel + 1,
                        "ENABLED" if parent.station_enabled[sel] else "DISABLED"
                    )
                    if hasattr(parent, "show_timed_info"):
                        parent.show_timed_info("STATION STATUS", message, timeout_ms=2000)

class FillingModeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.setStyleSheet("background-color: #222; color: #fff;")
        layout = QVBoxLayout(self)
        label = QLabel("SELECT FILLING MODE")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        layout.addWidget(label)

        self.options = ["AUTO", "MANUAL", "SMART"]
        self.selected_index = 0
        self.labels = []
        for opt in self.options:
            opt_label = QLabel(opt)
            opt_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            opt_label.setFont(QFont("Arial", 28, QFont.Weight.Bold))
            opt_label.setFixedHeight(64)
            self.labels.append(opt_label)
            layout.addWidget(opt_label)
        self.setLayout(layout)
        self.update_selection_box()

    def update_selection_box(self):
        for i, label in enumerate(self.labels):
            if i == self.selected_index:
                label.setStyleSheet("color: #F6EB61; border: 4px solid #F6EB61; border-radius: 12px; background: #333;")
            else:
                label.setStyleSheet("color: #fff; border: 4px solid transparent; border-radius: 12px; background: #222;")

    def select_next(self):
        self.selected_index = (self.selected_index + 1) % len(self.labels)
        self.update_selection_box()

    def select_prev(self):
        self.selected_index = (self.selected_index - 1) % len(self.labels)
        self.update_selection_box()

    def activate_selected(self):
        print(f"[DEBUG] activate_selected called with index {self.selected_index}")
        self.done(self.selected_index)

class CalibrationDialog(QDialog):
    def __init__(self, station_enabled, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.setStyleSheet("background-color: #222; color: #fff;")
        layout = QVBoxLayout(self)

        # Large label (main instruction)
        self.main_label = QLabel("CALIBRATION")
        self.main_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_label.setFont(QFont("Arial", 32, QFont.Weight.Bold))
        layout.addWidget(self.main_label)

        # Smaller label (sub-instruction)
        self.sub_label = QLabel("Follow the instructions to calibrate each station.")
        self.sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sub_label.setFont(QFont("Arial", 20))
        layout.addWidget(self.sub_label)

        # Four StationBoxWidgets inside QFrames
        self.weight_labels = []
        self.station_boxes = []
        weights_layout = QHBoxLayout()
        weights_layout.setSpacing(24)
        for i in range(4):
            box_widget = StationBoxWidget(
                station_index=i,
                name=f"Station {i+1}",
                color=STATION_COLORS[i],
                enabled=station_enabled[i],
                weight_text="--" if not station_enabled[i] else "0.0 g"
            )
            self.station_boxes.append(box_widget)
            self.weight_labels.append(box_widget.weight_label)

            frame = QFrame()
            frame.setFrameShape(QFrame.Shape.StyledPanel)
            frame.setLineWidth(0)
            frame.setStyleSheet("border: 2px solid #444; border-radius: 14px; background: transparent;")
            frame.setLayout(QVBoxLayout())
            frame.layout().setContentsMargins(0, 0, 0, 0)
            frame.layout().setAlignment(Qt.AlignmentFlag.AlignCenter)
            frame.layout().addWidget(box_widget)
            frame.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            frame.setFixedSize(box_widget.width() + 8, box_widget.height() + 8)
            weights_layout.addWidget(frame)
        layout.addLayout(weights_layout)

        # Bottom label (status or instruction)
        self.bottom_label = QLabel("Press SELECT to continue when ready.")
        self.bottom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bottom_label.setFont(QFont("Arial", 18))
        layout.addWidget(self.bottom_label)

        self.setLayout(layout)

    def set_main_label(self, text):
        self.main_label.setText(text)

    def set_sub_label(self, text):
        self.sub_label.setText(text)

    def set_weight(self, station_index, weight, color=None):
        """Update the weight label and optionally its color."""
        if 0 <= station_index < len(self.weight_labels):
            self.weight_labels[station_index].setText(f"{weight:.1f} g")
            if color:
                self.weight_labels[station_index].setStyleSheet(f"color: {color};")
            # Otherwise, main.py can set the color as needed

    def set_bottom_label(self, text):
        self.bottom_label.setText(text)

    def select_prev(self):
        self.done(1)  # Continue to next step

    def select_next(self):
        self.done(1)  # Continue to next step

    def activate_selected(self):
        self.done(1)  # Continue to next step

    def showEvent(self, event):
        super().showEvent(event)
        self.showFullScreen()

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
    def show_test_menu():
        menu = TestableMenuDialog(self)