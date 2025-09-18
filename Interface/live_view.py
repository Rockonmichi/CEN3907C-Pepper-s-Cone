# live_view.py
#
# Live display view (no streaming).
# - Camera selection by index (MSMF/DSHOW/ANY) or by name (DSHOW via ffmpeg listing)
# - Stable, LARGE in-app preview on the right (fixed-size container; UI doesn't jump)
# - Fullscreen output window to show your warped result (placeholder provided)

import time
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox

import numpy as np
import mediapipe as mp

import cv2
from PIL import Image, ImageTk

# Big (but reasonable) 16:9 preview area; tweak if you want
PREVIEW_W = 800
PREVIEW_H = 450

FRAME_SIZE = 400
CANVAS_SIZE = 800

# ---------- Warp Helpers ----------
def enhance_saturation_contrast(image_bgr, saturation_scale=1.3, contrast_alpha=1.2, brightness_beta=10):
    # BGR → HSV (float), boost S, back to BGR, then contrast/brightness
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * saturation_scale, 0, 255)
    enhanced = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    enhanced = cv2.convertScaleAbs(enhanced, alpha=contrast_alpha, beta=brightness_beta)
    return enhanced


def build_cone_maps(frame_size: int, canvas_size: int):
    """Precompute map_x, map_y for a circular cone warp like your prototype."""
    map_x = np.zeros((canvas_size, canvas_size), dtype=np.float32)
    map_y = np.zeros((canvas_size, canvas_size), dtype=np.float32)

    cx = cy = canvas_size // 2
    max_r = canvas_size // 2

    for y in range(canvas_size):
        dy = y - cy
        for x in range(canvas_size):
            dx = x - cx
            r = np.hypot(dx, dy)
            if r > max_r:
                continue
            angle = np.arctan2(dy, dx)  # -pi..pi
            if -np.pi / 2 <= angle <= np.pi / 2:
                # angle → [0..1], radius (flipped) → [0..1]
                norm_angle = (angle + (np.pi / 2)) / np.pi
                norm_radius = 1.0 - (r / max_r)

                sx = int(np.clip(norm_angle * frame_size, 0, frame_size - 1))
                sy = int(np.clip(norm_radius * frame_size, 0, frame_size - 1))
                map_x[y, x] = sx
                map_y[y, x] = sy
            else:
                map_x[y, x] = 0
                map_y[y, x] = 0
    return map_x, map_y


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
    # Mirrors record_view for consistency.
    src = f"video={name}"
    cap = cv2.VideoCapture(src, cv2.CAP_DSHOW)
    if cap.isOpened():
        return cap, "name", cv2.CAP_DSHOW
    cap.release()
    return None, None, None


