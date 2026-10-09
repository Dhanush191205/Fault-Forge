"""Safe application errors independent of HTTP and provider implementations."""


class DomainError(Exception):
    """Carry a public code/message/status without private provider output or stack traces."""

    def __init__(self, code: str, message: str, status: int = 422):
        """Build a handled error from safe constants; no external input is rendered automatically."""
        super().__init__(message)
        self.code, self.message, self.status = code, message, status
