import numpy as np
import sounddevice as sd
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import filedialog, messagebox
import scipy.io.wavfile as wav
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import sys
import os
import time

# --- CONFIGURATION MOTEUR ---
SAMPLE_RATE = 44100
FFT_SIZE = 2048


class PixonicGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("PIXONIC STUDIO - FFT ENGINE")
        self.root.geometry("1150x850")
        self.root.configure(bg="#121212")

        self.image_path = None
        self.audio_data = None
        self.img_preview = None
        self.is_playing = False
        self.playhead_line = None

        self.setup_ui()

    def setup_ui(self):
        self.colors = {
            "bg": "#1e1e1e", "bg_dark": "#121212", "accent": "#00ffcc",
            "text": "#ffffff", "btn_default": "#333333", "btn_play": "#27ae60",
            "btn_stop": "#c0392b", "btn_save": "#2980b9", "status_fg": "#aaaaaa"
        }

        # --- PANNEAU DE CONTRÔLE ---
        self.control_frame = tk.Frame(self.root, width=280, bg=self.colors["bg"], padx=20, pady=20)
        self.control_frame.pack(side=tk.LEFT, fill=tk.Y)
        self.control_frame.pack_propagate(False)

        tk.Label(self.control_frame, text="PIXONIC", font=("Segoe UI", 24, "bold"), bg=self.colors["bg"],
                 fg=self.colors["accent"]).pack(pady=(10, 20))

        btn_style = {"relief": tk.FLAT, "font": ("Segoe UI", 10, "bold"), "fg": "white", "height": 2, "cursor": "hand2"}

        # SECTION CHARGEMENT & VITESSE
        tk.Button(self.control_frame, text="📁 LOAD IMAGE", command=self.load_image, bg=self.colors["btn_default"],
                  **btn_style).pack(fill=tk.X, pady=5)

        tk.Label(self.control_frame, text="VITESSE (SEC/PIXEL)", font=("Segoe UI", 8), bg=self.colors["bg"],
                 fg=self.colors["status_fg"]).pack(pady=(15, 0))
        self.speed_slider = tk.Scale(self.control_frame, from_=0.001, to=0.1, resolution=0.001, orient=tk.HORIZONTAL,
                                     bg=self.colors["bg"], fg=self.colors["text"], highlightthickness=0)
        self.speed_slider.set(0.005)
        self.speed_slider.pack(fill=tk.X, pady=5)

        # SECTION TRANSPORT
        self.play_btn = tk.Button(self.control_frame, text="▶ PLAY / REFRESH", command=self.play_audio,
                                  state=tk.DISABLED, bg=self.colors["btn_play"], **btn_style)
        self.play_btn.pack(fill=tk.X, pady=(25, 5))

        self.stop_btn = tk.Button(self.control_frame, text="⏹ STOP", command=self.stop_audio, state=tk.DISABLED,
                                  bg=self.colors["btn_stop"], **btn_style)
        self.stop_btn.pack(fill=tk.X, pady=5)

        self.save_btn = tk.Button(self.control_frame, text="💾 SAVE WAV", command=self.save_wav, state=tk.DISABLED,
                                  bg=self.colors["btn_save"], **btn_style)
        self.save_btn.pack(fill=tk.X, pady=5)

        # --- SECTION BASSE (VOLUME + STATUS) ---
        # On utilise side=BOTTOM pour empiler depuis le bas
        self.status_var = tk.StringVar(value="Prêt")
        self.status_bar = tk.Label(self.control_frame, textvariable=self.status_var, bg=self.colors["bg"],
                                   fg=self.colors["accent"], font=("Segoe UI", 8, "italic"), wraplength=240,
                                   justify="left")
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X, pady=(5, 10))

        tk.Label(self.control_frame, text="VOLUME (%)", font=("Segoe UI", 8, "bold"), bg=self.colors["bg"],
                 fg=self.colors["text"]).pack(side=tk.BOTTOM, fill=tk.X, pady=(15, 0))
        self.volume_slider = tk.Scale(self.control_frame, from_=0, to=100, orient=tk.HORIZONTAL, bg=self.colors["bg"],
                                      fg=self.colors["text"], highlightthickness=0, troughcolor="#333")
        self.volume_slider.set(80)
        self.volume_slider.pack(side=tk.BOTTOM, fill=tk.X, pady=5)

        # --- ZONE DE VISUALISATION (DROITE) ---
        self.viz_frame = tk.Frame(self.root, bg=self.colors["bg_dark"])
        self.viz_frame.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH)

        self.img_label = tk.Label(self.viz_frame, text="Attente d'image PNG...", bg=self.colors["bg_dark"],
                                  fg="#444444", font=("Segoe UI", 12))
        self.img_label.pack(pady=20)

        self.fig, self.ax = plt.subplots(figsize=(5.5, 5.5), facecolor=self.colors["bg_dark"])
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.viz_frame)
        self.canvas.get_tk_widget().pack(padx=20, pady=10)
        self.ax.axis('off')

    def set_status(self, message):
        self.status_var.set(message)
        self.root.after(5000, lambda: self.status_var.set("Prêt"))

    def load_image(self):
        path = filedialog.askopenfilename(filetypes=[("Images PNG", "*.png")])
        if path:
            self.image_path = path
            img = Image.open(path).resize((300, 300))
            self.img_preview = ImageTk.PhotoImage(img)
            self.img_label.config(image=self.img_preview, text="")
            self.play_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.NORMAL)
            self.set_status(f"Image chargée : {os.path.basename(path)}")
            self.generate_fft()

    def generate_fft(self):
        if not self.image_path: return
        img = Image.open(self.image_path).convert('RGB').resize((512, 512))
        data = np.array(img, dtype=float)
        self.current_duration = self.speed_slider.get()
        samples_per_col = int(SAMPLE_RATE * self.current_duration)
        self.audio_data = np.zeros((512 * samples_per_col, 2))
        window = np.hanning(samples_per_col)

        for x in range(512):
            col = data[:, x]
            spec_l, spec_r = np.zeros(FFT_SIZE // 2 + 1, dtype=complex), np.zeros(FFT_SIZE // 2 + 1, dtype=complex)
            for y in range(512):
                r, g, b = col[y]
                if r == 0 and g == 0 and b == 0: continue
                idx = int(((512 - y) / 512) * (FFT_SIZE // 2))
                phase = np.random.uniform(0, 2 * np.pi)
                spec_l[idx] += ((r + g) / 510.0) * np.exp(1j * phase)
                spec_r[idx] += ((b + g) / 510.0) * np.exp(1j * phase)
            self.audio_data[x * samples_per_col:(x + 1) * samples_per_col, 0] = np.fft.irfft(spec_l,
                                                                                             n=samples_per_col) * window
            self.audio_data[x * samples_per_col:(x + 1) * samples_per_col, 1] = np.fft.irfft(spec_r,
                                                                                             n=samples_per_col) * window

        self.audio_data /= (np.max(np.abs(self.audio_data)) + 1e-6)
        self.update_spectrogram()
        self.save_btn.config(state=tk.NORMAL)

    def update_spectrogram(self):
        self.ax.clear()
        self.ax.specgram(self.audio_data[:, 0], Fs=SAMPLE_RATE, cmap='magma', NFFT=256)
        self.ax.axis('off')
        self.ax.set_aspect('auto')
        self.fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
        self.playhead_line = self.ax.axvline(x=0, color='red', linewidth=2, alpha=0)
        self.canvas.draw()

    def update_playhead(self, start_time, total_duration):
        if not self.is_playing: return
        elapsed = time.time() - start_time
        if elapsed < total_duration:
            self.playhead_line.set_xdata([elapsed])
            self.playhead_line.set_alpha(1.0)
            self.canvas.draw_idle()
            self.root.after(30, lambda: self.update_playhead(start_time, total_duration))
        else:
            self.playhead_line.set_alpha(0)
            self.canvas.draw_idle()
            self.is_playing = False

    def play_audio(self):
        if self.image_path:
            self.stop_audio()
            self.generate_fft()
            vol = self.volume_slider.get() / 100.0
            self.is_playing = True
            sd.play(self.audio_data * vol, SAMPLE_RATE)
            total_duration = len(self.audio_data) / SAMPLE_RATE
            self.update_playhead(time.time(), total_duration)
            self.set_status(f"Lecture : {total_duration:.2f}s")

    def stop_audio(self):
        sd.stop()
        self.is_playing = False
        if self.playhead_line:
            self.playhead_line.set_alpha(0)
            self.canvas.draw_idle()
        self.set_status("Arrêt.")

    def save_wav(self):
        if self.audio_data is not None:
            path = filedialog.asksaveasfilename(defaultextension=".wav", filetypes=[("WAV file", "*.wav")])
            if path:
                try:
                    vol = self.volume_slider.get() / 100.0
                    wav.write(path, SAMPLE_RATE, (self.audio_data * vol).astype(np.float32))
                    self.set_status(f"✨ Sauvegardé : {os.path.basename(path)}")
                except Exception as e:
                    messagebox.showerror("Erreur", f"Erreur : {e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = PixonicGUI(root)
    root.mainloop()