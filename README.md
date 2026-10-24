# League op.gg

Watches the League of Legends client during champ select and opens an
[op.gg](https://op.gg) tab for each player whose name the client shows.

It talks only to the local League Client (LCU) API on your own PC and uses only
the Python standard library.

## Requirements

- Windows
- Python 3.8 or newer
- The League of Legends client, installed and signed in

## Install

1. Install Python if you don't have it:

   ```powershell
   winget install Python.Python.3.12
   ```

   Open a new terminal afterwards and check it works:

   ```powershell
   py --version
   ```

2. Download the script:

   ```powershell
   git clone https://github.com/akshobhsingh/League-op-gg.git
   cd League-op-gg
   ```

   Or download `champ_select_opgg.py` from GitHub and put it in any folder.

## Setup

There is nothing to configure:

- The client is found automatically from the running `LeagueClientUx.exe`
  process. If that fails, the script falls back to
  `C:\Riot Games\League of Legends`.
- Your region (EUW, NA, KR, ...) is read from the client and mapped to the
  matching op.gg region.
- Pages open in your default browser.

## Run

Start the script before or after opening the League client:

```powershell
py champ_select_opgg.py
```

| Command | What it opens |
| --- | --- |
| `py champ_select_opgg.py` | Enemy players only |
| `py champ_select_opgg.py --allies` | Enemies and your teammates |
| `py champ_select_opgg.py --custom` | In custom games, players from the custom lobby's team lists |

Flags can be combined, for example `--allies --custom`.

Leave it running in the background. Every time you enter champ select it opens
a tab for each newly visible player, once per player. Press `Ctrl+C` to stop it.

Example output:

```
[18:02:11] Waiting for the League client...
[18:02:13] Connected to client (region: euw). Waiting for champ select...
[18:03:40] Phase: ChampSelect
[18:03:42] Opening op.gg for Player#EUW
```

## Notes

- The script only opens players the client already shows you. Players whose
  names are hidden in champ select are skipped.
- If the client is closed or restarted, the script reconnects on its own.
- If `py` isn't found, try `python` instead, or reinstall Python with
  "Add python.exe to PATH" ticked.
