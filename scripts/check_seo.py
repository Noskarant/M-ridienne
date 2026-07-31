from __future__ import annotations

from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree as ET
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = "https://meridienne-tapissier.fr"
EXPECTED_URLS = {
    f"{DOMAIN}/",
    f"{DOMAIN}/services/",
    f"{DOMAIN}/services/tapissier-ameublement/",
    f"{DOMAIN}/services/restauration-fauteuils-sieges/",
    f"{DOMAIN}/services/rideaux-voilages-sur-mesure/",
    f"{DOMAIN}/services/stores-interieurs-sur-mesure/",
    f"{DOMAIN}/services/tissus-ameublement-editeurs/",
    f"{DOMAIN}/services/restauration-boiseries-sieges/",
    f"{DOMAIN}/services/coussins-sur-mesure/",
    f"{DOMAIN}/services/decoupe-mousse-banquettes-matelas/",
    f"{DOMAIN}/zones/",
    f"{DOMAIN}/zones/tapissier-saint-hilaire-de-riez/",
    f"{DOMAIN}/zones/tapissier-le-fenouiller/",
    f"{DOMAIN}/zones/tapissier-givrand/",
    f"{DOMAIN}/zones/tapissier-notre-dame-de-riez/",
    f"{DOMAIN}/zones/tapissier-bretignolles-sur-mer/",
    f"{DOMAIN}/zones/tapissier-aiguillon-sur-vie/",
    f"{DOMAIN}/zones/tapissier-saint-reverend/",
    f"{DOMAIN}/zones/tapissier-saint-maixent-sur-vie/",
    f"{DOMAIN}/zones/tapissier-commequiers/",
    f"{DOMAIN}/zones/tapissier-coex/",
    f"{DOMAIN}/zones/tapissier-brem-sur-mer/",
    f"{DOMAIN}/zones/tapissier-la-chaize-giraud/",
    f"{DOMAIN}/zones/tapissier-landevieille/",
    f"{DOMAIN}/zones/tapissier-challans/",
    f"{DOMAIN}/zones/tapissier-soullans/",
    f"{DOMAIN}/zones/tapissier-les-sables-d-olonne/",
}


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_title = False
        self.in_json = False
        self.in_article = False
        self.title_parts: list[str] = []
        self.article_parts: list[str] = []
        self.h1_count = 0
        self.description: str | None = None
        self.canonical: str | None = None
        self.robots: str | None = None
        self.json_buffer: list[str] = []
        self.json_scripts: list[str] = []
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "title":
            self.in_title = True
        elif tag == "h1":
            self.h1_count += 1
        elif tag == "article":
            self.in_article = True
        elif tag == "meta":
            if attributes.get("name") == "description":
                self.description = attributes.get("content")
            elif attributes.get("name") == "robots":
                self.robots = attributes.get("content")
        elif tag == "link" and attributes.get("rel") == "canonical":
            self.canonical = attributes.get("href")
        elif tag == "script" and attributes.get("type") == "application/ld+json":
            self.in_json = True
            self.json_buffer = []
        elif tag == "a" and attributes.get("href"):
            self.links.append(attributes["href"] or "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        elif tag == "article":
            self.in_article = False
        elif tag == "script" and self.in_json:
            self.json_scripts.append("".join(self.json_buffer))
            self.in_json = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)
        if self.in_article:
            self.article_parts.append(data)
        if self.in_json:
            self.json_buffer.append(data)


def target_for_internal_link(href: str) -> Path | None:
    parsed = urlparse(href)
    if parsed.scheme or parsed.netloc or href.startswith(("mailto:", "tel:", "javascript:")):
        return None
    path = parsed.path
    if not path or path == "/":
        return ROOT / "index.html"
    if path.endswith("/"):
        return ROOT / path.lstrip("/") / "index.html"
    return ROOT / path.lstrip("/")


