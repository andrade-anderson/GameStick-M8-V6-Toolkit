# Game Stick Lite M8 v6 Toolkit

A small Python toolkit for compatible **Game Stick Lite M8 v6** firmware.

It was created to solve a common problem on M8 v6 sticks: after adding or replacing ROM files, the console may not automatically rebuild the game list. This toolkit redirects the firmware to an external SQLite game database on the SD card and provides a database builder that scans the ROM folders.

It also fixes ROM filenames that contain **more than one dot**, renames matching cover images, and updates PS1 `.cue` references when needed.

> **Important:** This is **not** a universal Game Stick tool. It is intended only for compatible **M8 v6** firmware using the database layout described below.

## Confirmed firmware

The toolkit was tested successfully on real hardware whose internal `/version` reports:

```text
M8-20231122-release-v6.0
```

The patcher is designed to accept firmware matching this pattern:

```text
M8-YYYYMMDD-release-v6.0
```

Examples that may be compatible:

```text
M8-20231021-release-v6.0
M8-20231122-release-v6.0
```

However, the version string alone is **not enough**. Before changing anything, the patcher checks the internal `DATA03` structure and refuses to continue if the required M8 v6 database layout is not found.

### Do not use this toolkit on unrelated families

Examples include:

```text
Q2
Q3
M15
X2
M88
```

or any firmware that does not use the same M8 v6 internal database structure.

---

## Files included

```text
Patch_DATA03_M8_V6_v2.py
DBMaker_M8_V6_v2.py
1_CHECK_AND_PATCH_DATA03.bat
2_BUILD_GAME_DATABASE.bat
README.md
```

### `Patch_DATA03_M8_V6_v2.py`

Checks the firmware and, if compatible, redirects:

```text
/db/m8_game_list.db
```

to:

```text
/mnt/roms/simple_games_m8_2w.db
```

### `DBMaker_M8_V6_v2.py`

Scans compatible ROM folders and generates:

```text
roms/simple_games_m8_2w.db
```

It also repairs ROM filenames containing extra dots and renames matching cover images.

### Batch files

The two `.bat` files are Windows launchers. Each `.bat` file must stay in the **same folder as its matching `.py` file**.

---

## Requirements

- Windows
- Python 3
- A compatible Game Stick Lite M8 v6 SD card
- Enough free space for a `DATA03` backup
- No external Python packages are required

The scripts use only Python's standard library.

To check whether Python is installed, open Command Prompt and run:

```bat
python --version
```

If that does not work, try:

```bat
py --version
```

---

## Expected SD card structure

A typical compatible card looks similar to this:

```text
SD CARD
│
├── download
│
├── res
│   ├── DATA01
│   ├── DATA02
│   ├── DATA03
│   ├── DATA04
│   ├── DATA05
│   ├── DATA06
│   ├── settings
│   └── system.img
│
├── roms
│   ├── atari
│   ├── gb
│   ├── gba
│   ├── gbc
│   ├── img
│   ├── mame
│   ├── md
│   ├── nes
│   ├── ps1
│   ├── res
│   └── sfc
│
└── save
```

Your card does not need every ROM folder, but the internal firmware structure must be compatible.

---

# Step 1 — Check and patch DATA03

Copy these two files into the SD card's **`res`** folder:

```text
Patch_DATA03_M8_V6_v2.py
1_CHECK_AND_PATCH_DATA03.bat
```

They should be next to `DATA03`:

```text
SD CARD
└── res
    ├── DATA03
    ├── Patch_DATA03_M8_V6_v2.py
    └── 1_CHECK_AND_PATCH_DATA03.bat
```

Then double-click:

```text
1_CHECK_AND_PATCH_DATA03.bat
```

The patcher first performs a **read-only diagnostic**.

A compatible card should show a report similar to:

```text
==============================================================
GAME STICK M8 V6 - COMPATIBILITY REPORT
==============================================================
DATA03 found:              YES
EXT2 structure detected:   YES
Firmware version:          M8-20231122-release-v6.0
M8 v6 version accepted:    YES
/db/m8_game_list.db:       FOUND
Symbolic link format:      OK
Current database target:   game_list_64_2w_add_ps1.db
Current database verified: YES
--------------------------------------------------------------
RESULT: COMPATIBLE - SAFE TO PATCH
==============================================================
```

