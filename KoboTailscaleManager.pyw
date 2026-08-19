import os, sys, json, shutil, tarfile, tempfile, ctypes, configparser, re, time, subprocess
from ctypes import wintypes
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

APP_NAME = 'Kobo Tailscale Manager'
APP_VERSION = '4.2'
TS_VERSION = '1.98.10'
NM_VERSION = '0.6.0'
CLARA_COLOUR_MODEL_ID = '00000000-0000-0000-0000-000000000390'
CLARA_COLOUR_PREFIX = 'N367'
OFFLINE_ASSET_NAMES = ('tailscale_1.98.10_arm.tgz', 'NickelMenu_KoboRoot.tgz')


def resource_path(*parts):
    """Resolve bundled resources both from source and from a PyInstaller EXE."""
    base = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
    return base.joinpath(*parts)

# Model IDs found in .kobo/version.  Configuration aliases are kept as a
# fallback because Kobo eReader.conf is not identical on every firmware.
KOBO_MODEL_IDS = {
    CLARA_COLOUR_MODEL_ID: 'Kobo Clara Colour',
}
KOBO_MODEL_ALIASES = {
    'N367': 'Kobo Clara Colour', 'N367B': 'Kobo Clara Colour',
    'N365': 'Kobo Clara BW', 'N365B': 'Kobo Clara BW', 'P365': 'Kobo Clara BW',
    'N428': 'Kobo Libra Colour',
    'N605': 'Kobo Elipsa 2E', 'N506': 'Kobo Clara 2E',
    'N778': 'Kobo Sage', 'N778K': 'Kobo Sage', 'N418': 'Kobo Libra 2',
    'N604': 'Kobo Elipsa', 'N873': 'Kobo Libra H2O', 'N782': 'Kobo Forma',
    'N249': 'Kobo Clara HD', 'N306': 'Kobo Nia',
    'N867': 'Kobo Aura H2O Edition 2', 'N709': 'Kobo Aura ONE',
    'N236': 'Kobo Aura Edition 2', 'N587': 'Kobo Touch 2.0',
    'N437': 'Kobo Glo HD', 'N250': 'Kobo Aura H2O', 'N514': 'Kobo Aura',
    'N204B': 'Kobo Aura HD', 'N613': 'Kobo Glo', 'N905': 'Kobo Touch',
    'N905B': 'Kobo Touch', 'N905C': 'Kobo Touch',
}
KOBO_MODEL_NAME_ALIASES = {
    'clara colour': 'Kobo Clara Colour', 'clara bw': 'Kobo Clara BW',
    'libra colour': 'Kobo Libra Colour', 'libra 2': 'Kobo Libra 2',
    'clara 2e': 'Kobo Clara 2E', 'clara hd': 'Kobo Clara HD',
    'sage': 'Kobo Sage', 'elipsa': 'Kobo Elipsa', 'elipsa 2e': 'Kobo Elipsa 2E',
}
KOBO_MODELS = KOBO_MODEL_ALIASES

