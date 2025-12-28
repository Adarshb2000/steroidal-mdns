# Steroidal mDNS 💉

**Zero-Config Local DNS & Reverse Proxy Automation for Docker**

**Steroidal mDNS** turns your Linux machine into a portable, self-configuring server. When you join a new network (WiFi or Ethernet), it automatically detects your running Docker containers, broadcasts them as `.local` domains (mDNS), and configures **Nginx Proxy Manager** to route traffic to them.

No more static IPs. No more editing `/etc/hosts`. No more "Bad Gateway" errors when your laptop's IP changes.

---

## 🚀 Why Use This?

If you run a Homelab on a laptop, a Raspberry Pi that moves around, or a development server on a dynamic DHCP network, you know the pain:

1.  **The IP Problem:** Your server's IP changes from `192.168.1.10` to `192.168.1.50`.
2.  **The Access Problem:** Your hardcoded bookmarks and reverse proxy configs break.
3.  **The Fix:** You have to manually update Nginx, edit DNS, or mess with router reservations.

**Steroidal mDNS solves this.** It runs in the background, detects network changes, and updates the entire chain (mDNS + Nginx) in seconds.

## ✨ Features

* **⚡ Network Agnostic:** Works flawlessly on WiFi, Ethernet, or VPNs. Triggers automatically on DHCP renewal.
* **🐳 Docker Native:** Scans the Docker socket for exposed ports.
* **🔄 Idempotent:** Uses a "Clean Slate" architecture. It wipes stale mDNS publishers and respawns them, preventing zombie processes.
* **🔒 Secure:** Runs locally. Uses strict Python Virtual Environments (`venv`) to respect system package managers (PEP 668 compliant).
* **📦 Portable:** Moving your server to a friend's house? Just plug it in. Your services are available at `plex.myserver.local` instantly.

---

## 🛠️ Architecture

1.  **Trigger:** NetworkManager detects a connection change (`dhcp4-change` or `up`).
2.  **Dispatch:** It launches the `run.sh` wrapper script.
3.  **Logic (Python):**
    * Detects the new LAN IP.
    * Scans Docker for containers with exposed ports.
    * Generates hostnames: `container_name.hostname.local`.
4.  **Action:**
    * **mDNS:** Spawns `avahi-publish` processes to broadcast the domains.
    * **NPM:** Pushes the new IP/Port configuration to Nginx Proxy Manager via API.

---

## 📦 Installation

### Prerequisites
* **Linux OS** (Ubuntu, Debian, Fedora, Raspbian).
* **Docker** installed and running.
* **Nginx Proxy Manager** (NPM) running.
    * *Note: NPM should run in `network_mode: host` for best results.*

### Option 1: The One-Click Installer (Recommended)

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/yourusername/steroidal-mdns.git](https://github.com/yourusername/steroidal-mdns.git)
    cd steroidal-mdns
    ```

2.  **Run the installer:**
    ```bash
    sudo ./install.sh
    ```

3.  **Configure:**
    The script will ask for your NPM URL and Credentials. Press `Enter` to accept defaults.
    ```text
    NPM URL [http://localhost:81]: 
    NPM Admin Email [admin@example.com]: 
    NPM Admin Password [changeme]: 
    ```

*The installer handles everything: creating the virtual environment, installing Python dependencies, creating the wrapper scripts, and hooking into NetworkManager.*

### Option 2: Manual Installation

<details>
<summary>Click to view manual steps</summary>

1.  **Install Dependencies:**
    ```bash
    sudo apt install python3-venv network-manager avahi-utils
    ```

2.  **Create Directory & vEnv:**
    ```bash
    sudo mkdir -p /opt/steroidal-mdns
    sudo python3 -m venv /opt/steroidal-mdns/venv
    ```

3.  **Install Libraries:**
    ```bash
    sudo /opt/steroidal-mdns/venv/bin/pip install docker requests
    ```

4.  **Copy Files:**
    * Copy `worker.py` to `/opt/steroidal-mdns/`.
    * Create a `config.env` with your NPM credentials.
    * Create a `run.sh` wrapper to launch the python script using the vEnv.

5.  **Setup Dispatcher:**
    Create a script in `/etc/NetworkManager/dispatcher.d/` that calls your `run.sh`.
</details>

---

## 📋 Usage

### Automatic
Just use your computer! Whenever you switch networks, the system logs will show:
`steroidal-trigger: Network update on eth0. Running wrapper.`

### Manual Trigger
You can force a sync at any time:
```bash
sudo /opt/steroidal-mdns/run.sh
```

## Viewing Logs
To see what the script is doing in real-time:
```bash
journalctl -t steroidal-mdns -f
```

## 🔮 Roadmap & Improvements
Feel free to contribute! Here are some ideas for "Steroidal mDNS v2":
- Docker Event Listeners: Instead of running only on network change, the script should listen to docker events. If a new container starts, it should instantly get a domain without waiting for a network trigger.
- Traefik/Caddy Support: Abstract the Proxy Updater logic to support other reverse proxies.
- Config UI: A simple web interface to "exclude" certain containers or rename their generated domains.
- Notification Support: Send a Discord/Telegram webhook when the server IP changes and new domains are published.
