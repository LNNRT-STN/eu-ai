"""Short briefings for mayors and fire brigades, drafted by Claude from a small facts dict (never datasets).
AI writes words, never numbers: every number comes from the tool and the model is told to use only those.
No key or an API error -> a deterministic template, marked "template"."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL = "claude-haiku-5-5"  # current fast model
MAX_TOKENS = 400
FOOTER = "Drafted by AI from the tool's numbers; check before sending."
TEMPLATE_FOOTER = "Generated from a fixed template from the tool's numbers; check before sending."

SYSTEM = f"""You draft short flood briefings for a public crisis room in Belgium, Germany or the Netherlands.
The reader is the named recipient (a mayor or a fire brigade). Write in plain English for a non-specialist.

Rules:
- Write 6 to 10 short lines of plain text. No headings, no markdown, no bullet symbols other than "- ".
- Use ONLY the facts given in the user message. Every number you write must appear exactly as given there.
  Never compute, round, estimate or invent a number, date, time, place or name, and never compare numbers
  with ratios such as "twice" or "half".
- If a fact is missing, do not guess it; leave it out.
- Line 1 says what changed: the planning scenario and the town's status. Then what it means for the recipient,
  then the concrete next step that fits the recipient (a mayor: order the evacuation of the zone, open the named
  shelters, ask the district for buses; a fire brigade: crews door to door, the number of homes to check, the
  shelters to send people to, the closed roads to avoid).
- The scenario is a modelled flood zone (EFAS) for a given return period, not a forecast and not an observed flood:
  say so once. A return period says how rare a flood is ("a 100-year flood": 1 % chance in any year), not when it
  comes. If people in other return-period zones are given, you may name them to show how the zone grows.
- Say that the zone is modelled whenever you give its number of people.
- End with this exact line: {FOOTER}"""

_client = None


def _key():
    try:
        from dotenv import dotenv_values
        k = dotenv_values(ROOT / ".env").get("claude_api")
    except Exception:
        k = None
    return k or os.environ.get("claude_api")


def client():
    """Anthropic client from .env (claude_api), or None. The key never leaves this function's object."""
    global _client
    if _client is None:
        k = _key()
        if not k:
            return None
        import anthropic
        _client = anthropic.Anthropic(api_key=k, timeout=20.0, max_retries=1)
    return _client


def _facts_text(facts):
    return "\n".join(f"- {k.replace('_', ' ')}: {v}" for k, v in facts.items())


def template(kind, recipient, facts):
    f = facts
    zone = next((k for k in f if k.startswith("people_in_") and k.endswith("_year_zone")
                 and k.split("_")[2] in f.get("scenario", "")), None)
    lines = [f"To: {recipient}",
             f"{f.get('town', 'Town')}: {f.get('status', kind)}. Scenario: {f.get('scenario', '?')}."]
    if zone:
        lines.append(f"About {f[zone]} residents live inside the modelled {zone.split('_')[2]}-year zone; "
                     f"{f.get('homes_to_check', '?')} homes to check.")
    if f.get("shelters"):
        lines.append(f"Shelters in the plan (candidates, not official): {f['shelters']}.")
    if f.get("people_without_a_shelter_place"):
        lines.append(f"{f['people_without_a_shelter_place']} people have no shelter place within 10 km: ask the district.")
    if f.get("roads_closed"):
        lines.append(f"Roads closed (inside the zone): {f['roads_closed']}.")
    if recipient.startswith("Fire brigade"):
        lines.append("Next step: crews door to door in the zone, help requests first; avoid the closed roads.")
    else:
        lines.append("Next step: order the evacuation of the zone, open the shelters, ask the district for buses.")
    lines.append(TEMPLATE_FOOTER)
    return "\n".join(lines)


def draft(kind, recipient, facts):
    """(text, source) with source "ai" or "template"."""
    c = client()
    if c is None:
        return template(kind, recipient, facts), "template"
    try:
        r = c.messages.create(
            model=MODEL, max_tokens=MAX_TOKENS,
            system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
            thinking={"type": "disabled"}, output_config={"effort": "low"},
            messages=[{"role": "user", "content": f"Report kind: {kind}\nRecipient: {recipient}\nFacts:\n"
                                                  f"{_facts_text(facts)}"}])
        text = "".join(b.text for b in r.content if b.type == "text").strip()
        if r.stop_reason not in ("end_turn", "max_tokens") or not text:
            raise RuntimeError(f"no usable text ({r.stop_reason})")
        if not text.endswith(FOOTER):
            text = text.rstrip() + "\n" + FOOTER
        global last_usage
        last_usage = r.usage
        return text, "ai"
    except Exception as e:  # never surface the key; the message of SDK errors does not contain it
        global last_error
        last_error = type(e).__name__
        return template(kind, recipient, facts), "template"


last_usage = None
last_error = None


def write(kind, recipient, facts) -> str:
    return draft(kind, recipient, facts)[0]


if __name__ == "__main__":
    t, s = draft("status", "Fire brigade, Pepinster", {
        "town": "Pepinster", "status": "evacuate", "from": "normal", "time": "30 Oct 2026 11:00",
        "scenario": "planning scenario: a 100-year river flood (EFAS flood hazard map; a flood this size has a 1 % "
                    "chance in any year). A model zone, not a forecast and not an observed flood",
        "people_in_100_year_zone": 2163, "people_in_10_year_zone": 1520, "homes_to_check": 640,
        "shelters": "Athénée royal (Rue des Écoles 1, Pepinster): about 900 people", "district": "Province of Liège"})
    print(s, last_error, last_usage)
    print(t)
