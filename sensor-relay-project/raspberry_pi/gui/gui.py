from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QGridLayout, QVBoxLayout, QSizePolicy, QDialog, QPushButton, QHBoxLayout, QStyle, QSpacerItem, QFrame
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRectF
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QPainterPath, QPixmap, QCursor, QFontMetrics  # <-- Add QFontMetrics here
import sys
import logging
import os
import weakref
from gui.languages import LANGUAGES
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app_config import DEBUG

logging.basicConfig(level=logging.INFO)

STATION_COLORS = [
    "#CB1212",  # Station 1: Red
    "#2E4BA8",  # Station 2: Blue
    "#3f922e",  # Station 3: Green
    "#EDE021",  # Station 4: Yellow
]


def qt_exception_hook(exctype, value, traceback):
    logging.error("Uncaught Qt exception", exc_info=(exctype, value, traceback))
    print("Uncaught Qt exception:", value)

sys.excepthook = qt_exception_hook

class OutlinedLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def paintEvent(self, event):
        try:
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
        except Exception as e:
            logging.error(f"Error in OutlinedLabel.paintEvent: {e}", exc_info=True)

class StationBoxWidget(QWidget):
    def __init__(self, station_index, name, color, connected=None, enabled=None, weight_text=None, parent=None):
        try:
            super().__init__(parent)
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(4)

            tr = parent.tr if parent and hasattr(parent, "tr") else (lambda k: LANGUAGES["en"].get(k, k))

            # Station name label with outline
            self.name_label = OutlinedLabel(name)
            self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.name_label.setFont(QFont("Arial", 24, QFont.Weight.Bold))
            self.name_label.setStyleSheet("background: transparent; padding: 4px;")
            layout.addWidget(self.name_label)

            # Connected/Enabled labels (optional)
            if connected is not None:
                self.connected_label = QLabel(tr("CONNECTED") if connected else tr("DISCONNECTED"))
                self.connected_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.connected_label.setFont(QFont("Arial", 16))
                self.connected_label.setStyleSheet(f"background: {color if connected else '#000'}; color: #fff; border-radius: 8px; border: none; padding: 4px;")
                layout.addWidget(self.connected_label)
            else:
                self.connected_label = None

            if enabled is not None:
                self.enabled_label = QLabel(tr("ENABLED") if enabled else tr("DISABLED"))
                self.enabled_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.enabled_label.setFont(QFont("Arial", 16))
                self.enabled_label.setStyleSheet(f"background: {color if enabled else '#000'}; color: #fff; border-radius: 8px; border: none; padding: 4px;")
                layout.addWidget(self.enabled_label)
            else:
                self.enabled_label = None

            # Weight label (optional, for calibration)
            if weight_text is not None:
                self.weight_label = QLabel(weight_text)
            else:
                self.weight_label = QLabel("--")
            self.weight_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.weight_label.setFont(QFont("Arial", 24, QFont.Weight.Bold))
            self.weight_label.setStyleSheet("color: #0f0; border: none;" if enabled else "color: #888; border: none;")
            layout.addWidget(self.weight_label)

            self.setFixedSize(216, 140)
        except Exception as e:
            logging.error(f"Error in StationBoxWidget.__init__ (station_index={station_index}, name={name}): {e}", exc_info=True)

class StationWidget(QWidget):
    def __init__(self, station_number, bg_color, enabled=True, *args, **kwargs):
        try:
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
            self.status_label = None
            self.progress_bar = None
            self.offline_label = None

            # Flashing status attributes
            self._status_flash_timer = None
            self._status_flash_state = False
            self._status_flash_color = "#FF2222"
            self._status_flash_text = ""
            self._status_flash_interval = 500  # ms

            if enabled:
                main_layout = QHBoxLayout(self)
                main_layout.setContentsMargins(0, 0, 0, 0)
                main_layout.setSpacing(0)

                bar_on_left = station_number in (1, 2)
                self.progress_bar = BottleProgressBar(max_value=100, value=0, bar_color="#4FC3F7")
                self.progress_bar.setFixedWidth(64)
                self.progress_bar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

                content_layout = QVBoxLayout()
                content_layout.setContentsMargins(0, 0, 0, 0)
                content_layout.setSpacing(0)

                # Large weight label
                self.weight_label = OutlinedLabel("0.0 / 0.0 g")
                self.weight_label.setFont(QFont("Arial", 64, QFont.Weight.Bold))
                self.weight_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                content_layout.addWidget(self.weight_label, stretch=2)  # 67%

                # Status label (smaller, below weight)
                self.status_label = QLabel(self.tr("READY"))
                self.status_label.setFont(QFont("Arial", 20))
                self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.status_label.setStyleSheet("color: #fff;")
                content_layout.addWidget(self.status_label, stretch=1)  # 33%

                # Add widgets to layout
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
        except Exception as e:
            logging.error(f"Error in StationWidget.__init__ (station_number={station_number}): {e}", exc_info=True)

    def set_weight(self, current_weight, target_weight, unit="g"):
        try:
            if self.weight_label is not None:
                if unit == "g":
                    new_text = f"{int(round(current_weight))} / {int(round(target_weight))} g"
                else:  # "oz"
                    current_oz = current_weight / 28.3495
                    target_oz = target_weight / 28.3495
                    new_text = f"{current_oz:.1f} / {target_oz:.1f} oz"
                if self.weight_label.text() != new_text:
                    self.weight_label.setText(new_text)
                    self.adjust_weight_label_font()
            if self.progress_bar is not None:
                self.progress_bar.set_max(target_weight)
                self.progress_bar.set_value(current_weight)
        except Exception as e:
            logging.error(f"Error in StationWidget.set_weight (station_number={getattr(self, 'station_number', '?')}): {e}", exc_info=True)

    def resizeEvent(self, event):
        try:
            super().resizeEvent(event)
            self.adjust_weight_label_font()
        except Exception as e:
            logging.error(f"Error in StationWidget.resizeEvent (station_number={getattr(self, 'station_number', '?')}): {e}", exc_info=True)

    def adjust_weight_label_font(self):
        try:
            if not self.weight_label:
                return
            label = self.weight_label
            rect = label.contentsRect()
            text = label.text()
            if not text:
                return
            font = label.font()
            min_size = 10
            max_size = 100
            step = 2
            for size in range(max_size, min_size, -step):
                font.setPointSize(size)
                metrics = QFontMetrics(font)
                text_width = metrics.horizontalAdvance(text)
                text_height = metrics.height()
                if text_width <= rect.width() - 8 and text_height <= rect.height() - 8:
                    label.setFont(font)
                    break
            else:
                font.setPointSize(min_size)
                label.setFont(font)
        except Exception as e:
            logging.error(f"Error in StationWidget.adjust_weight_label_font (station_number={getattr(self, 'station_number', '?')}): {e}", exc_info=True)

    def set_status(self, text, color="#fff"):
        try:
            if self.status_label is not None:
                print(f"set_status called: {text}")
                self.status_label.setText(text)
                self.status_label.setStyleSheet(f"color: {color};")
        except Exception as e:
            logging.error(f"Error in StationWidget.set_status (station_number={getattr(self, 'station_number', '?')}): {e}", exc_info=True)

    def _toggle_status_flash(self):
        try:
            if self.status_label is None:
                return
            self._status_flash_state = not self._status_flash_state
            if self._status_flash_state:
                self.status_label.setText(self._status_flash_text)
                self.status_label.setStyleSheet(f"color: {self._status_flash_color};")
            else:
                self.status_label.setText("")
                self.status_label.setStyleSheet("color: #fff;")
        except Exception as e:
            logging.error(f"Error in StationWidget._toggle_status_flash (station_number={getattr(self, 'station_number', '?')}): {e}", exc_info=True)

    def clear_status(self):
        try:
            if self._status_flash_timer and self._status_flash_timer.isActive():
                self._status_flash_timer.stop()
            if self.status_label is not None:
                self.status_label.setText("")
                self.status_label.setStyleSheet("color: #fff;")
        except Exception as e:
            logging.error(f"Error in StationWidget.clear_status (station_number={getattr(self, 'station_number', '?')}): {e}", exc_info=True)

    def update_language(self):
        try:
            parent = self.parent()
            tr = parent.tr if parent and hasattr(parent, "tr") else (lambda k: LANGUAGES["en"].get(k, k))
            if self.offline_label is not None:
                self.offline_label.setText(tr("STATION_OFFLINE"))
        except Exception as e:
            logging.error(f"Error in StationWidget.update_language (station_number={getattr(self, 'station_number', '?')}): {e}", exc_info=True)