BOOTSTRAP = r'''#!/bin/sh
PATH=/sbin:/usr/sbin:/bin:/usr/bin
export PATH
BASE="/mnt/onboard/.adds/tailscale"
SCRIPTS="$BASE/scripts"
STATE="$BASE/state"
NM_DIR="/mnt/onboard/.adds/nm"
STATUS="/mnt/onboard/Tailscale-Installer-STATUS.txt"
AUTHFILE="/mnt/onboard/.kobo/tailscale_auth_key.txt"
MANAGER="/mnt/onboard/.kobo/KoboTailscaleManager"
TS_VER="1.98.10"
NM_VER="0.6.0"
TS_URL="https://pkgs.tailscale.com/stable/tailscale_${TS_VER}_arm.tgz"
NM_URL="https://github.com/pgaskin/NickelMenu/releases/download/v${NM_VER}/KoboRoot.tgz"
TMP_TS="/tmp/tailscale_${TS_VER}_arm.tgz"
TMP_NM="/tmp/NickelMenu_KoboRoot.tgz"
ASSETS="/usr/local/kobo-tailscale-bootstrap/assets"

log(){ echo "$(date '+%Y-%m-%d %H:%M:%S' 2>/dev/null) $*" >> "$STATUS"; }
fail(){ log "ERROR: $*"; exit 1; }

# wait onboard
i=0
while [ ! -d /mnt/onboard/.kobo ] && [ "$i" -lt 120 ]; do sleep 1; i=$((i+1)); done
[ -d /mnt/onboard/.kobo ] || exit 1
mkdir -p "$BASE" "$SCRIPTS" "$STATE" "$NM_DIR" "$MANAGER"

echo "Kobo Tailscale Manager installer v4" > "$STATUS"
log "Bootstrap started"
ARCH="$(uname -m 2>/dev/null)"; KERNEL="$(uname -r 2>/dev/null)"
log "Architecture: $ARCH"; log "Kernel: $KERNEL"
[ "$ARCH" = "armv7l" ] || fail "Unsupported architecture: $ARCH"
[ -c /dev/net/tun ] || fail "/dev/net/tun missing"

# NickelMenu's documentation file is installed with the package and remains a
# reliable USB-visible marker even when firmware changes the library path.
NM_PRESENT=0
[ -f /usr/local/Kobo/imageformats/libnm.so ] && NM_PRESENT=1
[ -f /usr/local/NickelMenu/libnm.so ] && NM_PRESENT=1
[ -f "$NM_DIR/doc" ] && NM_PRESENT=1

# A config file alone is not proof that NickelMenu is installed: preserve it,
# but install NickelMenu if neither of the strong markers above is present.
if [ "$NM_PRESENT" = "0" ] && [ -f "$NM_DIR/config" ]; then
  log "NickelMenu config found without installation marker; preserving config and installing NickelMenu"
fi

# Internet only if a package is missing.
NEED_NET=0
[ -x "$BASE/tailscale_${TS_VER}_arm/tailscaled" ] || [ -f "$ASSETS/tailscale_${TS_VER}_arm.tgz" ] || NEED_NET=1
[ "$NM_PRESENT" = "1" ] || [ -f "$ASSETS/NickelMenu_KoboRoot.tgz" ] || NEED_NET=1
if [ "$NEED_NET" = "1" ]; then
  log "Waiting for Internet"
  i=0
  while [ "$i" -lt 180 ]; do
    if wget -q -O /tmp/kts-netcheck https://pkgs.tailscale.com/ 2>/dev/null; then rm -f /tmp/kts-netcheck; break; fi
    sleep 2; i=$((i+2))
  done
  [ "$i" -lt 180 ] || fail "No Internet. Connect Wi-Fi and reboot to retry"
fi

if [ ! -x "$BASE/tailscale_${TS_VER}_arm/tailscaled" ]; then
  log "Installing Tailscale ${TS_VER} ARM"
  rm -f "$TMP_TS"
  if [ -f "$ASSETS/tailscale_${TS_VER}_arm.tgz" ]; then
    log "Using bundled Tailscale package"
    cp "$ASSETS/tailscale_${TS_VER}_arm.tgz" "$TMP_TS" || fail "Bundled Tailscale package unavailable"
  else
    log "Downloading Tailscale package"
    wget -O "$TMP_TS" "$TS_URL" >>"$STATUS" 2>&1 || fail "Tailscale download failed"
  fi
  tar xzf "$TMP_TS" -C "$BASE" >>"$STATUS" 2>&1 || fail "Tailscale extraction failed"
  rm -f "$TMP_TS"
fi
BIN="$BASE/tailscale_${TS_VER}_arm"
[ -x "$BIN/tailscale" ] && [ -x "$BIN/tailscaled" ] || fail "Tailscale binaries unavailable"

if [ "$NM_PRESENT" = "0" ]; then
  log "Installing NickelMenu ${NM_VER}"
  touch "$MANAGER/installed_nickelmenu_by_manager"
  rm -f "$TMP_NM"
  if [ -f "$ASSETS/NickelMenu_KoboRoot.tgz" ]; then
    log "Using bundled NickelMenu package"
    cp "$ASSETS/NickelMenu_KoboRoot.tgz" "$TMP_NM" || fail "Bundled NickelMenu package unavailable"
  else
    log "Downloading NickelMenu package"
    wget -O "$TMP_NM" "$NM_URL" >>"$STATUS" 2>&1 || fail "NickelMenu download failed"
  fi
  tar xzf "$TMP_NM" -C / >>"$STATUS" 2>&1 || fail "NickelMenu extraction failed"
  rm -f "$TMP_NM"
else
  log "NickelMenu already installed"
fi

cat > "$SCRIPTS/start.sh" <<'EOS'
#!/bin/sh
PATH=/sbin:/usr/sbin:/bin:/usr/bin
BASE="/mnt/onboard/.adds/tailscale"; VER="1.98.10"
BIN="$BASE/tailscale_${VER}_arm"; STATE="$BASE/state/tailscaled.state"
SOCK="/tmp/tailscaled.sock"; LOG="$BASE/tailscaled.log"
TS="$BIN/tailscale"; TSD="$BIN/tailscaled"
mkdir -p "$BASE/state"
[ -x "$TS" ] && [ -x "$TSD" ] || exit 1
if ! pidof tailscaled >/dev/null 2>&1; then
  rm -f "$SOCK"
  "$TSD" --state="$STATE" --socket="$SOCK" >>"$LOG" 2>&1 &
fi
i=0
while [ ! -S "$SOCK" ] && [ "$i" -lt 25 ]; do sleep 1; i=$((i+1)); done
[ -S "$SOCK" ] || exit 1
[ "$1" = "--daemon-only" ] && exit 0
"$TS" --socket="$SOCK" up --accept-dns=false --accept-routes=true --netfilter-mode=off --timeout=30s
exit $?
EOS

cat > "$SCRIPTS/stop.sh" <<'EOS'
#!/bin/sh
BASE="/mnt/onboard/.adds/tailscale"; VER="1.98.10"
TS="$BASE/tailscale_${VER}_arm/tailscale"; SOCK="/tmp/tailscaled.sock"
if [ -S "$SOCK" ] && [ -x "$TS" ]; then "$TS" --socket="$SOCK" down >/dev/null 2>&1 || true; fi
killall tailscaled >/dev/null 2>&1 || true
rm -f "$SOCK"
exit 0
EOS

cat > "$SCRIPTS/status.sh" <<'EOS'
#!/bin/sh
BASE="/mnt/onboard/.adds/tailscale"; VER="1.98.10"
TS="$BASE/tailscale_${VER}_arm/tailscale"; SOCK="/tmp/tailscaled.sock"
OPLOG="$BASE/last-operation.log"
show_last_operation() {
  [ -s "$OPLOG" ] || return 0
  echo "--- Last operation ---"
  tail -8 "$OPLOG"
}
if ! pidof tailscaled >/dev/null 2>&1; then echo "Tailscale: OFF"; show_last_operation; exit 0; fi
[ -S "$SOCK" ] || { echo "Tailscale: daemon active, socket missing"; show_last_operation; exit 1; }
TS_STATUS="$("$TS" --socket="$SOCK" status 2>&1)"
if echo "$TS_STATUS" | grep -Eqi 'Tailscale is stopped|Logged out|NeedsLogin'; then
  echo "Tailscale: OFF (daemon actif)"
  echo "$TS_STATUS" | head -12
  show_last_operation
  exit 0
fi
IP="$("$TS" --socket="$SOCK" ip -4 2>/dev/null)"
echo "Tailscale: ON"; [ -n "$IP" ] && echo "IP: $IP"
echo "$TS_STATUS" | head -12
show_last_operation
exit 0
EOS

cat > "$SCRIPTS/login.sh" <<'EOS'
#!/bin/sh
BASE="/mnt/onboard/.adds/tailscale"; VER="1.98.10"
TS="$BASE/tailscale_${VER}_arm/tailscale"; SOCK="/tmp/tailscaled.sock"
AUTHFILE="/mnt/onboard/.kobo/tailscale_auth_key.txt"
i=0
while ! ip route show default 2>/dev/null | grep -q . && [ "$i" -lt 60 ]; do
  sleep 1; i=$((i+1))
done
ip route show default 2>/dev/null | grep -q . || {
  echo "ERROR: Wi-Fi non connecté après 60 secondes. Connecte-le depuis les réglages Kobo puis réessaie."
  exit 1
}
/bin/sh "$BASE/scripts/start.sh" --daemon-only || exit 1
if [ -s "$AUTHFILE" ]; then
  if "$TS" --socket="$SOCK" up --auth-key="file:$AUTHFILE" --accept-dns=false --accept-routes=true --netfilter-mode=off --timeout=60s; then
    rm -f "$AUTHFILE"
    echo "Tailscale authenticated."
    exit 0
  fi
  echo "ERROR: Tailscale authentication failed"
  exit 1
fi
exec "$TS" --socket="$SOCK" up --accept-dns=false --accept-routes=true --netfilter-mode=off
EOS

cat > "$SCRIPTS/tailscale-10min.sh" <<'EOS'
#!/bin/sh
BASE="/mnt/onboard/.adds/tailscale"; MARK="$BASE/tailscale-10min.pid"
# NickelMenu enables Wi-Fi before this command. Wait until the Kobo has a
# usable default route instead of assuming that Wi-Fi connected immediately.
i=0
while ! ip route show default 2>/dev/null | grep -q . && [ "$i" -lt 60 ]; do
  sleep 1; i=$((i+1))
done
ip route show default 2>/dev/null | grep -q . || { echo "ERROR: Wi-Fi connection unavailable"; exit 1; }

/bin/sh "$BASE/scripts/start.sh" || { echo "ERROR: Tailscale failed to start"; exit 1; }
TS="$BASE/tailscale_1.98.10_arm/tailscale"; SOCK="/tmp/tailscaled.sock"
# The required route depends on the configured Kobo API endpoint. A Tailscale
# endpoint must not be rejected just because the Kobo is not on 192.168.1.0/24.
ENDPOINT="$(awk 'BEGIN{section=0} /^\[/{section=($0=="[OneStoreServices]")} section && /^api_endpoint=/{sub(/^api_endpoint=/,""); print; exit}' /mnt/onboard/.kobo/Kobo/'Kobo eReader.conf' 2>/dev/null)"
ENDPOINT_HOST="$(echo "$ENDPOINT" | sed -e 's#^[A-Za-z][A-Za-z0-9+.-]*://##' -e 's#/.*##' -e 's#:[0-9]*$##')"
NEED_LAN_ROUTE=1
case "$ENDPOINT_HOST" in
  *.ts.net) NEED_LAN_ROUTE=0 ;;
  100.*)
    TS_OCTET="${ENDPOINT_HOST#100.}"; TS_OCTET="${TS_OCTET%%.*}"
    case "$TS_OCTET" in
      64|65|66|67|68|69|70|71|72|73|74|75|76|77|78|79|80|81|82|83|84|85|86|87|88|89|90|91|92|93|94|95|96|97|98|99|1[01][0-9]|12[0-7]) NEED_LAN_ROUTE=0 ;;
    esac
    ;;
esac

ENDPOINT_ROUTE_TARGET="$ENDPOINT_HOST"
case "$ENDPOINT_HOST" in
  *[!0-9.]*|*..*|"")
    ENDPOINT_ROUTE_TARGET="$(getent hosts "$ENDPOINT_HOST" 2>/dev/null | awk 'NR==1 {print $1}')"
    ;;
esac

endpoint_route_ok() {
  [ -n "$ENDPOINT_ROUTE_TARGET" ] && ip route get "$ENDPOINT_ROUTE_TARGET" 2>/dev/null | grep -q .
}

tailscale_connected() {
  "$TS" --socket="$SOCK" status >/dev/null 2>&1 && [ -n "$("$TS" --socket="$SOCK" ip -4 2>/dev/null)" ]
}

i=0
while [ "$i" -lt 30 ]; do
  if tailscale_connected && { [ "$NEED_LAN_ROUTE" = "0" ] || endpoint_route_ok; }; then
    break
  fi
  sleep 1; i=$((i+1))
done

if ! tailscale_connected; then
  echo "ERROR: Tailscale is not connected"
  exit 1
fi
if [ "$NEED_LAN_ROUTE" = "1" ] && ! endpoint_route_ok; then
  echo "ERROR: route vers l'endpoint LAN indisponible"
  exit 1
fi

if [ -f "$MARK" ]; then OLD="$(cat "$MARK" 2>/dev/null)"; [ -n "$OLD" ] && kill "$OLD" >/dev/null 2>&1 || true; fi
(
  sleep 600
  /bin/sh "$BASE/scripts/stop.sh" >/dev/null 2>&1
  rm -f "$MARK"
) &
echo $! > "$MARK"
if [ "$NEED_LAN_ROUTE" = "1" ]; then
  echo "Tailscale connecté — route LAN de l'endpoint active — arrêt automatique dans 10 minutes."
else
  echo "Tailscale connecté — endpoint Tailscale détecté — arrêt automatique dans 10 minutes."
fi
exit 0
EOS

# Keep the manager's entries in NickelMenu's canonical config file. The
# markers make updates idempotent and preserve every unrelated user entry.
NM_CONFIG="$NM_DIR/config"
log "Updating NickelMenu config: $NM_CONFIG"
touch "$NM_CONFIG"
sed -i '/^# KoboTailscaleManager BEGIN$/,/^# KoboTailscaleManager END$/d' "$NM_CONFIG"
menu_enabled(){ [ ! -f "$MANAGER/menu-selection.conf" ] || grep -q "^$1=1$" "$MANAGER/menu-selection.conf"; }
{
  echo '# KoboTailscaleManager BEGIN'
  if menu_enabled ten_min; then
    echo 'menu_item :main :Tailscale - 10 min :nickel_wifi :autoconnect'
    echo '  chain_always :cmd_spawn :/bin/sh /mnt/onboard/.adds/tailscale/scripts/tailscale-10min.sh > /mnt/onboard/.adds/tailscale/last-operation.log 2>&1'
    echo '  chain_always :dbg_toast :Démarrage Tailscale 10 min... Vérifie avec Tailscale - Status.'
  fi
  if menu_enabled status; then echo 'menu_item :main :Tailscale - Status :cmd_output :9999:/bin/sh /mnt/onboard/.adds/tailscale/scripts/status.sh'; fi
  if menu_enabled start; then echo 'menu_item :main :Tailscale - Start :cmd_spawn :/bin/sh /mnt/onboard/.adds/tailscale/scripts/start.sh > /mnt/onboard/.adds/tailscale/last-operation.log 2>&1'; fi
  if menu_enabled stop; then echo 'menu_item :main :Tailscale - Stop :cmd_spawn :/bin/sh /mnt/onboard/.adds/tailscale/scripts/stop.sh > /mnt/onboard/.adds/tailscale/last-operation.log 2>&1'; fi
  if menu_enabled login; then
    echo 'menu_item :main :Tailscale - Login :nickel_wifi :autoconnect'
    echo '  chain_always :cmd_spawn :/bin/sh /mnt/onboard/.adds/tailscale/scripts/login.sh > /mnt/onboard/.adds/tailscale/last-operation.log 2>&1'
    echo '  chain_always :dbg_toast :Login Tailscale lancé... Vérifie avec Tailscale - Status.'
  fi
  echo '# KoboTailscaleManager END'
} >> "$NM_CONFIG"
if menu_enabled ten_min; then
  grep -q '^menu_item :main :Tailscale - 10 min ' "$NM_CONFIG" || fail "NickelMenu 10-minute menu entry was not written"
  log "NickelMenu menu updated: Tailscale - 10 min enabled"
else
  log "NickelMenu menu updated: Tailscale - 10 min disabled by selection"
fi
# Keep the historical marker for USB detection, but do not duplicate menu items.
: > "$NM_DIR/tailscale-clara-colour"

# If an auth key was supplied and the device has no identity yet, authenticate headlessly.
if [ -f "$AUTHFILE" ] && [ ! -s "$STATE/tailscaled.state" ]; then
  log "Authenticating Tailscale with supplied auth key"
  /bin/sh "$SCRIPTS/start.sh" || fail "tailscaled failed to start for authentication"
  if "$BIN/tailscale" --socket=/tmp/tailscaled.sock up --auth-key="file:$AUTHFILE" --accept-dns=false --accept-routes=true --netfilter-mode=off --timeout=60s >>"$STATUS" 2>&1; then
    log "Tailscale authentication successful"
    rm -f "$AUTHFILE"
    /bin/sh "$SCRIPTS/stop.sh" >/dev/null 2>&1 || true
  else
    fail "Tailscale authentication failed; auth file retained for retry"
  fi
elif [ -f "$AUTHFILE" ] && [ -s "$STATE/tailscaled.state" ]; then
  log "Existing Tailscale identity detected; supplied auth key not needed"
  rm -f "$AUTHFILE"
fi

# No persistent autostart by design. User launches 10-minute session from NickelMenu.
rm -f /etc/udev/rules.d/98-tailscale-clara-colour.rules
rm -rf /usr/local/tailscale-clara-colour

touch "$MANAGER/install_complete"
log "Install/update complete"
rm -f /etc/udev/rules.d/97-kobo-tailscale-manager-bootstrap.rules
sync
sleep 3
reboot
exit 0
'''

