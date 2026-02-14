#!/usr/bin/env python3
"""
Watchlist management for the Gradient Research Assistant.

Handles adding/removing tickers, per-ticker alert rule overrides,
global settings, and display of effective rules.

All changes are persisted to watchlist.json and take effect on the
next heartbeat cycle.

Storage backends:
- Local file (default, for development/testing)
- DO Spaces (for backup/sync across deploys)

Set DO_SPACES_* env vars to enable Spaces-backed persistence.

Usage (called by OpenClaw):
    python3 manage_watchlist.py --add TICKER --name "Company Name"
    python3 manage_watchlist.py --remove TICKER
    python3 manage_watchlist.py --set-rule TICKER rule_name value
    python3 manage_watchlist.py --reset-rules TICKER
    python3 manage_watchlist.py --set-global key value
    python3 manage_watchlist.py --show
"""

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any, Optional

# Valid rule names and their expected types
VALID_RULES = {
    "price_movement_pct": (int, float),
    "sentiment_shift": (bool,),
    "social_volume_spike": (bool,),
    "sec_filing": (bool,),
    "competitive_news": (bool,),
}

# Valid global setting keys
VALID_GLOBALS = {"significance_threshold", "cheap_model", "strong_model"}

# Default path to watchlist.json (sibling of this script)
DEFAULT_WATCHLIST_PATH = str(Path(__file__).parent / "watchlist.json")

# Spaces key for persistent config storage
SPACES_CONFIG_KEY = "config/watchlist.json"


# ─── Spaces-backed Config Store ──────────────────────────────────


def _get_spaces_client():
    """Create an S3-compatible client for DO Spaces, or None if not configured."""
    import boto3
    from botocore.config import Config

    access_key = os.environ.get("DO_SPACES_ACCESS_KEY", "")
    secret_key = os.environ.get("DO_SPACES_SECRET_KEY", "")
    endpoint = os.environ.get("DO_SPACES_ENDPOINT", "")

    if not all([access_key, secret_key, endpoint]):
        return None

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4"),
    )


def _spaces_enabled() -> bool:
    """Check if DO Spaces is configured for config persistence."""
    return bool(
        os.environ.get("DO_SPACES_ACCESS_KEY")
        and os.environ.get("DO_SPACES_SECRET_KEY")
        and os.environ.get("DO_SPACES_ENDPOINT")
        and os.environ.get("DO_SPACES_BUCKET")
    )


def load_watchlist(filepath: str = DEFAULT_WATCHLIST_PATH, client=None) -> dict:
    """Load watchlist from Spaces (if configured) or local file.

    Priority:
    1. DO Spaces (if env vars set or client provided) — for persistence across deploys
    2. Local file — for development/testing

    Args:
        filepath: Path to local watchlist.json (fallback)
        client: Pre-configured S3 client (optional, for testing)

    Raises:
        FileNotFoundError: If local file doesn't exist and Spaces not configured.
        json.JSONDecodeError: If the content is invalid JSON.
    """
    if client is not None or _spaces_enabled():
        try:
            if client is None:
                client = _get_spaces_client()
            bucket = os.environ["DO_SPACES_BUCKET"]
            obj = client.get_object(Bucket=bucket, Key=SPACES_CONFIG_KEY)
            return json.loads(obj["Body"].read().decode("utf-8"))
        except Exception as e:
            # NoSuchKey or other error — fall through to local file
            error_code = getattr(e, "response", {}).get("Error", {}).get("Code", "")
            if error_code != "NoSuchKey":
                # Unexpected error, still fall through but could log
                pass

    with open(filepath, "r") as f:
        return json.load(f)


