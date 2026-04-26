"""
radar_ml.py — Radar acústico em tempo real com ML (model.pkl), captura estéreo (ex.: VB-Cable).
Fluxo típico: collector.py → train.py → python radar_ml.py
"""
import pyaudio
import numpy as np
import tkinter as tk
from threading import Thread
from collections import deque
import math
import time
import pickle
import os

# --- CONFIGURAÇÕES ---
CHUNK = 4096
RATE  = 48000

STEP_FREQ_MIN    = 200   # CS2 passos começam aqui
STEP_FREQ_MAX    = 500   # banda mais estreita = menos falsos positivos
NOISE_MULTIPLIER = 3.0   # mais agressivo

# Filtro de transiente: passos são bursts curtos
# Se energia ficar alta por mais de N frames seguidos = som contínuo, ignora
MAX_CONTINUOUS_FRAMES = 4

# Ratio mínimo de "burst": energia atual / média recente
# Passos têm pico alto seguido de queda — sons contínuos ficam estáveis
TRANSIENT_RATIO = 1.8

PING_LIFETIME    = 8.0
MAX_PINGS        = 40
MODEL_FILE       = "model.pkl"

BG       = '#030a03'
GREEN_HI = '#00ff41'
GREEN_MD = '#00cc33'
GREEN_LO = '#005510'
GREEN_DIM= '#001a05'
AMBER    = '#ffaa00'
GRID_COL = '#041a04'
CX, CY   = 220, 220
R_MAX    = 170


class Ping:
    def __init__(self, x, y, angle_deg, intensity):
        self.x         = x
        self.y         = y
        self.angle_deg = angle_deg
        self.intensity = intensity
        self.born_at   = time.time()

    def alpha(self):
        return max(0.0, 1.0 - (time.time() - self.born_at) / PING_LIFETIME)


def angle_to_color(angle_deg, alpha):
    """Cor baseada no ângulo: frente=verde, atrás=azul, laterais=amarelo."""
    a = math.radians(angle_deg)
    # Componente frente/atrás: cos(a)  1=frente, -1=atrás
    # Componente lateral:      |sin(a)| 1=lateral
    front = (math.cos(a) + 1) / 2   # 0..1
    side  = abs(math.sin(a))

    r = int(0   * alpha)
    g = int((front * 200 + 55) * alpha)
    b = int(((1 - front) * 220) * alpha)
    return f"#{r:02x}{g:02x}{b:02x}"


