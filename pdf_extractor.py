import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def extract_pdf(url: str) -> dict | None:
    """
    Download a PDF from `url` and return its raw bytes.

    Returns:
        {url, pdf_bytes, titre}  or  None on failure.
    """
    try:
        response = requests.get(url, headers=HEADERS, timeout=20, verify=False)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"[pdf_extractor] Erreur téléchargement ({url}): {e}")
        return None

    content_type = response.headers.get("Content-Type", "")
    if "pdf" not in content_type.lower() and not url.lower().endswith(".pdf"):
        print(f"[pdf_extractor] Contenu non-PDF ignoré ({content_type}): {url}")
        return None

    titre = (
        url.rstrip("/").split("/")[-1]
        .replace(".pdf", "")
        .replace("-", " ")
        .replace("_", " ")
        .strip()
    )

    return {
        "url": url,
        "pdf_bytes": response.content,
        "titre": titre,
    }


if __name__ == "__main__":
    test_url = input("URL du PDF à tester : ").strip()
    result = extract_pdf(test_url)
    if result:
        print(f"Titre : {result['titre']}")
        print(f"Taille: {len(result['pdf_bytes'])} octets")
    else:
        print("Échec du téléchargement.")