REVERT = r'''#!/bin/sh
PATH=/sbin:/usr/sbin:/bin:/usr/bin
export PATH
BASE="/mnt/onboard/.adds/tailscale"
MANAGER="/mnt/onboard/.kobo/KoboTailscaleManager"
# stop daemon if any
killall tailscaled >/dev/null 2>&1 || true
rm -f /tmp/tailscaled.sock
rm -f /etc/udev/rules.d/98-tailscale-clara-colour.rules
rm -rf /usr/local/tailscale-clara-colour
rm -f /etc/udev/rules.d/97-kobo-tailscale-manager-bootstrap.rules
rm -f /mnt/onboard/.adds/nm/tailscale-clara-colour
# Remove only the block owned by this manager; preserve user NickelMenu items.
NM_CONFIG="/mnt/onboard/.adds/nm/config"
[ -f "$NM_CONFIG" ] && sed -i '/^# KoboTailscaleManager BEGIN$/,/^# KoboTailscaleManager END$/d' "$NM_CONFIG"
# Uninstall NickelMenu only if this manager originally installed it.
if [ -f "$MANAGER/installed_nickelmenu_by_manager" ]; then
  mkdir -p /mnt/onboard/.adds/nm
  touch /mnt/onboard/.adds/nm/uninstall
fi
rm -rf "$BASE"
rm -f /mnt/onboard/.kobo/tailscale_auth_key.txt
rm -f /mnt/onboard/Tailscale-Installer-STATUS.txt
rm -f "$MANAGER/install_complete"
rm -f "$MANAGER/menu-selection.conf"
sync
sleep 2
reboot
exit 0
'''


