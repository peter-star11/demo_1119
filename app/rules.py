from datetime import date


def normalize_record(data):
    normalized = {key: value for key, value in data.items()}
    for field in ("name", "category", "location", "status", "date"):
        value = normalized.get(field)
        if isinstance(value, str):
            normalized[field] = " ".join(value.strip().split())

    if isinstance(normalized.get("category"), str):
        normalized["category"] = normalized["category"].title()
    if isinstance(normalized.get("status"), str):
        normalized["status"] = normalized["status"].upper()

    amount = normalized.get("amount")
    if amount is not None and amount != "":
        try:
            normalized["amount"] = round(float(amount), 2)
        except (TypeError, ValueError):
            normalized["amount"] = amount
    return normalized


def evaluate_record(data):
    rules = []
    missing = [
        field
        for field in ("name", "category", "amount", "location", "date", "status")
        if data.get(field) is None or data.get(field) == ""
    ]

    if missing:
        rules.append(
            {
                "id": "required-fields",
                "label": "Required fields present",
                "result": "flagged",
                "detail": f"Missing: {', '.join(missing)}",
            }
        )
        return {
            "confidence": 0.34,
            "decision": "NEEDS_REVIEW",
            "reason": f"Required information is missing: {', '.join(missing)}.",
            "rules": rules,
        }

    rules.append(
        {
            "id": "required-fields",
            "label": "Required fields present",
            "result": "passed",
            "detail": "All required fields are populated.",
        }
    )

    amount = data.get("amount")
    if not isinstance(amount, (int, float)):
        rules.append(
            {
                "id": "valid-amount",
                "label": "Amount is numeric",
                "result": "flagged",
                "detail": "Amount could not be interpreted as a number.",
            }
        )
        return {
            "confidence": 0.4,
            "decision": "NEEDS_REVIEW",
            "reason": "The amount is not a valid number.",
            "rules": rules,
        }

    if amount < 0:
        rules.append(
            {
                "id": "non-negative-amount",
                "label": "Amount is non-negative",
                "result": "flagged",
                "detail": "Negative amounts require manual validation.",
            }
        )
        return {
            "confidence": 0.38,
            "decision": "NEEDS_REVIEW",
            "reason": "A negative amount needs manual validation.",
            "rules": rules,
        }

    rules.append(
        {
            "id": "non-negative-amount",
            "label": "Amount is non-negative",
            "result": "passed",
            "detail": "Amount is zero or greater.",
        }
    )

    category = str(data["category"]).casefold()
    status = str(data["status"]).casefold()
    conflicts = []
    if status in {"closed", "complete", "completed"} and amount > 0:
        conflicts.append("record is marked closed but still has an outstanding amount")
    if category == "invoice" and amount == 0:
        conflicts.append("invoice has a zero amount")
    try:
        date.fromisoformat(str(data["date"]))
    except ValueError:
        conflicts.append("date is not in YYYY-MM-DD format")

    if conflicts:
        rules.append(
            {
                "id": "consistency-check",
                "label": "Record details are consistent",
                "result": "flagged",
                "detail": "; ".join(conflicts),
            }
        )
        return {
            "confidence": 0.58,
            "decision": "NEEDS_REVIEW",
            "reason": f"Conflicting information: {'; '.join(conflicts)}.",
            "rules": rules,
        }

    rules.extend(
        [
            {
                "id": "consistency-check",
                "label": "Record details are consistent",
                "result": "passed",
                "detail": "Category, status, amount, and date are consistent.",
            },
            {
                "id": "confidence-threshold",
                "label": "Automation confidence threshold",
                "result": "passed",
                "detail": "Confidence is above the 80% auto-processing threshold.",
            },
        ]
    )
    return {
        "confidence": 0.96,
        "decision": "AUTO_PROCESSED",
        "reason": "Required fields and consistency checks passed.",
        "rules": rules,
    }
