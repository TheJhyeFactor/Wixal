"""Adapted from NousResearch/hermes-agent cron/jobs.py at 0e21933114c911075782d5744cee5403996d38ae.
Copyright (c) 2025 Nous Research. MIT; see bundled Hermes-LICENSE.
"""
import re
_DURATION_MULTIPLIERS = {"m":1,"h":60,"d":1440}

def parse_duration(s: str) -> int:
    """Parse a duration into minutes: "30m" → 30, "2h" → 120, "1d" → 1440, bare "hour" → 60."""
    s = s.strip().lower()
    match = re.match(r'^(\d*)\s*(m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days)$', s)
    if not match:
        raise ValueError(
            f"Invalid duration: '{s}'. Use format like '30m', '2h', '1d', "
            "or a bare unit like 'hour' (defaults to 1).")
    value = int(match.group(1)) if match.group(1) else 1
    return value * _DURATION_MULTIPLIERS[match.group(2)[0]]


def bounded_seconds(value):
    seconds = parse_duration(value) * 60
    if not 60 <= seconds <= 366 * 86400:
        raise ValueError("Choose a duration between one minute and 366 days")
    return seconds
