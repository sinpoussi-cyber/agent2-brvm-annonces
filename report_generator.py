from datetime import datetime, timezone
from collections import defaultdict

BRVM_BLUE = "#003F8A"
BRVM_LIGHT = "#E8F0FA"

IMPACT_STYLE = {
    "positif":  {"bg": "#D4EDDA", "color": "#155724", "label": "Positif"},
    "négatif":  {"bg": "#F8D7DA", "color": "#721C24", "label": "Négatif"},
    "neutre":   {"bg": "#E2E3E5", "color": "#383D41", "label": "Neutre"},
}

TYPE_LABELS = {
    "journalier": "Rapport journalier",
    "hebdo":      "Rapport hebdomadaire",
    "mensuel":    "Rapport mensuel",
}

SOURCE_ORDER = [
    "Convocations AG",
    "Communiqués",
    "Avis",
]


def _today_str() -> str:
    now = datetime.now(timezone.utc)
    MONTHS = [
        "", "janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre",
    ]
    return f"{now.day} {MONTHS[now.month]} {now.year}"


def _build_subject(type_rapport: str, page_source: str | None) -> str:
    label = TYPE_LABELS.get(type_rapport, type_rapport.capitalize())
    source_part = f" — {page_source}" if page_source else ""
    return f"{label} BRVM{source_part} — {_today_str()}"


def _impact_badge_html(impact: str) -> str:
    style = IMPACT_STYLE.get(impact, IMPACT_STYLE["neutre"])
    return (
        f'<span style="display:inline-block;padding:2px 10px;border-radius:12px;'
        f'font-size:12px;font-weight:bold;'
        f'background:{style["bg"]};color:{style["color"]};">'
        f'{style["label"]}</span>'
    )


def _doc_html(doc: dict) -> str:
    points = doc.get("points_cles") or []
    points_li = "".join(f"<li>{p}</li>" for p in points)
    impact = (doc.get("impact") or "neutre").lower()
    badge = _impact_badge_html(impact)
    url = doc.get("doc_url") or doc.get("url", "#")
    societe = doc.get("societe_confirmee") or doc.get("societe", "—")
    titre = doc.get("titre", "Sans titre")
    resume = doc.get("resume", "")

    return f"""
    <div style="background:#fff;border:1px solid #dde3ec;border-radius:6px;
                padding:16px 20px;margin-bottom:14px;">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;
                  flex-wrap:wrap;gap:6px;">
        <div>
          <span style="font-size:13px;font-weight:600;color:{BRVM_BLUE};">{societe}</span>
          <p style="margin:4px 0 0;font-size:14px;font-weight:bold;color:#1a1a1a;">{titre}</p>
        </div>
        <div>{badge}</div>
      </div>
      {"<p style='margin:10px 0 0;font-size:13px;color:#444;line-height:1.5;'>" + resume + "</p>" if resume else ""}
      {"<ul style='margin:8px 0 0;padding-left:18px;font-size:13px;color:#333;line-height:1.7;'>" + points_li + "</ul>" if points_li else ""}
      <p style="margin:10px 0 0;">
        <a href="{url}" style="font-size:12px;color:{BRVM_BLUE};text-decoration:none;
           border:1px solid {BRVM_BLUE};padding:3px 10px;border-radius:4px;">
          Voir le document PDF →
        </a>
      </p>
    </div>"""


def _section_html(source: str, docs: list[dict]) -> str:
    docs_html = "".join(_doc_html(d) for d in docs)
    return f"""
  <div style="margin-bottom:28px;">
    <h2 style="margin:0 0 12px;font-size:15px;font-weight:700;color:{BRVM_BLUE};
               border-bottom:2px solid {BRVM_BLUE};padding-bottom:6px;">{source} ({len(docs)})</h2>
    {docs_html}
  </div>"""


