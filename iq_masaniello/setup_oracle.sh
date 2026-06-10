#!/bin/bash
# setup_oracle.sh
# ===============
# Instala e configura o bot Masaniello na Oracle Cloud (Ubuntu 22.04 ARM)
# Uso: bash setup_oracle.sh

set -e
echo "=============================================="
echo "  SETUP BOT MASANIELLO — Oracle Cloud Ubuntu"
echo "=============================================="

# ── 1. Atualiza o sistema ──────────────────────────────────
echo "[1/7] Atualizando sistema..."
sudo apt-get update -qq && sudo apt-get upgrade -y -qq

# ── 2. Instala Python 3.11 + pip + screen ─────────────────
echo "[2/7] Instalando Python, pip, screen, git..."
sudo apt-get install -y -qq python3.11 python3.11-venv python3-pip \
     screen git curl wget unzip build-essential

# ── 3. Cria ambiente virtual ───────────────────────────────
echo "[3/7] Criando ambiente virtual Python..."
python3.11 -m venv ~/masaniello_env
source ~/masaniello_env/bin/activate

# ── 4. Instala dependências Python ────────────────────────
echo "[4/7] Instalando dependências Python..."
pip install --quiet --upgrade pip
pip install --quiet \
    iqoptionapi \
    pandas \
    numpy \
    requests \
    websocket-client \
    pyOpenSSL

echo "  ✅ Dependências instaladas."

# ── 5. Clona o repositório ────────────────────────────────
echo "[5/7] Clonando repositório..."
cd ~
if [ -d "CODEX" ]; then
    echo "  Repositório já existe. Atualizando..."
    cd CODEX && git pull
else
    # Substitua pela URL do seu repositório
    git clone https://github.com/henriquegomesdacosta14/CODEX.git
    cd CODEX
fi

cd iq_masaniello
echo "  ✅ Repositório pronto em ~/CODEX/iq_masaniello"

# ── 6. Cria o serviço systemd (roda como daemon 24/7) ─────
echo "[6/7] Configurando serviço systemd..."

# Cria arquivo de serviço
sudo tee /etc/systemd/system/masaniello.service > /dev/null << EOF
[Unit]
Description=Masaniello IQ Option Bot
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$HOME/CODEX/iq_masaniello
ExecStart=$HOME/masaniello_env/bin/python bot_confluencia.py
Restart=always
RestartSec=30
StandardOutput=append:$HOME/CODEX/iq_masaniello/bot_confluencia.log
StandardError=append:$HOME/CODEX/iq_masaniello/bot_confluencia.log
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable masaniello
echo "  ✅ Serviço systemd configurado."

# ── 7. Instrução final ────────────────────────────────────
echo ""
echo "=============================================="
echo "  INSTALAÇÃO CONCLUÍDA!"
echo "=============================================="
echo ""
echo "PRÓXIMOS PASSOS:"
echo ""
echo "1. Edite as credenciais:"
echo "   nano ~/CODEX/iq_masaniello/bot_confluencia.py"
echo "   → Altere: email, password, account_type"
echo ""
echo "2. Teste manualmente primeiro:"
echo "   source ~/masaniello_env/bin/activate"
echo "   cd ~/CODEX/iq_masaniello"
echo "   python bot_confluencia.py"
echo "   (Ctrl+C para parar)"
echo ""
echo "3. Quando estiver ok, inicie o serviço 24/7:"
echo "   sudo systemctl start masaniello"
echo "   sudo systemctl status masaniello"
echo ""
echo "COMANDOS ÚTEIS:"
echo "  Ver logs ao vivo:    tail -f ~/CODEX/iq_masaniello/bot_confluencia.log"
echo "  Parar o bot:         sudo systemctl stop masaniello"
echo "  Reiniciar o bot:     sudo systemctl restart masaniello"
echo "  Ver status:          sudo systemctl status masaniello"
echo "  Ver cofre:           cat ~/CODEX/iq_masaniello/cofre_confluencia.json"
echo ""
echo "=============================================="
