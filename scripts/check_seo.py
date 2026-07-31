#!/usr/bin/env python3
"""Contrôles SEO statiques pour meridienne-tapissier.fr (stdlib uniquement)."""
from __future__ import annotations

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = "https://meridienne-tapissier.fr"
EXPECTED = [
    "/", "/services/", "/services/tapissier-ameublement/",
    "/services/restauration-fauteuils-sieges/",
    "/services/rideaux-voilages-sur-mesure/",
    "/services/stores-interieurs-sur-mesure/",
    "/services/tissus-ameublement-editeurs/",
    "/services/restauration-boiseries-sieges/",
    "/services/coussins-sur-mesure/",
    "/services/decoupe-mousse-banquettes-matelas/", "/zones/",
    "/zones/tapissier-saint-hilaire-de-riez/",
    "/zones/tapissier-le-fenouiller/", "/zones/tapissier-givrand/",
    "/zones/tapissier-notre-dame-de-riez/",
    "/zones/tapissier-bretignolles-sur-mer/",
    "/zones/tapissier-aiguillon-sur-vie/",
    "/zones/tapissier-saint-reverend/",
    "/zones/tapissier-saint-maixent-sur-vie/",
    "/zones/tapissier-commequiers/", "/zones/tapissier-coex/",
    "/zones/tapissier-brem-sur-mer/",
    "/zones/tapissier-la-chaize-giraud/",
    "/zones/tapissier-landevieille/", "/zones/tapissier-challans/",
    "/zones/tapissier-soullans/",
    "/zones/tapissier-les-sables-d-olonne/",
]


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.descriptions: list[str] = []
        self.canonicals: list[str] = []
        self.h1_count = 0
        self.links: list[str] = []
        self.json_ld: list[str] = []
        self._capture: str | None = None
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        attrs = dict(attrs_list)
        if tag == "title":
            self._capture, self._buffer = "title", []
        elif tag == "h1":
            self.h1_count += 1
        elif tag == "meta" and (attrs.get("name") or "").lower() == "description":
            self.descriptions.append(attrs.get("content") or "")
        elif tag == "link" and (attrs.get("rel") or "").lower() == "canonical":
            self.canonicals.append(attrs.get("href") or "")
        elif tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"] or "")
        elif tag == "script" and (attrs.get("type") or "").lower() == "application/ld+json":
            self._capture, self._buffer = "json", []

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title" and self._capture == "title":
            self.title = "".join(self._buffer).strip()
            self._capture = None
        elif tag == "script" and self._capture == "json":
            self.json_ld.append("".join(self._buffer).strip())
            self._capture = None


def path_for_url(path: str) -> Path:
    return ROOT / "index.html" if path == "/" else ROOT / path.strip("/") / "index.html"


def internal_target(href: str) -> Path | None:
    if href.startswith(("mailto:", "tel:", "#", "javascript:")):
        return None
    parsed = urlparse(href)
    if parsed.scheme and parsed.netloc != "meridienne-tapissier.fr":
        return None
    path = parsed.path
    if not path or path == "/":
        return ROOT / "index.html"
    if path.endswith("/"):
        return ROOT / path.strip("/") / "index.html"
    return ROOT / path.lstrip("/")


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def main() -> int:
    errors: list[str] = []
    titles: dict[str, Path] = {}
    descriptions: dict[str, Path] = {}
    canonicals: dict[str, Path] = {}

    sitemap = ROOT / "sitemap.xml"
    if not sitemap.exists():
        fail(errors, "sitemap.xml absent")
        sitemap_urls: list[str] = []
    else:
        tree = ET.parse(sitemap)
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        sitemap_urls = [e.text or "" for e in tree.findall("s:url/s:loc", ns)]
        expected_urls = [DOMAIN + p for p in EXPECTED]
        if sitemap_urls != expected_urls:
            fail(errors, "Le sitemap ne contient pas exactement les 27 URL attendues dans l’ordre prévu")
        if any("merci" in u for u in sitemap_urls):
            fail(errors, "merci.html ne doit pas figurer dans le sitemap")

    for url_path in EXPECTED:
        page = path_for_url(url_path)
        if not page.exists():
            fail(errors, f"Page absente : {page.relative_to(ROOT)}")
            continue
        parser = PageParser()
        parser.feed(page.read_text(encoding="utf-8"))
        rel = page.relative_to(ROOT)
        if not parser.title:
            fail(errors, f"Title absent : {rel}")
        elif parser.title in titles:
            fail(errors, f"Title dupliqué : {rel} et {titles[parser.title].relative_to(ROOT)}")
        else:
            titles[parser.title] = page
        if len(parser.descriptions) != 1 or not parser.descriptions[0].strip():
            fail(errors, f"Meta description invalide : {rel}")
        elif parser.descriptions[0] in descriptions:
            fail(errors, f"Description dupliquée : {rel}")
        else:
            descriptions[parser.descriptions[0]] = page
        if parser.h1_count != 1:
            fail(errors, f"Nombre de H1 = {parser.h1_count} : {rel}")
        expected_canonical = DOMAIN + url_path
        if parser.canonicals != [expected_canonical]:
            fail(errors, f"Canonical invalide : {rel}")
        elif expected_canonical in canonicals:
            fail(errors, f"Canonical dupliquée : {rel}")
        else:
            canonicals[expected_canonical] = page
        if not parser.json_ld:
            fail(errors, f"JSON-LD absent : {rel}")
        for block in parser.json_ld:
            try:
                json.loads(block)
            except json.JSONDecodeError as exc:
                fail(errors, f"JSON-LD invalide dans {rel}: {exc}")
        for href in parser.links:
            target = internal_target(href)
            if target is not None and not target.exists():
                fail(errors, f"Lien cassé dans {rel}: {href}")

    merci = (ROOT / "merci.html").read_text(encoding="utf-8") if (ROOT / "merci.html").exists() else ""
    if not re.search(r'<meta\s+name=["\']robots["\']\s+content=["\']noindex,follow["\']', merci, re.I):
        fail(errors, "merci.html doit contenir noindex,follow")
    robots = (ROOT / "robots.txt").read_text(encoding="utf-8") if (ROOT / "robots.txt").exists() else ""
    if f"Sitemap: {DOMAIN}/sitemap.xml" not in robots:
        fail(errors, "Déclaration sitemap absente de robots.txt")

    if errors:
        print("ÉCHEC SEO :")
        for error in errors:
            print(f"- {error}")
        return 1
    print("OK : 27 URL, titres et descriptions uniques, H1/canonical valides, JSON-LD lisible et liens internes présents.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
