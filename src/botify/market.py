"""Market data providers for Botify."""

from __future__ import annotations

import json
import math
import random
import time
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


class PriceFeed(Protocol):
    """Protocol for anything that can provide a BTCUSDT price."""

    def latest_price(self) -> float:
        """Return the latest BTCUSDT price."""


@dataclass
class BinancePublicPriceFeed:
    """Public Binance ticker feed that does not require API keys."""

    symbol: str = "BTCUSDT"
    timeout_seconds: float = 3.0
    endpoint: str = "https://api.binance.com/api/v3/ticker/price"

    def latest_price(self) -> float:
        query = urlencode({"symbol": self.symbol})
        with urlopen(f"{self.endpoint}?{query}", timeout=self.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return float(payload["price"])


@dataclass
class DeterministicPriceFeed:
    """Repeatable synthetic BTC price feed for offline testing."""

    start_price: float = 100_000.0
    tick: int = 0

    def latest_price(self) -> float:
        self.tick += 1
        wave = math.sin(self.tick / 5) * 180 + math.sin(self.tick / 17) * 420
        drift = math.sin(self.tick / 101) * 700
        return max(1_000.0, self.start_price + wave + drift)


@dataclass
class HybridPriceFeed:
    """Use Binance public data first, then safe local simulation if unavailable."""

    live_feed: PriceFeed
    fallback_feed: PriceFeed
    last_live_success: float | None = None
    using_fallback: bool = False

    def latest_price(self) -> float:
        try:
            price = self.live_feed.latest_price()
            self.last_live_success = time.time()
            self.using_fallback = False
            return price
        except (HTTPError, URLError, TimeoutError, KeyError, TypeError, ValueError, OSError):
            self.using_fallback = True
            return self.fallback_feed.latest_price()


class RandomWalkPriceFeed:
    """Non-deterministic local feed for manual dashboard demos."""

    def __init__(self, start_price: float = 100_000.0, seed: int | None = None) -> None:
        self.price = start_price
        self.random = random.Random(seed)

    def latest_price(self) -> float:
        move = self.random.gauss(0, 0.0018)
        self.price = max(1_000.0, self.price * (1 + move))
        return self.price
