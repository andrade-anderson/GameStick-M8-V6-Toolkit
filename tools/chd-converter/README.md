# PS1 CHD Recursive to Root Converter v4

A small Windows helper for converting PlayStation 1 `.chd` files to `BIN + CUE`
with **CHDMAN**.

It was made for collections where games may be stored several folders deep.
The script searches the selected folder recursively, converts the CHD files, and
places the resulting `.bin` and `.cue` files directly in the root folder.

## Features

- Recursively searches all subfolders for `.chd` files.
- Skips games that already have a complete `BIN + CUE` pair.
- Retries games that failed or are still missing.
- Never deletes the original CHD files.
- Never overwrites an existing complete conversion.
- Removes incomplete output from a previous failed attempt before retrying.
- Correctly handles filenames containing characters such as `[ ]`.
- Shows free disk space before conversions.
- Saves CHDMAN errors to `CHD_recursive_conversion_log_v4.txt`.

## Requirements

- Windows
- PowerShell
- `chdman.exe`

`chdman.exe` is distributed with **MAME** and is **not included in this repository**.
Download MAME from the official MAME website and copy `chdman.exe` next to the
converter files.

## Usage

Put these files in the root of your PS1 working folder:

```text
PS1 BR\
├── RUN_Convert_CHD_Recursive_to_Root_v4.bat
├── Convert_CHD_Recursive_to_Root_v4.ps1
├── chdman.exe
├── Game A\
├── Game B\
└── ...
```

Then double-click:

```text
RUN_Convert_CHD_Recursive_to_Root_v4.bat
```

Type `YES` when asked to confirm.

For example, a CHD located at:

```text
PS1 BR\Resident Evil\jogo\Resident Evil.chd
```

is converted to:

```text
PS1 BR\Resident Evil.bin
PS1 BR\Resident Evil.cue
```

The original CHD remains in its original folder.

## Safe re-run

The converter is designed to be run more than once. Existing complete
`BIN + CUE` pairs are reported as `SKIPPED`, while missing or failed games are
retried.

## Game Stick M8 v6 workflow

After conversion, copy the generated `.bin` and `.cue` files to:

```text
roms\ps1\
```

Then rebuild the external game database with the M8 v6 Toolkit.

## Notes

ZIP and RAR archives must be extracted first. This converter handles CHD files;
it does not extract ZIP or RAR archives.

