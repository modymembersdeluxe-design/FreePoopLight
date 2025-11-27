import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import tempfile

from preview import preview_file
from renderer import render_project
from utils import download_url

class FreePoopApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.build_ui()

        # internal state
        self.local_sources = []  # local file paths
        self.url_sources = []    # registered URLs

    def build_ui(self):
        frm = tk.Frame(self.root)
        frm.pack(fill="both", expand=True, padx=8, pady=8)

        # Local sources
        left = tk.LabelFrame(frm, text="Local Sources")
        left.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self.lst_local = tk.Listbox(left, width=50, height=10)
        self.lst_local.pack(side="left", fill="both", expand=True)
        left_btns = tk.Frame(left)
        left_btns.pack(side="right", fill="y", padx=4)
        tk.Button(left_btns, text="Add files...", command=self.add_local_files).pack(fill="x", pady=2)
        tk.Button(left_btns, text="Remove", command=self.remove_local_selected).pack(fill="x", pady=2)
        tk.Button(left_btns, text="Preview", command=self.preview_local_selected).pack(fill="x", pady=2)

        # URL sources
        right = tk.LabelFrame(frm, text="Registered URLs")
        right.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)
        self.lst_urls = tk.Listbox(right, width=50, height=10)
        self.lst_urls.pack(side="left", fill="both", expand=True)
        right_btns = tk.Frame(right)
        right_btns.pack(side="right", fill="y", padx=4)
        tk.Button(right_btns, text="Add URL...", command=self.add_url).pack(fill="x", pady=2)
        tk.Button(right_btns, text="Remove", command=self.remove_urls_selected).pack(fill="x", pady=2)
        tk.Button(right_btns, text="Preview (downloaded)", command=self.preview_url_selected).pack(fill="x", pady=2)

        # Effects / actions
        opts = tk.LabelFrame(frm, text="Effects / Export")
        opts.grid(row=1, column=0, columnspan=2, sticky="ew", padx=4, pady=4)
        self.var_stutter = tk.BooleanVar()
        self.var_reverse = tk.BooleanVar()
        self.var_scramble = tk.BooleanVar()
        self.var_earrape = tk.BooleanVar()
        self.var_overlay = tk.BooleanVar()
        tk.Checkbutton(opts, text="Stutter", variable=self.var_stutter).grid(row=0, column=0, sticky="w")
        tk.Checkbutton(opts, text="Reverse", variable=self.var_reverse).grid(row=0, column=1, sticky="w")
        tk.Checkbutton(opts, text="Scramble", variable=self.var_scramble).grid(row=0, column=2, sticky="w")
        tk.Checkbutton(opts, text="Ear-rape (loud)", variable=self.var_earrape).grid(row=0, column=3, sticky="w")
        tk.Checkbutton(opts, text="Overlay tint", variable=self.var_overlay).grid(row=0, column=4, sticky="w")

        tk.Button(opts, text="Render...", command=self.render_clicked).grid(row=1, column=0, columnspan=2, pady=6)
        self.lbl_status = tk.Label(opts, text="Idle", anchor="w")
        self.lbl_status.grid(row=1, column=2, columnspan=3, sticky="ew")

        # configure grid stretch
        frm.grid_columnconfigure(0, weight=1)
        frm.grid_columnconfigure(1, weight=1)
        frm.grid_rowconfigure(0, weight=1)

    def set_status(self, text: str):
        self.lbl_status.config(text=text)
        self.root.update_idletasks()

    def add_local_files(self):
        paths = filedialog.askopenfilenames(title="Select media files")
        if not paths:
            return
        for p in paths:
            if p not in self.local_sources:
                self.local_sources.append(p)
                self.lst_local.insert("end", p)

    def remove_local_selected(self):
        sel = list(self.lst_local.curselection())
        for i in reversed(sel):
            self.lst_local.delete(i)
            del self.local_sources[i]

    def add_url(self):
        url = simpledialog.askstring("Add URL", "Enter a direct URL or YouTube/Archive URL:")
        if url:
            self.url_sources.append(url)
            self.lst_urls.insert("end", url)

    def remove_urls_selected(self):
        sel = list(self.lst_urls.curselection())
        for i in reversed(sel):
            self.lst_urls.delete(i)
            del self.url_sources[i]

    def preview_local_selected(self):
        sel = self.lst_local.curselection()
        if not sel:
            messagebox.showinfo("Preview", "Select a local file to preview.")
            return
        path = self.local_sources[sel[0]]
        threading.Thread(target=self._run_preview, args=(path,), daemon=True).start()

    def preview_url_selected(self):
        sel = self.lst_urls.curselection()
        if not sel:
            messagebox.showinfo("Preview", "Select a URL to preview.")
            return
        url = self.url_sources[sel[0]]
        threading.Thread(target=self._download_and_preview, args=(url,), daemon=True).start()

    def _run_preview(self, path):
        try:
            self.set_status(f"Previewing: {os.path.basename(path)}")
            preview_file(path, duration=6)
        except Exception as e:
            messagebox.showerror("Preview error", f"Preview failed:\n{e}")
        finally:
            self.set_status("Idle")

    def _download_and_preview(self, url):
        tmpdir = tempfile.mkdtemp(prefix="freepoop_preview_")
        try:
            self.set_status("Downloading preview...")
            path = download_url(url, dest_dir=tmpdir)
            self._run_preview(path)
        except Exception as e:
            messagebox.showerror("Download error", f"Failed to download URL:\n{e}")
            self.set_status("Idle")
        # do not remove tmpdir immediately; downloaded file is temporary and removed on next reboot or manual cleaning

    def render_clicked(self):
        if not self.local_sources and not self.url_sources:
            messagebox.showinfo("Render", "Add some sources (local or URLs) before rendering.")
            return
        out_path = filedialog.asksaveasfilename(defaultextension=".mp4", filetypes=[("MP4 video","*.mp4"), ("MKV","*.mkv"), ("All files","*.*")])
        if not out_path:
            return
        cfg = {
            "local_sources": list(self.local_sources),
            "url_sources": list(self.url_sources),
            "stutter": bool(self.var_stutter.get()),
            "reverse": bool(self.var_reverse.get()),
            "scramble": bool(self.var_scramble.get()),
            "earrape": bool(self.var_earrape.get()),
            "overlay": bool(self.var_overlay.get()),
        }
        threading.Thread(target=self._render_background, args=(cfg, out_path), daemon=True).start()

    def _render_background(self, cfg, out_path):
        try:
            self.set_status("Rendering...")
            def progress(msg):
                self.set_status(msg)
            render_project(cfg, out_path, progress_callback=progress)
            messagebox.showinfo("Render complete", f"Render finished: {out_path}")
        except Exception as e:
            messagebox.showerror("Render failed", f"Render failed:\n{e}")
        finally:
            self.set_status("Idle")