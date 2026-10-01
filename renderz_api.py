import base64
import json
import zlib
try:
    from curl_cffi import requests
except ImportError:
    import requests

def search_fifarenderz(search_name="Messi", size=10, from_offset=0):
    """
    Queries the internal RenderZ Elasticsearch API.
    """
    query = {
        "query": {
            "bool": {
                "must": [{
                    "query_string": {
                        "fields": [
                            "cardName",
                            "commonName",
                            "firstName",
                            "lastName",
                        ],
                        "query": f"*{search_name}*",
                    }
                }],
                "should": [],
                "must_not": [],
            }
        },
        "sort": [{"rating": {"order": "desc"}}, {"assetId": {"order": "desc"}}],
        "_source": [],
        "from": from_offset,
        "size": size,
    }

    # Compress using zlib DEFLATE with wbits=-15
    raw_bytes = json.dumps(query, separators=(",", ":")).encode("utf-8")
    compressor = zlib.compressobj(level=9, method=zlib.DEFLATED, wbits=-15)
    compressed = compressor.compress(raw_bytes) + compressor.flush()
    
    # Base64url encode and strip trailing '='
    encoded_q = base64.urlsafe_b64encode(compressed).decode("utf-8").rstrip("=")

    url = f"https://renderz.app/api/search/23?v=1&q={encoded_q}"
    
    headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://renderz.app/players",
        "Accept": "application/json",
    }
    
    try:
        if "curl_cffi" in str(requests):
            resp = requests.get(url, headers=headers, timeout=15, impersonate="chrome124")
        else:
            resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("players", [])
    except Exception as e:
        print(f"Error fetching data: {e}")
        return []

def query_players_by_program(program_code: str, size: int = 24, from_offset: int = 0, min_rating: int = None, max_rating: int = None):
    size = min(max(1, size), 48)
    must_clauses = []
    if program_code:
        must_clauses.append({"match": {"source": program_code}})
    else:
        must_clauses.append({"match_all": {}})
        
    if min_rating or max_rating:
        rating_range = {}
        if min_rating: rating_range["gte"] = min_rating
        if max_rating: rating_range["lte"] = max_rating
        must_clauses.append({"range": {"rating": rating_range}})

    query_payload = {
        "query": {
            "bool": {
                "must": must_clauses,
                "should": [],
                "must_not": []
            }
        },
        "sort": [
            {"rating": {"order": "desc"}},
            {"assetId": {"order": "desc"}}
        ],
        "_source": [],
        "from": from_offset,
        "size": size
    }

    raw_bytes = json.dumps(query_payload, separators=(",", ":")).encode("utf-8")
    compressor = zlib.compressobj(level=9, method=zlib.DEFLATED, wbits=-15)
    compressed = compressor.compress(raw_bytes) + compressor.flush()
    encoded_q = base64.urlsafe_b64encode(compressed).decode("utf-8").rstrip("=")

    url = f"https://renderz.app/api/search/23?v=1&q={encoded_q}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://renderz.app/players",
        "Accept": "application/json"
    }

    for attempt in range(3):
        try:
            if "curl_cffi" in str(requests):
                resp = requests.get(url, headers=headers, timeout=15, impersonate="chrome124")
            else:
                resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code in (502, 503, 504):
                import time
                time.sleep(0.5 * (attempt + 1))
                continue
            resp.raise_for_status()
            data = resp.json()
            return data.get("players", [])
        except Exception as e:
            if attempt == 2:
                print(f"Error fetching data: {e}")
            import time
            time.sleep(0.5 * (attempt + 1))
    return []

if __name__ == "__main__":
    players = query_players_by_program("", min_rating=100, max_rating=150, size=1)
    if players:
        print(f"Found player: {players[0].get('cardName')} (OVR {players[0].get('rating')})")
        with open("test_player.json", "w") as f:
            json.dump(players[0], f, indent=2)
            print("Saved player data to test_player.json")
    else:
        print("No players found.")


def query_players_by_program_wildcard(program_query: str, size: int = 100, min_rating: int = None, max_rating: int = None):
    import json, zlib, base64, requests
    
    must_clauses = []
    if program_query:
        must_clauses.append({
            "wildcard": {
                "source": {
                    "value": f"*{program_query}*"
                }
            }
        })
    else:
        must_clauses.append({"match_all": {}})
        
    if min_rating or max_rating:
        rating_range = {}
        if min_rating: rating_range["gte"] = min_rating
        if max_rating: rating_range["lte"] = max_rating
        must_clauses.append({"range": {"rating": rating_range}})

    query_payload = {
        "query": {
            "bool": {
                "must": must_clauses
            }
        },
        "sort": [
            {"rating": {"order": "desc"}},
            {"assetId": {"order": "desc"}}
        ],
        "_source": [],
        "size": size
    }

    raw_bytes = json.dumps(query_payload, separators=(",", ":")).encode("utf-8")
    compressor = zlib.compressobj(level=9, method=zlib.DEFLATED, wbits=-15)
    compressed = compressor.compress(raw_bytes) + compressor.flush()
    encoded_q = base64.urlsafe_b64encode(compressed).decode("utf-8").rstrip("=")

    url = f"https://renderz.app/api/search/23?v=1&q={encoded_q}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://renderz.app/players",
        "Accept": "application/json"
    }

    try:
        if "curl_cffi" in str(requests):
            resp = requests.get(url, headers=headers, timeout=15, impersonate="chrome124")
        else:
            resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json().get("players", [])
    except Exception as e:
        print(f"Error: {e}")
        return []

_RATING_CACHE = {}
_CACHE_EXPIRY = 0

def fetch_all_players_by_rating(rating: int, force_refresh: bool = False) -> list:
    """
    Fetches ALL players in existence for a specific OVR rating with automatic pagination.
    Caches results in memory for rapid, zero-lag random sampling across drafts and exchanges.
    """
    import time
    global _RATING_CACHE, _CACHE_EXPIRY
    now = time.time()
    
    if not force_refresh and rating in _RATING_CACHE and now < _CACHE_EXPIRY:
        return _RATING_CACHE[rating]
        
    all_cards = []
    offset = 0
    seen_ids = set()
    while True:
        batch = query_players_by_program("", size=50, from_offset=offset, min_rating=rating, max_rating=rating)
        if not batch:
            break
        for p in batch:
            p_id = p.get('assetId') or p.get('id')
            if p_id and p_id not in seen_ids:
                seen_ids.add(p_id)
                all_cards.append(p)
            elif not p_id:
                all_cards.append(p)
        offset += len(batch)
        if len(batch) < 50:
            break
            
    _RATING_CACHE[rating] = all_cards
    _CACHE_EXPIRY = now + 7200  # 2-hour cache
    return all_cards

