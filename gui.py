import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk, Spinbox
import tempfile
import random

from preview import preview_file
from renderer import render_project
from utils import download_url

class FreePoopApp:
    def __init__(self, root: tk.Tk):
        self.root = root

        # initialize state BEFORE building the UI so widgets can reference these variables
        # internal categorized sources
        self.videos = []       # video files
        self.overlays = []     # overlay images / video
        self.audios = []       # music / long audio
        self.sounds = []       # short sounds / effects
        self.gifs = []         # gifs

        # other state
        self.registered_urls = []
        self.clip_count = tk.IntVar(value=6)

        # now build the UI
        self.build_ui()

    def build_ui(self):
        self.root.title("FreePoop Light — Super Deluxe")
        frm = tk.Frame(self.root)
        frm.pack(fill="both", expand=True, padx=6, pady=6)

        # Left: material sources (tabs)
        material_frame = tk.LabelFrame(frm, text="Material Sources")
        material_frame.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

        tabs = ttk.Notebook(material_frame)
        tabs.pack(fill="both", expand=True)

        # Helper factory to create a tab with listbox and buttons
        def make_tab(name, add_callback, remove_callback, preview_callback):
            frame = tk.Frame(tabs)
            lst = tk.Listbox(frame, width=60, height=8)
            lst.pack(side="left", fill="both", expand=True)
            btns = tk.Frame(frame)
            btns.pack(side="right", fill="y", padx=4)
            tk.Button(btns, text=f"Add {name}...", command=add_callback).pack(fill="x", pady=2)
            tk.Button(btns, text="Remove", command=remove_callback).pack(fill="x", pady=2)
            tk.Button(btns, text="Preview", command=preview_callback).pack(fill="x", pady=2)
            return frame, lst

        # Video tab
        def add_videos():
            paths = filedialog.askopenfilenames(title="Add video files", filetypes=[("Video", "*.mp4 *.mkv *.mov *.avi *.webm"), ("All","*.*")])
            if not paths:
                return
            for p in paths:
                if p not in self.videos:
                    self.videos.append(p)
                    lb_videos.insert("end", p)

        def remove_videos():
            sel = list(lb_videos.curselection())
            for i in reversed(sel):
                lb_videos.delete(i)
                del self.videos[i]

        def preview_video():
            sel = lb_videos.curselection()
            if not sel:
                messagebox.showinfo("Preview", "Select a video to preview.")
                return
            path = self.videos[sel[0]]
            threading.Thread(target=lambda: preview_file(path, duration=6), daemon=True).start()

        vtab, lb_videos = make_tab("Video", add_videos, remove_videos, preview_video)
        tabs.add(vtab, text="Video")

        # Overlays tab
        def add_overlays():
            paths = filedialog.askopenfilenames(title="Add overlay images/videos", filetypes=[("Images/Videos","*.png *.jpg *.mp4 *.webm"), ("All","*.*")])
            if not paths:
                return
            for p in paths:
                if p not in self.overlays:
                    self.overlays.append(p)
                    lb_overlays.insert("end", p)

        def remove_overlays():
            sel = list(lb_overlays.curselection())
            for i in reversed(sel):
                lb_overlays.delete(i)
                del self.overlays[i]

        def preview_overlay():
            sel = lb_overlays.curselection()
            if not sel:
                messagebox.showinfo("Preview", "Select an overlay to preview.")
                return
            path = self.overlays[sel[0]]
            threading.Thread(target=lambda: preview_file(path, duration=4), daemon=True).start()

        otab, lb_overlays = make_tab("Overlay", add_overlays, remove_overlays, preview_overlay)
        tabs.add(otab, text="Overlays")

        # Audio (music) tab
        def add_audios():
            paths = filedialog.askopenfilenames(title="Add audio/music files", filetypes=[("Audio","*.mp3 *.wav *.aac *.m4a *.ogg"), ("All","*.*")])
            if not paths:
                return
            for p in paths:
                if p not in self.audios:
                    self.audios.append(p)
                    lb_audios.insert("end", p)

        def remove_audios():
            sel = list(lb_audios.curselection())
            for i in reversed(sel):
                lb_audios.delete(i)
                del self.audios[i]

        def preview_audio():
            sel = lb_audios.curselection()
            if not sel:
                messagebox.showinfo("Preview", "Select an audio file to preview.")
                return
            path = self.audios[sel[0]]
            threading.Thread(target=lambda: preview_file(path, duration=6), daemon=True).start()

        atab, lb_audios = make_tab("Audio", add_audios, remove_audios, preview_audio)
        tabs.add(atab, text="Audio/Music")

        # Sounds tab (short fx)
        def add_sounds():
            paths = filedialog.askopenfilenames(title="Add sound effect files", filetypes=[("Audio","*.wav *.mp3 *.ogg"), ("All","*.*")])
            if not paths:
                return
            for p in paths:
                if p not in self.sounds:
                    self.sounds.append(p)
                    lb_sounds.insert("end", p)

        def remove_sounds():
            sel = list(lb_sounds.curselection())
            for i in reversed(sel):
                lb_sounds.delete(i)
                del self.sounds[i]

        def preview_sound():
            sel = lb_sounds.curselection()
            if not sel:
                messagebox.showinfo("Preview", "Select a sound to preview.")
                return
            path = self.sounds[sel[0]]
            threading.Thread(target=lambda: preview_file(path, duration=4), daemon=True).start()

        stab, lb_sounds = make_tab("Sound", add_sounds, remove_sounds, preview_sound)
        tabs.add(stab, text="Sounds/FX")

        # GIF tab
        def add_gifs():
            paths = filedialog.askopenfilenames(title="Add gif files", filetypes=[("GIF","*.gif"), ("All","*.*")])
            if not paths:
                return
            for p in paths:
                if p not in self.gifs:
                    self.gifs.append(p)
                    lb_gifs.insert("end", p)

        def remove_gifs():
            sel = list(lb_gifs.curselection())
            for i in reversed(sel):
                lb_gifs.delete(i)
                del self.gifs[i]

        def preview_gif():
            sel = lb_gifs.curselection()
            if not sel:
                messagebox.showinfo("Preview", "Select a gif to preview.")
                return
            path = self.gifs[sel[0]]
            threading.Thread(target=lambda: preview_file(path, duration=6), daemon=True).start()

        gtab, lb_gifs = make_tab("GIF", add_gifs, remove_gifs, preview_gif)
        tabs.add(gtab, text="GIFs")

        # Right: project / registered URLs / timeline options
        right = tk.LabelFrame(frm, text="Project / Timeline")
        right.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)

        # Registered URLs list
        tk.Label(right, text="Registered URLs (will be downloaded at render):").pack(anchor="w")
        self.lst_urls = tk.Listbox(right, width=60, height=6)
        self.lst_urls.pack(fill="both", expand=False)
        url_btns = tk.Frame(right)
        url_btns.pack(fill="x")
        tk.Button(url_btns, text="Add URL...", command=self.add_url).pack(side="left", padx=2, pady=2)
        tk.Button(url_btns, text="Remove", command=self.remove_url).pack(side="left", padx=2, pady=2)
        tk.Button(url_btns, text="Download & Preview", command=self.preview_url).pack(side="left", padx=2, pady=2)

        # Clip count
        cc_frame = tk.Frame(right)
        cc_frame.pack(fill="x", pady=6)
        tk.Label(cc_frame, text="Clip count (how many clips to use in render):").pack(side="left")
        self.spin_clip_count = Spinbox(cc_frame, from_=1, to=50, width=5, textvariable=self.clip_count)
        self.spin_clip_count.pack(side="left", padx=6)

        # Effects section
        effects = tk.LabelFrame(right, text="Effects / Randomization")
        effects.pack(fill="both", expand=False, pady=4)

        # Audio effects toggles
        self.var_stutter = tk.BooleanVar()
        self.var_reverse = tk.BooleanVar()
        self.var_scramble = tk.BooleanVar()
        self.var_earrape = tk.BooleanVar()
        self.var_overlay = tk.BooleanVar()
        tk.Checkbutton(effects, text="Stutter", variable=self.var_stutter).grid(row=0, column=0, sticky="w")
        tk.Checkbutton(effects, text="Reverse (clip-level)", variable=self.var_reverse).grid(row=0, column=1, sticky="w")
        tk.Checkbutton(effects, text="Scramble (shuffle)", variable=self.var_scramble).grid(row=0, column=2, sticky="w")
        tk.Checkbutton(effects, text="Ear-rape (loud)", variable=self.var_earrape).grid(row=0, column=3, sticky="w")
        tk.Checkbutton(effects, text="Overlay tint", variable=self.var_overlay).grid(row=0, column=4, sticky="w")

        # Advanced audio transforms
        tk.Label(effects, text="Pitch shift (semitones):").grid(row=1, column=0, sticky="e")
        self.pitch_semitones = tk.IntVar(value=0)
        self.spin_pitch = Spinbox(effects, from_=-12, to=12, width=5, textvariable=self.pitch_semitones)
        self.spin_pitch.grid(row=1, column=1, sticky="w")
        self.var_pitch_preserve = tk.BooleanVar(value=True)
        tk.Checkbutton(effects, text="Preserve speed (No Speed)", variable=self.var_pitch_preserve).grid(row=1, column=2, columnspan=2, sticky="w")

        # Prebuilt effect buttons
        btns = tk.Frame(right)
        btns.pack(fill="x", pady=6)
        tk.Button(btns, text="Render...", command=self.render_clicked).pack(side="left", padx=4)
        tk.Button(btns, text="Add Random Sounds to Timeline", command=self.add_random_sounds).pack(side="left", padx=4)

        self.lbl_status = tk.Label(right, text="Idle", anchor="w")
        self.lbl_status.pack(fill="x", pady=4)

        # Layout stretch
        frm.grid_columnconfigure(0, weight=1)
        frm.grid_columnconfigure(1, weight=1)
        frm.grid_rowconfigure(0, weight=1)

    def set_status(self, text: str):
        self.lbl_status.config(text=text)
        self.root.update_idletasks()

    def add_url(self):
        url = simpledialog.askstring("Add URL", "Enter a direct URL or YouTube/Archive URL:")
        if url:
            self.registered_urls.append(url)
            self.lst_urls.insert("end", url)

    def remove_url(self):
        sel = list(self.lst_urls.curselection())
        for i in reversed(sel):
            self.lst_urls.delete(i)
            del self.registered_urls[i]

    def preview_url(self):
        sel = self.lst_urls.curselection()
        if not sel:
            messagebox.showinfo("Preview", "Select a URL to preview.")
            return
        url = self.registered_urls[sel[0]]
        threading.Thread(target=self._download_and_preview, args=(url,), daemon=True).start()

    def _download_and_preview(self, url):
        tmpdir = tempfile.mkdtemp(prefix="freepoop_preview_")
        try:
            self.set_status("Downloading preview...")
            path = download_url(url, dest_dir=tmpdir)
            self.set_status("Previewing downloaded file...")
            preview_file(path, duration=6)
        except Exception as e:
            messagebox.showerror("Download error", f"Failed to download URL:\n{e}")
        finally:
            self.set_status("Idle")

    def add_random_sounds(self):
        if not self.sounds:
            messagebox.showinfo("Random sounds", "No sound materials available. Add sounds first.")
            return
        # Add 1..4 random sounds into registered URLs list for inclusion in render
        count = random.randint(1, min(4, len(self.sounds)))
        chosen = random.sample(self.sounds, count)
        for s in chosen:
            # We cheat: put local sound paths into registered_urls so renderer treats them as additional sources
            self.registered_urls.append(s)
            self.lst_urls.insert("end", s)
        self.set_status(f"Added {len(chosen)} random sounds to timeline.")

    def render_clicked(self):
        total_materials = len(self.videos) + len(self.gifs) + len(self.registered_urls)
        if total_materials == 0:
            messagebox.showinfo("Render", "Add some materials (video/gifs/urls) before rendering.")
            return
        out_path = filedialog.asksaveasfilename(defaultextension=".mp4", filetypes=[("MP4 video","*.mp4"), ("MKV","*.mkv"), ("All files","*.*")])
        if not out_path:
            return

        cfg = {
            "videos": list(self.videos),
            "overlays": list(self.overlays),
            "audios": list(self.audios),
            "sounds": list(self.sounds),
            "gifs": list(self.gifs),
            "urls": list(self.registered_urls),
            "clip_count": int(self.clip_count.get()),
            "stutter": bool(self.var_stutter.get()),
            "reverse": bool(self.var_reverse.get()),
            "scramble": bool(self.var_scramble.get()),
            "earrape": bool(self.var_earrape.get()),
            "overlay": bool(self.var_overlay.get()),
            "pitch_semitones": int(self.pitch_semitones.get()),
            "pitch_preserve": bool(self.var_pitch_preserve.get()),
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