def _list_dshow_devices_via_ffmpeg():
    """Return (video_names, audio_names) using ffmpeg's DirectShow listing."""
    try:
        proc = subprocess.Popen(["ffmpeg", "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        out, _ = proc.communicate(timeout=6)
    except Exception:
        return [], []

    import re

    video, audio = [], []
    m = re.compile(r'^\[dshow .*?\]\s+"([^"]+)"\s+\((video|audio)\)\s*$', re.IGNORECASE)
    for line in (out or "").splitlines():
        line = line.strip()
        mm = m.match(line)
        if not mm:
            continue
        name, kind = mm.group(1), mm.group(2).lower()
        (video if kind == "video" else audio).append(name)

    # dedupe while preserving order
    def dedup(xs):
        seen, out = set(), []
        for x in xs:
            if x not in seen:
                seen.add(x)
                out.append(x)
        return out
    
    return dedup(video), dedup(audio)


class LiveView(ttk.Frame):
    """Live display (preview + fullscreen) using the same open logic as record_view."""

    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        # --- Title ---
        ttk.Label(self, text="Live Display", style="Header.TLabel").pack(pady=(10, 4))
        ttk.Label(self, text="Pick a camera (index or name), preview it, then open fullscreen for the warped output.", style="Body.TLabel").pack(pady=(0, 10))

        # Two panes: left controls, right preview
        top = ttk.Frame(self)
        top.pack(fill="both", expand=True)
        left = ttk.Frame(top)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        right = ttk.Frame(top)
        right.pack(side="right", fill="both", expand=True, padx=(8, 0))

        # --- Camera selection ---
        cam_box = ttk.LabelFrame(left, text="Camera Selection")
        cam_box.pack(fill="x", padx=4, pady=(0, 10))
        cam_box.grid_columnconfigure(0, weight=1)

        self.sel_mode = tk.StringVar(value="index")
        r1 = ttk.Radiobutton(cam_box, text="By Index", variable=self.sel_mode, value="index", command=self._update_controls)
        r2 = ttk.Radiobutton(cam_box, text="By Name (DSHOW)", variable=self.sel_mode, value="name", command=self._update_controls)

        # index row
        idx_row = ttk.Frame(cam_box)
        ttk.Label(idx_row, text="Index:").grid(row=0, column=0, padx=(0, 6))
        self.idx_combo = ttk.Combobox(idx_row, state="readonly", width=36, values=self._scan_indices())
        self.idx_combo.set(self.idx_combo["values"][0])
        self.idx_combo.grid(row=0, column=1, sticky="w")
        ttk.Button(idx_row, text="Rescan", command=self._rescan_indices).grid(row=0, column=2, padx=6)
        ttk.Label(idx_row, text="Backend:").grid(row=0, column=3, padx=(12, 6))
        self.backend_combo = ttk.Combobox(idx_row, state="readonly", values=[label for (label, _) in BACKENDS], width=22)
        self.backend_combo.set(BACKENDS[0][0])
        self.backend_combo.grid(row=0, column=4, padx=(0, 6))

        # name row
        name_row = ttk.Frame(cam_box)
        ttk.Label(name_row, text="Device Name:").grid(row=0, column=0, padx=(0, 6))
        self.name_entry = ttk.Entry(name_row, width=36)
        self.name_entry.grid(row=0, column=1)
        ttk.Button(name_row, text="List Cameras (ffmpeg)", command=self._list_names_ffmpeg).grid(row=0, column=2, padx=6)
        self.names_combo = ttk.Combobox(name_row, state="readonly", width=36, values=[])
        self.names_combo.grid(row=1, column=1, pady=(6, 0), sticky="w")
        ttk.Button(name_row, text="Use Selected", command=self._use_selected_name).grid(row=1, column=2, padx=6, pady=(6, 0))

        # Arrange like: radio, its row; radio, its row
        r1.grid(row=0, column=0, sticky="w", padx=8, pady=(6, 2))
        idx_row.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 6))
        r2.grid(row=2, column=0, sticky="w", padx=8, pady=(8, 2))
        name_row.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 6))

        # --- Video settings ---
        settings = ttk.LabelFrame(left, text="Video Settings")
        settings.pack(fill="x", padx=4, pady=(0, 10))
        ttk.Label(settings, text="Resolution:").grid(row=0, column=0, padx=(8, 6), pady=8, sticky="w")
        self.res_combo = ttk.Combobox(settings, state="readonly", width=12, values=["1280x720", "1920x1080", "640x480"])
        self.res_combo.set("1280x720")
        self.res_combo.grid(row=0, column=1, sticky="w")
        ttk.Label(settings, text="FPS:").grid(row=0, column=2, padx=(16, 6), pady=8, sticky="w")
        self.fps_entry = ttk.Entry(settings, width=6)
        self.fps_entry.insert(0, "30")
        self.fps_entry.grid(row=0, column=3, sticky="w")

        # --- Actions ---
        actions = ttk.Frame(left)
        actions.pack(pady=(6, 2))
        self.btn_preview = ttk.Button(actions, text="Start Preview", command=self._start_preview)
        self.btn_stop_preview = ttk.Button(actions, text="Stop Preview", command=self._stop_preview, state="disabled")
        self.btn_fullscreen = ttk.Button(actions, text="Open Fullscreen", command=self._start_fullscreen)
        self.btn_close_fullscreen = ttk.Button(actions, text="Close Fullscreen", command=self._stop_fullscreen, state="disabled")
        back_btn = ttk.Button(actions, text="Back", command=lambda: controller.show_page("HomePage"))
        self.btn_preview.grid(row=0, column=0, padx=6)
        self.btn_stop_preview.grid(row=0, column=1, padx=6)
        self.btn_fullscreen.grid(row=0, column=2, padx=6)
        self.btn_close_fullscreen.grid(row=0, column=3, padx=6)
        back_btn.grid(row=0, column=4, padx=6)

        # --- Status ---
        status_box = ttk.Frame(left)
        status_box.pack(fill="x", padx=4, pady=(8, 0))
        self.status = tk.StringVar(value="Status: idle")
        ttk.Label(status_box, textvariable=self.status).pack(anchor="w")

        # --- Right: LARGE fixed-size preview (no jumping) ---
        ttk.Label(right, text="Preview", style="Body.TLabel").pack()
        preview_container = tk.Frame(right, width=PREVIEW_W, height=PREVIEW_H, bg="black", highlightthickness=0)
        preview_container.pack(padx=4, pady=4)
        preview_container.pack_propagate(False)  # keep container size fixed

        self._preview_label = tk.Label(preview_container, bg="black", bd=0, highlightthickness=0)
        self._preview_label.place(relx=0.5, rely=0.5, anchor="center")

        # Preview state
        self._preview_img = None
        self._last_bgr = None
        self._frame_lock = threading.Lock()
        self._cap = None
        self._preview_thread = None
        self._stop_preview_evt = threading.Event()

        # Fullscreen window state
        self.fs_win = None
        self._fs_label = None
        self._fs_img = None
        self._fs_running = False
        
        # Precompute warp maps (once)
        self._map_x, self._map_y = build_cone_maps(FRAME_SIZE, CANVAS_SIZE)
        self._segmentor = mp.solutions.selfie_segmentation.SelfieSegmentation(model_selection=1)


        # init
        self._update_controls()
        self.after(33, self._preview_tick)  # UI repaint timer

    # ---------- UI helpers ----------
    def _update_controls(self):
        mode = self.sel_mode.get()
        for w in (self.idx_combo, self.backend_combo):
            w.config(state=("normal" if mode == "index" else "disabled"))
        for w in (self.name_entry, self.names_combo):
            w.config(state=("normal" if mode == "name" else "disabled"))

    def _list_names_ffmpeg(self):
        vids, _ = _list_dshow_devices_via_ffmpeg()
        if vids:
            self.names_combo["values"] = vids
            self.names_combo.set(vids[0])
        else:
            messagebox.showwarning("ffmpeg", "No DirectShow video devices found.\nClose Zoom/Teams/OBS and retry.")

    def _use_selected_name(self):
        name = self.names_combo.get().strip()
        if name:
            self.name_entry.delete(0, tk.END)
            self.name_entry.insert(0, name)

    def _scan_indices(self, max_probe=6):
        """Build friendly labels like '0 – Integrated Webcam (MSMF)'."""
        friendly = []
        vids, _ = _list_dshow_devices_via_ffmpeg()  # may be empty; that's fine
        for i in range(max_probe):
            for label, api in BACKENDS:
                cap = cv2.VideoCapture(i, api)
                if cap.isOpened():
                    cap.release()
                    pretty = vids[i] if i < len(vids) else "Camera"
                    friendly.append(f"{i} – {pretty} ({label})")
                    break
        return friendly or ["(no cameras found)"]

    def _rescan_indices(self):
        vals = self._scan_indices()
        self.idx_combo["values"] = vals
        self.idx_combo.set(vals[0])

    # ---------- Preview ----------
    def _start_preview(self):
        if self._preview_thread and self._preview_thread.is_alive():
            return  # already running

        # open camera
        if self.sel_mode.get() == "index":
            sel = self.idx_combo.get()
            try:
                raw = sel.split("–")[0] if "–" in sel else sel.split("-")[0]
                idx = int(raw.strip())
            except Exception:
                try:
                    idx = int(sel.strip())
                except Exception:
                    idx = 0
            api_label = self.backend_combo.get()
            api_pref = dict(BACKENDS)[api_label]
            cap, _, _ = _open_by_index(idx, api_pref)
            if not cap:
                messagebox.showerror("Camera", f"Could not open index {idx} with {api_label}. Try name mode.")
                return
        else:
            name = self.name_entry.get().strip()
            if not name:
                messagebox.showwarning("Camera", "Enter/select a device name first.")
                return
            cap, _, _ = _open_by_name_dshow(name)
            if not cap:
                messagebox.showerror("Camera", f"Could not open device by name:\n{name}\n(Use the list button and match exactly.)")
                return

        # size/fps
        try:
            w_str, h_str = self.res_combo.get().split("x")
            width, height = int(w_str), int(h_str)
        except Exception:
            width, height = 1280, 720
        try:
            fps = max(1, int(self.fps_entry.get()))
        except Exception:
            fps = 30

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_FPS, fps)

        self._cap = cap
        self._stop_preview_evt.clear()
        self._preview_thread = threading.Thread(target=self._preview_loop, daemon=True)
        self._preview_thread.start()
        self.btn_preview.config(state="disabled")
        self.btn_stop_preview.config(state="normal")
        self.status.set("Status: previewing")

    def _stop_preview(self):
        self._stop_preview_evt.set()
        if self._preview_thread:
            self._preview_thread.join(timeout=1.5)
        self._preview_thread = None
        if self._cap:
            try:
                self._cap.release()
            except Exception:
                pass
        self._cap = None
        self.btn_preview.config(state="normal")
        self.btn_stop_preview.config(state="disabled")
        self.status.set("Status: idle")

    def _preview_loop(self):
        try:
            while not self._stop_preview_evt.is_set():
                ok, frame = self._cap.read()
                if not ok:
                    time.sleep(0.01)
                    continue
                with self._frame_lock:
                    self._last_bgr = frame
        except Exception as e:
            self.after(0, lambda e=e: messagebox.showerror("Preview error", str(e)))

    def _preview_tick(self):
        """Show RAW camera frame (unwarped) in the small preview pane."""
        frame = None
        with self._frame_lock:
            if self._last_bgr is not None:
                frame = self._last_bgr

        if frame is not None:
            fh, fw = frame.shape[:2]
            scale = min(PREVIEW_W / fw, PREVIEW_H / fh)
            new_w = max(1, int(fw * scale))
            new_h = max(1, int(fh * scale))
            resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)

            # IMPORTANT: no warp here — preview shows the unwarped camera feed
            rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            img = ImageTk.PhotoImage(Image.fromarray(rgb))
            self._preview_label.config(image=img)
            self._preview_label.image = img  # keep a reference

        self.after(33, self._preview_tick)  # ~30 fps UI update

    # ---------- Fullscreen display ----------
    def _start_fullscreen(self):
        if self.fs_win and self._fs_running:
            return
        if self._cap is None:
            messagebox.showwarning("Fullscreen", "Start the camera preview first.")
            return

        self.fs_win = tk.Toplevel(self)
        self.fs_win.title("Pepper's Cone Display")
        self.fs_win.attributes("-fullscreen", True)
        self.fs_win.configure(bg="black")
        self.fs_win.bind("<Escape>", lambda e: self._stop_fullscreen())
        self.fs_win.protocol("WM_DELETE_WINDOW", self._stop_fullscreen)

        self._fs_label = tk.Label(self.fs_win, bg="black")
        self._fs_label.pack(fill="both", expand=True)

        self._fs_running = True
        self.btn_fullscreen.config(state="disabled")
        self.btn_close_fullscreen.config(state="normal")
        self.status.set("Status: fullscreen output")
        self._fullscreen_tick()

    def _stop_fullscreen(self):
        self._fs_running = False
        if self.fs_win:
            try:
                self.fs_win.destroy()
            except Exception:
                pass
        self.fs_win = None
        self._fs_label = None
        self._fs_img = None
        self.btn_fullscreen.config(state="normal")
        self.btn_close_fullscreen.config(state="disabled")
        self.status.set("Status: idle")

    def _fullscreen_tick(self):
        if not self._fs_running:
            return
        frame = None
        with self._frame_lock:
            if self._last_bgr is not None:
                frame = self._last_bgr

        if frame is not None:
            # Apply your warp here for the projector/cone layout
            warped = self._apply_warp(frame)

            # Fit to current screen size while preserving aspect
            try:
                sw = self.fs_win.winfo_width()
                sh = self.fs_win.winfo_height()
                fh, fw = warped.shape[:2]
                scale = min(sw / fw, sh / fh)
                new_w, new_h = max(1, int(fw * scale)), max(1, int(fh * scale))
                disp = cv2.resize(warped, (new_w, new_h), interpolation=cv2.INTER_AREA)
            except Exception:
                disp = warped

            rgb = cv2.cvtColor(disp, cv2.COLOR_BGR2RGB)
            img = ImageTk.PhotoImage(Image.fromarray(rgb))
            if self._fs_label is not None:
                self._fs_label.config(image=img)
                self._fs_label.image = img
                self._fs_img = img  # keep a reference

        # Aim ~60 Hz for smoother motion; adjust as needed
        self.after(16, self._fullscreen_tick)

    
    # ---------- Warp Display ----------
    def _apply_warp(self, frame_bgr):
        """
        Takes a BGR frame from the camera, returns a warped BGR image.
        Steps mirror your CircularConeLive.py:
        - resize to FRAME_SIZE x FRAME_SIZE
        - optional background removal (MediaPipe)
        - center/scale subject
        - remap with precomputed circular-cone maps
        - saturation/contrast enhancement
        """
        # 1) square input
        sq = cv2.resize(frame_bgr, (FRAME_SIZE, FRAME_SIZE), interpolation=cv2.INTER_AREA)

        # 2) optional background removal
        if self._segmentor is not None:
            rgb = cv2.cvtColor(sq, cv2.COLOR_BGR2RGB)
            try:
                seg = self._segmentor.process(rgb)
                mask = (seg.segmentation_mask > 0.5)
                fg = np.zeros_like(sq)
                fg[mask] = sq[mask]
            except Exception:
                fg = sq
        else:
            fg = sq

        # 3) center + scale (same defaults as prototype: 0.6)
        scale = 0.6
        scaled = cv2.resize(fg, (0, 0), fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        padded = np.zeros_like(fg)
        y_off = (FRAME_SIZE - scaled.shape[0]) // 2
        x_off = (FRAME_SIZE - scaled.shape[1]) // 2
        padded[y_off:y_off + scaled.shape[0], x_off:x_off + scaled.shape[1]] = scaled

        # 4) cone warp
        warped = cv2.remap(
            padded, self._map_x, self._map_y,
            interpolation=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0)
        )

        # 5) color pop
        enhanced = enhance_saturation_contrast(
            warped, saturation_scale=1.4, contrast_alpha=1.8, brightness_beta=-25
        )

        return enhanced

