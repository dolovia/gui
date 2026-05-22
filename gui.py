import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog
from typing import Optional, Callable

from main import RunConfig, run_job


class ManagerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("TEG Manager")
        self.minsize(900, 650)

        self._queue: queue.Queue = queue.Queue()
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event: Optional[threading.Event] = None

        self._build_ui()
        self._poll_queue()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        defaults = RunConfig()

        self.working_port_var = tk.StringVar(value=str(defaults.working_port))
        self.worker_name_var = tk.StringVar(value=defaults.worker_name)
        self.batch_size_var = tk.StringVar(value=str(defaults.batch_size))
        self.sleep_request_var = tk.StringVar(value=str(defaults.sleep_per_request))
        self.sleep_candidate_var = tk.StringVar(value=str(defaults.sleep_per_candidate))
        self.sleep_batch_var = tk.StringVar(value=str(defaults.sleep_per_batch))
        self.names_file_var = tk.StringVar(value=defaults.names_file)
        self.results_file_var = tk.StringVar(value=defaults.results_file)

        self.status_var = tk.StringVar(value="Idle")
        self.processed_var = tk.StringVar(value="0/0")
        self.success_var = tk.StringVar(value="0")
        self.not_found_var = tk.StringVar(value="0")
        self.insurance_var = tk.StringVar(value="0")
        self.request_error_var = tk.StringVar(value="0")
        self.current_var = tk.StringVar(value="")
        self.summary_var = tk.StringVar(value="No run yet.")

        config_frame = ttk.LabelFrame(self, text="Configuration")
        config_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        config_frame.columnconfigure(1, weight=1)

        self._add_entry(config_frame, 0, "Working port", self.working_port_var)
        self._add_entry(config_frame, 1, "Worker name", self.worker_name_var)
        self._add_entry(config_frame, 2, "Batch size", self.batch_size_var)
        self._add_entry(config_frame, 3, "Sleep per request (s)", self.sleep_request_var)
        self._add_entry(config_frame, 4, "Sleep per candidate (s)", self.sleep_candidate_var)
        self._add_entry(config_frame, 5, "Sleep per batch (s)", self.sleep_batch_var)
        self._add_entry(
            config_frame,
            6,
            "Names file",
            self.names_file_var,
            browse_cmd=self._browse_names
        )
        self._add_entry(
            config_frame,
            7,
            "Results file",
            self.results_file_var,
            browse_cmd=self._browse_results
        )

        button_frame = ttk.Frame(config_frame)
        button_frame.grid(row=8, column=0, columnspan=3, sticky="w", pady=(10, 0))
        self.start_button = ttk.Button(button_frame, text="Start", command=self._start_run)
        self.stop_button = ttk.Button(button_frame, text="Stop", command=self._stop_run, state="disabled")
        self.start_button.grid(row=0, column=0, padx=(0, 8))
        self.stop_button.grid(row=0, column=1)

        progress_frame = ttk.LabelFrame(self, text="Progress")
        progress_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        progress_frame.columnconfigure(1, weight=1)

        ttk.Label(progress_frame, text="Status").grid(row=0, column=0, sticky="w")
        ttk.Label(progress_frame, textvariable=self.status_var).grid(row=0, column=1, sticky="w")

        ttk.Label(progress_frame, text="Processed").grid(row=1, column=0, sticky="w")
        ttk.Label(progress_frame, textvariable=self.processed_var).grid(row=1, column=1, sticky="w")

        ttk.Label(progress_frame, text="Successful records").grid(row=2, column=0, sticky="w")
        ttk.Label(progress_frame, textvariable=self.success_var).grid(row=2, column=1, sticky="w")

        ttk.Label(progress_frame, text="Not found").grid(row=3, column=0, sticky="w")
        ttk.Label(progress_frame, textvariable=self.not_found_var).grid(row=3, column=1, sticky="w")

        ttk.Label(progress_frame, text="Insurance issues").grid(row=4, column=0, sticky="w")
        ttk.Label(progress_frame, textvariable=self.insurance_var).grid(row=4, column=1, sticky="w")

        ttk.Label(progress_frame, text="Request errors").grid(row=5, column=0, sticky="w")
        ttk.Label(progress_frame, textvariable=self.request_error_var).grid(row=5, column=1, sticky="w")

        ttk.Label(progress_frame, text="Current").grid(row=6, column=0, sticky="w")
        ttk.Label(progress_frame, textvariable=self.current_var).grid(row=6, column=1, sticky="w")

        ttk.Label(progress_frame, text="Run summary").grid(row=7, column=0, sticky="nw")
        summary_message = tk.Message(progress_frame, textvariable=self.summary_var, width=650)
        summary_message.grid(row=7, column=1, sticky="w")

        self.progress_bar = ttk.Progressbar(progress_frame, orient="horizontal", mode="determinate")
        self.progress_bar.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        log_frame = ttk.LabelFrame(self, text="Log")
        log_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = tk.Text(log_frame, height=18, state="disabled", wrap="word")
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

    def _add_entry(
        self,
        frame: ttk.LabelFrame,
        row: int,
        label: str,
        variable: tk.StringVar,
        browse_cmd: Optional[Callable[[], None]] = None
    ) -> None:
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=2)
        entry = ttk.Entry(frame, textvariable=variable)
        entry.grid(row=row, column=1, sticky="ew", pady=2)
        if browse_cmd:
            ttk.Button(frame, text="Browse", command=browse_cmd).grid(row=row, column=2, padx=(8, 0), pady=2)

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
        sleep_per_request = self._parse_int(self.sleep_request_var.get(), "Sleep per request")
        sleep_per_candidate = self._parse_int(self.sleep_candidate_var.get(), "Sleep per candidate")
        sleep_per_batch = self._parse_int(self.sleep_batch_var.get(), "Sleep per batch")

        worker_name = self.worker_name_var.get().strip()
        if not worker_name:
            raise ValueError("Worker name is required.")

        names_file = self.names_file_var.get().strip()
        if not names_file:
            raise ValueError("Names file is required.")

        results_file = self.results_file_var.get().strip()
        if not results_file:
            raise ValueError("Results file is required.")

        return RunConfig(
            working_port=working_port,
            worker_name=worker_name,
            batch_size=batch_size,
            sleep_per_request=sleep_per_request,
            sleep_per_candidate=sleep_per_candidate,
            sleep_per_batch=sleep_per_batch,
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

    def _start_run(self) -> None:
        if self._worker_thread and self._worker_thread.is_alive():
            return
        try:
            config = self._build_config()
        except ValueError as exc:
            self._append_log(f"Config error: {exc}")
            return

        self._stop_event = threading.Event()
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
            self._append_log("Stop requested.")

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
                stop_event=self._stop_event
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
        self.after(200, self._poll_queue)

    def _update_progress(self, payload: dict) -> None:
        processed = int(payload.get("processed", 0))
        total = int(payload.get("total", 0))
        self.processed_var.set(f"{processed}/{total}")
        self.success_var.set(str(payload.get("success", 0)))
        self.not_found_var.set(str(payload.get("not_found", 0)))
        self.insurance_var.set(str(payload.get("insurance_issue", 0)))
        self.request_error_var.set(str(payload.get("request_error", 0)))
        self.current_var.set(payload.get("current") or "")

        if total > 0:
            self.progress_bar.configure(maximum=total, value=processed)
        else:
            self.progress_bar.configure(value=0)

    def _handle_state(self, state: str) -> None:
        if state == "done":
            self.status_var.set("Finished")
            self._set_running(False)
        elif state == "error":
            self.status_var.set("Error")
            self._set_running(False)
        elif state == "stopped":
            self.status_var.set("Stopped")
            self._set_running(False)

    def _set_running(self, running: bool) -> None:
        if running:
            self.status_var.set("Running")
            self.start_button.configure(state="disabled")
            self.stop_button.configure(state="normal")
        else:
            self.start_button.configure(state="normal")
            self.stop_button.configure(state="disabled")

    def _append_log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
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
            status_label = "Finished"

        processed = summary.get("processed", 0)
        total = summary.get("total", 0)
        success = summary.get("success", 0)
        not_found = summary.get("not_found", 0)
        insurance = summary.get("insurance_issue", 0)
        request_error = summary.get("request_error", 0)
        elapsed = summary.get("elapsed_hms", "")
        results_file = summary.get("results_file", "")
        message = summary.get("message", "")

        parts = [
            f"Status: {status_label}",
            f"Processed: {processed}/{total}",
            f"Success: {success}",
            f"Not found: {not_found}",
            f"Insurance issues: {insurance}",
            f"Request errors: {request_error}"
        ]
        if elapsed:
            parts.append(f"Time: {elapsed}")
        if results_file:
            parts.append(f"Results: {results_file}")
        if message:
            parts.append(f"Note: {message}")
        self.summary_var.set(" | ".join(parts))

    def _on_close(self) -> None:
        if self._stop_event and not self._stop_event.is_set():
            self._stop_event.set()
        self.destroy()


if __name__ == "__main__":
    app = ManagerApp()
    app.mainloop()
