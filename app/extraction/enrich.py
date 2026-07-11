"""Fill missing fields when the LLM omits obvious details from the text."""

from __future__ import annotations

import re
from typing import Optional

from app.extraction.schema import ExtractedJob

_MOVERS_RE = re.compile(
    r"\b(\d+)\s*(?:movers?|men|people|crew|person)\b",
    re.IGNORECASE,
)
_TRUCK_RE = re.compile(
    r"\b(\d+)\s*(?:ft|foot|feet|'|’)?\s*(?:truck|van)?\b",
    re.IGNORECASE,
)
_TRUCK_SIZE_RE = re.compile(
    r"\b(15|16|17|20|22|24|26)\s*(?:ft|foot|feet|'|’)\b",
    re.IGNORECASE,
)
# "Joshua Soberano 1 pm unload 15ft truck North Bethesda, MD (404) 450-7688 |"
_LEAD_NAME_RE = re.compile(
    r"^\s*([A-Z][a-zA-Z'''\-]+(?:\s+[A-Z][a-zA-Z'''\-]+){0,3})\s+"
    r"(?:\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM)|morning|afternoon|evening)",
    re.MULTILINE,
)
_PHONE_RE = re.compile(r"\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_HOURS_RE = re.compile(
    r"(?:pd\s+)?(\d+)\s*(?:hrs?|hours?)\s*minimum|minimum\s+(\d+)\s*(?:hrs?|hours?)",
    re.IGNORECASE,
)
_RATE_RE = re.compile(r"\$?\s*(\d{2,4})\s*/\s*hr", re.IGNORECASE)
_NO_HEAVY_RE = re.compile(
    r"no\s+(?:oversized|oversize|extremely\s+heavy|heavy\s+items)|"
    r"nothing\s+over\s+\d+\s*lbs?|no\s+single\s+item\s+over",
    re.IGNORECASE,
)
_UNLOAD_ONLY_RE = re.compile(
    r"\bunload(?:ing)?\s+only\b|\bjust\s+be\s+unloading\b|\bunloading\s+at\b|"
    r"\bunload\s+\d+\s*ft|\bunload\s+\d+ft|\bmoving\s+in\b",
    re.IGNORECASE,
)
_LOAD_ONLY_RE = re.compile(r"\bload(?:ing)?\s+only\b|\bneed\s+help\s+with\s+loading\b", re.IGNORECASE)
_UHAUL_RE = re.compile(r"u-?haul|moving\s*helper", re.IGNORECASE)