RESTORE_ONLY = r'''#!/bin/sh
PATH=/sbin:/usr/sbin:/bin:/usr/bin
export PATH
BASE="/mnt/onboard/.adds/tailscale"
killall tailscaled >/dev/null 2>&1 || true
rm -f /tmp/tailscaled.sock
rm -f /etc/udev/rules.d/98-tailscale-clara-colour.rules
rm -rf /usr/local/tailscale-clara-colour
rm -f /etc/udev/rules.d/97-kobo-tailscale-manager-bootstrap.rules
rm -f /mnt/onboard/.adds/nm/tailscale-clara-colour
NM_CONFIG="/mnt/onboard/.adds/nm/config"
[ -f "$NM_CONFIG" ] && sed -i '/^# KoboTailscaleManager BEGIN$/,/^# KoboTailscaleManager END$/d' "$NM_CONFIG"
rm -rf "$BASE/scripts"
rm -f "$BASE/tailscale-10min.pid"
rm -f /mnt/onboard/.kobo/tailscale_auth_key.txt
rm -f /mnt/onboard/Tailscale-Installer-STATUS.txt
rm -f /mnt/onboard/.kobo/KoboTailscaleManager/install_complete
rm -f /mnt/onboard/.kobo/KoboTailscaleManager/menu-selection.conf
sync
sleep 2
reboot
exit 0
'''


def is_windows():
    return os.name == 'nt'


def drive_candidates():
    out = []
    if is_windows():
        GetLogicalDrives = ctypes.windll.kernel32.GetLogicalDrives
        GetDriveTypeW = ctypes.windll.kernel32.GetDriveTypeW
        mask = GetLogicalDrives()
        for i in range(26):
            if mask & (1 << i):
                root = f"{chr(65+i)}:\\"
                try:
                    dtype = GetDriveTypeW(ctypes.c_wchar_p(root))
                    if dtype in (2, 3) and Path(root, '.kobo').is_dir():
                        out.append(root)
                except Exception:
                    pass
    else:
        for base in ('/media', '/mnt', '/run/media'):
            p = Path(base)
            if not p.exists():
                continue
            for cand in p.rglob('.kobo'):
                try:
                    root = str(cand.parent)
                    if root not in out:
                        out.append(root)
                except Exception:
                    pass
    return out


def read_version(root):
    p = Path(root) / '.kobo' / 'version'
    data = {'serial':'', 'kernel':'', 'firmware':'', 'model_id':'', 'model_hint':'', 'raw':''}
    if not p.exists(): return data
    raw = p.read_text(encoding='utf-8', errors='replace').strip()
    parts = [x.strip() for x in raw.split(',')]
    data['raw'] = raw
    if parts: data['serial'] = parts[0]
    if len(parts) > 1: data['kernel'] = parts[1]
    if len(parts) > 2: data['firmware'] = parts[2]
    if not data['firmware']:
        for part in parts:
            if re.fullmatch(r'\d+(?:\.\d+){2,}', part):
                data['firmware'] = part
                break
    for part in parts:
        if re.fullmatch(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}', part):
            data['model_id'] = part.lower()
    if not data['model_id'] and len(parts) > 5: data['model_id'] = parts[-1]
    for part in parts:
        if part.upper() in KOBO_MODELS:
            data['model_hint'] = part.upper()
            break
    return data


KNOWN_IDS = sorted(KOBO_MODEL_ALIASES, key=len, reverse=True)


def resolve_model_from_string(value):
    value = str(value or '').upper().strip()
    for model_id in KNOWN_IDS:
        if value.startswith(model_id):
            return model_id, KOBO_MODEL_ALIASES[model_id]
    return None, None


def read_hardware_sources(root):
    kobo = Path(root) / '.kobo'
    elabel_ids = set()
    elabel_dir = kobo / 'elabel'
    if elabel_dir.is_dir():
        for item in elabel_dir.glob('*.epub'):
            raw = item.stem.split('-', 1)[0].upper()
            model_id, _ = resolve_model_from_string(raw)
            if model_id: elabel_ids.add(model_id)

    serial = ''
    serial_ids = set()
    # Try the small set of usual Kobo metadata files first. Full recursive
    # scanning is only a fallback for unusual firmware layouts.
    candidates = [conf_path(root), kobo / 'device.xml', kobo / 'device_info.xml', kobo / 'affiliate.conf']
    candidates += list(kobo.glob('*.xml'))
    candidates += list(kobo.glob('*.conf'))
    candidates = list(dict.fromkeys(candidates))
    for item in candidates:
        if not item.is_file(): continue
        if not item.is_file() or item.suffix.lower() not in {'.xml', '.conf', '.ini'}: continue
        try: text = item.read_text(encoding='utf-8-sig', errors='replace')
        except OSError: continue
        match = re.search(r'<deviceSerial>\s*([^<]+?)\s*</deviceSerial>', text, re.IGNORECASE)
        if match:
            serial = match.group(1).strip()
            model_id, _ = resolve_model_from_string(serial)
            if model_id: serial_ids.add(model_id)
            break
    if not serial:
        for item in kobo.rglob('*'):
            if not item.is_file() or item in candidates or item.suffix.lower() not in {'.xml', '.conf', '.ini'}: continue
            try: text = item.read_text(encoding='utf-8-sig', errors='replace')
            except OSError: continue
            match = re.search(r'<deviceSerial>\s*([^<]+?)\s*</deviceSerial>', text, re.IGNORECASE)
            if match:
                serial = match.group(1).strip()
                model_id, _ = resolve_model_from_string(serial)
                if model_id: serial_ids.add(model_id)
                break
    return {'elabel_ids': sorted(elabel_ids), 'serial': serial, 'serial_ids': sorted(serial_ids)}


