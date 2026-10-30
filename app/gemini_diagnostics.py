"""Classify Gemini errors without exposing provider text or reflected input.

These are bounded diagnostic hints, not a verbatim API error viewer. Every
returned string is predefined here; neither evidence nor provider messages are
ever copied into the result.
"""
import re

import httpx


_FIELD_ALIASES = {
    "generationconfig.responsejsonschema": "generationConfig.responseJsonSchema",
    "generationconfig.responseschema": "generationConfig.responseSchema",
    "generationconfig.responsemimetype": "generationConfig.responseMimeType",
    "generationconfig.temperature": "generationConfig.temperature",
    "generationconfig.maxoutputtokens": "generationConfig.maxOutputTokens",
    "generationconfig.thinkingconfig": "generationConfig.thinkingConfig",
    "contents": "contents",
    "systeminstruction": "systemInstruction",
    "model": "model",
}

_MESSAGES = {
    "invalid_schema": "Google từ chối cấu hình structured JSON/schema. Kiểm tra schema và các trường được model/API hỗ trợ; không đổi model tự động.",
    "invalid_temperature": "Google từ chối tham số temperature. Kiểm tra phạm vi hoặc khả năng hỗ trợ tham số của model này.",
    "invalid_model": "Google từ chối model hoặc phương thức generateContent. Kiểm tra model ID, phiên bản API và khả năng truy cập của project.",
    "invalid_api_key": "Google báo API key không hợp lệ. Cập nhật key ở Terminal hoặc môi trường server; không gửi key trong chat.",
    "token_limit": "Google từ chối giới hạn token hoặc kích thước ngữ cảnh. Giảm số findings/bằng chứng trong case hoặc kiểm tra budget model.",
    "region_or_billing": "Google từ chối do điều kiện khu vực hoặc billing/project. Kiểm tra quyền truy cập và billing trong tài khoản Google.",
    "invalid_thinking_config": "Google từ chối thinkingConfig. Kiểm tra các tham số suy luận mà model này hỗ trợ.",
    "invalid_content": "Google từ chối cấu trúc contents hoặc systemInstruction. Kiểm tra định dạng yêu cầu API; nội dung bằng chứng không được hiển thị trong chẩn đoán.",
    "invalid_argument": "Google từ chối yêu cầu nhưng chưa có trường lỗi an toàn để phân loại. Cần chạy chẩn đoán cục bộ với dữ liệu tổng hợp.",
}


def _canonical_field(value):
    if not isinstance(value, str) or len(value) > 512:
        return None
    compact = value.lower().replace("_", "")
    if compact.startswith("generatecontentrequest."):
        compact = compact[len("generatecontentrequest."):]
    for prefix, canonical in _FIELD_ALIASES.items():
        # Ignore user-controlled nested property names; expose only this fixed root.
        if compact == prefix or compact.startswith(prefix + ".") or compact.startswith(prefix + "["):
            return canonical
    return None


def gemini_error_hint(response: httpx.Response) -> dict:
    """Return only {kind, message, fields}, with no reflected provider strings."""
    generic = {"kind": "invalid_argument", "message": _MESSAGES["invalid_argument"], "fields": []}
    if len(response.content) > 65536:
        return generic
    try:
        payload = response.json()
    except (ValueError, TypeError):
        return generic
    if not isinstance(payload, dict) or not isinstance(payload.get("error"), dict):
        return generic
    error = payload["error"]
    details = error.get("details", [])
    if not isinstance(details, list):
        details = []
    fields = set()
    reasons = set()
    for detail in details[:40]:
        if not isinstance(detail, dict):
            continue
        if detail.get("@type") == "type.googleapis.com/google.rpc.ErrorInfo":
            reason = detail.get("reason")
            if isinstance(reason, str) and reason in {"API_KEY_INVALID", "API_KEY_EXPIRED", "API_KEY_SERVICE_BLOCKED", "BILLING_DISABLED"}:
                reasons.add(reason)
        if detail.get("@type") != "type.googleapis.com/google.rpc.BadRequest":
            continue
        violations = detail.get("fieldViolations", [])
        if not isinstance(violations, list):
            continue
        for violation in violations[:50]:
            if isinstance(violation, dict):
                canonical = _canonical_field(violation.get("field"))
                if canonical:
                    fields.add(canonical)
    message = error.get("message", "")
    text = message[:8192].lower() if isinstance(message, str) else ""
    if reasons & {"API_KEY_INVALID", "API_KEY_EXPIRED"} or re.search(r"\bapi[ _-]?key\s+(?:is\s+)?(?:not valid|invalid|expired)\b|\b(?:invalid|expired)\s+api[ _-]?key\b", text):
        kind = "invalid_api_key"
    elif "BILLING_DISABLED" in reasons or re.search(r"(?:billing|region|country|location).{0,70}(?:not supported|unavailable|disabled|required|not available)|(?:not available|not supported).{0,50}(?:region|country|location)", text):
        kind = "region_or_billing"
    elif "generationConfig.temperature" in fields or re.search(r"\btemperature\b.{0,80}(?:not supported|unsupported|must be|should be|range|invalid)|(?:unsupported|invalid).{0,30}\btemperature\b", text):
        kind = "invalid_temperature"
    elif "generationConfig.maxOutputTokens" in fields or re.search(r"too many tokens|token limit|maximum (?:number of )?tokens|(?:input|output|context).{0,50}(?:too long|exceed|limit)|max[_ ]?output[_ ]?tokens", text):
        kind = "token_limit"
    elif "model" in fields or re.search(r"\bmodel\b.{0,100}(?:not found|not supported|does not support|unsupported|retired|deprecated|invalid)|generatecontent.{0,80}(?:not supported|unsupported)|(?:not supported|does not support|unsupported).{0,80}generatecontent", text):
        kind = "invalid_model"
    elif fields & {"generationConfig.responseJsonSchema", "generationConfig.responseSchema", "generationConfig.responseMimeType"} or re.search(r"response[_ ]?json[_ ]?schema|response[_ ]?schema|response[_ ]?mime[_ ]?type|json schema|\$defs|\$ref|additionalproperties", text):
        kind = "invalid_schema"
    elif "generationConfig.thinkingConfig" in fields or re.search(r"thinking[_ ]?config.{0,80}(?:unsupported|invalid|not supported)", text):
        kind = "invalid_thinking_config"
    elif fields & {"contents", "systemInstruction"}:
        kind = "invalid_content"
    else:
        kind = "invalid_argument"
    return {"kind": kind, "message": _MESSAGES[kind], "fields": sorted(fields)}
