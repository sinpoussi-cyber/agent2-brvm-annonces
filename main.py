import argparse
from datetime import datetime, timezone

from brvm_scraper import get_new_documents
from pdf_extractor import extract_pdf
from claude_analyzer import analyze
from supabase_client import (
    doc_exists,
    insert_document,
    get_documents_today,
    get_documents_week,
    get_documents_month,
    mark_sent,
)
from report_generator import generate
from email_sender import send_report

# ---------------------------------------------------------------------------
# Pages BRVM à scraper
# ---------------------------------------------------------------------------

BRVM_PAGES = [
    (
        "https://www.brvm.org/fr/emetteurs/type-annonces/convocations-assemblees-generales",
        "Convocations AG",
    ),
    (
        "https://www.brvm.org/fr/emetteurs/type-annonces/communiques",
        "Communiqués",
    ),
    (
        "https://www.brvm.org/fr/marche/avis-et-publications/avis",
        "Avis",
    ),
]


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{ts}] {msg}")


# ---------------------------------------------------------------------------
# Mode : collect
# ---------------------------------------------------------------------------

def _build_collect_html(
    date_str: str,
    total_found: int,
    total_new: int,
    total_errors: int,
    inserted_docs: list,
) -> str:
    rows_html = ""
    for d in inserted_docs:
        titre   = d.get("titre", "")[:80]
        societe = d.get("societe_confirmee") or d.get("societe", "")
        type_doc = d.get("page_source", "")
        date_doc = d.get("date_doc") or ""
        rows_html += (
            f"<tr>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #e0e0e0'>{titre}</td>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #e0e0e0'>{societe}</td>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #e0e0e0'>{type_doc}</td>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #e0e0e0'>{date_doc}</td>"
            f"</tr>"
        )

    if not rows_html:
        rows_html = (
            "<tr><td colspan='4' style='padding:10px;text-align:center;color:#888'>"
            "Aucune nouvelle annonce insérée.</td></tr>"
        )

    return f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f4f6f8;font-family:Arial,sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f8;padding:30px 0">
    <tr><td align="center">
      <table width="620" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.1)">

        <!-- EN-TÊTE -->
        <tr>
          <td style="background:#0d2b4e;padding:24px 30px">
            <h1 style="margin:0;color:#fff;font-size:20px">📢 Agent 2 BRVM — Nouvelles annonces</h1>
            <p style="margin:6px 0 0;color:#a8c4e0;font-size:13px">{date_str}</p>
          </td>
        </tr>

        <!-- STATISTIQUES -->
        <tr>
          <td style="padding:24px 30px 10px">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td align="center" style="background:#e8f0fe;border-radius:6px;padding:14px;width:30%">
                  <div style="font-size:28px;font-weight:bold;color:#0d2b4e">{total_found}</div>
                  <div style="font-size:12px;color:#555;margin-top:4px">PDFs trouvés</div>
                </td>
                <td width="20"></td>
                <td align="center" style="background:#e6f4ea;border-radius:6px;padding:14px;width:30%">
                  <div style="font-size:28px;font-weight:bold;color:#1e7e34">{total_new}</div>
                  <div style="font-size:12px;color:#555;margin-top:4px">Nouveaux insérés</div>
                </td>
                <td width="20"></td>
                <td align="center" style="background:#fce8e6;border-radius:6px;padding:14px;width:30%">
                  <div style="font-size:28px;font-weight:bold;color:#c5221f">{total_errors}</div>
                  <div style="font-size:12px;color:#555;margin-top:4px">Erreurs</div>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- TABLEAU DES NOUVELLES ANNONCES -->
        <tr>
          <td style="padding:20px 30px">
            <h2 style="margin:0 0 12px;font-size:15px;color:#0d2b4e;border-left:4px solid #0d2b4e;padding-left:10px">
              Nouvelles annonces insérées
            </h2>
            <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;font-size:13px">
              <thead>
                <tr style="background:#0d2b4e;color:#fff">
                  <th style="padding:8px 10px;text-align:left;font-weight:600">Titre</th>
                  <th style="padding:8px 10px;text-align:left;font-weight:600">Société</th>
                  <th style="padding:8px 10px;text-align:left;font-weight:600">Type</th>
                  <th style="padding:8px 10px;text-align:left;font-weight:600">Date</th>
                </tr>
              </thead>
              <tbody>
                {rows_html}
              </tbody>
            </table>
          </td>
        </tr>

        <!-- FOOTER -->
        <tr>
          <td style="background:#f4f6f8;padding:16px 30px;border-top:1px solid #e0e0e0">
            <p style="margin:0;font-size:11px;color:#999;text-align:center">
              ⚠️ Cet email est généré automatiquement par l'Agent 2 BRVM. Ne pas répondre à ce message.
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