def save_watchlist(watchlist: dict, filepath: str = DEFAULT_WATCHLIST_PATH, client=None) -> None:
    """Save watchlist to Spaces (if configured) AND local file.

    Writes to both locations so the local file stays in sync for
    the current process, and Spaces provides persistence across deploys.

    Args:
        watchlist: The watchlist dict to save
        filepath: Path to local watchlist.json
        client: Pre-configured S3 client (optional, for testing)
    """
    content = json.dumps(watchlist, indent=2) + "\n"

    # Always save locally (for current process)
    with open(filepath, "w") as f:
        f.write(content)

    # Also save to Spaces if configured (for persistence)
    if client is not None or _spaces_enabled():
        try:
            if client is None:
                client = _get_spaces_client()
            bucket = os.environ["DO_SPACES_BUCKET"]
            client.put_object(
                Bucket=bucket,
                Key=SPACES_CONFIG_KEY,
                Body=content.encode("utf-8"),
                ContentType="application/json",
                ACL="private",
            )
        except Exception:
            # Spaces write failed — local file is still updated
            pass


def _normalize_symbol(symbol: str) -> str:
    """Strip $ prefix and uppercase the symbol."""
    return symbol.lstrip("$").upper().strip()


def find_ticker(watchlist: dict, symbol: str) -> Optional[dict]:
    """Find a ticker in the watchlist by symbol (case-insensitive, $-tolerant).

    Returns the ticker dict if found, None otherwise.
    """
    normalized = _normalize_symbol(symbol)
    for ticker in watchlist.get("tickers", []):
        if ticker["symbol"] == normalized:
            return ticker
    return None


def add_ticker(
    watchlist: dict,
    symbol: str,
    name: str,
    theme: Optional[str] = None,
    directive: Optional[str] = None,
    explore_adjacent: bool = False,
) -> dict:
    """Add a new ticker to the watchlist with default rules.

    Args:
        watchlist: The watchlist dict
        symbol: Stock ticker symbol
        name: Company name
        theme: Optional research theme (e.g., "mRNA cancer research")
        directive: Optional research directive
        explore_adjacent: Whether to explore adjacent tickers

    Returns:
        dict with 'success' (bool) and 'message' (str).
    """
    normalized = _normalize_symbol(symbol)

    if not normalized:
        return {"success": False, "message": "Symbol cannot be empty."}

    if not name or not name.strip():
        return {"success": False, "message": "Company name cannot be empty."}

    if find_ticker(watchlist, normalized):
        return {
            "success": False,
            "message": f"${normalized} is already in your watchlist.",
        }

    ticker = {
        "symbol": normalized,
        "name": name.strip(),
        "added": date.today().isoformat(),
        "theme": theme.strip() if theme else None,
        "directive": directive.strip() if directive else None,
        "explore_adjacent": bool(explore_adjacent),
        "rules": {},
    }
    watchlist.setdefault("tickers", []).append(ticker)

    msg = f"Added ${normalized} ({name.strip()}) to your watchlist."
    if theme:
        msg += f" Theme: {theme.strip()}"
    if directive:
        msg += f" Directive: {directive.strip()}"
    if explore_adjacent:
        msg += " Adjacent ticker exploration enabled."

    return {"success": True, "message": msg}


def remove_ticker(watchlist: dict, symbol: str) -> dict:
    """Remove a ticker from the watchlist.

    Returns:
        dict with 'success' (bool) and 'message' (str).
    """
    normalized = _normalize_symbol(symbol)
    tickers = watchlist.get("tickers", [])
    original_len = len(tickers)

    watchlist["tickers"] = [t for t in tickers if t["symbol"] != normalized]

    if len(watchlist["tickers"]) == original_len:
        return {
            "success": False,
            "message": f"${normalized} not found in your watchlist.",
        }

    return {
        "success": True,
        "message": f"Removed ${normalized} from your watchlist.",
    }


def set_rule(watchlist: dict, symbol: str, rule_name: str, value: Any) -> dict:
    """Set a per-ticker alert rule override.

    Validates that the rule name is known and the value type is correct.

    Returns:
        dict with 'success' (bool) and 'message' (str).
    """
    ticker = find_ticker(watchlist, symbol)
    if ticker is None:
        normalized = _normalize_symbol(symbol)
        return {
            "success": False,
            "message": f"${normalized} not found in your watchlist.",
        }

    if rule_name not in VALID_RULES:
        return {
            "success": False,
            "message": f"Unknown rule '{rule_name}'. Valid rules: {', '.join(sorted(VALID_RULES.keys()))}",
        }

    expected_types = VALID_RULES[rule_name]
    if not isinstance(value, expected_types):
        type_names = " or ".join(t.__name__ for t in expected_types)
        return {
            "success": False,
            "message": f"Invalid value for '{rule_name}': expected {type_names}, got {type(value).__name__}.",
        }

    ticker["rules"][rule_name] = value
    return {
        "success": True,
        "message": f"Set {rule_name} = {value} for ${ticker['symbol']}. Effective next heartbeat.",
    }


