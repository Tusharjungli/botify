"""Small dependency smoke check for Botify."""

from src.botify.config import BotConfig
from src.botify.engine import GridEngine
from src.botify.market import DeterministicPriceFeed

engine = GridEngine(BotConfig())
feed = DeterministicPriceFeed()
for _ in range(30):
    engine.on_price(feed.latest_price())

snapshot = engine.snapshot()
print("Botify smoke check passed")
print(f"Symbol: {snapshot['config']['symbol']}")
print(f"Ticks: {snapshot['tick_count']}")
print(f"Mode: {snapshot['mode']}")
