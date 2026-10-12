from core.api.responses import ApiErrorResponse

JSON_CONTENT_TYPE = "application/json"


class APIContentTypeMiddleware:
    """
    Reject API writes whose Content-Type isn't application/json.

    The API only accepts JSON writes. This also protects local-only mode,
    where there's no API key: the API views are @csrf_exempt, so any website
    the operator visits could otherwise send a write request to this server.
    Browsers won't send a cross-origin request with a JSON Content-Type
    without a CORS preflight, which this server never approves, so requiring
    one on writes blocks those requests.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.path.startswith("/api/")
            and request.method in ("POST", "PUT")
            and request.content_type.lower() != JSON_CONTENT_TYPE
        ):
            return ApiErrorResponse(
                status_code=415,
                message="Unsupported Media Type",
                details=f"Please send a Content-Type header of {JSON_CONTENT_TYPE}",
            )
        return self.get_response(request)
