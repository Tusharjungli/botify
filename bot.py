from binance.client import Client
import os
from dotenv import load_dotenv
import time
import pandas as pd
from datetime import datetime

load_dotenv()
client = Client(os.getenv("API_KEY"), os.getenv("API_SECRET"))

symbol = "BTCUSDT"
grid_count = 40

fee_rate = 0.002
initial_balance = 1000
balance = initial_balance

MAX_TRADES = 4
cooldown = 10
last_trade_time = 0
last_price = None

stop_loss_pct = 0.02
trailing_pct = 0.002
min_profit_pct = 0.003
trend_exit_pct = 0.004   # 🔥 increased

# CAPITAL
base_risk = 0.04
max_risk = 0.08

# DAILY CONTROL
daily_start_balance = balance
daily_target_pct = 0.02
trading_enabled = True
current_day = datetime.now().day

wins = 0
losses = 0

grid_update_interval = 60
last_grid_update = 0
grids = []

long_positions = {}
short_positions = {}
filled_long = set()

closed_trades = 0
total_pnl = 0

print("Bot started...")

while True:
    try:
        # ===== DAILY RESET =====
        if datetime.now().day != current_day:
            current_day = datetime.now().day
            daily_start_balance = balance
            trading_enabled = True
            print("🔄 New Day Reset")

        # ===== DAILY LOCK =====
        daily_profit = (balance - daily_start_balance) / daily_start_balance
        if daily_profit >= daily_target_pct:
            trading_enabled = False
            print("🛑 Daily target reached")

        ticker = client.get_symbol_ticker(symbol=symbol)
        price = float(ticker["price"])

        klines = client.get_klines(symbol=symbol, interval="5m", limit=50)
        closes = [float(k[4]) for k in klines]

        df = pd.DataFrame(closes, columns=["price"])
        df["EMA9"] = df["price"].ewm(span=9).mean()
        df["EMA21"] = df["price"].ewm(span=21).mean()

        ema9 = df.iloc[-1]["EMA9"]
        ema21 = df.iloc[-1]["EMA21"]

        trend = "UP" if ema9 > ema21 else "DOWN"
        strength = abs(ema9 - ema21) / price * 100

        if strength < 0.03:
            trend = "RANGE"

        # ===== GRID =====
        if time.time() - last_grid_update > grid_update_interval or not grids:
            high = max(closes)
            low = min(closes)

            vol = (high - low) / low * 100
            rp = max(2, min(vol, 8))

            lower = price * (1 - rp / 100)
            upper = price * (1 + rp / 100)

            grid_size = (upper - lower) / grid_count
            grids = [lower + i * grid_size for i in range(grid_count + 1)]

            last_grid_update = time.time()
            print(f"🔄 Grid updated: {round(lower)} → {round(upper)}")

        print("\n" + "="*60)
        print(f"📊 Price: {price} | Mode: {trend} | Strength: {strength:.3f}%")

        MAX_TRADES = 5 if trend == "RANGE" else 4
        mid = (grids[0] + grids[-1]) / 2

        # ===== TREND FLIP PROTECTION =====
        if trend == "UP" and short_positions:
            for k in list(short_positions.keys()):
                pos = short_positions[k]
                pnl = (pos["entry"] - price) * (pos["size"]/pos["entry"]) - pos["size"]*fee_rate
                balance += pnl
                total_pnl += pnl
                closed_trades += 1
                wins += 1 if pnl > 0 else 0
                losses += 1 if pnl <= 0 else 0
                del short_positions[k]

        if trend == "DOWN" and long_positions:
            for k in list(long_positions.keys()):
                pos = long_positions[k]
                pnl = (price - pos["entry"]) * (pos["size"]/pos["entry"]) - pos["size"]*fee_rate
                balance += pnl
                total_pnl += pnl
                closed_trades += 1
                wins += 1 if pnl > 0 else 0
                losses += 1 if pnl <= 0 else 0
                del long_positions[k]
                filled_long.discard(k)

        # ===== GRID LOOP =====
        for i in range(len(grids) - 1):
            buy = grids[i]
            sell = grids[i+1]

            score = min(strength * 100, 40)
            score += min(abs(price - ema9) / price * 100 * 50, 30)
            score += (1 - i/grid_count) * 30

            if score < 20 or not trading_enabled:
                continue

            growth = balance / initial_balance
            risk = min(base_risk * growth, max_risk)
            size = balance * risk * (1 + score/100)

            # ===== LONG ENTRY (FIXED) =====
            if (
                last_price
                and price <= buy
                and abs(price - ema9)/price < 0.01
                and buy not in filled_long
                and len(long_positions) < MAX_TRADES
                and time.time() - last_trade_time > cooldown
                and (trend == "UP" or (trend == "RANGE" and buy < mid))
            ):
                long_positions[buy] = {"entry": buy, "size": size, "peak": price}
                filled_long.add(buy)
                last_trade_time = time.time()
                print(f"🟢 LONG {round(buy)}")

            # ===== SHORT ENTRY =====
            if (
                last_price
                and price >= sell
                and abs(price - ema9)/price < 0.01
                and sell not in short_positions
                and len(short_positions) < MAX_TRADES
                and time.time() - last_trade_time > cooldown
                and (trend == "DOWN" or (trend == "RANGE" and sell > mid))
            ):
                short_positions[sell] = {"entry": sell, "size": size, "bottom": price}
                last_trade_time = time.time()
                print(f"🔴 SHORT {round(sell)}")

            # ===== LONG EXIT (FIXED) =====
            if buy in long_positions:
                pos = long_positions[buy]
                pos["peak"] = max(pos["peak"], price)
                profit = (price - pos["entry"]) / pos["entry"]

                exit_trade = False

                if trend == "UP" and profit > 0.002:
                    exit_trade = True
                elif profit >= min_profit_pct:
                    exit_trade = True
                elif profit > 0 and price < pos["peak"] * (1 - trailing_pct):
                    exit_trade = True
                elif price <= pos["entry"] * (1 - stop_loss_pct):
                    exit_trade = True

                if exit_trade:
                    pnl = (price - pos["entry"]) * (pos["size"]/pos["entry"]) - pos["size"]*fee_rate
                    balance += pnl
                    total_pnl += pnl
                    closed_trades += 1

                    if pnl > 0:
                        wins += 1
                    else:
                        losses += 1

                    print(f"💰 LONG CLOSED | {pnl:.2f}")

                    del long_positions[buy]
                    filled_long.remove(buy)

        # ===== DASHBOARD =====
        unreal = 0

        print("\n📈 LONG:")
        for e,p in long_positions.items():
            pnl = (price - e)*(p["size"]/e)
            unreal += pnl
            print(f"L {round(e)} | {pnl:.2f}")

        print("\n📉 SHORT:")
        for e,p in short_positions.items():
            pnl = (e - price)*(p["size"]/e)
            unreal += pnl
            print(f"S {round(e)} | {pnl:.2f}")

        total_trades = wins + losses
        win_rate = (wins/total_trades*100) if total_trades else 0

        print("\n📊 SUMMARY:")
        print(f"Closed: {closed_trades}")
        print(f"Balance: {balance:.2f}")
        print(f"Realized: {total_pnl:.2f}")
        print(f"Unrealized: {unreal:.2f}")
        print(f"Win Rate: {win_rate:.2f}%")
        print(f"Daily Profit: {daily_profit*100:.2f}%")

        print("="*60)

        last_price = price
        time.sleep(5)

    except Exception as e:
        print("Error:", e)
        time.sleep(5)