#!/usr/bin/env bash
set -euo pipefail
# Migrate an existing source installation without resetting its user, LAN,
# cloud, hardware, data directory, power settings or button mappings.
root="$(cd "$(dirname "$0")/.." && pwd)"
unit=/etc/systemd/system/rpit3k.service
test -f "$unit"
sudo -v
if ! sudo grep -q '^ExecStart=.*rpi/server.py' "$unit"; then
 echo "Unsupported service layout; no changes made." >&2; exit 1
fi
if sudo ss -H -ltn 'sport = :80' | grep -q . && ! sudo grep -qE '^ExecStart=.* --port 80( |$)' "$unit"; then
 echo "Port 80 is already occupied; no changes made." >&2; exit 1
fi
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
sudo cat "$unit" > "$tmp"
python3 - "$tmp" <<'PY'
import pathlib,re,sys
p=pathlib.Path(sys.argv[1])
s=p.read_text()
s,n=re.subn(r'^ExecStart=.*$',lambda m: re.sub(r' --port(?:=| +)[0-9]+(?= |$)','',m[0])+' --port 80',s,flags=re.M)
if n!=1: raise SystemExit("Expected exactly one ExecStart")
if not re.search(r'^AmbientCapabilities=.*CAP_NET_BIND_SERVICE',s,re.M):
    if re.search(r'^AmbientCapabilities=',s,re.M):
        s=re.sub(r'^AmbientCapabilities=.*$',lambda m:m[0]+' CAP_NET_BIND_SERVICE',s,flags=re.M)
    else:
        s=s.replace('[Service]\n','[Service]\nAmbientCapabilities=CAP_NET_BIND_SERVICE\n',1)
p.write_text(s)
PY
backup="$unit.before-http80-$(date +%Y%m%d-%H%M%S)"
sudo cp -a "$unit" "$backup"
sudo install -m 644 "$tmp" "$unit"
sudo systemctl daemon-reload
if sudo systemctl restart rpit3k.service; then
 for attempt in $(seq 1 20); do
  if curl --noproxy '*' -fsS --max-time 2 http://127.0.0.1/api/status | python3 -c 'import sys,json; s=json.load(sys.stdin); sys.exit(not (len(s.get("presets",{}))==4 and s.get("running") is False))' 2>/dev/null; then
   sudo install -m 755 "$root/rpi/next-preset.sh" /usr/local/bin/rpit3k-next
   if [[ -f /usr/local/bin/rpit3k-button ]]; then sudo install -m 755 "$root/rpi/pisound-button.sh" /usr/local/bin/rpit3k-button; fi
   echo "Ton3K ready on HTTP port 80; audio OFF. Backup: $backup"
   exit 0
  fi
  sleep 1
 done
fi
echo "HTTP readiness failed; restoring previous service." >&2
sudo cp -a "$backup" "$unit"
sudo systemctl daemon-reload
sudo systemctl restart rpit3k.service
exit 1
