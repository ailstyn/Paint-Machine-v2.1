from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QGridLayout, QVBoxLayout, QSizePolicy, QDialog, QPushButton, QHBoxLayout, QStyle, QSpacerItem, QFrame
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRectF, QPropertyAnimation, QVariantAnimation
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QPainterPath, QPixmap, QCursor, QFontMetrics, QPalette
import sys
import logging
import os
import weakref
from gui.languages import LANGUAGES
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import STATION_COLORS, NUM_STATIONS, STATS_LOG_FILE, STATS_LOG_DIR, ERROR_LOG_FILE, ERROR_LOG_DIR
DEBUG = True
logging.basicConfig(level=logging.INFO)

def qt_exception_hook(exctype, value, traceback):
    logging.error("Uncaught Qt exception", exc_info=(exctype, value, traceback))
    print("Uncaught Qt exception:", value)

sys.excepthook = qt_exception_hook

def animate_frame_bg(frame, start_color, end_color, duration=200):
    animation = QVariantAnimation(frame)
    animation.setDuration(duration)
    animation.setStartValue(QColor(start_color))
    animation.setEndValue(QColor(end_color))
    selector = f"QFrame#{frame.objectName()}" if frame.objectName() else "QFrame"
    def update_styles(color):
        # Keep the frame border and animate the background
        frame.setStyleSheet(
            f"{selector} {{ background: {color.name()}; border-radius: 14px; border: 4px solid #F6EB61; padding: 1px; }}"
        )
        # If the frame contains a StationBoxWidget, ensure its weight label is always transparent and borderless
        if frame.layout() and frame.layout().count() > 0:
            box = frame.layout().itemAt(0).widget()
            if hasattr(box, "weight_label") and box.weight_label:
                box.weight_label.setStyleSheet(
                    "color: #0f0; font-size: 32px; font-weight: bold; background: transparent; border: none; border-width: 0px; border-radius: 8px; padding: 8px 2px 8px 2px; min-height: 48px;"
                )
    animation.valueChanged.connect(update_styles)
    animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

