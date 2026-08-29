#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Game Stick Lite M8 v6 - external game database builder.

Put this file inside the SD card "roms" folder and run:
    python DBMaker_M8_V6_v2.py

Features:
- Builds simple_games_m8_2w.db.
- Detects ROM names containing extra dots.
- Removes extra dots while preserving the extension dot.
- Renames matching cover images under roms/img.
- Updates PS1 .cue references if a referenced .bin file is renamed.
- Avoids overwriting files when a rename would cause a collision.
"""

from pathlib import Path
import re
import shutil
import sqlite3
import sys

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "simple_games_m8_2w.db"
TEMP = ROOT / "simple_games_m8_2w.db.tmp"

SYSTEMS = {
    "mame":  {".zip": (0, 4)},
    "nes":   {".nes": (1, 0)},
    "gb":    {".gb":  (2, 1)},
    "gba":   {".gba": (3, 1)},
    "gbc":   {".gbc": (4, 1)},
    "md":    {".bin": (5, 2)},
    "sfc":   {".sfc": (6, 3), ".smc": (6, 3)},
    "ps1":   {".iso": (7, 5), ".img": (7, 5), ".pbp": (7, 5), ".bin": (7, 5)},
    "atari": {".a26": (8, 6), ".a78": (8, 7)},
}

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}

CREATE_SQL = """
CREATE TABLE tbl_all (
    game_id INTEGER,
    en_name CHAR (128),
    cn_name CHAR (128),
    cn_match CHAR (128),
    suffix CHAR (8),
    class_type INTEGER,
    emu_type INTEGER,
    img_name CHAR (64),
    long_en_name CHAR (168)
)
"""


def remove_extra_dots(stem: str) -> str:
    return stem.replace(".", "").strip()


def replace_case_insensitive(text: str, old: str, new: str) -> str:
    return re.sub(re.escape(old), lambda _: new, text, flags=re.IGNORECASE)


def update_cue_references(folder: Path, rename_map: dict[str, str]):
    if not rename_map:
        return

    for cue in list(folder.iterdir()):
        if not cue.is_file() or cue.suffix.lower() != ".cue":
            continue

        try:
            original = cue.read_text(encoding="utf-8-sig", errors="ignore")
        except Exception:
            continue

        changed = original

        for old_name, new_name in rename_map.items():
            changed = replace_case_insensitive(changed, old_name, new_name)

        if changed != original:
            cue.write_text(changed, encoding="utf-8")


def rename_matching_covers(old_stem: str, new_stem: str):
    img_root = ROOT / "img"

    if not img_root.exists():
        return []

    renamed = []

    for img in list(img_root.rglob("*")):
        if not img.is_file() or img.suffix.lower() not in IMAGE_EXTS:
            continue

        if img.stem.casefold() != old_stem.casefold():
            continue

        target = img.with_name(new_stem + img.suffix)

        if target == img:
            continue

        if target.exists():
            print(
                "  WARNING: cover not renamed because target already exists: "
                f"{target.relative_to(ROOT)}"
            )
            continue

        img.rename(target)
        renamed.append((img, target))

    return renamed


def rename_files_with_extra_dots(folder_name: str, folder: Path):
    allowed = set(SYSTEMS[folder_name].keys())

    if folder_name == "ps1":
        allowed.add(".cue")

    candidates = [
        p for p in folder.iterdir()
        if p.is_file()
        and p.suffix.lower() in allowed
        and "." in p.stem
    ]

    plan = []
    name_map = {}

    for src in candidates:
        new_stem = remove_extra_dots(src.stem)

        if not new_stem:
            print("  WARNING: invalid filename, skipped:", src.name)
            continue

        dst = src.with_name(new_stem + src.suffix)

        if dst.exists() and dst.resolve() != src.resolve():
            print(
                f"  WARNING: cannot rename '{src.name}' because "
                f"'{dst.name}' already exists."
            )
            continue

        plan.append((src, dst))
        name_map[src.name] = dst.name

    if folder_name == "ps1":
        update_cue_references(folder, name_map)

    renamed_count = 0

    for src, dst in plan:
        old_stem = src.stem
        new_stem = dst.stem

        if src != dst:
            print(f"  Renaming: {src.name} -> {dst.name}")
            src.rename(dst)
            renamed_count += 1

            if dst.suffix.lower() != ".cue":
                for old_img, new_img in rename_matching_covers(old_stem, new_stem):
                    print(
                        "    Cover: "
                        f"{old_img.relative_to(ROOT)} -> "
                        f"{new_img.relative_to(ROOT)}"
                    )

    return renamed_count


def first_bin_from_cue(cue: Path):
    try:
        text = cue.read_text(encoding="utf-8-sig", errors="ignore")
    except Exception:
        return None

    for line in text.splitlines():
        m = re.match(
            r'^\s*FILE\s+(?:"([^"]+)"|(\S+))\s+',
            line,
            flags=re.I,
        )

        if m:
            return (m.group(1) or m.group(2)).strip()

    return None


def ps1_bins_to_include(folder: Path):
    all_bins = {
        p.name.casefold(): p
        for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() == ".bin"
    }

    referenced_nonfirst = set()
    first_bins = set()

    for cue in folder.iterdir():
        if not cue.is_file() or cue.suffix.lower() != ".cue":
            continue

        first = first_bin_from_cue(cue)

        if first:
            first_bins.add(Path(first).name.casefold())

        try:
            text = cue.read_text(encoding="utf-8-sig", errors="ignore")
        except Exception:
            continue

        refs = []

        for line in text.splitlines():
            m = re.match(
                r'^\s*FILE\s+(?:"([^"]+)"|(\S+))\s+',
                line,
                flags=re.I,
            )

            if m:
                refs.append(
                    Path(
                        (m.group(1) or m.group(2)).strip()
                    ).name.casefold()
                )

        for ref in refs[1:]:
            referenced_nonfirst.add(ref)

    include = set()

    for key in all_bins:
        if key in first_bins or key not in referenced_nonfirst:
            include.add(key)

    return include


def cover_name(rom_stem: str) -> str:
    img_root = ROOT / "img"

    if not img_root.exists():
        return ""

    for img in img_root.rglob("*"):
        if (
            img.is_file()
            and img.suffix.lower() in IMAGE_EXTS
            and img.stem.casefold() == rom_stem.casefold()
        ):
            return img.stem

    return ""


def main():
    print("=" * 62)
    print("GAME STICK M8 V6 - DATABASE BUILDER")
    print("=" * 62)
    print("ROM folder:", ROOT)
    print()

    existing_systems = [
        name for name in SYSTEMS
        if (ROOT / name).is_dir()
    ]

    if not existing_systems:
        raise RuntimeError(
            "No compatible console folders were found. "
            "Run this script from inside the SD card 'roms' folder."
        )

    print("Detected console folders:")
    for name in existing_systems:
        print(" ", name)
    print()

    print("Step 1/2 - Fixing filenames with extra dots...")

    total_renamed = 0

    for folder_name in existing_systems:
        total_renamed += rename_files_with_extra_dots(
            folder_name,
            ROOT / folder_name,
        )

    print("Files renamed:", total_renamed)
    print()
    print("Step 2/2 - Building game database...")

    if TEMP.exists():
        TEMP.unlink()

    rows = []
    game_id = 1

    for folder_name in existing_systems:
        folder = ROOT / folder_name
        ext_map = SYSTEMS[folder_name]

        ps1_bins = (
            ps1_bins_to_include(folder)
            if folder_name == "ps1"
            else None
        )

        files = sorted(
            (p for p in folder.iterdir() if p.is_file()),
            key=lambda p: p.name.casefold(),
        )

        for rom in files:
            ext_lower = rom.suffix.lower()

            if ext_lower not in ext_map:
                continue

            if "." in rom.stem:
                print(
                    "  WARNING: skipped because the name still contains "
                    f"an extra dot: {folder_name}/{rom.name}"
                )
                continue

            if folder_name == "ps1" and ext_lower == ".bin":
                if rom.name.casefold() not in ps1_bins:
                    continue

            class_type, emu_type = ext_map[ext_lower]
            stem = rom.stem

            rows.append((
                game_id,
                stem,
                "",
                "",
                rom.suffix,
                class_type,
                emu_type,
                cover_name(stem),
                stem,
            ))

            game_id += 1

    if OUTPUT.exists():
        backup = ROOT / "simple_games_m8_2w.db.bak"
        shutil.copy2(OUTPUT, backup)
        print("Previous database backup:", backup.name)

    con = sqlite3.connect(TEMP)

    try:
        con.execute(CREATE_SQL)

        con.executemany(
            """
            INSERT INTO tbl_all
            (game_id,en_name,cn_name,cn_match,suffix,class_type,
             emu_type,img_name,long_en_name)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            rows,
        )

        con.commit()

        count = con.execute(
            "SELECT COUNT(*) FROM tbl_all"
        ).fetchone()[0]
    finally:
        con.close()

    if count != len(rows):
        raise RuntimeError(
            "Database verification failed: inserted row count does not match."
        )

    if OUTPUT.exists():
        OUTPUT.unlink()

    TEMP.replace(OUTPUT)

    labels = {
        (0, 4): "MAME",
        (1, 0): "NES",
        (2, 1): "Game Boy",
        (3, 1): "Game Boy Advance",
        (4, 1): "Game Boy Color",
        (5, 2): "Mega Drive / Genesis",
        (6, 3): "SNES / Super Famicom",
        (7, 5): "PlayStation 1",
        (8, 6): "Atari 2600",
        (8, 7): "Atari 7800",
    }

    counts = {}

    for row in rows:
        key = (row[5], row[6])
        counts[key] = counts.get(key, 0) + 1

    print()
    print("Database created successfully:")
    print(" ", OUTPUT)
    print("Games added:", len(rows))

    for key, n in sorted(counts.items()):
        print(f"  {labels.get(key, str(key))}: {n}")

    print()
    print("Done. Safely eject the SD card before inserting it into the Game Stick.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print()
        print("ERROR:", exc)
        sys.exit(1)
