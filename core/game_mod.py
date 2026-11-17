"""
core/game_mod.py - Native Screen Stocks Mod Interface.
Provides zero-dependency connection to Screen Stocks via its official mod system:
- Discovers game directory across Windows, macOS, and Linux (Steam Proton / Steam Deck).
- Automatically verifies and activates official 'modSupport' and mod-settings.
- Reads real-time market snapshots, player positions, scheduled resets, and news from mods/export/market.json.
- Dispatches buy, sell, short, cover, and close orders via mods/commands.
"""
import os
import sys
import json
import time
import re
import shutil
from typing import Dict, Any, List, Optional, Tuple

APP_ID = 4356780
SAV_NAME = "thesmallshort_online_settings.sav"


def find_game_dir() -> Optional[str]:
    """Discovers Screen Stocks directory on Windows, macOS, or Linux/Proton."""
    home = os.path.expanduser("~")
    candidates = []

    userprofile = os.environ.get("USERPROFILE")
    if userprofile:
        candidates.append(os.path.join(userprofile, "AppData", "LocalLow", "Conradical Games", "Screen Stocks"))
    candidates.append(os.path.join(home, "AppData", "LocalLow", "Conradical Games", "Screen Stocks"))
    candidates.append(os.path.join(home, "Library", "Application Support", "Conradical Games", "Screen Stocks"))

    proton_tail = os.path.join(
        "steamapps", "compatdata", str(APP_ID), "pfx", "drive_c",
        "users", "steamuser", "AppData", "LocalLow", "Conradical Games", "Screen Stocks"
    )
    for steam_rel in [".local/share/Steam", ".steam/steam", ".var/app/com.valvesoftware.Steam/.local/share/Steam"]:
        candidates.append(os.path.join(home, steam_rel, proton_tail))

    for c in candidates:
        if os.path.exists(c):
            return os.path.abspath(c)
    return None


def get_game_paths(game_dir: Optional[str] = None) -> Dict[str, str]:
    """Returns mapped paths for game save, mods, market export, and commands."""
    gdir = game_dir or find_game_dir() or ""
    mods_dir = os.path.join(gdir, "mods") if gdir else ""
    return {
        "game_dir": gdir,
        "sav": os.path.join(gdir, SAV_NAME) if gdir else "",
        "mods": mods_dir,
        "mod_settings": os.path.join(mods_dir, "mod-settings.json") if mods_dir else "",
        "market": os.path.join(mods_dir, "export", "market.json") if mods_dir else "",
        "history": os.path.join(mods_dir, "export", "history.json") if mods_dir else "",
        "commands": os.path.join(mods_dir, "commands") if mods_dir else "",
        "skins": os.path.join(mods_dir, "skins") if mods_dir else ""
    }


def ensure_native_mod_support(game_dir: Optional[str] = None) -> Tuple[bool, str]:
    """
    Checks the game save file and enables 'modSupport': true and exports in mod-settings.json.
    Safe and non-destructive: creates a timestamped .bak backup before modifying.
    """
    paths = get_game_paths(game_dir)
    sav_path = paths["sav"]
    if not sav_path or not os.path.exists(sav_path):
        return False, "Screen Stocks save file not found. Open game once to generate save file."

    # 1. Verify / Enable modSupport in thesmallshort_online_settings.sav
    try:
        with open(sav_path, "r", encoding="utf-8-sig", errors="ignore") as f:
            content = f.read()

        if r'"modSupport"\s*:\s*"?true"?' not in content and '"modSupport": true' not in content and '"modSupport" : true' not in content:
            # Create backup
            bak_path = sav_path + f".bak"
            shutil.copy2(sav_path, bak_path)

            if '"modSupport"' in content:
                new_content = re.sub(r'("modSupport"\s*:\s*)(")?false(")?', r'\g<1>true', content)
            else:
                # Insert modSupport inside value dict
                new_content = re.sub(r'("value"\s*:\s*\{)', r'\g<1>\n\t\t\t"modSupport" : true,', content)

            with open(sav_path, "w", encoding="utf-8") as f:
                f.write(new_content)

        # 2. Ensure mods directory and mod-settings.json
        mods_dir = paths["mods"]
        os.makedirs(mods_dir, exist_ok=True)
        os.makedirs(os.path.join(mods_dir, "export"), exist_ok=True)
        os.makedirs(os.path.join(mods_dir, "commands"), exist_ok=True)

        mod_settings_path = paths["mod_settings"]
        settings_payload = {"export": True, "commands": True, "skins": True}
        if os.path.exists(mod_settings_path):
            try:
                with open(mod_settings_path, "r", encoding="utf-8") as f:
                    cur = json.load(f)
                if not cur.get("export") or not cur.get("commands"):
                    cur["export"] = True
                    cur["commands"] = True
                    with open(mod_settings_path, "w", encoding="utf-8") as f:
                        json.dump(cur, f, indent=2)
            except Exception:
                with open(mod_settings_path, "w", encoding="utf-8") as f:
                    json.dump(settings_payload, f, indent=2)
        else:
            with open(mod_settings_path, "w", encoding="utf-8") as f:
                json.dump(settings_payload, f, indent=2)

        return True, "Native Screen Stocks mod support configured and verified."
    except Exception as e:
        return False, f"Failed to configure native mod settings: {e}"