If the result is:

```text
RESULT: NOT COMPATIBLE - NO CHANGES WILL BE MADE
```

**Stop there. Do not try to force the patch.**

If the card is compatible, the program asks:

```text
Apply patch now? Type YES to continue:
```

Type exactly:

```text
YES
```

and press Enter.

Before changing `DATA03`, the tool creates:

```text
DATA03.before_external_db.bak
```

After a successful patch, the firmware will use:

```text
/mnt/roms/simple_games_m8_2w.db
```

as its game database.

## Diagnostic-only mode

If you only want to test compatibility without applying the patch, open Command Prompt inside the `res` folder and run:

```bat
python Patch_DATA03_M8_V6_v2.py --check
```

If `python` is not recognized, try:

```bat
py Patch_DATA03_M8_V6_v2.py --check
```

This performs the compatibility check and exits without changing `DATA03`.

---

# Step 2 — Build the game database

Copy these two files into the SD card's **`roms`** folder:

```text
DBMaker_M8_V6_v2.py
2_BUILD_GAME_DATABASE.bat
```

The structure should look like:

```text
SD CARD
└── roms
    ├── atari
    ├── gb
    ├── gba
    ├── gbc
    ├── img
    ├── mame
    ├── md
    ├── nes
    ├── ps1
    ├── sfc
    ├── DBMaker_M8_V6_v2.py
    └── 2_BUILD_GAME_DATABASE.bat
```

Then double-click:

```text
2_BUILD_GAME_DATABASE.bat
```

The script will:

1. Detect compatible console folders.
2. Find ROM filenames containing extra dots.
3. Rename those ROM files.
4. Rename matching cover images under `roms/img`.
5. Update PS1 `.cue` references when a referenced `.bin` is renamed.
6. Scan the ROM folders.
7. Generate a new SQLite database.
8. Save it as `roms/simple_games_m8_2w.db`.

If an older generated database already exists, the tool creates:

```text
simple_games_m8_2w.db.bak
```

before replacing it.

---

## Extra-dot filename repair

Some M8 database builders can have problems with ROM filenames containing multiple dots.

For example:

```text
Super.Mario.World.sfc
```

will be renamed to:

```text
SuperMarioWorld.sfc
```

Only the extra dots are removed. The extension separator is preserved.

The same applies to matching cover images.

Example:

```text
roms/sfc/Super.Mario.World.sfc
roms/img/sfc/Super.Mario.World.png
```

becomes:

```text
roms/sfc/SuperMarioWorld.sfc
roms/img/sfc/SuperMarioWorld.png
```

The image search is recursive under:

```text
roms/img
```

so matching covers may be inside console-specific subfolders.

---

## Filename collision protection

The script does **not** overwrite files when removing dots would create a duplicate filename.

Example:

```text
Mario.World.sfc
MarioWorld.sfc
```

In this case, the first file cannot safely be renamed because the target name already exists.

The script prints a warning and leaves the original file unchanged.

---

## PS1 BIN/CUE handling

For PlayStation 1 games, the toolkit supports:

```text
.iso
.img
.pbp
.bin
```

When a `.bin` filename is changed because it contains extra dots, the script also updates the corresponding reference inside `.cue` files.

Example:

Before:

```text
Game.Name.bin
Game.Name.cue
```

with the `.cue` containing:

```text
FILE "Game.Name.bin" BINARY
```

After the automatic rename:

```text
GameName.bin
GameName.cue
```

and the reference becomes:

```text
FILE "GameName.bin" BINARY
```

For multi-track BIN/CUE games, the database builder tries to avoid listing every track as a separate game.

---

## Supported systems and extensions