def conf_path(root): return Path(root) / '.kobo' / 'Kobo' / 'Kobo eReader.conf'

def backup_path(root): return Path(root) / '.kobo' / 'Kobo' / 'Kobo eReader.conf.kts-backup'

def manager_dir(root): return Path(root) / '.kobo' / 'KoboTailscaleManager'


def read_endpoint(root):
    p = conf_path(root)
    if not p.exists(): return ''
    section = None
    for line in p.read_text(encoding='utf-8-sig', errors='replace').splitlines():
        s=line.strip()
        if s.startswith('[') and s.endswith(']'):
            section=s[1:-1]
        elif section == 'OneStoreServices' and s.startswith('api_endpoint='):
            return s.split('=',1)[1].strip()
    return ''


def read_model_config(root):
    p = conf_path(root)
    values = {}
    if not p.exists(): return values
    wanted = {'model', 'product', 'device', 'hardware', 'serial'}
    for line in p.read_text(encoding='utf-8-sig', errors='replace').splitlines():
        if '=' not in line: continue
        key, value = line.split('=', 1)
        if key.strip().lower() in wanted and value.strip():
            values[key.strip().lower()] = value.strip()
    return values


def detect_hardware_model(root, version_info, config_values):
    hw = read_hardware_sources(root)
    elabel_id = hw['elabel_ids'][0] if hw['elabel_ids'] else None
    serial_id = hw['serial_ids'][0] if hw['serial_ids'] else None
    version_id, version_name = resolve_model_from_string(version_info.get('model_hint', ''))
    if not version_id and version_info.get('model_id', '').lower() in KOBO_MODEL_IDS:
        version_id = version_info['model_id'].upper()
        version_name = KOBO_MODEL_IDS[version_info['model_id'].lower()]
    config_id = None
    for value in config_values.values():
        config_id, _ = resolve_model_from_string(value)
        if config_id: break
    chosen_id = elabel_id or serial_id or version_id or config_id
    model = KOBO_MODEL_ALIASES.get(chosen_id, version_name or 'Kobo inconnue')
    source = 'eLabel' if elabel_id else ('deviceSerial' if serial_id else ('version' if version_id else ('configuration' if config_id else 'inconnue')))
    warning = ''
    if len(hw['elabel_ids']) > 1:
        warning = 'Avertissement : plusieurs identifiants eLabel différents ont été trouvés.'
    elif elabel_id and serial_id and KOBO_MODEL_ALIASES.get(elabel_id) != KOBO_MODEL_ALIASES.get(serial_id):
        warning = 'Avertissement : eLabel et deviceSerial indiquent des mod\u00e8les diff\u00e9rents.'
    elif elabel_id and serial_id:
        source = 'D\u00e9tection confirm\u00e9e (eLabel + deviceSerial)'
    return model, chosen_id or '', source, warning, hw['serial']


def set_endpoint(root, endpoint):
    p = conf_path(root)
    if not p.exists():
        raise FileNotFoundError(f'Configuration Kobo introuvable: {p}')
    b = backup_path(root)
    if not b.exists():
        shutil.copy2(p,b)
    text = p.read_text(encoding='utf-8-sig', errors='replace').replace('\r\n','\n').replace('\r','\n')
    lines=text.split('\n')
    out=[]; insec=False; foundsec=False; replaced=False; inserted=False
    for line in lines:
        stripped=line.strip()
        if stripped.startswith('[') and stripped.endswith(']'):
            if insec and not replaced and not inserted:
                out.append(f'api_endpoint={endpoint}'); inserted=True
            sec=stripped[1:-1]
            insec=(sec=='OneStoreServices')
            if insec: foundsec=True
            out.append(line)
            continue
        if insec and stripped.startswith('api_endpoint='):
            if not replaced:
                out.append(f'api_endpoint={endpoint}'); replaced=True
            continue
        out.append(line)
    if foundsec and not replaced and not inserted:
        out.append(f'api_endpoint={endpoint}')
    if not foundsec:
        if out and out[-1] != '': out.append('')
        out += ['[OneStoreServices]', f'api_endpoint={endpoint}']
    p.write_text('\n'.join(out), encoding='utf-8', newline='\n')


def restore_endpoint(root):
    b=backup_path(root); p=conf_path(root)
    if not b.exists():
        raise FileNotFoundError('Aucune sauvegarde Kobo eReader.conf créée par cet outil.')
    shutil.copy2(b,p)


def build_menu_config(enabled):
    lines=['# Managed by KoboTailscaleManager']
    if enabled.get('ten_min', True):
        lines += [
            'menu_item :main :Tailscale - 10 min :nickel_wifi :autoconnect',
            '  chain_always :cmd_spawn :/bin/sh /mnt/onboard/.adds/tailscale/scripts/tailscale-10min.sh > /mnt/onboard/.adds/tailscale/last-operation.log 2>&1',
            '  chain_always :dbg_toast :Démarrage Tailscale 10 min... Vérifie avec Tailscale - Status.',
        ]
    if enabled.get('status', True): lines.append('menu_item :main :Tailscale - Status :cmd_output :9999:/bin/sh /mnt/onboard/.adds/tailscale/scripts/status.sh')
    if enabled.get('start', True): lines.append('menu_item :main :Tailscale - Start :cmd_spawn :/bin/sh /mnt/onboard/.adds/tailscale/scripts/start.sh > /mnt/onboard/.adds/tailscale/last-operation.log 2>&1')
    if enabled.get('stop', True): lines.append('menu_item :main :Tailscale - Stop :cmd_spawn :/bin/sh /mnt/onboard/.adds/tailscale/scripts/stop.sh > /mnt/onboard/.adds/tailscale/last-operation.log 2>&1')
    if enabled.get('login', True):
        lines += [
            'menu_item :main :Tailscale - Login :nickel_wifi :autoconnect',
            '  chain_always :cmd_spawn :/bin/sh /mnt/onboard/.adds/tailscale/scripts/login.sh > /mnt/onboard/.adds/tailscale/last-operation.log 2>&1',
            '  chain_always :dbg_toast :Login Tailscale lancé... Vérifie avec Tailscale - Status.',
        ]
    return '\n'.join(lines)+'\n'


def embedded_tailscale_script(name):
    marker=f'cat > "$SCRIPTS/{name}" <<\'EOS\'\n'
    start=BOOTSTRAP.find(marker)
    if start < 0: raise ValueError(f'Script embarqué introuvable: {name}')
    start += len(marker)
    end=BOOTSTRAP.find('\nEOS',start)
    if end < 0: raise ValueError(f'Fin du script embarqué introuvable: {name}')
    return BOOTSTRAP[start:end]+'\n'


def safe_extract_tar(archive, destination):
    destination=Path(destination).resolve()
    with tarfile.open(archive,'r:gz') as tf:
        for member in tf.getmembers():
            target=(destination/member.name).resolve()
            if target != destination and destination not in target.parents:
                raise ValueError(f'Chemin dangereux dans {archive}: {member.name}')
        tf.extractall(destination)


