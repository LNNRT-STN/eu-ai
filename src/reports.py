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
- Line 1 says what changed and when. Then what it means for the recipient, then the concrete next step
  that fits the recipient (a mayor: alert and evacuate residents, open shelters; a fire brigade: crews,
  door-knocking, closed roads).
- Say that river flows come from a model (GloFAS) and are not a gauge reading when flows are mentioned.
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
    lines = [f"To: {recipient}",
             f"{f.get('town', 'Town')}: status {f.get('status', kind)} since {f.get('time', '?')}"
             + (f" (was {f['from']})." if f.get("from") else ".")]
    if "flow_m3s" in f:
        lines.append(f"River point {f.get('river_point', '?')}: {f['flow_m3s']} m3/s modelled (GloFAS), "
                     f"2-year flood {f.get('two_year_flow_m3s', '?')}, July 2021 peak {f.get('july_2021_peak_m3s', '?')}.")
    if "people_in_2021_water" in f:
        lines.append(f"About {f['people_in_2021_water']} residents lived inside the 2021 flood extent.")
    if f.get("roads_closed"):
        lines.append(f"Roads closed: {f['roads_closed']}.")
    if f.get("status") == "evacuate":
        lines.append("Next step: order evacuation of the 2021 flood zone, open shelters, send crews door to door.")
    else:
        lines.append("Next step: alert residents of the 2021 flood zone and prepare shelters and crews.")
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
    t, s = draft("status", "Mayor of Pepinster", {"town": "Pepinster", "status": "evacuate", "from": "warn",
                                                   "time": "13 Jul 2021 18:00", "river_point": "Vesdre · Chaudfontaine",
                                                   "flow_m3s": 146, "two_year_flow_m3s": 66, "july_2021_peak_m3s": 291,
                                                   "people_in_2021_water": 2163})
    print(s, last_error, last_usage)
    print(t)
