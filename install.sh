#!/usr/bin/env bash
#
# Instalador do sistema LPR (reconhecimento de placas) para Raspberry Pi / Linux.
#
# O que faz:
#   1. Instala dependências de sistema (Python, git, ffmpeg, libs do OpenCV e GPIO).
#   2. Clona (ou atualiza) o repositório do GitHub.
#   3. Cria um ambiente virtual e instala as dependências Python.
#   4. (Opcional) Configura um serviço systemd para iniciar no boot.
#
# Uso:
#   chmod +x install.sh && ./install.sh           # instala em ~/lpr
#   chmod +x install.sh && ./install.sh /opt/lpr  # diretório personalizado
#   chmod +x install.sh && ./install.sh --service # instala + autostart no boot
#
# Download direto (sem clonar antes):
#   curl -fsSL https://raw.githubusercontent.com/GustAlvesG/lpr/main/install.sh | bash
#
# Se aparecer "Permission denied" ou "/usr/bin/env: bash\r: not found":
#   sed -i 's/\r//' install.sh && chmod +x install.sh && ./install.sh
#
set -euo pipefail

# Auto-corrige CRLF caso o arquivo venha do Windows sem o .gitattributes aplicado.
# Só age se o script foi chamado diretamente (não via pipe do curl).
if [ -f "$0" ] && file "$0" 2>/dev/null | grep -q CRLF; then
  sed -i 's/\r//' "$0"
  exec bash "$0" "$@"
fi

REPO_URL="https://github.com/GustAlvesG/lpr.git"

# ----- Argumentos -----
INSTALL_DIR="$HOME/lpr"
CREATE_SERVICE=false
for arg in "$@"; do
  case "$arg" in
    --service) CREATE_SERVICE=true ;;
    -h|--help)
      grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) INSTALL_DIR="$arg" ;;
  esac
done

log()  { printf '\033[1;32m[install]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[aviso]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[erro]\033[0m %s\n' "$*" >&2; exit 1; }

# ----- sudo (se não for root) -----
SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  command -v sudo >/dev/null 2>&1 || die "É preciso root ou sudo para instalar pacotes de sistema."
  SUDO="sudo"
fi

# ----- 1. Dependências de sistema -----
log "Instalando dependências de sistema (apt)..."
$SUDO apt-get update -qq
$SUDO apt-get install -y \
  git \
  python3 \
  python3-venv \
  python3-pip \
  python3-dev \
  ffmpeg \
  libgl1 \
  libglib2.0-0 \
  liblgpio1 || warn "liblgpio1 indisponível nesta distro — o pip instalará lgpio mesmo assim."

# ----- Checa versão do Python (>= 3.10) -----
PY_OK=$(python3 -c 'import sys; print(1 if sys.version_info >= (3,10) else 0)')
[ "$PY_OK" = "1" ] || die "Python 3.10+ é necessário (encontrado: $(python3 --version))."

# ----- 2. Clonar ou atualizar o repositório -----
if [ -d "$INSTALL_DIR/.git" ]; then
  log "Repositório já existe em $INSTALL_DIR — atualizando (git pull)..."
  git -C "$INSTALL_DIR" pull --ff-only
else
  [ -e "$INSTALL_DIR" ] && die "Caminho '$INSTALL_DIR' já existe mas não é um repositório git. Remova-o ou escolha outro diretório."
  log "Clonando $REPO_URL em $INSTALL_DIR..."
  git clone "$REPO_URL" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# ----- 3. Ambiente virtual + dependências Python -----
if [ ! -d ".venv" ]; then
  log "Criando ambiente virtual (.venv)..."
  python3 -m venv .venv
fi

log "Instalando dependências Python (pode demorar alguns minutos)..."
./.venv/bin/python -m pip install --upgrade pip --quiet
./.venv/bin/python -m pip install -r requirements.txt

# ----- Pré-carrega os modelos ONNX (evita delay no primeiro uso real) -----
log "Pré-baixando modelos ONNX do fast-alpr..."
./.venv/bin/python - <<'PY'
from src.recognizer import PlateRecognizer
PlateRecognizer(
    detector_model="yolo-v9-t-384-license-plate-end2end",
    ocr_model="cct-xs-v2-global-model",
    min_confidence=0.8,
)
print("Modelos prontos.")
PY

# ----- 4. Serviço systemd (opcional) -----
if [ "$CREATE_SERVICE" = true ]; then
  SERVICE_NAME="lpr"
  RUN_USER="$(id -un)"
  log "Criando serviço systemd '$SERVICE_NAME' (usuário: $RUN_USER)..."
  $SUDO tee "/etc/systemd/system/${SERVICE_NAME}.service" >/dev/null <<EOF
[Unit]
Description=LPR - Reconhecimento de Placas
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${RUN_USER}
WorkingDirectory=${INSTALL_DIR}
ExecStart=${INSTALL_DIR}/.venv/bin/python ${INSTALL_DIR}/run.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
  $SUDO systemctl daemon-reload
  $SUDO systemctl enable "${SERVICE_NAME}.service"
  log "Serviço habilitado. Para iniciar agora: sudo systemctl start ${SERVICE_NAME}"
  log "Acompanhar logs:                         journalctl -u ${SERVICE_NAME} -f"
fi

# ----- Conclusão -----
echo
log "Instalação concluída em: $INSTALL_DIR"
echo
echo "  Próximos passos:"
echo "  1. Edite a configuração:  nano $INSTALL_DIR/config.yaml"
echo "  2. Execute o sistema:     cd $INSTALL_DIR && ./.venv/bin/python run.py"
if [ "$CREATE_SERVICE" != true ]; then
  echo
  echo "  Para iniciar no boot automaticamente, rode:"
  echo "    $INSTALL_DIR/install.sh --service"
fi