def normalize_truck_type(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    text = value.strip().lower().replace(" ", "")
    text = text.replace("foot", "ft").replace("feet", "ft").replace("'", "").replace("’", "")
    m = re.search(r"(\d+)\s*ft", text) or re.search(r"(\d+)ft", text) or re.search(r"(\d+)truck", text)
    if m:
        return f"{m.group(1)}ft"
    if text.isdigit():
        return f"{text}ft"
    return text or None


def _infer_movers(text: str) -> Optional[int]:
    m = _MOVERS_RE.search(text)
    if not m:
        return None
    try:
        n = int(m.group(1))
        return n if 1 <= n <= 20 else None
    except ValueError:
        return None


def _infer_truck(text: str) -> Optional[str]:
    m = _TRUCK_SIZE_RE.search(text) or _TRUCK_RE.search(text)
    if not m:
        return None
    return normalize_truck_type(f"{m.group(1)}ft")


_SIGN_OFF_NAME_RE = re.compile(
    r"(?i)(?:^|\n)\s*(?:best|thanks|thank you|regards|sincerely)[,!]?\s*\n\s*([A-Z][a-zA-Z'''\-]+(?:\s+[A-Z][a-zA-Z'''\-]+)?)\s*$"
)


def _infer_name(text: str) -> Optional[str]:
    m = _LEAD_NAME_RE.search(text or "")
    if m:
        name = m.group(1).strip()
        if name.lower() not in {"the", "truck", "unload", "load", "uhaul", "moving"}:
            return name
    m = _SIGN_OFF_NAME_RE.search((text or "").strip())
    if m:
        return m.group(1).strip()
    return None


_ASSEMBLY_YES_RE = re.compile(
    r"\b(?:need|needs|want|require)s?\s+(?:help\s+with\s+)?(?:assembly|assemble|breakdown|disassemble)",
    re.IGNORECASE,
)
_ASSEMBLY_NO_RE = re.compile(
    r"okay\s+with\s+assembly\s+just\s+need\s+manpower|no\s+assembly|assembly\s+not\s+needed",
    re.IGNORECASE,
)
_PACK_YES_RE = re.compile(r"\b(?:need|want|require)s?\s+(?:full\s+)?packing\b|\bpack(?:ing)?\s+(?:service|help)\b", re.I)
_UNPACK_YES_RE = re.compile(r"\b(?:need|want|require)s?\s+unpacking\b|\bunpack(?:ing)?\s+(?:service|help)\b", re.I)
_TIME_WINDOW_RE = re.compile(
    r"(?:preferred\s+(?:time\s+)?window|window|as\s+early\s+as)\s*[:=]?\s*"
    r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)?(?:\s*[-–to]+\s*\d{1,2}(?::\d{2})?\s*(?:am|pm)?)?)"
    r"|"
    r"\b(\d{1,2}(?::\d{2})?\s*(?:am|pm)\s*[-–to]+\s*\d{1,2}(?::\d{2})?\s*(?:am|pm))\b",
    re.IGNORECASE,
)
_EARLY_AS_RE = re.compile(
    r"as\s+early\s+as\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm))",
    re.IGNORECASE,
)
_WALK_RE = re.compile(
    r"(\d+\s*[-–to]+\s*\d+\s*(?:ft|feet|foot)\s+walk[^.!\n]{0,40})",
    re.IGNORECASE,
)
_HAND_TRUCK_RE = re.compile(r"\b(?:u-?haul\s+)?hand\s+truck\b", re.IGNORECASE)
_STREET_ADDR_RE = re.compile(
    r"(?:(?P<label>[A-Za-z][A-Za-z0-9'&. \-]{1,40})\s*:\s*)?"
    r"(?P<street>\d{1,6}\s+[A-Za-z0-9.' \-]+?"
    r"(?:Blvd|Boulevard|St|Street|Ave|Avenue|Rd|Road|Dr|Drive|Ln|Lane|Ct|Court|Way|Pkwy|Parkway|Pl|Place)\.?)"
    r"(?:,?\s*(?P<citystate>[A-Za-z .]+,\s*[A-Z]{2}(?:\s+\d{5}(?:-\d{4})?)?))?",
    re.IGNORECASE,
)
_INCOMPLETE_ADDR_TAIL_RE = re.compile(
    r"[\s.]*\b(?:the\s+apartment\s+is|apartment\s+is|the\s+truck\s+will|"
    r"from\s+the\s+elevator|inventory|preferred|it\s+will)\b.*$",
    re.IGNORECASE,
)
_FLUFF_ADDR_PREFIX_RE = re.compile(
    r"^(?:the\s+)?(?:apartment\s+complex|complex|building|property)\s+",
    re.IGNORECASE,
)
_EXPLICIT_ONE_MOVER_RE = re.compile(
    r"\b(?:1|one)\s*(?:mover|person|man)\b|\bsingle\s+mover\b",
    re.IGNORECASE,
)


def _normalize_addr(value: Optional[str]) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value.strip().lower())


def _clean_address(value: Optional[str], raw: str = "") -> Optional[str]:
    """Turn messy LLM/email address blobs into 'Label: street, City, ST ZIP'."""
    text = (value or "").strip()
    if not text and not raw:
        return None

    for source in (text, raw):
        if not source:
            continue
        m = _STREET_ADDR_RE.search(source)
        if not m:
            continue
        label = (m.group("label") or "").strip(" :")
        street = re.sub(r"\s+", " ", (m.group("street") or "").strip(" ,."))
        citystate = re.sub(r"\s+", " ", (m.group("citystate") or "").strip(" ,."))
        if label:
            label = _FLUFF_ADDR_PREFIX_RE.sub("", label).strip()
            if len(label) > 40:
                bits = label.split()
                label = " ".join(bits[-2:]) if len(bits) >= 2 else label
        if label and not label.lower().startswith("apartment"):
            out = f"{label}: {street}"
        else:
            out = street
        if citystate:
            out = f"{out}, {citystate}"
        return out

    cleaned = _INCOMPLETE_ADDR_TAIL_RE.sub("", text).strip(" .,;")
    cleaned = _FLUFF_ADDR_PREFIX_RE.sub("", cleaned).strip(" .,;")
    cleaned = re.sub(r"\s+", " ", cleaned)
    if cleaned.endswith((" the", " The", " is", " at")):
        cleaned = cleaned.rsplit(" ", 1)[0].strip(" .,;")
    return cleaned or None


