#!/usr/bin/env python3
"""Standalone migration script: mtk -> mail-memex.

Copies config and database from old mtk paths to new mail-memex paths.
Not part of the mail-memex package. Run once, then delete.

Usage:
    python scripts/migrate-from-mtk.py
    python scripts/migrate-from-mtk.py --dry-run
"""
import shutil, sys
from pathlib import Path

def main() -> None:
    dry_run = "--dry-run" in sys.argv
    old_config = Path.home() / ".config" / "mtk" / "config.yaml"
    new_config = Path.home() / ".config" / "mail-memex" / "config.yaml"
    old_db = Path.home() / ".local" / "share" / "mtk" / "mtk.db"
    new_db = Path.home() / ".local" / "share" / "mail-memex" / "mail-memex.db"

    actions = []
    if old_config.exists() and not new_config.exists():
        actions.append(("config", old_config, new_config))
    elif old_config.exists():
        print(f"SKIP: {new_config} already exists")
    else:
        print(f"SKIP: {old_config} not found")

    if old_db.exists() and not new_db.exists():
        actions.append(("database", old_db, new_db))
        for suffix in ("-wal", "-shm"):
            sidecar = old_db.with_name(old_db.name + suffix)
            if sidecar.exists():
                new_sidecar = new_db.with_name(new_db.name + suffix)
                actions.append(("sidecar", sidecar, new_sidecar))
    elif old_db.exists():
        print(f"SKIP: {new_db} already exists")
    else:
        print(f"SKIP: {old_db} not found")

    if not actions:
        print("Nothing to migrate.")
        return

    for kind, src, dst in actions:
        if dry_run:
            print(f"WOULD COPY {kind}: {src} -> {dst}")
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            print(f"COPIED {kind}: {src} -> {dst}")

    if not dry_run and new_config.exists():
        text = new_config.read_text()
        text = text.replace(str(old_db), str(new_db))
        text = text.replace("mtk.db", "mail-memex.db")
        new_config.write_text(text)
        print(f"UPDATED db_path in {new_config}")

    if dry_run:
        print("\nDry run complete. Run without --dry-run to execute.")
    else:
        print("\nMigration complete. Verify mail-memex works, then remove old paths.")

if __name__ == "__main__":
    main()