def _summary_table_html(by_source: dict[str, list]) -> str:
    rows = ""
    total_docs = 0
    total_pos = total_neg = total_neu = 0

    for source in SOURCE_ORDER:
        docs = by_source.get(source, [])
        if not docs:
            continue
        pos = sum(1 for d in docs if (d.get("impact") or "").lower() == "positif")
        neg = sum(1 for d in docs if (d.get("impact") or "").lower() == "négatif")
        neu = len(docs) - pos - neg
        total_docs += len(docs)
        total_pos += pos; total_neg += neg; total_neu += neu
        rows += f"""
      <tr>
        <td style="padding:7px 12px;border-bottom:1px solid #eee;">{source}</td>
        <td style="padding:7px 12px;border-bottom:1px solid #eee;text-align:center;">{len(docs)}</td>
        <td style="padding:7px 12px;border-bottom:1px solid #eee;text-align:center;color:#155724;">{pos}</td>
        <td style="padding:7px 12px;border-bottom:1px solid #eee;text-align:center;color:#383D41;">{neu}</td>
        <td style="padding:7px 12px;border-bottom:1px solid #eee;text-align:center;color:#721C24;">{neg}</td>
      </tr>"""

    return f"""
  <div style="margin-bottom:28px;">
    <h2 style="margin:0 0 12px;font-size:15px;font-weight:700;color:{BRVM_BLUE};
               border-bottom:2px solid {BRVM_BLUE};padding-bottom:6px;">Récapitulatif</h2>
    <table style="width:100%;border-collapse:collapse;font-size:13px;">
      <thead>
        <tr style="background:{BRVM_LIGHT};">
          <th style="padding:8px 12px;text-align:left;font-weight:600;">Source</th>
          <th style="padding:8px 12px;text-align:center;font-weight:600;">Total</th>
          <th style="padding:8px 12px;text-align:center;font-weight:600;color:#155724;">Positif</th>
          <th style="padding:8px 12px;text-align:center;font-weight:600;color:#383D41;">Neutre</th>
          <th style="padding:8px 12px;text-align:center;font-weight:600;color:#721C24;">Négatif</th>
        </tr>
      </thead>
      <tbody>
        {rows}
        <tr style="background:{BRVM_LIGHT};font-weight:700;">
          <td style="padding:8px 12px;">TOTAL</td>
          <td style="padding:8px 12px;text-align:center;">{total_docs}</td>
          <td style="padding:8px 12px;text-align:center;color:#155724;">{total_pos}</td>
          <td style="padding:8px 12px;text-align:center;color:#383D41;">{total_neu}</td>
          <td style="padding:8px 12px;text-align:center;color:#721C24;">{total_neg}</td>
        </tr>
      </tbody>
    </table>
  </div>"""


def _build_html(subject: str, by_source: dict[str, list], type_rapport: str) -> str:
    label = TYPE_LABELS.get(type_rapport, type_rapport.capitalize())
    sections = "".join(
        _section_html(src, by_source[src])
        for src in SOURCE_ORDER
        if by_source.get(src)
    )
    summary = _summary_table_html(by_source)
    total = sum(len(v) for v in by_source.values())

    return f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f4f6fb;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6fb;padding:24px 0;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0"
             style="background:#fff;border-radius:8px;overflow:hidden;
                    box-shadow:0 2px 8px rgba(0,0,0,.08);">

        <!-- HEADER -->
        <tr>
          <td style="background:{BRVM_BLUE};padding:24px 28px;">
            <p style="margin:0;font-size:11px;color:#a8c4e8;letter-spacing:1px;
                      text-transform:uppercase;">Bourse Régionale des Valeurs Mobilières</p>
            <h1 style="margin:6px 0 0;font-size:20px;color:#fff;font-weight:700;">{label}</h1>
            <p style="margin:6px 0 0;font-size:13px;color:#c5d9f0;">{_today_str()} · {total} document(s)</p>
          </td>
        </tr>

        <!-- BODY -->
        <tr>
          <td style="padding:24px 28px;">
            {summary}
            {sections}
          </td>
        </tr>

        <!-- FOOTER -->
        <tr>
          <td style="background:{BRVM_LIGHT};padding:14px 28px;
                     font-size:11px;color:#666;text-align:center;border-top:1px solid #dde3ec;">
            Rapport généré automatiquement par l'Agent BRVM · {_today_str()}
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _build_text(subject: str, by_source: dict[str, list], type_rapport: str) -> str:
    label = TYPE_LABELS.get(type_rapport, type_rapport.capitalize())
    lines = [
        f"{label} BRVM — {_today_str()}",
        "=" * 60,
        "",
    ]

    for src in SOURCE_ORDER:
        docs = by_source.get(src, [])
        if not docs:
            continue
        lines.append(f"[ {src.upper()} — {len(docs)} document(s) ]")
        lines.append("-" * 50)
        for d in docs:
            societe = d.get("societe_confirmee") or d.get("societe", "—")
            titre = d.get("titre", "Sans titre")
            impact = (d.get("impact") or "neutre").capitalize()
            resume = d.get("resume", "")
            points = d.get("points_cles") or []
            url = d.get("doc_url") or d.get("url", "")
            lines.append(f"  Société  : {societe}")
            lines.append(f"  Titre    : {titre}")
            lines.append(f"  Impact   : {impact}")
            if resume:
                lines.append(f"  Résumé   : {resume}")
            if points:
                lines.append("  Points clés :")
                for p in points:
                    lines.append(f"    • {p}")
            if url:
                lines.append(f"  PDF      : {url}")
            lines.append("")
        lines.append("")

    # Summary
    lines.append("RÉCAPITULATIF")
    lines.append("-" * 30)
    total = 0
    for src in SOURCE_ORDER:
        docs = by_source.get(src, [])
        if not docs:
            continue
        pos = sum(1 for d in docs if (d.get("impact") or "").lower() == "positif")
        neg = sum(1 for d in docs if (d.get("impact") or "").lower() == "négatif")
        neu = len(docs) - pos - neg
        lines.append(f"  {src:<20} {len(docs):>3} docs  |  +{pos}  ={neu}  -{neg}")
        total += len(docs)
    lines.append(f"  {'TOTAL':<20} {total:>3} docs")
    lines.append("")
    lines.append(f"Généré automatiquement par l'Agent BRVM · {_today_str()}")
    return "\n".join(lines)


