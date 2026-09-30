import asyncio
import json
import random
import aiohttp

AI_BASE_URL = "http://localhost:20128/v1/chat/completions"
DEFAULT_MODEL = "auto/best-free"

async def _call_ai_stream(messages, max_tokens=120, temperature=0.75, timeout_sec=5.0):
    """
    Call the local AI proxy at http://localhost:20128/v1 using the 100% free tier (auto/best-free).
    Strictly consumes zero paid tokens.
    """
    payload = {
        "model": DEFAULT_MODEL,
        "messages": messages,
        "stream": False,
        "max_tokens": max_tokens,
        "temperature": temperature
    }
    
    try:
        timeout = aiohttp.ClientTimeout(total=timeout_sec)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(AI_BASE_URL, json=payload) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                choices = data.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "")
                    return content.strip() if content else None
                return None
    except Exception as e:
        # Fallback gracefully on any timeout or connection error
        return None

async def generate_match_event_commentary(minute: int, event_type: str, player_name: str, team_name: str, opponent_name: str, score_str: str = ""):
    """
    Generate dynamic, electric 1-line commentary for a live match event using free local AI tokens.
    """
    prompt = (
        f"Minute: {minute}'\n"
        f"Score: {score_str}\n"
        f"Event: {event_type}\n"
        f"Key Player: {player_name}\n"
        f"Team: {team_name}\n"
        f"Opponent: {opponent_name}\n"
        f"Write exactly ONE dramatic, exciting football commentary sentence like Peter Drury / Martin Tyler. "
        f"Bold the player's name like **{player_name}**."
    )
    
    messages = [
        {"role": "system", "content": "You are a world-class, poetic, high-energy football commentator. Output exactly 1 punchy sentence. No introductory text."},
        {"role": "user", "content": prompt}
    ]
    
    res = await _call_ai_stream(messages, max_tokens=70, temperature=0.85, timeout_sec=4.0)
    return res

async def generate_post_match_analysis(home_name: str, away_name: str, score_a: int, score_b: int, motm_name: str, motm_rating: float, key_events: list = None):
    """
    Generate an AI Pundit post-match tactical review using free local AI tokens.
    """
    events_summary = ", ".join(key_events[:4]) if key_events else "Tactical battle across the pitch"
    winner = home_name if score_a > score_b else (away_name if score_b > score_a else "Draw")
    
    prompt = (
        f"Match Result: {home_name} {score_a} - {score_b} {away_name}\n"
        f"Winner: {winner}\n"
        f"Man of the Match: {motm_name} (Rating: {motm_rating})\n"
        f"Highlights: {events_summary}\n"
        f"Write a 2-sentence electric post-match pundit analysis summarizing the key moments and praising the standout performance of **{motm_name}**."
    )
    
    messages = [
        {"role": "system", "content": "You are an elite TV football analyst and pundit. Provide a crisp 2-sentence match summary. No greetings or headers."},
        {"role": "user", "content": prompt}
    ]
    
    res = await _call_ai_stream(messages, max_tokens=100, temperature=0.75, timeout_sec=4.5)
    return res