def mode_collect() -> None:
    log("=== DÉMARRAGE : collecte des documents BRVM ===")

    total_found = 0
    total_new = 0
    total_skipped = 0
    total_errors = 0
    inserted_docs: list = []

    for page_url, page_name in BRVM_PAGES:
        log(f"Scraping : {page_name}")
        documents = get_new_documents(page_url, page_name)
        log(f"  → {len(documents)} PDF(s) trouvé(s) sur la page")
        total_found += len(documents)

        for doc in documents:
            url = doc.get("url", "")
            if not url:
                continue

            # Déduplification
            nom = doc.get("titre") or url.split("/")[-1]
            if doc_exists(url):
                log(f"  [SKIP] Document déjà analysé : {nom[:80]}")
                total_skipped += 1
                continue

            # Extraction PDF
            log(f"  [DL]   Téléchargement : {url[:80]}")
            pdf_data = extract_pdf(url)
            if pdf_data is None:
                log(f"  [ERR]  Extraction PDF échouée — ignoré")
                total_errors += 1
                continue

            # Titre final : préférer celui du PDF s'il est plus riche
            titre = pdf_data.get("titre") or doc.get("titre", "")
            pdf_bytes = pdf_data.get("pdf_bytes", b"")

            # Analyse Claude
            log(f"  [AI]   Analyse Claude : {titre[:60]}")
            analysis = analyze(
                titre=titre,
                pdf_bytes=pdf_bytes,
                url=url,
                page_source=page_name,
            )
            if analysis is None:
                log(f"  [ERR]  Analyse Claude échouée — ignoré")
                total_errors += 1
                continue

            # Construction de la ligne Supabase
            row = {
                "doc_url":          url,
                "titre":            titre,
                "societe":          doc.get("societe", ""),
                "date_doc":         doc.get("date") or None,
                "page_source":      page_name,
                "nb_pages":         0,
                "resume":           analysis.get("resume", ""),
                "points_cles":      analysis.get("points_cles", []),
                "impact":           analysis.get("impact", "neutre"),
                "categorie":        analysis.get("categorie", ""),
                "societe_confirmee": analysis.get("societe_confirmee", ""),
                "envoye_email":     False,
            }

            inserted = insert_document(row)
            if inserted:
                log(f"  [OK]   Inséré : {titre[:60]} ({analysis.get('impact')})")
                inserted_docs.append(row)
                total_new += 1
            else:
                log(f"  [ERR]  Insertion Supabase échouée")
                total_errors += 1

    log("=== RÉSUMÉ COLLECTE ===")
    log(f"  Pages scrapées  : {len(BRVM_PAGES)}")
    log(f"  PDF trouvés     : {total_found}")
    log(f"  Nouveaux insérés: {total_new}")
    log(f"  Ignorés (déjà en base) : {total_skipped}")
    log(f"  Erreurs         : {total_errors}")
    log("=== FIN collecte ===")

    date_str = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    subject = f"📢 Agent 2 BRVM — Nouvelles annonces — {date_str}"
    html_body = _build_collect_html(date_str, total_found, total_new, total_errors, inserted_docs)
    log("Envoi de l'email de collecte...")
    ok = send_report(subject=subject, html_body=html_body)
    log(f"  → Email collect : {'OK' if ok else 'ÉCHEC'}")


# ---------------------------------------------------------------------------
# Modes : rapports
# ---------------------------------------------------------------------------

def _send_rapport(type_rapport: str, fetch_fn, label: str) -> None:
    log(f"=== DÉMARRAGE : rapport {label} ===")

    log(f"Récupération des documents ({label})...")
    documents = fetch_fn()
    log(f"  → {len(documents)} document(s) trouvé(s)")

    log("Génération du rapport...")
    report = generate(documents, type_rapport)
    log(f"  → Objet : {report['subject']}")

    log("Envoi de l'email...")
    success = send_report(
        subject=report["subject"],
        html_body=report["body_html"],
    )

    if success:
        ids = [d["id"] for d in documents if d.get("id")]
        if ids:
            mark_sent(ids)
            log(f"  → {len(ids)} document(s) marqué(s) comme envoyé(s)")
        log(f"=== FIN rapport {label} : OK ===")
    else:
        log(f"=== FIN rapport {label} : ÉCHEC envoi email ===")


def mode_rapport_jour() -> None:
    _send_rapport("journalier", get_documents_today, "journalier")


def mode_rapport_hebdo() -> None:
    _send_rapport("hebdo", get_documents_week, "hebdomadaire")


def mode_rapport_mensuel() -> None:
    _send_rapport("mensuel", get_documents_month, "mensuel")


# ---------------------------------------------------------------------------
# Entrée principale
# ---------------------------------------------------------------------------

MODES = {
    "collect":        mode_collect,
    "rapport-jour":   mode_rapport_jour,
    "rapport-hebdo":  mode_rapport_hebdo,
    "rapport-mensuel": mode_rapport_mensuel,
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Agent BRVM — collecte et envoi de rapports financiers",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=list(MODES.keys()),
        metavar="MODE",
        help=(
            "Mode d'exécution :\n"
            "  collect         — scrape les 3 pages BRVM et stocke les nouveaux documents\n"
            "  rapport-jour    — envoie le rapport des documents du jour\n"
            "  rapport-hebdo   — envoie le rapport des 7 derniers jours\n"
            "  rapport-mensuel — envoie le rapport du mois en cours"
        ),
    )

    args = parser.parse_args()
    MODES[args.mode]()


if __name__ == "__main__":
    main()