def reset_rules(watchlist: dict, symbol: str) -> dict:
    """Reset a ticker's rules to defaults (clear all overrides).

    Returns:
        dict with 'success' (bool) and 'message' (str).
    """
    ticker = find_ticker(watchlist, symbol)
    if ticker is None:
        normalized = _normalize_symbol(symbol)
        return {
            "success": False,
            "message": f"${normalized} not found in your watchlist.",
        }

    ticker["rules"] = {}
    return {
        "success": True,
        "message": f"Reset ${ticker['symbol']} to default alert rules.",
    }


def set_global(watchlist: dict, key: str, value: Any) -> dict:
    """Set a global setting (significance_threshold, cheap_model, strong_model).

    Returns:
        dict with 'success' (bool) and 'message' (str).
    """
    if key not in VALID_GLOBALS:
        return {
            "success": False,
            "message": f"Unknown setting '{key}'. Valid settings: {', '.join(sorted(VALID_GLOBALS))}",
        }

    watchlist.setdefault("global_settings", {})[key] = value
    return {
        "success": True,
        "message": f"Set global {key} = {value}. Effective next heartbeat.",
    }


def get_effective_rules(watchlist: dict, symbol: str) -> Optional[dict]:
    """Get the effective alert rules for a ticker (defaults merged with overrides).

    Returns:
        dict of effective rules, or None if ticker not found.
    """
    ticker = find_ticker(watchlist, symbol)
    if ticker is None:
        return None

    defaults = watchlist.get("default_rules", {})
    overrides = ticker.get("rules", {})

    # Merge: defaults as base, overrides take precedence
    effective = {**defaults, **overrides}
    return effective


def set_directive(
    watchlist: dict,
    symbol: str,
    theme: Optional[str] = None,
    directive: Optional[str] = None,
    explore_adjacent: Optional[bool] = None,
) -> dict:
    """Set research theme, directive, or explore_adjacent for a ticker.

    Args:
        watchlist: The watchlist dict
        symbol: Stock ticker symbol
        theme: Research theme (None = don't change)
        directive: Research directive (None = don't change)
        explore_adjacent: Whether to explore adjacent tickers (None = don't change)

    Returns:
        dict with 'success' (bool) and 'message' (str).
    """
    ticker = find_ticker(watchlist, symbol)
    if ticker is None:
        normalized = _normalize_symbol(symbol)
        return {
            "success": False,
            "message": f"${normalized} not found in your watchlist.",
        }

    changes = []
    if theme is not None:
        ticker["theme"] = theme.strip() if theme else None
        changes.append(f"theme='{theme}'" if theme else "theme cleared")
    if directive is not None:
        ticker["directive"] = directive.strip() if directive else None
        changes.append(f"directive='{directive}'" if directive else "directive cleared")
    if explore_adjacent is not None:
        ticker["explore_adjacent"] = bool(explore_adjacent)
        changes.append(f"explore_adjacent={'on' if explore_adjacent else 'off'}")

    if not changes:
        return {"success": False, "message": "No changes specified."}

    return {
        "success": True,
        "message": f"Updated ${ticker['symbol']}: {', '.join(changes)}",
    }


