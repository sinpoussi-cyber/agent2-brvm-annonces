import io
import json
import os
import time

import requests
from pypdf import PdfReader
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration DeepSeek (API compatible OpenAI)
# ---------------------------------------------------------------------------
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
# Anciens alias (deepseek-chat / deepseek-reasoner) retirés le 24/07/2026.
# Modèles actuels : deepseek-v4-flash (rapide) et deepseek-v4-pro (raisonnement).
MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")
MAX_TEXT_CHARS = 60_000   # borne le texte envoyé (les PDF BRVM sont courts)
REQUEST_TIMEOUT = 120


class DeepSeekFatalError(RuntimeError):
    """Erreur non récupérable (clé invalide, solde épuisé) : doit stopper le run."""


SYSTEM_PROMPT = """Tu es un analyste financier expert de la Bourse Régionale des Valeurs Mobilières (BRVM)
d'Afrique de l'Ouest. Tu analyses des documents officiels d'entreprises cotées et retournes
UNIQUEMENT un objet JSON valide, sans texte avant ni après."""

USER_PROMPT = """Analyse ce document officiel de la BRVM et retourne UNIQUEMENT un objet JSON avec exactement ces 5 champs :

{{
  "resume": "Résumé du document en 3 phrases maximum.",
  "points_cles": ["point 1", "point 2", "point 3", "point 4", "point 5"],
  "impact": "positif" | "neutre" | "négatif",
  "categorie": "Type de document parmi : convocation AG, résultats financiers, nomination, émission obligataire, dividende, communiqué divers, avis de marché, autre",
  "societe_confirmee": "Nom exact de la société tel qu'il apparaît dans le contenu"
}}

Règles strictes :
- "impact" doit être exactement l'une de ces valeurs : "positif", "neutre", "négatif"
- "points_cles" doit contenir exactement 5 éléments
- Retourne UNIQUEMENT le JSON, aucun autre texte

Métadonnées :
Titre      : {titre}
Source     : {page_source}
URL        : {url}

Contenu du document :
\"\"\"
{contenu}
\"\"\""""


def _extract_text(pdf_bytes: bytes) -> str:
    """Extrait le texte d'un PDF en mémoire via pypdf. Retourne '' si illisible."""
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        parts = [(page.extract_text() or "") for page in reader.pages]
    except Exception as e:  # PDF corrompu, chiffré, etc.
        print(f"[deepseek_analyzer] Extraction texte échouée: {e}")
        return ""
    return "\n".join(parts).strip()[:MAX_TEXT_CHARS]


def analyze(titre: str, pdf_bytes: bytes, url: str, page_source: str) -> dict | None:
    """
    Analyse un document BRVM via DeepSeek.

    Le PDF est converti en texte localement (pypdf) puis envoyé à DeepSeek,
    qui ne lit pas les PDF nativement (contrairement à Claude).

    Returns:
        {resume, points_cles, impact, categorie, societe_confirmee}
        ou None sur échec récupérable (doc réessayable au prochain run).

    Raises:
        DeepSeekFatalError sur clé invalide (401) ou solde épuisé (402) :
        le run doit s'arrêter, inutile de mitrailler les documents suivants.
    """
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise DeepSeekFatalError("DEEPSEEK_API_KEY manquante dans l'environnement.")

    contenu = _extract_text(pdf_bytes)
    if not contenu:
        print("[deepseek_analyzer] Aucun texte exploitable (PDF scanné/image ?) — ignoré")
        return None

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": USER_PROMPT.format(
                    titre=titre, page_source=page_source, url=url, contenu=contenu
                ),
            },
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": 1024,
        "temperature": 0,
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    time.sleep(3)  # politesse / limitation de débit
    try:
        r = requests.post(
            DEEPSEEK_API_URL, headers=headers, json=payload, timeout=REQUEST_TIMEOUT
        )
    except requests.RequestException as e:
        print(f"[deepseek_analyzer] Erreur réseau: {e}")
        return None

    # --- Gestion des statuts ------------------------------------------------
    if r.status_code in (401, 402):
        # 401 = clé invalide ; 402 = solde insuffisant. Non récupérable.
        raise DeepSeekFatalError(
            f"Erreur fatale DeepSeek ({r.status_code}): {r.text[:200]}"
        )
    if r.status_code == 429:
        print("[deepseek_analyzer] Limite de débit atteinte (429) — ignoré")
        return None
    if r.status_code >= 400:
        print(f"[deepseek_analyzer] Erreur API ({r.status_code}): {r.text[:200]}")
        return None

    # --- Extraction du contenu texte (le raisonnement éventuel est dans
    #     reasoning_content, qu'on ignore volontairement) ---------------------
    try:
        data = r.json()
        raw = data["choices"][0]["message"]["content"] or ""
    except (ValueError, KeyError, IndexError) as e:
        print(f"[deepseek_analyzer] Réponse inattendue: {e}")
        return None

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned[cleaned.index("{"):]
    if cleaned.endswith("```"):
        cleaned = cleaned[:cleaned.rindex("}") + 1]
    cleaned = cleaned.strip()

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as e:
        print(f"[deepseek_analyzer] Réponse non-JSON ({e}): {raw[:200]}")
        return None

    impact = str(result.get("impact", "neutre")).lower().strip()
    if impact not in ("positif", "neutre", "négatif"):
        impact = "neutre"

    return {
        "resume": result.get("resume", ""),
        "points_cles": result.get("points_cles", []),
        "impact": impact,
        "categorie": result.get("categorie", ""),
        "societe_confirmee": result.get("societe_confirmee", ""),
    }
