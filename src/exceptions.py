class APIKeyNotFoundError(Exception):
    """Raised when an API key cannot be found"""


class StockPortfolioError(Exception):
    """Raised when an error is encountered with the stock portfolio"""


class ToolCallError(Exception):
    """Raised when an error is encountered with tool calls"""


class EmptySaveError(Exception):
    """Raised when the program tries to load an empty save"""


class SaveCancelError(Exception):
    """Raised when a save is cancelled"""
