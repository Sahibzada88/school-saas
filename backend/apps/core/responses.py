"""Response envelope helpers.

Every JSON response uses:
  success: {"success": true,  "data": ..., "message": "..."}
  error:   {"success": false, "message": "...", "errors": {...}, "code": "...", "request_id": "..."}
"""
from rest_framework.response import Response


class Envelope(dict):
    """Marker type: a payload that is already wrapped. The renderer will not wrap it again."""


def success_response(data=None, message: str = "Operation completed successfully", status: int = 200) -> Response:
    return Response(Envelope(success=True, data=data, message=message), status=status)


def error_envelope(message: str, *, errors=None, code: str | None = None, request_id: str | None = None) -> Envelope:
    payload = Envelope(success=False, message=message, errors=errors if errors is not None else {})
    if code:
        payload["code"] = code
    if request_id:
        payload["request_id"] = request_id
    return payload