class OutlinedLabel(QLabel):
    """
    QLabel with optional outline effect for station names and other prominent labels.
    Uses native Qt methods for appearance, no stylesheets.
    """
    def __init__(self, text="", parent=None, font_size=24, bold=True, color="#fff", bg_color=None, border_radius=14, padding=4):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        weight = QFont.Weight.Bold if bold else QFont.Weight.Normal
        self.setFont(QFont("Arial", font_size, weight))
        self._default_color = QColor(color)
        self._default_bg = QColor(bg_color) if bg_color else None
        self._default_border_radius = border_radius
        self._default_padding = padding
        self._highlighted = False
        self._highlight_color = QColor("#F6EB61")
        self._highlight_text_color = QColor("#222")
        self._highlight_border_color = QColor("#F6EB61")
        self._highlight_border_width = 4
        self._normal_border_color = QColor("transparent")
        self._normal_border_width = 4
        self._normal_bg = None

    def set_highlight(self, highlighted: bool):
        """
        Highlight the label (yellow background, dark text).
        """
        self._highlighted = highlighted
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()

        # Padding
        pad = self._default_padding
        inner_rect = rect.adjusted(pad, pad, -pad, -pad)

        # Draw background and border
        if self._highlighted:
            painter.setBrush(self._highlight_color)
            painter.setPen(QPen(self._highlight_border_color, self._highlight_border_width))
            text_color = self._highlight_text_color
        else:
            painter.setBrush(self._default_bg if self._default_bg else Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(self._normal_border_color, self._normal_border_width))
            text_color = self._default_color

        painter.drawRoundedRect(inner_rect, self._default_border_radius, self._default_border_radius)

        # Draw text with outline effect
        font = self.font()
        painter.setFont(font)
        text = self.text()
        metrics = painter.fontMetrics()
        text_width = metrics.horizontalAdvance(text)
        text_height = metrics.height()
        x = inner_rect.x() + (inner_rect.width() - text_width) / 2
        y = inner_rect.y() + (inner_rect.height() + text_height) / 2 - metrics.descent()

        path = QPainterPath()
        path.addText(x, y, font, text)

        # Draw black outline (stroke)
        outline_width = 6
        painter.setPen(QPen(QColor("black"), outline_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        # Draw fill
        painter.setPen(QPen(text_color, 1))
        painter.setBrush(text_color)
        painter.drawPath(path)

class StationBoxWidget(QWidget):
    def __init__(self, station_index, name, color, connected=None, enabled=None, weight_text=None, parent=None):
        super().__init__(parent)
        self.station_index = station_index
        self.color = color
        self.connected = connected
        self.enabled = enabled
        self.weight_text = weight_text if weight_text is not None else "--"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        tr = parent.tr if parent and hasattr(parent, "tr") else (lambda k: LANGUAGES["en"].get(k, k))

        # Station name label
        self.name_label = QLabel(name)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        self.name_label.setMinimumHeight(36)
        self.name_label.setMaximumHeight(40)
        # Set background color and rounded corners using palette and paintEvent
        self.name_label.setAutoFillBackground(True)
        name_palette = self.name_label.palette()
        name_palette.setColor(QPalette.ColorRole.Window, QColor(color))
        name_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
        self.name_label.setPalette(name_palette)
        layout.addWidget(self.name_label)

        # Connected label
        self.connected_label = None
        if connected is not None:
            self.connected_label = QLabel(tr("CONNECTED") if connected else tr("DISCONNECTED"))
            self.connected_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.connected_label.setFont(QFont("Arial", 16))
            self.connected_label.setMinimumHeight(28)
            self.connected_label.setMaximumHeight(32)
            self.connected_label.setAutoFillBackground(True)
            conn_palette = self.connected_label.palette()
            conn_palette.setColor(QPalette.ColorRole.Window, QColor(color if connected else "#000"))
            conn_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
            self.connected_label.setPalette(conn_palette)
            layout.addWidget(self.connected_label)

        # Enabled label
        self.enabled_label = None
        if enabled is not None:
            self.enabled_label = QLabel(tr("ENABLED") if enabled else tr("DISABLED"))
            self.enabled_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.enabled_label.setFont(QFont("Arial", 16))
            self.enabled_label.setMinimumHeight(28)
            self.enabled_label.setMaximumHeight(32)
            self.enabled_label.setAutoFillBackground(True)
            en_palette = self.enabled_label.palette()
            en_palette.setColor(QPalette.ColorRole.Window, QColor(color if enabled else "#000"))
            en_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
            self.enabled_label.setPalette(en_palette)
            layout.addWidget(self.enabled_label)

        # Weight label
        self.weight_label = QLabel(self.weight_text)
        self.weight_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.weight_label.setFont(QFont("Arial", 32, QFont.Weight.Bold))
        self.weight_label.setMinimumHeight(48)
        self.weight_label.setMaximumHeight(56)
        # Only set text color, no background or border
        weight_palette = self.weight_label.palette()
        weight_palette.setColor(QPalette.ColorRole.WindowText, QColor("#0f0"))
        self.weight_label.setPalette(weight_palette)
        layout.addWidget(self.weight_label)

        self.setMinimumWidth(216)
        self.setMinimumHeight(110)
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Expanding)

    def set_connected(self, connected, color):
        self.connected = connected
        if self.connected_label:
            self.connected_label.setText("CONNECTED" if connected else "DISCONNECTED")
            conn_palette = self.connected_label.palette()
            conn_palette.setColor(QPalette.ColorRole.Window, QColor(color if connected else "#000"))
            conn_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
            self.connected_label.setPalette(conn_palette)

    def set_enabled(self, enabled, color):
        self.enabled = enabled
        if self.enabled_label:
            self.enabled_label.setText("ENABLED" if enabled else "DISABLED")
            en_palette = self.enabled_label.palette()
            en_palette.setColor(QPalette.ColorRole.Window, QColor(color if enabled else "#000"))
            en_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
            self.enabled_label.setPalette(en_palette)

    def set_weight(self, current_weight, target_weight=None, unit="g"):
        try:
            current_weight = float(current_weight)
            if target_weight is not None:
                target_weight = float(target_weight)
        except (TypeError, ValueError):
            current_weight = 0
            target_weight = 0 if target_weight is not None else None
    
        if unit == "g":
            text = f"{int(round(current_weight))} / {int(round(target_weight))} g" if target_weight is not None else f"{int(round(current_weight))} g"
        else:
            current_oz = current_weight / 28.3495
            if target_weight is not None:
                target_oz = target_weight / 28.3495
                text = f"{current_oz:.1f} / {target_oz:.1f} oz"
            else:
                text = f"{current_oz:.1f} oz"
        self.weight_text = text
        if self.weight_label:
            self.weight_label.setText(text)

    def paintEvent(self, event):
        # Draw rounded corners for the widget background
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        painter.setBrush(QColor("#222"))  # Dark grey background
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, 24, 24)
        super().paintEvent(event)

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
        self.bg_color = QColor(bg_color)
        self.enabled = enabled

        # Always define these attributes
        self.weight_label = None
        self.status_label = None
        self.progress_bar = None
        self.offline_label = None

        # Flashing status attributes
        self._status_flash_timer = None
        self._status_flash_state = False
        self._status_flash_color = QColor("#FF2222")
        self._status_flash_text = ""
        self._status_flash_interval = 500  # ms

        if enabled:
            main_layout = QHBoxLayout(self)
            main_layout.setContentsMargins(0, 0, 0, 0)
            main_layout.setSpacing(0)

            # Use BottleProgressBar instead of QProgressBar
            self.progress_bar = BottleProgressBar(parent=self)

            content_layout = QVBoxLayout()
            content_layout.setContentsMargins(0, 0, 0, 0)
            content_layout.setSpacing(0)

            # Large weight label
            self.weight_label = OutlinedLabel("0.0 / 0.0 g", font_size=64, bold=True, color="#0f0")
            self.weight_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.weight_label.setFont(QFont("Arial", 64, QFont.Weight.Bold))
            content_layout.addWidget(self.weight_label, stretch=2)

            # Status label
            self.status_label = QLabel(self.tr("READY"))
            self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.status_label.setFont(QFont("Arial", 20))
            status_palette = self.status_label.palette()
            status_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
            self.status_label.setPalette(status_palette)
            content_layout.addWidget(self.status_label, stretch=1)

            # Add widgets to layout
            if hasattr(self, "bar_on_left") and self.bar_on_left:
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
            self.offline_label = OutlinedLabel(self.tr("STATION_OFFLINE"), font_size=32, bold=True, color="#FF2222")
            self.offline_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.offline_label.setFont(QFont("Arial", 32, QFont.Weight.Bold))
            offline_layout.addWidget(self.offline_label)
            self.setLayout(offline_layout)

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
                self.status_label.setText(text)
                status_palette = self.status_label.palette()
                status_palette.setColor(QPalette.ColorRole.WindowText, QColor(color))
                self.status_label.setPalette(status_palette)
        except Exception as e:
            logging.error(f"Error in StationWidget.set_status (station_number={getattr(self, 'station_number', '?')}): {e}", exc_info=True)

    def _toggle_status_flash(self):
        try:
            if self.status_label is None:
                return
            self._status_flash_state = not self._status_flash_state
            if self._status_flash_state:
                self.status_label.setText(self._status_flash_text)
                status_palette = self.status_label.palette()
                status_palette.setColor(QPalette.ColorRole.WindowText, self._status_flash_color)
                self.status_label.setPalette(status_palette)
            else:
                self.status_label.setText("")
                status_palette = self.status_label.palette()
                status_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
                self.status_label.setPalette(status_palette)
        except Exception as e:
            logging.error(f"Error in StationWidget._toggle_status_flash (station_number={getattr(self, 'station_number', '?')}): {e}", exc_info=True)

    def clear_status(self):
        try:
            if self._status_flash_timer and self._status_flash_timer.isActive():
                self._status_flash_timer.stop()
            if self.status_label is not None:
                self.status_label.setText("")
                status_palette = self.status_label.palette()
                status_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
                self.status_label.setPalette(status_palette)
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

    def paintEvent(self, event):
        # Draw background and border for the widget
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        painter.setBrush(self.bg_color)
        painter.setPen(QPen(QColor("#222"), 2))
        painter.drawRoundedRect(rect, 14, 14)
        super().paintEvent(event)

class MenuDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_index = 0
        self.menu_keys = [
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
            label = OutlinedLabel(item, font_size=28, bold=True, color="#fff")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setFixedSize(320, 64)
            self.labels.append(label)
            layout.addWidget(label)
        self.setLayout(layout)
        self.update_selection_box()

    def update_selection_box(self):
        for i, label in enumerate(self.labels):
            if i == self.selected_index:
                label.set_highlight(True)
            else:
                label.set_highlight(False)

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
        elif selected_key == "SET TARGET WEIGHT":
            self.hide()
            parent.target_weight_dialog = SetTargetWeightDialog(parent)
            parent.active_dialog = parent.target_weight_dialog
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
            self.hide()
            parent.open_filling_mode_dialog()

    def show_again(self):
        self.show()
        parent = self.parent()
        if hasattr(parent, "target_weight_dialog"):
            parent.target_weight_dialog = None
        if hasattr(parent, "time_limit_dialog"):
            parent.time_limit_dialog = None
        if hasattr(parent, "language_dialog"):
            parent.language_dialog = None
        if hasattr(parent, "change_units_dialog"):
            parent.change_units_dialog = None

    def update_menu_language(self):
        self.menu_items = [self.parent().tr(key) for key in self.menu_keys]
        for label, text in zip(self.labels, self.menu_items):
            label.setText(text)

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
                widget.setFixedSize(475, 280)
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
        """
        Update the weight label for a specific station box at any step.
        """
        if 0 <= station_index < len(self.station_boxes):
            text = f"{weight:.1f} g"
            self.weight_texts[station_index] = text
            box = self.station_boxes[station_index]
            if box.weight_label:
                box.weight_label.setText(text)

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
            self.setModal(True)
            self.setMinimumWidth(400)
            self.setMinimumHeight(220)
            self.setMaximumHeight(320)

            # Set background color and rounded corners using paintEvent
            self._bg_color = QColor("#222")
            self._border_radius = 24

            layout = QVBoxLayout(self)
            layout.setContentsMargins(24, 24, 24, 24)
            layout.setSpacing(12)

            self.title_label = QLabel(title)
            self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.title_label.setFont(QFont("Arial", 32, QFont.Weight.Bold))
            title_palette = self.title_label.palette()
            title_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
            self.title_label.setPalette(title_palette)
            self.title_label.setMinimumHeight(48)
            layout.addWidget(self.title_label)

            self.value_label = QLabel(message)
            self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.value_label.setFont(QFont("Arial", 48, QFont.Weight.Bold))
            value_palette = self.value_label.palette()
            value_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
            self.value_label.setPalette(value_palette)
            self.value_label.setMinimumHeight(72)
            self.value_label.setMaximumHeight(150)
            layout.addWidget(self.value_label)

            self.setLayout(layout)
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

    def paintEvent(self, event):
        # Draw rounded background for the dialog
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        painter.setBrush(self._bg_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, self._border_radius, self._border_radius)
        super().paintEvent(event)

class BottleProgressBar(QWidget):
    def __init__(self, max_value=100, value=0, bar_color="#4FC3F7", parent=None):
        try:
            super().__init__(parent)
            self.max_value = max_value
            self.value = value
            self.bar_color = QColor(bar_color)
            self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
            # No stylesheet needed
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
            corner_radius = body_width * 0.18

            neck_left = rect.center().x() - neck_width / 2
            neck_right = rect.center().x() + neck_width / 2
            body_left = rect.center().x() - body_width / 2
            body_right = rect.center().x() + body_width / 2

            bottle_path = QPainterPath()
            bottle_path.moveTo(neck_left, margin)
            bottle_path.lineTo(neck_right, margin)
            bottle_path.lineTo(neck_right, neck_height + margin)
            bottle_path.arcTo(
                body_right - 2 * corner_radius, neck_height + margin,
                2 * corner_radius, 2 * corner_radius,
                90, -90
            )
            bottle_path.lineTo(body_right, neck_height + margin + corner_radius)
            bottle_path.lineTo(body_right, neck_height + body_height)
            bottle_path.arcTo(
                body_left, neck_height + body_height - body_width / 2,
                body_width, body_width,
                0, -180
            )
            bottle_path.lineTo(body_left, neck_height + margin + corner_radius)
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
            painter.setBrush(self.bar_color)
            painter.setClipPath(bottle_path)
            painter.drawRect(fill_rect)
            painter.setClipping(False)
            # No percentage text overlay
        except Exception as e:
            logging.error(f"Error in BottleProgressBar.paintEvent: {e}", exc_info=True)

class SetTargetWeightDialog(QDialog):
    def __init__(self, parent=None):
        try:
            super().__init__(parent)
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
            self.setModal(True)
            self.setMinimumWidth(400)
            self.setMinimumHeight(320)
            self._bg_color = QColor("#222")
            self._border_radius = 24

            tr = parent.tr if parent else (lambda k: LANGUAGES["en"].get(k, k))
            self.setWindowTitle(tr("SET_TARGET_WEIGHT"))
            layout = QVBoxLayout(self)
            layout.setContentsMargins(24, 24, 24, 24)
            layout.setSpacing(12)

            label = QLabel(tr("ENTER_NEW_TARGET_WEIGHT"))
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setFont(QFont("Arial", 20, QFont.Weight.Bold))
            label_palette = label.palette()
            label_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
            label.setPalette(label_palette)
            label.setMinimumHeight(36)
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
                up_palette = up.palette()
                up_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
                up.setPalette(up_palette)
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
                lbl_palette = lbl.palette()
                lbl_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
                lbl.setPalette(lbl_palette)
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
                down_palette = down.palette()
                down_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
                down.setPalette(down_palette)
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
            color = QColor("#00FF00")
            if direction == "up":
                self.up_labels[self.current_digit].setPalette(self._make_palette(color))
            elif direction == "down":
                self.down_labels[self.current_digit].setPalette(self._make_palette(color))
        except Exception as e:
            logging.error(f"Error in SetTargetWeightDialog.set_arrow_active: {e}", exc_info=True)

    def set_arrow_inactive(self, direction):
        try:
            color = Qt.GlobalColor.white
            if direction == "up":
                self.up_labels[self.current_digit].setPalette(self._make_palette(color))
            elif direction == "down":
                self.down_labels[self.current_digit].setPalette(self._make_palette(color))
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
                    lbl.setPalette(self._make_palette(QColor("#F6EB61")))
                    lbl.setFont(QFont("Arial", 48, QFont.Weight.Bold))
                else:
                    lbl.setPalette(self._make_palette(Qt.GlobalColor.white))
                    lbl.setFont(QFont("Arial", 48, QFont.Weight.Bold))
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

    def _make_palette(self, color):
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.WindowText, color)
        return palette

    def paintEvent(self, event):
        # Draw rounded background for the dialog
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        painter.setBrush(self._bg_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, self._border_radius, self._border_radius)
        super().paintEvent(event)

