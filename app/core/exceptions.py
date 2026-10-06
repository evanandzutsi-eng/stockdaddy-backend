"""
Centralized custom exception classes for the NGX Intelligence Terminal.
These are caught by the generic exception handler in main.py and 
translated into safe, masked HTTP responses in production.
"""


class NGXBaseException(Exception):
    """Base exception for all domain-specific errors."""
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class InsufficientFundsError(NGXBaseException):
    """Raised when a BUY order exceeds the virtual cash balance."""
    def __init__(self, message: str = "Insufficient virtual funds."):
        super().__init__(message=message, status_code=400)


class InsufficientHoldingsError(NGXBaseException):
    """Raised when a SELL order exceeds the current holding quantity."""
    def __init__(self, message: str = "Insufficient holdings."):
        super().__init__(message=message, status_code=400)


class StockPriceUnavailableError(NGXBaseException):
    """Raised when no market data is available for the requested symbol."""
    def __init__(self, message: str = "Market data unavailable for this symbol."):
        super().__init__(message=message, status_code=422)


class VerificationGateError(NGXBaseException):
    """Raised when a user attempts an action blocked by the Verification Gate."""
    def __init__(self, message: str = "Verification requirements not met."):
        super().__init__(message=message, status_code=403)


class ScamContentDetectedError(NGXBaseException):
    """Raised when Tier 1 regex scrubbing detects prohibited content."""
    def __init__(self, message: str = "Content contains prohibited links or phrases."):
        super().__init__(message=message, status_code=400)