def _infer_move_time(text: str) -> Optional[str]:
    m = _TIME_WINDOW_RE.search(text or "")
    if m:
        raw = (m.group(1) or m.group(2) or "").strip(" :")
        if raw:
            early = _EARLY_AS_RE.search(text or "")
            if early and early.group(1).lower() not in raw.lower():
                return f"{raw} (as early as {early.group(1)})"
            return raw
    early = _EARLY_AS_RE.search(text or "")
    if early:
        return f"as early as {early.group(1)}"
    return None


def _infer_access_notes(text: str) -> Optional[str]:
    """Build compact access notes only from phrases present in the email."""
    parts: list[str] = []
    raw = text or ""

    floor_m = re.search(r"(\d+(?:st|nd|rd|th)?\s+floor)", raw, re.IGNORECASE)
    if floor_m:
        parts.append(floor_m.group(1))

    if re.search(r"loading\s+dock", raw, re.I) and re.search(r"elevator", raw, re.I):
        parts.append("loading dock beside elevator")
    elif re.search(r"\bno\s+elevator\b", raw, re.I):
        parts.append("no elevator")
    elif re.search(r"\belevator\b", raw, re.I):
        parts.append("elevator")

    walk = _WALK_RE.search(raw)
    if walk:
        bit = re.sub(r"\s+", " ", walk.group(1)).strip(" ,.;")
        bit = re.sub(r"^(?:about\s+a\s+|about\s+)", "", bit, flags=re.I)
        parts.append(bit)

    if re.search(r"luggage\s+cart", raw, re.I):
        parts.append("complex luggage cart for small items")

    if _HAND_TRUCK_RE.search(raw):
        if re.search(r"u-?haul", raw, re.I):
            parts.append("U-Haul hand truck available")
        else:
            parts.append("hand truck available")

    if not parts:
        return None
    seen: set[str] = set()
    cleaned: list[str] = []
    for p in parts:
        key = p.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(p)
    return "; ".join(cleaned[:5])


def _notes_look_hallucinated(notes: Optional[str], raw: str) -> bool:
    """True when special_notes contain floors/access not present in the email."""
    if not notes:
        return False
    raw_l = (raw or "").lower()
    notes_l = notes.lower()
    for m in re.finditer(r"(\d+)\s*(?:st|nd|rd|th)?\s*floor", notes_l):
        n = m.group(1)
        if (
            f"{n}th floor" not in raw_l
            and f"{n}nd floor" not in raw_l
            and f"{n}st floor" not in raw_l
            and f"{n}rd floor" not in raw_l
            and f"{n} floor" not in raw_l
        ):
            return True
    if "no elevator" in notes_l and "no elevator" not in raw_l and "without elevator" not in raw_l:
        return True
    return False


def _notes_are_bloated(notes: Optional[str]) -> bool:
    if not notes:
        return False
    if len(notes) > 180:
        return True
    floors = re.findall(r"\d+(?:st|nd|rd|th)?\s+floor", notes, flags=re.I)
    return len(floors) >= 2


