"""
Orchestrateur d'analyse en cascade pour les documents BRVM.

Ordre de priorité :
  1. DeepSeek (deepseek_analyzer) — rapide et économique, texte extrait via pypdf.
  2. Claude / Anthropic (claude_analyzer) — secours, lit le PDF nativement
     (utile notamment pour les PDF scannés que DeepSeek ne peut pas traiter).

`main.py` importe uniquement `analyze` depuis ce module : la logique de
bascule est entièrement encapsulée ici.
"""

import deepseek_analyzer
import claude_analyzer


def analyze(titre: str, pdf_bytes: bytes, url: str, page_source: str) -> dict | None:
    """
    Analyse un document en essayant DeepSeek d'abord, puis Claude en secours.

    Returns:
        Le dict d'analyse {resume, points_cles, impact, categorie,
        societe_confirmee} du premier fournisseur qui réussit, ou None si les
        deux échouent (le document sera réessayé au prochain run).
    """
    # --- 1) DeepSeek en priorité --------------------------------------------
    try:
        result = deepseek_analyzer.analyze(
            titre=titre, pdf_bytes=pdf_bytes, url=url, page_source=page_source
        )
    except deepseek_analyzer.DeepSeekFatalError as e:
        # Clé invalide ou solde épuisé : on ne stoppe pas le run, on bascule.
        print(f"[analyzer] DeepSeek indisponible ({e}) — bascule vers Claude")
        result = None
    except Exception as e:  # garde-fou : toute autre erreur DeepSeek → secours
        print(f"[analyzer] Erreur DeepSeek inattendue ({e}) — bascule vers Claude")
        result = None

    if result is not None:
        print("[analyzer] Analyse fournie par DeepSeek")
        return result

    # --- 2) Claude / Anthropic en secours -----------------------------------
    print("[analyzer] Tentative de secours via Claude...")
    try:
        result = claude_analyzer.analyze(
            titre=titre, pdf_bytes=pdf_bytes, url=url, page_source=page_source
        )
    except Exception as e:  # claude_analyzer gère déjà ses erreurs, ceinture+bretelles
        print(f"[analyzer] Erreur Claude inattendue ({e})")
        return None

    if result is not None:
        print("[analyzer] Analyse fournie par Claude (secours)")
    else:
        print("[analyzer] Échec des deux fournisseurs — document ignoré")
    return result
