# record_view.py
import os
import time
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import cv2


def _open_capture(index: int):
    """
    Try to open a camera on Windows with Media Foundation first (MSMF),
    then fallback to DirectShow (DSHOW). Return (cap, backend_name) or (None, None).
    """
    for backend, name in ((cv2.CAP_MSMF, "MSMF"), (cv2.CAP_DSHOW, "DSHOW"), (cv2.CAP_ANY, "ANY")):
        cap = cv2.VideoCapture(index, backend)
        if cap.isOpened():
            return cap, name
        cap.release()
    return None, None


def _enumerate_cameras(max_probe=5):
    found = []
    for i in range(max_probe):
        cap, backend = _open_capture(i)
        if cap:
            found.append((i, backend))
            cap.release()
    return found


class RecordView(ttk.Frame):
    """
    Record Video screen (functional).
    - Lets the user choose a camera index, resolution, FPS, and output file.
    - Records video to MP4 (H.264-ish via 'mp4v' or system MPEG-4) using OpenCV VideoWriter.
    - No audio capture (keeps it simple and reliable).
    """
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        # ---------- UI ----------
        title = ttk.Label(self, text="Record Video", style="Header.TLabel")
        subtitle = ttk.Label(self, text="Pick a camera, choose settings, select a file, then start recording.", style="Body.TLabel")

        # Camera row
        cam_row = ttk.Frame(self)
        self.cam_list = ttk.Combobox(cam_row, state="readonly", width=28, values=["(scanning...)"])
        self.refresh_btn = ttk.Button(cam_row, text="Refresh", command=self.refresh_cameras)

        # Settings row
        settings = ttk.Frame(self)
        ttk.Label(settings, text="Resolution:").grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.res_combo = ttk.Combobox(settings, state="readonly", width=12,
                                      values=["1280x720", "1920x1080", "640x480"])
        self.res_combo.set("1280x720")

        ttk.Label(settings, text="FPS:").grid(row=0, column=2, sticky="w", padx=(12, 6))
        self.fps_entry = ttk.Entry(settings, width=6)
        self.fps_entry.insert(0, "30")

        # Output row
        out_row = ttk.Frame(self)
        self.out_path_var = tk.StringVar(value="No file selected.")
        out_btn = ttk.Button(out_row, text="Choose Output (.mp4)", command=self.choose_output_file)
        out_label = ttk.Label(out_row, textvariable=self.out_path_var, width=48)

        # Control buttons
        ctrl = ttk.Frame(self)
        self.start_btn = ttk.Button(ctrl, text="Start Recording", command=self.start_recording, state="disabled")
        self.stop_btn  = ttk.Button(ctrl, text="Stop Recording",  command=self.stop_recording, state="disabled")
        back_btn       = ttk.Button(ctrl, text="← Back", command=lambda: controller.show_page("HomePage"))

        # Status
        self.status_var = tk.StringVar(value="Status: idle")
        self.counter_var = tk.StringVar(value="Frames: 0")
        status_row = ttk.Frame(self)
        status_label = ttk.Label(status_row, textvariable=self.status_var, style="Body.TLabel")
        counter_label = ttk.Label(status_row, textvariable=self.counter_var, style="Body.TLabel")

        # Layout
        title.pack(pady=(10, 4))
        subtitle.pack(pady=(0, 12))

        cam_row.pack(fill="x", pady=(0, 10))
        ttk.Label(cam_row, text="Camera:").grid(row=0, column=0, padx=(0, 6))
        self.cam_list.grid(row=0, column=1)
        self.refresh_btn.grid(row=0, column=2, padx=(8, 0))

        settings.pack(pady=(0, 10))
        settings.grid_columnconfigure(1, minsize=100)

        out_row.pack(fill="x", pady=(0, 10))
        out_btn.grid(row=0, column=0, padx=(0, 8))
        out_label.grid(row=0, column=1, sticky="w")

        ctrl.pack(pady=(4, 10))
        self.start_btn.grid(row=0, column=0, padx=6)
        self.stop_btn.grid(row=0, column=1, padx=6)
        back_btn.grid(row=0, column=2, padx=6)

        status_row.pack()
        status_label.grid(row=0, column=0, padx=(0, 12))
        counter_label.grid(row=0, column=1)

        # runtime vars
        self._record_thread = None
        self._stop_flag = threading.Event()
        self._frame_count = 0
        self._cap = None
        self._writer = None

        # kick off camera scan
        self.after(100, self.refresh_cameras)

    # ---------- UI helpers ----------
    def refresh_cameras(self):
        self.cam_list["values"] = ["(scanning...)"]
        self.cam_list.set("(scanning...)")
        self.start_btn.config(state="disabled")
        self.status_var.set("Status: scanning for cameras...")
        def _scan():
            cams = _enumerate_cameras(6)
            values = [f"Index {i} ({backend})" for i, backend in cams] or ["(no cameras found)"]
            self.after(0, lambda: self._apply_cam_scan(values, cams))
        threading.Thread(target=_scan, daemon=True).start()

    def _apply_cam_scan(self, display_values, raw_list):
        self._raw_cam_list = raw_list  # list of (index, backend)
        self.cam_list["values"] = display_values
        sel = display_values[0]
        self.cam_list.set(sel)
        self.status_var.set("Status: idle" if raw_list else "Status: no cameras found")
        # Enable start only when we have cams and output file chosen
        self._update_start_enabled()

    def choose_output_file(self):
        path = filedialog.asksaveasfilename(
            title="Save recorded video",
            defaultextension=".mp4",
            filetypes=[("MP4 video", "*.mp4"), ("AVI", "*.avi"), ("All files", "*.*")]
        )
        if path:
            self.out_path_var.set(path)
            self._update_start_enabled()

    def _update_start_enabled(self):
        has_cam = hasattr(self, "_raw_cam_list") and len(self._raw_cam_list) > 0 and "(no cameras found)" not in (self.cam_list.get() or "")
        has_path = (self.out_path_var.get() != "No file selected.") and len(self.out_path_var.get().strip()) > 0
        self.start_btn.config(state="normal" if (has_cam and has_path) else "disabled")

    # ---------- Recording logic ----------
    def start_recording(self):
        if self._record_thread and self._record_thread.is_alive():
            return

        # parse camera index from combobox selection
        sel = self.cam_list.get()
        if "(no cameras found)" in sel:
            messagebox.showwarning("No camera", "No camera is available.")
            return

        if not hasattr(self, "_raw_cam_list") or len(self._raw_cam_list) == 0:
            messagebox.showwarning("No camera", "No camera is available.")
            return

        # Use the same order as display values; pick the matching tuple
        idx = self.cam_list.current()
        cam_index = self._raw_cam_list[idx][0]  # actual index (int)

        # parse resolution
        try:
            w_str, h_str = self.res_combo.get().split("x")
            width, height = int(w_str), int(h_str)
        except Exception:
            width, height = 1280, 720

        # parse fps
        try:
            fps = int(self.fps_entry.get())
            if fps <= 0: raise ValueError
        except Exception:
            fps = 30

        outfile = self.out_path_var.get().strip()
        if not outfile:
            messagebox.showwarning("Output", "Please choose an output file.")
            return

        # open capture with backend preference
        cap, backend = _open_capture(cam_index)
        if not cap:
            messagebox.showerror("Camera error", f"Could not open camera index {cam_index}.")
            return

        # set capture props (best-effort)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_FPS, fps)

        # fetch actual to sync writer
        actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or width
        actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or height
        actual_fps = cap.get(cv2.CAP_PROP_FPS) or fps
        if actual_fps <= 1:  # some drivers return 0/1; fallback
            actual_fps = fps

        # decide codec based on extension
        ext = os.path.splitext(outfile)[1].lower()
        if ext == ".avi":
            fourcc = cv2.VideoWriter_fourcc(*"XVID")
        else:
            # default to MP4; 'mp4v' is widely available on Windows
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")

        writer = cv2.VideoWriter(outfile, fourcc, float(actual_fps), (actual_w, actual_h))
        if not writer.isOpened():
            cap.release()
            messagebox.showerror("Writer error", "Could not open output file for writing.\nTry another path or extension.")
            return

        # store handles
        self._cap = cap
        self._writer = writer
        self._frame_count = 0
        self._stop_flag.clear()

        # update UI
        self.status_var.set(f"Status: recording (backend {backend}, {actual_w}x{actual_h}@{int(actual_fps)}fps)")
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.refresh_btn.config(state="disabled")
        self.cam_list.config(state="disabled")

        # launch thread
        self._record_thread = threading.Thread(target=self._record_loop, daemon=True)
        self._record_thread.start()
        # UI counter refresher
        self.after(300, self._tick_counter)

    def _record_loop(self):
        try:
            while not self._stop_flag.is_set():
                ok, frame = self._cap.read()
                if not ok:
                    # Give device a breath; if it keeps failing, break
                    time.sleep(0.01)
                    continue
                self._writer.write(frame)
                self._frame_count += 1
        except Exception as e:
            # report in UI thread
            self.after(0, lambda: self.status_var.set(f"Status: error during recording: {e}"))
        finally:
            self._teardown_writer()

    def _tick_counter(self):
        # called periodically to refresh the UI counter
        self.counter_var.set(f"Frames: {self._frame_count}")
        if self._record_thread and self._record_thread.is_alive():
            self.after(300, self._tick_counter)

    def stop_recording(self):
        if not self._record_thread:
            return
        self._stop_flag.set()
        self._record_thread.join(timeout=2.0)
        self._record_thread = None
        self.status_var.set("Status: idle")
        self.stop_btn.config(state="disabled")
        self.start_btn.config(state="normal")
        self.refresh_btn.config(state="normal")
        self.cam_list.config(state="readonly")

    def _teardown_writer(self):
        try:
            if self._writer:
                self._writer.release()
        except Exception:
            pass
        try:
            if self._cap:
                self._cap.release()
        except Exception:
            pass
        self._writer = None
        self._cap = None
