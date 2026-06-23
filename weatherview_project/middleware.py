## @file middleware.py
#  @brief Custom middleware for HTTP response headers not covered by Django's SecurityMiddleware.
#
#  @author Jari Jankkila
#  @date 2026


class PermissionsPolicyMiddleware:
    """Add a Permissions-Policy header to every response.

    Restricts powerful browser features to the same origin only.
    Geolocation is intentionally allowed for self (the "Use my location"
    feature), while camera/microphone and other sensor APIs are disabled.
    """

    POLICY = (
        "geolocation=(self), "
        "camera=(), "
        "microphone=(), "
        "payment=(), "
        "usb=(), "
        "magnetometer=(), "
        "gyroscope=(), "
        "accelerometer=()"
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["Permissions-Policy"] = self.POLICY
        return response
