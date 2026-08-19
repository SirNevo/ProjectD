import tkinter as tk
from tkinter import scrolledtext, ttk
import yt_dlp
import threading
import os
import sys
import queue
import glob


# =========================================================
# BASE DIRECTORY
# =========================================================

def base_dir():

    if getattr(sys, "frozen", False):
        return sys._MEIPASS

    return os.path.dirname(
        os.path.abspath(__file__)
    )


BASE_DIR = base_dir()


# =========================================================
# FFMPEG LOCATION
# =========================================================

if getattr(sys, "frozen", False):

    # PyInstaller EXE
    FFMPEG_LOCATION = BASE_DIR

elif os.name == "nt":

    # Windows Python script
    FFMPEG_LOCATION = os.path.join(
        BASE_DIR,
        "ffmpeg"
    )

else:

    # Linux
    FFMPEG_LOCATION = "/usr/bin"


# =========================================================
# DOWNLOAD DIRECTORY
# =========================================================

DOWNLOAD_DIR = os.path.expanduser(
    "~/Documents/Downloads"
)

os.makedirs(
    DOWNLOAD_DIR,
    exist_ok=True
)


# =========================================================
# GUI QUEUE
# =========================================================

gui_queue = queue.Queue()


# =========================================================
# DOWNLOAD STATE
# =========================================================

download_in_progress = False


# =========================================================
# YOUTUBE DETECTION
# =========================================================

def is_youtube_url(url):

    url = url.lower()

    return (
        "youtube.com/" in url
        or "youtu.be/" in url
        or "youtube-nocookie.com/" in url
    )


# =========================================================
# CLEAN FAILED PART FILES
# =========================================================

def cleanup_part_files():

    try:

        for path in glob.glob(
            os.path.join(
                DOWNLOAD_DIR,
                "*.part"
            )
        ):

            try:

                os.remove(path)

                print(
                    f"Removed failed part file: {path}"
                )

            except Exception as e:

                print(
                    f"Could not remove {path}: {e}"
                )

    except Exception as e:

        print(
            f"Part-file cleanup error: {e}"
        )


# =========================================================
# FORMAT SPEED
# =========================================================

def format_speed(speed):

    if not speed:
        return ""

    if speed >= 1024 * 1024:

        return (
            f"{speed / (1024 * 1024):.2f} MB/s"
        )

    if speed >= 1024:

        return (
            f"{speed / 1024:.1f} KB/s"
        )

    return (
        f"{speed:.0f} B/s"
    )


# =========================================================
# FORMAT ETA
# =========================================================

def format_eta(eta):

    if eta is None:
        return ""

    minutes, seconds = divmod(
        int(eta),
        60
    )

    if minutes:

        return (
            f"{minutes}m {seconds:02d}s"
        )

    return (
        f"{seconds}s"
    )


# =========================================================
# PROGRESS HOOK
# =========================================================

def create_progress_hook():

    def hook(d):

        status = d.get("status")


        # -------------------------------------------------
        # DOWNLOADING
        # -------------------------------------------------

        if status == "downloading":

            downloaded = d.get(
                "downloaded_bytes",
                0
            )

            total = d.get(
                "total_bytes"
            )

            if total is None:

                total = d.get(
                    "total_bytes_estimate"
                )


            if total:

                percent = (
                    downloaded / total
                ) * 100

                percent = max(
                    0,
                    min(
                        100,
                        percent
                    )
                )

            else:

                percent = 0


            speed = d.get(
                "speed"
            )

            eta = d.get(
                "eta"
            )


            gui_queue.put((
                "progress",
                percent,
                speed,
                eta
            ))


        # -------------------------------------------------
        # FILE FINISHED
        # -------------------------------------------------

        elif status == "finished":

            # Do NOT set progress to 100%.
            #
            # yt-dlp may still need to merge video/audio.
            # The worker sends the final success message
            # only after ydl.download() has completed.

            gui_queue.put((
                "finalizing"
            ))

    return hook


# =========================================================
# CREATE YT-DLP OPTIONS
# =========================================================

