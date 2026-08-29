#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Game Stick Lite M8 v6 - DATA03 compatibility checker and patcher.

What it does:
1. Finds DATA03.
2. Detects the embedded EXT2 filesystem.
3. Reads /version.
4. Accepts only firmware matching:
      M8-YYYYMMDD-release-v6.0
5. Checks /db/m8_game_list.db.
6. Verifies that the current internal database exists.
7. Prints a compatibility report.
8. Only after confirmation, creates a backup and redirects:
      /db/m8_game_list.db
   to:
      /mnt/roms/simple_games_m8_2w.db

Safety:
- No changes are made during the diagnostic phase.
- Incompatible firmware is rejected.
- A backup is created before patching.
"""

from pathlib import Path
import argparse
import os
import re
import shutil
import struct
import sys

NEW_TARGET = b"/mnt/roms/simple_games_m8_2w.db"
VERSION_RE = re.compile(rb"^M8-\d{8}-release-v6\.0\s*$")


class Ext2:
    def __init__(self, path: Path):
        self.path = path
        self.size = path.stat().st_size
        self.base = self._find_fs_base()

        with path.open("rb") as f:
            f.seek(self.base + 1024)
            self.sb = f.read(1024)

        self.block_size = 1024 << struct.unpack_from("<I", self.sb, 24)[0]
        self.first_data_block = struct.unpack_from("<I", self.sb, 20)[0]
        self.blocks_count = struct.unpack_from("<I", self.sb, 4)[0]
        self.blocks_per_group = struct.unpack_from("<I", self.sb, 32)[0]
        self.inodes_per_group = struct.unpack_from("<I", self.sb, 40)[0]
        self.inode_size = struct.unpack_from("<H", self.sb, 88)[0] or 128
        self.group_count = (
            self.blocks_count + self.blocks_per_group - 1
        ) // self.blocks_per_group

        gdt_off = self.base + (self.first_data_block + 1) * self.block_size
        with path.open("rb") as f:
            f.seek(gdt_off)
            self.gdt = f.read(self.group_count * 32)

    def _find_fs_base(self) -> int:
        needle = b"\x53\xef"
        chunk_size = 4 * 1024 * 1024
        overlap = 2048
        pos = 0
        tail = b""

        with self.path.open("rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break

                data = tail + chunk
                base_pos = pos - len(tail)
                start = 0

                while True:
                    idx = data.find(needle, start)
                    if idx < 0:
                        break

                    magic_abs = base_pos + idx
                    sb_start = magic_abs - 56
                    start = idx + 1

                    if sb_start < 1024:
                        continue

                    try:
                        current = f.tell()
                        f.seek(sb_start)
                        sb = f.read(1024)
                        f.seek(current)

                        if len(sb) < 1024:
                            continue

                        magic = struct.unpack_from("<H", sb, 56)[0]
                        log_bs = struct.unpack_from("<I", sb, 24)[0]
                        blocks = struct.unpack_from("<I", sb, 4)[0]
                        bpg = struct.unpack_from("<I", sb, 32)[0]
                        ipg = struct.unpack_from("<I", sb, 40)[0]
                        inode_size = struct.unpack_from("<H", sb, 88)[0] or 128

                        if magic != 0xEF53 or log_bs > 6:
                            continue
                        if not blocks or not bpg or not ipg:
                            continue
                        if inode_size not in (128, 256):
                            continue

                        block_size = 1024 << log_bs
                        fs_base = sb_start - 1024
                        fs_end = fs_base + blocks * block_size

                        if fs_base >= 0 and fs_end == self.size:
                            return fs_base
                    except Exception:
                        continue

                tail = data[-overlap:]
                pos += len(chunk)

        raise RuntimeError(
            "Could not locate a compatible EXT2 filesystem inside DATA03."
        )

    def inode_offset(self, ino: int) -> int:
        group = (ino - 1) // self.inodes_per_group
        index = (ino - 1) % self.inodes_per_group

        if ino < 1 or group >= self.group_count:
            raise ValueError("Invalid inode.")

        desc_off = group * 32
        inode_table_block = struct.unpack_from("<I", self.gdt, desc_off + 8)[0]

        return (
            self.base
            + inode_table_block * self.block_size
            + index * self.inode_size
        )

    def read_inode(self, ino: int) -> bytes:
        off = self.inode_offset(ino)
        with self.path.open("rb") as f:
            f.seek(off)
            data = f.read(self.inode_size)

        if len(data) != self.inode_size:
            raise RuntimeError("Failed to read inode.")

        return data

    def inode_mode(self, ino: int) -> int:
        return struct.unpack_from("<H", self.read_inode(ino), 0)[0]

    def _read_indirect(self, block_no: int):
        if not block_no:
            return []

        with self.path.open("rb") as f:
            f.seek(self.base + block_no * self.block_size)
            block = f.read(self.block_size)

        count = self.block_size // 4
        return [n for n in struct.unpack("<" + "I" * count, block) if n]

    def data_blocks(self, ino: int):
        inode = self.read_inode(ino)
        ptrs = list(struct.unpack_from("<15I", inode, 40))
        blocks = [b for b in ptrs[:12] if b]

        if ptrs[12]:
            blocks.extend(self._read_indirect(ptrs[12]))

        return blocks

    def read_file(self, ino: int) -> bytes:
        inode = self.read_inode(ino)
        mode = struct.unpack_from("<H", inode, 0)[0]
        size = struct.unpack_from("<I", inode, 4)[0]

        if (mode & 0xF000) == 0xA000 and size <= 60:
            return bytes(inode[40:40 + size])

        out = bytearray()

        with self.path.open("rb") as f:
            for block_no in self.data_blocks(ino):
                f.seek(self.base + block_no * self.block_size)
                out.extend(f.read(self.block_size))
                if len(out) >= size:
                    break

        return bytes(out[:size])

    def list_dir(self, ino: int):
        mode = self.inode_mode(ino)

        if (mode & 0xF000) != 0x4000:
            raise RuntimeError("Expected a directory but found another inode type.")

        data = self.read_file(ino)
        pos = 0
        entries = []

        while pos + 8 <= len(data):
            inode_no, rec_len, name_len, file_type = struct.unpack_from(
                "<IHBB", data, pos
            )

            if rec_len < 8 or pos + rec_len > len(data):
                break

            name_raw = data[pos + 8:pos + 8 + name_len]
            name = name_raw.decode("utf-8", "replace")

            if inode_no:
                entries.append((name, inode_no, file_type))

            pos += rec_len

        return entries

    def resolve(self, path: str) -> int:
        parts = [p for p in path.split("/") if p]
        ino = 2

        for part in parts:
            entries = {name: inode for name, inode, _ in self.list_dir(ino)}

            if part not in entries:
                raise FileNotFoundError(path)

            ino = entries[part]

        return ino

    def patch_fast_symlink(self, ino: int, new_target: bytes):
        inode = self.read_inode(ino)
        mode = struct.unpack_from("<H", inode, 0)[0]
        old_size = struct.unpack_from("<I", inode, 4)[0]

        if (mode & 0xF000) != 0xA000:
            raise RuntimeError("m8_game_list.db is not a symbolic link.")

        if old_size > 60 or len(new_target) > 60:
            raise RuntimeError("The symbolic link format is not compatible.")

        off = self.inode_offset(ino)

        with self.path.open("r+b") as f:
            f.seek(off + 4)
            f.write(struct.pack("<I", len(new_target)))

            f.seek(off + 40)
            f.write(new_target.ljust(60, b"\x00"))

            f.flush()
            os.fsync(f.fileno())


def locate_data03() -> Path:
    here = Path(__file__).resolve().parent

    candidates = [
        here / "DATA03",
        here / "res" / "DATA03",
        here.parent / "res" / "DATA03",
    ]

    for p in candidates:
        if p.exists() and p.is_file():
            return p

    raise FileNotFoundError(
        "DATA03 was not found. Put this script in the 'res' folder next to DATA03, "
        "or in the SD card root."
    )


def compatibility_report(data03: Path):
    result = {
        "data03": data03,
        "ext2": False,
        "version": None,
        "version_ok": False,
        "link_exists": False,
        "link_is_symlink": False,
        "current_target": None,
        "internal_db_exists": False,
        "already_patched": False,
        "compatible": False,
        "fs": None,
        "link_ino": None,
    }

    try:
        fs = Ext2(data03)
        result["fs"] = fs
        result["ext2"] = True
    except Exception:
        return result

    try:
        version_ino = fs.resolve("/version")
        version = fs.read_file(version_ino).strip()
        result["version"] = version.decode("utf-8", "replace")
        result["version_ok"] = bool(VERSION_RE.match(version))
    except Exception:
        pass

    try:
        link_ino = fs.resolve("/db/m8_game_list.db")
        result["link_exists"] = True
        result["link_ino"] = link_ino

        mode = fs.inode_mode(link_ino)
        result["link_is_symlink"] = (mode & 0xF000) == 0xA000

        if result["link_is_symlink"]:
            target = fs.read_file(link_ino)
            result["current_target"] = target.decode("utf-8", "replace")

            if target == NEW_TARGET:
                result["already_patched"] = True
                result["internal_db_exists"] = True
            elif target.endswith(b".db") and b"/" not in target:
                try:
                    fs.resolve("/db/" + target.decode("utf-8", "strict"))
                    result["internal_db_exists"] = True
                except Exception:
                    pass
    except Exception:
        pass

    result["compatible"] = all([
        result["ext2"],
        result["version_ok"],
        result["link_exists"],
        result["link_is_symlink"],
        result["internal_db_exists"],
    ])

    return result


def print_report(r):
    print()
    print("=" * 62)
    print("GAME STICK M8 V6 - COMPATIBILITY REPORT")
    print("=" * 62)
    print(f"DATA03 found:              {'YES' if r['data03'] else 'NO'}")
    print(f"EXT2 structure detected:   {'YES' if r['ext2'] else 'NO'}")
    print(f"Firmware version:          {r['version'] or 'NOT FOUND'}")
    print(f"M8 v6 version accepted:    {'YES' if r['version_ok'] else 'NO'}")
    print(f"/db/m8_game_list.db:       {'FOUND' if r['link_exists'] else 'NOT FOUND'}")
    print(f"Symbolic link format:      {'OK' if r['link_is_symlink'] else 'NOT COMPATIBLE'}")
    print(f"Current database target:   {r['current_target'] or 'UNKNOWN'}")
    print(f"Current database verified: {'YES' if r['internal_db_exists'] else 'NO'}")
    print("-" * 62)

    if r["already_patched"]:
        print("RESULT: ALREADY PATCHED / READY TO USE")
    elif r["compatible"]:
        print("RESULT: COMPATIBLE - SAFE TO PATCH")
    else:
        print("RESULT: NOT COMPATIBLE - NO CHANGES WILL BE MADE")

    print("=" * 62)
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Compatibility checker and patcher for Game Stick Lite M8 v6 DATA03."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run compatibility check only. Do not patch."
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Patch without interactive confirmation after all compatibility checks pass."
    )
    args = parser.parse_args()

    data03 = locate_data03()
    report = compatibility_report(data03)
    print_report(report)

    if args.check:
        return

    if report["already_patched"]:
        return

    if not report["compatible"]:
        sys.exit(2)

    if not args.yes:
        answer = input("Apply patch now? Type YES to continue: ").strip()
        if answer != "YES":
            print("Cancelled. No changes were made.")
            return

    backup = data03.with_name("DATA03.before_external_db.bak")

    if not backup.exists():
        print("Creating DATA03 backup...")
        shutil.copy2(data03, backup)
        print("Backup created:", backup)
    else:
        print("Backup already exists:", backup)

    fs = report["fs"]
    fs.patch_fast_symlink(report["link_ino"], NEW_TARGET)

    verify = compatibility_report(data03)

    if not verify["already_patched"]:
        raise RuntimeError(
            "Verification failed after patching. Restore DATA03.before_external_db.bak."
        )

    print()
    print("Patch completed successfully.")
    print("/db/m8_game_list.db ->", NEW_TARGET.decode())
    print()
    print("Next step: run DBMaker_M8_V6_v2.py inside the 'roms' folder.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print()
        print("ERROR:", exc)
        sys.exit(1)
