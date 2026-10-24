"""Watch the League client during champ select and open op.gg pages for
enemy players whose names the client shows.

Uses only the local League Client (LCU) API and the Python standard library.
Run:  python champ_select_opgg.py           (enemies only)
      python champ_select_opgg.py --allies  (also open teammates)
      python champ_select_opgg.py --custom  (custom games: use the lobby's player list)
"""

import argparse
import base64
import json
import ssl
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path

POLL_SECONDS = 2

# LCU region -> op.gg region slug
OPGG_REGIONS = {
    "NA": "na", "EUW": "euw", "EUNE": "eune", "KR": "kr", "JP": "jp",
    "BR": "br", "LAN": "lan", "LAS": "las", "OCE": "oce", "TR": "tr",
    "RU": "ru", "ME1": "me", "SG2": "sg", "TW2": "tw", "VN2": "vn",
    "PH2": "ph", "TH2": "th",
}

# The client uses a self-signed certificate on localhost
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


def find_lockfile():
    """Locate the client's lockfile via the running LeagueClientUx process."""
    cmd = [
        "powershell", "-NoProfile", "-Command",
        "(Get-CimInstance Win32_Process -Filter \"name='LeagueClientUx.exe'\").CommandLine",
    ]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    for arg in out.split('" "'):
        arg = arg.strip('" \r\n')
        if arg.startswith("--install-directory="):
            path = Path(arg.split("=", 1)[1]) / "lockfile"
            if path.exists():
                return path
    for path in (Path(r"C:\Riot Games\League of Legends\lockfile"),):
        if path.exists():
            return path
    return None


class LCU:
    def __init__(self, lockfile):
        # lockfile format: name:pid:port:password:protocol
        _, _, port, password, protocol = lockfile.read_text().split(":")
        self.base = f"{protocol}://127.0.0.1:{port}"
        token = base64.b64encode(f"riot:{password}".encode()).decode()
        self.headers = {"Authorization": f"Basic {token}", "Accept": "application/json"}

    def get(self, endpoint):
        req = urllib.request.Request(self.base + endpoint, headers=self.headers)
        try:
            with urllib.request.urlopen(req, context=SSL_CTX, timeout=5) as resp:
                return json.load(resp)
        except urllib.error.HTTPError:
            return None


def log(message):
    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)


def opgg_url(region, game_name, tag_line):
    riot_id = urllib.parse.quote(f"{game_name}-{tag_line}")
    return f"https://op.gg/lol/summoners/{region}/{riot_id}"


def visible_riot_id(lcu, player):
    """Return (gameName, tagLine) if the client exposes this player's name."""
    if player.get("nameVisibilityType") == "HIDDEN":
        return None
    name, tag = player.get("gameName"), player.get("tagLine")
    if name and tag:
        return name, tag
    # Older client payloads only carry an id; resolve it if it isn't hidden
    summoner_id = player.get("summonerId")
    if summoner_id:
        summoner = lcu.get(f"/lol-summoner/v1/summoners/{summoner_id}") or {}
        if summoner.get("gameName") and summoner.get("tagLine"):
            return summoner["gameName"], summoner["tagLine"]
    return None


def custom_lobby_players(lcu, allies):
    """In custom games champ select hides enemies, but the lobby lists both teams."""
    config = (lcu.get("/lol-lobby/v2/lobby") or {}).get("gameConfig", {})
    if not config.get("isCustom"):
        return []
    me = (lcu.get("/lol-summoner/v1/current-summoner") or {}).get("puuid")
    team100 = config.get("customTeam100") or []
    team200 = config.get("customTeam200") or []
    if any(p.get("puuid") == me for p in team100):
        mine, theirs = team100, team200
    else:
        mine, theirs = team200, team100
    members = theirs + (mine if allies else [])
    players = []
    for member in members:
        puuid = member.get("puuid")
        if member.get("isBot") or not puuid or puuid == me:
            continue
        summoner = lcu.get(f"/lol-summoner/v2/summoners/puuid/{puuid}") or {}
        players.append({"gameName": summoner.get("gameName"), "tagLine": summoner.get("tagLine")})
    return players


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--allies", action="store_true", help="also open teammates' pages")
    parser.add_argument("--custom", action="store_true",
                        help="in custom games, read players from the custom lobby")
    args = parser.parse_args()

    lcu = None
    opened = set()
    last_phase = None
    region = None

    log("Waiting for the League client...")
    while True:
        try:
            if lcu is None:
                lockfile = find_lockfile()
                if lockfile is None:
                    time.sleep(POLL_SECONDS)
                    continue
                lcu = LCU(lockfile)
                lcu_region = (lcu.get("/riotclient/region-locale") or {}).get("region", "")
                region = OPGG_REGIONS.get(lcu_region.upper(), lcu_region.lower())
                log(f"Connected to client (region: {region}). Waiting for champ select...")

            phase = lcu.get("/lol-gameflow/v1/gameflow-phase")
            if phase != last_phase:
                log(f"Phase: {phase}")
                if phase == "ChampSelect":
                    opened.clear()
                last_phase = phase

            if phase == "ChampSelect":
                session = lcu.get("/lol-champ-select/v1/session") or {}
                players = list(session.get("theirTeam", []))
                if args.allies:
                    local_cell = session.get("localPlayerCellId")
                    players += [p for p in session.get("myTeam", []) if p.get("cellId") != local_cell]
                if args.custom and session.get("isCustomGame"):
                    players += custom_lobby_players(lcu, args.allies)
                for player in players:
                    riot_id = visible_riot_id(lcu, player)
                    if riot_id and riot_id not in opened:
                        opened.add(riot_id)
                        log(f"Opening op.gg for {riot_id[0]}#{riot_id[1]}")
                        webbrowser.open_new_tab(opgg_url(region, *riot_id))
        except (urllib.error.URLError, ConnectionError, OSError, ValueError):
            # Client closed or restarted; reconnect on the next loop
            if lcu is not None:
                log("Lost connection to the client, retrying...")
            lcu = None
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
