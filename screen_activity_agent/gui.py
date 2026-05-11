from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from PySide6.QtCore import QDate, QObject, QRectF, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSizePolicy,
    QSpinBox,
    QStatusBar,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from screen_activity_agent.agent import ScreenActivityAgent
from screen_activity_agent.config import (
    ApiProfile,
    Settings,
    delete_api_profile,
    load_api_profiles,
    load_settings,
    save_api_profiles,
    save_settings_to_env,
    upsert_api_profile,
)
from screen_activity_agent.logs import (
    ALL_CATEGORIES_LABEL,
    category_label,
    category_options,
    export_items_to_csv,
    export_items_to_json,
    filter_items_by_category,
    format_day_log,
    format_minutes,
    load_events,
    load_raw_records,
    save_events,
    save_raw_records,
    today_summary,
)
from screen_activity_agent.models import ActivityRecord
from screen_activity_agent.reports import render_report_text


APP_STYLESHEET = """
QMainWindow, QDialog {
    background: #f4f6fb;
    color: #172033;
    font-family: "Microsoft YaHei UI", "Segoe UI";
    font-size: 13px;
}
QTabWidget::pane {
    border: 0;
    background: #f4f6fb;
}
QTabBar::tab {
    background: transparent;
    color: #667085;
    padding: 11px 16px;
    margin: 4px 2px 0 2px;
    border-radius: 6px;
}
QTabBar::tab:selected {
    background: #ffffff;
    color: #1457d9;
    font-weight: 600;
}
QFrame#panel {
    background: #ffffff;
    border: 1px solid #e4e8f0;
    border-radius: 8px;
}
QLabel#pageTitle {
    color: #111827;
    font-size: 22px;
    font-weight: 700;
}
QLabel#sectionTitle {
    color: #172033;
    font-size: 15px;
    font-weight: 700;
}
QLabel#muted {
    color: #667085;
}
QLabel#metricValue {
    color: #111827;
    font-size: 22px;
    font-weight: 700;
}
QLabel#metricTitle {
    color: #667085;
    font-size: 12px;
}
QLabel#statusPill {
    background: #eef4ff;
    color: #1457d9;
    border: 1px solid #c7d7fe;
    border-radius: 8px;
    padding: 6px 10px;
    font-weight: 600;
}
QPushButton {
    background: #ffffff;
    border: 1px solid #cfd7e6;
    border-radius: 6px;
    padding: 7px 12px;
    color: #172033;
}
QPushButton:hover {
    background: #f8fbff;
    border-color: #9eb4dc;
}
QPushButton#primaryButton {
    background: #1457d9;
    border-color: #1457d9;
    color: #ffffff;
    font-weight: 600;
}
QPushButton#dangerButton {
    color: #b42318;
    border-color: #f1b4ad;
}
QPushButton:disabled {
    background: #eef1f6;
    color: #98a2b3;
    border-color: #d8dee9;
}
QLineEdit, QSpinBox, QDateEdit, QComboBox {
    background: #ffffff;
    border: 1px solid #cfd7e6;
    border-radius: 6px;
    min-height: 30px;
    padding: 2px 8px;
}
QPlainTextEdit, QTableWidget {
    background: #ffffff;
    border: 1px solid #e4e8f0;
    border-radius: 8px;
    color: #172033;
    selection-background-color: #dbe8ff;
    selection-color: #111827;
}
QTableWidget {
    gridline-color: #edf0f5;
    alternate-background-color: #f9fbff;
}
QHeaderView::section {
    background: #f6f8fc;
    color: #475467;
    border: 0;
    border-bottom: 1px solid #e4e8f0;
    padding: 8px;
    font-weight: 600;
}
QStatusBar {
    background: #ffffff;
    color: #667085;
    border-top: 1px solid #e4e8f0;
}
"""

CATEGORY_COLORS = [
    "#1457d9",
    "#0f9f8f",
    "#9a5bdf",
    "#d97706",
    "#dc3f64",
    "#2f6f4e",
    "#64748b",
    "#c2410c",
]


def _category_primary(category: Any) -> str:
    if isinstance(category, list) and category and str(category[0]).strip():
        return str(category[0]).strip()
    return "未知"


def _event_minutes(event: dict[str, Any]) -> int:
    try:
        return max(0, int(event.get("duration_minutes", 0)))
    except (TypeError, ValueError):
        return 0


def _category_totals(events: list[dict[str, Any]]) -> Counter[str]:
    totals: Counter[str] = Counter()
    for event in events:
        minutes = _event_minutes(event)
        if minutes > 0:
            totals[_category_primary(event.get("category"))] += minutes
    return totals


def _summary_for_date(data_dir: Path, date_text: str) -> tuple[int, Counter[str], int]:
    events = load_events(data_dir, date_text)
    totals = _category_totals(events)
    return sum(totals.values()), totals, len(events)


def _period_bounds(anchor: date, period: str) -> tuple[date, date]:
    if period == "day":
        return anchor, anchor
    if period == "week":
        start = anchor - timedelta(days=anchor.weekday())
        return start, start + timedelta(days=6)
    if period == "month":
        start = anchor.replace(day=1)
        if anchor.month == 12:
            end = date(anchor.year + 1, 1, 1) - timedelta(days=1)
        else:
            end = date(anchor.year, anchor.month + 1, 1) - timedelta(days=1)
        return start, end
    if period == "last7":
        return anchor - timedelta(days=6), anchor
    if period == "last30":
        return anchor - timedelta(days=29), anchor
    return anchor, anchor


def _iter_dates(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _period_events(data_dir: Path, anchor: date, period: str) -> list[dict[str, Any]]:
    start, end = _period_bounds(anchor, period)
    events: list[dict[str, Any]] = []
    for current in _iter_dates(start, end):
        events.extend(load_events(data_dir, current.isoformat()))
    return events


def _panel(*, margins: tuple[int, int, int, int] = (18, 16, 18, 16)) -> QFrame:
    frame = QFrame()
    frame.setObjectName("panel")
    frame.setFrameShape(QFrame.Shape.NoFrame)
    frame.setContentsMargins(*margins)
    return frame


def _page_title(title: str, subtitle: str = "") -> tuple[QWidget, QLabel]:
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 4)
    layout.setSpacing(3)
    title_label = QLabel(title)
    title_label.setObjectName("pageTitle")
    layout.addWidget(title_label)
    subtitle_label = QLabel(subtitle)
    subtitle_label.setObjectName("muted")
    subtitle_label.setWordWrap(True)
    layout.addWidget(subtitle_label)
    return widget, subtitle_label


def _metric_card(title: str, value: str = "-", accent: str = "#1457d9") -> tuple[QFrame, QLabel]:
    frame = _panel(margins=(14, 12, 14, 12))
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(5)
    title_label = QLabel(title)
    title_label.setObjectName("metricTitle")
    value_label = QLabel(value)
    value_label.setObjectName("metricValue")
    value_label.setWordWrap(True)
    accent_line = QFrame()
    accent_line.setFixedHeight(3)
    accent_line.setStyleSheet(f"background: {accent}; border-radius: 2px;")
    layout.addWidget(title_label)
    layout.addWidget(value_label)
    layout.addStretch(1)
    layout.addWidget(accent_line)
    return frame, value_label


class CategoryBarsWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.totals: Counter[str] = Counter()
        self.setMinimumHeight(190)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_totals(self, totals: Counter[str]) -> None:
        self.totals = Counter({name: minutes for name, minutes in totals.items() if minutes > 0})
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#ffffff"))
        total = sum(self.totals.values())
        painter.setPen(QColor("#667085"))
        if total <= 0:
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "暂无统计数据")
            return

        items = self.totals.most_common(6)
        left = 96
        minutes_col = 118
        percent_col = 58
        right = minutes_col + percent_col + 28
        top = 18
        row_h = 25
        bar_h = 9
        max_value = max(minutes for _name, minutes in items)
        width = max(80, self.width() - left - right)
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)
        for index, (name, minutes) in enumerate(items):
            y = top + index * row_h
            color = QColor(CATEGORY_COLORS[index % len(CATEGORY_COLORS)])
            painter.setPen(QColor("#344054"))
            painter.drawText(8, y + 13, name[:12])
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#eef2f8"))
            painter.drawRoundedRect(QRectF(left, y + 5, width, bar_h), 4, 4)
            bar_w = width * minutes / max_value if max_value else 0
            painter.setBrush(color)
            painter.drawRoundedRect(QRectF(left, y + 5, bar_w, bar_h), 4, 4)
            painter.setPen(QColor("#667085"))
            pct = minutes * 100 / total
            painter.drawText(
                QRectF(left + width + 10, y, minutes_col - 10, row_h),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                format_minutes(minutes),
            )
            painter.drawText(
                QRectF(left + width + minutes_col + 10, y, percent_col, row_h),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{pct:.1f}%",
            )


def _mask_api_key(api_key: str) -> str:
    key = api_key.strip()
    if not key:
        return "未填写"
    if len(key) <= 10:
        return f"{key[:2]}...{key[-2:]}"
    return f"{key[:6]}...{key[-4:]}"


class ProfileDialog(QDialog):
    def __init__(
        self,
        existing_names: set[str],
        *,
        title: str,
        profile: ApiProfile | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.existing_names = {name.casefold() for name in existing_names}
        self.original_name = profile.name.casefold() if profile else None
        self.setWindowTitle(title)
        self.resize(520, 220)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name_input = QLineEdit()
        self.api_key_input = QLineEdit()
        self.api_key_input.setReadOnly(profile is not None)
        self.base_url_input = QLineEdit()
        self.model_input = QLineEdit()
        self._api_key_value = profile.api_key if profile else ""
        if profile is None:
            self.api_key_input.setPlaceholderText("输入完整 API Key")

        if profile:
            self.name_input.setText(profile.name)
            self.api_key_input.setText(_mask_api_key(profile.api_key))
            self.base_url_input.setText(profile.base_url)
            self.model_input.setText(profile.model)

        self.copy_api_key_button = QPushButton("复制")
        self.copy_api_key_button.clicked.connect(self.copy_api_key)
        self.change_api_key_button = QPushButton("更换")
        self.change_api_key_button.clicked.connect(self.enable_api_key_edit)
        api_key_row = QHBoxLayout()
        api_key_row.addWidget(self.api_key_input, 1)
        api_key_row.addWidget(self.copy_api_key_button)
        api_key_row.addWidget(self.change_api_key_button)
        self.copy_api_key_button.setEnabled(bool(self._api_key_value))
        self.change_api_key_button.setEnabled(profile is not None)

        form.addRow("配置名称", self.name_input)
        form.addRow("OPENAI_API_KEY", api_key_row)
        form.addRow("API Base URL", self.base_url_input)
        form.addRow("模型", self.model_input)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("保存")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)

        layout.addLayout(form)
        layout.addWidget(buttons)

    def validate_and_accept(self) -> None:
        name = self.name_input.text().strip()
        api_key = self.api_key_input.text().strip()
        if self._api_key_value:
            api_key = self._api_key_value
        base_url = self.base_url_input.text().strip()
        model = self.model_input.text().strip()
        if not name or not api_key or not base_url or not model:
            QMessageBox.warning(self, "配置不完整", "配置名称、API Key、URL 和模型都必须填写。")
            return
        normalized_name = name.casefold()
        if normalized_name in self.existing_names and normalized_name != self.original_name:
            QMessageBox.warning(self, "配置名称重复", "配置名称不能和已有配置重复。")
            return
        self.accept()

    def profile(self) -> ApiProfile:
        return ApiProfile(
            name=self.name_input.text().strip(),
            api_key=self._api_key_value or self.api_key_input.text().strip(),
            base_url=self.base_url_input.text().strip(),
            model=self.model_input.text().strip(),
        )

    @Slot()
    def copy_api_key(self) -> None:
        if not self._api_key_value:
            QMessageBox.information(self, "没有 API Key", "当前配置没有可复制的 API Key。")
            return
        QApplication.clipboard().setText(self._api_key_value)
        QMessageBox.information(self, "已复制", "完整 API Key 已复制到剪贴板。")

    @Slot()
    def enable_api_key_edit(self) -> None:
        self._api_key_value = ""
        self.api_key_input.clear()
        self.api_key_input.setReadOnly(False)
        self.api_key_input.setPlaceholderText("输入新的完整 API Key")
        self.copy_api_key_button.setEnabled(False)
        self.api_key_input.setFocus()


