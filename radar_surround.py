"""
radar_surround.py — Radar heurístico multicanal (surround 5.1/7.1 se o driver expuser) ou estéreo.
Não usa model.pkl; compare com radar_ml.py para o caminho com aprendizado de máquina.
Uso: python radar_surround.py
"""
import pyaudio
import numpy as np
import tkinter as tk
from threading import Thread
from collections import deque
import math
import time

# --- CONFIGURAÇÕES ---
CHUNK = 4096
RATE  = 48000  # 48kHz é padrão para surround

STEP_FREQ_MIN = 150
STEP_FREQ_MAX = 600
NOISE_MULTIPLIER = 2.5

PING_LIFETIME = 8.0
MAX_PINGS = 40

# 7.1: FL FR FC LFE RL RR SL SR
# 5.1: FL FR FC LFE RL RR
CH_FL, CH_FR, CH_FC = 0, 1, 2
CH_LFE              = 3
CH_RL, CH_RR        = 4, 5
CH_SL, CH_SR        = 6, 7
TOTAL_CHANNELS = 8

ANGLES_DEG = {
    'fl': 315, 'fr': 45, 'fc': 0,
    'rl': 225, 'rr': 135,
    'sl': 270, 'sr': 90,
}


class Ping:
    def __init__(self, x, y, is_behind, intensity):
        self.x         = x
        self.y         = y
        self.is_behind = is_behind
        self.intensity = intensity
        self.born_at   = time.time()

    def alpha(self):
        age  = time.time() - self.born_at
        frac = max(0.0, 1.0 - age / PING_LIFETIME)
        return frac  # 1.0 = novo, 0.0 = some


