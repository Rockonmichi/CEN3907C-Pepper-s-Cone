# studio_main.py
import tkinter as tk
from tkinter import ttk
from upload_view import UploadView  # existing upload screen
from record_view import RecordView  # separate record screen
from live_view import LiveView  # live streaming screen

APP_TITLE = "Live & Upload Studio"
APP_WIDTH, APP_HEIGHT = 560, 380


class StudioApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(f"{APP_WIDTH}x{APP_HEIGHT}")
        self.minsize(440, 300)
        self.configure(bg="#f7f7fb")

        self.container = ttk.Frame(self, padding=20)
        self.container.pack(fill="both", expand=True)
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.pages = {}
        for Page in (HomePage, LiveView, UploadView, RecordView):
            page = Page(parent=self.container, controller=self)
            self.pages[Page.__name__] = page
            page.grid(row=0, column=0, sticky="nsew")

        self.show_page("HomePage")

        style = ttk.Style(self)
        style.configure("TButton", padding=10)
        style.configure("Header.TLabel", font=("Segoe UI", 16, "bold"))
        style.configure("Body.TLabel", font=("Segoe UI", 10))

    def show_page(self, name: str):
        self.pages[name].tkraise()


class HomePage(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        header = ttk.Label(self, text="Live & Upload Studio", style="Header.TLabel")
        subtitle = ttk.Label(self, text="Choose what you want to do:", style="Body.TLabel")

        buttons = ttk.Frame(self)
        live_btn = ttk.Button(buttons, text="Live Stream", command=lambda: controller.show_page("LiveView"))
        record_btn = ttk.Button(buttons, text="Record Video", command=lambda: controller.show_page("RecordView"))
        upload_btn = ttk.Button(buttons, text="Upload Video", command=lambda: controller.show_page("UploadView"))

        header.pack(pady=(10, 4))
        subtitle.pack(pady=(0, 16))
        buttons.pack()

        live_btn.grid(row=0, column=0, padx=8, pady=8, ipadx=20, ipady=10)
        record_btn.grid(row=0, column=1, padx=8, pady=8, ipadx=20, ipady=10)
        upload_btn.grid(row=0, column=2, padx=8, pady=8, ipadx=20, ipady=10)


if __name__ == "__main__":
    app = StudioApp()
    app.mainloop()
