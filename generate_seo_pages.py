#!/usr/bin/env python3
"""Déploie l’archive SEO puis enrichit la page d’accueil existante."""
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


def enrich_homepage() -> None:
    path = ROOT / "index.html"
    text = path.read_text(encoding="utf-8")
    robots = '  <meta name="robots" content="index,follow" />'
    if 'rel="canonical" href="https://meridienne-tapissier.fr/"' not in text:
        seo_head = '''  <link rel="canonical" href="https://meridienne-tapissier.fr/" />
  <meta property="og:type" content="website" />
  <meta property="og:locale" content="fr_FR" />
  <meta property="og:title" content="Méridienne – Cédric Rainssant | Tapissier Décorateur 85" />
  <meta property="og:description" content="Tapissier décorateur à Saint-Gilles-Croix-de-Vie. Restauration de sièges, rideaux et tissus d’éditeur." />
  <meta property="og:url" content="https://meridienne-tapissier.fr/" />
  <meta property="og:image" content="https://i.imgur.com/O4sZKGk.png" />
  <meta name="twitter:card" content="summary_large_image" />
  <script type="application/ld+json">{"@context":"https://schema.org","@type":"LocalBusiness","@id":"https://meridienne-tapissier.fr/#business","name":"Méridienne — Cédric Rainssant","url":"https://meridienne-tapissier.fr/","telephone":"+33251351872","email":"meridienne.tapissier@orange.fr","address":{"@type":"PostalAddress","streetAddress":"32 Boulevard de l’Égalité","postalCode":"85800","addressLocality":"Saint-Gilles-Croix-de-Vie","addressCountry":"FR"},"areaServed":["Saint-Gilles-Croix-de-Vie","Saint-Hilaire-de-Riez","Le Fenouiller","Givrand","Brétignolles-sur-Mer","Challans","Les Sables-d’Olonne"]}</script>'''
        if robots not in text:
            raise SystemExit("Balise robots de la page d’accueil introuvable")
        text = text.replace(robots, robots + "\n" + seo_head, 1)

    if 'href="/services/"' not in text:
        navigation_marker = '        <a href="#services">Savoir-faire</a>'
        navigation_links = navigation_marker + '\n        <a href="/services/">Services détaillés</a>\n        <a href="/zones/">Zones desservies</a>'
        if navigation_marker not in text:
            raise SystemExit("Navigation de la page d’accueil introuvable")
        text = text.replace(navigation_marker, navigation_links, 1)

    path.write_text(text, encoding="utf-8")


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

    enrich_homepage()
    print("Pages SEO extraites et page d’accueil enrichie avec succès.")


if __name__ == "__main__":
    main()