class SetTimeLimitDialog(QDialog):
    def __init__(self, parent=None):
        try:
            super().__init__(parent)
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
            self.setModal(True)
            self.setMinimumWidth(400)
            self.setMinimumHeight(320)
            self._bg_color = QColor("#222")
            self._border_radius = 24

            tr = parent.tr if parent else (lambda k: LANGUAGES["en"].get(k, k))
            self.setWindowTitle(tr("SET_TIME_LIMIT"))
            layout = QVBoxLayout(self)
            layout.setContentsMargins(24, 24, 24, 24)
            layout.setSpacing(12)

            label = QLabel(tr("ENTER_NEW_TIME_LIMIT"))
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setFont(QFont("Arial", 20, QFont.Weight.Bold))
            label_palette = label.palette()
            label_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
            label.setPalette(label_palette)
            label.setMinimumHeight(36)
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
                up_palette = up.palette()
                up_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
                up.setPalette(up_palette)
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
                lbl_palette = lbl.palette()
                lbl_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
                lbl.setPalette(lbl_palette)
                self.digit_labels.append(lbl)
                digits_layout.addWidget(lbl)
                if i == 2:  # After the third digit, add the decimal point
                    dot = QLabel(".")
                    dot.setFont(QFont("Arial", 48, QFont.Weight.Bold))
                    dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    dot.setFixedWidth(24)
                    dot_palette = dot.palette()
                    dot_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
                    dot.setPalette(dot_palette)
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
                down_palette = down.palette()
                down_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
                down.setPalette(down_palette)
                self.down_labels.append(down)
                down_arrows_layout.addWidget(down)
                if i == 2:  # After the third arrow, add a spacer for the decimal point
                    spacer = QSpacerItem(24, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
                    down_arrows_layout.addItem(spacer)
            layout.addLayout(down_arrows_layout)

            self.setLayout(layout)
            self.setModal(True)
            self.update_display()
        except Exception as e:
            logging.error(f"Error in SetTimeLimitDialog.__init__: {e}", exc_info=True)

    def set_arrow_active(self, direction):
        try:
            color = QColor("#00FF00")
            if direction == "up":
                self.up_labels[self.current_digit].setPalette(self._make_palette(color))
            elif direction == "down":
                self.down_labels[self.current_digit].setPalette(self._make_palette(color))
        except Exception as e:
            logging.error(f"Error in SetTimeLimitDialog.set_arrow_active: {e}", exc_info=True)

    def set_arrow_inactive(self, direction):
        try:
            color = Qt.GlobalColor.white
            if direction == "up":
                self.up_labels[self.current_digit].setPalette(self._make_palette(color))
            elif direction == "down":
                self.down_labels[self.current_digit].setPalette(self._make_palette(color))
        except Exception as e:
            logging.error(f"Error in SetTimeLimitDialog.set_arrow_inactive: {e}", exc_info=True)

    def select_prev(self):
        try:
            self.digits[self.current_digit] = (self.digits[self.current_digit] + 1) % 10
            self.update_display()
        except Exception as e:
            logging.error(f"Error in SetTimeLimitDialog.select_prev: {e}", exc_info=True)

    def select_next(self):
        try:
            self.digits[self.current_digit] = (self.digits[self.current_digit] - 1) % 10
            self.update_display()
        except Exception as e:
            logging.error(f"Error in SetTimeLimitDialog.select_next: {e}", exc_info=True)

    def update_display(self):
        try:
            for i, lbl in enumerate(self.digit_labels):
                if i == self.current_digit:
                    lbl.setPalette(self._make_palette(QColor("#F6EB61")))
                    lbl.setFont(QFont("Arial", 48, QFont.Weight.Bold))
                else:
                    lbl.setPalette(self._make_palette(Qt.GlobalColor.white))
                    lbl.setFont(QFont("Arial", 48, QFont.Weight.Bold))
                lbl.setText(str(self.digits[i]))
        except Exception as e:
            logging.error(f"Error in SetTimeLimitDialog.update_display: {e}", exc_info=True)

    def activate_selected(self):
        try:
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
        except Exception as e:
            logging.error(f"Error in SetTimeLimitDialog.activate_selected: {e}", exc_info=True)

    def _make_palette(self, color):
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.WindowText, color)
        return palette

    def paintEvent(self, event):
        # Draw rounded background for the dialog
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        painter.setBrush(self._bg_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, self._border_radius, self._border_radius)
        super().paintEvent(event)