| System | Folder | Extensions | class_type | emu_type |
|---|---|---|---:|---:|
| MAME | `mame` | `.zip` | 0 | 4 |
| NES / Famicom | `nes` | `.nes` | 1 | 0 |
| Game Boy | `gb` | `.gb` | 2 | 1 |
| Game Boy Advance | `gba` | `.gba` | 3 | 1 |
| Game Boy Color | `gbc` | `.gbc` | 4 | 1 |
| Mega Drive / Genesis | `md` | `.bin` | 5 | 2 |
| SNES / Super Famicom | `sfc` | `.sfc`, `.smc` | 6 | 3 |
| PlayStation 1 | `ps1` | `.iso`, `.img`, `.pbp`, `.bin` | 7 | 5 |
| Atari 2600 | `atari` | `.a26` | 8 | 6 |
| Atari 7800 | `atari` | `.a78` | 8 | 7 |

---

## Generated database format

The output is an SQLite database containing table:

```text
tbl_all
```

with these fields:

```text
game_id
en_name
cn_name
cn_match
suffix
class_type
emu_type
img_name
long_en_name
```

Output path:

```text
roms/simple_games_m8_2w.db
```

---

## Running manually from Command Prompt

Instead of the `.bat` files, you can run the Python scripts manually.

For the patcher:

```bat
cd /d E:\res
python Patch_DATA03_M8_V6_v2.py
```

For the database builder:

```bat
cd /d E:\roms
python DBMaker_M8_V6_v2.py
```

Replace `E:` with the actual drive letter of your SD card.

If `python` is not recognized, use `py` instead.

---

## Restoring the original DATA03

If you need to undo the DATA03 patch:

1. Remove the SD card from the Game Stick.
2. Open the `res` folder on a computer.
3. Keep a copy of the patched `DATA03` if you want to investigate it later.
4. Replace `DATA03` with the backup `DATA03.before_external_db.bak`.
5. Rename the restored backup back to `DATA03`.

---

## Updating the game list later

Once `DATA03` has already been successfully patched, you normally do **not** need to patch it again just because you added more games.

To update the list:

1. Add or remove ROMs in the appropriate folders.
2. Add matching cover images if desired.
3. Run `2_BUILD_GAME_DATABASE.bat` again.

This rebuilds:

```text
simple_games_m8_2w.db
```

from the current ROM folders.

---

## Important safety notes

- Back up important SD card files before experimenting.
- Never force the patch on firmware that reports `NOT COMPATIBLE`.
- The patcher modifies the internal filesystem stored inside `DATA03`.
- The automatically created `DATA03` backup requires additional free space on the SD card.
- Firmware names alone do not guarantee compatibility.
- A Game Stick may look identical externally and still use completely different hardware or firmware.
- Safely eject the SD card from Windows before inserting it into the Game Stick.
- This toolkit does not provide ROM files or copyrighted game content.

---

## Troubleshooting

### `python` is not recognized

Try:

```bat
py Patch_DATA03_M8_V6_v2.py
```

or:

```bat
py DBMaker_M8_V6_v2.py
```

If neither command works, install Python 3.

### `DATA03 was not found`

Make sure `Patch_DATA03_M8_V6_v2.py` is inside the SD card's `res` folder, next to `DATA03`.

### `RESULT: NOT COMPATIBLE`

Do not patch the file. The stick may use a different M8 revision or a completely different firmware layout.

### Games do not appear

Check that this file was created successfully:

```text
roms/simple_games_m8_2w.db
```

Also verify that the ROM files are in the correct folders and use supported extensions.

### Game appears but cover does not

The cover filename should match the ROM filename stem.

Example:

```text
roms/nes/MegaMan2.nes
roms/img/nes/MegaMan2.png
```

---

## Recommended first test on an unconfirmed firmware revision

1. Run the patcher in diagnostic-only mode.
2. Confirm that every compatibility check passes.
3. Keep an additional copy of `DATA03`.
4. Add only a few test ROMs.
5. Build the database.
6. Test the SD card in the Game Stick.
7. Only after successful testing, add the full ROM collection.

---

## Project status

Confirmed working on:

```text
M8-20231122-release-v6.0
```

Other `M8-YYYYMMDD-release-v6.0` revisions should be considered **potentially compatible only when the diagnostic report passes all checks**.

If you test another revision successfully, please post the internal `/version` value and results so compatibility can be documented for other users.

---

## Disclaimer

Use at your own risk.

This is an unofficial community tool and is not affiliated with the Game Stick manufacturer or firmware authors. Always keep backups before modifying firmware-related files.
