import re


def mask_email(value: str | None) -> str:
    """对外展示时隐藏邮箱局部信息，保留排查所需的最小线索。"""
    if not value or "@" not in value:
        return value or ""
    local, domain = value.split("@", 1)
    return f"{local[:2]}***@{domain}"


def mask_phone(value: str | None) -> str:
    if not value:
        return ""
    digits = re.sub(r"\D", "", value)
    return f"***{digits[-4:]}" if len(digits) >= 4 else "***"
