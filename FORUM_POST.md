# Game Stick Lite M8 v6 — External Game Database Builder / DATA03 Patcher

I put together a small Python toolkit for compatible **Game Stick Lite M8 v6** firmware.

The main purpose is to make it easier to add or replace ROM files and rebuild the game list without relying on the old DBMaker packages that are difficult to find or download.

## Confirmed working

Tested successfully on real hardware with internal firmware version:

```text
M8-20231122-release-v6.0
```

The patcher accepts the general version pattern:

```text
M8-YYYYMMDD-release-v6.0
```

but it does **not** patch based on the version name alone. It first checks the internal `DATA03` filesystem structure, `/version`, `/db/m8_game_list.db`, the symbolic-link format, and the currently referenced internal database.

If the structure is not compatible, it stops without making changes.

## What it does

### 1. DATA03 compatibility checker / patcher

It redirects:

```text
/db/m8_game_list.db
```

to:

```text
/mnt/roms/simple_games_m8_2w.db
```

Before changing anything it prints a compatibility report and requires the user to type `YES`. It also creates a backup of `DATA03`.

There is also a check-only mode:

```bat
python Patch_DATA03_M8_V6_v2.py --check
```

### 2. Game database builder

It scans the normal M8 v6 folders (`nes`, `sfc`, `md`, `gba`, `gbc`, `gb`, `ps1`, `mame`, `atari`) and generates:

```text
roms/simple_games_m8_2w.db
```

It also automatically fixes ROM filenames containing extra dots.

Example:

```text
Super.Mario.World.sfc
```

becomes:

```text
SuperMarioWorld.sfc
```

If there is a matching cover image under `roms/img`, the cover is renamed too.

For PS1 BIN/CUE games, references inside `.cue` files are updated when a referenced `.bin` file is renamed.

The tool also protects against filename collisions and will not overwrite an existing file.

## Windows usage

The ZIP contains two `.bat` launchers.

Put:

```text
Patch_DATA03_M8_V6_v2.py
1_CHECK_AND_PATCH_DATA03.bat
```

inside the SD card's:

```text
res
```

folder, next to `DATA03`.

Run the first batch file and follow the compatibility report.

Then put:

```text
DBMaker_M8_V6_v2.py
2_BUILD_GAME_DATABASE.bat
```

inside:

```text
roms
```

and run the second batch file.

Python 3 is required. No external Python modules are needed.

## Important

This is **not** intended for every stick sold as “Game Stick 4K Lite”.

Do not use it on unrelated firmware/hardware families such as Q2, Q3, M15, X2, M88, etc.

Externally identical sticks can contain different boards and completely different firmware.

The only firmware revision currently confirmed by real-device testing is:

```text
M8-20231122-release-v6.0
```

Other M8 v6 revisions should only be tried if the diagnostic tool reports:

```text
RESULT: COMPATIBLE - SAFE TO PATCH
```

Please read the full `README.md` before using the toolkit. It includes the folder layout, step-by-step instructions, backup/restore procedure, supported extensions, troubleshooting, PS1 handling, and safety notes.

If anyone tests another M8 v6 firmware revision successfully, please post the internal `/version` value and the result so compatibility can be documented.
