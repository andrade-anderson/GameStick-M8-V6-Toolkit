#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Game Stick M8 v6 Toolkit v3 - All-in-One

Single-program toolkit for compatible M8 v6 SD cards.

Features:
- Automatically locates the SD-card root.
- Checks DATA03 compatibility.
- Reads the internal /version.
- Detects /db/m8_game_list.db.
- Creates a DATA03 backup before patching.
- Redirects the game database to:
    /mnt/roms/simple_games_m8_2w.db
- Fixes ROM filenames containing extra dots.
- Renames matching cover images.
- Updates PS1 BIN/CUE references.
- Builds simple_games_m8_2w.db.
- Supports Mega Drive / Genesis ROMs in .bin, .md, .gen and .smd formats.
- Can restore the original DATA03 backup.
- Interactive menu and command-line modes.
- Python standard library only at runtime.

Confirmed working firmware during development:
    M8-20231122-release-v6.0

Other M8-YYYYMMDD-release-v6.0 revisions are accepted only when the
expected internal DATA03 structure is detected.
"""

from __future__ import annotations

from pathlib import Path
import argparse
import os
import re
import shutil
import sqlite3
import struct
import sys
import string
import time

APP_NAME = "Game Stick M8 v6 Toolkit"
APP_VERSION = "3.0.1"

NEW_DB_TARGET = b"/mnt/roms/simple_games_m8_2w.db"
VERSION_RE = re.compile(rb"^M8-\d{8}-release-v6\.0\s*$")

SYSTEMS = {
    "mame":  {".zip": (0, 4)},
    "nes":   {".nes": (1, 0)},
    "gb":    {".gb":  (2, 1)},
    "gba":   {".gba": (3, 1)},
    "gbc":   {".gbc": (4, 1)},
    "md":    {".bin": (5, 2), ".md": (5, 2), ".gen": (5, 2), ".smd": (5, 2)},
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


def app_directory() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def banner():
    print("=" * 68)
    print(f"{APP_NAME} v{APP_VERSION}")
    print("=" * 68)


def looks_like_sd_root(path: Path) -> bool:
    try:
        return (
            path.is_dir()
            and (path / "res" / "DATA03").is_file()
            and (path / "roms").is_dir()
        )
    except OSError:
        return False


def root_candidates():
    seen = set()
    candidates = []

    def add(p: Path):
        try:
            p = p.resolve()
        except Exception:
            return
        key = str(p).casefold()
        if key not in seen:
            seen.add(key)
            candidates.append(p)

    app = app_directory()
    cwd = Path.cwd()

    add(app)
    add(cwd)

    for p in [app, cwd]:
        for parent in p.parents:
            add(parent)

    if os.name == "nt":
        for letter in string.ascii_uppercase:
            drive = Path(f"{letter}:\\")
            if drive.exists():
                add(drive)

    return candidates


def locate_sd_root(explicit: Path | None = None) -> Path:
    if explicit is not None:
        explicit = explicit.resolve()
        if not looks_like_sd_root(explicit):
            raise RuntimeError(
                f"The selected path does not look like a compatible SD-card root:\n{explicit}\n"
                "Expected: res\\DATA03 and roms\\"
            )
        return explicit

    matches = [p for p in root_candidates() if looks_like_sd_root(p)]

    if not matches:
        raise RuntimeError(
            "No compatible SD-card root was found.\n"
            "Place the program in the SD-card root or run with --root X:\\"
        )

    # Prefer the folder containing the EXE/script.
    app = app_directory()
    for p in matches:
        if p == app:
            return p

    # Prefer the current directory next.
    cwd = Path.cwd().resolve()
    for p in matches:
        if p == cwd:
            return p

    if len(matches) == 1:
        return matches[0]

    print("Multiple possible Game Stick SD cards were found:")
    for i, p in enumerate(matches, 1):
        print(f"  {i}. {p}")

    while True:
        answer = input("Select the SD card number: ").strip()
        if answer.isdigit():
            idx = int(answer)
            if 1 <= idx <= len(matches):
                return matches[idx - 1]
        print("Invalid selection.")


class ExtFS:
    """Minimal EXT2/3/4 reader/writer for the specific fast-symlink patch."""

    def __init__(self, container: Path, base: int):
        self.container = container
        self.base = base
        self.container_size = container.stat().st_size

        with container.open("rb") as f:
            f.seek(base + 1024)
            self.sb = f.read(1024)

        if len(self.sb) != 1024:
            raise RuntimeError("Short EXT superblock.")

        if struct.unpack_from("<H", self.sb, 56)[0] != 0xEF53:
            raise RuntimeError("Invalid EXT superblock magic.")

        self.block_size = 1024 << struct.unpack_from("<I", self.sb, 24)[0]
        self.first_data_block = struct.unpack_from("<I", self.sb, 20)[0]
        self.blocks_count = struct.unpack_from("<I", self.sb, 4)[0]
        self.blocks_per_group = struct.unpack_from("<I", self.sb, 32)[0]
        self.inodes_per_group = struct.unpack_from("<I", self.sb, 40)[0]
        self.inodes_count = struct.unpack_from("<I", self.sb, 0)[0]
        self.inode_size = struct.unpack_from("<H", self.sb, 88)[0] or 128

        if not self.blocks_count or not self.blocks_per_group or not self.inodes_per_group:
            raise RuntimeError("Invalid EXT geometry.")
        if self.inode_size not in (128, 256):
            raise RuntimeError(f"Unsupported inode size: {self.inode_size}")

        self.fs_bytes = self.blocks_count * self.block_size
        self.group_count = (
            self.blocks_count + self.blocks_per_group - 1
        ) // self.blocks_per_group

        gdt_off = self.base + (self.first_data_block + 1) * self.block_size
        with container.open("rb") as f:
            f.seek(gdt_off)
            self.gdt = f.read(self.group_count * 32)

        if len(self.gdt) < self.group_count * 32:
            raise RuntimeError("Short EXT group descriptor table.")

    @staticmethod
    def find_candidates(container: Path):
        size = container.stat().st_size
        needle = b"\x53\xef"
        chunk_size = 8 * 1024 * 1024
        overlap = 2048
        found = set()
        pos = 0
        tail = b""

        with container.open("rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break

                data = tail + chunk
                data_abs = pos - len(tail)
                start = 0

                while True:
                    idx = data.find(needle, start)
                    if idx < 0:
                        break
                    start = idx + 1

                    magic_abs = data_abs + idx
                    sb_abs = magic_abs - 56
                    fs_base = sb_abs - 1024

                    if fs_base < 0:
                        continue

                    try:
                        current = f.tell()
                        f.seek(sb_abs)
                        sb = f.read(1024)
                        f.seek(current)

                        if len(sb) < 1024:
                            continue
                        if struct.unpack_from("<H", sb, 56)[0] != 0xEF53:
                            continue

                        log_bs = struct.unpack_from("<I", sb, 24)[0]
                        blocks = struct.unpack_from("<I", sb, 4)[0]
                        bpg = struct.unpack_from("<I", sb, 32)[0]
                        ipg = struct.unpack_from("<I", sb, 40)[0]
                        inode_size = struct.unpack_from("<H", sb, 88)[0] or 128

                        if log_bs > 6 or not blocks or not bpg or not ipg:
                            continue
                        if inode_size not in (128, 256):
                            continue

                        block_size = 1024 << log_bs
                        fs_end = fs_base + blocks * block_size

                        if fs_end <= size and fs_end > fs_base:
                            found.add(fs_base)
                    except Exception:
                        continue

                tail = data[-overlap:]
                pos += len(chunk)

        return sorted(found)

    def inode_offset(self, ino: int):
        if ino < 1 or ino > self.inodes_count:
            raise ValueError("Invalid inode.")

        group = (ino - 1) // self.inodes_per_group
        index = (ino - 1) % self.inodes_per_group
        desc = group * 32
        inode_table_block = struct.unpack_from("<I", self.gdt, desc + 8)[0]

        return (
            self.base
            + inode_table_block * self.block_size
            + index * self.inode_size
        )

    def read_inode(self, ino: int):
        off = self.inode_offset(ino)
        with self.container.open("rb") as f:
            f.seek(off)
            data = f.read(self.inode_size)

        if len(data) != self.inode_size:
            raise RuntimeError("Short inode read.")
        return data

    def inode_type(self, ino: int):
        mode = struct.unpack_from("<H", self.read_inode(ino), 0)[0] & 0xF000
        return {
            0x4000: "dir",
            0x8000: "file",
            0xA000: "symlink",
        }.get(mode, f"other_{mode:04x}")

    def inode_size_bytes(self, ino: int):
        inode = self.read_inode(ino)
        lo = struct.unpack_from("<I", inode, 4)[0]
        if self.inode_type(ino) == "file" and self.inode_size >= 128:
            high = struct.unpack_from("<I", inode, 108)[0]
            return lo | (high << 32)
        return lo

    def _indirect(self, block_no: int, level: int, limit: int):
        if not block_no or limit <= 0:
            return []

        with self.container.open("rb") as f:
            f.seek(self.base + block_no * self.block_size)
            raw = f.read(self.block_size)

        count = len(raw) // 4
        ptrs = struct.unpack("<" + "I" * count, raw[:count * 4])
        out = []

        for ptr in ptrs:
            if not ptr:
                continue
            if level == 1:
                out.append(ptr)
            else:
                out.extend(self._indirect(ptr, level - 1, limit - len(out)))
            if len(out) >= limit:
                break

        return out[:limit]

    def data_blocks(self, ino: int, max_blocks: int):
        inode = self.read_inode(ino)
        ptrs = struct.unpack_from("<15I", inode, 40)
        out = [p for p in ptrs[:12] if p][:max_blocks]

        if len(out) < max_blocks and ptrs[12]:
            out.extend(self._indirect(ptrs[12], 1, max_blocks - len(out)))
        if len(out) < max_blocks and ptrs[13]:
            out.extend(self._indirect(ptrs[13], 2, max_blocks - len(out)))
        if len(out) < max_blocks and ptrs[14]:
            out.extend(self._indirect(ptrs[14], 3, max_blocks - len(out)))

        return out[:max_blocks]

    def read_file(self, ino: int, cap: int | None = None):
        inode = self.read_inode(ino)
        kind = self.inode_type(ino)
        size = self.inode_size_bytes(ino)

        if kind == "symlink" and size <= 60:
            return bytes(inode[40:40 + size])

        wanted = size if cap is None else min(size, cap)
        if wanted <= 0:
            return b""

        blocks_needed = (wanted + self.block_size - 1) // self.block_size
        out = bytearray()

        with self.container.open("rb") as f:
            for block_no in self.data_blocks(ino, blocks_needed):
                f.seek(self.base + block_no * self.block_size)
                out.extend(f.read(self.block_size))
                if len(out) >= wanted:
                    break

        return bytes(out[:wanted])

    def list_dir(self, ino: int):
        if self.inode_type(ino) != "dir":
            raise RuntimeError("Not a directory.")

        data = self.read_file(ino, cap=32 * 1024 * 1024)
        pos = 0
        entries = []

        while pos + 8 <= len(data):
            child, rec_len, name_len, file_type = struct.unpack_from("<IHBB", data, pos)
            if rec_len < 8 or pos + rec_len > len(data):
                break

            name = data[pos + 8:pos + 8 + name_len].decode("utf-8", "replace")
            if child and name not in (".", ".."):
                entries.append((name, child))

            pos += rec_len

        return entries

    def resolve(self, path: str):
        ino = 2
        for part in [p for p in path.split("/") if p]:
            entries = {name: child for name, child in self.list_dir(ino)}
            if part not in entries:
                raise FileNotFoundError(path)
            ino = entries[part]
        return ino

    def patch_fast_symlink(self, ino: int, new_target: bytes):
        inode = self.read_inode(ino)
        kind = self.inode_type(ino)
        old_size = struct.unpack_from("<I", inode, 4)[0]

        if kind != "symlink":
            raise RuntimeError("m8_game_list.db is not a symbolic link.")
        if old_size > 60 or len(new_target) > 60:
            raise RuntimeError("Symbolic link format is not compatible.")

        off = self.inode_offset(ino)

        with self.container.open("r+b") as f:
            f.seek(off + 4)
            f.write(struct.pack("<I", len(new_target)))
            f.seek(off + 40)
            f.write(new_target.ljust(60, b"\x00"))
            f.flush()
            os.fsync(f.fileno())


def find_compatible_fs(data03: Path):
    candidates = ExtFS.find_candidates(data03)

    for base in candidates:
        try:
            fs = ExtFS(data03, base)
            version = fs.read_file(fs.resolve("/version"), cap=4096).strip()
            link_ino = fs.resolve("/db/m8_game_list.db")
            if fs.inode_type(link_ino) != "symlink":
                continue
            return fs, version, link_ino
        except Exception:
            continue

    raise RuntimeError(
        "No compatible M8 v6 filesystem structure was found inside DATA03."
    )


def compatibility_report(root: Path):
    data03 = root / "res" / "DATA03"

    result = {
        "data03": data03,
        "data03_exists": data03.is_file(),
        "filesystem_found": False,
        "version": None,
        "version_ok": False,
        "link_found": False,
        "current_target": None,
        "internal_db_verified": False,
        "already_patched": False,
        "compatible": False,
        "fs": None,
        "link_ino": None,
    }

    if not result["data03_exists"]:
        return result

    try:
        fs, version, link_ino = find_compatible_fs(data03)
        result["filesystem_found"] = True
        result["fs"] = fs
        result["version"] = version.decode("utf-8", "replace")
        result["version_ok"] = bool(VERSION_RE.match(version))
        result["link_found"] = True
        result["link_ino"] = link_ino

        target = fs.read_file(link_ino, cap=4096)
        result["current_target"] = target.decode("utf-8", "replace")

        if target == NEW_DB_TARGET:
            result["already_patched"] = True
            result["internal_db_verified"] = True
        elif target.endswith(b".db") and b"/" not in target:
            try:
                fs.resolve("/db/" + target.decode("utf-8", "strict"))
                result["internal_db_verified"] = True
            except Exception:
                pass

        result["compatible"] = all([
            result["filesystem_found"],
            result["version_ok"],
            result["link_found"],
            result["internal_db_verified"],
        ])
    except Exception:
        pass

    return result


def print_compatibility(report, root: Path):
    print()
    print("-" * 68)
    print("FIRMWARE COMPATIBILITY REPORT")
    print("-" * 68)
    print(f"SD card root:              {root}")
    print(f"DATA03 found:              {'YES' if report['data03_exists'] else 'NO'}")
    print(f"EXT filesystem detected:   {'YES' if report['filesystem_found'] else 'NO'}")
    print(f"Firmware version:          {report['version'] or 'NOT FOUND'}")
    print(f"M8 v6 version accepted:    {'YES' if report['version_ok'] else 'NO'}")
    print(f"/db/m8_game_list.db:       {'FOUND' if report['link_found'] else 'NOT FOUND'}")
    print(f"Current database target:   {report['current_target'] or 'UNKNOWN'}")
    print(f"Current database verified: {'YES' if report['internal_db_verified'] else 'NO'}")
    print("-" * 68)

    if report["already_patched"]:
        print("RESULT: ALREADY PATCHED / READY TO USE")
    elif report["compatible"]:
        print("RESULT: COMPATIBLE - SAFE TO PATCH")
    else:
        print("RESULT: NOT COMPATIBLE - NO CHANGES SHOULD BE MADE")

    print("-" * 68)
    print()


def patch_data03(root: Path, assume_yes: bool = False):
    report = compatibility_report(root)
    print_compatibility(report, root)

    if report["already_patched"]:
        print("DATA03 is already patched. No patching is needed.")
        return True

    if not report["compatible"]:
        print("Patch cancelled because compatibility checks did not pass.")
        return False

    if not assume_yes:
        answer = input("Apply the DATA03 patch? Type YES to continue: ").strip()
        if answer != "YES":
            print("Cancelled. No changes were made.")
            return False

    data03 = root / "res" / "DATA03"
    backup = root / "res" / "DATA03.before_external_db.bak"

    if not backup.exists():
        print("Creating DATA03 backup...")
        shutil.copy2(data03, backup)
        print("Backup created:", backup)
    else:
        print("Existing DATA03 backup found:", backup)

    report["fs"].patch_fast_symlink(report["link_ino"], NEW_DB_TARGET)

    verify = compatibility_report(root)
    if not verify["already_patched"]:
        raise RuntimeError(
            "Patch verification failed. Restore DATA03.before_external_db.bak."
        )

    print("DATA03 patch completed successfully.")
    print("/db/m8_game_list.db ->", NEW_DB_TARGET.decode())
    return True


def restore_data03(root: Path, assume_yes: bool = False):
    data03 = root / "res" / "DATA03"
    backup = root / "res" / "DATA03.before_external_db.bak"

    if not backup.is_file():
        print("No DATA03.before_external_db.bak backup was found.")
        return False

    if not assume_yes:
        print("This will replace the current DATA03 with the saved backup.")
        answer = input("Type RESTORE to continue: ").strip()
        if answer != "RESTORE":
            print("Restore cancelled.")
            return False

    safety_copy = root / "res" / "DATA03.before_restore.bak"
    if data03.exists() and not safety_copy.exists():
        shutil.copy2(data03, safety_copy)

    shutil.copy2(backup, data03)
    print("DATA03 was restored from backup.")
    return True


def remove_extra_dots(stem: str):
    return stem.replace(".", "").strip()


def replace_case_insensitive(text: str, old: str, new: str):
    return re.sub(re.escape(old), lambda _: new, text, flags=re.IGNORECASE)


def update_cue_references(folder: Path, rename_map: dict[str, str]):
    if not rename_map:
        return 0

    changed_files = 0

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
            changed_files += 1

    return changed_files


def rename_matching_covers(img_root: Path, old_stem: str, new_stem: str):
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
                "  WARNING: cover not renamed because target already exists:",
                target,
            )
            continue

        img.rename(target)
        renamed.append((img, target))

    return renamed


def fix_extra_dot_filenames(roms_root: Path):
    img_root = roms_root / "img"
    total_roms = 0
    total_cues = 0
    total_covers = 0

    print("Checking ROM filenames for extra dots...")

    for folder_name, ext_map in SYSTEMS.items():
        folder = roms_root / folder_name
        if not folder.is_dir():
            continue

        allowed = set(ext_map.keys())
        if folder_name == "ps1":
            allowed.add(".cue")

        candidates = [
            p for p in folder.iterdir()
            if p.is_file()
            and p.suffix.lower() in allowed
            and "." in p.stem
        ]

        plan = []
        rename_map = {}

        for src in candidates:
            new_stem = remove_extra_dots(src.stem)
            if not new_stem:
                print("  WARNING: invalid filename skipped:", src.name)
                continue

            dst = src.with_name(new_stem + src.suffix)

            if dst.exists() and dst.resolve() != src.resolve():
                print(
                    f"  WARNING: cannot rename '{src.name}' because "
                    f"'{dst.name}' already exists."
                )
                continue

            plan.append((src, dst))
            rename_map[src.name] = dst.name

        if folder_name == "ps1":
            total_cues += update_cue_references(folder, rename_map)

        for src, dst in plan:
            old_stem = src.stem
            new_stem = dst.stem

            if src == dst:
                continue

            print(f"  {folder_name}: {src.name} -> {dst.name}")
            src.rename(dst)

            if dst.suffix.lower() == ".cue":
                continue

            total_roms += 1

            for old_img, new_img in rename_matching_covers(
                img_root, old_stem, new_stem
            ):
                total_covers += 1
                print(
                    "    Cover:",
                    old_img.relative_to(roms_root),
                    "->",
                    new_img.relative_to(roms_root),
                )

    print(
        f"Filename cleanup complete: {total_roms} ROM(s), "
        f"{total_covers} cover(s), {total_cues} CUE file(s) updated."
    )


def first_bin_from_cue(cue: Path):
    try:
        text = cue.read_text(encoding="utf-8-sig", errors="ignore")
    except Exception:
        return None

    for line in text.splitlines():
        match = re.match(
            r'^\s*FILE\s+(?:"([^"]+)"|(\S+))\s+',
            line,
            flags=re.I,
        )
        if match:
            return (match.group(1) or match.group(2)).strip()

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
            match = re.match(
                r'^\s*FILE\s+(?:"([^"]+)"|(\S+))\s+',
                line,
                flags=re.I,
            )
            if match:
                refs.append(
                    Path((match.group(1) or match.group(2)).strip()).name.casefold()
                )

        for ref in refs[1:]:
            referenced_nonfirst.add(ref)

    return {
        name
        for name in all_bins
        if name in first_bins or name not in referenced_nonfirst
    }


def build_cover_index(img_root: Path):
    index = {}

    if not img_root.is_dir():
        return index

    for img in img_root.rglob("*"):
        if not img.is_file() or img.suffix.lower() not in IMAGE_EXTS:
            continue
        index.setdefault(img.stem.casefold(), img.stem)

    return index


def build_game_database(root: Path):
    roms_root = root / "roms"
    if not roms_root.is_dir():
        raise RuntimeError("The roms folder was not found.")

    fix_extra_dot_filenames(roms_root)

    output = roms_root / "simple_games_m8_2w.db"
    temp = roms_root / "simple_games_m8_2w.db.tmp"
    backup = roms_root / "simple_games_m8_2w.db.bak"

    if temp.exists():
        temp.unlink()

    cover_index = build_cover_index(roms_root / "img")
    rows = []
    game_id = 1

    counts = {}

    for folder_name, ext_map in SYSTEMS.items():
        folder = roms_root / folder_name
        if not folder.is_dir():
            continue

        ps1_bins = ps1_bins_to_include(folder) if folder_name == "ps1" else None

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
                    "  WARNING: skipped because the filename still contains an "
                    f"extra dot: {folder_name}/{rom.name}"
                )
                continue

            if folder_name == "ps1" and ext_lower == ".bin":
                if rom.name.casefold() not in ps1_bins:
                    continue

            class_type, emu_type = ext_map[ext_lower]
            stem = rom.stem
            image_name = cover_index.get(stem.casefold(), "")

            rows.append((
                game_id,
                stem,
                "",
                "",
                rom.suffix,
                class_type,
                emu_type,
                image_name,
                stem,
            ))

            counts[(class_type, emu_type)] = counts.get(
                (class_type, emu_type), 0
            ) + 1
            game_id += 1

    if output.exists():
        shutil.copy2(output, backup)
        print("Previous game database backup:", backup)

    con = sqlite3.connect(temp)
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
        count = con.execute("SELECT COUNT(*) FROM tbl_all").fetchone()[0]
    finally:
        con.close()

    if count != len(rows):
        if temp.exists():
            temp.unlink()
        raise RuntimeError("Database verification failed.")

    # Verify exact schema before replacing the old database.
    check = sqlite3.connect(temp)
    try:
        cols = [
            row[1]
            for row in check.execute("PRAGMA table_info(tbl_all)").fetchall()
        ]
    finally:
        check.close()

    expected_cols = [
        "game_id", "en_name", "cn_name", "cn_match", "suffix",
        "class_type", "emu_type", "img_name", "long_en_name"
    ]

    if cols != expected_cols:
        temp.unlink(missing_ok=True)
        raise RuntimeError("Generated database schema verification failed.")

    if output.exists():
        output.unlink()
    temp.replace(output)

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

    print()
    print("Game database created successfully:")
    print(output)
    print("Games added:", len(rows))

    for key, amount in sorted(counts.items()):
        print(f"  {labels.get(key, str(key))}: {amount}")

    return output


def full_setup(root: Path, assume_yes: bool = False):
    print()
    print("FULL SETUP")
    print("-" * 68)

    report = compatibility_report(root)
    print_compatibility(report, root)

    if not report["compatible"] and not report["already_patched"]:
        print("Full setup stopped: incompatible firmware.")
        return False

    if not report["already_patched"]:
        if not patch_data03(root, assume_yes=assume_yes):
            return False

    build_game_database(root)

    final_report = compatibility_report(root)
    db = root / "roms" / "simple_games_m8_2w.db"

    print()
    print("-" * 68)
    print("FINAL VERIFICATION")
    print("-" * 68)
    print(
        "DATA03 external database link:",
        "OK" if final_report["already_patched"] else "FAILED",
    )
    print("External database exists:", "YES" if db.is_file() else "NO")

    if final_report["already_patched"] and db.is_file():
        print("RESULT: FULL SETUP COMPLETED SUCCESSFULLY")
        return True

    print("RESULT: FINAL VERIFICATION FAILED")
    return False


def interactive_menu(root: Path):
    while True:
        banner()
        print("Detected SD card:", root)
        print()
        print("1 - Check firmware compatibility")
        print("2 - Patch DATA03")
        print("3 - Build / rebuild game database")
        print("4 - Full setup")
        print("5 - Restore original DATA03 backup")
        print("6 - Show detected SD-card path")
        print("0 - Exit")
        print()

        choice = input("Select an option: ").strip()
        print()

        try:
            if choice == "1":
                print_compatibility(compatibility_report(root), root)
            elif choice == "2":
                patch_data03(root)
            elif choice == "3":
                build_game_database(root)
            elif choice == "4":
                full_setup(root)
            elif choice == "5":
                restore_data03(root)
            elif choice == "6":
                print("SD card root:", root)
            elif choice == "0":
                return
            else:
                print("Invalid option.")
        except Exception as exc:
            print()
            print("ERROR:", exc)

        print()
        input("Press Enter to return to the menu...")
        print()


def parse_args():
    ap = argparse.ArgumentParser(
        description="All-in-One toolkit for compatible Game Stick M8 v6 SD cards."
    )
    ap.add_argument("--root", type=Path, help="SD-card root, for example E:\\")
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="Compatibility check only.")
    group.add_argument("--patch", action="store_true", help="Patch DATA03.")
    group.add_argument("--build", action="store_true", help="Build/rebuild game database.")
    group.add_argument("--full", action="store_true", help="Run full setup.")
    group.add_argument("--restore", action="store_true", help="Restore DATA03 backup.")
    ap.add_argument(
        "--yes",
        action="store_true",
        help="Skip interactive confirmation for patch/full/restore.",
    )
    return ap.parse_args()


def main():
    args = parse_args()
    root = locate_sd_root(args.root)

    if args.check:
        banner()
        print_compatibility(compatibility_report(root), root)
        return

    if args.patch:
        banner()
        if not patch_data03(root, assume_yes=args.yes):
            sys.exit(2)
        return

    if args.build:
        banner()
        build_game_database(root)
        return

    if args.full:
        banner()
        if not full_setup(root, assume_yes=args.yes):
            sys.exit(2)
        return

    if args.restore:
        banner()
        if not restore_data03(root, assume_yes=args.yes):
            sys.exit(2)
        return

    interactive_menu(root)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(130)
    except Exception as exc:
        print()
        print("ERROR:", exc)
        if getattr(sys, "frozen", False):
            print()
            input("Press Enter to close...")
        sys.exit(1)
