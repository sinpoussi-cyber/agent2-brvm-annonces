import os
from datetime import datetime, timezone, timedelta
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

TABLE = "brvm_documents"

_client: Client | None = None


def _get_client() -> Client:
    global _client
    if _client is None:
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_KEY", "")
        if not url or not key:
            raise EnvironmentError("SUPABASE_URL et SUPABASE_KEY doivent être définis dans .env")
        _client = create_client(url, key)
    return _client


# ---------------------------------------------------------------------------
# doc_exists
# ---------------------------------------------------------------------------

def doc_exists(url: str) -> bool:
    """
    Retourne True si un document avec cette doc_url existe déjà dans brvm_documents.
    Utilise la contrainte UNIQUE sur doc_url pour une vérification fiable.
    """
    try:
        result = (
            _get_client()
            .table(TABLE)
            .select("id")
            .eq("doc_url", url)
            .limit(1)
            .execute()
        )
        return len(result.data) > 0
    except Exception as e:
        print(f"[supabase_client] doc_exists error: {e}")
        return False


# ---------------------------------------------------------------------------
# insert_document
# ---------------------------------------------------------------------------

def insert_document(data: dict) -> dict | None:
    """
    Insère un document dans brvm_documents.
    data doit contenir au minimum : doc_url, titre, societe, page_source.
    Retourne la ligne insérée ou None si échec.
    """
    try:
        result = (
            _get_client()
            .table(TABLE)
            .insert(data)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"[supabase_client] insert_document error: {e}")
        return None


# ---------------------------------------------------------------------------
# Helpers de fenêtre temporelle
# ---------------------------------------------------------------------------

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


# ---------------------------------------------------------------------------
# get_documents_today
# ---------------------------------------------------------------------------

def get_documents_today() -> list[dict]:
    """Récupère les documents dont created_at est dans la journée courante (UTC)."""
    now = _now_utc()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    try:
        result = (
            _get_client()
            .table(TABLE)
            .select("*")
            .gte("created_at", _iso(start))
            .lt("created_at", _iso(end))
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []
    except Exception as e:
        print(f"[supabase_client] get_documents_today error: {e}")
        return []


# ---------------------------------------------------------------------------
# get_documents_week
# ---------------------------------------------------------------------------

def get_documents_week() -> list[dict]:
    """Récupère les documents des 7 derniers jours (UTC)."""
    end = _now_utc()
    start = end - timedelta(days=7)
    try:
        result = (
            _get_client()
            .table(TABLE)
            .select("*")
            .gte("created_at", _iso(start))
            .lte("created_at", _iso(end))
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []
    except Exception as e:
        print(f"[supabase_client] get_documents_week error: {e}")
        return []


# ---------------------------------------------------------------------------
# get_documents_month
# ---------------------------------------------------------------------------

def get_documents_month() -> list[dict]:
    """Récupère les documents du mois calendaire en cours (UTC)."""
    now = _now_utc()
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # Premier jour du mois suivant
    if now.month == 12:
        end = now.replace(year=now.year + 1, month=1, day=1,
                          hour=0, minute=0, second=0, microsecond=0)
    else:
        end = now.replace(month=now.month + 1, day=1,
                          hour=0, minute=0, second=0, microsecond=0)
    try:
        result = (
            _get_client()
            .table(TABLE)
            .select("*")
            .gte("created_at", _iso(start))
            .lt("created_at", _iso(end))
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []
    except Exception as e:
        print(f"[supabase_client] get_documents_month error: {e}")
        return []


# ---------------------------------------------------------------------------
# mark_sent
# ---------------------------------------------------------------------------

def mark_sent(ids: list[int | str]) -> bool:
    """
    Met envoye_email=True pour les documents dont l'id est dans la liste.
    Retourne True si la mise à jour a réussi.
    """
    if not ids:
        return True
    try:
        _get_client().table(TABLE).update({"envoye_email": True}).in_("id", ids).execute()
        return True
    except Exception as e:
        print(f"[supabase_client] mark_sent error: {e}")
        return False


# ---------------------------------------------------------------------------
# Test rapide
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Connexion Supabase...")
    today = get_documents_today()
    print(f"Documents aujourd'hui : {len(today)}")
    week = get_documents_week()
    print(f"Documents 7 derniers jours : {len(week)}")
    month = get_documents_month()
    print(f"Documents ce mois : {len(month)}")

    test_url = "https://example.com/test.pdf"
    print(f"doc_exists('{test_url}') : {doc_exists(test_url)}")
