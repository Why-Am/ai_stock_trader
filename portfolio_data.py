from dataclasses import dataclass


@dataclass
class PortfolioData:
    holdings: dict[str, float]
    total_value: float
    money_available_to_trade: float
