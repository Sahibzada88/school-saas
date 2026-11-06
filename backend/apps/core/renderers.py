from rest_framework.renderers import JSONRenderer

from .responses import Envelope, error_envelope


class EnvelopeJSONRenderer(JSONRenderer):
    """JSON renderer that guarantees the standard envelope on every response."""

    def render(self, data, accepted_media_type=None, renderer_context=None):
        response = (renderer_context or {}).get("response")
        status_code = getattr(response, "status_code", 200)

        if status_code == 204:
            return b""

        if not isinstance(data, Envelope):
            if status_code >= 400:
                data = error_envelope("Request failed.", errors=data if data is not None else {})
            else:
                data = Envelope(success=True, data=data, message="")

        return super().render(data, accepted_media_type, renderer_context)