def add_direct_offline_payload(td, menu_config):
    nm_asset=resource_path('assets','NickelMenu_KoboRoot.tgz')
    ts_asset=resource_path('assets','tailscale_1.98.10_arm.tgz')
    if not nm_asset.is_file() or not ts_asset.is_file():
        raise FileNotFoundError('Les paquets hors ligne NickelMenu/Tailscale sont absents de l’application.')
    safe_extract_tar(nm_asset,td)
    ts_dir=td/'mnt/onboard/.adds/tailscale'
    ts_dir.mkdir(parents=True,exist_ok=True)
    safe_extract_tar(ts_asset,ts_dir)
    scripts=ts_dir/'scripts'; scripts.mkdir(exist_ok=True)
    (ts_dir/'state').mkdir(exist_ok=True)
    for name in ('start.sh','stop.sh','status.sh','login.sh','tailscale-10min.sh'):
        script=scripts/name
        script.write_text(embedded_tailscale_script(name),encoding='utf-8',newline='\n')
        os.chmod(script,0o755)
    nm_dir=td/'mnt/onboard/.adds/nm'; nm_dir.mkdir(parents=True,exist_ok=True)
    menu_file=nm_dir/'kobo-tailscale-manager'
    menu_file.write_text(menu_config,encoding='utf-8',newline='\n')
    os.chmod(menu_file,0o644)
    status=td/'mnt/onboard/Tailscale-Installer-STATUS.txt'
    status.write_text('Direct offline payload installed: NickelMenu + Tailscale + menu configuration.\n',encoding='utf-8',newline='\n')


def create_tar_gz(target, bootstrap_text, revert=False, menu_config=None):
    with tempfile.TemporaryDirectory() as td:
        td=Path(td)
        if menu_config is not None:
            add_direct_offline_payload(td,menu_config)
        else:
            (td/'usr/local/kobo-tailscale-bootstrap').mkdir(parents=True)
            (td/'etc/udev/rules.d').mkdir(parents=True)
            script = td/'usr/local/kobo-tailscale-bootstrap/bootstrap.sh'
            script.write_text(bootstrap_text, encoding='utf-8', newline='\n')
            os.chmod(script,0o755)
            kick=td/'usr/local/kobo-tailscale-bootstrap/kick.sh'
            kick.write_text('''#!/bin/sh
# udev terminates slow children. Re-exec in a detached session first.
if [ "${KTS_SETSID:-}" != "1" ]; then
  KTS_SETSID=1 setsid "$0" "$@" &
  exit 0
fi
mkdir /tmp/kobo-tailscale-bootstrap.lock 2>/dev/null || exit 0
exec /usr/local/kobo-tailscale-bootstrap/bootstrap.sh >/tmp/kobo-ts-manager.log 2>&1
''',encoding='utf-8',newline='\n')
            os.chmod(kick,0o755)
            rule=td/'etc/udev/rules.d/97-kobo-tailscale-manager-bootstrap.rules'
            rule.write_text('KERNEL=="loop0", ACTION=="add", RUN+="/usr/local/kobo-tailscale-bootstrap/kick.sh"\n',encoding='utf-8',newline='\n')
            os.chmod(rule,0o644)
        with tarfile.open(target,'w:gz',format=tarfile.GNU_FORMAT) as tf:
            def portable_mode(info):
                # Windows does not preserve Unix executable bits in the
                # temporary staging tree. Kobo needs them in KoboRoot.tgz.
                name=info.name.replace('\\','/')
                if info.isdir():
                    info.mode=0o755
                elif info.isfile():
                    executable=(
                        name.endswith('.sh')
                        or name == 'usr/local/Kobo/imageformats/libnm.so'
                        or name.endswith('/tailscale')
                        or name.endswith('/tailscaled')
                    )
                    info.mode=0o755 if executable else 0o644
                return info
            for f in sorted(td.rglob('*')):
                arcname=str(f.relative_to(td)).replace('\\','/')
                tf.add(f,arcname=arcname,recursive=False,filter=portable_mode)


def validate_endpoint(s):
    return bool(re.match(r'^https?://[^\s]+$', s.strip()))

def validate_auth_key(s):
    s=s.strip()
    return (not s) or s.startswith('tskey-')