def show_watchlist(watchlist: dict) -> str:
    """Format the current watchlist with effective rules for display.

    Returns:
        Human-readable string representation.
    """
    tickers = watchlist.get("tickers", [])
    if not tickers:
        return "No tickers in your watchlist. Send me a ticker to start tracking!"

    lines = []
    lines.append("📊 **Your Watchlist**\n")

    global_settings = watchlist.get("global_settings", {})
    if global_settings:
        threshold = global_settings.get("significance_threshold", "N/A")
        lines.append(f"⚙️ Global significance threshold: {threshold}")
        lines.append(f"   Cheap model: {global_settings.get('cheap_model', 'N/A')}")
        lines.append(f"   Strong model: {global_settings.get('strong_model', 'N/A')}")
        lines.append("")

    defaults = watchlist.get("default_rules", {})

    for ticker in tickers:
        symbol = ticker["symbol"]
        name = ticker["name"]
        added = ticker.get("added", "unknown")
        overrides = ticker.get("rules", {})
        theme = ticker.get("theme")
        directive = ticker.get("directive")
        explore = ticker.get("explore_adjacent", False)

        lines.append(f"**${symbol}** — {name} (since {added})")

        # Show theme/directive if set
        if theme:
            lines.append(f"  🎯 Theme: {theme}")
        if directive:
            lines.append(f"  📌 Directive: {directive}")
        if explore:
            lines.append("  🔍 Adjacent ticker exploration: on")

        effective = {**defaults, **overrides}
        for rule_name, value in sorted(effective.items()):
            is_override = rule_name in overrides
            marker = " ✏️" if is_override else ""
            if rule_name == "price_movement_pct":
                lines.append(f"  • Price movement alert: >{value}%{marker}")
            elif isinstance(value, bool):
                status = "✅" if value else "❌"
                label = rule_name.replace("_", " ").title()
                lines.append(f"  • {label}: {status}{marker}")
        lines.append("")

    return "\n".join(lines)


# ─── CLI Interface ────────────────────────────────────────────────


def _parse_value(value_str: str) -> Any:
    """Parse a CLI string value into the appropriate Python type."""
    if value_str.lower() in ("true", "yes", "on"):
        return True
    if value_str.lower() in ("false", "no", "off"):
        return False
    try:
        return int(value_str)
    except ValueError:
        pass
    try:
        return float(value_str)
    except ValueError:
        pass
    return value_str


def main():
    parser = argparse.ArgumentParser(description="Manage research watchlist")
    parser.add_argument("--file", default=DEFAULT_WATCHLIST_PATH, help="Path to watchlist.json")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--add", metavar="TICKER", help="Add a ticker")
    group.add_argument("--remove", metavar="TICKER", help="Remove a ticker")
    group.add_argument("--set-rule", nargs=3, metavar=("TICKER", "RULE", "VALUE"), help="Set a per-ticker rule")
    group.add_argument("--reset-rules", metavar="TICKER", help="Reset ticker to default rules")
    group.add_argument("--set-global", nargs=2, metavar=("KEY", "VALUE"), help="Set a global setting")
    group.add_argument("--set-directive", metavar="TICKER", help="Set theme/directive for a ticker")
    group.add_argument("--show", action="store_true", help="Show current watchlist")

    parser.add_argument("--name", help="Company name (required with --add)")
    parser.add_argument("--theme", default=None, help="Research theme (with --add or --set-directive)")
    parser.add_argument("--directive", default=None, help="Research directive (with --add or --set-directive)")
    parser.add_argument("--explore", action="store_true", help="Enable adjacent ticker exploration (with --add or --set-directive)")

    args = parser.parse_args()

    watchlist = load_watchlist(args.file)

    if args.add:
        if not args.name:
            print("Error: --name is required when adding a ticker.", file=sys.stderr)
            sys.exit(1)
        result = add_ticker(
            watchlist,
            args.add,
            args.name,
            theme=args.theme,
            directive=args.directive,
            explore_adjacent=args.explore,
        )
    elif args.remove:
        result = remove_ticker(watchlist, args.remove)
    elif args.set_rule:
        ticker, rule, value = args.set_rule
        result = set_rule(watchlist, ticker, rule, _parse_value(value))
    elif args.reset_rules:
        result = reset_rules(watchlist, args.reset_rules)
    elif args.set_global:
        key, value = args.set_global
        result = set_global(watchlist, key, _parse_value(value))
    elif args.set_directive:
        result = set_directive(
            watchlist,
            args.set_directive,
            theme=args.theme,
            directive=args.directive,
            explore_adjacent=args.explore if args.explore else None,
        )
    elif args.show:
        print(show_watchlist(watchlist))
        return

    print(result["message"])
    if result["success"]:
        save_watchlist(watchlist, args.file)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