def enrich_job_for_pricing(job: ExtractedJob, conversation: str = "") -> ExtractedJob:
    """Backfill obvious fields the LLM missed from the raw email text."""
    blob = " ".join(
        part
        for part in (
            job.summary or "",
            conversation or "",
            " ".join(job.customer_requests or []),
            job.service_requested or "",
            job.special_notes or "",
        )
        if part
    )
    raw = conversation or ""

    data = job.model_dump()

    if not data.get("customer_name"):
        inferred = _infer_name(raw) or _infer_name(blob)
        if inferred:
            data["customer_name"] = inferred

    if not data.get("customer_phone"):
        m = _PHONE_RE.search(raw) or _PHONE_RE.search(blob)
        if m:
            data["customer_phone"] = m.group(0)

    if not data.get("customer_email"):
        m = _EMAIL_RE.search(raw) or _EMAIL_RE.search(blob)
        if m:
            data["customer_email"] = m.group(0)

    inferred_movers = _infer_movers(blob)
    if data.get("num_movers") is None:
        if inferred_movers is not None:
            data["num_movers"] = inferred_movers
        elif _UHAUL_RE.search(blob):
            data["num_movers"] = 2
    elif (
        data.get("num_movers") == 1
        and _UHAUL_RE.search(blob)
        and inferred_movers is None
        and not _EXPLICIT_ONE_MOVER_RE.search(raw)
    ):
        # Small models often emit 1; U-Haul labor default is 2 unless email says otherwise
        data["num_movers"] = 2

    truck = normalize_truck_type(data.get("truck_type"))
    if not truck:
        truck = _infer_truck(blob)
    data["truck_type"] = truck

    if not data.get("move_time"):
        inferred_time = _infer_move_time(raw) or _infer_move_time(blob)
        if inferred_time:
            data["move_time"] = inferred_time

    if not data.get("minimum_hours"):
        m = _HOURS_RE.search(blob)
        if m:
            data["minimum_hours"] = m.group(1) or m.group(2)

    if not data.get("hourly_rate"):
        m = _RATE_RE.search(blob)
        if m:
            data["hourly_rate"] = f"${m.group(1)}/hr"

    if not data.get("booking_source") and _UHAUL_RE.search(blob):
        data["booking_source"] = "U-Haul" if re.search(r"u-?haul", blob, re.I) else "Moving Helper"

    unload_only = bool(_UNLOAD_ONLY_RE.search(blob)) or (
        (data.get("service_requested") or "").lower().find("unload") >= 0
        and "load" not in (data.get("service_requested") or "").lower().replace("unload", "")
    )
    load_only = bool(_LOAD_ONLY_RE.search(blob))
    if unload_only or load_only:
        if not _PACK_YES_RE.search(blob):
            data["packing"] = "N"
        if unload_only and not _UNPACK_YES_RE.search(blob):
            data["unpacking"] = "N"
        if load_only and not _UNPACK_YES_RE.search(blob):
            if data.get("unpacking") in (None, ""):
                data["unpacking"] = "N"

    if unload_only:
        if not data.get("service_requested") or (data.get("service_requested") or "").lower() in {
            "unloading",
            "unload",
        }:
            data["service_requested"] = "unload only"
        cleaned_unload = _clean_address(data.get("unload_address"), raw) or _clean_address(
            None, raw
        )
        if cleaned_unload:
            data["unload_address"] = cleaned_unload
        load = data.get("load_address")
        unload = data.get("unload_address")
        if load and unload and _normalize_addr(load) == _normalize_addr(unload):
            data["load_address"] = None
        elif load and not unload:
            data["unload_address"] = _clean_address(load, raw) or load
            data["load_address"] = None
        else:
            data["load_address"] = None
    elif load_only:
        if not data.get("service_requested") or (data.get("service_requested") or "").lower() in {
            "loading",
            "load",
        }:
            data["service_requested"] = "load only"
        cleaned_load = _clean_address(data.get("load_address"), raw)
        if cleaned_load:
            data["load_address"] = cleaned_load
        data["unload_address"] = None
    else:
        if data.get("unload_address"):
            data["unload_address"] = _clean_address(data.get("unload_address"), raw) or data.get(
                "unload_address"
            )
        if data.get("load_address"):
            data["load_address"] = _clean_address(data.get("load_address"), raw) or data.get(
                "load_address"
            )

    if _PACK_YES_RE.search(blob):
        data["packing"] = "Y"
    if _UNPACK_YES_RE.search(blob):
        data["unpacking"] = "Y"

    if _NO_HEAVY_RE.search(blob):
        data["over_250_lbs"] = "N"
        if not data.get("heaviest_item"):
            data["heaviest_item"] = "none noted"

    if _ASSEMBLY_NO_RE.search(blob):
        data["assembly"] = "N"
    elif _ASSEMBLY_YES_RE.search(blob):
        data["assembly"] = "Y"

    access = _infer_access_notes(raw)
    if access and (
        not data.get("special_notes")
        or _notes_look_hallucinated(data.get("special_notes"), raw)
        or _notes_are_bloated(data.get("special_notes"))
    ):
        data["special_notes"] = access
    elif access and data.get("special_notes"):
        notes = data["special_notes"]
        for bit in access.split("; "):
            if bit and bit.lower() not in notes.lower():
                notes = f"{notes}; {bit}"
        data["special_notes"] = notes

    # Prefer early-arrival detail in Time when email has it
    if data.get("move_time") and raw:
        early = _EARLY_AS_RE.search(raw)
        mt = data["move_time"]
        if early and early.group(1).lower() not in mt.lower() and "early" not in mt.lower():
            data["move_time"] = f"{mt} (as early as {early.group(1)})"

    promises = list(data.get("promises_made") or [])
    cleaned = []
    for p in promises:
        pl = str(p).lower()
        if "hand truck" in pl or ("u-haul" in pl and "truck" in pl and "assign" in pl):
            notes = data.get("special_notes") or ""
            extra = str(p).strip()
            if extra and extra.lower() not in notes.lower():
                data["special_notes"] = f"{notes}; {extra}".strip("; ")
            continue
        cleaned.append(p)
    data["promises_made"] = cleaned

    return ExtractedJob.model_validate(data)