def create_ydl_options(
    fallback=False
):

    options = {

        # -------------------------------------------------
        # Output filename
        # -------------------------------------------------

        "outtmpl": (
            f"{DOWNLOAD_DIR}/"
            "%(title)s_%(id)s.%(ext)s"
        ),


        # -------------------------------------------------
        # BEST AVAILABLE
        # -------------------------------------------------
        #
        # This means:
        #
        #   best video + best audio
        #
        # or:
        #
        #   best combined format
        #
        # It does NOT force 360p.
        #

        "format": (
            "bv*+ba/b"
        ),


        # -------------------------------------------------
        # Merge into MP4 when possible
        # -------------------------------------------------

        "merge_output_format": "mp4",


        # -------------------------------------------------
        # Don't download playlists
        # -------------------------------------------------

        "noplaylist": True,


        # -------------------------------------------------
        # Progress hook
        # -------------------------------------------------

        "progress_hooks": [
            create_progress_hook()
        ],


        # -------------------------------------------------
        # FFmpeg
        # -------------------------------------------------

        "ffmpeg_location": FFMPEG_LOCATION,


        # -------------------------------------------------
        # Don't overwrite existing files
        # -------------------------------------------------

        "overwrites": False,


        # -------------------------------------------------
        # Resume partial downloads when possible
        #
        # Failed .part files are manually removed after
        # a failed attempt.
        # -------------------------------------------------

        "continuedl": True,


        # -------------------------------------------------
        # Console output
        # -------------------------------------------------

        "quiet": False,

        "no_warnings": False,
    }


    # =====================================================
    # YOUTUBE ANDROID FALLBACK
    # =====================================================

    if fallback:

        options["extractor_args"] = {

            "youtube": {

                "player_client": [
                    "android"
                ]

            }

        }


        # -------------------------------------------------
        # IMPORTANT:
        #
        # Still request the BEST Android format.
        #
        # We are NOT forcing format 18.
        #
        # If Android exposes 720p, yt-dlp will prefer it.
        # If Android only exposes 360p, then 360p is used.
        # -------------------------------------------------

        options["format"] = (
            "bv*+ba/b"
        )


    return options


# =========================================================
# CHECK WHETHER VIDEO IS ALREADY DOWNLOADED
# =========================================================

def check_existing_download(link):

    try:

        check_opts = {

            "quiet": True,

            "no_warnings": True,

            "skip_download": True,

            "noplaylist": True,

        }


        with yt_dlp.YoutubeDL(
            check_opts
        ) as ydl:

            info = ydl.extract_info(
                link,
                download=False
            )


            if not info:

                return False


            video_id = info.get(
                "id"
            )


            if not video_id:

                return False


            # -------------------------------------------------
            # First check using the exact filename yt-dlp
            # would normally generate.
            # -------------------------------------------------

            try:

                expected = ydl.prepare_filename(
                    info
                )

                if os.path.exists(
                    expected
                ):

                    return True


            except Exception:

                pass


            # -------------------------------------------------
            # Check common extensions.
            #
            # This also catches cases where yt-dlp merged
            # the final file into MP4.
            # -------------------------------------------------

            extensions = [
                "mp4",
                "mkv",
                "webm",
                "mov",
                "avi",
                "flv",
                "m4v"
            ]


            for extension in extensions:

                pattern = os.path.join(

                    DOWNLOAD_DIR,

                    f"*_{video_id}.{extension}"

                )


                matches = glob.glob(
                    pattern
                )


                for path in matches:

                    if not path.endswith(
                        ".part"
                    ):

                        return True


            return False


    except Exception as e:

        print(
            f"Existing-file check failed: {e}"
        )

        return False


# =========================================================
# DOWNLOAD ONE URL
# =========================================================

def download_one(
    link,
    fallback=False
):

    options = create_ydl_options(
        fallback=fallback
    )


    try:

        with yt_dlp.YoutubeDL(
            options
        ) as ydl:

            result = ydl.download([
                link
            ])


            return result == 0


    except Exception as e:

        print(
            f"Download exception: {e}"
        )

        return False


# =========================================================
# DOWNLOAD WORKER
# =========================================================

