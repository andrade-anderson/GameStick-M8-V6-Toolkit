# PS1 CHD Recursive to Root Converter v4

A small Windows helper for converting PlayStation 1 `.chd` files to `BIN + CUE`
with **CHDMAN**.

It was designed for PS1 collections where games may be stored several folders
deep. The converter searches the selected folder recursively, converts every
CHD it finds, and places the generated `.bin` and `.cue` files directly in the
root folder.

## Features

- Recursively searches all subfolders for `.chd` files.
- Converts CHD files to `BIN + CUE`.
- Places converted files directly in the root working folder.
- Skips games that already have a complete `BIN + CUE` pair.
- Retries games that failed or are still missing.
- Never deletes the original CHD files.
- Never overwrites an existing complete conversion.
- Removes incomplete output from a previous failed attempt before retrying.
- Correctly handles filenames containing characters such as `[ ]`.
- Shows free disk space before conversions.
- Saves CHDMAN errors to `CHD_recursive_conversion_log_v4.txt`.
- Includes an optional helper to obtain `chdman.exe` automatically from the
  official MAME GitHub release.

## Files

```text
chd-converter/
├── Convert_CHD_Recursive_to_Root_v4.ps1
├── RUN_Convert_CHD_Recursive_to_Root_v4.bat
├── GET_CHDMAN.bat
├── Get_CHDMAN.ps1
└── README.md
```

`chdman.exe` is intentionally **not included in this repository**.

## Requirements

- Windows
- PowerShell
- 7-Zip
- CHDMAN

CHDMAN is distributed with **MAME**.

You can obtain it manually from the official MAME release, or use the included
automatic helper.

## Getting CHDMAN automatically

The easiest method is:

1. Install **7-Zip**.
2. Keep `GET_CHDMAN.bat` and `Get_CHDMAN.ps1` in the same folder as the converter.
3. Double-click:

```text
GET_CHDMAN.bat
```

4. The helper will:
   - check the latest official `mamedev/mame` GitHub release;
   - detect whether Windows is x64 or ARM64;
   - download the matching official MAME package;
   - extract it with 7-Zip;
   - copy only `chdman.exe` into the converter folder.

If `chdman.exe` already exists, the helper asks before replacing it.

After this step, the folder should look like:

```text
chd-converter/
├── Convert_CHD_Recursive_to_Root_v4.ps1
├── RUN_Convert_CHD_Recursive_to_Root_v4.bat
├── GET_CHDMAN.bat
├── Get_CHDMAN.ps1
├── chdman.exe
└── README.md
```

## Converting a PS1 collection

Place the converter files and `chdman.exe` in the **root of your PS1 working
folder**.

Example:

```text
PS1 BR\
├── RUN_Convert_CHD_Recursive_to_Root_v4.bat
├── Convert_CHD_Recursive_to_Root_v4.ps1
├── GET_CHDMAN.bat
├── Get_CHDMAN.ps1
├── chdman.exe
├── Alundra\
├── Atlantis\
├── Diablo\
├── Resident Evil 2\
└── ...
```

Then double-click:

```text
RUN_Convert_CHD_Recursive_to_Root_v4.bat
```

Type:

```text
YES
```

when asked to confirm.

## Recursive folder support

The CHD does not need to be in the root folder.

For example:

```text
PS1 BR\
└── Resident Evil\
    └── jogo\
        └── Resident Evil.chd
```

will be converted to:

```text
PS1 BR\
├── Resident Evil.bin
├── Resident Evil.cue
└── Resident Evil\
    └── jogo\
        └── Resident Evil.chd
```

The original `.chd` remains where it was.

## Safe re-run

The converter is designed to be run multiple times.

If this already exists:

```text
Game.bin
Game.cue
```

the game is reported as:

```text
SKIPPED
```

and is not converted again.

If only one incomplete file from a previous failed attempt exists, the converter
removes that incomplete output and retries the CHD.

## ZIP and RAR files

This converter does **not** extract `.zip` or `.rar` archives.

Extract ZIP/RAR files first with 7-Zip.

After extraction, the converter can find `.chd` files even if they are several
folders deep.

## Log file

The converter creates:

```text
CHD_recursive_conversion_log_v4.txt
```

The log records successful conversions, skipped files, failed conversions, and
CHDMAN error information.

## Game Stick M8 v6 workflow

After conversion, copy the generated `.bin` and `.cue` files to:

```text
roms\ps1\
```

on the Game Stick microSD card.

Then run the **Game Stick M8 v6 Toolkit** and choose:

```text
3 - Build / rebuild game database
```

The database must be rebuilt whenever games are added or removed.

You do **not** need to patch `DATA03` again if it is already patched.

## Recommended workflow

```text
1. Extract ZIP/RAR files with 7-Zip
2. Run GET_CHDMAN.bat once
3. Run RUN_Convert_CHD_Recursive_to_Root_v4.bat
4. Copy generated BIN+CUE files to roms\ps1\
5. Run option 3 in the Game Stick M8 v6 Toolkit
6. Safely eject the microSD card and test it in the Game Stick
```

## CHDMAN / MAME notice

CHDMAN is part of the MAME project and is not included in this repository.

The automatic downloader obtains CHDMAN from the official `mamedev/mame`
GitHub release instead of redistributing the MAME binary as part of this
project.

This project is not affiliated with or endorsed by MAMEdev.
