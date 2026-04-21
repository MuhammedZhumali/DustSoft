"""Desktop operator UI built with Tkinter."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from core.application import Application


class DustSoftUI:
    """Multi-screen operator UI for the simplified DustSoft workflow."""

    def __init__(self, app: Application) -> None:
        self.app = app
        self.root = tk.Tk()
        self.root.title("DustSoft Operator Console")
        self.root.geometry("1180x760")
        self.root.minsize(980, 640)
        self._refresh_job: str | None = None

        self.status_var = tk.StringVar(value="Ready")
        self.telemetry_vars = {
            "state": tk.StringVar(value="-"),
            "pressure": tk.StringVar(value="-"),
            "reference": tk.StringVar(value="-"),
            "compressor": tk.StringVar(value="-"),
            "valve": tk.StringVar(value="-"),
            "remote": tk.StringVar(value="-"),
        }
        self.info_vars = {
            "software_version": tk.StringVar(value="-"),
            "data_directory": tk.StringVar(value="-"),
            "settings_file": tk.StringVar(value="-"),
            "log_export_directory": tk.StringVar(value="-"),
            "remote_policy": tk.StringVar(value="-"),
            "device_summary": tk.StringVar(value="-"),
        }

        self.injection_duration_var = tk.StringVar(
            value=str(self.app.injection_settings.duration_seconds)
        )
        self.injection_interval_var = tk.StringVar(
            value=str(self.app.injection_settings.interval_seconds)
        )
        self.injection_count_var = tk.StringVar(value=str(self.app.injection_settings.count))
        self.injection_cycle_var = tk.StringVar(
            value=str(self.app.injection_settings.cycle_seconds)
        )
        self.pressure_min_var = tk.StringVar(value=str(self.app.controller.pressure_min))
        self.pressure_max_var = tk.StringVar(value=str(self.app.controller.pressure_max))
        self.user_parameters_var = tk.StringVar(
            value=", ".join(
                f"{key}={value}" for key, value in sorted(self.app.user_parameters.items())
            )
        )
        self.journal_filter_var = tk.StringVar(value="all")

        self._build_layout()
        self._refresh_all()

    def run(self) -> None:
        self.root.mainloop()

    def _build_layout(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        header = ttk.Frame(self.root, padding=16)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        ttk.Label(
            header,
            text="DustSoft Operator Console",
            font=("Segoe UI", 18, "bold"),
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            textvariable=self.status_var,
            font=("Segoe UI", 10),
        ).grid(row=1, column=0, sticky="w", pady=(6, 0))

        notebook = ttk.Notebook(self.root)
        notebook.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))

        self.main_frame = ttk.Frame(notebook, padding=16)
        self.injection_frame = ttk.Frame(notebook, padding=16)
        self.pressure_frame = ttk.Frame(notebook, padding=16)
        self.journal_frame = ttk.Frame(notebook, padding=16)
        self.info_frame = ttk.Frame(notebook, padding=16)

        notebook.add(self.main_frame, text="Главный")
        notebook.add(self.injection_frame, text="Настройка впрыска")
        notebook.add(self.pressure_frame, text="Настройка давления")
        notebook.add(self.journal_frame, text="Журнал")
        notebook.add(self.info_frame, text="Об установке")

        self._build_main_screen()
        self._build_injection_screen()
        self._build_pressure_screen()
        self._build_journal_screen()
        self._build_info_screen()

    def _build_main_screen(self) -> None:
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=1)

        command_frame = ttk.LabelFrame(self.main_frame, text="Команды", padding=16)
        command_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 8))

        buttons = [
            ("Пуск", lambda: self._invoke_action(self.app.start, "Пуск выполнен")),
            ("Стоп", lambda: self._invoke_action(self.app.stop, "Стоп выполнен")),
            (
                "Аварийная остановка",
                lambda: self._invoke_action(
                    lambda: self.app.emergency_stop("ui_emergency_button"),
                    "Аварийная остановка выполнена",
                ),
            ),
            (
                "Подать пыль",
                lambda: self._invoke_action(
                    self.app.manual_injection,
                    "Команда подачи пыли выполнена",
                ),
            ),
            (
                "Сброс аварии",
                lambda: self._invoke_action(
                    self.app.reset_emergency,
                    "Аварийный режим сброшен",
                ),
            ),
            (
                "Обновить телеметрию",
                lambda: self._invoke_action(self._refresh_all, "Телеметрия обновлена"),
            ),
        ]

        for index, (label, command) in enumerate(buttons):
            ttk.Button(command_frame, text=label, command=command).grid(
                row=index // 2,
                column=index % 2,
                sticky="ew",
                padx=6,
                pady=6,
            )
        for column in range(2):
            command_frame.columnconfigure(column, weight=1)

        telemetry_frame = ttk.LabelFrame(self.main_frame, text="Телеметрия", padding=16)
        telemetry_frame.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=(0, 8))
        telemetry_frame.columnconfigure(1, weight=1)

        rows = [
            ("Состояние", "state"),
            ("Давление, бар", "pressure"),
            ("Эталонный прибор", "reference"),
            ("Компрессор", "compressor"),
            ("Клапан впрыска", "valve"),
            ("Удаленная связь", "remote"),
        ]
        for index, (label, key) in enumerate(rows):
            ttk.Label(telemetry_frame, text=label).grid(row=index, column=0, sticky="w", pady=4)
            ttk.Label(
                telemetry_frame,
                textvariable=self.telemetry_vars[key],
                font=("Segoe UI", 10, "bold"),
            ).grid(row=index, column=1, sticky="w", pady=4, padx=(12, 0))

        hint_frame = ttk.LabelFrame(self.main_frame, text="Индикаторы", padding=16)
        hint_frame.grid(row=1, column=0, columnspan=2, sticky="ew")
        ttk.Label(
            hint_frame,
            text=(
                "Интерфейс обновляет давление, состояние исполнительных устройств и "
                "показания эталонного прибора автоматически раз в секунду."
            ),
            wraplength=900,
            justify="left",
        ).grid(row=0, column=0, sticky="w")

    def _build_injection_screen(self) -> None:
        form = ttk.LabelFrame(self.injection_frame, text="Параметры впрыска", padding=16)
        form.grid(row=0, column=0, sticky="nsew")
        self.injection_frame.columnconfigure(0, weight=1)
        form.columnconfigure(1, weight=1)

        fields = [
            ("Время впрыска, с", self.injection_duration_var),
            ("Интервал между впрысками, с", self.injection_interval_var),
            ("Количество впрысков", self.injection_count_var),
            ("Длительность цикла, с", self.injection_cycle_var),
            ("Пользовательские параметры", self.user_parameters_var),
        ]
        for index, (label, variable) in enumerate(fields):
            ttk.Label(form, text=label).grid(row=index, column=0, sticky="w", pady=6)
            ttk.Entry(form, textvariable=variable).grid(
                row=index, column=1, sticky="ew", pady=6, padx=(12, 0)
            )

        ttk.Button(
            form,
            text="Сохранить настройки впрыска",
            command=self._save_injection_settings,
        ).grid(row=len(fields), column=0, columnspan=2, sticky="ew", pady=(12, 0))

    def _build_pressure_screen(self) -> None:
        form = ttk.LabelFrame(self.pressure_frame, text="Параметры давления", padding=16)
        form.grid(row=0, column=0, sticky="nsew")
        self.pressure_frame.columnconfigure(0, weight=1)
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="Нижний предел, бар").grid(row=0, column=0, sticky="w", pady=6)
        ttk.Entry(form, textvariable=self.pressure_min_var).grid(
            row=0, column=1, sticky="ew", pady=6, padx=(12, 0)
        )
        ttk.Label(form, text="Верхний предел, бар").grid(row=1, column=0, sticky="w", pady=6)
        ttk.Entry(form, textvariable=self.pressure_max_var).grid(
            row=1, column=1, sticky="ew", pady=6, padx=(12, 0)
        )
        ttk.Button(
            form,
            text="Применить настройки давления",
            command=self._save_pressure_settings,
        ).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(12, 0))

    def _build_journal_screen(self) -> None:
        controls = ttk.Frame(self.journal_frame)
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        self.journal_frame.columnconfigure(0, weight=1)
        self.journal_frame.rowconfigure(1, weight=1)

        ttk.Label(controls, text="Фильтр").grid(row=0, column=0, sticky="w")
        filter_box = ttk.Combobox(
            controls,
            textvariable=self.journal_filter_var,
            values=("all", "event", "alarm", "technical"),
            state="readonly",
            width=12,
        )
        filter_box.grid(row=0, column=1, sticky="w", padx=(8, 12))
        filter_box.bind("<<ComboboxSelected>>", lambda _event: self._refresh_journal())
        ttk.Button(controls, text="Обновить журнал", command=self._refresh_journal).grid(
            row=0, column=2, sticky="w"
        )
        ttk.Button(controls, text="Экспорт логов", command=self._export_logs).grid(
            row=0, column=3, sticky="w", padx=(12, 0)
        )

        columns = ("timestamp", "channel", "event_type", "description", "state")
        self.journal_tree = ttk.Treeview(
            self.journal_frame,
            columns=columns,
            show="headings",
            height=20,
        )
        for heading, width in (
            ("timestamp", 180),
            ("channel", 80),
            ("event_type", 160),
            ("description", 440),
            ("state", 100),
        ):
            self.journal_tree.heading(heading, text=heading)
            self.journal_tree.column(heading, width=width, anchor="w")
        self.journal_tree.grid(row=1, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(
            self.journal_frame,
            orient="vertical",
            command=self.journal_tree.yview,
        )
        scrollbar.grid(row=1, column=1, sticky="ns")
        self.journal_tree.configure(yscrollcommand=scrollbar.set)

    def _build_info_screen(self) -> None:
        frame = ttk.LabelFrame(self.info_frame, text="Информация о системе", padding=16)
        frame.grid(row=0, column=0, sticky="nsew")
        self.info_frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

        rows = [
            ("Версия ПО", self.info_vars["software_version"]),
            ("Каталог данных", self.info_vars["data_directory"]),
            ("Файл настроек", self.info_vars["settings_file"]),
            ("Каталог архивов логов", self.info_vars["log_export_directory"]),
            ("Политика удаленного доступа", self.info_vars["remote_policy"]),
            ("Сводка по устройствам", self.info_vars["device_summary"]),
        ]
        for index, (label, variable) in enumerate(rows):
            ttk.Label(frame, text=label).grid(row=index, column=0, sticky="nw", pady=6)
            ttk.Label(frame, textvariable=variable, wraplength=700, justify="left").grid(
                row=index,
                column=1,
                sticky="w",
                padx=(12, 0),
                pady=6,
            )

    def _invoke_action(self, action, success_message: str) -> None:
        try:
            action()
        except Exception as exc:
            self.status_var.set(f"Ошибка: {exc}")
            messagebox.showerror("DustSoft", str(exc), parent=self.root)
        else:
            self.status_var.set(success_message)
        finally:
            self._refresh_all()

    def _save_injection_settings(self) -> None:
        self.app.configure_injection(
            duration_seconds=float(self.injection_duration_var.get()),
            interval_seconds=float(self.injection_interval_var.get()),
            count=int(self.injection_count_var.get()),
            cycle_seconds=float(self.injection_cycle_var.get()),
        )
        user_parameters = self._parse_user_parameters(self.user_parameters_var.get())
        self.app.update_user_parameters(**user_parameters)
        self.status_var.set("Настройки впрыска сохранены")
        self._refresh_all()

    def _save_pressure_settings(self) -> None:
        self.app.configure_pressure(
            minimum_bar=float(self.pressure_min_var.get()),
            maximum_bar=float(self.pressure_max_var.get()),
        )
        self.status_var.set("Настройки давления сохранены")
        self._refresh_all()

    @staticmethod
    def _parse_user_parameters(raw_value: str) -> dict[str, str]:
        result: dict[str, str] = {}
        if not raw_value.strip():
            return result

        for chunk in raw_value.split(","):
            entry = chunk.strip()
            if not entry:
                continue
            if "=" not in entry:
                raise ValueError(
                    "User parameters must be provided as key=value pairs separated by commas"
                )
            key, value = entry.split("=", 1)
            result[key.strip()] = value.strip()
        return result

    def _refresh_all(self) -> None:
        if self._refresh_job is not None:
            self.root.after_cancel(self._refresh_job)
            self._refresh_job = None

        telemetry = self.app.read_telemetry()
        self.telemetry_vars["state"].set(telemetry["state"])
        self.telemetry_vars["pressure"].set(self._format_number(telemetry["pressure"]))
        self.telemetry_vars["reference"].set(self._format_number(telemetry["reference"]))
        self.telemetry_vars["compressor"].set(
            self._device_status(
                telemetry["devices"]["compressor_running"],
                telemetry["devices"]["compressor_connected"],
            )
        )
        self.telemetry_vars["valve"].set(
            self._device_status(
                telemetry["devices"]["valve_running"],
                telemetry["devices"]["valve_connected"],
            )
        )
        self.telemetry_vars["remote"].set(
            "Активна" if telemetry["remote"]["link_active"] else "Деградировано"
        )

        info = self.app.build_system_info()
        self.info_vars["software_version"].set(info["software_version"])
        self.info_vars["data_directory"].set(info["data_directory"])
        self.info_vars["settings_file"].set(info["settings_file"])
        self.info_vars["log_export_directory"].set(info["log_export_directory"])
        self.info_vars["remote_policy"].set(
            "TLS обязателен: {tls}; токенов: {tokens}; сертификатов: {certs}; связь: {link}".format(
                tls="да" if info["remote_access"]["tls_required"] else "нет",
                tokens=info["remote_access"]["token_count"],
                certs=info["remote_access"]["certificate_count"],
                link="активна" if info["remote_access"]["link_active"] else "деградировано",
            )
        )
        self.info_vars["device_summary"].set(
            ", ".join(
                f"{name}={'ok' if value else 'fault'}"
                for name, value in info["devices"].items()
            )
        )
        self._refresh_journal()
        self._refresh_job = self.root.after(1000, self._refresh_all)

    def _export_logs(self) -> None:
        archive_path = self.app.export_logs_archive()
        self.status_var.set(f"Логи экспортированы: {archive_path.name}")
        messagebox.showinfo(
            "DustSoft",
            f"Архив логов сохранен в:\n{archive_path}",
            parent=self.root,
        )
        self._refresh_all()

    def _refresh_journal(self) -> None:
        for row_id in self.journal_tree.get_children():
            self.journal_tree.delete(row_id)

        for channel, entry in self.app.get_journal_entries(self.journal_filter_var.get())[:200]:
            self.journal_tree.insert(
                "",
                "end",
                values=(
                    entry.timestamp,
                    channel,
                    entry.event_type,
                    entry.description,
                    entry.system_snapshot.get("state", "-"),
                ),
            )

    @staticmethod
    def _format_number(value: object) -> str:
        if value is None:
            return "-"
        if isinstance(value, float):
            return f"{value:.3f}"
        return str(value)

    @staticmethod
    def _device_status(is_running: bool, is_connected: bool) -> str:
        if not is_connected:
            return "Нет связи"
        return "В работе" if is_running else "Остановлен"


def launch_ui(app: Application) -> None:
    DustSoftUI(app).run()
