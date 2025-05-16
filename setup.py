#!/usr/bin/env python3
import subprocess
import time
import os

# Configuration
VCPUS = 4
MEMORY = 4096  # 4GB
DISK_SIZE = 8192  # 8GB
SNAPSHOT_TYPE = "computer-dev-04072025"
INSTANCE_ID = "morphvm_rvm78m7x"

def run(cmd, check=True, capture_output=False, shell=True):
    """Run a shell command."""
    print(f"Running: {cmd}")
    return subprocess.run(cmd, check=check, capture_output=capture_output, shell=shell, text=True)

def morph_exec(instance_id, command):
    """Run command on remote Morph Cloud instance."""
    full_cmd = f'morphcloud instance exec "{instance_id}" "{command}"'
    run(full_cmd)

def morph_copy(src, dest):
    """Copy file to Morph Cloud instance."""
    run(f'morphcloud instance copy {src} {dest}')

def setup_remote_desktop(instance_id):
    print("Setting up remote desktop environment...")

    # Step 1
    morph_exec(instance_id, "sudo DEBIAN_FRONTEND=noninteractive apt-get update -q && sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q python3")

    # Step 2
    morph_exec(instance_id, (
        "sudo DEBIAN_FRONTEND=noninteractive apt-get update -q && "
        "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q "
        "-o Dpkg::Options::=\"--force-confdef\" "
        "-o Dpkg::Options::=\"--force-confold\" "
        "xfce4 xfce4-goodies tigervnc-standalone-server tigervnc-common python3 python3-pip "
        "python3-websockify git net-tools nginx dbus dbus-x11 xfonts-base"
    ))

    # Step 3 (optional noVNC clone - commented in original)
    # morph_exec(instance_id, "sudo git clone https://github.com/novnc/noVNC.git /opt/noVNC")

    # Step 4
    morph_exec(instance_id, "sudo pkill Xvnc || true; sudo rm -f /tmp/.X1-lock /tmp/.X11-unix/X1 || true")

    # Step 5
    morph_exec(instance_id, "sudo mkdir -p /root/.config/xfce4 /root/.config/xfce4-session /root/.config/autostart /root/.config/systemd")

    # Step 6: VNC server service
    with open("/tmp/vncserver.service", "w") as f:
        f.write("""[Unit]
Description=VNC Server for X11
After=syslog.target network.target

[Service]
Type=simple
User=root
Environment=HOME=/root
Environment=DISPLAY=:1
ExecStartPre=-/bin/rm -f /tmp/.X1-lock /tmp/.X11-unix/X1
ExecStart=/usr/bin/Xvnc :1 -geometry 1280x800 -depth 24 -SecurityTypes None -localhost no
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
""")
    morph_copy("/tmp/vncserver.service", f"{instance_id}:/tmp/")
    morph_exec(instance_id, "sudo mv /tmp/vncserver.service /etc/systemd/system/")

    # Step 7: XFCE startup script
    with open("/tmp/start-xfce-session", "w") as f:
        f.write("""#!/bin/bash
export DISPLAY=:1
export HOME=/root
export XDG_CONFIG_HOME=/root/.config
export XDG_CACHE_HOME=/root/.cache
export XDG_DATA_HOME=/root/.local/share
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/dbus/system_bus_socket

if [ -z "$DBUS_SESSION_BUS_PID" ]; then
  eval $(dbus-launch --sh-syntax)
fi

/usr/lib/x86_64-linux-gnu/xfce4/xfconf/xfconfd &
sleep 2
exec startxfce4
""")
    morph_copy("/tmp/start-xfce-session", f"{instance_id}:/tmp/")
    morph_exec(instance_id, "sudo mv /tmp/start-xfce-session /usr/local/bin/ && sudo chmod +x /usr/local/bin/start-xfce-session")

    # Step 8: XFCE session service
    with open("/tmp/xfce-session.service", "w") as f:
        f.write("""[Unit]
Description=XFCE Session
After=vncserver.service dbus.service
Requires=vncserver.service dbus.service

[Service]
Type=simple
User=root
ExecStart=/usr/local/bin/start-xfce-session
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
""")
    morph_copy("/tmp/xfce-session.service", f"{instance_id}:/tmp/")
    morph_exec(instance_id, "sudo mv /tmp/xfce-session.service /etc/systemd/system/")

    # Step 9: noVNC service
    with open("/tmp/novnc.service", "w") as f:
        f.write("""[Unit]
Description=noVNC service
After=vncserver.service
Requires=vncserver.service

[Service]
Type=simple
User=root
ExecStart=/usr/bin/websockify --web=/opt/noVNC 6080 localhost:5901
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
""")
    morph_copy("/tmp/novnc.service", f"{instance_id}:/tmp/")
    morph_exec(instance_id, "sudo mv /tmp/novnc.service /etc/systemd/system/")

    # Step 10: Nginx config
    with open("/tmp/novnc-nginx", "w") as f:
        f.write("""server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://localhost:6080/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
""")
    morph_copy("/tmp/novnc-nginx", f"{instance_id}:/tmp/")
    morph_exec(instance_id, "sudo mv /tmp/novnc-nginx /etc/nginx/sites-available/novnc")

    # Step 11
    morph_exec(instance_id, "sudo ln -sf /etc/nginx/sites-available/novnc /etc/nginx/sites-enabled/novnc && sudo rm -f /etc/nginx/sites-enabled/default")

    # Step 12: Enable services
    for service in ["vncserver", "xfce-session", "novnc", "nginx"]:
        morph_exec(instance_id, f"sudo systemctl daemon-reload && sudo systemctl enable {service} && sudo systemctl restart {service}")

    # Step 13: Verify services
    for service in ["vncserver", "xfce-session", "novnc", "nginx"]:
        script_path = f"/tmp/check_{service}.sh"
        with open(script_path, "w") as f:
            f.write(f"""#!/bin/bash
for i in {{1..3}}; do
  if systemctl is-active {service} > /dev/null; then
    echo '{service} is running'
    break
  fi
  echo 'Waiting for {service} to start...'
  systemctl restart {service}
  sleep 3
done
""")
        morph_copy(script_path, f"{instance_id}:{script_path}")
        morph_exec(instance_id, f"chmod +x {script_path} && sudo {script_path}")

    # Step 14
    morph_exec(instance_id, f"morphcloud instance expose-http {instance_id} desktop 80")

    print("Waiting for services to fully start...")
    time.sleep(10)
    print("Remote desktop setup complete!")

