from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6.QtCore import QDate, QObject, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSpinBox,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from screen_activity_agent.agent import ScreenActivityAgent
from screen_activity_agent.config import (
    ApiProfile,
    delete_api_profile,
    load_api_profiles,
    load_settings,
    save_api_profiles,
    save_settings_to_env,
    upsert_api_profile,
    Settings,
)
from screen_activity_agent.logs import format_day_log
from screen_activity_agent.models import ActivityRecord


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
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.base_url_input = QLineEdit()
        self.model_input = QLineEdit()

        if profile:
            self.name_input.setText(profile.name)
            self.api_key_input.setText(profile.api_key)
            self.base_url_input.setText(profile.base_url)
            self.model_input.setText(profile.model)

        form.addRow("配置名称", self.name_input)
        form.addRow("OPENAI_API_KEY", self.api_key_input)
        form.addRow("API Base URL", self.base_url_input)
        form.addRow("模型", self.model_input)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setText("保存")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        self.buttons.accepted.connect(self.validate_and_accept)
        self.buttons.rejected.connect(self.reject)

        layout.addLayout(form)
        layout.addWidget(self.buttons)

    def validate_and_accept(self) -> None:
        name = self.name_input.text().strip()
        api_key = self.api_key_input.text().strip()
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
            api_key=self.api_key_input.text().strip(),
            base_url=self.base_url_input.text().strip(),
            model=self.model_input.text().strip(),
        )


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
        self.resize(920, 680)
        self.setStatusBar(QStatusBar())

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self._build_dashboard_tab()
        self._build_logs_tab()
        self._build_settings_tab()
        self.reload_profiles()
        self._start_worker()
        self.refresh_config_labels()
        self.refresh_logs()

        if not self.settings.is_complete:
            self.tabs.setCurrentWidget(self.settings_tab)
            self.statusBar().showMessage("请先配置 API Key、URL 和模型。")
            QMessageBox.information(self, "需要配置", "请先在配置页添加并应用完整的 API 配置。")

    def _build_dashboard_tab(self) -> None:
        self.dashboard_tab = QWidget()
        layout = QVBoxLayout(self.dashboard_tab)

        self.status_label = QLabel("状态：已暂停")
        self.key_label = QLabel()
        self.model_label = QLabel()
        self.base_url_label = QLabel()
        self.last_time_label = QLabel("最近识别：无")
        self.current_label = QLabel("当前活动：无")
        self.current_label.setWordWrap(True)

        self.result_text = QPlainTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setPlaceholderText("识别结果会显示在这里。")

        self.start_button = QPushButton("开始记录")
        self.pause_button = QPushButton("暂停")
        self.once_button = QPushButton("手动识别一次")

        button_row = QHBoxLayout()
        for button in (
            self.start_button,
            self.pause_button,
            self.once_button,
        ):
            button_row.addWidget(button)

        layout.addWidget(self.status_label)
        layout.addWidget(self.key_label)
        layout.addWidget(self.model_label)
        layout.addWidget(self.base_url_label)
        layout.addWidget(self.last_time_label)
        layout.addWidget(self.current_label)
        layout.addLayout(button_row)
        layout.addWidget(self.result_text, 1)

        self.start_button.clicked.connect(self._start_clicked)
        self.pause_button.clicked.connect(self.pause_requested.emit)
        self.once_button.clicked.connect(self._once_clicked)

        self.tabs.addTab(self.dashboard_tab, "控制台")

    def _build_logs_tab(self) -> None:
        self.logs_tab = QWidget()
        layout = QVBoxLayout(self.logs_tab)

        row = QHBoxLayout()
        self.log_date = QDateEdit()
        self.log_date.setCalendarPopup(True)
        self.log_date.setDate(QDate.currentDate())
        self.refresh_logs_button = QPushButton("刷新日志")
        row.addWidget(QLabel("日期："))
        row.addWidget(self.log_date)
        row.addWidget(self.refresh_logs_button)
        row.addStretch(1)

        self.logs_text = QPlainTextEdit()
        self.logs_text.setReadOnly(True)

        layout.addLayout(row)
        layout.addWidget(self.logs_text, 1)
        self.refresh_logs_button.clicked.connect(self.refresh_logs)
        self.tabs.addTab(self.logs_tab, "日志")

    def _build_settings_tab(self) -> None:
        self.settings_tab = QWidget()
        layout = QVBoxLayout(self.settings_tab)
        form = QFormLayout()

        self.active_profile_label = QLabel("未应用保存的配置")
        self.active_profile_label.setWordWrap(True)
        self.interval_input = QSpinBox()
        self.interval_input.setRange(5, 3600)
        self.interval_input.setValue(self.settings.interval_seconds)

        form.addRow("当前配置名称", self.active_profile_label)
        form.addRow("截图间隔（秒）", self.interval_input)

        self.add_profile_button = QPushButton("添加配置")
        self.add_profile_button.setMinimumHeight(30)
        self.profile_list_layout = QVBoxLayout()
        self.profile_list_layout.setSpacing(8)

        self.save_settings_button = QPushButton("保存截图间隔")
        self.config_hint = QLabel(f"配置文件：{self.settings.env_path}")
        self.config_hint.setWordWrap(True)
        self.data_hint = QLabel(f"数据目录：{self.settings.data_dir}（修改 API 配置不会清空或迁移历史日志）")
        self.data_hint.setWordWrap(True)

        layout.addLayout(form)
        layout.addWidget(QLabel("已保存配置"))
        layout.addLayout(self.profile_list_layout)
        layout.addWidget(self.add_profile_button)
        layout.addWidget(self.save_settings_button)
        layout.addWidget(self.config_hint)
        layout.addWidget(self.data_hint)
        layout.addStretch(1)

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

    def reload_profiles(self) -> None:
        self.profiles, self.active_profile = load_api_profiles(self.settings.env_path)
        self._refresh_active_profile_label()
        while self.profile_list_layout.count():
            item = self.profile_list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        if not self.profiles:
            empty_label = QLabel("暂无保存的配置。")
            empty_label.setStyleSheet("color: #666;")
            self.profile_list_layout.addWidget(empty_label)
            return
        for profile in self.profiles:
            self.profile_list_layout.addWidget(self._build_profile_row(profile))

    def _refresh_active_profile_label(self) -> None:
        if self.active_profile:
            self.active_profile_label.setText(self.active_profile)
        else:
            self.active_profile_label.setText("未应用保存的配置")

    def _build_profile_row(self, profile: ApiProfile) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)

        name_label = QLabel(profile.name)
        name_label.setMinimumWidth(220)
        name_label.setWordWrap(True)

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
            apply_button.setStyleSheet(
                "QPushButton { background: #f7f7f7; color: #111; border: 1px solid #888; }"
                "QPushButton:hover { background: #e8f0fe; }"
            )
            apply_button.clicked.connect(lambda _checked=False, item=profile: self.apply_profile(item))

        edit_button = QPushButton("修改")
        edit_button.setMinimumWidth(72)
        edit_button.clicked.connect(lambda _checked=False, item=profile: self.edit_profile(item))

        delete_button = QPushButton("删除")
        delete_button.setMinimumWidth(72)
        delete_button.clicked.connect(lambda _checked=False, item=profile: self.delete_profile(item))

        layout.addWidget(name_label)
        layout.addWidget(apply_button)
        layout.addWidget(model_label, 1)
        layout.addWidget(delete_button)
        layout.addWidget(edit_button)
        return row

    @Slot()
    def add_profile(self) -> None:
        dialog = ProfileDialog({profile.name for profile in self.profiles}, title="添加配置", parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        profile = dialog.profile()
        upsert_api_profile(self.settings.env_path, profile, make_active=False)
        self.reload_profiles()
        self.statusBar().showMessage(f"API 配置已添加：{profile.name}")

    def edit_profile(self, profile: ApiProfile) -> None:
        existing_names = {item.name for item in self.profiles if item.name != profile.name}
        dialog = ProfileDialog(
            existing_names,
            title="修改配置",
            profile=profile,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        updated = dialog.profile()
        was_active = profile.name == self.active_profile
        upsert_api_profile(self.settings.env_path, updated, make_active=was_active)
        self.reload_profiles()
        if was_active or updated.name == self.active_profile:
            self._apply_values(
                api_key=updated.api_key,
                base_url=updated.base_url,
                model=updated.model,
                interval_seconds=self.interval_input.value(),
                active_profile=updated.name if was_active else self.active_profile,
            )
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
        QMessageBox.information(self, "配置已保存", "截图间隔已保存，新的记录任务会使用最新配置。")
        self.tabs.setCurrentWidget(self.dashboard_tab)

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
        )
        self.settings = load_settings(self.settings.env_path.parent)
        if active_profile:
            profiles, _active = load_api_profiles(self.settings.env_path)
            save_api_profiles(self.settings.env_path, profiles, active_profile)
        self.config_hint.setText(f"配置文件：{self.settings.env_path}")
        self.data_hint.setText(f"数据目录：{self.settings.data_dir}（修改 API 配置不会清空或迁移历史日志）")
        self.interval_input.setValue(self.settings.interval_seconds)
        self.refresh_config_labels()
        self.reload_profiles()
        self._restart_worker()
        self.statusBar().showMessage("配置已保存。")

    @Slot()
    def refresh_logs(self) -> None:
        date_text = self.log_date.date().toString("yyyy-MM-dd")
        self.logs_text.setPlainText(format_day_log(self.settings.data_dir, date_text))

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
        self.refresh_logs()

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
