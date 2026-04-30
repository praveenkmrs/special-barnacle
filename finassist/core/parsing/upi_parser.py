from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class UPIDetails:
    method: str = "UPI"
    counterparty_name: str | None = None
    counterparty_vpa: str | None = None
    counterparty_ifsc: str | None = None
    reference_number: str | None = None
    remark: str | None = None


_IFSC_RE = re.compile(r"^[A-Z]{4}[0-9A-Z]{7}$")
_REF_RE = re.compile(r"^\d{8,18}$")


def parse_upi_narration(narration: str) -> UPIDetails | None:
    if not narration:
        return None

    narration = str(narration).strip()
    upper = narration.upper()

    method: str | None = None
    for m in ("UPI", "IMPS", "NEFT", "RTGS"):
        if upper.startswith(m):
            method = m
            break
    if not method:
        return None

    details = UPIDetails(method=method)

    if "-" in narration and "/" not in narration:
        parts = [p.strip() for p in narration.split("-") if p.strip()]
        for part in parts[1:]:
            if _IFSC_RE.match(part):
                details.counterparty_ifsc = part
            elif _REF_RE.match(part):
                details.reference_number = part
            elif "@" in part:
                details.counterparty_vpa = part
            elif len(part) > 2 and not part.startswith("X"):
                if not details.counterparty_name:
                    details.counterparty_name = part
    elif "/" in narration:
        parts = [p.strip() for p in narration.split("/") if p.strip()]
        if len(parts) >= 4:
            details.reference_number = parts[2] if len(parts) > 2 else None
            details.counterparty_name = parts[3] if len(parts) > 3 else None
            if len(parts) > 4 and _IFSC_RE.match(parts[4]):
                details.counterparty_ifsc = parts[4]

    return details
