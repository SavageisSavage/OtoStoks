"""
core/steam_news.py - Screen Stocks Official Steam News & Patch Notes Interface.
Polls Steam Web API (App ID 4356780) for real-time game announcements and developer notes.
"""
import time
import json
import re
import urllib.request
import threading
from datetime import datetime
from typing import List, Dict, Any

APP_ID = 4356780
STEAM_NEWS_URL = f"https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid={APP_ID}&count=15"

_cached_news: List[Dict[str, Any]] = []
_last_fetch_time: float = 0.0


def clean_bbcode(text: str) -> str:
    """Strips and converts basic Steam BBCode tags to clean readable HTML/text."""
    if not text:
        return ""
    # Remove images
    t = re.sub(r'\{STEAM_CLAN_IMAGE\}[^\s]+', '', text)
    # Convert [b] to bold
    t = re.sub(r'\[b\](.*?)\[/b\]', r'<strong>\1</strong>', t, flags=re.IGNORECASE)
    # Convert [i] to italics
    t = re.sub(r'\[i\](.*?)\[/i\]', r'<em>\1</em>', t, flags=re.IGNORECASE)
    # Convert [url=...]...[/url] to links
    t = re.sub(r'\[url=(.*?)\](.*?)\[/url\]', r'<a href="\1" target="_blank" class="news-link">\2</a>', t, flags=re.IGNORECASE)
    # Convert [list] and [*]
    t = re.sub(r'\[list\]', '<ul>', t, flags=re.IGNORECASE)
    t = re.sub(r'\[/list\]', '</ul>', t, flags=re.IGNORECASE)
    t = re.sub(r'\[\*\](.*?)(\n|$)', r'<li>\1</li>', t, flags=re.IGNORECASE)
    # Strip remaining unknown tags
    t = re.sub(r'\[/?[a-zA-Z0-9_]+(=[^\]]+)?\]', '', t)
    # Collapse excess newlines
    t = re.sub(r'\n{3,}', '\n\n', t)
    return t.strip()


def fetch_steam_news(count: int = 10, timeout: float = 6.0) -> List[Dict[str, Any]]:
    """Fetches Screen Stocks announcements from Steam Web API."""
    global _cached_news, _last_fetch_time
    now = time.time()
    if _cached_news and (now - _last_fetch_time) < 300.0:
        return _cached_news

    try:
        req = urllib.request.Request(
            f"https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid={APP_ID}&count={count}",
            headers={"User-Agent": "OtoStoksBot/5.0 ScreenStocksAnalyst"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_items = data.get("appnews", {}).get("newsitems", [])
            news = []
            for item in raw_items:
                raw_contents = item.get("contents", "")
                summary = clean_bbcode(raw_contents)
                ts = item.get("date", 0)
                try:
                    date_str = datetime.fromtimestamp(ts).strftime("%b %d, %Y - %H:%M") if ts > 0 else "Recent"
                except Exception:
                    date_str = "Recent"

                news.append({
                    "gid": item.get("gid", ""),
                    "title": item.get("title", "Game Update"),
                    "url": item.get("url", f"https://store.steampowered.com/news/app/{APP_ID}"),
                    "author": item.get("author", "Developer"),
                    "date": date_str,
                    "timestamp": ts,
                    "feedlabel": item.get("feedlabel", "Community Announcements"),
                    "summary": summary
                })

            if news:
                _cached_news = news
                _last_fetch_time = now
                return news
    except Exception as e:
        # If fetch fails, return cached if available or fallback
        if _cached_news:
            return _cached_news

    return [
        {
            "gid": "local-fallback",
            "title": "Screen Stocks v1.0.4 - Live Event Engine Active",
            "url": f"https://store.steampowered.com/news/app/{APP_ID}",
            "author": "Conradical Games",
            "date": datetime.now().strftime("%b %d, %Y"),
            "timestamp": int(time.time()),
            "feedlabel": "Official News",
            "summary": "Screen Stocks live market updates and official community announcements. Connect your bridge to stream real-time price feeds."
        }
    ]


def start_steam_news_poller(state, interval: float = 900.0):
    """Starts background daemon to keep Steam News updated in AppState."""
    def _worker():
        while state.running:
            try:
                items = fetch_steam_news(count=15)
                with state.lock:
                    state.steam_news = items
            except Exception:
                pass
            time.sleep(interval)

    t = threading.Thread(target=_worker, daemon=True, name="SteamNewsPoller")
    t.start()
    return t