def read_native_market_file(game_dir: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Reads and parses mods/export/market.json written by Screen Stocks.
    Returns normalized market snapshot matching OtoStoksBot schema.
    """
    paths = get_game_paths(game_dir)
    mfile = paths["market"]
    if not mfile or not os.path.exists(mfile):
        return None

    try:
        # Check mtime to avoid reading partially written files
        mtime = os.path.getmtime(mfile)
        if time.time() - mtime > 15.0:
            # File is stale (game paused or closed)
            pass

        with open(mfile, "r", encoding="utf-8", errors="ignore") as f:
            data = json.load(f)

        if not data or not data.get("marketReady", True):
            return None

        # Transform to unified snapshot dictionary
        stocks_dict = {}
        for s in data.get("stocks", []):
            sid = str(s.get("stockId", "")).strip()
            if not sid:
                continue
            stocks_dict[sid] = {
                "ticker": sid,
                "name": s.get("name", sid),
                "price": float(s.get("price", 0.0)),
                "basePrice": float(s.get("basePrice", 0.0)),
                "priceCap": float(s.get("priceCap", 0.0)),
                "dividendRate": float(s.get("dividendRate", 0.0)),
                "availableShares": float(s.get("availableShares", 0.0)),
                "maxVolume": float(s.get("maxVolume", 0.0)),
                "unlocked": s.get("unlocked", True),
                "holding": {
                    "sharesOwnedDouble": 0.0,
                    "sharesShortedDouble": 0.0,
                    "averageBuyPrice": 0.0,
                    "averageShortPrice": 0.0
                }
            }

        player_data = data.get("player", {})
        cash_val = float(player_data.get("cash", 0.0))
        net_worth_val = float(player_data.get("netWorth", 0.0))

        # Map positions into stocks_dict
        for pos in player_data.get("positions", []):
            sid = str(pos.get("stockId", "")).strip()
            if sid in stocks_dict:
                stocks_dict[sid]["holding"] = {
                    "sharesOwnedDouble": float(pos.get("sharesOwned", 0.0)),
                    "sharesShortedDouble": float(pos.get("sharesShorted", 0.0)),
                    "averageBuyPrice": float(pos.get("averageBuyPrice", 0.0)),
                    "averageShortPrice": float(pos.get("averageShortPrice", 0.0))
                }

        # Calculate accurate net worth if not provided
        if net_worth_val <= 0:
            net_worth_val = cash_val
            for sid, s in stocks_dict.items():
                h = s["holding"]
                px = s["price"]
                net_worth_val += h["sharesOwnedDouble"] * px
                if h["sharesShortedDouble"] > 0:
                    avg_short = h["averageShortPrice"] if h["averageShortPrice"] > 0 else px
                    net_worth_val += h["sharesShortedDouble"] * (2 * avg_short - px)

        snapshot = {
            "marketReady": True,
            "source": "native_mod",
            "serverTick": int(data.get("sequence", 0)),
            "serverTimeMs": float(data.get("serverTimeMs", time.time() * 1000)),
            "writtenAtMs": float(data.get("writtenAtMs", time.time() * 1000)),
            "player": {
                "cashDouble": cash_val,
                "netWorthDouble": net_worth_val,
                "totalUnrealizedPnL": float(player_data.get("totalUnrealizedPnL", 0.0)),
                "level": int(player_data.get("level", 1)),
                "ipoCount": int(player_data.get("ipoCount", 0)),
                "unlockedAchievementCount": int(player_data.get("unlockedAchievementCount", 0)),
                "buyCooldownSeconds": float(player_data.get("buyCooldownSeconds", 0.0)),
                "shortCooldownSeconds": float(player_data.get("shortCooldownSeconds", 0.0)),
                "nextBuyAtMs": float(player_data.get("nextBuyAtMs", 0.0)),
                "nextShortAtMs": float(player_data.get("nextShortAtMs", 0.0))
            },
            "stocks": stocks_dict,
            "unlockedStocks": [sid for sid, s in stocks_dict.items() if s.get("unlocked", True)],
            "scheduledNews": data.get("scheduledNews", []),
            "marketNews": data.get("marketNews", []),
            "commandResults": data.get("commandResults", [])
        }
        return snapshot
    except Exception:
        return None


def dispatch_native_order(ticker: str, action: str, amount_or_pct: Any, is_max: bool = True, game_dir: Optional[str] = None) -> Tuple[bool, str]:
    """
    Dispatches order via Screen Stocks official mods/commands/<stockId>/ directory:
    - Writes buymax.json / buypercent.json, sellmax.json / sellpercent.json, etc.
    - Format: {"execute": true} or {"execute": true, "percent": 50}
    """
    paths = get_game_paths(game_dir)
    cmds_dir = paths["commands"]
    if not cmds_dir or not os.path.exists(cmds_dir):
        return False, "Mods commands directory does not exist. Ensure Screen Stocks is open with mod support."

    stock_dir = os.path.join(cmds_dir, ticker)
    os.makedirs(stock_dir, exist_ok=True)

    act = action.lower()
    if act not in ("buy", "sell", "short", "cover", "close"):
        return False, f"Unknown trade action: {action}"

    filename = f"{act}max.json" if is_max else f"{act}percent.json"
    filepath = os.path.join(stock_dir, filename)

    try:
        # Check if already executing
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    cur = json.load(f)
                if cur.get("execute") is True:
                    return False, f"Previous {action} order for {ticker} is still pending game pickup."
            except Exception:
                pass

        payload: Dict[str, Any] = {"execute": True}
        if not is_max:
            try:
                pct = int(amount_or_pct) if str(amount_or_pct).isdigit() else 25
                payload["percent"] = max(1, min(100, pct))
            except Exception:
                payload["percent"] = 25

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        return True, f"Native mod order {action.upper()} dispatched to {filepath}"
    except Exception as e:
        return False, f"Failed writing native mod order: {e}"


def read_in_game_settings(game_dir: Optional[str] = None) -> Dict[str, Any]:
    """Reads SettingsData.value directly from Screen Stocks thesmallshort_online_settings.sav."""
    paths = get_game_paths(game_dir)
    sav_path = paths["sav"]
    if not sav_path or not os.path.exists(sav_path):
        return {}
    try:
        with open(sav_path, "r", encoding="utf-8-sig", errors="ignore") as f:
            data = json.load(f)
        return data.get("SettingsData", {}).get("value", {})
    except Exception:
        return {}


def save_in_game_settings(patch: Dict[str, Any], game_dir: Optional[str] = None) -> Tuple[bool, str]:
    """Updates SettingsData.value in thesmallshort_online_settings.sav directly, creating a backup."""
    paths = get_game_paths(game_dir)
    sav_path = paths["sav"]
    if not sav_path or not os.path.exists(sav_path):
        return False, "Save file not found."
    try:
        with open(sav_path, "r", encoding="utf-8-sig", errors="ignore") as f:
            data = json.load(f)

        if "SettingsData" not in data or "value" not in data["SettingsData"]:
            return False, "Invalid save file structure."

        val = data["SettingsData"]["value"]
        # Backup before writing
        shutil.copy2(sav_path, sav_path + ".bak")

        # Apply allowed in-game settings patch
        allowed_keys = [
            "sfxVolume", "musicVolume", "audioMuted", "screenShake",
            "windowSize", "alwaysOnTop", "scientificNotation", "advancedMode",
            "fullscreen", "pauseOnMenus", "equippedBGSkinId", "frameRateIndex",
            "unfocusedWindowOpacityPercent", "modSupport"
        ]
        for k, v in patch.items():
            if k in allowed_keys:
                val[k] = v

        with open(sav_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

        return True, "In-game settings updated successfully."
    except Exception as e:
        return False, f"Failed updating in-game settings: {e}"


def list_skins(game_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lists all skins installed in Screen Stocks mods/skins/ directory."""
    paths = get_game_paths(game_dir)
    skins_dir = paths["skins"]
    if not skins_dir or not os.path.exists(skins_dir):
        return []

    settings = read_in_game_settings(game_dir)
    equipped_id = settings.get("equippedBGSkinId", "")

    skins_list = []
    # Add default game skin entry
    skins_list.append({
        "id": "GR3Y-OS",
        "name": "GR3Y-OS (Default Theme)",
        "equipped": (equipped_id == "GR3Y-OS" or not equipped_id),
        "file": "",
        "is_custom": False
    })

    try:
        for fname in sorted(os.listdir(skins_dir)):
            if fname.endswith(".json"):
                jpath = os.path.join(skins_dir, fname)
                try:
                    with open(jpath, "r", encoding="utf-8", errors="ignore") as f:
                        meta = json.load(f)
                    skin_id = fname[:-5]
                    d_name = meta.get("displayName") or skin_id
                    bg_img = meta.get("backgroundImage") or meta.get("skinImage") or ""
                    skins_list.append({
                        "id": skin_id,
                        "name": d_name,
                        "equipped": (equipped_id == skin_id or equipped_id == d_name),
                        "file": bg_img,
                        "is_custom": True,
                        "meta": meta
                    })
                except Exception:
                    pass
    except Exception:
        pass
    return skins_list


def install_skin(name: str, file_bytes: bytes, file_ext: str, meta: Optional[Dict[str, Any]] = None, game_dir: Optional[str] = None) -> Tuple[bool, str]:
    """Installs a PNG or JPG background skin and writes metadata json into mods/skins/."""
    paths = get_game_paths(game_dir)
    skins_dir = paths["skins"]
    if not skins_dir:
        return False, "Skins directory not available."

    try:
        os.makedirs(skins_dir, exist_ok=True)
        slug = re.sub(r'[^a-zA-Z0-9_\-]', '_', name.strip()).strip('_')
        if not slug:
            slug = f"skin_{int(time.time())}"

        ext = file_ext.lower().replace(".", "")
        if ext not in ("png", "jpg", "jpeg"):
            return False, "Unsupported file format. Must be PNG or JPG."

        img_filename = f"{slug}.{ext}"
        img_path = os.path.join(skins_dir, img_filename)
        with open(img_path, "wb") as f:
            f.write(file_bytes)

        # Build skin metadata JSON
        col_bg = meta.get("cameraBackgroundColor", "#27282BFF") if meta else "#27282BFF"
        col_frame = meta.get("osFrameColor", "#B7B7B0FF") if meta else "#B7B7B0FF"
        skin_meta = {
            "enabled": True,
            "displayName": name,
            "backgroundImage": img_filename,
            "backgroundSprite": 0,
            "uiImageColor": "#FFFFFF",
            "cameraBackgroundColor": col_bg,
            "usesOSFrame": True,
            "osFrameColor": col_frame,
            "osFrames": [
                {"id": "BGLevel", "visible": True},
                {"id": "BGMoney", "visible": True},
                {"id": "CenterBG", "visible": True},
                {"id": "DividendBG", "visible": True},
                {"id": "GraphBG", "visible": True},
                {"id": "InfoBG", "visible": True},
                {"id": "MainBG", "visible": True},
                {"id": "NewsBG", "visible": True},
                {"id": "SharesBG", "visible": True},
                {"id": "TickerBG", "visible": True}
            ],
            "usesBloom": True,
            "bloomColor": meta.get("bloomColor", "#25bf20") if meta else "#25bf20",
            "bloomIntensity": 1.0,
            "bloomStrength": 2.0,
            "bloomSpill": 0.1,
            "usesSkinImage": True,
            "skinImage": img_filename,
            "skinImageAspectRatio": {"x": 1.0, "y": 1.0},
            "skinImageScale": 1.0,
            "buttonSprite": -1,
            "buttonColor": meta.get("buttonColor", "#0b005c") if meta else "#0b005c"
        }

        json_path = os.path.join(skins_dir, f"{slug}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(skin_meta, f, indent=4)

        return True, f"Skin '{name}' installed into {img_filename} and {slug}.json"
    except Exception as e:
        return False, f"Failed installing skin: {e}"


def delete_skin(skin_id: str, game_dir: Optional[str] = None) -> Tuple[bool, str]:
    """Deletes a custom skin and its corresponding image from mods/skins/."""
    paths = get_game_paths(game_dir)
    skins_dir = paths["skins"]
    if not skins_dir or not os.path.exists(skins_dir):
        return False, "Skins directory not found."

    json_path = os.path.join(skins_dir, f"{skin_id}.json")
    if not os.path.exists(json_path):
        return False, "Skin metadata file not found."

    try:
        with open(json_path, "r", encoding="utf-8", errors="ignore") as f:
            meta = json.load(f)
        bg_img = meta.get("backgroundImage") or meta.get("skinImage") or ""
        if bg_img:
            img_path = os.path.join(skins_dir, bg_img)
            if os.path.exists(img_path):
                os.remove(img_path)

        os.remove(json_path)

        # If currently equipped, reset to GR3Y-OS
        settings = read_in_game_settings(game_dir)
        if settings.get("equippedBGSkinId") == skin_id or settings.get("equippedBGSkinId") == meta.get("displayName"):
            save_in_game_settings({"equippedBGSkinId": "GR3Y-OS"}, game_dir)

        return True, f"Skin {skin_id} deleted."
    except Exception as e:
        return False, f"Failed deleting skin: {e}"


def equip_skin(skin_id: str, game_dir: Optional[str] = None) -> Tuple[bool, str]:
    """Equips skin directly in Screen Stocks save file."""
    return save_in_game_settings({"equippedBGSkinId": skin_id}, game_dir)