class MenuDialog(QDialog):
    def __init__(self, parent=None):
        try:
            super().__init__(parent)
            print("MenuDialog: __init__ called")
            self.selected_index = 0
            self.menu_keys = [
                # "STATION STATUS",
                "SET TARGET WEIGHT",
                "SET TIME LIMIT",
                "SET LANGUAGE",
                "CHANGE UNITS",
                "SET FILLING MODE",
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
        except Exception as e:
            logging.error(f"Error in MenuDialog.__init__: {e}", exc_info=True)

    def update_selection_box(self):
        try:
            for i, label in enumerate(self.labels):
                if i == self.selected_index:
                    label.setStyleSheet(
                        "font-size: 24px; border: 4px solid #F6EB61; border-radius: 16px; background: transparent;"
                    )
                else:
                    label.setStyleSheet(
                        "font-size: 24px; border: 4px solid transparent; border-radius: 16px; background: transparent;"
                    )
        except Exception as e:
            logging.error(f"Error in MenuDialog.update_selection_box: {e}", exc_info=True)

    def select_next(self):
        try:
            self.selected_index = (self.selected_index + 1) % len(self.labels)
            self.update_selection_box()
        except Exception as e:
            logging.error(f"Error in MenuDialog.select_next: {e}", exc_info=True)

    def select_prev(self):
        try:
            self.selected_index = (self.selected_index - 1) % len(self.labels)
            self.update_selection_box()
        except Exception as e:
            logging.error(f"Error in MenuDialog.select_prev: {e}", exc_info=True)

    def activate_selected(self):
        try:
            selected_key = self.menu_keys[self.selected_index]
            parent = self.parent()
            print(f"[MenuDialog] activate_selected: {selected_key}")
            if selected_key == "EXIT":
                print("[MenuDialog] Exiting menu.")
                self.accept()
            elif selected_key == "STATION STATUS":
                print("[MenuDialog] Opening Station Status Dialog.")
                self.hide()
                parent.station_status_dialog = StationStatusDialog(
                    parent,
                    station_enabled=getattr(parent, "station_enabled", None),
                    bg_colors=getattr(parent, "bg_colors", None),
                )
                parent.active_dialog = parent.station_status_dialog
                parent.station_status_dialog.station_selected.connect(parent.handle_station_selected)
                parent.station_status_dialog.finished.connect(lambda: setattr(parent, "active_dialog", None))
                parent.station_status_dialog.show()
            elif selected_key == "SET TARGET WEIGHT":
                print("[MenuDialog] Opening Set Target Weight Dialog.")
                self.hide()
                parent.target_weight_dialog = SetTargetWeightDialog(parent)
                parent.active_dialog = parent.target_weight_dialog
                parent.target_weight_dialog.finished.connect(lambda: setattr(parent, "active_dialog", None))
                parent.target_weight_dialog.finished.connect(self.show_again)
                parent.target_weight_dialog.show()
            elif selected_key == "SET TIME LIMIT":
                print("[MenuDialog] Opening Set Time Limit Dialog.")
                self.hide()
                parent.time_limit_dialog = SetTimeLimitDialog(parent)
                parent.active_dialog = parent.time_limit_dialog
                parent.time_limit_dialog.finished.connect(lambda: setattr(parent, "active_dialog", None))
                parent.time_limit_dialog.show()
            elif selected_key == "SET LANGUAGE":
                print("[MenuDialog] Opening Language Dialog.")
                self.hide()
                parent.language_dialog = SelectionDialog(
                    options=[("en", parent.tr("English")), ("es", parent.tr("Español"))],
                    parent=parent,
                    title=parent.tr("SET LANGUAGE"),
                    on_select=parent.set_language
                )
                parent.active_dialog = parent.language_dialog
                parent.language_dialog.finished.connect(lambda: setattr(parent, "active_dialog", None))
                parent.language_dialog.show()
            elif selected_key == "CHANGE UNITS":
                print("[MenuDialog] Opening Units Dialog.")
                self.hide()
                parent.change_units_dialog = SelectionDialog(
                    options=[("g", parent.tr("Grams")), ("oz", parent.tr("Ounces"))],
                    parent=parent,
                    title=parent.tr("CHANGE UNITS"),
                    on_select=parent.set_units
                )
                parent.active_dialog = parent.change_units_dialog
                parent.change_units_dialog.finished.connect(lambda: setattr(parent, "active_dialog", None))
                parent.change_units_dialog.show()
            elif selected_key == "SET FILLING MODE":
                print("[MenuDialog] Opening Filling Mode Dialog.")
                self.hide()
                parent.open_filling_mode_dialog()
        except Exception as e:
            logging.error(f"Error in MenuDialog.activate_selected: {e}", exc_info=True)

    def show_again(self):
        try:
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
        except Exception as e:
            logging.error(f"Error in MenuDialog.show_again: {e}", exc_info=True)

    def update_colors(self, color_scheme):
        try:
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
        except Exception as e:
            logging.error(f"Error in MenuDialog.update_colors: {e}", exc_info=True)

    def show(self):
        try:
            if DEBUG:
                print("MenuDialog: show() called")
            super().show()
        except Exception as e:
            logging.error(f"Error in MenuDialog.show: {e}", exc_info=True)

    def update_menu_language(self):
        try:
            self.menu_items = [self.parent().tr(key) for key in self.menu_keys]
            for label, text in zip(self.labels, self.menu_items):
                label.setText(text)
        except Exception as e:
            logging.error(f"Error in MenuDialog.update_menu_language: {e}", exc_info=True)

class RelayControlApp(QWidget):
    def __init__(self, station_enabled=None, filling_mode_callback=None):
        try:
            super().__init__()
            self.filling_mode_callback = filling_mode_callback
            if DEBUG:
                print(f"[DEBUG] RelayControlApp.__init__ called with station_enabled={station_enabled}")
            else:
                logging.info(f"RelayControlApp.__init__ called with station_enabled={station_enabled}")
            self.setWindowTitle("Four Station Control")
            self.setStyleSheet("background-color: #222222;")
            self.setFixedSize(1024, 600)  # Ensure window fits screen exactly

            # Define station colors
            self.bg_colors = STATION_COLORS

            # Enabled state
            if station_enabled is not None:
                self.station_enabled = station_enabled
            else:
                self.station_enabled = [False, False, False, False]

            # --- Main grid layout (2x2 for four stations) ---
            grid = QGridLayout()
            grid.setContentsMargins(8, 8, 8, 8)
            grid.setSpacing(8)
            self.station_widgets = [None] * 4
            for i in range(4):
                widget = StationWidget(i + 1, self.bg_colors[i], enabled=self.station_enabled[i])
                widget.setFixedSize(475, 280)  # Each station widget fixed size
                # Set initial color with opacity based on enabled state
                if self.station_enabled[i]:
                    color = self.bg_colors[i]
                else:
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
            grid.addWidget(self.station_widgets[0], 0, 0)
            grid.addWidget(self.station_widgets[1], 1, 0)
            grid.addWidget(self.station_widgets[2], 0, 1)
            grid.addWidget(self.station_widgets[3], 1, 1)

            # --- Right-side column for button labels ---
            self.button_column = ButtonColumnWidget(
                icons=["▲", "⏎", "▼"],
                font_size=32,
                fixed_width=64,
                margins=(0, 30, 0, 0),
                spacing=50,
                parent=self
            )
            main_layout = QHBoxLayout(self)
            main_layout.setContentsMargins(0, 0, 0, 0)
            main_layout.setSpacing(0)
            main_layout.addLayout(grid, stretch=1)
            main_layout.addWidget(self.button_column, stretch=0)
            self.setLayout(main_layout)

            # Borderless fullscreen for kiosk mode
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
            self.setGeometry(0, 0, 1024, 600)
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

            self.setCursor(QCursor(Qt.CursorShape.BlankCursor))
            self.active_menu = None
            self.active_dialog = None

            # Overlay widget for messages
            self.overlay_widget = OverlayWidget(self)
            self.overlay_widget.resize(self.size())
            self.overlay_widget.hide()

            # Arduino serial ports (example initialization)
            self.arduino_ports = []
        except Exception as e:
            logging.error(f"Error in RelayControlApp.__init__: {e}", exc_info=True)

    def show_menu(self):
        try:
            self.active_menu = "main_menu"
            if DEBUG:
                print("RelayControlApp: show_menu() called")
            else:
                logging.info("RelayControlApp: show_menu() called")
            if self.menu_dialog is None or not self.menu_dialog.isVisible():
                self.menu_dialog = MenuDialog(self)
                self.active_dialog = self.menu_dialog
                self.menu_dialog.finished.connect(lambda: setattr(self, "active_dialog", None))
                self.menu_dialog.show()
        except Exception as e:
            logging.error(f"Error in RelayControlApp.show_menu: {e}", exc_info=True)

    def set_target_weight(self, value):
        try:
            self.target_weight = value
            for i, widget in enumerate(self.station_widgets):
                if widget.weight_label is not None:
                    current_weight = 0  # Or use actual current weight if available
                    widget.set_weight(current_weight, self.target_weight, self.units)
        except Exception as e:
            logging.error(f"Error in RelayControlApp.set_target_weight: {e}", exc_info=True)

    def set_time_limit(self, value):
        try:
            self.time_limit = value
            if DEBUG:
                print(f"[RelayControlApp] Time limit set to {value} ms")
            else:
                logging.info(f"Time limit set to {value} ms")
            # Optionally update UI here
        except Exception as e:
            logging.error(f"Error in RelayControlApp.set_time_limit: {e}", exc_info=True)

    def tr(self, key):
        try:
            lang = getattr(self, "language", "en")
            return LANGUAGES.get(lang, LANGUAGES["en"]).get(key, key)
        except Exception as e:
            logging.error(f"Error in RelayControlApp.tr: {e}", exc_info=True)
            return key

    def set_language(self, lang_code):
        try:
            self.language = lang_code
            # Update menu dialog
            if self.menu_dialog is not None:
                self.menu_dialog.update_menu_language()
            # Update all station widgets
            for widget in self.station_widgets:
                widget.update_language()
        except Exception as e:
            logging.error(f"Error in RelayControlApp.set_language: {e}", exc_info=True)

    def show_info_dialog(self, title, message):
        try:
            dialog = InfoDialog(title, message, self)
            dialog.exec()
        except Exception as e:
            logging.error(f"Error in RelayControlApp.show_info_dialog: {e}", exc_info=True)

    def update_station_weight(self, station_index, weight):
        try:
            self.station_widgets[station_index].set_weight(weight, self.target_weight, self.units)
            # If CalibrationDialog is active, update its weight display too
            if hasattr(self, "active_dialog") and isinstance(self.active_dialog, CalibrationDialog):
                self.active_dialog.set_weight(station_index, weight)
        except Exception as e:
            logging.error(f"Error in RelayControlApp.update_station_weight: {e}", exc_info=True)

    def refresh_ui(self):
        try:
            QApplication.processEvents()
        except Exception as e:
            logging.error(f"Error in RelayControlApp.refresh_ui: {e}", exc_info=True)

    def update_station_states(self, station_enabled):
        try:
            if DEBUG:
                print(f"[update_station_states] station_enabled={station_enabled}")
            else:
                logging.info(f"[update_station_states] station_enabled={station_enabled}")
            for i, widget in enumerate(self.station_widgets):
                if DEBUG:
                    print(f"[update_station_states] Setting Station {i+1} active={station_enabled[i]}, color={self.bg_colors[i]}")
                else:
                    logging.info(f"[update_station_states] Setting Station {i+1} active={station_enabled[i]}, color={self.bg_colors[i]}")
                widget.set_active(station_enabled[i], self.bg_colors[i])
        except Exception as e:
            logging.error(f"Error in RelayControlApp.update_station_states: {e}", exc_info=True)

    def set_units(self, units):
        try:
            self.units = units
            # Refresh all station widgets to update display
            for i, widget in enumerate(self.station_widgets):
                current_weight = 0
                widget.set_weight(current_weight, self.target_weight, self.units)
        except Exception as e:
            logging.error(f"Error in RelayControlApp.set_units: {e}", exc_info=True)

    def open_units_dialog(self):
        try:
            if DEBUG:
                print("[RelayControlApp] open_units_dialog called")
            else:
                logging.info("open_units_dialog called")
            dlg = SelectionDialog(
                options=[("g", self.tr("Grams")), ("oz", self.tr("Ounces"))],
                parent=self,
                title=self.tr("CHANGE UNITS"),
                on_select=self.set_units
            )
            self.active_dialog = dlg
            if DEBUG:
                print(f"[RelayControlApp] active_dialog set to: {dlg}")
            else:
                logging.info(f"active_dialog set to: {dlg}")
            dlg.finished.connect(lambda: setattr(self, "active_dialog", None))
            dlg.show()
        except Exception as e:
            logging.error("Error in open_units_dialog", exc_info=True)
            self.show_timed_info(self.tr("ERROR"), f"Failed to open units dialog: {e}", timeout_ms=2000)

    def open_language_dialog(self):
        try:
            if DEBUG:
                print("[RelayControlApp] open_language_dialog called")
            else:
                logging.info("open_language_dialog called")
            def set_language(lang_code):
                self.set_language(lang_code)
                for widget in self.station_widgets:
                    widget.update_language()
            dlg = SelectionDialog(
                options=[("en", self.tr("English")), ("es", self.tr("Español"))],
                parent=self,
                title=self.tr("SET LANGUAGE"),
                on_select=set_language
            )
            self.active_dialog = dlg
            if DEBUG:
                print(f"[RelayControlApp] active_dialog set to: {dlg}")
            else:
                logging.info(f"active_dialog set to: {dlg}")
            dlg.finished.connect(lambda: setattr(self, "active_dialog", None))
            dlg.show()
        except Exception as e:
            logging.error("Error in open_language_dialog", exc_info=True)
            self.show_timed_info(self.tr("ERROR"), f"Failed to open language dialog: {e}", timeout_ms=2000)

    def open_filling_mode_dialog(self):
        try:
            if DEBUG:
                print("[RelayControlApp] open_filling_mode_dialog called")
            else:
                logging.info("open_filling_mode_dialog called")
            def set_filling_mode(mode):
                if self.filling_mode_callback:
                    self.filling_mode_callback(mode)
                self.filling_mode = mode
                self.show_timed_info(self.tr("FILLING MODE"), f"{self.tr('Mode set to:')} {mode}", timeout_ms=1500)
            dlg = SelectionDialog(
                options=[("AUTO", self.tr("AUTO")), ("MANUAL", self.tr("MANUAL")), ("SMART", self.tr("SMART"))],
                parent=self,
                title=self.tr("FILLING MODE"),
                on_select=set_filling_mode
            )
            self.active_dialog = dlg
            dlg.finished.connect(lambda: setattr(self, "active_dialog", None))
            dlg.show()
        except Exception as e:
            logging.error("Error in open_filling_mode_dialog", exc_info=True)
            self.show_timed_info(self.tr("ERROR"), f"Failed to open filling mode dialog: {e}", timeout_ms=2000)

    def show_timed_info(self, title, message, timeout_ms=2000):
        try:
            dialog = InfoDialog(title, message, self)
            dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
            dialog.show()
            QTimer.singleShot(timeout_ms, dialog.close)
        except Exception as e:
            logging.error(f"Error in RelayControlApp.show_timed_info: {e}", exc_info=True)

    def handle_station_selected(self, station_index):
        try:
            if DEBUG:
                print(f"StationStatusDialog: Station {station_index+1} selected for (re)connect")
            else:
                logging.info(f"StationStatusDialog: Station {station_index+1} selected for (re)connect")
            from main import try_connect_station  # Import your connect function
            success = try_connect_station(station_index)
            if success:
                if DEBUG:
                    print(f"Station {station_index+1} connected and enabled.")
                else:
                    logging.info(f"Station {station_index+1} connected and enabled.")
                self.station_enabled[station_index] = True
                self.update_station_states(self.station_enabled)
            else:
                if DEBUG:
                    print(f"Station {station_index+1} connection failed.")
                else:
                    logging.error(f"Station {station_index+1} connection failed.")
        except Exception as e:
            if DEBUG:
                print(f"Error connecting to station {station_index+1}: {e}")
            else:
                logging.error(f"Error connecting to station {station_index+1}: {e}")

class InfoDialog(QDialog):
    def __init__(self, title, message, parent=None):
        try:
            super().__init__(parent)
            self.setWindowTitle(title)
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
            self.setStyleSheet("""
                QDialog {
                    background-color: #444;      /* Medium grey */
                    border: 6px solid #fff;      /* White border */
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
        except Exception as e:
            logging.error(f"Error in InfoDialog.__init__: {e}", exc_info=True)

    def set_message(self, message):
        try:
            self.value_label.setText(message)
        except Exception as e:
            logging.error(f"Error in InfoDialog.set_message: {e}", exc_info=True)

    def show_with_callback(self, callback, delay_ms=2000):
        def on_accepted():
            callback()
        self.accepted.connect(on_accepted)
        self.show()
        QTimer.singleShot(delay_ms, self.accept)

class BottleProgressBar(QWidget):
    def __init__(self, max_value=100, value=0, bar_color="#4FC3F7", parent=None):
        try:
            super().__init__(parent)
            self.max_value = max_value
            self.value = value
            self.bar_color = bar_color
        except Exception as e:
            logging.error(f"Error in BottleProgressBar.__init__: {e}", exc_info=True)

    def set_value(self, value):
        try:
            self.value = value
            self.update()
        except Exception as e:
            logging.error(f"Error in BottleProgressBar.set_value: {e}", exc_info=True)

    def set_max(self, max_value):
        try:
            self.max_value = max_value
            self.update()
        except Exception as e:
            logging.error(f"Error in BottleProgressBar.set_max: {e}", exc_info=True)

    def paintEvent(self, event):
        try:
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
        except Exception as e:
            logging.error(f"Error in BottleProgressBar.paintEvent: {e}", exc_info=True)

class SetTargetWeightDialog(QDialog):
    def __init__(self, parent=None):
        try:
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
                up.setStyleSheet("color: #fff;")
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
                down.setStyleSheet("color: #fff;")
                self.down_labels.append(down)
                down_arrows_layout.addWidget(down)
            layout.addLayout(down_arrows_layout)

            self.setLayout(layout)
            self.setModal(True)
            self.update_display()
        except Exception as e:
            logging.error(f"Error in SetTargetWeightDialog.__init__: {e}", exc_info=True)

    def set_arrow_active(self, direction):
        try:
            if direction == "up":
                self.up_labels[self.current_digit].setStyleSheet("color: #00FF00;")
            elif direction == "down":
                self.down_labels[self.current_digit].setStyleSheet("color: #00FF00;")
        except Exception as e:
            logging.error(f"Error in SetTargetWeightDialog.set_arrow_active: {e}", exc_info=True)

    def set_arrow_inactive(self, direction):
        try:
            if direction == "up":
                self.up_labels[self.current_digit].setStyleSheet("color: #fff;")
            elif direction == "down":
                self.down_labels[self.current_digit].setStyleSheet("color: #fff;")
        except Exception as e:
            logging.error(f"Error in SetTargetWeightDialog.set_arrow_inactive: {e}", exc_info=True)

    def select_prev(self):
        try:
            self.digits[self.current_digit] = (self.digits[self.current_digit] + 1) % 10
            self.update_display()
        except Exception as e:
            logging.error(f"Error in SetTargetWeightDialog.select_prev: {e}", exc_info=True)

    def select_next(self):
        try:
            self.digits[self.current_digit] = (self.digits[self.current_digit] - 1) % 10
            self.update_display()
        except Exception as e:
            logging.error(f"Error in SetTargetWeightDialog.select_next: {e}", exc_info=True)

    def update_display(self):
        try:
            for i, lbl in enumerate(self.digit_labels):
                if i == self.current_digit:
                    lbl.setStyleSheet("color: #F6EB61; border: 2px solid #F6EB61; border-radius: 8px; background: #222;")
                else:
                    lbl.setStyleSheet("color: #fff; border: 2px solid transparent; background: #222;")
                lbl.setText(str(self.digits[i]))
        except Exception as e:
            logging.error(f"Error in SetTargetWeightDialog.update_display: {e}", exc_info=True)

    def activate_selected(self):
        try:
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
        except Exception as e:
            logging.error(f"Error in SetTargetWeightDialog.activate_selected: {e}", exc_info=True)

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
    def __init__(self, options, parent=None, title="", label_text="", outlined=True, on_select=None):
        try:
            super().__init__(parent)
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
            self.selected_index = 0
            self.options = options
            self.on_select_callback = on_select
            layout = QVBoxLayout(self)

            # Use OutlinedLabel for the title if provided, with smaller font
            if title:
                title_label = OutlinedLabel(title)
                title_label.setFont(QFont("Arial", 32, QFont.Weight.Bold))  # Smaller font
                title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(title_label)

            # Center the option buttons
            button_container = QWidget()
            button_layout = QVBoxLayout(button_container)
            button_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            self.labels = []
            for _, display_text in self.options:
                item_label = OutlinedLabel(display_text) if outlined else QLabel(display_text)
                item_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                item_label.setFixedSize(320, 64)
                self.labels.append(item_label)
                button_layout.addWidget(item_label)
            layout.addWidget(button_container)
            self.setLayout(layout)
            self.update_selection_box()
            self.setModal(True)
        except Exception as e:
            logging.error(f"Error in SelectionDialog.__init__: {e}", exc_info=True)

    def update_selection_box(self):
        try:
            for i, label in enumerate(self.labels):
                if i == self.selected_index:
                    label.setStyleSheet(
                        "font-size: 24px; border: 4px solid #F6EB61; border-radius: 16px; background: transparent;"
                    )
                else:
                    label.setStyleSheet(
                        "font-size: 24px; border: 4px solid transparent; border-radius: 16px; background: transparent;"
                    )
        except Exception as e:
            logging.error(f"Error in SelectionDialog.update_selection_box: {e}", exc_info=True)

    def select_next(self):
        try:
            self.selected_index = (self.selected_index + 1) % len(self.labels)
            self.update_selection_box()
        except Exception as e:
            logging.error(f"Error in SelectionDialog.select_next: {e}", exc_info=True)

    def select_prev(self):
        try:
            self.selected_index = (self.selected_index - 1) % len(self.labels)
            self.update_selection_box()
        except Exception as e:
            logging.error(f"Error in SelectionDialog.select_prev: {e}", exc_info=True)

    def activate_selected(self):
        try:
            value = self.options[self.selected_index][0]
            if self.on_select_callback:
                self.on_select_callback(value)
            self.accept()
        except Exception as e:
            logging.error(f"Error in SelectionDialog.activate_selected: {e}", exc_info=True)

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
            # Make the border fully transparent and background black for blending
            frame.setStyleSheet("border: 4px solid transparent; border-radius: 18px; background: #000;")
            frame.setLayout(QVBoxLayout())
            frame.layout().setContentsMargins(16, 16, 16, 16)  # Add equal padding all around
            frame.layout().setAlignment(Qt.AlignmentFlag.AlignCenter)
            frame.layout().addWidget(box_widget)
            frame.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
            self.grid.addWidget(frame)
            self.station_frames.append(frame)
        layout.addLayout(stations_layout)

        # Accept button
        self.accept_label = QLabel("ACCEPT")
        self.accept_label.setFont(QFont("Arial", 28, QFont.Weight.Bold))
        self.accept_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
                # Always use 6px border, just change color
                frame.setStyleSheet("border: 6px solid #F6EB61; border-radius: 14px; background: transparent; padding: 0px;")
            else:
                frame.setStyleSheet("border: 6px solid transparent; border-radius: 14px; background: transparent; padding: 0px;")
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
            frame.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
            self.grid.addWidget(frame)
            self.station_frames.append(frame)
        self.layout.addLayout(self.grid)

        # Accept button
        self.accept_label = QLabel(self.tr("ACCEPT"))
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
                f"background: {color}; color: #fff; border-radius: 8px; border: none; padding: 4px;"
            )

            # Update connected label
            if box_widget.connected_label is not None:
                box_widget.connected_label.setText(self.tr("CONNECTED") if is_connected else self.tr("DISCONNECTED"))
                box_widget.connected_label.setStyleSheet(
                    f"background: {color if is_connected else '#000'}; color: #fff; border-radius: 8px; border: none; padding: 4px;"
                )
            else:
                connected_label = QLabel(self.tr("CONNECTED") if is_connected else self.tr("DISCONNECTED"))
                connected_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                connected_label.setFont(QFont("Arial", 16))
                connected_label.setStyleSheet(
                    f"background: {color if is_connected else '#000'}; color: #fff; border-radius: 8px; border: none; padding: 4px;"
                )
                box_widget.layout().insertWidget(1, connected_label)
                box_widget.connected_label = connected_label

            # Update enabled label
            if box_widget.enabled_label is not None:
                box_widget.enabled_label.setText(self.tr("ENABLED") if is_enabled else self.tr("DISABLED"))
                box_widget.enabled_label.setStyleSheet(
                    f"background: {color if is_enabled else '#000'}; color: #fff; border-radius: 8px; border: none; padding: 4px;"
                )
            else:
                enabled_label = QLabel(self.tr("ENABLED") if is_enabled else self.tr("DISABLED"))
                enabled_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                enabled_label.setFont(QFont("Arial", 16))
                enabled_label.setStyleSheet(
                    f"background: {color if is_enabled else '#000'}; color: #fff; border-radius: 8px; border: none; padding: 4px;"
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
            # Toggle enabled state for the selected station
            if hasattr(parent, "station_enabled"):
                parent.station_enabled[sel] = not parent.station_enabled[sel]
                # Update statuses/colors for UI (use self.station_connected for connection status)
                statuses = []
                for i in range(len(parent.station_enabled)):
                    if parent.station_enabled[i] and self.station_connected[i]:
                        statuses.append("ENABLED & CONNECTED")
                    elif parent.station_enabled[i] and not self.station_connected[i]:
                        statuses.append("ENABLED & DISCONNECTED")
                    elif not parent.station_enabled[i] and self.station_connected[i]:
                        statuses.append("DISABLED & CONNECTED")
                    else:
                        statuses.append("DISABLED & DISCONNECTED")
                self.statuses = statuses
                self.show_station_verification(self.station_names, self.statuses, self.colors, self.station_connected)
                # Optionally show a message
                if hasattr(parent, "show_timed_info"):
                    parent.show_timed_info(
                        "STATION STATUS",
                        f"Station {sel+1} is now {'ENABLED' if parent.station_enabled[sel] else 'DISABLED'}",
                        timeout_ms=1500
                    )

class CalibrationDialog(QDialog):
    def __init__(self, station_enabled, parent=None):
        try:
            super().__init__(parent)
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
            self.setModal(True)
            self.setStyleSheet("background-color: #222; color: #fff;")

            # Main horizontal layout
            main_layout = QHBoxLayout(self)
            main_layout.setContentsMargins(0, 0, 0, 0)
            main_layout.setSpacing(0)

            # Left: content layout
            content_layout = QVBoxLayout()
            # Large label (main instruction)
            self.main_label = QLabel("CALIBRATION")
            self.main_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.main_label.setFont(QFont("Arial", 32, QFont.Weight.Bold))
            content_layout.addWidget(self.main_label)

            # Smaller label (sub-instruction)
            self.sub_label = QLabel("Follow the instructions to calibrate each station.")
            self.sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.sub_label.setFont(QFont("Arial", 20))
            content_layout.addWidget(self.sub_label)

            # Four StationBoxWidgets inside QFrames
            self.weight_labels = []
            self.station_boxes = []
            weights_layout = QHBoxLayout()
            weights_layout.setSpacing(24)
            for i in range(4):
                try:
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
                    frame.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
                except Exception as e:
                    logging.error(f"Error creating StationBoxWidget for station {i+1}: {e}", exc_info=True)
                    continue
            self.bottom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.bottom_label.setFont(QFont("Arial", 18))
            content_layout.addWidget(self.bottom_label)
            main_layout.addLayout(content_layout, stretch=3)

            # Right: button label column
            self.button_column = ButtonColumnWidget(
                icons=["▲", "⏎", "▼"],
                font_size=32,
                fixed_width=64,
                margins=(0, 30, 0, 0),
                spacing=50,
                parent=self
            )
            main_layout.addWidget(self.button_column, stretch=0)

            self.setLayout(main_layout)
        except Exception as e:
            logging.error(f"Error in CalibrationDialog.__init__: {e}", exc_info=True)

    def set_weight(self, station_index, weight):
        try:
            if self.weight_labels[station_index]:
                if isinstance(weight, (int, float)):
                    new_text = f"{weight:.1f} g"
                else:
                    new_text = str(weight)
                self.weight_labels[station_index].setText(new_text)
        except Exception as e:
            logging.error(f"Error in CalibrationDialog.set_weight (station_index={station_index}): {e}", exc_info=True)

    def set_bottom_label(self, text):
        try:
            self.bottom_label.setText(text)
        except Exception as e:
            logging.error(f"Error in CalibrationDialog.set_bottom_label: {e}", exc_info=True)

    def select_prev(self):
        try:
            self.done(1)  # Continue to next step
        except Exception as e:
            logging.error("Error in CalibrationDialog.select_prev", exc_info=True)

    def select_next(self):
        try:
            self.done(1)  # Continue to next step
        except Exception as e:
            logging.error("Error in CalibrationDialog.select_next", exc_info=True)

    def activate_selected(self):
        try:
            self.done(1)  # Continue to next step
        except Exception as e:
            logging.error("Error in CalibrationDialog.activate_selected", exc_info=True)

    def showEvent(self, event):
        try:
            super().showEvent(event)
            self.main_label.setText(text)
        except Exception as e:
            logging.error("Error in CalibrationDialog.set_main_label", exc_info=True)

    def set_sub_label(self, text):
        try:
            self.sub_label.setText(text)
        except Exception as e:
            logging.error("Error in CalibrationDialog.set_sub_label", exc_info=True)

    def set_bottom_label(self, text):
        try:
            self.bottom_label.setText(text)
        except Exception as e:
            logging.error("Error in CalibrationDialog.set_bottom_label (duplicate): {e}", exc_info=True)

class ButtonColumnWidget(QWidget):
    def __init__(
        self,
        icons=["▲", "⏎", "▼"],
        parent=None,
        font_size=32,
        fixed_width=64,
        margins=(0, 30, 0, 0),
        spacing=50,
        align=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        style="color: #fff; background: #333; border-radius: 12px; padding: 12px 0px;"
    ):
        super().__init__(parent)
        if icons is None:
            icons = ["▲", "⏎", "▼"]
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*margins)
        layout.setSpacing(spacing)
        for icon in icons:
            lbl = QLabel(icon)
            lbl.setFont(QFont("Arial", font_size, QFont.Weight.Bold))
            lbl.setStyleSheet(style)
            lbl.setFixedWidth(fixed_width)
            lbl.setAlignment(align)
            layout.addWidget(lbl)
        layout.addStretch(1)
        self.setLayout(layout)

    def flash_icon(self, index, flash_color="#11BD33", duration=150):
        """
        Flash the icon at the given index with the specified color for a short duration.
        """
        labels = self.findChildren(QLabel)
        if not (0 <= index < len(labels)):
            return
        label = labels[index]
        original_style = label.styleSheet()
        label.setStyleSheet(original_style + f"; color: {flash_color}; background: #444;")
        label_ref = weakref.ref(label)
        def restore_style():
            lbl = label_ref()
            if lbl is not None:
                lbl.setStyleSheet(original_style)
        QTimer.singleShot(duration, restore_style)

class StartupWizardDialog(QDialog):
    """
    A single dialog for all startup steps, styled to match the provided wireframe.
    Uses StationBoxWidget for station display.
    """
    def __init__(self, parent=None, num_stations=4):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.setFixedSize(1024, 600)  # Ensure dialog fits the screen exactly
        self.num_stations = num_stations

        # Step tracking
        self.current_step = 0
        self.selection_index = 0
        self.station_enabled = [True] * num_stations
        self.station_connected = [True] * num_stations
        self.station_names = [f"Station {i+1}" for i in range(num_stations)]
        self.weight_texts = [None] * num_stations

        # Main vertical layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Main label
        self.main_label = QLabel("MAIN LABEL")
        self.main_label.setFont(QFont("Arial", 36, QFont.Weight.Bold))
        self.main_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_label.setFixedHeight(60)
        self.main_label.setStyleSheet("""
            background: transparent;
            color: #fff;
            border: 2px solid #ccc;
            border-radius: 12px;
            padding: 6px;
        """)
        main_layout.addWidget(self.main_label)

        # Info/Prompt area
        self.info_label = QLabel("Startup Info ....")
        self.info_label.setFont(QFont("Arial", 22))
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.info_label.setWordWrap(True)
        self.info_label.setMinimumHeight(60)
        self.info_label.setMaximumHeight(80)
        self.info_label.setStyleSheet("""
            background: transparent;
            color: #fff;
            border: 2px solid #ccc;
            border-radius: 12px;
            padding: 8px;
        """)
        main_layout.addWidget(self.info_label)

        # Station boxes row (now using StationBoxWidget)
        stations_layout = QHBoxLayout()
        stations_layout.setSpacing(16)
        self.station_boxes = []
        for i in range(self.num_stations):
            box = StationBoxWidget(
                station_index=i,
                name=f"Station {i+1}",
                color=STATION_COLORS[i % len(STATION_COLORS)],
                connected=True,
                enabled=True,
                weight_text="--",  # Default to --
                parent=self
            )
            box.setFixedSize(216, 140)  # 20% wider
            self.station_boxes.append(box)
            stations_layout.addWidget(box)
        main_layout.addLayout(stations_layout)

        # Accept/Continue label
        self.accept_label = QLabel("CONTINUE")
        self.accept_label.setFont(QFont("Arial", 28, QFont.Weight.Bold))
        self.accept_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.accept_label.setFixedHeight(48)
        self.accept_label.setStyleSheet("color: #fff; border: 2px solid #ccc; border-radius: 12px; padding: 8px 24px; margin-top: 8px;")
        main_layout.addWidget(self.accept_label)

        # Right-side: button labels (identical to RelayControlApp)
        button_column = ButtonColumnWidget(
            icons=["▲", "⏎", "▼"],
            font_size=28,
            fixed_width=48,
            margins=(0, 16, 0, 0),
            spacing=32,
            parent=self
        )

        # Place main content and button column in a horizontal layout
        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)
        h_layout.addLayout(main_layout, stretch=10)
        h_layout.addWidget(button_column, stretch=0)
        self.setLayout(h_layout)

        # Save reference for flashing, etc.
        self.button_column = button_column

        # Initial highlight
        self.step_mode = "station_select"
        self.update_highlight()

    def set_main_label(self, text):
        self.main_label.setText(text)

    def set_info_text(self, text):
        self.info_label.setText(text)

    def set_station_labels(self, names=None, connected=None, enabled=None, weight_texts=None):
        """
        Update the StationBoxWidgets.
        """
        if names:
            self.station_names = names
        if connected:
            self.station_connected = connected
        if enabled:
            self.station_enabled = enabled
        if weight_texts:
            self.weight_texts = weight_texts

        for i, box in enumerate(self.station_boxes):
            if self.station_names and i < len(self.station_names):
                box.name_label.setText(self.station_names[i])
            if self.station_connected and i < len(self.station_connected):
                if box.connected_label:
                    box.connected_label.setText("CONNECTED" if self.station_connected[i] else "DISCONNECTED")
            if self.station_enabled and i < len(self.station_enabled):
                if box.enabled_label:
                    box.enabled_label.setText("ENABLED" if self.station_enabled[i] else "DISABLED")
            # Always update weight label
            weight = "0.0 g"
            if self.weight_texts and i < len(self.weight_texts) and self.weight_texts[i] is not None:
                weight = self.weight_texts[i]
            if box.weight_label:
                box.weight_label.setText(weight)
        self.update_highlight()

    def set_step(self, step):
        """
        Set the current step and update navigation mode.
        """
        self.current_step = step
        # You can expand this logic for more steps as needed
        if step == 0:
            self.step_mode = "station_select"  # Station enable/disable + continue
            self.selection_index = 0
        elif step in (1, 2, 3):  # Accept-only steps (e.g. calibration, bottle check)
            self.step_mode = "accept_only"
            self.selection_index = 0
        else:
            self.step_mode = "none"
        self.update_highlight()

    def update_highlight(self):
        # Highlight station boxes or accept label based on selection_index and step_mode
        for i, box in enumerate(self.station_boxes):
            if self.step_mode == "station_select" and self.selection_index == i:
                box.setStyleSheet("border: 4px solid #F6EB61; border-radius: 12px; background: transparent;")
            else:
                box.setStyleSheet("border: 2px solid #ccc; border-radius: 12px; background: transparent;")
        if self.step_mode in ("station_select", "accept_only"):
            if (self.step_mode == "station_select" and self.selection_index == self.num_stations) or (self.step_mode == "accept_only" and self.selection_index == 0):
                self.accept_label.setStyleSheet("color: #F6EB61; border: 4px solid #F6EB61; border-radius: 12px; padding: 12px 32px; margin-top: 18px; background: #444;")
            else:
                self.accept_label.setStyleSheet("color: #fff; border: 2px solid #ccc; border-radius: 12px; padding: 12px 32px; margin-top: 18px; background: transparent;")
        else:
            self.accept_label.setStyleSheet("color: #fff; border: 2px solid #ccc; border-radius: 12px; padding: 12px 32px; margin-top: 18px; background: transparent;")

    def select_next(self):
        if self.step_mode == "station_select":
            self.selection_index = (self.selection_index + 1) % (self.num_stations + 1)
        elif self.step_mode == "accept_only":
            self.selection_index = 0  # Only accept/continue
        self.update_highlight()

    def select_prev(self):
        if self.step_mode == "station_select":
            self.selection_index = (self.selection_index - 1) % (self.num_stations + 1)
        elif self.step_mode == "accept_only":
            self.selection_index = 0
        self.update_highlight()

    def activate_selected(self):
        # Step 0: station select/toggle
        if self.current_step == 0 and self.step_mode == "station_select":
            if self.selection_index < self.num_stations:
                # Toggle enabled state for this station
                self.station_enabled[self.selection_index] = not self.station_enabled[self.selection_index]
                # Update enabled label
                if self.station_boxes[self.selection_index].enabled_label:
                    self.station_boxes[self.selection_index].enabled_label.setText("ENABLED" if self.station_enabled[self.selection_index] else "DISABLED")
                self.update_highlight()
            else:
                self.accept()
        # Steps 1,2,3: just accept/continue
        elif self.step_mode == "accept_only":
            self.accept()
        # If step_mode == "none", do nothing

    def get_station_enabled(self):
        return list(self.station_enabled)