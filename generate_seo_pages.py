#!/usr/bin/env python3
"""Generate the reviewed static SEO pages for meridienne-tapissier.fr."""
from pathlib import Path
import base64
import io
import lzma
import tarfile

root = Path(__file__).resolve().parent
parts = sorted((root / "seo_payload_v2").glob("part*.txt"))
if not parts:
    raise RuntimeError("No SEO payload parts found")
payload_b64 = "".join(part.read_text(encoding="utf-8").strip() for part in parts)
payload = lzma.decompress(base64.b64decode(payload_b64, validate=True))

with tarfile.open(fileobj=io.BytesIO(payload), mode="r:") as archive:
    root_resolved = root.resolve()
    for member in archive.getmembers():
        target = (root / member.name).resolve()
        if target != root_resolved and root_resolved not in target.parents:
            raise RuntimeError(f"Unsafe archive path: {member.name}")
    archive.extractall(root, filter="data")

print(f"SEO pages generated in {root} from {len(parts)} payload parts")