class EventEditDialog(QDialog):
    def __init__(self, event: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("编辑合并事件")
        self.resize(520, 240)
        self.original = event

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.start_input = QLineEdit(str(event.get("start", "")))
        self.end_input = QLineEdit(str(event.get("end", "")))
        self.category_input = QLineEdit(category_label(event.get("category")))
        self.event_input = QLineEdit(str(event.get("event", "")))
        self.duration_input = QSpinBox()
        self.duration_input.setRange(1, 24 * 60)
        self.duration_input.setValue(max(1, int(event.get("duration_minutes", 1) or 1)))
        self.privacy_checkbox = QCheckBox("隐私风险")
        self.privacy_checkbox.setChecked(bool(event.get("privacy_risk", False)))

        form.addRow("开始时间 HH:mm", self.start_input)
        form.addRow("结束时间 HH:mm", self.end_input)
        form.addRow("分类，用 / 分隔", self.category_input)
        form.addRow("事件描述", self.event_input)
        form.addRow("时长", self.duration_input)
        form.addRow("", self.privacy_checkbox)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("保存")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addLayout(form)
        layout.addWidget(buttons)

    def updated_event(self) -> dict[str, Any]:
        item = dict(self.original)
        item["start"] = self.start_input.text().strip() or item.get("start", "--:--")
        item["end"] = self.end_input.text().strip() or item.get("end", "--:--")
        item["category"] = [part.strip() for part in self.category_input.text().split("/") if part.strip()] or ["未知"]
        item["event"] = self.event_input.text().strip() or "未知活动"
        item["duration_minutes"] = self.duration_input.value()
        item["privacy_risk"] = self.privacy_checkbox.isChecked()
        return item


class AgentWorker(QObject):
    result_ready = Signal(dict)
    error_ready = Signal(str)
    status_ready = Signal(str)

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings
        self.agent = ScreenActivityAgent(settings)
        self.timer: QTimer | None = None

    @Slot()
    def start(self) -> None:
        if not self.settings.is_complete:
            self.error_ready.emit("API Key、URL 或模型未配置完整，无法开始记录。")
            self.status_ready.emit("已暂停")
            return
        if self.timer is None:
            self.timer = QTimer(self)
            self.timer.setInterval(self.settings.interval_seconds * 1000)
            self.timer.timeout.connect(self.analyze_once)
        self.status_ready.emit("运行中")
        self.analyze_once()
        self.timer.start()

    @Slot()
    def pause(self) -> None:
        if self.timer:
            self.timer.stop()
        self.status_ready.emit("已暂停")

    @Slot()
    def stop(self) -> None:
        if self.timer:
            self.timer.stop()
        self.status_ready.emit("已暂停")

    @Slot()
    def analyze_once(self) -> None:
        if not self.settings.is_complete:
            self.error_ready.emit("API Key、URL 或模型未配置完整，无法识别。")
            return
        try:
            record: ActivityRecord = self.agent.analyze_once()
        except Exception as exc:
            self.error_ready.emit(str(exc))
            return
        self.result_ready.emit(record.to_dict())


class MainWindow(QMainWindow):
    start_requested = Signal()
    pause_requested = Signal()
    once_requested = Signal()

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings
        self.thread: QThread | None = None
        self.worker: AgentWorker | None = None
        self.profiles: list[ApiProfile] = []
        self.active_profile: str | None = None

        self.setWindowTitle("屏幕活动记录 Agent")
        self.resize(1180, 800)
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.setStyleSheet(APP_STYLESHEET)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self._build_dashboard_tab()
        self._build_timeline_tab()
        self._build_statistics_tab()
        self._build_records_tab()
        self._build_logs_tab()
        self._build_settings_tab()
        self.reload_profiles()
        self._start_worker()
        self.refresh_config_labels()
        self.refresh_all_data_views()

        if not self.settings.is_complete:
            self.tabs.setCurrentWidget(self.settings_tab)
            self.statusBar().showMessage("请先配置 API Key、URL 和模型。")
            QMessageBox.information(self, "需要配置", "请先在配置页添加并应用完整的 API 配置。")

    def _build_dashboard_tab(self) -> None:
        self.dashboard_tab = QWidget()
        layout = QVBoxLayout(self.dashboard_tab)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(14)

        header, _subtitle = _page_title("首页", "查看运行状态、今日记录概览和最近一次识别结果。")
        layout.addWidget(header)

        self.status_label = QLabel("状态：已暂停")
        self.status_label.setObjectName("statusPill")
        self.key_label = QLabel()
        self.model_label = QLabel()
        self.base_url_label = QLabel()
        self.last_time_label = QLabel("最近识别：无")
        self.current_label = QLabel("当前活动：无")
        self.current_label.setWordWrap(True)
        self.today_duration_label = QLabel("今日已记录时长：0 分钟")
        self.today_share_label = QLabel("今日主要分类占比：暂无记录")
        self.today_share_label.setWordWrap(True)

        metric_row = QGridLayout()
        metric_row.setHorizontalSpacing(12)
        self.status_card, self.status_value = _metric_card("运行状态", "已暂停", "#1457d9")
        self.duration_card, self.duration_value = _metric_card("今日已记录", "0 分钟", "#0f9f8f")
        self.main_category_card, self.main_category_value = _metric_card("今日主要分类", "暂无记录", "#9a5bdf")
        self.last_seen_card, self.last_seen_value = _metric_card("最近识别", "无", "#d97706")
        metric_row.addWidget(self.status_card, 0, 0)
        metric_row.addWidget(self.duration_card, 0, 1)
        metric_row.addWidget(self.main_category_card, 0, 2)
        metric_row.addWidget(self.last_seen_card, 0, 3)
        layout.addLayout(metric_row)

        config_panel = _panel()
        config_layout = QGridLayout(config_panel)
        config_layout.setContentsMargins(18, 14, 18, 14)
        config_layout.setHorizontalSpacing(18)
        config_layout.setVerticalSpacing(8)
        config_layout.addWidget(QLabel("运行信息"), 0, 0)
        config_layout.itemAtPosition(0, 0).widget().setObjectName("sectionTitle")
        config_layout.addWidget(self.status_label, 0, 1)
        config_layout.addWidget(self.key_label, 1, 0)
        config_layout.addWidget(self.model_label, 1, 1)
        config_layout.addWidget(self.base_url_label, 1, 2)
        config_layout.addWidget(self.last_time_label, 2, 0)
        config_layout.addWidget(self.current_label, 2, 1, 1, 2)
        config_layout.addWidget(self.today_duration_label, 3, 0)
        config_layout.addWidget(self.today_share_label, 3, 1, 1, 2)

        chart_panel = _panel()
        chart_layout = QVBoxLayout(chart_panel)
        chart_layout.setContentsMargins(18, 14, 18, 14)
        chart_title = QLabel("今日分类占比")
        chart_title.setObjectName("sectionTitle")
        self.dashboard_bars = CategoryBarsWidget()
        chart_layout.addWidget(chart_title)
        chart_layout.addWidget(self.dashboard_bars)

        self.result_text = QPlainTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setPlaceholderText("识别结果会显示在这里。")
        self.result_text.setMinimumHeight(180)

        self.start_button = QPushButton("开始记录")
        self.start_button.setObjectName("primaryButton")
        self.pause_button = QPushButton("暂停")
        self.once_button = QPushButton("手动识别一次")

        button_row = QHBoxLayout()
        for button in (self.start_button, self.pause_button, self.once_button):
            button_row.addWidget(button)
        button_row.addStretch(1)

        result_panel = _panel()
        result_layout = QVBoxLayout(result_panel)
        result_layout.setContentsMargins(18, 14, 18, 14)
        result_title = QLabel("最近一次识别结果")
        result_title.setObjectName("sectionTitle")
        result_layout.addWidget(result_title)
        result_layout.addWidget(self.result_text, 1)

        layout.addWidget(config_panel)
        layout.addWidget(chart_panel)
        layout.addLayout(button_row)
        layout.addWidget(result_panel, 1)

        self.start_button.clicked.connect(self._start_clicked)
        self.pause_button.clicked.connect(self.pause_requested.emit)
        self.once_button.clicked.connect(self._once_clicked)
        self.tabs.addTab(self.dashboard_tab, "首页")

    def _build_timeline_tab(self) -> None:
        self.timeline_tab = QWidget()
        layout = QVBoxLayout(self.timeline_tab)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(14)

        header, _subtitle = _page_title("时间线", "按日期和分类查看合并后的活动记录。")
        layout.addWidget(header)

        toolbar = _panel(margins=(12, 10, 12, 10))
        row = QHBoxLayout()
        row.setContentsMargins(12, 8, 12, 8)
        self.timeline_date = QDateEdit()
        self.timeline_date.setCalendarPopup(True)
        self.timeline_date.setDate(QDate.currentDate())
        self.timeline_category = QComboBox()
        self.timeline_category.addItem(ALL_CATEGORIES_LABEL)
        self.refresh_timeline_button = QPushButton("刷新")
        row.addWidget(QLabel("日期"))
        row.addWidget(self.timeline_date)
        row.addWidget(QLabel("分类"))
        row.addWidget(self.timeline_category)
        row.addWidget(self.refresh_timeline_button)
        row.addStretch(1)
        toolbar.setLayout(row)

        self.timeline_table = QTableWidget(0, 5)
        self.timeline_table.setHorizontalHeaderLabels(["开始", "结束", "分类", "事件", "时长"])
        self.timeline_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.timeline_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.timeline_table.horizontalHeader().setStretchLastSection(False)
        self.timeline_table.verticalHeader().setVisible(False)
        self.timeline_table.setAlternatingRowColors(True)
        self.timeline_table.setShowGrid(False)
        self.timeline_table.setWordWrap(False)
        self.timeline_table.setSortingEnabled(True)
        self.timeline_table.setMinimumHeight(460)

        content_panel = _panel()
        content_layout = QVBoxLayout(content_panel)
        content_layout.setContentsMargins(18, 14, 18, 14)
        content_title = QLabel("完整时间线")
        content_title.setObjectName("sectionTitle")
        content_layout.addWidget(content_title)
        content_layout.addWidget(self.timeline_table, 1)

        layout.addWidget(toolbar)
        layout.addWidget(content_panel, 1)
        self.refresh_timeline_button.clicked.connect(self.refresh_timeline)
        self.timeline_date.dateChanged.connect(self.refresh_timeline)
        self.timeline_category.currentTextChanged.connect(self.refresh_timeline)
        self.tabs.addTab(self.timeline_tab, "时间线")

    def _build_statistics_tab(self) -> None:
        self.statistics_tab = QWidget()
        layout = QVBoxLayout(self.statistics_tab)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(14)

        header, _subtitle = _page_title("统计", "查看日、周、月以及滚动周期的分类占比和主要活动。")
        layout.addWidget(header)

        toolbar = _panel(margins=(12, 10, 12, 10))
        row = QHBoxLayout()
        row.setContentsMargins(12, 8, 12, 8)
        self.statistics_date = QDateEdit()
        self.statistics_date.setCalendarPopup(True)
        self.statistics_date.setDate(QDate.currentDate())
        self.statistics_period = QComboBox()
        self.statistics_period.addItems(["day", "week", "month", "last7", "last30"])
        self.refresh_statistics_button = QPushButton("刷新统计")
        row.addWidget(QLabel("日期"))
        row.addWidget(self.statistics_date)
        row.addWidget(QLabel("周期"))
        row.addWidget(self.statistics_period)
        row.addWidget(self.refresh_statistics_button)
        row.addStretch(1)
        toolbar.setLayout(row)

        summary_row = QGridLayout()
        summary_row.setHorizontalSpacing(12)
        self.stat_total_card, self.stat_total_value = _metric_card("总记录时长", "0 分钟", "#1457d9")
        self.stat_top_card, self.stat_top_value = _metric_card("占比最高分类", "暂无记录", "#0f9f8f")
        self.stat_unknown_card, self.stat_unknown_value = _metric_card("未知占比", "0.0%", "#d97706")
        summary_row.addWidget(self.stat_total_card, 0, 0)
        summary_row.addWidget(self.stat_top_card, 0, 1)
        summary_row.addWidget(self.stat_unknown_card, 0, 2)

        chart_panel = _panel()
        chart_layout = QVBoxLayout(chart_panel)
        chart_layout.setContentsMargins(18, 14, 18, 14)
        chart_title = QLabel("分类占比图")
        chart_title.setObjectName("sectionTitle")
        self.statistics_bars = CategoryBarsWidget()
        chart_layout.addWidget(chart_title)
        chart_layout.addWidget(self.statistics_bars)

        self.statistics_text = QPlainTextEdit()
        self.statistics_text.setReadOnly(True)
        self.statistics_text.setMinimumHeight(260)

        report_panel = _panel()
        report_layout = QVBoxLayout(report_panel)
        report_layout.setContentsMargins(18, 14, 18, 14)
        report_title = QLabel("文本报表")
        report_title.setObjectName("sectionTitle")
        report_layout.addWidget(report_title)
        report_layout.addWidget(self.statistics_text, 1)

        layout.addWidget(toolbar)
        layout.addLayout(summary_row)
        layout.addWidget(chart_panel)
        layout.addWidget(report_panel, 1)
        self.refresh_statistics_button.clicked.connect(self.refresh_statistics)
        self.statistics_date.dateChanged.connect(self.refresh_statistics)
        self.statistics_period.currentTextChanged.connect(self.refresh_statistics)
        self.tabs.addTab(self.statistics_tab, "统计")

    def _build_records_tab(self) -> None:
        self.records_tab = QWidget()
        layout = QVBoxLayout(self.records_tab)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(14)

        header, _subtitle = _page_title("记录管理", "查看、编辑、删除和导出本地记录。")
        layout.addWidget(header)

        toolbar = _panel(margins=(12, 10, 12, 10))
        row = QHBoxLayout()
        row.setContentsMargins(12, 8, 12, 8)
        self.records_date = QDateEdit()
        self.records_date.setCalendarPopup(True)
        self.records_date.setDate(QDate.currentDate())
        self.records_category = QComboBox()
        self.records_category.addItem(ALL_CATEGORIES_LABEL)
        self.refresh_records_button = QPushButton("刷新")
        self.view_record_button = QPushButton("查看详情")
        self.edit_event_button = QPushButton("编辑合并事件")
        self.delete_record_button = QPushButton("删除选中")
        self.delete_record_button.setObjectName("dangerButton")
        self.export_json_button = QPushButton("导出 JSON")
        self.export_csv_button = QPushButton("导出 CSV")
        for widget in (
            QLabel("日期"),
            self.records_date,
            QLabel("分类"),
            self.records_category,
            self.refresh_records_button,
            self.view_record_button,
            self.edit_event_button,
            self.delete_record_button,
            self.export_json_button,
            self.export_csv_button,
        ):
            row.addWidget(widget)
        row.addStretch(1)
        toolbar.setLayout(row)

        self.records_tabs = QTabWidget()
        self.events_table = QTableWidget(0, 7)
        self.events_table.setHorizontalHeaderLabels(["开始", "结束", "分类", "事件", "时长", "置信度", "隐私"])
        self.raw_table = QTableWidget(0, 7)
        self.raw_table.setHorizontalHeaderLabels(["时间", "分类", "事件", "应用", "窗口", "置信度", "隐私"])
        for table in (self.events_table, self.raw_table):
            table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            table.horizontalHeader().setStretchLastSection(False)
            table.verticalHeader().setVisible(False)
            table.setAlternatingRowColors(True)
            table.setShowGrid(False)
            table.setWordWrap(False)
            table.setSortingEnabled(True)
            table.setMinimumHeight(300)
        self._configure_records_columns()
        self.records_tabs.addTab(self.events_table, "合并事件")
        self.records_tabs.addTab(self.raw_table, "原始识别")

        self.record_detail = QPlainTextEdit()
        self.record_detail.setReadOnly(True)
        self.record_detail.setMaximumHeight(170)
        self.record_detail.setPlaceholderText("选中一条记录后可查看完整 JSON。")

        tables_panel = _panel()
        tables_layout = QVBoxLayout(tables_panel)
        tables_layout.setContentsMargins(18, 14, 18, 14)
        tables_title = QLabel("记录列表")
        tables_title.setObjectName("sectionTitle")
        tables_layout.addWidget(tables_title)
        tables_layout.addWidget(self.records_tabs, 1)

        detail_panel = _panel()
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(18, 14, 18, 14)
        detail_title = QLabel("记录详情")
        detail_title.setObjectName("sectionTitle")
        detail_layout.addWidget(detail_title)
        detail_layout.addWidget(self.record_detail)

        layout.addWidget(toolbar)
        layout.addWidget(tables_panel, 1)
        layout.addWidget(detail_panel)

        self.refresh_records_button.clicked.connect(self.refresh_records)
        self.view_record_button.clicked.connect(self.show_selected_record_detail)
        self.edit_event_button.clicked.connect(self.edit_selected_event)
        self.delete_record_button.clicked.connect(self.delete_selected_record)
        self.export_json_button.clicked.connect(lambda: self.export_records("json"))
        self.export_csv_button.clicked.connect(lambda: self.export_records("csv"))
        self.records_date.dateChanged.connect(self.refresh_records)
        self.records_category.currentTextChanged.connect(self.refresh_records)
        self.events_table.itemSelectionChanged.connect(self.show_selected_record_detail)
        self.raw_table.itemSelectionChanged.connect(self.show_selected_record_detail)
        self.tabs.addTab(self.records_tab, "记录管理")

    def _build_logs_tab(self) -> None:
        self.logs_tab = QWidget()
        layout = QVBoxLayout(self.logs_tab)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(14)

        header, _subtitle = _page_title("日志", "按日期查看原始识别记录和合并事件的文本摘要。")
        layout.addWidget(header)

        toolbar = _panel(margins=(12, 10, 12, 10))
        row = QHBoxLayout()
        row.setContentsMargins(12, 8, 12, 8)
        self.log_date = QDateEdit()
        self.log_date.setCalendarPopup(True)
        self.log_date.setDate(QDate.currentDate())
        self.refresh_logs_button = QPushButton("刷新日志")
        row.addWidget(QLabel("日期"))
        row.addWidget(self.log_date)
        row.addWidget(self.refresh_logs_button)
        row.addStretch(1)
        toolbar.setLayout(row)

        self.logs_text = QPlainTextEdit()
        self.logs_text.setReadOnly(True)

        log_panel = _panel()
        log_layout = QVBoxLayout(log_panel)
        log_layout.setContentsMargins(18, 14, 18, 14)
        log_title = QLabel("日志内容")
        log_title.setObjectName("sectionTitle")
        log_layout.addWidget(log_title)
        log_layout.addWidget(self.logs_text, 1)

        layout.addWidget(toolbar)
        layout.addWidget(log_panel, 1)
        self.refresh_logs_button.clicked.connect(self.refresh_logs)
        self.log_date.dateChanged.connect(self.refresh_logs)
        self.tabs.addTab(self.logs_tab, "日志")

    def _build_settings_tab(self) -> None:
        self.settings_tab = QWidget()
        layout = QVBoxLayout(self.settings_tab)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(14)

        header, _subtitle = _page_title("配置", "管理 API 配置档案、记录间隔、数据目录和隐私相关开关。")
        layout.addWidget(header)

        settings_panel = _panel()
        settings_layout = QVBoxLayout(settings_panel)
        settings_layout.setContentsMargins(18, 14, 18, 14)
        settings_title = QLabel("运行设置")
        settings_title.setObjectName("sectionTitle")
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        self.active_profile_label = QLabel("未应用保存的配置")
        self.active_profile_label.setWordWrap(True)
        self.interval_input = QSpinBox()
        self.interval_input.setRange(5, 3600)
        self.interval_input.setValue(self.settings.interval_seconds)
        self.data_dir_input = QLineEdit(str(self.settings.data_dir))
        self.browse_data_dir_button = QPushButton("选择目录")
        data_dir_row = QHBoxLayout()
        data_dir_row.addWidget(self.data_dir_input, 1)
        data_dir_row.addWidget(self.browse_data_dir_button)

        self.save_raw_screenshot_checkbox = QCheckBox("保存原始截图")
        self.save_raw_screenshot_checkbox.setChecked(self.settings.save_raw_screenshot)
        self.privacy_checkbox = QCheckBox("隐私保护")
        self.privacy_checkbox.setChecked(self.settings.privacy_protection_enabled)
        self.sensitive_filter_checkbox = QCheckBox("敏感内容过滤")
        self.sensitive_filter_checkbox.setChecked(self.settings.sensitive_content_filter_enabled)
        self.autostart_checkbox = QCheckBox("开机自启")
        self.autostart_checkbox.setChecked(self.settings.autostart_enabled)

        form.addRow("当前配置名称", self.active_profile_label)
        form.addRow("截图间隔（秒）", self.interval_input)
        form.addRow("数据保存目录", data_dir_row)
        form.addRow("", self.save_raw_screenshot_checkbox)
        form.addRow("", self.privacy_checkbox)
        form.addRow("", self.sensitive_filter_checkbox)
        form.addRow("", self.autostart_checkbox)

        settings_layout.addWidget(settings_title)
        settings_layout.addLayout(form)

        self.add_profile_button = QPushButton("添加 API 配置")
        self.add_profile_button.setObjectName("primaryButton")
        self.profile_list_layout = QVBoxLayout()
        self.profile_list_layout.setSpacing(8)
        self.save_settings_button = QPushButton("保存设置")
        self.save_settings_button.setObjectName("primaryButton")
        self.config_hint = QLabel(f"配置文件：{self.settings.env_path}")
        self.config_hint.setWordWrap(True)
        self.config_hint.setObjectName("muted")
        self.data_hint = QLabel(f"数据目录：{self.settings.data_dir}")
        self.data_hint.setWordWrap(True)
        self.data_hint.setObjectName("muted")

        profiles_panel = _panel()
        profiles_layout = QVBoxLayout(profiles_panel)
        profiles_layout.setContentsMargins(18, 14, 18, 14)
        profiles_title = QLabel("已保存 API 配置")
        profiles_title.setObjectName("sectionTitle")
        profiles_layout.addWidget(profiles_title)
        profiles_layout.addLayout(self.profile_list_layout)
        profiles_layout.addWidget(self.add_profile_button)

        footer_panel = _panel()
        footer_layout = QVBoxLayout(footer_panel)
        footer_layout.setContentsMargins(18, 14, 18, 14)
        footer_layout.addWidget(self.save_settings_button)
        footer_layout.addWidget(self.config_hint)
        footer_layout.addWidget(self.data_hint)

        layout.addWidget(settings_panel)
        layout.addWidget(profiles_panel, 1)
        layout.addWidget(footer_panel)
        layout.addStretch(1)

        self.browse_data_dir_button.clicked.connect(self.browse_data_dir)
        self.add_profile_button.clicked.connect(self.add_profile)
        self.save_settings_button.clicked.connect(self.save_settings)
        self.tabs.addTab(self.settings_tab, "配置")

    def _start_worker(self) -> None:
        self.thread = QThread()
        self.worker = AgentWorker(self.settings)
        self.worker.moveToThread(self.thread)
        self.start_requested.connect(self.worker.start)
        self.pause_requested.connect(self.worker.pause)
        self.once_requested.connect(self.worker.analyze_once)
        self.worker.result_ready.connect(self.show_result)
        self.worker.error_ready.connect(self.show_error)
        self.worker.status_ready.connect(self.set_status)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.start()

    def _restart_worker(self) -> None:
        if self.worker:
            self.worker.stop()
        if self.thread:
            self.thread.quit()
            self.thread.wait(3000)
        self._start_worker()

    def _require_complete_config(self) -> bool:
        if self.settings.is_complete:
            return True
        self.tabs.setCurrentWidget(self.settings_tab)
        QMessageBox.warning(self, "配置不完整", "请先配置 API Key、URL 和模型。")
        return False

    def _start_clicked(self) -> None:
        if self._require_complete_config():
            self.start_requested.emit()

    def _once_clicked(self) -> None:
        if self._require_complete_config():
            self.once_requested.emit()

    def refresh_config_labels(self) -> None:
        self.key_label.setText(f"OPENAI_API_KEY：{'已配置' if self.settings.has_api_key else '未配置'}")
        self.model_label.setText(f"模型：{self.settings.model if self.settings.has_model_config else '未配置'}")
        self.base_url_label.setText(
            f"API Base URL：{self.settings.base_url if self.settings.has_base_url_config else '未配置'}"
        )

    def refresh_dashboard_summary(self) -> None:
        date_text = QDate.currentDate().toString("yyyy-MM-dd")
        duration_text, share_text = today_summary(self.settings.data_dir, date_text)
        _total_minutes, totals, event_count = _summary_for_date(self.settings.data_dir, date_text)
        self.today_duration_label.setText(f"今日已记录时长：{duration_text}")
        self.today_share_label.setText(f"今日主要分类占比：{share_text}")
        self.duration_value.setText(duration_text)
        top_text = "暂无记录"
        if totals:
            top_name, top_minutes = totals.most_common(1)[0]
            top_text = f"{top_name} · {format_minutes(top_minutes)}"
        self.main_category_value.setText(top_text)
        self.dashboard_bars.set_totals(totals)
        self.last_seen_value.setText(f"{event_count} 条事件")

    def refresh_all_data_views(self) -> None:
        self.refresh_dashboard_summary()
        self.refresh_timeline()
        self.refresh_statistics()
        self.refresh_records()
        self.refresh_logs()

    def refresh_visible_data_views(self) -> None:
        self.refresh_dashboard_summary()
        current = self.tabs.currentWidget()
        if current is self.timeline_tab:
            self.refresh_timeline()
        elif current is self.statistics_tab:
            self.refresh_statistics()
        elif current is self.records_tab:
            self.refresh_records()
        elif current is self.logs_tab:
            self.refresh_logs()

    def reload_profiles(self) -> None:
        self.profiles, self.active_profile = load_api_profiles(self.settings.env_path)
        self._refresh_active_profile_label()
        while self.profile_list_layout.count():
            item = self.profile_list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        if not self.profiles:
            empty_label = QLabel("暂无保存的 API 配置。")
            empty_label.setStyleSheet("color: #666;")
            self.profile_list_layout.addWidget(empty_label)
            return
        for profile in self.profiles:
            self.profile_list_layout.addWidget(self._build_profile_row(profile))

    def _refresh_active_profile_label(self) -> None:
        if hasattr(self, "active_profile_label"):
            self.active_profile_label.setText(self.active_profile or "未应用保存的配置")

    def _refresh_category_filter(self, combo: QComboBox, date_text: str) -> None:
        options = [ALL_CATEGORIES_LABEL] + category_options(self.settings.data_dir, date_text)
        current = combo.currentText()
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(options)
        if current in options:
            combo.setCurrentText(current)
        combo.blockSignals(False)

    def _build_profile_row(self, profile: ApiProfile) -> QWidget:
        row = _panel(margins=(10, 8, 10, 8))
        layout = QHBoxLayout(row)
        layout.setContentsMargins(10, 8, 10, 8)

        name_label = QLabel(profile.name)
        name_label.setMinimumWidth(180)
        model_label = QLabel(f"{profile.base_url} / {profile.model}")
        model_label.setStyleSheet("color: #555;")
        model_label.setWordWrap(True)

        apply_button = QPushButton("已应用" if profile.name == self.active_profile else "应用")
        apply_button.setMinimumWidth(86)
        if profile.name == self.active_profile:
            apply_button.setEnabled(False)
            apply_button.setStyleSheet(
                "QPushButton:disabled { background: #1f7a34; color: white; font-weight: 700; "
                "border: 1px solid #155724; }"
            )
        else:
            apply_button.clicked.connect(lambda _checked=False, item=profile: self.apply_profile(item))

        edit_button = QPushButton("修改")
        edit_button.clicked.connect(lambda _checked=False, item=profile: self.edit_profile(item))
        delete_button = QPushButton("删除")
        delete_button.setObjectName("dangerButton")
        delete_button.clicked.connect(lambda _checked=False, item=profile: self.delete_profile(item))

        layout.addWidget(name_label)
        layout.addWidget(apply_button)
        layout.addWidget(model_label, 1)
        layout.addWidget(edit_button)
        layout.addWidget(delete_button)
        return row

    @Slot()
    def add_profile(self) -> None:
        dialog = ProfileDialog({profile.name for profile in self.profiles}, title="添加 API 配置", parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        profile = dialog.profile()
        upsert_api_profile(self.settings.env_path, profile, make_active=False)
        self.reload_profiles()
        self.statusBar().showMessage(f"API 配置已添加：{profile.name}")

    def edit_profile(self, profile: ApiProfile) -> None:
        existing_names = {item.name for item in self.profiles if item.name != profile.name}
        dialog = ProfileDialog(existing_names, title="修改 API 配置", profile=profile, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        updated = dialog.profile()
        was_active = profile.name == self.active_profile
        upsert_api_profile(self.settings.env_path, updated, make_active=was_active)
        if was_active:
            self._apply_values(
                api_key=updated.api_key,
                base_url=updated.base_url,
                model=updated.model,
                interval_seconds=self.interval_input.value(),
                active_profile=updated.name,
            )
        else:
            self.reload_profiles()
        self.statusBar().showMessage(f"API 配置已修改：{updated.name}")

    def apply_profile(self, profile: ApiProfile) -> None:
        self._apply_values(
            api_key=profile.api_key,
            base_url=profile.base_url,
            model=profile.model,
            interval_seconds=self.interval_input.value(),
            active_profile=profile.name,
        )
        QMessageBox.information(self, "配置已应用", f"已切换到 API 配置：{profile.name}")

    def delete_profile(self, profile: ApiProfile) -> None:
        reply = QMessageBox.question(self, "删除配置", f"确定删除 API 配置“{profile.name}”？")
        if reply != QMessageBox.StandardButton.Yes:
            return
        delete_api_profile(self.settings.env_path, profile.name)
        self.reload_profiles()
        self.statusBar().showMessage("API 配置已删除。")

    @Slot()
    def browse_data_dir(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "选择数据保存目录", self.data_dir_input.text().strip())
        if selected:
            self.data_dir_input.setText(selected)

    @Slot()
    def save_settings(self) -> None:
        api_key = (self.settings.api_key or "").strip()
        base_url = self.settings.base_url.strip()
        model = self.settings.model.strip()
        if not api_key or not base_url or not model:
            QMessageBox.warning(self, "配置不完整", "请先添加并应用一个完整的 API 配置。")
            return
        self._apply_values(
            api_key=api_key,
            base_url=base_url,
            model=model,
            interval_seconds=self.interval_input.value(),
            active_profile=self.active_profile,
        )
        QMessageBox.information(self, "设置已保存", "设置已保存，新的记录任务会使用最新配置。")

    def _apply_values(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        interval_seconds: int,
        active_profile: str | None,
    ) -> None:
        save_settings_to_env(
            env_path=self.settings.env_path,
            api_key=api_key,
            base_url=base_url,
            model=model,
            interval_seconds=interval_seconds,
            data_dir=self.data_dir_input.text().strip() or self.settings.data_dir,
            save_raw_screenshot=self.save_raw_screenshot_checkbox.isChecked(),
            privacy_protection_enabled=self.privacy_checkbox.isChecked(),
            sensitive_content_filter_enabled=self.sensitive_filter_checkbox.isChecked(),
            autostart_enabled=self.autostart_checkbox.isChecked(),
        )
        if active_profile:
            profiles, _active = load_api_profiles(self.settings.env_path)
            save_api_profiles(self.settings.env_path, profiles, active_profile)
        self.settings = load_settings(self.settings.env_path.parent)
        self.config_hint.setText(f"配置文件：{self.settings.env_path}")
        self.data_hint.setText(f"数据目录：{self.settings.data_dir}")
        self.interval_input.setValue(self.settings.interval_seconds)
        self.data_dir_input.setText(str(self.settings.data_dir))
        self.save_raw_screenshot_checkbox.setChecked(self.settings.save_raw_screenshot)
        self.privacy_checkbox.setChecked(self.settings.privacy_protection_enabled)
        self.sensitive_filter_checkbox.setChecked(self.settings.sensitive_content_filter_enabled)
        self.autostart_checkbox.setChecked(self.settings.autostart_enabled)
        self.refresh_config_labels()
        self.reload_profiles()
        self.refresh_all_data_views()
        self._restart_worker()
        self.statusBar().showMessage("设置已保存。")

    @Slot()
    def refresh_logs(self) -> None:
        date_text = self.log_date.date().toString("yyyy-MM-dd")
        self.logs_text.setPlainText(format_day_log(self.settings.data_dir, date_text))

    @Slot()
    def refresh_timeline(self) -> None:
        date_text = self.timeline_date.date().toString("yyyy-MM-dd")
        category = self.timeline_category.currentText()
        self._refresh_category_filter(self.timeline_category, date_text)
        events = filter_items_by_category(load_events(self.settings.data_dir, date_text), category)
        self._populate_timeline_table(events)

    @Slot()
    def refresh_statistics(self) -> None:
        from datetime import date as _date

        date_text = self.statistics_date.date().toString("yyyy-MM-dd")
        period = self.statistics_period.currentText()
        anchor = _date.fromisoformat(date_text)
        report = render_report_text(self.settings.data_dir, anchor, period)
        self.statistics_text.setPlainText(report)
        events = _period_events(self.settings.data_dir, anchor, period)
        totals = _category_totals(events)
        total_minutes = sum(totals.values())
        self.stat_total_value.setText(format_minutes(total_minutes))
        if totals and total_minutes:
            top_name, top_minutes = totals.most_common(1)[0]
            self.stat_top_value.setText(f"{top_name} · {top_minutes * 100 / total_minutes:.1f}%")
        else:
            self.stat_top_value.setText("暂无记录")
        unknown_minutes = totals.get("未知", 0)
        unknown_pct = unknown_minutes * 100 / total_minutes if total_minutes else 0.0
        self.stat_unknown_value.setText(f"{unknown_pct:.1f}%")
        self.statistics_bars.set_totals(totals)

    @Slot()
    def refresh_records(self) -> None:
        date_text = self.records_date.date().toString("yyyy-MM-dd")
        self._refresh_category_filter(self.records_category, date_text)
        category = self.records_category.currentText()
        events = filter_items_by_category(load_events(self.settings.data_dir, date_text), category)
        raw_records = filter_items_by_category(load_raw_records(self.settings.data_dir, date_text), category)
        self._populate_events_table(events)
        self._populate_raw_table(raw_records)
        self.record_detail.clear()

    def _set_item(self, table: QTableWidget, row: int, column: int, text: str, payload: Any | None = None) -> None:
        item = QTableWidgetItem(text)
        if payload is not None:
            item.setData(Qt.ItemDataRole.UserRole, payload)
        table.setItem(row, column, item)

    def _configure_records_columns(self) -> None:
        event_widths = [80, 80, 210, 360, 90, 90, 70]
        raw_widths = [170, 210, 330, 120, 170, 90, 70]
        for table, widths, stretch_column in (
            (self.events_table, event_widths, 3),
            (self.raw_table, raw_widths, 2),
        ):
            header = table.horizontalHeader()
            for index, width in enumerate(widths):
                header.setSectionResizeMode(index, QHeaderView.ResizeMode.Interactive)
                table.setColumnWidth(index, width)
            header.setSectionResizeMode(stretch_column, QHeaderView.ResizeMode.Stretch)

    def _configure_timeline_columns(self) -> None:
        widths = [90, 90, 240, 520, 100]
        header = self.timeline_table.horizontalHeader()
        for index, width in enumerate(widths):
            header.setSectionResizeMode(index, QHeaderView.ResizeMode.Interactive)
            self.timeline_table.setColumnWidth(index, width)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

    def _populate_timeline_table(self, events: list[dict[str, Any]]) -> None:
        self.timeline_table.setSortingEnabled(False)
        self.timeline_table.clearContents()
        self.timeline_table.setRowCount(len(events))
        for row, event in enumerate(events):
            minutes = int(event.get("duration_minutes", 0) or 0)
            self._set_item(self.timeline_table, row, 0, str(event.get("start", "--:--")), event)
            self._set_item(self.timeline_table, row, 1, str(event.get("end", "--:--")))
            self._set_item(self.timeline_table, row, 2, category_label(event.get("category")))
            self._set_item(self.timeline_table, row, 3, str(event.get("event", "未知活动")))
            self._set_item(self.timeline_table, row, 4, format_minutes(minutes))
        self._configure_timeline_columns()
        self.timeline_table.setSortingEnabled(True)
        if events:
            self.timeline_table.scrollToBottom()

    def _populate_events_table(self, events: list[dict[str, Any]]) -> None:
        self.events_table.setSortingEnabled(False)
        self.events_table.clearContents()
        self.events_table.setRowCount(len(events))
        for row, event in enumerate(events):
            minutes = int(event.get("duration_minutes", 0) or 0)
            self._set_item(self.events_table, row, 0, str(event.get("start", "--:--")), event)
            self._set_item(self.events_table, row, 1, str(event.get("end", "--:--")))
            self._set_item(self.events_table, row, 2, category_label(event.get("category")))
            self._set_item(self.events_table, row, 3, str(event.get("event", "未知活动")))
            self._set_item(self.events_table, row, 4, format_minutes(minutes))
            self._set_item(self.events_table, row, 5, str(event.get("confidence", 0)))
            self._set_item(self.events_table, row, 6, "是" if event.get("privacy_risk") else "否")
        self._configure_records_columns()
        self.events_table.setSortingEnabled(True)

    def _populate_raw_table(self, records: list[dict[str, Any]]) -> None:
        self.raw_table.setSortingEnabled(False)
        self.raw_table.clearContents()
        self.raw_table.setRowCount(len(records))
        for row, record in enumerate(records):
            self._set_item(self.raw_table, row, 0, str(record.get("timestamp", "未知时间")), record)
            self._set_item(self.raw_table, row, 1, category_label(record.get("category")))
            self._set_item(self.raw_table, row, 2, str(record.get("event", "未知活动")))
            self._set_item(self.raw_table, row, 3, str(record.get("app", "未知")))
            self._set_item(self.raw_table, row, 4, str(record.get("window_title", "未知")))
            self._set_item(self.raw_table, row, 5, str(record.get("confidence", 0)))
            self._set_item(self.raw_table, row, 6, "是" if record.get("privacy_risk") else "否")
        self._configure_records_columns()
        self.raw_table.setSortingEnabled(True)

    def _selected_payload(self) -> tuple[str, int, dict[str, Any]] | None:
        table = self.events_table if self.records_tabs.currentWidget() is self.events_table else self.raw_table
        rows = table.selectionModel().selectedRows()
        if not rows:
            return None
        row = rows[0].row()
        item = table.item(row, 0)
        payload = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not isinstance(payload, dict):
            return None
        return ("events" if table is self.events_table else "raw", row, payload)

    @Slot()
    def show_selected_record_detail(self) -> None:
        selected = self._selected_payload()
        if selected is None:
            return
        _kind, _row, payload = selected
        self.record_detail.setPlainText(json.dumps(payload, ensure_ascii=False, indent=2))

    @Slot()
    def edit_selected_event(self) -> None:
        selected = self._selected_payload()
        if selected is None or selected[0] != "events":
            QMessageBox.information(self, "未选择合并事件", "请先在“合并事件”表格中选择一条记录。")
            return
        _kind, _row, selected_event = selected
        date_text = self.records_date.date().toString("yyyy-MM-dd")
        events = load_events(self.settings.data_dir, date_text)
        event_index = self._find_item_index(events, selected_event)
        if event_index is None:
            QMessageBox.warning(self, "记录不存在", "当前记录已变化，请刷新后再试。")
            return
        dialog = EventEditDialog(events[event_index], self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        events[event_index] = dialog.updated_event()
        save_events(self.settings.data_dir, date_text, events)
        self.refresh_all_data_views()
        self.statusBar().showMessage("合并事件已更新。")

    @Slot()
    def delete_selected_record(self) -> None:
        selected = self._selected_payload()
        if selected is None:
            QMessageBox.information(self, "未选择记录", "请先选择一条记录。")
            return
        kind, _row, payload = selected
        reply = QMessageBox.question(self, "删除记录", "确定删除选中的记录？此操作会修改本地记录文件。")
        if reply != QMessageBox.StandardButton.Yes:
            return
        date_text = self.records_date.date().toString("yyyy-MM-dd")
        if kind == "events":
            items = load_events(self.settings.data_dir, date_text)
            index = self._find_item_index(items, payload)
            if index is not None:
                del items[index]
                save_events(self.settings.data_dir, date_text, items)
        else:
            items = load_raw_records(self.settings.data_dir, date_text)
            index = self._find_item_index(items, payload)
            if index is not None:
                del items[index]
                save_raw_records(self.settings.data_dir, date_text, items)
        self.refresh_all_data_views()
        self.statusBar().showMessage("记录已删除。")

    def _find_item_index(self, items: list[dict[str, Any]], target: dict[str, Any]) -> int | None:
        target_text = json.dumps(target, ensure_ascii=False, sort_keys=True)
        for index, item in enumerate(items):
            if json.dumps(item, ensure_ascii=False, sort_keys=True) == target_text:
                return index
        return None

    @Slot()
    def export_records(self, file_type: str) -> None:
        date_text = self.records_date.date().toString("yyyy-MM-dd")
        category = self.records_category.currentText()
        table_is_events = self.records_tabs.currentWidget() is self.events_table
        items = load_events(self.settings.data_dir, date_text) if table_is_events else load_raw_records(self.settings.data_dir, date_text)
        items = filter_items_by_category(items, category)
        if not items:
            QMessageBox.information(self, "没有可导出记录", "当前筛选条件下没有记录。")
            return
        kind = "events" if table_is_events else "raw"
        default_name = f"{date_text}-{kind}.{file_type}"
        filters = "JSON 文件 (*.json)" if file_type == "json" else "CSV 文件 (*.csv)"
        path_text, _selected_filter = QFileDialog.getSaveFileName(self, "导出记录", default_name, filters)
        if not path_text:
            return
        path = Path(path_text)
        if file_type == "json":
            export_items_to_json(path, items)
        else:
            export_items_to_csv(path, items)
        self.statusBar().showMessage(f"记录已导出：{path}")

    @Slot(str)
    def set_status(self, status: str) -> None:
        self.status_label.setText(f"状态：{status}")
        self.status_value.setText(status)
        if status == "运行中":
            self.status_label.setStyleSheet(
                "background: #ecfdf3; color: #027a48; border: 1px solid #abefc6; "
                "border-radius: 8px; padding: 6px 10px; font-weight: 600;"
            )
        else:
            self.status_label.setStyleSheet(
                "background: #eef4ff; color: #1457d9; border: 1px solid #c7d7fe; "
                "border-radius: 8px; padding: 6px 10px; font-weight: 600;"
            )
        self.statusBar().showMessage(status)

    @Slot(str)
    def show_error(self, message: str) -> None:
        self.statusBar().showMessage(f"错误：{message}")
        self.result_text.setPlainText(f"识别失败：{message}")

    @Slot(dict)
    def show_result(self, result: dict) -> None:
        category = category_label(result.get("category"))
        event = result.get("event", "未知活动")
        timestamp = result.get("timestamp", "未知")
        self.last_time_label.setText(f"最近识别：{timestamp}")
        self.last_seen_value.setText(str(timestamp).replace("T", " ")[:16])
        self.current_label.setText(f"当前活动：{category} —— {event}")
        self.result_text.setPlainText(json.dumps(result, ensure_ascii=False, indent=2))
        self.statusBar().showMessage("识别完成")
        self.refresh_visible_data_views()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.worker:
            self.worker.stop()
        if self.thread:
            self.thread.quit()
            self.thread.wait(3000)
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    settings = load_settings(Path.cwd())
    window = MainWindow(settings)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
