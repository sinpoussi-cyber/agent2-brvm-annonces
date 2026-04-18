import base64
import json
import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic()

MODEL = "claude-sonnet-4-20250514"

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
URL        : {url}"""


def analyze(titre: str, pdf_bytes: bytes, url: str, page_source: str) -> dict | None:
    """
    Analyse un document BRVM en envoyant le PDF directement à Claude.

    Returns:
        {resume, points_cles, impact, categorie, societe_confirmee}  or  None on failure.
    """
    base64_data = base64.standard_b64encode(pdf_bytes).decode("utf-8")

    content = [
        {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": base64_data,
            },
        },
        {
            "type": "text",
            "text": USER_PROMPT.format(titre=titre, page_source=page_source, url=url),
        },
    ]

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
        )
    except anthropic.AuthenticationError:
        print("[claude_analyzer] Clé API invalide ou manquante.")
        return None
    except anthropic.RateLimitError:
        print("[claude_analyzer] Limite de taux atteinte. Réessayez plus tard.")
        return None
    except anthropic.APIStatusError as e:
        print(f"[claude_analyzer] Erreur API ({e.status_code}): {e.message}")
        return None
    except anthropic.APIConnectionError as e:
        print(f"[claude_analyzer] Erreur réseau: {e}")
        return None

    raw = next((b.text for b in response.content if b.type == "text"), "")

    cleaned = raw.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[cleaned.index("{"):]
    if cleaned.endswith("```"):
        cleaned = cleaned[:cleaned.rindex("}") + 1]
    cleaned = cleaned.strip()

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as e:
        print(f"[claude_analyzer] Réponse non-JSON ({e}): {raw[:200]}")
        return None

    impact = result.get("impact", "neutre").lower().strip()
    if impact not in ("positif", "neutre", "négatif"):
        impact = "neutre"
    result["impact"] = impact

    return {
        "resume": result.get("resume", ""),
        "points_cles": result.get("points_cles", []),
        "impact": impact,
        "categorie": result.get("categorie", ""),
        "societe_confirmee": result.get("societe_confirmee", ""),
    }
