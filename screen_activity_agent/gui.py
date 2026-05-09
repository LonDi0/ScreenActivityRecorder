from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from screen_activity_agent.agent import ScreenActivityAgent
from screen_activity_agent.config import Settings, load_settings
from screen_activity_agent.models import ActivityRecord


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
        if not self.settings.has_api_key:
            self.error_ready.emit("OPENAI_API_KEY 未配置，无法开始记录。")
            self.status_ready.emit("已停止")
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
        self.status_ready.emit("已停止")

    @Slot()
    def analyze_once(self) -> None:
        if not self.settings.has_api_key:
            self.error_ready.emit("OPENAI_API_KEY 未配置，无法识别。")
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
    stop_requested = Signal()
    once_requested = Signal()

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings
        self.setWindowTitle("屏幕活动记录 Agent")
        self.resize(780, 560)

        self.status_label = QLabel("状态：已停止")
        self.key_label = QLabel(f"OPENAI_API_KEY：{'已配置' if settings.has_api_key else '未配置'}")
        self.model_label = QLabel(f"模型：{settings.model}")
        self.base_url_label = QLabel(f"API Base URL：{settings.base_url}")
        self.capture_label = QLabel(
            f"截图：{'所有屏幕' if settings.screenshot_all_screens else '主屏'}，"
            f"{settings.image_format.upper()}，最大宽度 {settings.screenshot_max_width}px"
        )
        self.last_time_label = QLabel("最近识别：无")
        self.current_label = QLabel("当前活动：无")
        self.current_label.setWordWrap(True)

        self.result_text = QPlainTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setPlaceholderText("识别结果会显示在这里。")

        self.start_button = QPushButton("开始")
        self.pause_button = QPushButton("暂停")
        self.stop_button = QPushButton("停止")
        self.once_button = QPushButton("手动识别一次")

        button_row = QHBoxLayout()
        button_row.addWidget(self.start_button)
        button_row.addWidget(self.pause_button)
        button_row.addWidget(self.stop_button)
        button_row.addWidget(self.once_button)

        layout = QVBoxLayout()
        layout.addWidget(self.status_label)
        layout.addWidget(self.key_label)
        layout.addWidget(self.model_label)
        layout.addWidget(self.base_url_label)
        layout.addWidget(self.capture_label)
        layout.addWidget(self.last_time_label)
        layout.addWidget(self.current_label)
        layout.addLayout(button_row)
        layout.addWidget(self.result_text, 1)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)
        self.setStatusBar(QStatusBar())

        self.start_button.clicked.connect(self._start_clicked)
        self.pause_button.clicked.connect(self.pause_requested.emit)
        self.stop_button.clicked.connect(self.stop_requested.emit)
        self.once_button.clicked.connect(self._once_clicked)

        if not settings.has_api_key:
            self.statusBar().showMessage("OPENAI_API_KEY 未配置，请先在环境变量或 .env 中配置。")

    def _require_key(self) -> bool:
        if self.settings.has_api_key:
            return True
        QMessageBox.warning(self, "API Key 未配置", "OPENAI_API_KEY 未配置，无法调用视觉模型。")
        return False

    def _start_clicked(self) -> None:
        if self._require_key():
            self.start_requested.emit()

    def _once_clicked(self) -> None:
        if self._require_key():
            self.once_requested.emit()

    @Slot(str)
    def set_status(self, status: str) -> None:
        self.status_label.setText(f"状态：{status}")
        self.statusBar().showMessage(status)

    @Slot(str)
    def show_error(self, message: str) -> None:
        self.statusBar().showMessage(f"错误：{message}")
        self.result_text.setPlainText(f"识别失败：{message}")

    @Slot(dict)
    def show_result(self, result: dict) -> None:
        category = " / ".join(result.get("category", ["未知"]))
        event = result.get("event", "未知活动")
        timestamp = result.get("timestamp", "未知")
        self.last_time_label.setText(f"最近识别：{timestamp}")
        self.current_label.setText(f"当前活动：{category} —— {event}")
        self.result_text.setPlainText(json.dumps(result, ensure_ascii=False, indent=2))
        self.statusBar().showMessage("识别完成")

    def closeEvent(self, event) -> None:  # noqa: N802
        self.stop_requested.emit()
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    settings = load_settings(Path.cwd())

    thread = QThread()
    worker = AgentWorker(settings)
    worker.moveToThread(thread)

    window = MainWindow(settings)
    window.start_requested.connect(worker.start)
    window.pause_requested.connect(worker.pause)
    window.stop_requested.connect(worker.stop)
    window.once_requested.connect(worker.analyze_once)
    worker.result_ready.connect(window.show_result)
    worker.error_ready.connect(window.show_error)
    worker.status_ready.connect(window.set_status)

    app.aboutToQuit.connect(worker.stop)
    app.aboutToQuit.connect(thread.quit)
    thread.finished.connect(worker.deleteLater)
    thread.start()

    window.show()
    exit_code = app.exec()
    thread.quit()
    thread.wait(3000)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
