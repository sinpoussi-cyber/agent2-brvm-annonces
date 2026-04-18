import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

BRVM_BASE = "https://www.brvm.org"

# Pages to scrape
PAGES = [
    ("https://www.brvm.org/fr/emetteurs/type-annonces/convocations-assemblees-generales", "Convocations AG"),
    ("https://www.brvm.org/fr/emetteurs/type-annonces/communiques", "Communiqués"),
    ("https://www.brvm.org/fr/marche/avis-et-publications/avis", "Avis"),
]

# Common company suffixes to help extraction
COMPANY_SUFFIXES = r"\b(SA|SA\.|SARL|SAS|CI|BF|SN|TG|BJ|ML|GN|NE|CM)\b"


def _extract_societe(titre: str) -> str:
    """Best-effort extraction of company name from document title."""
    if not titre:
        return ""
    # Pattern: "Convocation AG - SOCIÉTÉ XYZ SA" or "SOCIÉTÉ XYZ SA : ..."
    for sep in [" - ", " : ", " | ", " / "]:
        parts = titre.split(sep)
        for part in parts:
            part = part.strip()
            if re.search(COMPANY_SUFFIXES, part, re.IGNORECASE):
                return part
    # Fallback: return first capitalised segment
    words = titre.strip().split()
    if words:
        return words[0].title()
    return ""


def _extract_date(text: str) -> str:
    """Try to parse a date string from surrounding text."""
    patterns = [
        r"\b(\d{2}[/-]\d{2}[/-]\d{4})\b",   # DD/MM/YYYY or DD-MM-YYYY
        r"\b(\d{4}[/-]\d{2}[/-]\d{2})\b",   # YYYY-MM-DD
        r"\b(\d{1,2}\s+\w+\s+\d{4})\b",     # 5 janvier 2024
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return ""


def _resolve_url(href: str) -> str:
    """Make relative URLs absolute."""
    if href.startswith("http"):
        return href
    return BRVM_BASE + href if href.startswith("/") else BRVM_BASE + "/" + href


def _find_context_text(tag) -> str:
    """Return the text of the nearest meaningful ancestor (row, list item, div)."""
    for parent_tag in ["tr", "li", "div", "p", "article"]:
        ancestor = tag.find_parent(parent_tag)
        if ancestor:
            return ancestor.get_text(separator=" ", strip=True)
    return tag.get_text(strip=True)


def get_new_documents(page_url: str, page_name: str) -> list[dict]:
    """
    Scrape a BRVM page and return all PDF document metadata found.

    Returns a list of dicts:
        {url, titre, societe, date, page_source}
    """
    try:
        response = requests.get(page_url, headers=HEADERS, timeout=15, verify=False)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"[brvm_scraper] Erreur lors du chargement de '{page_name}': {e}")
        return []

    try:
        soup = BeautifulSoup(response.text, "html.parser")
        documents = []
        seen_urls = set()

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if ".pdf" not in href.lower():
                continue

            pdf_url = _resolve_url(href)
            if pdf_url in seen_urls:
                continue
            seen_urls.add(pdf_url)

            # Title: prefer link text, fall back to title attribute
            titre = a_tag.get_text(strip=True) or a_tag.get("title", "")
            if not titre:
                # Try sibling or parent text
                parent_text = _find_context_text(a_tag)
                # Remove the URL itself from parent text to keep it clean
                titre = parent_text[:200]

            context_text = _find_context_text(a_tag)
            date = _extract_date(context_text)
            societe = _extract_societe(titre)

            documents.append({
                "url": pdf_url,
                "titre": titre,
                "societe": societe,
                "date": date,
                "page_source": page_name,
            })

        return documents

    except Exception as e:
        print(f"[brvm_scraper] Erreur lors du parsing de '{page_name}': {e}")
        return []


if __name__ == "__main__":
    for url, name in PAGES:
        docs = get_new_documents(url, name)
        print(f"\n=== {name} : {len(docs)} PDF(s) trouvé(s) ===")
        for d in docs[:3]:
            print(f"  - {d['titre'][:60]} | {d['societe']} | {d['date']}")
            print(f"    {d['url']}")
