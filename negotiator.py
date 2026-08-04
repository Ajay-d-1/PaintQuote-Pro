"""
negotiator.py
─────────────
AI-powered negotiation response generator.
Uses Groq LLM when configured; falls back to deterministic rule-based
responses when no valid API key is available.
"""

import os
import json
import logging
import requests
from typing import List, Dict

logger = logging.getLogger(__name__)

# ── Config (import after dotenv has been loaded by config.py) ─────────────────
from config import HAS_GROQ, GROQ_API_KEY

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL    = "llama-3.3-70b-versatile"

# Keywords that flag a message as price-related (requires Dad's approval)
PRICE_KEYWORDS = [
    "discount", "reduce", "lower", "cheaper", "less", "price", "cost",
    "budget", "negotiate", "deal", "offer", "afford", "expensive",
    "too much", "bring down", "can you do", "best price", "final price",
    "how much", "rate", "charges", "fees", "rs", "₹", "rupees",
    "payment", "advance", "what if", "instead of",
]


def _is_price_related(message: str) -> bool:
    """Heuristic: does this message involve pricing?"""
    lower = message.lower()
    return any(kw in lower for kw in PRICE_KEYWORDS)


def negotiate_response(quote: dict, client_message: str,
                       chat_history: List[dict]) -> dict:
    """
    Generate a negotiation response.

    Returns a dict:
        reply           str
        suggested_price float | None
        action          str   ('counter_offer' | 'accept' | 'decline' | 'explain')
        trade_off       str
        source          str   ('ai' | 'ai_raw' | 'rule')
        requires_approval bool  True when price-related
    """
    price_related = _is_price_related(client_message)

    if not HAS_GROQ:
        logger.debug("Groq not configured — using rule-based fallback")
        result = _fallback_response(quote, client_message)
        result["requires_approval"] = price_related
        return result

    system_prompt = """You are a smart assistant for a professional painting contractor with 20+ years of experience.
Your job is to help the contractor respond to client messages about their painting quote.

STRICT RULES:
1. NEVER just cut the price. ALWAYS offer a specific TRADE-OFF when reducing cost:
   - Cheaper paint grade: Luxury→Premium saves ~15%, Premium→Economy saves ~20%
   - Skip extras: Putty (₹8/sqft), Primer (₹5/sqft)
   - Reduce scope: fewer rooms, skip ceiling
   - Extend timeline: no rush surcharge
2. Minimum acceptable margin = 15% below quote. NEVER suggest below that.
3. Be polite, professional, confident. The contractor is skilled and charges fair rates.
4. If client asks for >25% off, gently explain why quality matters and hold firm.
5. For general questions (not price-related), just answer helpfully and set is_price_related=false.

OUTPUT: Respond ONLY with valid JSON, no markdown, no extra text:
{
  "reply": "<what the contractor should say to the client>",
  "suggested_price": <number or null>,
  "action": "counter_offer" | "accept" | "decline" | "explain",
  "trade_off": "<what changed, e.g. 'Switched from Luxury to Premium paint'>",
  "is_price_related": true | false
}"""

    context = f"""QUOTE CONTEXT:
- Client: {quote.get('client_name', 'Unknown')}
- Total Area: {quote.get('total_area', 0):.0f} sq ft
- Paint Grade: {quote.get('paint_grade', 'premium').title()}
- Paint Cost: ₹{quote.get('paint_cost', 0):,.0f}
- Labour Cost: ₹{quote.get('labor_cost', 0):,.0f}
- Extras Cost: ₹{quote.get('extras_cost', 0):,.0f}
- GST (18%): ₹{quote.get('gst_cost', 0):,.0f}
- Total Quote: ₹{quote.get('total_cost', 0):,.0f}
- Minimum Acceptable (15% below): ₹{quote.get('total_cost', 0) * 0.85:,.0f}

CLIENT MESSAGE: {client_message}"""

    messages = [{"role": "system", "content": system_prompt}]

    # Include last 5 messages for context
    for msg in chat_history[-5:]:
        role = "user" if msg["role"] == "client" else "assistant"
        messages.append({"role": role, "content": msg["message"]})

    messages.append({"role": "user", "content": context})

    try:
        resp = requests.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"model": MODEL, "messages": messages, "temperature": 0.3},
            timeout=30,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]

        # Strip markdown code fences if present
        content = content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()

        try:
            parsed = json.loads(content)
            return {
                "reply":            parsed.get("reply", content),
                "suggested_price":  parsed.get("suggested_price"),
                "action":           parsed.get("action", "counter_offer"),
                "trade_off":        parsed.get("trade_off", ""),
                "source":           "ai",
                "requires_approval": bool(parsed.get("is_price_related", price_related)),
            }
        except json.JSONDecodeError:
            logger.warning("Groq returned non-JSON; using raw content")
            return {
                "reply":            content,
                "suggested_price":  None,
                "action":           "explain",
                "trade_off":        "",
                "source":           "ai_raw",
                "requires_approval": price_related,
            }

    except Exception as exc:
        logger.error("Groq API error: %s", exc)
        result = _fallback_response(quote, client_message)
        result["requires_approval"] = price_related
        return result