def generate(documents: list[dict], type_rapport: str, page_source: str | None = None) -> dict:
    """
    Génère un rapport email à partir d'une liste de documents analysés.

    Args:
        documents   : liste de dicts (colonnes de brvm_documents)
        type_rapport: "journalier", "hebdo" ou "mensuel"
        page_source : filtre optionnel sur page_source

    Returns:
        {subject, body_html, body_text}
    """
    # Filtre optionnel par source
    if page_source:
        documents = [d for d in documents if d.get("page_source") == page_source]

    subject = _build_subject(type_rapport, page_source)

    if not documents:
        label = TYPE_LABELS.get(type_rapport, type_rapport.capitalize())
        source_msg = f" pour « {page_source} »" if page_source else ""
        msg = f"Aucun nouveau document BRVM{source_msg} pour ce {type_rapport}."
        body_html = f"""<!DOCTYPE html><html lang="fr"><body
          style="font-family:Arial,sans-serif;padding:32px;color:#555;">
          <h2 style="color:{BRVM_BLUE};">{label} BRVM — {_today_str()}</h2>
          <p>{msg}</p>
        </body></html>"""
        return {"subject": subject, "body_html": body_html, "body_text": msg}

    # Regroupe par page_source
    by_source: dict[str, list] = defaultdict(list)
    for d in documents:
        src = d.get("page_source", "Autre")
        by_source[src].append(d)

    return {
        "subject": subject,
        "body_html": _build_html(subject, by_source, type_rapport),
        "body_text": _build_text(subject, by_source, type_rapport),
    }


if __name__ == "__main__":
    sample_docs = [
        {
            "societe_confirmee": "SONATEL SA",
            "titre": "Convocation AGO 2025",
            "resume": "SONATEL convoque ses actionnaires à l'AGO du 15 mai 2025.",
            "points_cles": ["Date : 15 mai 2025", "Lieu : Dakar", "Approbation des comptes 2024",
                            "Affectation du résultat", "Renouvellement des administrateurs"],
            "impact": "neutre",
            "page_source": "Convocations AG",
            "doc_url": "https://www.brvm.org/exemple1.pdf",
        },
        {
            "societe_confirmee": "ECOBANK CI",
            "titre": "Résultats financiers S1 2025",
            "resume": "ECOBANK CI annonce une hausse de 12% de son bénéfice net au premier semestre.",
            "points_cles": ["Bénéfice net +12%", "PNB en hausse", "Dividende maintenu",
                            "Croissance des dépôts", "Portefeuille crédits sain"],
            "impact": "positif",
            "page_source": "Communiqués",
            "doc_url": "https://www.brvm.org/exemple2.pdf",
        },
    ]
    report = generate(sample_docs, "journalier")
    print("Subject:", report["subject"])
    print("\n--- TEXT ---")
    print(report["body_text"])
    with open("preview_report.html", "w", encoding="utf-8") as f:
        f.write(report["body_html"])
    print("\nHTML sauvegardé dans preview_report.html")
