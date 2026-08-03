"""
Hermes plugin: /codexusage

Reads ~/.hermes/auth.json, retrieves the OpenAI/Codex access_token,
extracts the chatgpt_account_id from the JWT, and queries
https://chatgpt.com/backend-api/wham/usage. Output as a compact
ASCII status block with bars for the 5h and weekly windows.

Installation:
  mkdir -p ~/.hermes/plugins/codexusage
  cp codexusage_plugin.yaml ~/.hermes/plugins/codexusage/plugin.yaml
  cp codexusage_init.py     ~/.hermes/plugins/codexusage/__init__.py
  hermes plugins enable codexusage
  # restart hermes, then: /codexusage
"""

import base64
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

AUTH_FILE = os.environ.get(
    "HERMES_AUTH_FILE", os.path.expanduser("~/.hermes/auth.json")
)
USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"


def _bar(used_percent, width=24):
    used_percent = max(0, min(100, used_percent))
    filled = round(width * used_percent / 100)
    return "[" + "#" * filled + "-" * (width - filled) + f"] {used_percent:5.1f}%"


def _human_seconds(seconds):
    if seconds is None:
        return "-"
    delta = timedelta(seconds=int(seconds))
    days, rem = divmod(delta.total_seconds(), 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{int(days)}d")
    if hours or days:
        parts.append(f"{int(hours)}h")
    parts.append(f"{int(minutes)}m")
    return " ".join(parts)


def _window_label(limit_window_seconds):
    if not limit_window_seconds:
        return "Fenster"
    hours = limit_window_seconds / 3600
    if hours <= 6:
        return "5h-Limit"
    if hours <= 48:
        return f"{int(hours)}h-Limit"
    days = limit_window_seconds / 86400
    return f"{int(days)}d-Limit"


def _decode_jwt_payload(token):
    parts = token.split(".")
    if len(parts) != 3:
        return {}
    payload = parts[1]
    payload += "=" * (-len(payload) % 4)
    try:
        raw = base64.urlsafe_b64decode(payload.encode("ascii"))
        return json.loads(raw)
    except Exception:
        return {}


def _load_access_token():
    with open(AUTH_FILE, "r", encoding="utf-8") as f:
        auth = json.load(f)

    providers = auth.get("providers", {})
    token = providers.get("openai-codex", {}).get("tokens", {}).get("access_token")

    if not token:
        pool = auth.get("credential_pool", {}).get("openai-codex", [])
        for entry in pool:
            if entry.get("access_token"):
                token = entry["access_token"]
                break

    if not token:
        raise RuntimeError(
            f"No OpenAI/Codex access_token available in {AUTH_FILE} gefunden."
        )
    return token


def _fetch_usage(access_token):
    claims = _decode_jwt_payload(access_token)
    account_id = claims.get("https://api.openai.com/auth", {}).get(
        "chatgpt_account_id"
    )
    if not account_id:
        raise RuntimeError(
            "chatgpt_account_id not extracted from JWT "
            "(Token eventually expired -> may ask hermes to use openai one time to refresh tokens)."
        )

    req = urllib.request.Request(
        USAGE_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "ChatGPT-Account-Id": account_id,
            "Origin": "https://chatgpt.com",
            "Referer": "https://chatgpt.com/",
            "User-Agent": "Mozilla/5.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")
        raise RuntimeError(f"HTTP {e.code} von {USAGE_URL}: {body[:200]}") from e


def _format_report(data):
    plan = data.get("plan_type", "unknown")
    rl = data.get("rate_limit", {}) or {}
    limit_reached = rl.get("limit_reached", False)
    allowed = rl.get("allowed", True)

    lines = [
        f"Plan: {plan}   |   Limit reached: {'YES' if limit_reached else 'No'}"
        f"   |   Requests accepted: {'yes' if allowed else 'NO'}",
        "",
    ]

    for key in ("primary_window", "secondary_window"):
        win = rl.get(key)
        if not win:
            continue
        label = _window_label(win.get("limit_window_seconds"))
        used = win.get("used_percent", 0) or 0
        reset_in = _human_seconds(win.get("reset_after_seconds"))
        lines.append(f"{label:<10} {_bar(used)}   Reset in {reset_in}")

    credits = data.get("credits")
    if credits:
        bal = credits.get("balance")
        unlimited = credits.get("unlimited")
        lines.append("")
        lines.append(
            f"Credits: {'unlimited' if unlimited else bal}"
        )

    return "\n".join(lines)


def _handle_codexusage(raw_args: str) -> str:
    try:
        token = _load_access_token()
        data = _fetch_usage(token)
    except Exception as e:
        return f"codexusage: ERROR - {e}"

    if raw_args.strip() == "json":
        return json.dumps(data, indent=2, ensure_ascii=False)

    return _format_report(data)


def register(ctx):
    ctx.register_command(
        "codexusage",
        handler=_handle_codexusage,
        description="Display OpenAI/Codex Plan-consumption (5h/weekly, Credits). 'json' to get raw data.",
    )