class Radar360:
    def __init__(self, root):
        self.root = root
        self.root.title("RADAR 360° — ML")
        self.root.geometry("500x560")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)

        self.noise_floor      = {'l': deque(maxlen=60), 'r': deque(maxlen=60)}
        self.pings            = []
        self.pings_lock       = __import__('threading').Lock()
        self.sweep_angle      = 0.0
        self.last_ping_t      = 0.0
        self.energy_history   = deque(maxlen=8)
        self.continuous_count = 0

        self._build_ui()

        # Carrega modelo ML
        self.model_payload = None
        if os.path.exists(MODEL_FILE):
            with open(MODEL_FILE, 'rb') as f:
                self.model_payload = pickle.load(f)
            name = self.model_payload['model_name']
            acc  = self.model_payload['test_acc']
            self.mode_var.set(f"ML  {name}  acc={acc:.0%}")
            self.mode_lbl.config(fg=GREEN_HI)
        else:
            self.mode_var.set("HEURISTIC MODE  (model.pkl not found)")
            self.mode_lbl.config(fg=AMBER)

        self.p = pyaudio.PyAudio()
        self.device_idx = self.find_device()

        if self.device_idx is not None:
            Thread(target=self.audio_thread, daemon=True).start()
        else:
            self.status_var.set("✖ DEVICE NOT FOUND")

        self._animate_sweep()
        self._render_loop()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.canvas = tk.Canvas(self.root, width=500, height=470,
                                bg=BG, highlightthickness=0)
        self.canvas.pack()

        bottom = tk.Frame(self.root, bg=BG)
        bottom.pack(fill='x', padx=14, pady=2)

        self.mode_var = tk.StringVar()
        self.mode_lbl = tk.Label(bottom, textvariable=self.mode_var,
                                 fg=AMBER, bg=BG, font=("Courier", 8))
        self.mode_lbl.pack(anchor='w')

        self.status_var = tk.StringVar(value="INITIALIZING...")
        tk.Label(bottom, textvariable=self.status_var,
                 fg=GREEN_MD, bg=BG, font=("Courier", 9)).pack(anchor='w')

        self.angle_var = tk.StringVar(value="")
        tk.Label(bottom, textvariable=self.angle_var,
                 fg=GREEN_HI, bg=BG, font=("Courier", 10, "bold")).pack(anchor='w')

        self._draw_static()

    def _draw_static(self):
        c = self.canvas
        c.create_text(250, 16, text="◈  ACOUSTIC RADAR 360°  ◈",
                      fill=GREEN_MD, font=("Courier", 10, "bold"))
        c.create_line(20, 28, 480, 28, fill=GREEN_DIM)

        for r, lbl in [(57,"25m"),(114,"50m"),(171,"75m")]:
            c.create_oval(CX-r, CY-r, CX+r, CY+r,
                          outline=GRID_COL, width=1, dash=(3,7))
            c.create_text(CX+r+4, CY+4, text=lbl,
                          fill='#021402', font=("Courier",6), anchor='w')

        for a in range(0, 360, 30):
            rad = math.radians(a - 90)
            x2  = CX + R_MAX * math.cos(rad)
            y2  = CY + R_MAX * math.sin(rad)
            c.create_line(CX, CY, x2, y2, fill=GRID_COL, dash=(2,10))

        c.create_oval(CX-R_MAX, CY-R_MAX, CX+R_MAX, CY+R_MAX,
                      outline='#0a2a0a', width=2)

        for ang_deg, lbl in [(0,"N"),(90,"E"),(180,"S"),(270,"W")]:
            rad = math.radians(ang_deg - 90)
            x   = CX + (R_MAX+18) * math.cos(rad)
            y   = CY + (R_MAX+18) * math.sin(rad)
            c.create_text(x, y, text=lbl, fill='#1a3a1a',
                          font=("Courier", 8, "bold"))

        # YOU
        c.create_oval(CX-5, CY-5, CX+5, CY+5, fill=GREEN_HI, outline=GREEN_MD)
        c.create_text(CX, CY-15, text="YOU", fill=GREEN_MD, font=("Courier",7,"bold"))

        # Sweep (atrás dos pings)
        self.sweep_fan  = c.create_arc(
            CX-R_MAX, CY-R_MAX, CX+R_MAX, CY+R_MAX,
            start=89, extent=5, fill='#001a00', outline='',
            style=tk.PIESLICE, tags="sweep"
        )
        self.sweep_line = c.create_line(CX, CY, CX, CY-R_MAX,
                                        fill=GREEN_MD, width=1, tags="sweep")

    # ── SWEEP ─────────────────────────────────────────────────────────────────

    def _animate_sweep(self):
        self.sweep_angle = (self.sweep_angle + 1.5) % 360
        tk_start = (90 - self.sweep_angle) % 360
        rad = math.radians(self.sweep_angle - 90)
        x2  = CX + R_MAX * math.cos(rad)
        y2  = CY + R_MAX * math.sin(rad)
        self.canvas.coords(self.sweep_line, CX, CY, x2, y2)
        self.canvas.itemconfig(self.sweep_fan, start=tk_start-1, extent=7)
        self.root.after(25, self._animate_sweep)

    # ── DEVICE ────────────────────────────────────────────────────────────────

    def find_device(self):
        for i in range(self.p.get_device_count()):
            info = self.p.get_device_info_by_index(i)
            if "CABLE" in info['name'] and info['maxInputChannels'] >= 2:
                self.root.after(0, self.status_var.set,
                                f"● {info['name'][:36]}")
                return i
        return None

    # ── FEATURES (mesmas do collector) ────────────────────────────────────────

    def extract_features(self, l_full, r_full):
        freqs = np.fft.rfftfreq(len(l_full), 1.0 / RATE)
        fft_l = np.abs(np.fft.rfft(l_full))
        fft_r = np.abs(np.fft.rfft(r_full))
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
        return np.array(features).reshape(1, -1)

    # ── PREDIÇÃO ──────────────────────────────────────────────────────────────

    def predict_angle(self, l, r):
        """Retorna ângulo previsto (0-315) e confiança (0-1)."""
        if self.model_payload is None:
            return self._heuristic_angle(l, r), 0.5

        feats  = self.extract_features(l, r)
        scaled = self.model_payload['scaler'].transform(feats)
        model  = self.model_payload['model']
        angle  = int(model.predict(scaled)[0])

        # Confiança via probabilidade se disponível
        if hasattr(model, 'predict_proba'):
            proba   = model.predict_proba(scaled)[0]
            classes = list(model.classes_)
            conf    = float(proba[classes.index(angle)]) if angle in classes else 0.5
        else:
            conf = 0.8

        return angle, conf

    def _heuristic_angle(self, l, r):
        """Fallback sem modelo: só pan L/R."""
        fft_l  = np.abs(np.fft.rfft(l))
        fft_r  = np.abs(np.fft.rfft(r))
        freqs  = np.fft.rfftfreq(len(l), 1.0 / RATE)
        mask   = (freqs >= STEP_FREQ_MIN) & (freqs <= STEP_FREQ_MAX)
        el     = np.sum(fft_l[mask]) + 1e-9
        er     = np.sum(fft_r[mask]) + 1e-9
        pan    = (er - el) / (er + el)   # -1..+1
        return int(round(pan * 90)) % 360

    # ── AUDIO THREAD ──────────────────────────────────────────────────────────

    def audio_thread(self):
        stream = self.p.open(
            format=pyaudio.paInt16, channels=2, rate=RATE,
            input=True, input_device_index=self.device_idx,
            frames_per_buffer=CHUNK
        )
        self.root.after(0, self.status_var.set, "● REC")

        # Buffer de frames para ter contexto (igual ao collector)
        buf = deque(maxlen=5)
        calibrated = False

        while True:
            data  = stream.read(CHUNK, exception_on_overflow=False)
            audio = np.frombuffer(data, dtype=np.int16).astype(np.float32)
            l, r  = audio[0::2], audio[1::2]

            # Energia na banda de passos
            fft_l  = np.abs(np.fft.rfft(l))
            fft_r  = np.abs(np.fft.rfft(r))
            freqs  = np.fft.rfftfreq(len(l), 1.0 / RATE)
            mask   = (freqs >= STEP_FREQ_MIN) & (freqs <= STEP_FREQ_MAX)
            el     = float(np.sum(fft_l[mask]) / 1e5)
            er_val = float(np.sum(fft_r[mask]) / 1e5)

            # Calibração do ruído
            nf_l = self.noise_floor['l']
            nf_r = self.noise_floor['r']
            if len(nf_l) < 10 or el < np.percentile(list(nf_l), 70):
                nf_l.append(el)
            if len(nf_r) < 10 or er_val < np.percentile(list(nf_r), 70):
                nf_r.append(er_val)

            if len(nf_l) < 10 or len(nf_r) < 10:
                self.root.after(0, self.status_var.set, "CALIBRANDO...")
                continue

            thr_l = np.mean(list(nf_l)) * NOISE_MULTIPLIER
            thr_r = np.mean(list(nf_r)) * NOISE_MULTIPLIER
            energy = el + er_val
            above_thr = el > thr_l or er_val > thr_r

            buf.append((l.copy(), r.copy()))
            self.energy_history.append(energy)

            if not above_thr:
                self.continuous_count = 0
                continue

            # ── Filtro 1: som contínuo ─────────────────────────────────────
            # Se ficou ativo por muitos frames seguidos = não é passo
            self.continuous_count += 1
            if self.continuous_count > MAX_CONTINUOUS_FRAMES:
                self.root.after(0, self.status_var.set, "● REC — CONTINUOUS (ignored)")
                continue

            # ── Filtro 2: transiente ───────────────────────────────────────
            # Passo = pico de energia brusco. Som contínuo = energia estável.
            if len(self.energy_history) >= 4:
                avg_recent = np.mean(list(self.energy_history)[:-1])  # exclui atual
                transient_ratio = energy / (avg_recent + 1e-9)
                if transient_ratio < TRANSIENT_RATIO:
                    self.root.after(0, self.status_var.set, "● REC — NOT TRANSIENT (ignored)")
                    continue

            # Cooldown
            now = time.time()
            if now - self.last_ping_t < 0.15:
                continue
            self.last_ping_t = now

            # Concatena frames do buffer para mais contexto
            l_ctx = np.concatenate([f[0] for f in buf])
            r_ctx = np.concatenate([f[1] for f in buf])

            angle_deg, conf = self.predict_angle(l_ctx, r_ctx)

            # Posição no radar
            rad       = math.radians(angle_deg - 90)
            intensity = min((el + er_val) * 0.5, 5.0)
            dist      = R_MAX * 0.55 + intensity * 8
            dist      = min(dist, R_MAX * 0.9)
            px = CX + dist * math.cos(rad)
            py = CY + dist * math.sin(rad)

            ping = Ping(px, py, angle_deg, intensity)
            with self.pings_lock:
                self.pings.append(ping)
                if len(self.pings) > MAX_PINGS:
                    self.pings.pop(0)

            self.root.after(0, self.angle_var.set,
                            f"↗ {angle_deg}°  conf={conf:.0%}  int={intensity:.1f}")
            self.root.after(0, self.status_var.set, "● REC — ACTIVE")

    # ── RENDER LOOP ───────────────────────────────────────────────────────────

    def _render_loop(self):
        self.canvas.delete("pings")

        with self.pings_lock:
            self.pings = [p for p in self.pings if p.alpha() > 0.0]
            snap = list(self.pings)

        for p in snap:
            alpha = p.alpha()
            cor   = angle_to_color(p.angle_deg, alpha)
            tam   = max(2, int(3 + p.intensity * 1.2))

            self.canvas.create_oval(
                p.x-tam, p.y-tam, p.x+tam, p.y+tam,
                fill=cor, outline="", tags="pings"
            )
            if alpha > 0.75:
                self.canvas.create_oval(
                    p.x-tam-4, p.y-tam-4, p.x+tam+4, p.y+tam+4,
                    fill="", outline=cor, width=1, tags="pings"
                )

        self.root.after(50, self._render_loop)


if __name__ == "__main__":
    root = tk.Tk()
    app  = Radar360(root)
    root.mainloop()