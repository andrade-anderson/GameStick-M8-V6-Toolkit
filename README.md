## v3.0.1 update

Mega Drive / Genesis database scanning now recognizes:

- `.bin`
- `.md`
- `.gen`
- `.smd`

All four formats use the existing M8 Mega Drive mapping:

```text
class_type = 5
emu_type   = 2
```

After adding or removing ROMs, run:

```text
3 - Build / rebuild game database
```

Compressed `.zip` / `.rar` collections must be extracted first before placing
the actual Mega Drive ROM files in `roms\md\`.


# Game Stick M8 v6 Toolkit v3 — All-in-One

A single-program toolkit for compatible **Game Stick Lite M8 v6** SD cards.

v3 combines the previous DATA03 patcher and DBMaker into one application.

## Confirmed firmware

Confirmed working during development:

```text
M8-20231122-release-v6.0
```

The toolkit accepts firmware matching:

```text
M8-YYYYMMDD-release-v6.0
```

but only when the expected internal DATA03 structure is also detected.

This is **not** a universal Game Stick tool.

Do not use it on unrelated families such as:

```text
Q2
Q3
M15
X2
M88
```

unless that firmware has been separately analyzed and supported.

---

# Main improvement in v3

The end user no longer needs to place different scripts in different folders.

The recommended final release is one Windows executable:

```text
GameStick_M8_V6_Toolkit_v3.exe
```

Place it in the SD-card root:

```text
SD CARD
│
├── GameStick_M8_V6_Toolkit_v3.exe
├── download
├── res
│   └── DATA03
├── roms
└── save
```

Run it and the toolkit automatically detects:

```text
res\DATA03
roms\
roms\img\
```

---

# Interactive menu

The program shows:

```text
1 - Check firmware compatibility
2 - Patch DATA03
3 - Build / rebuild game database
4 - Full setup
5 - Restore original DATA03 backup
6 - Show detected SD-card path
0 - Exit
```

## Option 1 — Check firmware compatibility

Read-only.

The toolkit checks:

- DATA03 exists
- compatible embedded EXT filesystem exists
- `/version` exists
- version matches `M8-YYYYMMDD-release-v6.0`
- `/db/m8_game_list.db` exists
- it is a compatible symbolic link
- its current internal database target exists

If any required check fails, the program reports the firmware as incompatible.

## Option 2 — Patch DATA03

The toolkit redirects:

```text
/db/m8_game_list.db
```

to:

```text
/mnt/roms/simple_games_m8_2w.db
```

Before modifying DATA03 it creates:

```text
res\DATA03.before_external_db.bak
```

If DATA03 is already patched, no second patch is applied.

## Option 3 — Build / rebuild game database

The toolkit scans supported ROM folders and creates:

```text
roms\simple_games_m8_2w.db
```

If an older external database exists, it creates:

```text
roms\simple_games_m8_2w.db.bak
```

The new SQLite database is verified before replacing the previous file.

## Option 4 — Full setup

Recommended for a new compatible card.

It performs:

```text
Detect SD card
↓
Check firmware compatibility
↓
Create DATA03 backup
↓
Patch DATA03
↓
Fix ROM filenames with extra dots
↓
Rename matching covers
↓
Update PS1 CUE references
↓
Build game database
↓
Verify DATA03 link and database
```

## Option 5 — Restore original DATA03

Restores:

```text
DATA03.before_external_db.bak
```

back to:

```text
DATA03
```

Before restoring, the currently patched DATA03 is preserved as:

```text
DATA03.before_restore.bak
```

---

# Automatic SD-card detection

The toolkit checks:

1. the folder containing the EXE;
2. the current folder;
3. parent folders;
4. Windows drive letters.

A valid root must contain:

```text
res\DATA03
roms\
```

If several compatible cards are found, the user is asked which one to use.

You can also specify the root manually:

```bat
GameStick_M8_V6_Toolkit_v3.exe --root E:\
```

---

# Extra-dot filename repair

ROM files such as:

```text
Super.Mario.World.sfc
```

are automatically renamed to:

```text
SuperMarioWorld.sfc
```

The extension separator remains unchanged.

Matching cover images under `roms\img` are renamed too.

Example:

```text
roms\sfc\Super.Mario.World.sfc
roms\img\sfc\Super.Mario.World.png
```

becomes:

```text
roms\sfc\SuperMarioWorld.sfc
roms\img\sfc\SuperMarioWorld.png
```

If the target filename already exists, nothing is overwritten.

---

# PS1 BIN/CUE support

If a PS1 BIN filename is changed, matching references inside `.cue` files are updated.

The builder also tries to avoid listing every BIN track from multi-track games as a separate title.

Supported PS1 formats:

```text
.iso
.img
.pbp
.bin
```

---

# Supported systems

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

# Command-line modes

Compatibility check:

```bat
GameStick_M8_V6_Toolkit_v3.exe --check
```

Patch:

```bat
GameStick_M8_V6_Toolkit_v3.exe --patch
```

Build database:

```bat
GameStick_M8_V6_Toolkit_v3.exe --build
```

Full setup:

```bat
GameStick_M8_V6_Toolkit_v3.exe --full
```

Restore:

```bat
GameStick_M8_V6_Toolkit_v3.exe --restore
```

Manual SD-card path:

```bat
GameStick_M8_V6_Toolkit_v3.exe --root E:\ --check
```

For automated testing, `--yes` skips confirmation:

```bat
GameStick_M8_V6_Toolkit_v3.exe --root E:\ --full --yes
```

Use `--yes` only when you already know the correct card was selected.

---

# Build the Windows EXE

The repository includes:

```text
BUILD_WINDOWS_EXE.bat
```

Run it on Windows.

It installs PyInstaller and creates:

```text
dist\GameStick_M8_V6_Toolkit_v3.exe
```

Once built, the end user only needs the `.exe`.

Python is not required on the end user's computer.

---

# GitHub Actions

The repository also contains:

```text
.github\workflows\build-windows-exe.yml
```

The workflow can automatically build the Windows EXE:

- manually from the GitHub **Actions** tab;
- automatically when a version tag such as `v3.0` is pushed.

The generated EXE is uploaded as a GitHub Actions artifact.

---

# Recommended GitHub release contents

For a public release, publish:

```text
GameStick_M8_V6_Toolkit_v3.exe
```

as the main download.

Keep the Python source code in the repository so users can review the implementation.

---

# Safety notes

- Make a backup before experimenting with firmware.
- Never force a patch after an incompatible result.
- External appearance does not identify a Game Stick firmware family.
- Two visually identical sticks can contain different boards and firmware.
- Safely eject the SD card before inserting it into the Game Stick.
- The project does not provide ROMs or copyrighted game content.
- The DATA03 patch modifies an embedded filesystem and is intentionally limited to firmware that passes all compatibility checks.

---

# Disclaimer

Use at your own risk.

This is an unofficial community project and is not affiliated with the Game Stick manufacturer or firmware authors.
