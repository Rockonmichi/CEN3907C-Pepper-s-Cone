# record_view.py (with live preview)
import base64
import os
import time
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk


import cv2

# ---------- Backends ----------
BACKENDS = [
    ("MSMF (Windows 10/11)", cv2.CAP_MSMF),
    ("DSHOW (DirectShow)", cv2.CAP_DSHOW),
    ("ANY (let OpenCV pick)", cv2.CAP_ANY),
]


def _open_by_index(index: int, api_pref: int):
    cap = cv2.VideoCapture(index, api_pref)
    if cap.isOpened():
        return cap, "index", api_pref
    cap.release()
    return None, None, None


def _open_by_name_dshow(name: str):
    src = f"video={name}"
    cap = cv2.VideoCapture(src, cv2.CAP_DSHOW)
    if cap.isOpened():
        return cap, "name", cv2.CAP_DSHOW
    cap.release()
    return None, None, None


def _enumerate_indices(max_probe=6):
    found = []
    for i in range(max_probe):
        for label, api in BACKENDS:
            cap = cv2.VideoCapture(i, api)
            if cap.isOpened():
                found.append((i, label))
                cap.release()
                break
    return found


def _list_dshow_devices_via_ffmpeg():
    try:
        proc = subprocess.Popen(["ffmpeg", "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        out, _ = proc.communicate(timeout=6)
    except Exception:
        return [], []

    video, audio = [], []
    current = None
    for line in out.splitlines():
        line = line.strip()
        if "DirectShow video devices" in line:
            current = "video"
            continue
        if "DirectShow audio devices" in line:
            current = "audio"
            continue
        if line.startswith('"') and line.endswith('"'):
            name = line.strip('"')
            if current == "video":
                video.append(name)
            elif current == "audio":
                audio.append(name)
    return video, audio


class RecordView(ttk.Frame):
    """
    Functional recorder with preview.
    - Open by index (MSMF/DSHOW/ANY) or by name (DSHOW).
    - Records to MP4 (video only) via OpenCV VideoWriter.
    - Shows a live preview while recording (no Pillow required).
    """

    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        # ----- Title -----
        title = ttk.Label(self, text="Record Video", style="Header.TLabel")
        subtitle = ttk.Label(self, text="Pick camera (by index or name), choose settings, set output, then record.", style="Body.TLabel")
        title.pack(pady=(10, 4))
        subtitle.pack(pady=(0, 10))

        # We’ll put controls on the left, preview on the right
        top = ttk.Frame(self)
        top.pack(fill="both", expand=True)
        left = ttk.Frame(top)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        right = ttk.Frame(top)
        right.pack(side="right", fill="both", padx=(8, 0))

        # ----- Camera selection (left) -----
        cam_mode = ttk.LabelFrame(left, text="Camera Selection")
        cam_mode.pack(fill="x", padx=4, pady=(0, 10))

        self.sel_mode = tk.StringVar(value="index")
        r1 = ttk.Radiobutton(cam_mode, text="By Index", variable=self.sel_mode, value="index", command=self._update_controls)
        r2 = ttk.Radiobutton(cam_mode, text="By Name (DSHOW)", variable=self.sel_mode, value="name", command=self._update_controls)

        idx_row = ttk.Frame(cam_mode)
        ttk.Label(idx_row, text="Index:").grid(row=0, column=0, padx=(0, 6))
        self.idx_combo = ttk.Combobox(idx_row, state="readonly", width=20, values=["(scan...)"])
        self.idx_combo.set("(scan...)")
        self.btn_scan_idx = ttk.Button(idx_row, text="Scan Indices", command=self.scan_indices)

        ttk.Label(idx_row, text="Backend:").grid(row=0, column=3, padx=(12, 6))
        self.backend_combo = ttk.Combobox(idx_row, state="readonly", values=[label for (label, _) in BACKENDS], width=22)
        self.backend_combo.set(BACKENDS[0][0])

        name_row = ttk.Frame(cam_mode)
        ttk.Label(name_row, text="Device Name:").grid(row=0, column=0, padx=(0, 6))
        self.name_entry = ttk.Entry(name_row, width=36)
        self.btn_list_names = ttk.Button(name_row, text="List Cameras (ffmpeg)", command=self.list_names_ffmpeg)
        self.names_combo = ttk.Combobox(name_row, state="readonly", width=36, values=[])
        self.btn_use_selected = ttk.Button(name_row, text="Use Selected", command=self.use_selected_name)

        r1.pack(anchor="w", padx=8, pady=(6, 2))
        idx_row.pack(fill="x", padx=16, pady=(0, 6))
        self.idx_combo.grid(row=0, column=1)
        self.btn_scan_idx.grid(row=0, column=2, padx=6)
        self.backend_combo.grid(row=0, column=4, padx=(0, 6))

        r2.pack(anchor="w", padx=8, pady=(8, 2))
        name_row.pack(fill="x", padx=16, pady=(0, 6))
        self.name_entry.grid(row=0, column=1)
        self.btn_list_names.grid(row=0, column=2, padx=6)
        self.names_combo.grid(row=1, column=1, pady=(6, 0), sticky="w")
        self.btn_use_selected.grid(row=1, column=2, padx=6, pady=(6, 0))

        # ----- Settings (left) -----
        settings = ttk.LabelFrame(left, text="Settings")
        settings.pack(fill="x", padx=4, pady=(0, 10))

        ttk.Label(settings, text="Resolution:").grid(row=0, column=0, padx=(8, 6), pady=8, sticky="w")
        self.res_combo = ttk.Combobox(settings, state="readonly", width=12, values=["1280x720", "1920x1080", "640x480"])
        self.res_combo.set("1280x720")
        self.res_combo.grid(row=0, column=1, sticky="w")

        ttk.Label(settings, text="FPS:").grid(row=0, column=2, padx=(16, 6), pady=8, sticky="w")
        self.fps_entry = ttk.Entry(settings, width=6)
        self.fps_entry.insert(0, "30")
        self.fps_entry.grid(row=0, column=3, sticky="w")

        # ----- Output (left) -----
        out_row = ttk.Frame(left)
        out_row.pack(fill="x", padx=4, pady=(0, 10))
        self.out_path = tk.StringVar(value="No file selected.")
        out_btn = ttk.Button(out_row, text="Choose Output (.mp4)", command=self.choose_output)
        out_lbl = ttk.Label(out_row, textvariable=self.out_path, width=48)
        out_btn.grid(row=0, column=0, padx=(0, 8))
        out_lbl.grid(row=0, column=1, sticky="w")

        # ----- Controls (left) -----
        ctrl = ttk.Frame(left)
        ctrl.pack(pady=(4, 8))
        self.btn_start = ttk.Button(ctrl, text="Start Recording", command=self.start_record, state="disabled")
        self.btn_stop = ttk.Button(ctrl, text="Stop Recording", command=self.stop_record, state="disabled")
        back_btn = ttk.Button(ctrl, text="← Back", command=lambda: self.controller.show_page("HomePage"))
        self.btn_start.grid(row=0, column=0, padx=6)
        self.btn_stop.grid(row=0, column=1, padx=6)
        back_btn.grid(row=0, column=2, padx=6)

        # ----- Status (left) -----
        status_row = ttk.Frame(left)
        status_row.pack()
        self.status = tk.StringVar(value="Status: idle")
        self.frames = tk.StringVar(value="Frames: 0")
        ttk.Label(status_row, textvariable=self.status).grid(row=0, column=0, padx=(0, 12))
        ttk.Label(status_row, textvariable=self.frames).grid(row=0, column=1)

        # ----- Preview (right) -----
        ttk.Label(right, text="Preview", style="Body.TLabel").pack()
        self.preview_w = 320
        self.preview_h = 180  # 16:9 default; will adapt
        self._preview_label = tk.Label(right, bg="#000", width=self.preview_w, height=self.preview_h)
        self._preview_label.pack(padx=4, pady=4)
        self._preview_img = None  # keep reference to avoid GC
        self._last_bgr = None  # latest frame (BGR) from record loop
        self._frame_lock = threading.Lock()

        # runtime vars
        self._cap = None
        self._writer = None
        self._stop_evt = threading.Event()
        self._rec_thread = None
        self._frame_count = 0

        # initial scan + UI init
        self.scan_indices()
        self._update_controls()
        self._update_start_enabled()
        self.after(100, self._preview_tick)  # start preview timer (polls self._last_bgr)

    # ---------- UI Helpers ----------
    def _update_controls(self):
        mode = self.sel_mode.get()
        state_idx = "normal" if mode == "index" else "disabled"
        state_name = "normal" if mode == "name" else "disabled"
        for w in (self.idx_combo, self.btn_scan_idx, self.backend_combo):
            w.config(state=state_idx)
        for w in (self.name_entry, self.btn_list_names, self.names_combo, self.btn_use_selected):
            w.config(state=state_name)
        self._update_start_enabled()

    def _update_start_enabled(self):
        has_output = self.out_path.get() != "No file selected."
        has_camera = False
        if self.sel_mode.get() == "index":
            has_camera = self.idx_combo.get() and "(no indices)" not in self.idx_combo.get()
        else:
            has_camera = len(self.name_entry.get().strip()) > 0
        self.btn_start.config(state="normal" if (has_output and has_camera) else "disabled")

    def scan_indices(self):
        self.idx_combo["values"] = ["(scanning...)"]
        self.idx_combo.set("(scanning...)")
        self.status.set("Status: scanning indices...")

        def _scan():
            found = _enumerate_indices(8)
            vals = [f"{i} ({backend})" for i, backend in found] or ["(no indices)"]
            self.after(0, lambda: self._apply_idx_scan(vals))

        threading.Thread(target=_scan, daemon=True).start()

    def _apply_idx_scan(self, values):
        self.idx_combo["values"] = values
        self.idx_combo.set(values[0])
        self.status.set("Status: idle")
        self._update_start_enabled()

    def list_names_ffmpeg(self):
        vids, _ = _list_dshow_devices_via_ffmpeg()
        if not vids:
            messagebox.showinfo("ffmpeg", "No video devices found (or ffmpeg not available).")
            return
        self.names_combo["values"] = vids
        if vids:
            self.names_combo.set(vids[0])

    def use_selected_name(self):
        name = self.names_combo.get().strip()
        if name:
            self.name_entry.delete(0, tk.END)
            self.name_entry.insert(0, name)
        self._update_start_enabled()

    def choose_output(self):
        path = filedialog.asksaveasfilename(title="Save recorded video", defaultextension=".mp4", filetypes=[("MP4 video", "*.mp4"), ("AVI", "*.avi"), ("All files", "*.*")])
        if path:
            self.out_path.set(path)
        self._update_start_enabled()

    # ---------- Recording ----------
    def start_record(self):
        if self._rec_thread and self._rec_thread.is_alive():
            return
        outfile = self.out_path.get()
        if not outfile or outfile == "No file selected.":
            messagebox.showwarning("Output", "Please choose an output file.")
            return

        # Open capture
        mode = self.sel_mode.get()
        if mode == "index":
            sel = self.idx_combo.get()
            if "(no indices)" in sel:
                messagebox.showwarning("Camera", "No working indices found.")
                return
            try:
                idx = int(sel.split()[0])
            except Exception:
                idx = 0
            api_label = self.backend_combo.get()
            api_pref = dict(BACKENDS)[api_label]
            cap, _, _ = _open_by_index(idx, api_pref)
            if not cap:
                messagebox.showerror("Camera", f"Could not open index {idx} with {api_label}. Try name mode.")
                return
            backend_used = api_label
        else:
            name = self.name_entry.get().strip()
            if not name:
                messagebox.showwarning("Camera", "Enter a device name (or use the list button).")
                return
            cap, _, _ = _open_by_name_dshow(name)
            if not cap:
                messagebox.showerror("Camera", f"Could not open device by name:\n{name}\n(Ensure it matches the ffmpeg list exactly.)")
                return
            backend_used = "DSHOW (name)"

        # Settings
        try:
            w_str, h_str = self.res_combo.get().split("x")
            width, height = int(w_str), int(h_str)
        except Exception:
            width, height = 1280, 720
        try:
            fps = int(self.fps_entry.get())
            fps = max(1, fps)
        except Exception:
            fps = 30

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_FPS, fps)

        actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or width
        actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or height
        actual_fps = cap.get(cv2.CAP_PROP_FPS) or fps
        if actual_fps <= 1:
            actual_fps = fps

        # Adapt preview aspect to camera
        self._set_preview_aspect(actual_w, actual_h)

        ext = os.path.splitext(outfile)[1].lower()
        fourcc = cv2.VideoWriter_fourcc(*("XVID" if ext == ".avi" else "mp4v"))
        writer = cv2.VideoWriter(outfile, fourcc, float(actual_fps), (actual_w, actual_h))
        if not writer.isOpened():
            cap.release()
            messagebox.showerror("Writer", "Could not open output file. Try a different path/extension.")
            return

        # Store handles
        self._cap = cap
        self._writer = writer
        self._frame_count = 0
        self._stop_evt.clear()

        self.status.set(f"Status: recording ({backend_used}, {actual_w}x{actual_h}@{int(actual_fps)}fps)")
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")

        # Launch record thread
        self._rec_thread = threading.Thread(target=self._record_loop, daemon=True)
        self._rec_thread.start()
        # Start UI counters/preview already running via after()

    def _record_loop(self):
        try:
            while not self._stop_evt.is_set():
                ok, frame = self._cap.read()
                if not ok:
                    time.sleep(0.01)
                    continue
                # Save latest frame for preview
                with self._frame_lock:
                    self._last_bgr = frame.copy()
                # Write to file
                self._writer.write(frame)
                self._frame_count += 1
        except Exception as e:
            self.after(0, lambda e=e: self.status.set(f"Status: error: {e}"))
        finally:
            try:
                if self._writer:
                    self._writer.release()
            finally:
                self._writer = None
            try:
                if self._cap:
                    self._cap.release()
            finally:
                self._cap = None

    def stop_record(self):
        if not self._rec_thread:
            return
        self._stop_evt.set()
        self._rec_thread.join(timeout=2.0)
        self._rec_thread = None
        self.btn_stop.config(state="disabled")
        self.btn_start.config(state="normal")
        self.status.set("Status: idle")

    # ---------- Preview ----------
    def _preview_tick(self):
        """
        Pull latest BGR frame, convert to RGB, and display via Pillow (ImageTk).
        This avoids Tk's PNG decoding quirks and fixes the blue-tint issue.
        """
        frame = None
        with self._frame_lock:
            if self._last_bgr is not None:
                frame = self._last_bgr

        if frame is not None:
            # Fit to preview box while keeping aspect
            ph, pw = self.preview_h, self.preview_w
            fh, fw = frame.shape[:2]
            scale = min(pw / fw, ph / fh)
            new_w, new_h = max(1, int(fw * scale)), max(1, int(fh * scale))
            resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)

            # Convert BGR -> RGB (critical for correct colors)
            rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

            # Hand off to Tk via Pillow
            pil_img = Image.fromarray(rgb)  # mode "RGB"
            img = ImageTk.PhotoImage(image=pil_img)
            self._preview_label.config(image=img, width=self.preview_w, height=self.preview_h)
            self._preview_label.image = img  # keep a reference

        # Update counter and schedule next tick
        self.frames.set(f"Frames: {self._frame_count}")
        self.after(33, self._preview_tick)  # ~30 FPS UI update

    def _set_preview_aspect(self, w, h):
        # set preview box size to a nice fit (max width 360, keep aspect)
        maxw = 360
        scale = maxw / float(w)
        pw = int(w * scale)
        ph = int(h * scale)
        # clamp reasonable size
        pw = max(200, min(360, pw))
        ph = max(120, min(240, ph))
        self.preview_w, self.preview_h = pw, ph
        self._preview_label.config(width=pw, height=ph)