class Radar360:
    def __init__(self, root):
        self.root = root
        self.root.title("Radar 360° — Minimapa")
        self.root.geometry("440x520")
        self.root.configure(bg='#050505')

        self.cx, self.cy = 210, 200
        self.raio_max    = 155

        self.noise_floor = {k: deque(maxlen=60) for k in ANGLES_DEG}
        self.pings: list[Ping] = []
        self.pings_lock = __import__('threading').Lock()

        self._build_ui()

        self.p = pyaudio.PyAudio()
        self.device_idx, self.n_channels = self.find_device()

        if self.device_idx is not None:
            modo = f"SURROUND {self.n_channels}ch" if self.n_channels >= 6 else "STEREO (fallback)"
            self.label.config(text=f"MODO: {modo} — CALIBRANDO...", fg="#FFAA00")
            Thread(target=self.audio_thread, daemon=True).start()
        else:
            self.label.config(text="ERRO: dispositivo não encontrado", fg="red")

        self._render_loop()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.canvas = tk.Canvas(self.root, width=420, height=420,
                                bg='#050505', highlightthickness=0)
        self.canvas.pack()
        self._draw_static_grid()

        self.label = tk.Label(self.root, text="CALIBRANDO...",
                              fg="#FFAA00", bg="#050505", font=("Consolas", 9))
        self.label.pack()

        self.debug_label = tk.Label(self.root, text="",
                                    fg="#335533", bg="#050505", font=("Consolas", 8))
        self.debug_label.pack()

    def _draw_static_grid(self):
        cx, cy = self.cx, self.cy
        # Círculos
        for r in [52, 103, 155]:
            self.canvas.create_oval(cx-r, cy-r, cx+r, cy+r,
                                    outline="#0a1a0a", width=1)
        # Linhas de eixo
        self.canvas.create_line(cx, cy-160, cx, cy+160, fill="#0a1a0a")
        self.canvas.create_line(cx-160, cy, cx+160, cy, fill="#0a1a0a")
        # Diagonais
        for ang in [45, 135]:
            r = math.radians(ang)
            dx, dy = math.sin(r)*155, math.cos(r)*155
            self.canvas.create_line(cx-dx, cy-dy, cx+dx, cy+dy, fill="#071007")

        # Labels direção
        self.canvas.create_text(cx,     cy-168, text="N", fill="#1a441a", font=("Consolas", 8, "bold"))
        self.canvas.create_text(cx,     cy+168, text="S", fill="#1a441a", font=("Consolas", 8, "bold"))
        self.canvas.create_text(cx-168, cy,     text="W", fill="#1a441a", font=("Consolas", 8, "bold"))
        self.canvas.create_text(cx+168, cy,     text="E", fill="#1a441a", font=("Consolas", 8, "bold"))

        # Jogador no centro
        self.canvas.create_oval(cx-5, cy-5, cx+5, cy+5,
                                fill="#00FF00", outline="#004400")
        self.canvas.create_text(cx+12, cy-12, text="YOU",
                                fill="#00AA00", font=("Consolas", 7))

    # ── DEVICE ────────────────────────────────────────────────────────────────

    def find_device(self):
        print("\n=== DISPOSITIVOS DE ÁUDIO DISPONÍVEIS ===")
        best_surround = (None, 0)
        best_stereo   = (None, 0)

        for i in range(self.p.get_device_count()):
            info = self.p.get_device_info_by_index(i)
            name = info['name']
            ch   = int(info['maxInputChannels'])
            if ch < 1:
                continue
            print(f"  [{i:02d}] {name}  ({ch}ch)")

            if "CABLE" in name or "Virtual" in name or "VB-Audio" in name:
                if ch >= 6 and ch > best_surround[1]:
                    best_surround = (i, ch)
                elif ch >= 2 and best_stereo[0] is None:
                    best_stereo = (i, ch)

        print("=========================================\n")

        if best_surround[0] is not None:
            info = self.p.get_device_info_by_index(best_surround[0])
            ch   = min(best_surround[1], TOTAL_CHANNELS)
            print(f"[OK] Surround: {info['name']} ({ch}ch)")
            return best_surround[0], ch

        if best_stereo[0] is not None:
            info = self.p.get_device_info_by_index(best_stereo[0])
            print(f"[WARN] Stereo fallback: {info['name']} (2ch)")
            return best_stereo[0], 2

        # Último recurso: qualquer dispositivo com CABLE no nome
        for i in range(self.p.get_device_count()):
            info = self.p.get_device_info_by_index(i)
            if "CABLE" in info['name'] and int(info['maxInputChannels']) >= 2:
                return i, 2

        return None, 2

    # ── ÁUDIO ────────────────────────────────────────────────────────────────

    def step_energy(self, signal):
        fft   = np.abs(np.fft.rfft(signal))
        freqs = np.fft.rfftfreq(len(signal), 1.0 / RATE)
        mask  = (freqs >= STEP_FREQ_MIN) & (freqs <= STEP_FREQ_MAX)
        return float(np.sum(fft[mask]) / 1e5)

    def adaptive_threshold(self, key, e):
        history = self.noise_floor[key]
        if len(history) < 10 or e < np.percentile(list(history), 70):
            history.append(e)
        if len(history) < 10:
            return False, 0.0
        floor = np.mean(list(history))
        thr   = floor * NOISE_MULTIPLIER
        return e > thr, thr

    def audio_thread(self):
        stream = self.p.open(
            format=pyaudio.paInt16,
            channels=self.n_channels,
            rate=RATE,
            input=True,
            input_device_index=self.device_idx,
            frames_per_buffer=CHUNK
        )

        # Cooldown: evita pings duplicados do mesmo evento sonoro
        last_ping_time = 0.0
        PING_COOLDOWN  = 0.15  # segundos

        while True:
            data   = stream.read(CHUNK, exception_on_overflow=False)
            audio  = np.frombuffer(data, dtype=np.int16).astype(np.float32)
            frames = audio.reshape(-1, self.n_channels)

            def get_sig(ch):
                return frames[:, ch] if ch < self.n_channels else np.zeros(CHUNK)

            all_calibrated = all(len(self.noise_floor[k]) >= 10 for k in ANGLES_DEG)

            if self.n_channels >= 6:
                # Canais disponíveis dependendo do modo
                # 5.1 = 6ch: FL FR FC LFE RL RR  (sem SL SR)
                # 7.1 = 8ch: FL FR FC LFE RL RR SL SR
                raw = {
                    'fl': self.step_energy(get_sig(CH_FL)),
                    'fr': self.step_energy(get_sig(CH_FR)),
                    'fc': self.step_energy(get_sig(CH_FC)),
                    'rl': self.step_energy(get_sig(CH_RL)),
                    'rr': self.step_energy(get_sig(CH_RR)),
                    'sl': self.step_energy(get_sig(CH_SL)) if self.n_channels >= 8 else 0.0,
                    'sr': self.step_energy(get_sig(CH_SR)) if self.n_channels >= 8 else 0.0,
                    # LFE ignorado — subwoofer não tem info direcional
                }
                energies = {}
                any_active = False
                for k, e in raw.items():
                    active, _ = self.adaptive_threshold(k, e)
                    energies[k] = e if active else 0.0
                    if active:
                        any_active = True

                if not all_calibrated:
                    self.root.after(0, self.label.config,
                                    {'text': 'CALIBRANDO RUÍDO...', 'fg': '#FFAA00'})
                    continue

                if not any_active:
                    self.root.after(0, self.label.config,
                                    {'text': 'SILÊNCIO', 'fg': '#112211'})
                    continue

                vx, vy = 0.0, 0.0
                for k, ang in ANGLES_DEG.items():
                    rad = math.radians(ang)
                    vx += energies[k] * math.sin(rad)
                    vy += energies[k] * math.cos(rad)

                angle_result = math.atan2(vx, vy)
                magnitude    = math.sqrt(vx**2 + vy**2)
                distancia    = min(magnitude * 6, self.raio_max)
                is_behind    = math.cos(angle_result) < 0
                total        = sum(energies.values())
                dbg = f"FL={raw['fl']:.2f} FR={raw['fr']:.2f} RL={raw['rl']:.2f} RR={raw['rr']:.2f} | {math.degrees(angle_result):.0f}°"

            else:
                # Stereo fallback
                l, r = get_sig(0), get_sig(1)
                el = self.step_energy(l)
                er = self.step_energy(r)
                al, _ = self.adaptive_threshold('fl', el)
                ar, _ = self.adaptive_threshold('fr', er)

                if not all_calibrated:
                    self.root.after(0, self.label.config,
                                    {'text': 'CALIBRANDO RUÍDO...', 'fg': '#FFAA00'})
                    continue

                if not (al or ar):
                    self.root.after(0, self.label.config,
                                    {'text': 'SILÊNCIO', 'fg': '#112211'})
                    continue

                total     = el + er
                panning   = (er - el) / (total + 1e-6)
                distancia = min(total * 4, self.raio_max)
                ang       = panning * (math.pi / 2.2)

                # ITD para frente/atrás
                corr      = np.correlate(
                    l / (np.linalg.norm(l) + 1e-9),
                    r / (np.linalg.norm(r) + 1e-9), mode='full')
                center    = len(corr) // 2
                peak      = np.max(np.abs(corr[center-44: center+44]))
                is_behind = peak < 0.55

                vx = distancia * math.sin(ang)
                vy = distancia * math.cos(ang) * (-1 if not is_behind else 1)
                angle_result = math.atan2(vx, -vy)
                dbg = f"STEREO | L={el:.2f} R={er:.2f} | ITD={peak:.3f}"

            px = self.cx + distancia * math.sin(angle_result)
            py = self.cy - distancia * math.cos(angle_result)

            # Adiciona ping com cooldown
            now = time.time()
            if now - last_ping_time > PING_COOLDOWN:
                last_ping_time = now
                ping = Ping(px, py, is_behind, min(total, 5.0))
                with self.pings_lock:
                    self.pings.append(ping)
                    if len(self.pings) > MAX_PINGS:
                        self.pings.pop(0)

            deg = math.degrees(angle_result)
            self.root.after(0, self.label.config,
                            {'text': f"{'ATRÁS' if is_behind else 'FRENTE'} | {deg:.0f}°",
                             'fg': '#0055FF' if is_behind else '#00FF00'})
            self.root.after(0, self.debug_label.config, {'text': dbg})

    # ── RENDER LOOP ───────────────────────────────────────────────────────────

    def _render_loop(self):
        """Redesenha os pings a cada 50ms com fade baseado na idade."""
        self.canvas.delete("pings")  # deleta apenas os pings, não o grid

        with self.pings_lock:
            # Remove pings expirados
            self.pings = [p for p in self.pings if p.alpha() > 0.0]
            pings_snapshot = list(self.pings)

        for p in pings_snapshot:
            alpha = p.alpha()

            # Interpola cor com base no alpha e no tipo
            if p.is_behind:
                # Azul → preto
                r_val = int(0   * alpha)
                g_val = int(85  * alpha)
                b_val = int(255 * alpha)
            else:
                # Verde → preto
                r_val = int(0   * alpha)
                g_val = int(255 * alpha)
                b_val = int(0   * alpha)

            cor  = f"#{r_val:02x}{g_val:02x}{b_val:02x}"
            tam  = max(2, int(4 + p.intensity * 1.5))

            self.canvas.create_oval(
                p.x - tam, p.y - tam, p.x + tam, p.y + tam,
                fill=cor, outline="", tags="pings"
            )

            # Halo nos pings recentes (alpha > 0.7)
            if alpha > 0.7:
                halo_alpha = (alpha - 0.7) / 0.3
                halo_size  = tam + 4
                halo_col   = "#005500" if not p.is_behind else "#001144"
                self.canvas.create_oval(
                    p.x - halo_size, p.y - halo_size,
                    p.x + halo_size, p.y + halo_size,
                    fill="", outline=halo_col, width=1, tags="pings"
                )

        self.root.after(50, self._render_loop)


if __name__ == "__main__":
    root = tk.Tk()
    app  = Radar360(root)
    root.mainloop()