class SelectionDialog(QDialog):
    def __init__(self, options, parent=None, title="", label_text="", outlined=True, on_select=None):
        try:
            super().__init__(parent)
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
            self.setModal(True)
            self.setMinimumWidth(400)
            self.setMinimumHeight(320)
            self._bg_color = QColor("#222")
            self._border_radius = 24

            self.selected_index = 0
            self.options = options
            self.on_select_callback = on_select
            layout = QVBoxLayout(self)
            layout.setContentsMargins(24, 24, 24, 24)
            layout.setSpacing(12)

            # Title label (optional)
            if title:
                title_label = OutlinedLabel(title, font_size=32, bold=True, color="#fff")
                title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(title_label)

            # Option labels
            button_container = QWidget()
            button_layout = QVBoxLayout(button_container)
            button_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            self.labels = []
            for _, display_text in self.options:
                item_label = OutlinedLabel(display_text, font_size=28, bold=True, color="#fff") if outlined else QLabel(display_text)
                item_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                item_label.setFixedSize(320, 64)
                if not outlined:
                    item_label.setFont(QFont("Arial", 28, QFont.Weight.Bold))
                    palette = item_label.palette()
                    palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
                    item_label.setPalette(palette)
                self.labels.append(item_label)
                button_layout.addWidget(item_label)
            layout.addWidget(button_container)
            self.setLayout(layout)
            self.setModal(True)
            self.update_selection_box()
        except Exception as e:
            logging.error(f"Error in SelectionDialog.__init__: {e}", exc_info=True)

    def update_selection_box(self):
        try:
            for i, label in enumerate(self.labels):
                if isinstance(label, OutlinedLabel):
                    label.set_highlight(i == self.selected_index)
                else:
                    # For plain QLabel, set background color and text color directly
                    palette = label.palette()
                    if i == self.selected_index:
                        palette.setColor(QPalette.ColorRole.Window, QColor("#F6EB61"))
                        palette.setColor(QPalette.ColorRole.WindowText, QColor("#222"))
                        label.setAutoFillBackground(True)
                    else:
                        palette.setColor(QPalette.ColorRole.Window, Qt.GlobalColor.transparent)
                        palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
                        label.setAutoFillBackground(False)
                    label.setPalette(palette)
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
            index = self.selected_index
            value = self.options[index][0]
            if self.on_select_callback:
                self.on_select_callback(value, index)
            self.accept()
        except Exception as e:
            logging.error(f"Error in SelectionDialog.activate_selected: {e}", exc_info=True)

    def paintEvent(self, event):
        # Draw rounded background for the dialog
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        painter.setBrush(self._bg_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, self._border_radius, self._border_radius)
        super().paintEvent(event)

