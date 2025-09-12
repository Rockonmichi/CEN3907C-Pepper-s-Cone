import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

class UploadView(ttk.Frame):
    """
    Upload screen:
      - Choose a video from the user's device (MP4/MOV/MKV/WEBM)
      - Shows selected filename
      - (Optional) placeholder "Upload" button to wire to your backend later
    """
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.selected_path = tk.StringVar(value="No file selected.")

        title = ttk.Label(self, text="Upload Video", style="Header.TLabel")
        subtitle = ttk.Label(self, text="Pick a video from your device.", style="Body.TLabel")

        pick_row = ttk.Frame(self)
        pick_btn = ttk.Button(pick_row, text="Choose File", command=self.choose_file)
        self.path_label = ttk.Label(pick_row, textvariable=self.selected_path, width=48)

        actions = ttk.Frame(self)
        upload_btn = ttk.Button(actions, text="Upload (stub)", command=self.do_upload_stub)
        back_btn = ttk.Button(actions, text="← Back", command=lambda: controller.show_page("HomePage"))

        title.pack(pady=(10, 4))
        subtitle.pack(pady=(0, 16))
        pick_row.pack(fill="x", pady=(0, 12))
        pick_btn.grid(row=0, column=0, padx=(0, 8))
        self.path_label.grid(row=0, column=1, sticky="w")

        actions.pack(pady=(8, 0))
        upload_btn.grid(row=0, column=0, padx=(0, 8))
        back_btn.grid(row=0, column=1)

        # Tip text
        tip = ttk.Label(self, text="(This is a stub—wire to your backend later.)", style="Body.TLabel")
        tip.pack(pady=(12, 0))

    def choose_file(self):
        path = filedialog.askopenfilename(
            title="Choose a video",
            filetypes=[
                ("Video files", "*.mp4 *.mov *.mkv *.webm"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.selected_path.set(path)

    def do_upload_stub(self):
        path = self.selected_path.get()
        if not path or path == "No file selected.":
            messagebox.showwarning("No file", "Please choose a video file first.")
            return
        # Placeholder: replace with real upload logic later
        fname = os.path.basename(path)
        messagebox.showinfo("Upload", f"Stub: would upload\n{fname}\n\n(Replace this with your real upload code.)")
