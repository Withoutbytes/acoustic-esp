# Acoustic ESP — Acoustic Radar

> 🇺🇸 **English** | [🇧🇷 Português abaixo](#-acoustic-esp--radar-acústico-pt-br)

---

## Demonstration

Example video in the repository root: [`demonstration.mp4`](demonstration.mp4)

<video src="demonstration.mp4" controls playsinline width="100%"></video>

---

## Quick Reference

| File | Use when… |
|------|-----------|
| `collector.py` | **Record training data**: label steps by direction → generates `samples.csv` |
| `train.py` | You have samples and want to generate **`model.pkl`** |
| **`radar_ml.py`** | **Main radar**: stereo + **ML model** (`model.pkl`) |
| **`radar_surround.py`** | Test **radar without ML**, via **multiple channels** (5.1/7.1) when the driver exposes surround |

### Screenshots

| Collector UI | In-game Demo |
|---|---|
| ![Collector UI](prints/collector-ui.png) | ![In-game Demo](prints/in-game-demo-ui.png) |

---

## Overview

**Acoustic radar** project: estimate **direction (angle)** and **relative distance** to the player from captured audio (e.g. footsteps), using **stereo + machine learning**, instead of relying on **8 raw surround 7.1 channels**.

---

## Intent & Difference from "7.1 ESP"

Many approaches try to read each virtual speaker of the **7.1 mix** (FL, FR, RL, RR, etc.) to determine the sound's origin. This repository is **not** focused on that path.

The main flow here is:

1. Capture a **stereo** signal (left/right) — e.g. the game's output routed through a **virtual cable** (VB-Audio Cable, etc.)
2. Extract **features** in the frequency domain, L/R correlation, phase, energy per band — the same cues the brain uses with **two ears**
3. Train a **scikit-learn** classifier to map these features to discrete **angles** (0°, 45°, …, 315°) and use **intensity** as a proxy for **"how close"** on the radar

When the game is in **headphones with spatialization**, what usually arrives at the cable is **stereo already processed** by something equivalent to **HRTF** (*Head-Related Transfer Function*). So: it's **not** necessary to decode 7.1 channel by channel; the model learns patterns in the **L/R pair** that the game + HRTF already conditioned to direction.

The `radar_surround.py` script is the **heuristic / multichannel** variant (surround when the device has 6+ inputs). The recommended flow for the "stereo + HRTF + ML" design is **`collector.py` → `train.py` → `radar_ml.py`**.

---

## Roadmap

1. **Current phase — acoustic radar**
   Indicate **direction** and **relative visual distance** (radius on radar) relative to the player, based on sound events (e.g. footsteps).

2. **Desired evolution**
   Move toward an **acoustic "wallhack"**: keep on the map/screen the **last estimated position** (or recent trail) derived from noise, not just a momentary ping.

*(Phase 2 depends on minimap/world space integration; the repository today delivers the detection + angle + radar UI core.)*

---

## Prerequisites

- **Python 3.10+** (3.11 or 3.12 recommended on Windows)
- **VB-Audio Virtual Cable** (or equivalent): game sends audio to the cable; Python **records** from it as input
- On Windows: game output → **CABLE Input**; the Python app uses **CABLE Output** as **microphone input** (names may vary slightly — the code looks for devices whose name contains `"CABLE"`)

---

## Audio Device Setup

You need a **7.1 audio device** set as your primary speaker. If your sound card or headphones don't support it natively, use a virtual audio device instead.

> **Inspired by / reference:** [CanetisRadar by SamuelTulach](https://github.com/SamuelTulach/CanetisRadar)

### Option 1 — Use your existing device
Check if your sound card or headphones already support 7.1 surround. If yes, skip to the main setup.

### Option 2 — Virtual audio device (recommended)

1. Download **[VB-Cable](https://www.vb-audio.com/Cable/)** (or the better alternative: **[Razer Surround](https://www.razer.com/surround)**)
2. Install it
3. Reboot your PC
4. Open **Sound Settings → Playback tab**
5. Set **CABLE Input** as default device
6. Click **Configure** → set to **7.1 Surround** and enable all speakers
7. Go to **Recording tab**
8. Click on **CABLE Output** → **Properties → Listen tab**
9. Check **"Listen to this device"**
10. Set your normal playback device (your actual headphones/speakers)
11. Done — game audio will now route through the virtual 7.1 device

---

## Windows Setup

1. **Install Python** at [python.org](https://www.python.org/downloads/) — check **"Add python.exe to PATH"**

2. **Virtual environment** (recommended), in the project folder:
```powershell
   cd C:\path\to\acoustic-esp
   python -m venv .venv
   .\.venv\Scripts\activate
```

3. **Dependencies**:
```powershell
   pip install -r requiriments.txt
```

4. **PyAudio on Windows** — if `pip install PyAudio` fails:
   - Use an [unofficial wheel compatible with your Python version](https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio), or
   - `pip install pipwin` then `pipwin install pyaudio`

5. **Tkinter** — usually bundled with the official Python installer. If missing, reinstall with the **tcl/tk** component checked.

---

## How to Run (Main Flow)

| Step | Command | What it does |
|------|---------|--------------|
| 1. Collect data | `python collector.py` | Opens UI, records `samples.csv` when you press **numpad keys** as you hear a footstep in the indicated direction |
| 2. Train model | `python train.py` | Reads `samples.csv`, trains and saves `model.pkl` |
| 3. Live radar | `python radar_ml.py` | Uses `model.pkl` + stereo audio from cable; shows pings on radar |

**Optional:** `python radar_surround.py` — radar **without trained model**, with **surround** logic when the device has 6+ channels.

---

## Important Files

| File | Purpose |
|------|---------|
| `collector.py` | Labeled collection → `samples.csv` |
| `train.py` | Training → `model.pkl` |
| `radar_ml.py` | Radar with **ML** (stereo + `model.pkl`) — main use |
| `radar_surround.py` | **Heuristic** / multichannel radar (surround if available) |
| `requiriments.txt` | `pip` dependencies |
| `demonstration.mp4` | Demo video |

---

## Ethical & Usage Note

Using any tool that alters competitive advantage in **online games** may violate the game's **terms of service** and result in a ban. This README describes the project for technical transparency; responsibility for use is yours.

---

---

# 🇧🇷 Acoustic ESP — Radar Acústico (PT-BR)

---

## Demonstração

Vídeo de exemplo na raiz do repositório: [`demonstration.mp4`](demonstration.mp4)

<video src="demonstration.mp4" controls playsinline width="100%"></video>

---

## Guia rápido

| Arquivo | Use quando… |
|---------|-------------|
| `collector.py` | Quiser **gravar treino**: rotular passos por direção → gera `samples.csv` |
| `train.py` | Já tiver amostras e quiser gerar **`model.pkl`** |
| **`radar_ml.py`** | **Radar principal**: estéreo + **modelo ML** (`model.pkl`) |
| **`radar_surround.py`** | Quiser testar **radar sem ML**, por **vários canais** (5.1/7.1) quando o driver expõe surround |

### Prints

| Collector UI | Demo em jogo |
|---|---|
| ![Collector UI](prints/collector-ui.png) | ![In-game Demo](prints/in-game-demo-ui.png) |

---

## Visão geral

Projeto de **radar acústico**: estimar **direção (ângulo)** e **distância relativa** ao jogador a partir do som capturado (ex.: passos), usando **estéreo + aprendizado de máquina**, em vez de depender de **8 canais crus de surround 7.1**.

---

## Intuito e diferença em relação a "ESP por 7.1"

Muitas abordagens tentam ler **cada alto-falante virtual** do mix **7.1** (FL, FR, RL, RR, etc.) para saber de onde veio o som. Esse repositório **não** é focado nesse caminho.

O fluxo principal aqui é:

1. Capturar um sinal **estéreo** (esquerda/direita), por exemplo o que sai do jogo já roteado para um **cabo virtual** (VB-Audio Cable, etc.)
2. Extrair **features** no domínio da frequência, correlação L/R, fase, energia por banda — o mesmo tipo de pistas que o cérebro usa com **duas orelhas**
3. Treinar um classificador (**scikit-learn**) para mapear essas features para **ângulos** discretos (0°, 45°, …, 315°) e usar a **intensidade** como proxy de **"quão perto"** no radar

Quando o jogo está em **fone com espacialização**, o que costuma chegar no cabo é **estéreo já processado** por algo equivalente a **HRTF** (*Head-Related Transfer Function* — filtros e atrasos que simulam como o som chega a cada ouvido). Ou seja: **não** é necessário decodificar 7.1 canal a canal; o modelo aprende padrões no **par L/R** que o próprio jogo + HRTF já condicionaram à direção.

O script `radar_surround.py` é a variante **heurística / multicanal**. O fluxo recomendado é **`collector.py` → `train.py` → `radar_ml.py`**.

---

## Roadmap

1. **Fase atual — radar acústico**
   Indicar **direção** e **distância visual relativa** (raio no radar) em relação ao jogador, com base em eventos sonoros (ex.: passos).

2. **Evolução desejada**
   Caminhar para um **"wallhack" acústico**: manter no mapa/tela a **última posição estimada** (ou trilha recente) derivada do barulho, não só um ping momentâneo.

*(Fase 2 depende de integração com minimapa/world space.)*

---

## Pré-requisitos

- **Python 3.10+** (recomendado 3.11 ou 3.12 no Windows)
- **VB-Audio Virtual Cable** (ou equivalente)
- No Windows: saída do jogo → **CABLE Input**; o app Python usa **CABLE Output** como **microfone de entrada**

---


## Configuração do dispositivo de áudio

É necessário um **dispositivo de áudio 7.1** configurado como saída principal. Se sua placa de som ou fone não suportar nativamente, use um dispositivo virtual.

> **Referência / inspiração:** [CanetisRadar by SamuelTulach](https://github.com/SamuelTulach/CanetisRadar)

### Opção 1 — Usar seu dispositivo atual
Verifique se sua placa de som ou headset já suporta surround 7.1. Se sim, pule para o setup principal.

### Opção 2 — Dispositivo virtual (recomendado)

1. Baixe o **[VB-Cable](https://www.vb-audio.com/Cable/)** (alternativa melhor: **[Razer Surround](https://www.razer.com/surround)**)
2. Instale
3. Reinicie o PC
4. Abra **Configurações de Som → aba Reprodução**
5. Defina **CABLE Input** como dispositivo padrão
6. Clique em **Configurar** → selecione **Surround 7.1** e habilite todos os alto-falantes
7. Vá para a **aba Gravação**
8. Clique em **CABLE Output** → **Propriedades → aba Ouvir**
9. Marque **"Ouvir este dispositivo"**
10. Selecione seu dispositivo de reprodução normal (fone/caixas reais)
11. Pronto — o áudio do jogo agora passa pelo dispositivo 7.1 virtual

---

## Setup no Windows

1. **Instale o Python** em [python.org](https://www.python.org/downloads/) — marque **"Add python.exe to PATH"**

2. **Ambiente virtual**:
```powershell
   cd C:\caminho\para\acoustic-esp
   python -m venv .venv
   .\.venv\Scripts\activate
```

3. **Dependências**:
```powershell
   pip install -r requiriments.txt
```

4. **PyAudio no Windows** — se `pip install PyAudio` falhar:
   - Wheel não oficial: [lfd.uci.edu/~gohlke/pythonlibs/#pyaudio](https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio), ou
   - `pip install pipwin` → `pipwin install pyaudio`

6. **Tkinter** — vem com o instalador oficial. Se faltar, reinstale marcando **tcl/tk**

---

## Como rodar

| Etapa | Comando | O que faz |
|-------|---------|-----------|
| 1. Coletar dados | `python collector.py` | Abre a UI, grava `samples.csv` ao pressionar as teclas do **numpad** |
| 2. Treinar modelo | `python train.py` | Lê `samples.csv`, treina e grava `model.pkl` |
| 3. Radar em tempo real | `python radar_ml.py` | Usa `model.pkl` + áudio estéreo do cabo; mostra pings no radar |

**Opcional:** `python radar_surround.py` — radar sem modelo, com lógica surround.

---

## Arquivos importantes

| Arquivo | Função |
|---------|--------|
| `collector.py` | Coleta rotulada → `samples.csv` |
| `train.py` | Treino → `model.pkl` |
| `radar_ml.py` | Radar com **ML** — uso principal |
| `radar_surround.py` | Radar heurístico / multicanal |
| `requiriments.txt` | Dependências `pip` |
| `demonstration.mp4` | Vídeo de demonstração |

---

## Nota ética e de uso

Usar qualquer ferramenta que altere vantagem competitiva em **jogos online** pode violar os **termos de serviço** do jogo e resultar em banimento. A responsabilidade pelo uso é sua.