class StationStatusDialog(QDialog):
    station_selected = pyqtSignal(int)

    def __init__(self, parent=None, station_enabled=None, bg_colors=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.setMinimumWidth(800)
        self.setMinimumHeight(320)
        self._bg_color = QColor("#222")
        self._border_radius = 24

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
                color=STATION_COLORS[i],
                connected=station_enabled[i],
                enabled=station_enabled[i],
                weight_text=None
            )
            self.station_boxes.append(box_widget)

            frame = QFrame()
            frame.setObjectName(f"stationFrame_{i}")
            frame.setFrameShape(QFrame.Shape.StyledPanel)
            frame.setLineWidth(0)
            frame.setLayout(QVBoxLayout())
            frame.layout().setContentsMargins(1, 1, 1, 1)
            frame.layout().setAlignment(Qt.AlignmentFlag.AlignCenter)
            frame.layout().addWidget(box_widget)
            frame.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
            self.station_frames.append(frame)
            stations_layout.addWidget(frame)
        layout.addLayout(stations_layout)

        # Accept button
        self.accept_label = OutlinedLabel("ACCEPT", font_size=28, bold=True, color="#fff")
        self.accept_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.accept_label.setFixedWidth(220)
        self.accept_label.setMinimumHeight(72)
        layout.addWidget(self.accept_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.setLayout(layout)
        self.setModal(True)
        self.update_selection_box()

    def update_selection_box(self):
        # Highlight station frames by setting a property and using paintEvent
        for i, frame in enumerate(self.station_frames):
            if self.selected_index == i:
                frame.setProperty("highlighted", True)
                frame.update()
            else:
                frame.setProperty("highlighted", False)
                frame.update()
        # Highlight accept button
        self.accept_label.set_highlight(self.selected_index == self.num_stations)

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

    def paintEvent(self, event):
        # Draw rounded background for the dialog
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        painter.setBrush(self._bg_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, self._border_radius, self._border_radius)
        super().paintEvent(event)

class OverlayWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self._border_color = QColor("#CD0A0A")
        self._border_radius = 32
        self._border_width = 8
        self._bg_color = QColor(0, 0, 0, 180)  # semi-transparent black

        self.label = QLabel("", self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setFont(QFont("Arial", 64, QFont.Weight.Bold))
        label_palette = self.label.palette()
        label_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
        self.label.setPalette(label_palette)

        layout = QVBoxLayout(self)
        layout.addWidget(self.label)
        self.setLayout(layout)
        self.hide()

    def show_overlay(self, html, color="#CD0A0A"):
        self.label.setText(html)
        self._border_color = QColor(color)
        self.resize(self.parent().size())
        self.move(0, 0)
        self.show()
        self.raise_()

    def hide_overlay(self):
        self.hide()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        # Draw semi-transparent background
        painter.setBrush(self._bg_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, self._border_radius, self._border_radius)
        # Draw border
        painter.setPen(QPen(self._border_color, self._border_width))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect.adjusted(
            self._border_width // 2, self._border_width // 2,
            -self._border_width // 2, -self._border_width // 2
        ), self._border_radius, self._border_radius)
        super().paintEvent(event)

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
        style=None
    ):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*margins)
        layout.setSpacing(spacing)
        self.labels = []
        for icon in icons:
            lbl = QLabel(icon)
            lbl.setFont(QFont("Arial", font_size, QFont.Weight.Bold))
            lbl.setAlignment(align)
            lbl.setFixedWidth(fixed_width)
            lbl.setMinimumHeight(48)
            # Set text color and background using palette and paintEvent
            palette = lbl.palette()
            palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
            lbl.setPalette(palette)
            self.labels.append(lbl)
            layout.addWidget(lbl)
        layout.addStretch(1)
        self.setLayout(layout)

    def flash_icon(self, index, flash_color="#11BD33", duration=150):
        """
        Flash the icon at the given index with the specified color for a short duration.
        """
        if not (0 <= index < len(self.labels)):
            return
        label = self.labels[index]
        original_palette = label.palette()
        flash_palette = QPalette()
        flash_palette.setColor(QPalette.ColorRole.WindowText, QColor(flash_color))
        label.setPalette(flash_palette)
        label_ref = weakref.ref(label)
        def restore_palette():
            lbl = label_ref()
            if lbl is not None:
                lbl.setPalette(original_palette)
        QTimer.singleShot(duration, restore_palette)

