#!/bin/bash
set -euo pipefail
action="${0##*/}"; action="${action#rpit3k-button-}"
source /usr/local/pisound/scripts/common/common.sh
exec 9>/run/lock/rpit3k-button.lock
flock -w 35 9
api=http://127.0.0.1/api
post(){ curl --noproxy '*' --silent --show-error --fail-with-body --max-time 35 -X POST -H 'X-RPiT3K: 1' "$api/$1"; }
status(){ curl --noproxy '*' --silent --show-error --fail --max-time 10 "$api/status"; }
flashes(){ local n="$1"; [[ "$n" =~ ^[1-4]$ ]] || return 1; for ((i=0;i<n;i++)); do flash_leds 10; sleep .60; done; }
preset(){ python3 -c 'import json,sys; s=json.load(sys.stdin); print(s["active"] or s["settings"]["last"])'; }
case "$action" in
 stomp) log "RPiT3K: single click / NAM 1"; if ! result=$(post stomp); then log "RPiT3K stomp failed: $result"; exit 1; fi; enabled=$(python3 -c 'import json,sys; s=json.load(sys.stdin); p=s["presets"][s["active"] or s["settings"]["last"]]; print(int(p["nam1_enabled"]))' <<<"$result"); log "RPiT3K: NAM 1 enabled=$enabled"; if [[ "$enabled" == 1 ]]; then flash_leds 15; else flash_leds 5; fi ;;
 next) post next >/dev/null; flash_leds 10 ;;
 identify) result=$(status); flashes "$(preset <<<"$result")" ;;
 audio) result=$(post audio-toggle); running=$(python3 -c 'import json,sys; s=json.load(sys.stdin); print(int(s["running"] and s["active"] is not None))' <<<"$result"); if [[ "$running" == 1 ]]; then flash_leds 20; else flash_leds 5; fi ;;
 hotspot)
   if nmcli connection show RPiT3K-fallback >/dev/null 2>&1; then
      if nmcli -t -f NAME connection show --active | grep -Fxq RPiT3K-fallback; then
         touch /run/rpit3k-hotspot-manual-off
         nmcli connection down RPiT3K-fallback
         flash_leds 40
      else
         nmcli connection up RPiT3K-fallback
         rm -f /run/rpit3k-hotspot-manual-off
         flash_leds 200
      fi
   else
      /usr/local/pisound/scripts/pisound-btn/toggle_wifi_hotspot.sh
   fi ;;
 shutdown) exec /usr/local/pisound/scripts/pisound-btn/shutdown.sh ;;
 *) exit 2 ;;
esac
