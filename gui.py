import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog
from time import time
from typing import Optional, Callable

from main import RunConfig, run_job


class ToolTip:
    def __init__(self, widget: tk.Widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self._window: Optional[tk.Toplevel] = None
        self._after_id: Optional[str] = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None) -> None:
        self._cancel()
        self._after_id = self.widget.after(400, self._show)

    def _cancel(self) -> None:
        if self._after_id is not None:
            self.widget.after_cancel(self._after_id)
            self._after_id = None

    def _show(self) -> None:
        if self._window is not None or not self.text:
            return
        x = self.widget.winfo_rootx() + 16
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        self._window = tk.Toplevel(self.widget)
        self._window.wm_overrideredirect(True)
        self._window.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            self._window,
            text=self.text,
            justify="left",
            bg="#fff7d6",
            fg="#334155",
            relief="solid",
            borderwidth=1,
            padx=8,
            pady=6,
            wraplength=280,
            font=("Segoe UI", 9),
        )
        label.pack()

    def _hide(self, _event=None) -> None:
        self._cancel()
        if self._window is not None:
            self._window.destroy()
            self._window = None


class ManagerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("TEG Manager")
        self.minsize(980, 760)
        self.configure(bg="#eef3f8")

        self._queue: queue.Queue = queue.Queue()
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event: Optional[threading.Event] = None
        self._pause_event: Optional[threading.Event] = None
        self._run_started_at: Optional[float] = None
        self._final_elapsed_seconds: Optional[int] = None
        self._paused_started_at: Optional[float] = None
        self._paused_accumulated_seconds: float = 0.0
        self._last_progress: dict = {}
        self._log_records: list[dict] = []
        self._config_widgets: list[tk.Widget] = []
        self._browse_buttons: list[ttk.Button] = []
        self._tooltips: list[ToolTip] = []

        self._configure_styles()
        self._build_ui()
        self._set_status_badge("Idle")
        self._poll_queue()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _configure_styles(self) -> None:
        self.option_add("*Font", "{Segoe UI} 10")
        self.option_add("*Label.Font", "{Segoe UI} 10")
        self.option_add("*Message.Font", "{Segoe UI} 10")

        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("Card.TLabelframe", background="#ffffff", borderwidth=1, relief="solid")
        style.configure("Card.TLabelframe.Label", background="#ffffff", foreground="#0f172a", font=("Segoe UI", 10, "bold"))
        style.configure("App.TFrame", background="#ffffff")
        style.configure("Toolbar.TFrame", background="#ffffff")
        style.configure("TLabel", background="#ffffff", foreground="#334155")
        style.configure("Stat.TLabel", background="#ffffff", foreground="#0f172a", font=("Segoe UI", 10, "bold"))
        style.configure("Muted.TLabel", background="#ffffff", foreground="#64748b")
        style.configure("TEntry", fieldbackground="#f8fafc", bordercolor="#cbd5e1", lightcolor="#cbd5e1", darkcolor="#cbd5e1")
        style.map("TEntry", fieldbackground=[("disabled", "#e2e8f0")], foreground=[("disabled", "#64748b")])
        style.configure("TButton", padding=(10, 6), font=("Segoe UI", 10, "bold"))
        style.configure("Accent.TButton", background="#2563eb", foreground="#ffffff", borderwidth=0)
        style.map("Accent.TButton", background=[("active", "#1d4ed8"), ("disabled", "#93c5fd")], foreground=[("disabled", "#eff6ff")])
        style.configure("Warn.TButton", background="#f59e0b", foreground="#ffffff", borderwidth=0)
        style.map("Warn.TButton", background=[("active", "#d97706"), ("disabled", "#fcd34d")], foreground=[("disabled", "#fff7ed")])
        style.configure("Danger.TButton", background="#dc2626", foreground="#ffffff", borderwidth=0)
        style.map("Danger.TButton", background=[("active", "#b91c1c"), ("disabled", "#fca5a5")], foreground=[("disabled", "#fff1f2")])
        style.configure("TCombobox", fieldbackground="#f8fafc", background="#f8fafc")
        style.map("TCombobox", fieldbackground=[("readonly", "#f8fafc"), ("disabled", "#e2e8f0")])
        style.configure("TProgressbar", troughcolor="#dbeafe", background="#2563eb", bordercolor="#dbeafe", lightcolor="#2563eb", darkcolor="#2563eb")

    def _build_ui(self) -> None:
        defaults = RunConfig()

        self.working_port_var = tk.StringVar(value=str(defaults.working_port))
        self.worker_name_var = tk.StringVar(value=defaults.worker_name)
        self.batch_size_var = tk.StringVar(value=str(defaults.batch_size))
        self.sleep_request_min_var = tk.StringVar(value=str(defaults.sleep_per_request_min))
        self.sleep_request_max_var = tk.StringVar(value=str(defaults.sleep_per_request_max))
        self.sleep_candidate_min_var = tk.StringVar(value=str(defaults.sleep_per_candidate_min))
        self.sleep_candidate_max_var = tk.StringVar(value=str(defaults.sleep_per_candidate_max))
        self.sleep_batch_min_var = tk.StringVar(value=str(defaults.sleep_per_batch_min))
        self.sleep_batch_max_var = tk.StringVar(value=str(defaults.sleep_per_batch_max))
        self.names_file_var = tk.StringVar(value=defaults.names_file)
        self.results_file_var = tk.StringVar(value=defaults.results_file)

        self.status_var = tk.StringVar(value="Idle")
        self.processed_var = tk.StringVar(value="0/0")
        self.success_var = tk.StringVar(value="0")
        self.not_found_var = tk.StringVar(value="0")
        self.insurance_var = tk.StringVar(value="0")
        self.request_error_var = tk.StringVar(value="0")
        self.failed_candidates_var = tk.StringVar(value="0")
        self.current_var = tk.StringVar(value="")
        self.elapsed_var = tk.StringVar(value="00:00:00")
        self.average_var = tk.StringVar(value="-")
        self.eta_var = tk.StringVar(value="-")
        self.summary_var = tk.StringVar(value="No run yet.")
        self.log_filter_var = tk.StringVar(value="All")

        config_frame = ttk.LabelFrame(self, text="Configuration", style="Card.TLabelframe")
        config_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        config_frame.columnconfigure(1, weight=1)

        self._add_entry(config_frame, 0, "Working port", self.working_port_var, help_text="Chrome remote debugging port used to attach the scraper to the already opened browser session.")
        self._add_entry(config_frame, 1, "Worker name", self.worker_name_var, help_text="Name shown in logs and run tracking so you can identify which worker instance produced the results.")
        self._add_entry(config_frame, 2, "Batch size", self.batch_size_var, help_text="Number of successful records to collect before saving to the Excel file.")
        self._add_range_entry(
            config_frame,
            3,
            "Request sleep (s)",
            self.sleep_request_min_var,
            self.sleep_request_max_var,
            help_text="Random pause between one search and the next. The app picks a number between min and max."
        )
        self._add_range_entry(
            config_frame,
            4,
            "Candidate sleep (s)",
            self.sleep_candidate_min_var,
            self.sleep_candidate_max_var,
            help_text="Random pause between candidate detail fetches when one name returns multiple beneficiaries."
        )
        self._add_range_entry(
            config_frame,
            5,
            "Batch sleep (s)",
            self.sleep_batch_min_var,
            self.sleep_batch_max_var,
            help_text="Random pause after a batch save. Useful for slowing down long continuous runs."
        )
        self._add_entry(
            config_frame,
            6,
            "Names file",
            self.names_file_var,
            browse_cmd=self._browse_names,
            help_text="Input text file containing names or NIR values to search. One item per line."
        )
        self._add_entry(
            config_frame,
            7,
            "Results file",
            self.results_file_var,
            browse_cmd=self._browse_results,
            help_text="Excel file where extracted results will be written and updated during the run."
        )

        button_frame = ttk.Frame(config_frame, style="App.TFrame")
        button_frame.grid(row=8, column=0, columnspan=3, sticky="w", pady=(10, 0))
        self.start_button = ttk.Button(button_frame, text="Start", command=self._start_run, style="Accent.TButton")
        self.pause_button = ttk.Button(button_frame, text="Pause", command=self._toggle_pause, state="disabled", style="Warn.TButton")
        self.stop_button = ttk.Button(button_frame, text="Stop", command=self._stop_run, state="disabled", style="Danger.TButton")
        self.start_button.grid(row=0, column=0, padx=(0, 8))
        self.pause_button.grid(row=0, column=1, padx=(0, 8))
        self.stop_button.grid(row=0, column=2)

        progress_frame = ttk.LabelFrame(self, text="Progress", style="Card.TLabelframe")
        progress_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        progress_frame.columnconfigure(1, weight=1)

        ttk.Label(progress_frame, text="Status").grid(row=0, column=0, sticky="w")
        self.status_badge = tk.Label(
            progress_frame,
            textvariable=self.status_var,
            width=12,
            relief="ridge",
            padx=8,
            pady=2
        )
        self.status_badge.grid(row=0, column=1, sticky="w")

        ttk.Label(progress_frame, text="Processed").grid(row=1, column=0, sticky="w")
        ttk.Label(progress_frame, textvariable=self.processed_var).grid(row=1, column=1, sticky="w")

        ttk.Label(progress_frame, text="Elapsed").grid(row=2, column=0, sticky="w")
        ttk.Label(progress_frame, textvariable=self.elapsed_var).grid(row=2, column=1, sticky="w")

        ttk.Label(progress_frame, text="Avg / request").grid(row=3, column=0, sticky="w")
        ttk.Label(progress_frame, textvariable=self.average_var).grid(row=3, column=1, sticky="w")

        ttk.Label(progress_frame, text="ETA").grid(row=4, column=0, sticky="w")
        ttk.Label(progress_frame, textvariable=self.eta_var).grid(row=4, column=1, sticky="w")

        ttk.Label(progress_frame, text="Current").grid(row=5, column=0, sticky="w")
        ttk.Label(progress_frame, textvariable=self.current_var).grid(row=5, column=1, sticky="w")

        ttk.Label(progress_frame, text="Run summary").grid(row=6, column=0, sticky="nw")
        summary_message = tk.Message(progress_frame, textvariable=self.summary_var, width=650)
        summary_message.grid(row=6, column=1, sticky="w")

        self.progress_bar = ttk.Progressbar(progress_frame, orient="horizontal", mode="determinate")
        self.progress_bar.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        summary_frame = ttk.LabelFrame(self, text="Summary", style="Card.TLabelframe")
        summary_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)
        summary_frame.columnconfigure(1, weight=1)

        ttk.Label(summary_frame, text="Success", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(summary_frame, textvariable=self.success_var, style="Stat.TLabel").grid(row=0, column=1, sticky="w")

        ttk.Label(summary_frame, text="Not found", style="Muted.TLabel").grid(row=1, column=0, sticky="w")
        ttk.Label(summary_frame, textvariable=self.not_found_var, style="Stat.TLabel").grid(row=1, column=1, sticky="w")

        ttk.Label(summary_frame, text="Insurance issues", style="Muted.TLabel").grid(row=2, column=0, sticky="w")
        ttk.Label(summary_frame, textvariable=self.insurance_var, style="Stat.TLabel").grid(row=2, column=1, sticky="w")

        ttk.Label(summary_frame, text="Request errors", style="Muted.TLabel").grid(row=3, column=0, sticky="w")
        ttk.Label(summary_frame, textvariable=self.request_error_var, style="Stat.TLabel").grid(row=3, column=1, sticky="w")

        ttk.Label(summary_frame, text="Failed candidates", style="Muted.TLabel").grid(row=4, column=0, sticky="w")
        ttk.Label(summary_frame, textvariable=self.failed_candidates_var, style="Stat.TLabel").grid(row=4, column=1, sticky="w")

        log_frame = ttk.LabelFrame(self, text="Log", style="Card.TLabelframe")
        log_frame.grid(row=3, column=0, sticky="nsew", padx=10, pady=10)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(1, weight=1)

        filter_frame = ttk.Frame(log_frame, style="Toolbar.TFrame")
        filter_frame.grid(row=0, column=0, sticky="w", pady=(0, 8))
        ttk.Label(filter_frame, text="Filter", style="Muted.TLabel").grid(row=0, column=0, padx=(0, 8))
        filter_box = ttk.Combobox(
            filter_frame,
            textvariable=self.log_filter_var,
            values=("All", "Info", "Warnings", "Errors"),
            state="readonly",
            width=12
        )
        filter_box.grid(row=0, column=1, sticky="w")
        filter_box.bind("<<ComboboxSelected>>", lambda _event: self._refresh_log_view())

        self.log_text = tk.Text(
            log_frame,
            height=18,
            state="disabled",
            wrap="word",
            bg="#f8fafc",
            fg="#1e293b",
            insertbackground="#1e293b",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#cbd5e1",
            highlightcolor="#93c5fd",
            padx=10,
            pady=10,
        )
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.tag_configure("info", foreground="#1f2937")
        self.log_text.tag_configure("warning", foreground="#9a6700")
        self.log_text.tag_configure("error", foreground="#b42318")
        self.log_text.grid(row=1, column=0, sticky="nsew")
        scrollbar.grid(row=1, column=1, sticky="ns")

        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

    def _add_entry(
        self,
        frame: ttk.LabelFrame,
        row: int,
        label: str,
        variable: tk.StringVar,
        browse_cmd: Optional[Callable[[], None]] = None,
        help_text: str = ""
    ) -> None:
        label_widget = ttk.Label(frame, text=label, style="Muted.TLabel")
        label_widget.grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
        entry = ttk.Entry(frame, textvariable=variable)
        entry.grid(row=row, column=1, sticky="ew", pady=4)
        self._config_widgets.append(entry)
        self._attach_tooltip(label_widget, help_text)
        self._attach_tooltip(entry, help_text)
        if browse_cmd:
            browse_button = ttk.Button(frame, text="Browse", command=browse_cmd)
            browse_button.grid(row=row, column=2, padx=(8, 0), pady=4)
            self._browse_buttons.append(browse_button)
            self._attach_tooltip(browse_button, help_text)

    def _add_range_entry(
        self,
        frame: ttk.LabelFrame,
        row: int,
        label: str,
        min_variable: tk.StringVar,
        max_variable: tk.StringVar,
        help_text: str = ""
    ) -> None:
        label_widget = ttk.Label(frame, text=label, style="Muted.TLabel")
        label_widget.grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)

        range_frame = ttk.Frame(frame, style="App.TFrame")
        range_frame.grid(row=row, column=1, columnspan=2, sticky="ew", pady=4)
        range_frame.columnconfigure(1, weight=1)
        range_frame.columnconfigure(4, weight=1)

        min_label = ttk.Label(range_frame, text="Min", style="Muted.TLabel")
        min_label.grid(row=0, column=0, padx=(0, 6))
        min_entry = ttk.Entry(range_frame, textvariable=min_variable, width=10)
        min_entry.grid(row=0, column=1, sticky="ew")

        to_label = ttk.Label(range_frame, text="to", style="Muted.TLabel")
        to_label.grid(row=0, column=2, padx=10)

        max_label = ttk.Label(range_frame, text="Max", style="Muted.TLabel")
        max_label.grid(row=0, column=3, padx=(0, 6))
        max_entry = ttk.Entry(range_frame, textvariable=max_variable, width=10)
        max_entry.grid(row=0, column=4, sticky="ew")

        self._config_widgets.extend([min_entry, max_entry])
        for widget in (label_widget, range_frame, min_label, min_entry, to_label, max_label, max_entry):
            self._attach_tooltip(widget, help_text)

    def _browse_names(self) -> None:
        path = filedialog.askopenfilename(title="Select names file", filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if path:
            self.names_file_var.set(path)

    def _browse_results(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Select results file",
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
        )
        if path:
            self.results_file_var.set(path)

    def _build_config(self) -> RunConfig:
        working_port = self._parse_int(self.working_port_var.get(), "Working port")
        batch_size = self._parse_int(self.batch_size_var.get(), "Batch size")
        sleep_per_request_min = self._parse_int(self.sleep_request_min_var.get(), "Request sleep min")
        sleep_per_request_max = self._parse_int(self.sleep_request_max_var.get(), "Request sleep max")
        sleep_per_candidate_min = self._parse_int(self.sleep_candidate_min_var.get(), "Candidate sleep min")
        sleep_per_candidate_max = self._parse_int(self.sleep_candidate_max_var.get(), "Candidate sleep max")
        sleep_per_batch_min = self._parse_int(self.sleep_batch_min_var.get(), "Batch sleep min")
        sleep_per_batch_max = self._parse_int(self.sleep_batch_max_var.get(), "Batch sleep max")

        worker_name = self.worker_name_var.get().strip()
        if not worker_name:
            raise ValueError("Worker name is required.")

        names_file = self.names_file_var.get().strip()
        if not names_file:
            raise ValueError("Names file is required.")

        results_file = self.results_file_var.get().strip()
        if not results_file:
            raise ValueError("Results file is required.")

        self._validate_range(sleep_per_request_min, sleep_per_request_max, "Request sleep")
        self._validate_range(sleep_per_candidate_min, sleep_per_candidate_max, "Candidate sleep")
        self._validate_range(sleep_per_batch_min, sleep_per_batch_max, "Batch sleep")

        return RunConfig(
            working_port=working_port,
            worker_name=worker_name,
            batch_size=batch_size,
            sleep_per_request_min=sleep_per_request_min,
            sleep_per_request_max=sleep_per_request_max,
            sleep_per_candidate_min=sleep_per_candidate_min,
            sleep_per_candidate_max=sleep_per_candidate_max,
            sleep_per_batch_min=sleep_per_batch_min,
            sleep_per_batch_max=sleep_per_batch_max,
            names_file=names_file,
            results_file=results_file,
            pause_on_finish=0
        )

    @staticmethod
    def _parse_int(value: str, label: str) -> int:
        try:
            return int(value)
        except ValueError as exc:
            raise ValueError(f"{label} must be an integer.") from exc

    @staticmethod
    def _validate_range(min_value: int, max_value: int, label: str) -> None:
        if min_value < 0 or max_value < 0:
            raise ValueError(f"{label} values must be zero or greater.")
        if min_value > max_value:
            raise ValueError(f"{label} min cannot be greater than max.")

    def _start_run(self) -> None:
        if self._worker_thread and self._worker_thread.is_alive():
            return
        try:
            config = self._build_config()
        except ValueError as exc:
            self._append_log(f"Config error: {exc}")
            return

        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._run_started_at = time()
        self._final_elapsed_seconds = None
        self._paused_started_at = None
        self._paused_accumulated_seconds = 0.0
        self._last_progress = {"processed": 0, "total": 0}
        self._log_records.clear()
        self._clear_log_view()
        self._reset_run_metrics()
        self._set_running(True)
        self._append_log("Starting processing...")
        self.summary_var.set("Running...")

        self._worker_thread = threading.Thread(
            target=self._run_worker,
            args=(config,),
            daemon=True
        )
        self._worker_thread.start()

    def _stop_run(self) -> None:
        if self._stop_event:
            self._stop_event.set()
            if self._pause_event:
                self._pause_event.clear()
            self._resume_elapsed_clock()
            self.pause_button.configure(state="disabled", text="Pause")
            self._set_status_badge("Stopping")
            self._append_log("Stop requested.")

    def _toggle_pause(self) -> None:
        if not self._pause_event:
            return
        if self._pause_event.is_set():
            self._pause_event.clear()
            self._resume_elapsed_clock()
            self.pause_button.configure(text="Pause")
            self._set_status_badge("Running")
            self._append_log("Resume requested.")
        else:
            self._pause_event.set()
            self._paused_started_at = time()
            self.pause_button.configure(text="Resume")
            self._set_status_badge("Paused")
            self._append_log("Pause requested.")

    def _run_worker(self, config: RunConfig) -> None:
        def log(message: str) -> None:
            self._queue.put(("log", message))

        def progress(payload: dict) -> None:
            self._queue.put(("progress", payload))

        try:
            summary = run_job(
                config=config,
                logger=log,
                use_color=False,
                progress_cb=progress,
                stop_event=self._stop_event,
                pause_event=self._pause_event
            )
            self._queue.put(("summary", summary))
            if not summary:
                self._queue.put(("state", "error"))
            elif summary.get("status") == "error":
                self._queue.put(("state", "error"))
            elif summary.get("status") == "stopped" or summary.get("stopped"):
                self._queue.put(("state", "stopped"))
            else:
                self._queue.put(("state", "done"))
        except Exception as exc:
            self._queue.put(("log", f"Error: {exc}"))
            self._queue.put(("state", "error"))

    def _poll_queue(self) -> None:
        try:
            while True:
                event, payload = self._queue.get_nowait()
                if event == "log":
                    self._append_log(payload)
                elif event == "progress":
                    self._update_progress(payload)
                elif event == "summary":
                    self._update_summary(payload)
                elif event == "state":
                    self._handle_state(payload)
        except queue.Empty:
            pass
        self._refresh_runtime_metrics()
        self.after(200, self._poll_queue)

    def _update_progress(self, payload: dict) -> None:
        self._last_progress = payload
        processed = int(payload.get("processed", 0))
        total = int(payload.get("total", 0))
        self.processed_var.set(f"{processed}/{total}")
        self.success_var.set(str(payload.get("success", 0)))
        self.not_found_var.set(str(payload.get("not_found", 0)))
        self.insurance_var.set(str(payload.get("insurance_issue", 0)))
        self.request_error_var.set(str(payload.get("request_error", 0)))
        self.failed_candidates_var.set(str(payload.get("failed_candidates", 0)))
        self.current_var.set(payload.get("current") or "")

        if total > 0:
            self.progress_bar.configure(maximum=total, value=processed)
        else:
            self.progress_bar.configure(value=0)

    def _handle_state(self, state: str) -> None:
        if state == "done":
            self._set_status_badge("Done")
            self._set_running(False)
        elif state == "error":
            self._set_status_badge("Error")
            self._set_running(False)
        elif state == "stopped":
            self._set_status_badge("Done")
            self._set_running(False)

    def _set_running(self, running: bool) -> None:
        if running:
            self._set_status_badge("Running")
            self.start_button.configure(state="disabled")
            self.pause_button.configure(state="normal", text="Pause")
            self.stop_button.configure(state="normal")
            self._set_config_inputs_enabled(False)
        else:
            self._resume_elapsed_clock()
            self.start_button.configure(state="normal")
            self.pause_button.configure(state="disabled", text="Pause")
            self.stop_button.configure(state="disabled")
            self._set_config_inputs_enabled(True)

    def _append_log(self, message: str) -> None:
        level = self._classify_log_level(message)
        self._log_records.append({"message": message, "level": level})
        if self.log_filter_var.get() != "All" and not self._matches_log_filter(level):
            return
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n", level)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _update_summary(self, summary: Optional[dict]) -> None:
        if not summary:
            self.summary_var.set("No summary available.")
            return
        status = summary.get("status", "done")
        if status == "error":
            status_label = "Error"
        elif status == "stopped":
            status_label = "Stopped"
        else:
            status_label = "Done"

        processed = summary.get("processed", 0)
        total = summary.get("total", 0)
        success = summary.get("success", 0)
        not_found = summary.get("not_found", 0)
        insurance = summary.get("insurance_issue", 0)
        request_error = summary.get("request_error", 0)
        failed_candidates = summary.get("failed_candidates", 0)
        elapsed = summary.get("elapsed_hms", "")
        elapsed_seconds = summary.get("elapsed_seconds")
        results_file = summary.get("results_file", "")
        message = summary.get("message", "")
        self.failed_candidates_var.set(str(failed_candidates))
        if isinstance(elapsed_seconds, int):
            self._final_elapsed_seconds = elapsed_seconds
            self.elapsed_var.set(self._format_seconds(elapsed_seconds))

        parts = [
            f"Status: {status_label}",
            f"Processed: {processed}/{total}",
            f"Success: {success}",
            f"Not found: {not_found}",
            f"Insurance issues: {insurance}",
            f"Request errors: {request_error}",
            f"Failed candidates: {failed_candidates}"
        ]
        if elapsed:
            parts.append(f"Time: {elapsed}")
        if results_file:
            parts.append(f"Results: {results_file}")
        if message:
            parts.append(f"Note: {message}")
        self.summary_var.set(" | ".join(parts))

    def _classify_log_level(self, message: str) -> str:
        lowered = message.lower()
        if any(token in lowered for token in ("error", "failed", "timed out", "traceback")):
            return "error"
        if any(token in lowered for token in ("not found", "warning", "insurance", "stop requested", "sleeping", "no existing results")):
            return "warning"
        return "info"

    def _matches_log_filter(self, level: str) -> bool:
        selected = self.log_filter_var.get()
        if selected == "All":
            return True
        if selected == "Info":
            return level == "info"
        if selected == "Warnings":
            return level == "warning"
        if selected == "Errors":
            return level == "error"
        return True

    def _refresh_log_view(self) -> None:
        self._clear_log_view()
        self.log_text.configure(state="normal")
        for record in self._log_records:
            if self._matches_log_filter(record["level"]):
                self.log_text.insert("end", record["message"] + "\n", record["level"])
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _clear_log_view(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _reset_run_metrics(self) -> None:
        self.status_var.set("Idle")
        self.processed_var.set("0/0")
        self.success_var.set("0")
        self.not_found_var.set("0")
        self.insurance_var.set("0")
        self.request_error_var.set("0")
        self.failed_candidates_var.set("0")
        self.current_var.set("")
        self.elapsed_var.set("00:00:00")
        self.average_var.set("-")
        self.eta_var.set("-")

    def _refresh_runtime_metrics(self) -> None:
        if self._run_started_at is None:
            return
        if self._final_elapsed_seconds is not None:
            elapsed_seconds = self._final_elapsed_seconds
        else:
            elapsed_seconds = max(0, int(time() - self._run_started_at - self._current_pause_offset()))
        self.elapsed_var.set(self._format_seconds(elapsed_seconds))

        processed = int(self._last_progress.get("processed", 0))
        total = int(self._last_progress.get("total", 0))
        if processed > 0 and elapsed_seconds > 0:
            average = elapsed_seconds / processed
            self.average_var.set(f"{average:.1f}s")
            remaining = max(0, total - processed)
            self.eta_var.set(self._format_seconds(int(remaining * average)))
        else:
            self.average_var.set("-")
            self.eta_var.set("-")

    def _set_status_badge(self, status: str) -> None:
        colors = {
            "Idle": ("#e5e7eb", "#111827"),
            "Running": ("#dcfce7", "#166534"),
            "Paused": ("#fef3c7", "#92400e"),
            "Stopping": ("#fde68a", "#92400e"),
            "Error": ("#fee2e2", "#991b1b"),
            "Done": ("#dbeafe", "#1d4ed8"),
        }
        background, foreground = colors.get(status, ("#e5e7eb", "#111827"))
        self.status_var.set(status)
        self.status_badge.configure(bg=background, fg=foreground, activebackground=background, activeforeground=foreground, bd=0)

    def _set_config_inputs_enabled(self, enabled: bool) -> None:
        entry_state = "normal" if enabled else "disabled"
        button_state = "normal" if enabled else "disabled"
        for widget in self._config_widgets:
            widget.configure(state=entry_state)
        for button in self._browse_buttons:
            button.configure(state=button_state)

    def _attach_tooltip(self, widget: tk.Widget, text: str) -> None:
        if text:
            self._tooltips.append(ToolTip(widget, text))

    def _current_pause_offset(self) -> float:
        if self._paused_started_at is None:
            return self._paused_accumulated_seconds
        return self._paused_accumulated_seconds + (time() - self._paused_started_at)

    def _resume_elapsed_clock(self) -> None:
        if self._paused_started_at is not None:
            self._paused_accumulated_seconds += time() - self._paused_started_at
            self._paused_started_at = None

    @staticmethod
    def _format_seconds(value: int) -> str:
        hours = value // 3600
        minutes = (value % 3600) // 60
        seconds = value % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _on_close(self) -> None:
        if self._stop_event and not self._stop_event.is_set():
            self._stop_event.set()
        self.destroy()


if __name__ == "__main__":
    app = ManagerApp()
    app.mainloop()
