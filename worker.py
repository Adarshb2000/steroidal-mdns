import docker
import requests
import subprocess
import socket
import time
import re
import syslog
import sys
import os

# --- CONFIGURATION ---
NPM_URL = os.getenv('NPM_URL', 'http://localhost:81')  # e.g., http://npm-container:81 if in Docker
NPM_USERNAME = os.getenv('NPM_USERNAME', 'your@email.com')
NPM_PASSWORD = os.getenv('NPM_PASSWORD', 'yourpassword')
LOG_TAG = "steroidal-mdns"
HOSTNAME = subprocess.check_output(['hostname', '-s']).decode().strip()

# --- LOGGING HELPER ---
def logger(msg, is_error=False):
    """
    Writes to syslog so it appears in journalctl -t steroidal-mdns
    Also prints to stdout/stderr for manual debugging.
    """
    # Initialize syslog with our custom tag
    syslog.openlog(ident=LOG_TAG, logoption=syslog.LOG_PID, facility=syslog.LOG_USER)
    
    priority = syslog.LOG_ERR if is_error else syslog.LOG_INFO
    syslog.syslog(priority, msg)
    
    # Optional: Also print to console if running manually
    if is_error:
        print(f"ERROR: {msg}", file=sys.stderr)
    else:
        print(msg)

# --- NETWORK HELPERS ---

def get_lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def nuke_old_publishers():
    logger("Nuking old avahi-publish processes...")
    subprocess.run(['pkill', '-f', 'avahi-publish -a'], stderr=subprocess.DEVNULL)
    time.sleep(1)

def spawn_publisher(hostname, ip):
    cmd = ['avahi-publish', '-a', '-R', hostname, ip]
    
    try:
        subprocess.Popen(
            cmd, 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        logger(f"Spawned publisher: {hostname} -> {ip}")
    except Exception as e:
        logger(f"Failed to spawn publisher for {hostname}: {e}", is_error=True)

# --- API HELPERS ---

def get_npm_token():
    try:
        resp = requests.post(f"{NPM_URL}/api/tokens", json={"identity": NPM_USERNAME, "secret": NPM_PASSWORD})
        resp.raise_for_status()
        return resp.json()['token']
    except Exception as e:
        logger(f"Failed to login to NPM: {e}", is_error=True)
        return None

def get_container_mappings():
    try:
        client = docker.from_env()
        container_map = []
        
        for container in client.containers.list():
            ports = container.attrs['NetworkSettings']['Ports']
            if not ports:
                continue
                
            container_name = container.name
            clean_name = re.sub(r'[^a-zA-Z0-9-]', '', container_name)
            
            exposed_ports = []
            for port_proto, host_bindings in ports.items():
                if host_bindings:
                    exposed_ports.append(int(host_bindings[0]['HostPort']))
            
            exposed_ports.sort()
            
            for i, port in enumerate(exposed_ports):
                suffix = f"_{i}" if i > 0 else ""
                hostname_full = f"{clean_name}{suffix}.{HOSTNAME}.local"
                
                container_map.append({
                    "hostname": hostname_full,
                    "port": port,
                    "container": container_name
                })
        return container_map
    except Exception as e:
        logger(f"Docker API Error: {e}", is_error=True)
        raise e

def update_npm(token, mappings):
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        hosts = requests.get(f"{NPM_URL}/api/nginx/proxy-hosts", headers=headers).json()
    except Exception as e:
        logger(f"Failed to fetch NPM hosts: {e}", is_error=True)
        return

    existing_local_hosts = {h['domain_names'][0]: h for h in hosts if '.local' in h['domain_names'][0]}

    for m in mappings:
        domain = m['hostname']
        forward_port = m['port']
        
        payload = {
            "domain_names": [domain],
            "forward_scheme": "http",
            "forward_host": 'localhost',
            "forward_port": forward_port,
            "access_list_id": "0",
            "certificate_id": 0,
            "meta": {"letsencrypt_agree": False, "dns_challenge": False},
            "advanced_config": "",
            "locations": [],
            "block_exploits": False,
            "caching_enabled": False,
            "allow_websocket_upgrade": True,
            "http2_support": False,
            "hsts_enabled": False,
            "hsts_subdomains": False,
            "ssl_forced": False
        }

        if domain in existing_local_hosts:
            current = existing_local_hosts[domain]
            if (str(current['forward_port']) != str(forward_port)) or (current['forward_host'] != 'localhost'):
                logger(f"NPM: Updating {domain} (Configuration Changed)")
                requests.put(f"{NPM_URL}/api/nginx/proxy-hosts/{current['id']}", headers=headers, json=payload)
            else:
                # Verbose logging can be commented out if it gets too noisy
                logger(f"NPM: Skipping {domain} (No Change)")
        else:
            logger(f"NPM: Creating {domain}")
            requests.post(f"{NPM_URL}/api/nginx/proxy-hosts", headers=headers, json=payload)

# --- MAIN ---

if __name__ == "__main__":
    logger("--- Steroidal mDNS Sync Started ---")
    
    current_ip = get_lan_ip()
    logger(f"Detected LAN IP: {current_ip}")
    
    nuke_old_publishers()
    
    try:
        mappings = get_container_mappings()
        
        # Spawn publishers
        for m in mappings:
            spawn_publisher(m['hostname'], current_ip)

        # Update NPM
        token = get_npm_token()
        if token:
            update_npm(token, mappings)
            
    except Exception as e:
        logger(f"Critical Failure: {e}", is_error=True)
        sys.exit(1)
    
    logger("--- Sync Complete ---")