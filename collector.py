import pyaudio
import numpy as np
import tkinter as tk
from threading import Thread
from collections import deque
import time
import csv
import os
import math

# --- CONFIGURAÇÕES ---
CHUNK   = 4096
RATE    = 48000
OUTPUT_CSV = "samples.csv"

STEP_FREQ_MIN = 150
STEP_FREQ_MAX = 600

FRAMES_BEFORE = 3
FRAMES_AFTER  = 2

ANGLE_KEYS = {
    '8': 0,    'KP_8': 0,
    '9': 45,   'KP_9': 45,
    '6': 90,   'KP_6': 90,
    '3': 135,  'KP_3': 135,
    '2': 180,  'KP_2': 180,
    '1': 225,  'KP_1': 225,
    '4': 270,  'KP_4': 270,
    '7': 315,  'KP_7': 315,
}

BG       = '#030a03'
GREEN_HI = '#00ff41'
GREEN_MD = '#00cc33'
GREEN_LO = '#005510'
GREEN_DIM= '#001a05'
AMBER    = '#ffaa00'
RED_COL  = '#ff3322'
GRID_COL = '#041a04'

CX, CY   = 220, 220
R_MAX    = 170


class Collector:
    def __init__(self, root):
        self.root = root
        self.root.title("ACOUSTIC COLLECTOR v1.0")
        self.root.geometry("640x700")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)

        self.frame_buffer    = deque(maxlen=FRAMES_BEFORE + 1)
        self.pending_capture = 0
        self.pending_angle   = None
        self.capture_frames  = []
        self.lock            = __import__('threading').Lock()

        self.total_samples   = {a: 0 for a in set(ANGLE_KEYS.values())}
        self.session_samples = 0
        self.sweep_angle     = 0.0

        self._build_ui()
        self._load_existing()

        self.p = pyaudio.PyAudio()
        self.device_idx = self.find_device()

        if self.device_idx is not None:
            Thread(target=self.audio_thread, daemon=True).start()
            self._animate_sweep()
        else:
            self.status_var.set("✖ DEVICE NOT FOUND")

        self.root.bind("<Key>", self.on_key)
        self.root.focus_set()

    # ── BUILD UI ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.canvas = tk.Canvas(
            self.root, width=640, height=460,
            bg=BG, highlightthickness=0
        )
        self.canvas.pack()

        bottom = tk.Frame(self.root, bg=BG)
        bottom.pack(fill='x', padx=16, pady=2)

        # Status
        self.status_var = tk.StringVar(value="INITIALIZING...")
        self.status_lbl = tk.Label(bottom, textvariable=self.status_var,
                                   fg=AMBER, bg=BG, font=("Courier", 9), anchor='w')
        self.status_lbl.pack(fill='x')

        # Contadores
        count_row = tk.Frame(bottom, bg=BG)
        count_row.pack(fill='x', pady=3)
        tk.Label(count_row, text="SAMPLES/ANGLE ▸",
                 fg=GREEN_LO, bg=BG, font=("Courier", 8)).pack(side='left', padx=(0,6))

        self.count_labels = {}
        for ang in sorted(set(ANGLE_KEYS.values())):
            f = tk.Frame(count_row, bg=BG)
            f.pack(side='left', padx=4)
            tk.Label(f, text=f"{ang}°", fg=GREEN_LO, bg=BG,
                     font=("Courier", 7)).pack()
            lbl = tk.Label(f, text="0", fg=RED_COL, bg=BG,
                           font=("Courier", 9, "bold"))
            lbl.pack()
            self.count_labels[ang] = lbl

        # Total
        self.total_var = tk.StringVar(value="TOTAL: 0  |  SESSION: 0")
        tk.Label(bottom, textvariable=self.total_var,
                 fg=GREEN_MD, bg=BG, font=("Courier", 9)).pack(anchor='w')

        # Instrução
        tk.Label(bottom,
                 text="NUMPAD  7↖ 8↑ 9↗  ·  4← 6→  ·  1↙ 2↓ 3↘   (press when step heard)",
                 fg=GREEN_LO, bg=BG, font=("Courier", 7)).pack(anchor='w', pady=(3,0))

        self._draw_static()

    def _draw_static(self):
        c = self.canvas

        # Header
        c.create_text(320, 16, text="◈  ACOUSTIC POSITION COLLECTOR  ◈",
                      fill=GREEN_MD, font=("Courier", 10, "bold"))
        c.create_line(20, 28, 620, 28, fill=GREEN_DIM)

        # Círculos com dash
        for r, lbl in [(57, "25m"), (114, "50m"), (171, "75m")]:
            c.create_oval(CX-r, CY-r, CX+r, CY+r,
                          outline=GRID_COL, width=1, dash=(3, 7))
            c.create_text(CX + r + 5, CY + 4, text=lbl,
                          fill='#021402', font=("Courier", 6), anchor='w')

        # Linhas radiais
        for a in range(0, 360, 30):
            rad = math.radians(a - 90)
            x2  = CX + R_MAX * math.cos(rad)
            y2  = CY + R_MAX * math.sin(rad)
            c.create_line(CX, CY, x2, y2, fill=GRID_COL, dash=(2, 10))

        # Anel externo duplo
        c.create_oval(CX-R_MAX, CY-R_MAX, CX+R_MAX, CY+R_MAX,
                      outline='#0a2a0a', width=2)
        c.create_oval(CX-R_MAX-5, CY-R_MAX-5, CX+R_MAX+5, CY+R_MAX+5,
                      outline='#031003', width=1)

        # Cardinais
        for ang_deg, lbl in [(0,"N"),(90,"E"),(180,"S"),(270,"W")]:
            rad = math.radians(ang_deg - 90)
            x   = CX + (R_MAX + 18) * math.cos(rad)
            y   = CY + (R_MAX + 18) * math.sin(rad)
            c.create_text(x, y, text=lbl, fill='#1a3a1a',
                          font=("Courier", 8, "bold"))

        # YOU no centro
        c.create_oval(CX-5, CY-5, CX+5, CY+5,
                      fill=GREEN_HI, outline=GREEN_MD)
        c.create_text(CX, CY - 15, text="YOU",
                      fill=GREEN_MD, font=("Courier", 7, "bold"))

        # Sweep (criado antes dos botões para ficar atrás)
        self.sweep_fan = c.create_arc(
            CX-R_MAX, CY-R_MAX, CX+R_MAX, CY+R_MAX,
            start=89, extent=5, fill='#001a00', outline='',
            style=tk.PIESLICE, tags="sweep"
        )
        self.sweep_line = c.create_line(
            CX, CY, CX, CY - R_MAX,
            fill=GREEN_MD, width=1, tags="sweep"
        )

        # Botões de ângulo ao redor do radar
        self.angle_buttons = {}
        btn_pos = {
            0:   (CX,              CY - R_MAX - 36),
            45:  (CX + int(R_MAX/1.3), CY - int(R_MAX/1.3)),
            90:  (CX + R_MAX + 36, CY),
            135: (CX + int(R_MAX/1.3), CY + int(R_MAX/1.3)),
            180: (CX,              CY + R_MAX + 36),
            225: (CX - int(R_MAX/1.3), CY + int(R_MAX/1.3)),
            270: (CX - R_MAX - 36, CY),
            315: (CX - int(R_MAX/1.3), CY - int(R_MAX/1.3)),
        }

        for ang, (bx, by) in btn_pos.items():
            # Linha conectora até borda do radar
            rad = math.radians(ang - 90)
            lx  = CX + R_MAX * math.cos(rad)
            ly  = CY + R_MAX * math.sin(rad)
            c.create_line(lx, ly, bx, by, fill='#031803', width=1,
                          tags=f"line_{ang}")

            # Caixa do botão
            w, h = 46, 30
            rect = c.create_rectangle(
                bx-w//2, by-h//2, bx+w//2, by+h//2,
                fill=GREEN_DIM, outline='#0a2a0a', width=1,
                tags=f"btn_{ang}"
            )
            ang_txt = c.create_text(
                bx, by - 5, text=f"{ang}°",
                fill=GREEN_MD, font=("Courier", 8, "bold"),
                tags=f"btn_{ang}"
            )
            cnt_txt = c.create_text(
                bx, by + 7, text="0",
                fill=GREEN_LO, font=("Courier", 7),
                tags=f"btn_{ang}"
            )
            self.angle_buttons[ang] = {
                'rect': rect,
                'ang_txt': ang_txt,
                'cnt_txt': cnt_txt,
                'x': bx, 'y': by,
            }

    # ── SWEEP ─────────────────────────────────────────────────────────────────

    def _animate_sweep(self):
        self.sweep_angle = (self.sweep_angle + 1.5) % 360
        tk_start = (90 - self.sweep_angle) % 360
        rad = math.radians(self.sweep_angle - 90)
        x2  = CX + R_MAX * math.cos(rad)
        y2  = CY + R_MAX * math.sin(rad)
        self.canvas.coords(self.sweep_line, CX, CY, x2, y2)
        self.canvas.itemconfig(self.sweep_fan, start=tk_start - 1, extent=7)
        self.root.after(25, self._animate_sweep)

    # ── DEVICE ────────────────────────────────────────────────────────────────

    def find_device(self):
        for i in range(self.p.get_device_count()):
            info = self.p.get_device_info_by_index(i)
            if "CABLE" in info['name'] and info['maxInputChannels'] >= 2:
                self.status_var.set(f"● DEVICE: {info['name'][:32]}")
                self.status_lbl.config(fg=GREEN_MD)
                return i
        return None

    # ── ÁUDIO ─────────────────────────────────────────────────────────────────

    def audio_thread(self):
        stream = self.p.open(
            format=pyaudio.paInt16, channels=2, rate=RATE,
            input=True, input_device_index=self.device_idx,
            frames_per_buffer=CHUNK
        )
        self.root.after(0, lambda: (
            self.status_var.set("● REC — PRESS NUMPAD KEY ON ENEMY STEP"),
            self.status_lbl.config(fg=GREEN_HI)
        ))
        while True:
            data  = stream.read(CHUNK, exception_on_overflow=False)
            audio = np.frombuffer(data, dtype=np.int16).astype(np.float32)
            l, r  = audio[0::2], audio[1::2]
            with self.lock:
                self.frame_buffer.append((l.copy(), r.copy()))
                if self.pending_capture > 0:
                    self.capture_frames.append((l.copy(), r.copy()))
                    self.pending_capture -= 1
                    if self.pending_capture == 0:
                        frames = list(self.capture_frames)
                        angle  = self.pending_angle
                        self.capture_frames = []
                        Thread(target=self.save_sample,
                               args=(frames, angle), daemon=True).start()

    # ── KEYPRESS ──────────────────────────────────────────────────────────────

    def on_key(self, event):
        key = event.keysym
        if key not in ANGLE_KEYS:
            return
        angle = ANGLE_KEYS[key]
        with self.lock:
            if self.pending_capture > 0:
                return
            self.capture_frames  = list(self.frame_buffer)
            self.pending_capture = FRAMES_AFTER
            self.pending_angle   = angle
        self.root.after(0, self._flash_button, angle)

    # ── FEATURES ──────────────────────────────────────────────────────────────

    def extract_features(self, frames):
        l_full = np.concatenate([f[0] for f in frames])
        r_full = np.concatenate([f[1] for f in frames])
        freqs  = np.fft.rfftfreq(len(l_full), 1.0 / RATE)
        fft_l  = np.abs(np.fft.rfft(l_full))
        fft_r  = np.abs(np.fft.rfft(r_full))
        features = []

        bands = np.linspace(0, 8000, 17)
        for lo, hi in zip(bands[:-1], bands[1:]):
            mask = (freqs >= lo) & (freqs < hi)
            el = np.sum(fft_l[mask]) + 1e-9
            er = np.sum(fft_r[mask]) + 1e-9
            features.append(float((er - el) / (er + el)))

        norm_l = l_full / (np.linalg.norm(l_full) + 1e-9)
        norm_r = r_full / (np.linalg.norm(r_full) + 1e-9)
        corr   = np.correlate(norm_l, norm_r, mode='full')
        center = len(corr) // 2
        window = int(RATE * 0.001)
        cw     = corr[center - window: center + window]
        peak_i = np.argmax(np.abs(cw))
        features.append((peak_i - window) / RATE)
        features.append(float(cw[peak_i]))

        ph_l = np.angle(np.fft.rfft(l_full))
        ph_r = np.angle(np.fft.rfft(r_full))
        pd   = np.angle(np.exp(1j * (ph_l - ph_r)))
        for lo, hi in zip(bands[::2][:-1], bands[::2][1:]):
            mask = (freqs >= lo) & (freqs < hi)
            features.append(float(np.mean(pd[mask])) if mask.any() else 0.0)

        e_tot = np.sum(fft_l) + np.sum(fft_r) + 1e-9
        features.append(float(np.sum(fft_l) / e_tot))
        features.append(float(np.sum(fft_r) / e_tot))
        features.append(float(np.sum(freqs * fft_l) / (np.sum(fft_l) + 1e-9)) / 8000.0)
        features.append(float(np.sum(freqs * fft_r) / (np.sum(fft_r) + 1e-9)) / 8000.0)
        return features

    # ── SALVAR ────────────────────────────────────────────────────────────────

    def save_sample(self, frames, angle):
        features     = self.extract_features(frames)
        write_header = not os.path.exists(OUTPUT_CSV)
        with open(OUTPUT_CSV, 'a', newline='') as f:
            writer = csv.writer(f)
            if write_header:
                writer.writerow(['angle'] + [f'f{i}' for i in range(len(features))])
            writer.writerow([angle] + [f'{v:.6f}' for v in features])
        self.total_samples[angle] = self.total_samples.get(angle, 0) + 1
        self.session_samples += 1
        self.root.after(0, self._refresh_counts)

    def _load_existing(self):
        if not os.path.exists(OUTPUT_CSV):
            return
        with open(OUTPUT_CSV, newline='') as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                try:
                    ang = int(row[0])
                    if ang in self.total_samples:
                        self.total_samples[ang] += 1
                except:
                    pass
        self._refresh_counts()

    # ── UI HELPERS ────────────────────────────────────────────────────────────

    def _flash_button(self, angle):
        btn = self.angle_buttons.get(angle)
        if not btn:
            return

        # Acende botão
        self.canvas.itemconfig(btn['rect'],    fill='#003a00', outline=GREEN_HI)
        self.canvas.itemconfig(btn['ang_txt'], fill=GREEN_HI)

        # Ping no radar
        rad = math.radians(angle - 90)
        r   = R_MAX * 0.55
        px  = CX + r * math.cos(rad)
        py  = CY + r * math.sin(rad)
        ring = self.canvas.create_oval(px-10, py-10, px+10, py+10,
                                       fill=GREEN_HI, outline='', tags="fpings")
        line = self.canvas.create_line(CX, CY, btn['x'], btn['y'],
                                       fill=GREEN_MD, width=1, dash=(2,4),
                                       tags="fpings")

        def _restore():
            self.canvas.itemconfig(btn['rect'],    fill=GREEN_DIM, outline='#0a2a0a')
            self.canvas.itemconfig(btn['ang_txt'], fill=GREEN_MD)
            self.canvas.delete(ring)
            self.canvas.delete(line)

        self.root.after(350, _restore)

    def _refresh_counts(self):
        total = 0
        for ang, lbl in self.count_labels.items():
            n = self.total_samples.get(ang, 0)
            total += n
            cor = GREEN_HI if n >= 50 else AMBER if n >= 20 else GREEN_LO if n > 0 else RED_COL
            lbl.config(text=str(n), fg=cor)

        for ang, btn in self.angle_buttons.items():
            n   = self.total_samples.get(ang, 0)
            cor = GREEN_HI if n >= 50 else AMBER if n >= 20 else GREEN_LO
            self.canvas.itemconfig(btn['cnt_txt'], text=str(n), fill=cor)

        ready = all(self.total_samples.get(a, 0) >= 50
                    for a in set(ANGLE_KEYS.values()))
        suffix = "  ✓ READY TO TRAIN" if ready else f"  (need 50/angle)"
        self.total_var.set(
            f"TOTAL: {total}  |  SESSION: {self.session_samples}{suffix}"
        )


if __name__ == "__main__":
    root = tk.Tk()
    app  = Collector(root)
    root.mainloop()