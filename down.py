import tkinter as tk
from tkinter import scrolledtext, ttk
import yt_dlp
import threading
import os
import sys


# --- portable path handling ---
if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(__file__)

FFMPEG_PATH = os.path.join(BASE_DIR, "ffmpeg.exe")


DOWNLOAD_DIR = os.path.expanduser("~/Documents/Downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


# ---------------- download logic ----------------
def download_links(links, progress_window, progress_bar, status_label):

    def safe_ui_update(fn):
        progress_window.after(0, fn)

    def hook(d):
        if d["status"] == "downloading":
            downloaded = d.get("downloaded_bytes", 0)
            total = d.get("total_bytes") or d.get("total_bytes_estimate")

            if total:
                percent = downloaded / total * 100

                safe_ui_update(lambda: (
                    progress_bar.config(value=percent),
                    status_label.config(text=f"Downloading... {percent:.1f}%")
                ))

        elif d["status"] == "finished":
            safe_ui_update(lambda: status_label.config(text="Finalizing..."))

    ydl_opts = {
        "outtmpl": f"{DOWNLOAD_DIR}/%(uploader)s_%(id)s.%(ext)s",
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "progress_hooks": [hook],

        # correct ffmpeg handling
        "ffmpeg_location": BASE_DIR if os.path.exists(FFMPEG_PATH) else None,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for link in links:
            link = link.strip()
            if link:
                ydl.download([link])

    safe_ui_update(lambda: (
        status_label.config(text="Done"),
        progress_bar.config(value=100)
    ))

    progress_window.after(800, progress_window.destroy)


# ---------------- UI ----------------
def start_download():
    raw = text_box.get("1.0", tk.END)
    links = [l for l in raw.split("\n") if l.strip()]

    if not links:
        return

    win = tk.Toplevel(root)
    win.title("Downloading...")
    win.geometry("400x120")

    tk.Label(win, text="Starting download...").pack(pady=5)

    progress = ttk.Progressbar(win, length=300, mode="determinate")
    progress.pack(pady=10)
    progress["maximum"] = 100

    status = tk.Label(win, text="Waiting...")
    status.pack()

    thread = threading.Thread(
        target=download_links,
        args=(links, win, progress, status),
        daemon=True
    )
    thread.start()


# ---------------- main window ----------------
root = tk.Tk()
root.title("Video Downloader (stable edition)")
root.geometry("600x400")

tk.Label(root, text="Paste YT/Twitter/X links (one per line):").pack(pady=5)

text_box = scrolledtext.ScrolledText(root, width=70, height=15)
text_box.pack(padx=10, pady=10)

tk.Button(root, text="Download", command=start_download).pack(pady=10)

root.mainloop()