def device_status(root):
    v=read_version(root); config_values=read_model_config(root)
    v['config_values']=config_values
    model, hardware_id, detection_source, detection_warning, device_serial = detect_hardware_model(root, v, config_values)
    serial=device_serial or v.get('serial','') or config_values.get('serial','')
    fw=v.get('firmware','')
    ts_state=Path(root,'.adds','tailscale','state','tailscaled.state').exists()
    ts_scripts=Path(root,'.adds','tailscale','scripts','start.sh').exists()
    nm_dir=Path(root,'.adds','nm')
    nm_doc=nm_dir/'doc'
    nm_ts=nm_dir/'tailscale-clara-colour'
    if nm_doc.is_file():
        nm_status='D\u00e9tect\u00e9 (NickelMenu)'
    elif nm_ts.is_file():
        nm_status='D\u00e9tect\u00e9 (configuration Tailscale)'
    elif nm_dir.is_dir() and any(item.is_file() for item in nm_dir.iterdir()):
        nm_status='Probablement install\u00e9 (.adds/nm pr\u00e9sent)'
    else:
        nm_status='Non d\u00e9tectable via USB'
    status_file=Path(root,'Tailscale-Installer-STATUS.txt')
    return {
        'root':root,'model':model,'serial':serial,'kernel':v.get('kernel',''),
        'firmware':fw,'model_id':hardware_id or v.get('model_id',''),'detection_source':detection_source,'detection_warning':detection_warning,'endpoint':read_endpoint(root),
        'tailscale':'Configuré' if ts_state else ('Fichiers présents' if ts_scripts else 'Absent'),
        'nickelmenu':nm_status,
        'backup':'Oui' if backup_path(root).exists() else 'Non',
        'pending':'Oui' if Path(root,'.kobo','KoboRoot.tgz').exists() else 'Non',
        'status_exists':status_file.exists(),
        'status_text':status_file.read_text(encoding='utf-8',errors='replace')[-8000:] if status_file.exists() else ''
    }


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f'{APP_NAME}  v{APP_VERSION}')
        self.geometry('1040x700')
        self.minsize(920,620)
        self.configure(bg='#f4f6f8')
        self.style=ttk.Style(self)
        try: self.style.theme_use('vista')
        except: pass
        self.style.configure('Title.TLabel',font=('Segoe UI',20,'bold'))
        self.style.configure('Sub.TLabel',font=('Segoe UI',10),foreground='#56606a')
        self.style.configure('Card.TLabelframe',padding=12)
        self.style.configure('Go.TButton',font=('Segoe UI',10,'bold'))
        self.drive_var=tk.StringVar(); self.endpoint_var=tk.StringVar(); self.auth_var=tk.StringVar()
        self.menu_vars={name:tk.BooleanVar(value=True) for name in ('ten_min','status','start','stop','login')}
        self.auto_eject_var=tk.BooleanVar(value=False)
        self.status_var=tk.StringVar(value='Connecte une Kobo en USB puis clique Actualiser.')
        self._build(); self.refresh_drives()

    def _build(self):
        top=ttk.Frame(self,padding=(24,20,24,8)); top.pack(fill='x')
        ttk.Label(top,text='Kobo Tailscale Manager',style='Title.TLabel').pack(anchor='w')
        ttk.Label(top,text='Provisionnement Clara Colour · NickelMenu · Tailscale · endpoint Kobo · restauration',style='Sub.TLabel').pack(anchor='w',pady=(2,0))

        dev=ttk.LabelFrame(self,text='1  Liseuse USB',style='Card.TLabelframe'); dev.pack(fill='x',padx=24,pady=8)
        row=ttk.Frame(dev); row.pack(fill='x')
        self.combo=ttk.Combobox(row,textvariable=self.drive_var,state='readonly',width=42); self.combo.pack(side='left',fill='x',expand=True)
        self.combo.bind('<<ComboboxSelected>>',lambda e:self.inspect())
        ttk.Button(row,text='Actualiser',command=self.refresh_drives).pack(side='left',padx=(8,0))
        self.tree=ttk.Treeview(dev,columns=('value',),show='tree headings',height=8)
        self.tree.bind('<ButtonRelease-1>', self.copy_tree_value)
        self.tree.heading('#0',text='Information'); self.tree.heading('value',text='Valeur')
        self.tree.column('#0',width=220,anchor='w'); self.tree.column('value',width=690,anchor='w')
        self.tree.pack(fill='x',pady=(10,0))

        cfg=ttk.LabelFrame(self,text='2  Configuration',style='Card.TLabelframe'); cfg.pack(fill='x',padx=24,pady=8)
        ttk.Label(cfg,text='API endpoint Kobo').grid(row=0,column=0,sticky='w',padx=(0,10),pady=6)
        ttk.Entry(cfg,textvariable=self.endpoint_var).grid(row=0,column=1,sticky='ew',pady=6)
        ttk.Label(cfg,text='Clé Tailscale auth').grid(row=1,column=0,sticky='w',padx=(0,10),pady=6)
        self.auth_entry=ttk.Entry(cfg,textvariable=self.auth_var); self.auth_entry.grid(row=1,column=1,sticky='ew',pady=6)
        ttk.Label(cfg,text='Visible et conservée uniquement en mémoire jusqu’à la fermeture. Laisse vide pour une liseuse déjà authentifiée.',style='Sub.TLabel').grid(row=2,column=1,sticky='w')
        cfg.columnconfigure(1,weight=1)

        menu=ttk.LabelFrame(self,text='Menu NickelMenu',style='Card.TLabelframe'); menu.pack(fill='x',padx=24,pady=8)
        for col,(key,label) in enumerate((('ten_min','Tailscale - 10 min'),('status','Status'),('start','Start'),('stop','Stop'),('login','Login'))):
            ttk.Checkbutton(menu,text=label,variable=self.menu_vars[key]).grid(row=0,column=col,padx=6,pady=5,sticky='w')
        ttk.Checkbutton(menu,text='Éjecter automatiquement après préparation',variable=self.auto_eject_var).grid(row=1,column=0,columnspan=5,padx=6,pady=(0,5),sticky='w')

        actions=ttk.Frame(self,padding=(24,8)); actions.pack(fill='x')
        ttk.Button(actions,text='GO — Installer / Mettre à jour',style='Go.TButton',command=self.go).pack(side='left')
        ttk.Button(actions,text='Restore Kobo config',command=self.restore_config).pack(side='left',padx=10)
        ttk.Button(actions,text='Full uninstall',command=self.full_uninstall).pack(side='left',padx=10)
        ttk.Button(actions,text='Relire le statut',command=self.inspect).pack(side='left')

        logf=ttk.LabelFrame(self,text='Statut',style='Card.TLabelframe'); logf.pack(fill='both',expand=True,padx=24,pady=(8,20))
        self.log=tk.Text(logf,height=10,wrap='word',font=('Consolas',9),bg='#ffffff',relief='flat')
        self.log.pack(fill='both',expand=True)
        self.log.insert('1.0',self.status_var.get()); self.log.config(state='disabled')

    def setlog(self,s):
        self.log.config(state='normal'); self.log.delete('1.0','end'); self.log.insert('1.0',s); self.log.config(state='disabled')

    def copy_tree_value(self, event=None):
        item = self.tree.identify_row(event.y) if event else ''
        if not item: return
        value = self.tree.set(item, 'value')
        if value:
            self.clipboard_clear()
            self.clipboard_append(value)
            self.update()

    def refresh_drives(self):
        ds=drive_candidates(); self.combo['values']=ds
        if ds:
            if self.drive_var.get() not in ds: self.drive_var.set(ds[0])
            self.inspect()
        else:
            self.drive_var.set(''); self.tree.delete(*self.tree.get_children()); self.setlog('Aucune Kobo détectée. Branche la liseuse, choisis « Connecter » sur la Kobo, puis Actualiser.')

    def inspect(self):
        root=self.drive_var.get()
        if not root or not Path(root,'.kobo').exists(): return
        try: st=device_status(root)
        except Exception as e: messagebox.showerror(APP_NAME,str(e)); return
        self.load_menu_selection(root)
        self.tree.delete(*self.tree.get_children())
        rows=[('Mod\u00e8le',st['model']),('Hardware ID',st['model_id'] or '\u2014'),('Source de d\u00e9tection',st['detection_source']),('Lecteur',st['root']),('Firmware',st['firmware']),('Kernel',st['kernel']),('N\u00b0 s\u00e9rie',st['serial']),('API endpoint',st['endpoint'] or '\u2014'),('Tailscale',st['tailscale']),('NickelMenu',st['nickelmenu']),('Sauvegarde config',st['backup']),('Mise \u00e0 jour en attente',st['pending'])]
        for k,v in rows: self.tree.insert('', 'end', text=k, values=(v,))
        if not self.endpoint_var.get() and st['endpoint']: self.endpoint_var.set(st['endpoint'])
        msg='Diagnostic USB terminé.'
        if st['detection_warning']: msg+='\n'+st['detection_warning']
        if st['model'] == 'Kobo inconnue': msg+='\nModèle commercial non résolu ; Hardware ID conservé.'
        if st['firmware'].startswith('5.'):
            msg+='\n⚠ Firmware 5.x détecté : NickelMenu n’est pas pris en charge par cette version.'
        if st['status_text']:
            msg+='\n\n=== Journal du dernier bootstrap Kobo ===\n'+st['status_text']
        elif st['pending']=='Oui':
            msg+='\n\n=== Journal bootstrap ===\nKoboRoot.tgz est encore présent : la liseuse n’a pas encore appliqué la mise à jour. Éjecte-la puis attends le redémarrage complet.'
        else:
            msg+='\n\n=== Journal bootstrap ===\nAucun rapport trouvé. Si rien ne s’est installé, le bootstrap n’a pas démarré ou a échoué avant de pouvoir écrire son journal.'
        self.setlog(msg)

    def write_menu_selection(self, root):
        md=manager_dir(root); md.mkdir(parents=True,exist_ok=True)
        lines=[f'{key}={1 if var.get() else 0}' for key,var in self.menu_vars.items()]
        (md/'menu-selection.conf').write_text('\n'.join(lines)+'\n',encoding='ascii',newline='\n')

    def load_menu_selection(self, root):
        p=manager_dir(root)/'menu-selection.conf'
        if not p.exists(): return
        try:
            values=dict(line.strip().split('=',1) for line in p.read_text(encoding='ascii',errors='ignore').splitlines() if '=' in line)
        except OSError:
            return
        for key,var in self.menu_vars.items():
            if key in values: var.set(values[key] == '1')

    def eject_drive(self, root):
        if not is_windows() or not re.fullmatch(r'[A-Za-z]:\\', root): return False
        def unmounted(timeout=10):
            deadline=time.time()+timeout
            while time.time() < deadline:
                if not Path(root).exists(): return True
                time.sleep(0.5)
            return not Path(root).exists()
        try:
            kernel32=ctypes.windll.kernel32
            volume=f'\\\\.\\{root[0]}:'
            kernel32.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,wintypes.LPVOID,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
            kernel32.CreateFileW.restype=wintypes.HANDLE
            kernel32.DeviceIoControl.argtypes=[wintypes.HANDLE,wintypes.DWORD,wintypes.LPVOID,wintypes.DWORD,wintypes.LPVOID,wintypes.DWORD,ctypes.POINTER(wintypes.DWORD),wintypes.LPVOID]
            kernel32.DeviceIoControl.restype=wintypes.BOOL
            kernel32.CloseHandle.argtypes=[wintypes.HANDLE]
            kernel32.CloseHandle.restype=wintypes.BOOL
            # Lock/dismount requires GENERIC_READ | GENERIC_WRITE. Opening the
            # volume with access=0 made the former implementation silently fail.
            handle=kernel32.CreateFileW(volume,0xC0000000,3,None,3,0,None)
            if handle == wintypes.HANDLE(-1).value: raise OSError('Impossible d’ouvrir le volume pour éjection')
            kernel32.FlushFileBuffers(handle)
            returned=ctypes.c_ulong(0)
            # Lock and dismount the selected volume before requesting removable-media eject.
            locked=kernel32.DeviceIoControl(handle,0x00090018,None,0,None,0,ctypes.byref(returned),None)
            if locked:
                kernel32.DeviceIoControl(handle,0x00090020,None,0,None,0,ctypes.byref(returned),None)
            ok=kernel32.DeviceIoControl(handle,0x002D4808,None,0,None,0,ctypes.byref(returned),None)
            kernel32.CloseHandle(handle)
            if ok and unmounted(): return True
        except (OSError, AttributeError):
            pass
        # Fallback to the same Eject verb exposed by Windows Explorer.
        drive=f'{root[0]}:'
        command=(
            "$shell=New-Object -ComObject Shell.Application; "
            "$item=$shell.Namespace(17).ParseName('"+drive+"'); "
            "if($null -eq $item){exit 1}; "
            "$verb=@($item.Verbs() | Where-Object { $_.Name -match 'Eject|jecter' }) | Select-Object -First 1; "
            "if($null -eq $verb){exit 1}; $verb.DoIt()"
        )
        try:
            result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],capture_output=True,text=True,timeout=15)
            return result.returncode == 0 and unmounted()
        except (OSError, subprocess.SubprocessError):
            return False

    def go(self):
        root=self.drive_var.get(); ep=self.endpoint_var.get().strip(); key=self.auth_var.get().strip()
        if not root or not Path(root,'.kobo').exists(): messagebox.showerror(APP_NAME,'Sélectionne une Kobo.'); return
        st=device_status(root)
        if st['detection_warning']: messagebox.showerror(APP_NAME,st['detection_warning']); return
        if st['firmware'].startswith('5.'):
            messagebox.showerror(APP_NAME,'Firmware 5.x détecté. NickelMenu n’est actuellement pas supporté.'); return
        if not validate_endpoint(ep): messagebox.showerror(APP_NAME,'API endpoint invalide. Il doit commencer par http:// ou https://'); return
        if not validate_auth_key(key): messagebox.showerror(APP_NAME,'La clé Tailscale ne ressemble pas à une clé tskey-...'); return
        if st['tailscale']=='Absent' and not key:
            if not messagebox.askyesno(APP_NAME,'Aucune identité Tailscale détectée et aucune clé fournie. Continuer quand même ? Tu devras faire Tailscale - Login depuis NickelMenu.'):
                return
        if Path(root,'.kobo','KoboRoot.tgz').exists():
            if not messagebox.askyesno(APP_NAME,'Un KoboRoot.tgz est déjà présent. Le remplacer par celui de Kobo Tailscale Manager ?'):
                return
        try:
            md=manager_dir(root); md.mkdir(parents=True,exist_ok=True)
            self.write_menu_selection(root)
            manifest={'version':APP_VERSION,'timestamp':time.strftime('%Y-%m-%d %H:%M:%S'),'firmware':st['firmware'],'serial':st['serial'],'original_endpoint':st['endpoint'],'had_tailscale_state':Path(root,'.adds','tailscale','state','tailscaled.state').exists(),'had_nm_config':Path(root,'.adds','nm','tailscale-clara-colour').exists()}
            (md/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
            set_endpoint(root,ep)
            if key:
                Path(root,'.kobo','tailscale_auth_key.txt').write_text(key+'\n',encoding='ascii',newline='\n')
            else:
                Path(root,'.kobo','tailscale_auth_key.txt').unlink(missing_ok=True)
            menu_config=build_menu_config({key:var.get() for key,var in self.menu_vars.items()})
            create_tar_gz(Path(root,'.kobo','KoboRoot.tgz'),BOOTSTRAP,menu_config=menu_config)
            self.inspect()
            if self.auto_eject_var.get() and self.eject_drive(root):
                messagebox.showinfo(APP_NAME,'Kobo éjectée. Elle installera/mettra à jour NickelMenu + Tailscale au prochain redémarrage.')
            else:
                messagebox.showinfo(APP_NAME,'Prêt. Éjecte proprement la Kobo. Elle installera/mettra à jour NickelMenu + Tailscale puis redémarrera.\n\nLe mode par défaut est Tailscale - 10 min (pas d’autostart permanent).')
        except Exception as e:
            messagebox.showerror(APP_NAME,f'Échec : {e}')

    def _prepare_cleanup(self, full):
        root=self.drive_var.get()
        if not root or not Path(root,'.kobo').exists():
            messagebox.showerror(APP_NAME,'Sélectionne une Kobo.')
            return
        if full:
            question='Full uninstall restaure la configuration et supprime Tailscale, son état et notre intégration. Continuer ?'
            script=REVERT
        else:
            question='Restore Kobo config restaure api_endpoint et supprime uniquement notre intégration. L’état Tailscale est conservé. Continuer ?'
            script=RESTORE_ONLY
        if not messagebox.askyesno(APP_NAME,question): return
        try:
            restore_endpoint(root)
            Path(root,'.kobo','tailscale_auth_key.txt').unlink(missing_ok=True)
            create_tar_gz(Path(root,'.kobo','KoboRoot.tgz'),script,True)
            self.inspect()
            messagebox.showinfo(APP_NAME,'Opération préparée. Éjecte proprement la Kobo : le nettoyage sera effectué au prochain redémarrage.')
        except Exception as e:
            messagebox.showerror(APP_NAME,f'Nettoyage impossible : {e}')

    def restore_config(self):
        self._prepare_cleanup(False)

    def full_uninstall(self):
        self._prepare_cleanup(True)

    def revert(self):
        self.full_uninstall()

if __name__=='__main__':
    App().mainloop()
