import tkinter as tk
from tkinter import scrolledtext, ttk
import yt_dlp
import threading
import os
import sys


def base_dir():
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(__file__)


BASE_DIR = base_dir()

DOWNLOAD_DIR = os.path.expanduser("~/Documents/Downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def download_links(links, progress_window, progress_bar, status_label):
    def hook(d):
        if d["status"] == "downloading":
            try:
                percent = float(d.get("_percent_str", "0%").strip().replace("%", ""))
                progress_bar["value"] = percent
                status_label.config(text=f"Downloading... {int(percent)}%")
            except:
                pass
        elif d["status"] == "finished":
            status_label.config(text="Finalizing...")

    ydl_opts = {
        "outtmpl": f"{DOWNLOAD_DIR}/%(uploader)s_%(id)s.%(ext)s",
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "progress_hooks": [hook],
        "ffmpeg_location": BASE_DIR,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for link in links:
            link = link.strip()
            if link:
                ydl.download([link])

    status_label.config(text="Done")
    progress_bar["value"] = 100
    progress_window.after(800, progress_window.destroy)


def start_download():
    raw = text_box.get("1.0", tk.END)
    links = [l for l in raw.split("\n") if l.strip()]
    if not links:
        return

    win = tk.Toplevel(root)
    win.title("Downloading")
    win.geometry("400x120")

    tk.Label(win, text="Starting...").pack(pady=5)

    progress = ttk.Progressbar(win, length=300, mode="determinate", maximum=100)
    progress.pack(pady=10)

    status = tk.Label(win, text="Waiting...")
    status.pack()

    threading.Thread(
        target=download_links,
        args=(links, win, progress, status),
        daemon=True
    ).start()


root = tk.Tk()
root.title("Downloader")
root.geometry("600x400")

tk.Label(root, text="Paste links (one per line):").pack(pady=5)

text_box = scrolledtext.ScrolledText(root, width=70, height=15)
text_box.pack(padx=10, pady=10)

tk.Button(root, text="Download", command=start_download).pack(pady=10)

root.mainloop()
