#!/bin/bash

# Standard colors
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo -e "${GREEN}--- Steroidal mDNS Installer ---${NC}"

# 1. Check Root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (sudo ./install.sh)"
  exit
fi

# 2. Gather Configuration with Defaults
# Syntax: ${VAR:-default} uses 'default' if VAR is unset or null.

read -p "NPM URL [http://localhost:81]: " INPUT_URL
NPM_URL=${INPUT_URL:-http://localhost:81}

read -p "NPM Admin Email [admin@example.com]: " INPUT_USER
NPM_USER=${INPUT_USER:-admin@example.com}

# -s hides input for password
read -s -p "NPM Admin Password [changeme]: " INPUT_PASS
echo "" # Add newline since -s suppresses it
NPM_PASS=${INPUT_PASS:-changeme}

echo -e "\n----------------------------------------"
echo "Configuration to be used:"
echo "URL:  $NPM_URL"
echo "User: $NPM_USER"
echo "Pass: ******"
echo "----------------------------------------"

# 3. Install System Dependencies
echo -e "\n${GREEN}[+] Installing System Dependencies...${NC}"
apt-get update -qq
apt-get install -y python3 python3-pip python3-venv network-manager avahi-utils

# 4. Setup Directory & vEnv
INSTALL_DIR="/opt/steroidal-mdns"
VENV_DIR="$INSTALL_DIR/venv"

echo -e "${GREEN}[+] Creating Directory & Virtual Environment...${NC}"
mkdir -p $INSTALL_DIR

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi

# 5. Install Python Libs
echo -e "${GREEN}[+] Installing Python Libraries...${NC}"
"$VENV_DIR/bin/pip" install --upgrade pip > /dev/null
"$VENV_DIR/bin/pip" install docker requests > /dev/null

# 6. Create config.env
echo -e "${GREEN}[+] Creating Config File...${NC}"
cat > "$INSTALL_DIR/config.env" <<EOF
NPM_URL=$NPM_URL
NPM_USERNAME=$NPM_USER
NPM_PASSWORD=$NPM_PASS
EOF
chmod 600 "$INSTALL_DIR/config.env"

# 7. Copy Worker Script
echo -e "${GREEN}[+] Copying Worker Script...${NC}"
if [ -f "worker.py" ]; then
    cp worker.py "$INSTALL_DIR/worker.py"
else
    echo "WARNING: worker.py not found. Please copy it manually to $INSTALL_DIR/worker.py"
fi

# 8. Create Wrapper Script (run.sh)
echo -e "${GREEN}[+] Creating Wrapper Script...${NC}"
RUN_SCRIPT="$INSTALL_DIR/run.sh"

cat > "$RUN_SCRIPT" <<EOF
#!/bin/bash
DIR="\$( cd "\$( dirname "\${BASH_SOURCE[0]}" )" && pwd )"

# Load config if exists
if [ -f "\$DIR/config.env" ]; then
    set -a
    source "\$DIR/config.env"
    set +a
fi

# Ensure Root
if [ "\$EUID" -ne 0 ]; then
  echo "Error: Must run as root."
  exit 1
fi

# Execute Worker via vEnv Python
exec "\$DIR/venv/bin/python3" "\$DIR/worker.py"
EOF

chmod +x "$RUN_SCRIPT"

# 9. Create Dispatcher
echo -e "${GREEN}[+] Configuring NetworkManager Trigger...${NC}"
DISPATCHER_PATH="/etc/NetworkManager/dispatcher.d/99-steroidal-trigger"

cat > "$DISPATCHER_PATH" <<EOF
#!/bin/bash
INTERFACE=\$1
STATUS=\$2

# Trigger on DHCP change or Interface Up
if [[ "\$STATUS" == "dhcp4-change" ]] || [[ "\$STATUS" == "up" ]]; then
    logger -t "steroidal-trigger" "Network update on \$INTERFACE. Running wrapper."
    $RUN_SCRIPT &
fi
EOF

chmod +x "$DISPATCHER_PATH"
chown root:root "$DISPATCHER_PATH"

echo -e "${GREEN}--- Installation Complete! ---${NC}"
echo "Manual Run: sudo $INSTALL_DIR/run.sh"
