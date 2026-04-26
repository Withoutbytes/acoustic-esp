# Acoustic ESP — radar acústico

## Guia rápido (só de olhar nos nomes)

| Arquivo | Use quando… |
|---------|----------------|
| `collector.py` | Quiser **gravar treino**: rotular passos por direção → gera `samples.csv`. |
| `train.py` | Já tiver amostras e quiser gerar **`model.pkl`**. |
| **`radar_ml.py`** | Quiser o **radar principal**: estéreo + **modelo ML** (`model.pkl`). |
| **`radar_surround.py`** | Quiser testar **radar sem ML**, por **vários canais** (5.1/7.1) quando o driver expõe surround. |

Projeto de **radar acústico**: estimar **direção (ângulo)** e **distância relativa** ao jogador a partir do som capturado (ex.: passos), usando **estéreo + aprendizado de máquina**, em vez de depender de **8 canais crus de surround 7.1**.

---

## Intuito e diferença em relação a “ESP por 7.1”

Muitas abordagens tentam ler **cada alto-falante virtual** do mix **7.1** (FL, FR, RL, RR, etc.) para saber de onde veio o som. Esse repositório **não** é o foco principal desse caminho.

Aqui o fluxo principal é:

1. Capturar um sinal **estéreo** (esquerda/direita), por exemplo o que sai do jogo já roteado para um **cabo virtual** (VB-Audio Cable, etc.).
2. Extrair **features** no domínio da frequência, correlação L/R, fase, energia por banda — o mesmo tipo de pistas que o cérebro usa com **duas orelhas**.
3. Treinar um classificador (**scikit-learn**) para mapear essas features para **ângulos** discretos (0°, 45°, …, 315°) e usar a **intensidade** como proxy de **“quão perto”** no radar.

Quando o jogo está em **fone com espacialização**, o que costuma chegar no cabo é **estéreo já processado** por algo equivalente a **HRTF** (*Head-Related Transfer Function* — função de transferência relacionada à cabeça: filtros e atrasos que simulam como o som chega a cada ouvido). Ou seja: **não** é necessário decodificar 7.1 canal a canal; o modelo aprende padrões no **par L/R** que o próprio jogo + HRTF já condicionaram à direção.

O script **`radar_surround.py`** é a variante **heurística / multicanal** (surround quando o dispositivo tem 6+ entradas). O fluxo recomendado para o desenho “estéreo + HRTF + ML” é **`collector.py` → `train.py` → `radar_ml.py`**.

---

## Objetivos (roadmap)

1. **Fase atual — radar acústico**  
   Indicar no plano 2D **direção** e uma **distância visual relativa** (raio no radar) em relação ao jogador, com base em eventos sonoros (ex.: passos).

2. **Evolução desejada**  
   Caminhar para um **“wallhack” acústico**: manter no mapa/tela a **última posição estimada** (ou trilha recente) derivada do barulho, não só um ping momentâneo.

*(Implementação da fase 2 depende de integração com minimapa/world space; o repositório hoje entrega o núcleo de detecção + ângulo + UI de radar.)*

---

## Pré-requisitos

- **Python 3.10+** (recomendado 3.11 ou 3.12 no Windows).
- **VB-Audio Virtual Cable** (ou equivalente): o jogo envia o áudio para o cabo; o Python **grava** desse cabo como entrada.
- No Windows: saída do jogo → **CABLE Input**; o app Python usa **CABLE Output** como **microfone de entrada** (nomes podem variar levemente — o código procura dispositivos cujo nome contenha `"CABLE"`).

---

## Setup no Windows

1. **Instale o Python** em [python.org](https://www.python.org/downloads/) e marque **“Add python.exe to PATH”**.

2. **Ambiente virtual** (recomendado), na pasta do projeto:

   ```powershell
   cd C:\caminho\para\acoustic-esp
   python -m venv .venv
   .\.venv\Scripts\activate
   ```

3. **Dependências**:

   ```powershell
   pip install -r requiriments.txt
   ```

4. **PyAudio no Windows**  
   Se `pip install PyAudio` falhar, use um dos caminhos comuns:
   - Instalar de [wheel não oficial compatível com sua versão do Python](https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio) (baixar o `.whl` certo e `pip install arquivo.whl`), ou  
   - `pip install pipwin` e depois `pipwin install pyaudio`  
   Em muitos casos o `pip install` direto já funciona em Python recente.

5. **VB-Audio Cable**  
   - Baixe em [vb-audio.com](https://vb-audio.com/Cable/) e instale.  
   - No Windows: **Configurações → Som** (ou mixer do jogo): saída do jogo = **CABLE Input**.  
   - Confirme que **CABLE Output** aparece como dispositivo de **entrada** e que o volume não está mutado.

6. **Tkinter**  
   Geralmente vem com o instalador oficial do Python. Se faltar, no instalador marque **tcl/tk** ou reinstale com componente “Python Tkinter”.

---

## Como rodar o projeto (fluxo principal)

Ordem sugerida:

| Etapa | Comando | O que faz |
|--------|---------|-----------|
| 1. Coletar dados | `python collector.py` | Abre a UI, grava `samples.csv` quando você pressiona as teclas do **numpad** no momento em que ouve o passo na direção indicada. |
| 2. Treinar modelo | `python train.py` | Lê `samples.csv`, treina e grava `model.pkl`. |
| 3. Radar em tempo real | `python radar_ml.py` | Usa `model.pkl` + áudio estéreo do cabo; mostra pings no radar. |

**Opcional:** `python radar_surround.py` — radar **sem modelo treinado**, com lógica de **surround** quando o dispositivo tem 6+ canais; útil para comparar com o `radar_ml.py`.

---

## Arquivos importantes

| Arquivo | Função |
|---------|--------|
| `collector.py` | Coleta rotulada → `samples.csv` |
| `train.py` | Treino → `model.pkl` |
| `radar_ml.py` | Radar com **ML** (estéreo + `model.pkl`) — uso principal |
| `radar_surround.py` | Radar **heurístico** / multicanal (surround se disponível) |
| `requiriments.txt` | Dependências `pip` |

---

## Nota ética e de uso

Usar qualquer ferramenta que altere vantagem competitiva em **jogos online** pode violar os **termos de serviço** do jogo e resultar em banimento. Este README descreve o projeto por transparência técnica; a responsabilidade pelo uso é sua.
