class APIKeyNotFoundError(Exception):
    """Raised when an API key cannot be found"""


class StockPortfolioError(Exception):
    """Raised when an error is encountered with the stock portfolio"""


class ToolCallError(Exception):
    """Raised when an error is encountered with tool calls"""
