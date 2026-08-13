_trades_property = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "action": {"enum": ["buy", "sell"], "description": "Type of trade to make"},
            "ticker": {
                "type": "string",
                "description": "Ticker of the stock to take action on",
            },
            "amount": {"type": "number", "description": "Amount of shares to buy/sell"},
        },
    },
}

_explanation_property = {
    "type": "string",
    "description": "Explanation of the trades made",
}

json_schema = {
    "type": "json_schema",
    "json_schema": {
        "name": "trades",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "trades": _trades_property,
                "explanation": _explanation_property,
            },
            "required": ["trades", "explanation"],
            "additionalProperties": False,
        },
    },
}