def download_links(links):

    global download_in_progress

    try:

        total_links = len(
            links
        )


        completed = 0

        already_downloaded = 0

        failed = 0


        # -------------------------------------------------
        # Process every URL
        # -------------------------------------------------

        for index, link in enumerate(
            links,
            start=1
        ):

            link = link.strip()


            if not link:
                continue


            # =================================================
            # CHECK EXISTING DOWNLOAD
            # =================================================

            gui_queue.put((
                "checking",
                index,
                total_links,
                link
            ))


            if check_existing_download(
                link
            ):

                already_downloaded += 1

                gui_queue.put((
                    "already_exists",
                    index,
                    total_links,
                    link
                ))

                continue


            # =================================================
            # DEFAULT METHOD
            # =================================================

            gui_queue.put((
                "starting",
                index,
                total_links
            ))


            success = download_one(
                link,
                fallback=False
            )


            # =================================================
            # DEFAULT METHOD FAILED
            # =================================================

            if not success:

                # ---------------------------------------------
                # Remove failed partial files before fallback.
                # ---------------------------------------------

                cleanup_part_files()


                # ---------------------------------------------
                # Only use Android fallback for YouTube.
                # ---------------------------------------------

                if is_youtube_url(
                    link
                ):

                    gui_queue.put((
                        "fallback",
                        link
                    ))


                    success = download_one(
                        link,
                        fallback=True
                    )


                    if not success:

                        cleanup_part_files()

                        failed += 1

                        gui_queue.put((
                            "failed",
                            link
                        ))

                        continue


                else:

                    failed += 1

                    gui_queue.put((
                        "failed",
                        link
                    ))

                    continue


            # =================================================
            # SUCCESS
            # =================================================

            completed += 1


            gui_queue.put((
                "success",
                link
            ))


        # =====================================================
        # ALL URLS PROCESSED
        # =====================================================

        gui_queue.put((
            "done",
            completed,
            already_downloaded,
            failed,
            total_links
        ))


    except Exception as e:

        print(
            f"Worker error: {e}"
        )

        gui_queue.put((
            "error",
            str(e)
        ))


    finally:

        download_in_progress = False


# =========================================================
# PROCESS GUI QUEUE
# =========================================================

def process_gui_queue():

    try:

        while True:

            message = gui_queue.get_nowait()

            message_type = message[0]


            # =================================================
            # CHECKING
            # =================================================

            if message_type == "checking":

                index = message[1]

                total = message[2]


                status_label.config(
                    text=(
                        f"Checking video "
                        f"{index}/{total}..."
                    )
                )


                progress_bar["value"] = 0


            # =================================================
            # STARTING
            # =================================================

            elif message_type == "starting":

                index = message[1]

                total = message[2]


                status_label.config(
                    text=(
                        f"Downloading "
                        f"{index}/{total}..."
                    )
                )


                progress_bar["value"] = 0


            # =================================================
            # DOWNLOADING
            # =================================================

            elif message_type == "progress":

                percent = message[1]

                speed = message[2]

                eta = message[3]


                progress_bar["value"] = percent


                text = (
                    f"Downloading... "
                    f"{percent:.1f}%"
                )


                speed_text = format_speed(
                    speed
                )


                eta_text = format_eta(
                    eta
                )


                if speed_text:

                    text += (
                        f"  •  {speed_text}"
                    )


                if eta_text:

                    text += (
                        f"  •  ETA {eta_text}"
                    )


                status_label.config(
                    text=text
                )


            # =================================================
            # FINALIZING
            # =================================================

            elif message_type == "finalizing":

                status_label.config(
                    text="Finalizing..."
                )


            # =================================================
            # FALLBACK
            # =================================================

            elif message_type == "fallback":

                progress_bar["value"] = 0


                status_label.config(
                    text=(
                        "Default method failed. "
                        "Trying fallback method..."
                    )
                )


            # =================================================
            # ALREADY EXISTS
            # =================================================

            elif message_type == "already_exists":

                progress_bar["value"] = 100


                status_label.config(
                    text=(
                        "Video is already downloaded"
                    )
                )


            # =================================================
            # SUCCESS
            # =================================================

            elif message_type == "success":

                progress_bar["value"] = 100


                status_label.config(
                    text="Download complete"
                )


            # =================================================
            # FAILED
            # =================================================

            elif message_type == "failed":

                progress_bar["value"] = 0


                status_label.config(
                    text="Download failed"
                )


            # =================================================
            # ERROR
            # =================================================

            elif message_type == "error":

                progress_bar["value"] = 0


                status_label.config(
                    text="Unexpected error"
                )


                print(
                    message[1]
                )


            # =================================================
            # DONE
            # =================================================

            elif message_type == "done":

                completed = message[1]

                already_downloaded = message[2]

                failed = message[3]

                total = message[4]


                # -------------------------------------------------
                # IMPORTANT:
                #
                # Don't overwrite the "already downloaded"
                # message with "Download complete" when there
                # was only one URL.
                # -------------------------------------------------

                if total == 1:

                    if already_downloaded == 1:

                        progress_bar["value"] = 100

                        status_label.config(
                            text=(
                                "Video is already downloaded"
                            )
                        )


                    elif completed == 1:

                        progress_bar["value"] = 100

                        status_label.config(
                            text=(
                                "Download complete"
                            )
                        )


                    else:

                        progress_bar["value"] = 0

                        status_label.config(
                            text=(
                                "Download failed"
                            )
                        )


                # -------------------------------------------------
                # Multiple URLs
                # -------------------------------------------------

                else:

                    progress_bar["value"] = 100


                    if failed == 0:

                        if already_downloaded > 0:

                            status_label.config(
                                text=(
                                    f"Finished: "
                                    f"{completed} downloaded, "
                                    f"{already_downloaded} "
                                    f"already downloaded"
                                )
                            )

                        else:

                            status_label.config(
                                text=(
                                    f"All {total} "
                                    f"downloads finished"
                                )
                            )


                    else:

                        status_label.config(
                            text=(
                                f"Finished: "
                                f"{completed} downloaded, "
                                f"{already_downloaded} "
                                f"already downloaded, "
                                f"{failed} failed"
                            )
                        )


                # -------------------------------------------------
                # Close progress window after 1.5 seconds.
                # -------------------------------------------------

                progress_window.after(
                    1500,
                    progress_window.destroy
                )


    except queue.Empty:

        pass


    # ---------------------------------------------------------
    # Keep processing GUI messages.
    # ---------------------------------------------------------

    root.after(
        100,
        process_gui_queue
    )


