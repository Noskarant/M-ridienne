#!/usr/bin/env python3
"""Generate the reviewed static SEO pages for meridienne-tapissier.fr."""
from pathlib import Path
import base64
import io
import lzma
import tarfile

root = Path(__file__).resolve().parent
payload_b64 = "".join(
    (root / "seo_payload" / f"part{i:02d}.txt").read_text(encoding="utf-8").strip()
    for i in range(1, 7)
)
payload = lzma.decompress(base64.b64decode(payload_b64))

with tarfile.open(fileobj=io.BytesIO(payload), mode="r:") as archive:
    root_resolved = root.resolve()
    for member in archive.getmembers():
        target = (root / member.name).resolve()
        if target != root_resolved and root_resolved not in target.parents:
            raise RuntimeError(f"Unsafe archive path: {member.name}")
    archive.extractall(root, filter="data")

print(f"SEO pages generated in {root}")