# Main script
print("Starting setup for Remote Desktop on Morph Cloud...")
setup_remote_desktop(INSTANCE_ID)

# Fetch desktop URL
result = run(f"morphcloud instance get {INSTANCE_ID}", capture_output=True)
url_line = [line for line in result.stdout.splitlines() if '"url":"' in line and 'desktop' in line]
if url_line:
    desktop_url = url_line[0].split('"')[3]
    print(f"\nAccess your remote desktop at:\nhttps://desktop-{INSTANCE_ID.replace('_', '-')}.http.cloud.morph.so/vnc_lite.html")
else:
    print("Failed to retrieve desktop URL.")

print(f"\nInstance ID: {INSTANCE_ID}")
print(f"To SSH: morphcloud instance ssh {INSTANCE_ID}")
print(f"To stop: morphcloud instance stop {INSTANCE_ID}")

# Snapshot
print("\nCreating a final snapshot for future use...")
result = run(f"morphcloud instance snapshot {INSTANCE_ID}", capture_output=True)
snapshot_id = result.stdout.strip()
run(f"morphcloud snapshot set-metadata {snapshot_id} type=computer-dev-04072025 description='Remote desktop environment with XFCE and noVNC'")
print(f"Final snapshot created: {snapshot_id}")
print(f"To start new instance: morphcloud instance start {snapshot_id}")