# =========================================================
# START DOWNLOAD
# =========================================================

def start_download():

    global download_in_progress

    global progress_window

    global progress_bar

    global status_label


    # ---------------------------------------------------------
    # Prevent multiple simultaneous download jobs.
    # ---------------------------------------------------------

    if download_in_progress:

        return


    raw = text_box.get(
        "1.0",
        tk.END
    )


    links = [

        line.strip()

        for line in raw.splitlines()

        if line.strip()

    ]


    if not links:

        return


    download_in_progress = True


    # =========================================================
    # PROGRESS WINDOW
    # =========================================================

    progress_window = tk.Toplevel(
        root
    )


    progress_window.title(
        "Downloading"
    )


    progress_window.geometry(
        "520x150"
    )


    progress_window.resizable(
        False,
        False
    )


    # =========================================================
    # STATUS LABEL
    # =========================================================

    status_label = tk.Label(

        progress_window,

        text="Starting...",

        anchor="w"

    )


    status_label.pack(

        fill="x",

        padx=15,

        pady=(12, 5)

    )


    # =========================================================
    # PROGRESS BAR
    # =========================================================

    progress_bar = ttk.Progressbar(

        progress_window,

        length=480,

        mode="determinate",

        maximum=100

    )


    progress_bar.pack(

        padx=15,

        pady=10

    )


    # =========================================================
    # START BACKGROUND WORKER
    # =========================================================

    threading.Thread(

        target=download_links,

        args=(links,),

        daemon=True

    ).start()


# =========================================================
# MAIN WINDOW
# =========================================================

root = tk.Tk()


root.title(
    "Downloader"
)


root.geometry(
    "600x400"
)


# =========================================================
# LABEL
# =========================================================

tk.Label(

    root,

    text="Paste links (one per line):"

).pack(

    pady=5

)


# =========================================================
# URL TEXTBOX
# =========================================================

text_box = scrolledtext.ScrolledText(

    root,

    width=70,

    height=15

)


text_box.pack(

    padx=10,

    pady=10

)


# =========================================================
# DOWNLOAD BUTTON
# =========================================================

tk.Button(

    root,

    text="Download",

    command=start_download

).pack(

    pady=10

)


# =========================================================
# START GUI QUEUE PROCESSING
# =========================================================

root.after(

    100,

    process_gui_queue

)


# =========================================================
# START APPLICATION
# =========================================================

root.mainloop()
