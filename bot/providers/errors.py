"""Provider error classification (retry loop — ТЗ-12)."""


class ProviderError(Exception):
    """Base provider failure."""

    def __init__(self, message: str, *, retryable: bool = False, status_code: int | None = None):
        self.retryable = retryable
        self.status_code = status_code
        super().__init__(message)


class ProviderRetryableError(ProviderError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message, retryable=True, status_code=status_code)


class ProviderFatalError(ProviderError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message, retryable=False, status_code=status_code)