def _fallback_response(quote: dict, client_message: str) -> dict:
    """Rule-based responses used when Groq is unavailable."""
    total     = quote.get("total_cost", 0)
    minimum   = total * 0.85
    grade     = quote.get("paint_grade", "premium")
    msg_lower = client_message.lower()

    # Price-related
    if any(kw in msg_lower for kw in [
        "discount", "reduce", "less", "cheaper", "lower", "price",
        "budget", "afford", "expensive", "deal", "offer", "rs", "₹"
    ]):
        if grade == "luxury":
            new_price = round(total * 0.88, 2)
            return {
                "reply": (
                    f"I understand budget is a consideration. If we switch from "
                    f"Luxury to Premium paint, I can bring it down to ₹{new_price:,.0f}. "
                    f"The finish will still be excellent with 5-year durability. "
                    f"Would that work for you?"
                ),
                "suggested_price": new_price,
                "action":    "counter_offer",
                "trade_off": "Switched from Luxury to Premium paint grade",
                "source":    "rule",
            }
        elif grade == "premium":
            new_price = round(total * 0.82, 2)
            return {
                "reply": (
                    f"I can work with you on this. If we use Economy paint and skip the "
                    f"primer, I can bring it down to ₹{new_price:,.0f}. The finish will look "
                    f"good for 2–3 years, though it won't have the same durability as Premium. "
                    f"Shall I revise the quote?"
                ),
                "suggested_price": new_price,
                "action":    "counter_offer",
                "trade_off": "Switched to Economy paint, removed Primer Coat",
                "source":    "rule",
            }
        else:
            return {
                "reply": (
                    f"We're already using the most economical paint option available. "
                    f"The absolute lowest I can go is ₹{minimum:,.0f} — below that I'd be "
                    f"covering only material costs with no margin for labour. I hope you understand."
                ),
                "suggested_price": round(minimum, 2),
                "action":    "decline",
                "trade_off": "Already at minimum margin",
                "source":    "rule",
            }

    # Time-related
    elif any(kw in msg_lower for kw in ["time", "fast", "quick", "rush", "days", "when", "finish"]):
        return {
            "reply": (
                f"I can prioritise your project and start Monday if you confirm by tomorrow. "
                f"For a rush schedule, I add 10% for overtime labour — total would be "
                f"₹{total * 1.10:,.0f}. Alternatively, if you can wait 2 weeks, the quote "
                f"stays at ₹{total:,.0f}. What works best?"
            ),
            "suggested_price": round(total * 1.10, 2),
            "action":    "counter_offer",
            "trade_off": "Rush job — overtime labour surcharge added",
            "source":    "rule",
        }

    # What paint / materials
    elif any(kw in msg_lower for kw in ["paint", "brand", "material", "quality", "type"]):
        return {
            "reply": (
                f"We use {grade.title()} grade paint for this project — "
                f"{'a top-tier designer finish lasting 7+ years' if grade == 'luxury' else 'a smooth finish with 5-year durability' if grade == 'premium' else 'a clean basic finish with 2-year durability'}. "
                f"All paints are from reputable brands (Asian Paints / Berger / Dulux). "
                f"We can discuss upgrading or downgrading the grade if needed."
            ),
            "suggested_price": None,
            "action":    "explain",
            "trade_off": "",
            "source":    "rule",
        }

    # Warranty / guarantee
    elif any(kw in msg_lower for kw in ["warranty", "guarantee", "guarantee"]):
        return {
            "reply": (
                "Our workmanship comes with a 2-year warranty. If any peeling or bubbling "
                "occurs within that period, we fix it at no charge. We've maintained this "
                "standard for 20+ years — you're in safe hands."
            ),
            "suggested_price": None,
            "action":    "explain",
            "trade_off": "",
            "source":    "rule",
        }

    # Generic / unclear
    else:
        return {
            "reply": (
                f"Thank you for your message. The quote of ₹{total:,.0f} covers all "
                f"materials, labour, and a 2-year workmanship warranty. Is there a specific "
                f"aspect of the scope you'd like to discuss or adjust?"
            ),
            "suggested_price": None,
            "action":    "explain",
            "trade_off": "",
            "source":    "rule",
        }
