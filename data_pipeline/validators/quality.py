def validate_required_fields(
    rows: list[dict[str, object]], required_fields: list[str]
) -> list[str]:
    errors: list[str] = []
    for index, row in enumerate(rows):
        missing = [field for field in required_fields if field not in row]
        if missing:
            errors.append(f"row {index} missing fields: {', '.join(missing)}")
    return errors


def summarize_row_count(rows: list[dict[str, object]], label: str) -> dict[str, object]:
    return {
        "label": label,
        "row_count": len(rows),
        "is_empty": len(rows) == 0,
    }