def trigrams(text: str) -> Counter[tuple[str, str, str]]:
    words = re.findall(r"[a-zà-ÿ'-]+", text.lower())
    return Counter(zip(words, words[1:], words[2:]))


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    titles: dict[str, str] = {}
    descriptions: dict[str, str] = {}
    canonicals: dict[str, str] = {}
    parsed_pages: dict[str, PageParser] = {}

    html_files = sorted(ROOT.rglob("*.html"))
    for file in html_files:
        rel = file.relative_to(ROOT).as_posix()
        parser = PageParser()
        parser.feed(file.read_text(encoding="utf-8"))
        parsed_pages[rel] = parser
        title = "".join(parser.title_parts).strip()

        if not title:
            errors.append(f"{rel}: title manquant")

        if rel == "merci.html":
            if parser.robots != "noindex,follow":
                errors.append("merci.html: robots doit être noindex,follow")
            continue

        if not parser.description:
            errors.append(f"{rel}: meta description manquante")
        if parser.h1_count != 1:
            errors.append(f"{rel}: {parser.h1_count} H1 au lieu de 1")
        if not parser.canonical:
            errors.append(f"{rel}: canonical manquante")
        if parser.robots != "index,follow":
            errors.append(f"{rel}: robots doit être index,follow")

        if title in titles:
            errors.append(f"title dupliqué: {rel} / {titles[title]}")
        titles[title] = rel
        if parser.description in descriptions:
            errors.append(f"description dupliquée: {rel} / {descriptions[parser.description]}")
        descriptions[parser.description or ""] = rel
        if parser.canonical in canonicals:
            errors.append(f"canonical dupliquée: {rel} / {canonicals[parser.canonical or '']}")
        canonicals[parser.canonical or ""] = rel

        for raw in parser.json_scripts:
            try:
                json.loads(raw)
            except json.JSONDecodeError as exc:
                errors.append(f"{rel}: JSON-LD invalide: {exc}")

        for href in parser.links:
            target = target_for_internal_link(href)
            if target is None:
                continue
            # The staging directory may intentionally omit the existing root homepage.
            if target == ROOT / "index.html" and not target.exists():
                continue
            if not target.exists():
                errors.append(f"{rel}: lien interne cassé vers {href}")

    sitemap_path = ROOT / "sitemap.xml"
    tree = ET.parse(sitemap_path)
    namespace = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    sitemap_urls = [node.text or "" for node in tree.findall(".//s:loc", namespace)]
    sitemap_set = set(sitemap_urls)
    if sitemap_set != EXPECTED_URLS:
        missing = sorted(EXPECTED_URLS - sitemap_set)
        extra = sorted(sitemap_set - EXPECTED_URLS)
        if missing:
            errors.append("sitemap: URL manquantes: " + ", ".join(missing))
        if extra:
            errors.append("sitemap: URL inattendues: " + ", ".join(extra))
    if len(sitemap_urls) != len(sitemap_set):
        errors.append("sitemap: URL dupliquée")
    if any("merci" in url for url in sitemap_urls):
        errors.append("sitemap: merci.html ne doit pas être présente")

    robots = (ROOT / "robots.txt").read_text(encoding="utf-8")
    if "User-agent: *" not in robots or "Allow: /" not in robots:
        errors.append("robots.txt: directives d’exploration incorrectes")
    if f"Sitemap: {DOMAIN}/sitemap.xml" not in robots:
        errors.append("robots.txt: déclaration du sitemap manquante")

    # Verify that every generated indexable page is linked by at least one other generated page.
    incoming: Counter[str] = Counter()
    for rel, parser in parsed_pages.items():
        for href in parser.links:
            target = target_for_internal_link(href)
            if target is None:
                continue
            try:
                target_rel = target.relative_to(ROOT).as_posix()
            except ValueError:
                continue
            incoming[target_rel] += 1
    for rel in parsed_pages:
        if rel in {"merci.html", "index.html"}:
            continue
        if incoming[rel] == 0:
            errors.append(f"{rel}: page orpheline")

    # Prevent near-duplicate local landing pages by comparing article trigrams.
    zone_articles: dict[str, Counter[tuple[str, str, str]]] = {}
    for rel, parser in parsed_pages.items():
        if rel.startswith("zones/tapissier-"):
            zone_articles[rel] = trigrams(" ".join(parser.article_parts))
    zone_items = list(zone_articles.items())
    for index, (rel_a, grams_a) in enumerate(zone_items):
        for rel_b, grams_b in zone_items[index + 1 :]:
            intersection = sum((grams_a & grams_b).values())
            union = sum((grams_a | grams_b).values())
            similarity = intersection / union if union else 0
            if similarity > 0.25:
                errors.append(f"contenu local trop similaire ({similarity:.2f}): {rel_a} / {rel_b}")

    if not (ROOT / "index.html").exists():
        warnings.append("index.html existant non inclus dans ce dossier de staging; il sera conservé par son blob GitHub.")

    if errors:
        print("\n".join(f"ERREUR: {error}" for error in errors))
        return 1
    print(
        f"OK: {len(html_files)} fichiers HTML générés, {len(sitemap_urls)} URL sitemap, "
        "métadonnées uniques, JSON-LD valide, liens internes valides et pages locales distinctes."
    )
    for warning in warnings:
        print(f"AVERTISSEMENT: {warning}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
