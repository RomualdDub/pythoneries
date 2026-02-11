import sys, numpy as np, sounddevice as sd, rtmidi, json, os, random, queue, threading, time, gc
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QWidget,
                             QLabel, QPushButton, QComboBox, QHBoxLayout)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QColor, QPen

# --- CONFIG HARDWARE ---
CONFIG_FILE = "config_hardware.json"
CRYSTAL_EMOJIS = ["💎", "✨", "🔮", "💠", "⚡", "🛸", "⚛️", "🔱", "🌌", "🧬", "🌈", "🔥"]


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {"midi_name": "", "audio_name": ""}


def save_config(midi_name, audio_name):
    with open(CONFIG_FILE, "w") as f:
        json.dump({"midi_name": midi_name, "audio_name": audio_name}, f)


class AudioEngine:
    def __init__(self):
        self.fs = 44100
        self.active_notes = {}
        self.params = {
            "type_A": "SINE", "type_B": "SAW", "ratio_B": 1.0, "mix": 0.5,
            "bright": 0.5, "att": 0.005, "rel": 0.1, "d_fb": 0.4, "d_time": 0.2
        }
        self.lock = threading.Lock()
        self.is_booting = False
        self.visual_buffer = np.zeros(1024)
        self.delay_buf = np.zeros(int(44100 * 2))
        self.delay_ptr = 0
        self.last_out = 0

    def _generate_waveform(self, ph, w_type, num_h):
        res = np.sin(ph)
        if w_type == "SQUARE":
            for h in range(3, num_h * 2, 2): res += (1.0 / h) * np.sin(ph * h)
        elif w_type == "SAW":
            for h in range(2, num_h + 1): res += (1.0 / h) * np.sin(ph * h)
        elif w_type == "TRIANGLE":
            for h in range(3, num_h * 2, 2):
                res += (1.0 / (h * h)) * np.sin(ph * h) * ((-1) ** ((h - 1) // 2))
        return res

    def callback(self, outdata, frames, time_info, status):
        if self.is_booting:
            outdata.fill(0);
            return
        with self.lock:
            while not midi_queue.empty():
                msg, n, v = midi_queue.get_nowait()
                if msg == "on":
                    if n in self.active_notes:
                        self.active_notes[n]["s"] = "A";
                        self.active_notes[n]["v"] = v / 127.0
                    else:
                        self.active_notes[n] = {"p": 0.0, "e": 0.0, "s": "A", "v": v / 127.0}
                elif msg == "off" and n in self.active_notes:
                    self.active_notes[n]["s"] = "R"

            out = np.zeros(frames)
            dt = 1.0 / self.fs
            t_vec = np.arange(frames)
            num_h = int(1 + 15 * self.params["bright"])

            for key, data in list(self.active_notes.items()):
                freq = 440.0 * (2.0 ** ((key - 69) / 12.0))
                p_inc = 2.0 * np.pi * freq / self.fs
                ph_base = data["p"] + t_vec * p_inc

                # --- OSCILLATEUR A (Base) ---
                wave_A = self._generate_waveform(ph_base, self.params["type_A"], num_h)

                # --- OSCILLATEUR B (Harmonique) ---
                ph_B = ph_base * self.params["ratio_B"]
                wave_B = self._generate_waveform(ph_B, self.params["type_B"], max(1, num_h // 2))

                # MÉLANGE ADDITIF
                res = (wave_A * (1 - self.params["mix"])) + (wave_B * self.params["mix"] * 0.6)

                # Enveloppe avec sécurité anti-clic
                envs = np.zeros(frames);
                curr_e = data["e"]
                a_s = dt / max(0.008, self.params["att"])
                r_s = dt / max(0.02, self.params["rel"])
                for i in range(frames):
                    if data["s"] == "A":
                        curr_e = min(1.0, curr_e + a_s)
                        if curr_e >= 1.0: data["s"] = "S"
                    elif data["s"] == "R":
                        curr_e = max(0.0, curr_e - r_s)
                    envs[i] = curr_e

                data["e"], data["p"] = curr_e, (ph_base[-1] + p_inc) % (2.0 * np.pi)
                out += res * envs * data["v"]
                if data["e"] <= 0 and data["s"] == "R": del self.active_notes[key]

            # Delay
            d_idx = int(self.params["d_time"] * self.fs)
            for i in range(frames):
                r = (self.delay_ptr - d_idx) % len(self.delay_buf)
                self.delay_buf[self.delay_ptr] = out[i] + self.delay_buf[r] * self.params["d_fb"]
                out[i] += self.delay_buf[r] * 0.3
                self.delay_ptr = (self.delay_ptr + 1) % len(self.delay_buf)

            # LOI DE SLEW (Amortisseur acoustique)
            final = np.tanh(out * 0.4)
            smoothed = np.zeros_like(final);
            alpha = 0.85
            for i in range(len(final)):
                self.last_out = alpha * self.last_out + (1 - alpha) * final[i]
                smoothed[i] = self.last_out
            self.visual_buffer = smoothed.copy()
            outdata[:] = smoothed.reshape(-1, 1)


engine = AudioEngine()
midi_queue = queue.Queue()


class Oscilloscope(QWidget):
    def __init__(self):
        super().__init__();
        self.setFixedHeight(220)

    def paintEvent(self, event):
        p = QPainter(self);
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(5, 5, 5))
        w, h, mid = self.width(), self.height(), self.height() / 2
        buf = engine.visual_buffer
        if len(buf) < 2: return
        p.setPen(QPen(QColor(212, 175, 55), 3))
        display_len = min(len(buf), 512)
        for i in range(display_len - 1):
            p.drawLine(int((i / display_len) * w), int(mid + buf[i] * mid * 0.8),
                       int(((i + 1) / display_len) * w), int(mid + buf[i + 1] * mid * 0.8))


class NeonBlackFinal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.conf = load_config()
        self.setWindowTitle("NEON BLACK - FINAL 1.6 HARMONIC");
        self.setFixedSize(800, 600)
        self.setStyleSheet(
            "QMainWindow { background: #000; } QComboBox { background: #111; color: #D4AF37; border: 1px solid #333; font-size: 16px; }")
        layout = QVBoxLayout()
        sel_row = QHBoxLayout()
        self.m_sel = QComboBox();
        self.m_sel.addItems(rtmidi.MidiIn().get_ports())
        self.a_sel = QComboBox();
        self.a_sel.addItems([d['name'] for d in sd.query_devices() if d['max_output_channels'] > 0])
        if self.conf["midi_name"] in rtmidi.MidiIn().get_ports(): self.m_sel.setCurrentText(self.conf["midi_name"])
        if self.conf["audio_name"]: self.a_sel.setCurrentText(self.conf["audio_name"])
        sel_row.addWidget(self.m_sel);
        sel_row.addWidget(self.a_sel);
        layout.addLayout(sel_row)
        self.osc = Oscilloscope();
        layout.addWidget(self.osc)
        self.lbl_emoji = QLabel("🔱");
        self.lbl_emoji.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_emoji.setStyleSheet("font-size: 120px; background: transparent;");
        layout.addWidget(self.lbl_emoji)
        self.btn = QPushButton("🎲 HARMONIC RANDOMIZE")
        self.btn.clicked.connect(self.randomize);
        layout.addWidget(self.btn)
        self.btn.setStyleSheet(
            "background: #D4AF37; color: #000; font-weight: bold; padding: 25px; border-radius: 10px; font-size: 24px;")
        self.midi = rtmidi.MidiIn();
        self.m_sel.currentIndexChanged.connect(self.init_midi);
        self.a_sel.currentIndexChanged.connect(self.request_audio_boot)
        cw = QWidget();
        cw.setLayout(layout);
        self.setCentralWidget(cw)
        self.stream = None;
        self.init_midi();
        self.request_audio_boot()
        self.timer = QTimer();
        self.timer.timeout.connect(self.refresh);
        self.timer.start(20)

    def init_midi(self):
        idx = self.m_sel.currentIndex()
        if self.midi.is_port_open(): self.midi.close_port()
        if idx >= 0: self.midi.open_port(idx); self.midi.set_callback(self.midi_cb)
        save_config(self.m_sel.currentText(), self.a_sel.currentText())

    def midi_cb(self, event, data=None):
        if engine.is_booting: return
        m, _ = event;
        s, n, v = m[0] & 0xF0, m[1], m[2]
        if s == 0x90 and v > 0:
            midi_queue.put(("on", n, v))
        elif s == 0x80 or (s == 0x90 and v == 0):
            midi_queue.put(("off", n, 0))

    def request_audio_boot(self):
        engine.is_booting = True
        with engine.lock: engine.active_notes.clear(); engine.delay_buf.fill(0); engine.visual_buffer.fill(0)
        threading.Thread(target=self.boot_audio, daemon=True).start()

    def request_audio_boot(self):
        # 1. LA DOUBLE BARRIÈRE
        engine.is_booting = True  # Bloque le callback audio

        # 2. NETTOYAGE PHYSIQUE
        with engine.lock:
            # On vide le dictionnaire pour que le callback n'ait RIEN à itérer
            engine.active_notes.clear()
            engine.delay_buf.fill(0)
            engine.last_out = 0

        # 3. PAUSE DE SYNCHRO
        # On attend un micro-délai pour être sûr que le dernier callback est fini
        time.sleep(0.05)

        threading.Thread(target=self.boot_audio, daemon=True).start()

    def boot_audio(self):
        if self.stream is not None:
            try:
                # On arrête le flux AVANT de le fermer
                self.stream.abort()
                self.stream.close()
            except:
                pass
            self.stream = None

        gc.collect()
        time.sleep(0.4)  # On laisse Windows et la 5090 respirer

        try:
            name = self.a_sel.currentText()
            devices = sd.query_devices()
            idx = next(i for i, d in enumerate(devices) if d['name'] == name)

            self.stream = sd.OutputStream(
                device=idx,
                callback=engine.callback,
                channels=1,
                samplerate=44100,
                blocksize=1024
            )
            self.stream.start()
            save_config(self.m_sel.currentText(), name)
        except Exception as e:
            print(f"Boot Error: {e}")
        finally:
            # On ne réactive le MIDI et l'audio qu'à la toute fin
            engine.is_booting = False

    def midi_cb(self, event, data=None):
        # Si on est en train de rebooter, on ignore TOUT,
        # même si Romuald reste appuyé sur une touche.
        if engine.is_booting:
            return

        m, _ = event
        s, n, v = m[0] & 0xF0, m[1], m[2]
        if s == 0x90 and v > 0:
            midi_queue.put(("on", n, v))
        elif s == 0x80 or (s == 0x90 and v == 0):
            midi_queue.put(("off", n, 0))

    def randomize(self):
        types = ["SINE", "SQUARE", "SAW", "TRIANGLE"]
        h_ratios = [1.0, 1.5, 2.0, 3.0, 4.0]  # Unisson, Quinte, Octave, Octave+Quinte, 2 Octaves
        with engine.lock:
            engine.params.update({
                "type_A": random.choice(types), "type_B": random.choice(types),
                "ratio_B": random.choice(h_ratios), "mix": random.uniform(0.2, 0.7),
                "bright": random.uniform(0.1, 1.0), "att": random.uniform(0.005, 0.04),
                "rel": random.uniform(0.05, 0.4), "d_fb": random.uniform(0.1, 0.5),
                "d_time": random.uniform(0.1, 0.3)
            })
            self.lbl_emoji.setText(random.choice(CRYSTAL_EMOJIS))

    def refresh(self):
        self.osc.update()
        amp = np.max(np.abs(engine.visual_buffer)) if engine.active_notes else 0
        scale = 100 + int(amp * 120);
        self.lbl_emoji.setStyleSheet(f"font-size: {scale}px; color: #D4AF37;")


if __name__ == "__main__":
    app = QApplication(sys.argv);
    win = NeonBlackFinal();
    win.show();
    sys.exit(app.exec())