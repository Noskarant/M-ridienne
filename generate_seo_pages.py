#!/usr/bin/env python3
"""Déploie l’archive statique SEO stockée en plusieurs fragments base64."""
from __future__ import annotations

import base64
import io
import lzma
import shutil
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PARTS_DIR = ROOT / "seo_payload_final"
TARGET_DIRS = ("assets", "services", "zones")
TARGET_FILES = ("robots.txt", "sitemap.xml", "merci.html")


def main() -> None:
    parts = sorted(PARTS_DIR.glob("part*.txt"))
    if len(parts) != 8:
        raise SystemExit(f"8 fragments attendus, {len(parts)} trouvés")
    encoded = "".join(p.read_text(encoding="utf-8").strip() for p in parts)
    compressed = base64.b64decode(encoded, validate=True)
    archive_bytes = lzma.decompress(compressed)

    for name in TARGET_DIRS:
        path = ROOT / name
        if path.exists():
            shutil.rmtree(path)
    for name in TARGET_FILES:
        path = ROOT / name
        if path.exists():
            path.unlink()

    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:") as archive:
        for member in archive.getmembers():
            target = (ROOT / member.name).resolve()
            if ROOT.resolve() not in target.parents and target != ROOT.resolve():
                raise SystemExit(f"Chemin interdit dans l’archive : {member.name}")
        archive.extractall(ROOT, filter="data")

    print("Pages SEO extraites avec succès.")


if __name__ == "__main__":
    main()
