"""Simple request/response timing middleware."""
import time


class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started_at = time.perf_counter()
        response = self.get_response(request)
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        # Required fields are printed for every completed request.
        print(
            f"{request.method} {request.path} "
            f"status={response.status_code} duration_ms={elapsed_ms:.2f}"
        )
        return response