class StartupWizardDialog(QDialog):
    def __init__(self, parent=None, num_stations=4, on_station_verified=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.setFixedSize(1024, 600)
        self.num_stations = num_stations

        # Step tracking
        self.current_step = 0
        self.selection_index = 0
        self.station_enabled = [True] * num_stations
        self.station_connected = [True] * num_stations
        self.station_names = [f"Station {i+1}" for i in range(num_stations)]
        self.weight_texts = ["--"] * num_stations
        self.selection_indices = []
        self.on_station_verified = on_station_verified

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(24, 16, 24, 16)
        main_layout.setSpacing(8)

        # Main label
        self.main_label = QLabel("Welcome to Paint Machine")
        self.main_label.setFont(QFont("Arial", 36, QFont.Weight.Bold))
        self.main_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_palette = self.main_label.palette()
        main_palette.setColor(QPalette.ColorRole.WindowText, QColor("#eee"))  # Light grey
        self.main_label.setPalette(main_palette)
        main_layout.addWidget(self.main_label)

        # Info/Prompt area
        self.info_label = QLabel("Startup Info ....")
        self.info_label.setFont(QFont("Arial", 22))
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.info_label.setMinimumHeight(150)
        self.info_label.setMaximumHeight(150)
        info_palette = self.info_label.palette()
        info_palette.setColor(QPalette.ColorRole.WindowText, QColor("#eee"))  # Light grey
        self.info_label.setPalette(info_palette)
        main_layout.addWidget(self.info_label)

        # Station boxes row
        stations_layout = QHBoxLayout()
        stations_layout.setSpacing(10)
        self.station_boxes = []
        self.station_frames = []
        for i in range(self.num_stations):
            box = StationBoxWidget(
                station_index=i,
                name=f"Station {i+1}",
                color=STATION_COLORS[i],
                connected=True,
                enabled=True,
                weight_text="--",
                parent=self
            )
            box.setMinimumWidth(216)
            box.setMinimumHeight(110)
            box.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Expanding)
            self.station_boxes.append(box)
            frame = QFrame()
            frame.setObjectName(f"stationFrame_{i}")
            frame.setFrameShape(QFrame.Shape.StyledPanel)
            frame.setLineWidth(0)
            frame.setLayout(QVBoxLayout())
            frame.layout().setContentsMargins(1, 1, 1, 1)
            frame.layout().setAlignment(Qt.AlignmentFlag.AlignCenter)
            frame.layout().addWidget(box)
            frame.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
            # Set frame color/border using palette and paintEvent
            self.station_frames.append(frame)
            stations_layout.addWidget(frame)
        main_layout.addLayout(stations_layout, stretch=2)

        main_layout.addStretch(1)

        self.accept_label = OutlinedLabel(
            "CONTINUE",
            font_size=48,
            bold=True,
            color="#fff",          # White infill
            bg_color=None,         # Transparent background
            border_radius=16,
            padding=8
        )
        self.accept_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.accept_label.setMinimumHeight(72)
        self.accept_label.setFixedWidth(360)
        self.accept_label.set_highlight(False)  # Always use white infill
        main_layout.addWidget(self.accept_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Right-side: button labels
        button_column = ButtonColumnWidget(
            icons=["▲", "⏎", "▼"],
            font_size=28,
            fixed_width=56,
            margins=(0, 20, 0, 0),
            spacing=36,
            align=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            parent=self
        )

        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(0, 0, 0,  0)
        h_layout.setSpacing(0)
        h_layout.addLayout(main_layout, stretch=10)
        h_layout.addWidget(button_column, stretch=0)
        self.setLayout(h_layout)

        self.button_column = button_column

        self.step_mode = "station_select"
        self.update_selection_indices()
        self.selection_index = self.selection_indices.index("accept")  # Always start on "accept"
        self.update_highlight()
        self.update_station_widgets()

    @property
    def station_widgets(self):
        return self.station_boxes

    def set_main_label(self, text):
        self.main_label.setText(text)

    def set_info_text(self, text):
        self.info_label.setText(text)

    def set_station_labels(self, names=None, connected=None, enabled=None, weight_texts=None):
        if names:
            self.station_names = names
        if connected:
            self.station_connected = connected
        if enabled:
            self.station_enabled = enabled
        if weight_texts:
            self.weight_texts = weight_texts
        self.update_station_widgets()

    def update_station_widgets(self):
        for i, box in enumerate(self.station_boxes):
            if self.station_names and i < len(self.station_names):
                box.name_label.setText(self.station_names[i])
            if box.connected_label:
                box.connected_label.setText("CONNECTED" if self.station_connected[i] else "DISCONNECTED")
                box.set_connected(self.station_connected[i], STATION_COLORS[i % len(STATION_COLORS)])
            if self.station_enabled and i < len(self.station_enabled):
                if box.enabled_label:
                    box.enabled_label.setText("ENABLED" if self.station_enabled[i] else "DISABLED")
                    box.set_enabled(self.station_enabled[i], STATION_COLORS[i % len(STATION_COLORS)])
            # Weight
            weight = "--"
            if self.weight_texts and i < len(self.weight_texts) and self.weight_texts[i] is not None:
                weight = self.weight_texts[i]
            if box.weight_label:
                box.set_weight(weight)
        self.update_highlight()

    def set_weight(self, station_index, current_weight, target_weight=None, unit="g"):
        if 0 <= station_index < len(self.station_boxes):
            box = self.station_boxes[station_index]
            if box.weight_label:
                if unit == "g":
                    new_text = f"{int(round(current_weight))} g"
                else:
                    oz = current_weight / 28.3495
                    new_text = f"{oz:.1f} oz"
                box.set_weight(new_text)
                self.weight_texts[station_index] = new_text

    def set_step(self, step):
        self.current_step = step
        self.update_selection_indices()
        self.selection_index = self.selection_indices.index("accept")  # Always start on "accept"
        if step == 0:
            self.step_mode = "station_select"
        elif step in (1, 2, 3):
            self.step_mode = "accept_only"  # Change to accept_only for other steps

    def update_selection_indices(self):
        self.selection_indices = [i for i, c in enumerate(self.station_connected) if c]
        self.selection_indices.append("accept")
        if self.selection_index >= len(self.selection_indices):
            self.selection_index = len(self.selection_indices) - 1

    def select_next(self):
        if self.current_step == 0 and self.step_mode == "station_select":
            self.update_selection_indices()
            self.selection_index = (self.selection_index + 1) % len(self.selection_indices)
            self.update_highlight()
        elif self.step_mode == "accept_only":
            self.selection_index = 0
            self.update_highlight()

    def select_prev(self):
        if self.current_step == 0 and self.step_mode == "station_select":
            self.update_selection_indices()
            self.selection_index = (self.selection_index - 1) % len(self.selection_indices)
            self.update_highlight()
        elif self.step_mode == "accept_only":
            self.selection_index = 0
            self.update_highlight()

   
    def activate_selected(self):
        if self.current_step == 0 and self.step_mode == "station_select":
            self.update_selection_indices()
            sel = self.selection_indices[self.selection_index]
            parent = self.parent()
            if sel == "accept":
                print("[DEBUG] Station verification accepted, moving to next step (do not close wizard)")
                if self.on_station_verified:
                    self.on_station_verified()
                return
            # Toggle enabled state for the selected station
            self.station_enabled[sel] = not self.station_enabled[sel]

            if hasattr(parent, "station_enabled"):
                parent.station_enabled[sel] = self.station_enabled[sel]
            if self.station_boxes[sel].enabled_label:
                self.station_boxes[sel].enabled_label.setText("ENABLED" if self.station_enabled[sel] else "DISABLED")
                self.station_boxes[sel].set_enabled(self.station_enabled[sel], STATION_COLORS[sel % len(STATION_COLORS)])
            self.update_highlight()
        elif self.step_mode == "accept_only":
            print(f"[DEBUG] Step {self.current_step} accepted, advancing to step {self.current_step + 1}")
            if self.current_step >= self.last_step:  # Define self.last_step appropriately
                print("[DEBUG] Last step reached, closing wizard.")
                self.accept()
            else:
                self.set_step(self.current_step + 1)

    def get_station_enabled(self):
        return self.station_enabled

    def update_highlight(self):
        if not self.selection_indices or self.selection_index >= len(self.selection_indices):
            return
        for i, frame in enumerate(self.station_frames):
            if self.selection_indices[self.selection_index] == i:
                # Animate highlight for selected frame
                # Instead of stylesheet, set a property and use paintEvent for highlight
                frame.setProperty("highlighted", True)
                frame.update()
            else:
                frame.setProperty("highlighted", False)
                frame.update()
        # For the CONTINUE button, you can set a property and update its style
        if self.selection_indices[self.selection_index] == "accept":
            self.accept_label.set_highlight(True)
        else:
            self.accept_label.set_highlight(False)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        painter.setBrush(QColor("#222"))  # Dark grey background
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(rect)
        super().paintEvent(event)

# Add this to QFrame subclass or monkey-patch QFrame if you want to handle highlight in paintEvent:
def frame_paintEvent(self, event):
    painter = QPainter(self)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    rect = self.rect()
    highlighted = self.property("highlighted") if self.property("highlighted") is not None else False
    if highlighted:
        painter.setBrush(QColor("#F6EB61"))
        painter.setPen(QPen(QColor("#F6EB61"), 4))
    else:
        painter.setBrush(QColor("#222"))
        painter.setPen(QPen(QColor("#ccc"), 2))
    painter.drawRoundedRect(rect, 14, 14)
    QFrame.paintEvent(self, event)