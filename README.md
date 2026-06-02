# LPR Clube — Reconhecimento de Placas via RTSP

Sistema que recebe o vídeo de **uma ou mais câmeras** por **RTSP**, identifica **placas de
veículos** (formato antigo `ABC-1234` e Mercosul `ABC1D23`) e **registra a câmera + a placa +
o momento da leitura**. Cada câmera roda em sua própria thread.

Para cada placa reconhecida o sistema: **grava** em arquivo de texto, **consulta uma API de
autorização** (placa + horário) e, conforme a resposta, **aciona um pino GPIO** do Raspberry Pi
(ex.: abrir um portão). Projetado para rodar **no próprio Raspberry Pi**.

Reconhecimento 100% **local** (sem nuvem) usando [`fast-alpr`](https://github.com/ankandrew/fast-alpr)
(detector YOLO + OCR ONNX), rodando em **CPU**.

## Como funciona

```
cada câmera (thread):
  RTSP → captura (frame skipping) → fast-alpr (detecção + OCR)
       → filtro de confiança → validação formato BR → dedupe por tempo
       → grava no arquivo → consulta API de autorização → se autorizado, aciona GPIO
```

A confiabilidade vem de três camadas: confiança mínima do OCR, validação do formato de placa
brasileira e deduplicação por janela de tempo (mesma placa não é regravada por X segundos).

**Pré-processamento (contra farol/glare):** antes do reconhecimento, cada frame passa por
conversão para tons de cinza + **CLAHE** (equalização adaptativa de contraste, recupera detalhe
em áreas estouradas) e correção de gamma opcional. Tudo configurável na seção `preprocess` do
`config.yaml`. O resultado é mantido em 3 canais (exigência do detector YOLO).

**Multi-câmera:** todas as câmeras compartilham um único motor de reconhecimento (a inferência
é serializada por lock, pois em CPU rodar dois `predict()` ao mesmo tempo apenas sobrecarrega os
núcleos) e os mesmos sinks (escrita thread-safe). A deduplicação é **independente por câmera**.

## Requisitos

- **Python 3.10+** (testado com 3.14).
- Conexão de rede com a(s) câmera(s) RTSP.
- Para o acionamento físico: **Raspberry Pi** com Raspberry Pi OS (as libs de GPIO são
  instaladas só no Linux). Em outros sistemas, o GPIO é apenas **simulado** (log).

## Instalação

```bash
python -m pip install -r requirements.txt
```

> No primeiro uso, o `fast-alpr` baixa os modelos ONNX automaticamente.
> As dependências de GPIO (`gpiozero`, `lgpio`) só são instaladas em Linux/Raspberry Pi.

## Configuração

Edite o `config.yaml`:

```yaml
cameras:
  - name: "entrada"
    source: "rtsp://usuario:senha@ip:554/stream"   # ou um caminho .mp4 para testar
  - name: "saida"
    source: "rtsp://usuario:senha@ip2:554/stream"
frame_skip: 5            # processa 1 a cada N frames (alivia a CPU)
min_confidence: 0.80     # confiança mínima do OCR
dedup_window_seconds: 30 # mesma placa não é regravada antes disso
validate_br_format: true # só registra placas BR válidas
sinks:
  file:
    enabled: true
    path: "output/placas.txt"
api:
  enabled: false
  url: "https://exemplo/api/acesso"
  timeout: 5
  api_key: ""              # vai no header Authorization: Bearer <api_key>
  auth_field: "autorizado" # campo da resposta que decide (vazio = só HTTP 2xx)
  auth_value: true         # valor que significa "liberar"
gpio:
  enabled: false           # requer api.enabled: true
  pin: 17                  # pino BCM
  active_high: true        # nível que aciona o relé/portão
  pulse_seconds: 2         # tempo acionado por liberação
```

## Execução

```powershell
python run.py
```

Saída em `output/placas.txt` (inclui o nome da câmera):

```
2026-06-01T15:30:12 | entrada | ABC1D23 | conf=0.94
```

Encerre com `Ctrl+C`.

## Testar sem câmera

Aponte `source` para um arquivo `.mp4` com placas e rode `python run.py`.
Confirme que `output/placas.txt` recebe as leituras e que repetições dentro da janela
não são regravadas.

## API de autorização + GPIO

Quando `api.enabled: true`, cada placa reconhecida gera um `POST` para `api.url`:

```json
{ "placa": "ABC1D23", "camera": "entrada", "momento": "2026-06-01T15:30:12" }
```

A resposta decide a liberação:
- Se `auth_field` estiver preenchido (ex.: `"autorizado"`), libera quando
  `resposta[auth_field] == auth_value`.
- Se `auth_field` estiver vazio, libera com base apenas no status **HTTP 2xx**.
- Falha de rede/timeout → **nega** por segurança (não trava o pipeline).

Quando o acesso é **autorizado** e `gpio.enabled: true`, o pino BCM configurado é acionado por
`pulse_seconds` segundos (ex.: pulso para abrir um portão/relé). `Authorization: Bearer <api_key>`
é enviado se `api_key` estiver preenchido.

### Rodando no Raspberry Pi

```bash
sudo apt install python3-venv
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # instala também gpiozero + lgpio
python run.py
```

> **Fiação:** o pino BCM do `config.yaml` normalmente vai a um **módulo relé** que comanda o
> portão (não ligue o motor direto no GPIO). Ajuste `active_high` ao tipo de relé (muitos são
> acionados em nível baixo → `active_high: false`).

Fora do Raspberry Pi (ex.: Windows de desenvolvimento), o acionamento é **simulado** e apenas
registrado no log — útil para testar a integração com a API sem hardware.

## Testes

```powershell
python -m pip install pytest
python -m pytest tests/ -v
```

## Estrutura

```
config.yaml            # configuração
run.py                 # ponto de entrada
src/
  main.py              # orquestra as câmeras (uma thread por câmera) + shutdown
  worker.py            # CameraWorker: pipeline de uma câmera (lê → grava → autoriza → GPIO)
  config.py            # carga/validação do config.yaml (câmeras, api, gpio)
  stream.py            # captura RTSP + frame skipping + reconexão
  recognizer.py        # wrapper do fast-alpr + filtro de confiança (thread-safe)
  plate_validator.py   # regex BR (antiga/Mercosul) + normalização
  dedupe.py            # deduplicação por janela de tempo (por câmera)
  preprocess.py        # melhora a imagem (cinza + CLAHE + gamma) contra farol/glare
  sinks.py             # FileSink: registro das leituras em arquivo (thread-safe)
  authorizer.py        # cliente da API de autorização + interpretação da resposta
  gpio.py              # acionamento do GPIO (gpiozero) com fallback simulado
tests/
  test_plate_validator.py
  test_config.py
  test_authorizer.py
  test_preprocess.py
```
