import ccxt
import time
import requests
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# 1. Render Web Service Port Listener (Never Sleeps)
class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is active 24/7 on Render")

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), DummyServer)
    server.serve_forever()

threading.Thread(target=run_server, daemon=True).start()

# 2. Delta Exchange & Telegram Setup
API_KEY = os.getenv("DELTA_API_KEY")
API_SECRET = os.getenv("DELTA_API_SECRET")
TG_TOKEN = os.getenv("TG_TOKEN")
CHAT_ID = os.getenv("TG_CHAT_ID")

def notify(msg):
    if TG_TOKEN and CHAT_ID:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        try:
            requests.post(url, json={"chat_id": CHAT_ID, "text": msg}, timeout=10)
        except Exception:
            pass

exchange = ccxt.delta({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'enableRateLimit': True,
})
exchange.set_sandbox_mode(True)

notify("🚀 Institutional Top/Bottom Compounder Bot Live on Delta Demo!")

PAIRS = ['BTC/USD:USD', 'ETH/USD:USD', 'SOL/USD:USD']

def scan_asset(symbol):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe='15m', limit=50)
    c_trigger = ohlcv[-2]
    c_prev1 = ohlcv[-3]
    
    range_high = max([x[2] for x in ohlcv[-25:-3]])
    range_low = min([x[3] for x in ohlcv[-25:-3]])
    avg_vol = sum([x[5] for x in ohlcv[-15:-3]]) / 12
    has_vol_trap = c_trigger[5] > (avg_vol * 1.3)
    
    # Bearish SFP (Exact Top Hunt)
    is_sfp_short = c_trigger[2] > range_high and c_trigger[4] < range_high
    wick_short = c_trigger[2] - max(c_trigger[1], c_trigger[4])
    body_short = abs(c_trigger[4] - c_trigger[1])
    is_choch_short = c_trigger[4] < c_prev1[3]

    if is_sfp_short and (wick_short > body_short * 1.2) and is_choch_short and has_vol_trap:
        entry = c_trigger[4]
        sl = c_trigger[2] + (entry * 0.001)
        risk = sl - entry
        tp1 = entry - (risk * 3)
        tp2 = entry - (risk * 5)
        
        msg = (f"🔴 SHORT TRAP CONFIRMED\n"
               f"Coin: {symbol}\n"
               f"Sweep: {range_high}\n"
               f"Entry: {entry}\n"
               f"SL: {sl}\n"
               f"TP1 (1:3): {tp1}\n"
               f"TP2 (1:5): {tp2}")
        notify(msg)
        try:
            exchange.create_order(symbol, 'market', 'sell', 1)
        except Exception as e:
            print(f"Order Error: {e}")

    # Bullish SFP (Exact Bottom Hunt)
    is_sfp_long = c_trigger[3] < range_low and c_trigger[4] > range_low
    wick_long = min(c_trigger[1], c_trigger[4]) - c_trigger[3]
    body_long = abs(c_trigger[4] - c_trigger[1])
    is_choch_long = c_trigger[4] > c_prev1[2]

    if is_sfp_long and (wick_long > body_long * 1.2) and is_choch_long and has_vol_trap:
        entry = c_trigger[4]
        sl = c_trigger[3] - (entry * 0.001)
        risk = entry - sl
        tp1 = entry + (risk * 3)
        tp2 = entry + (risk * 5)
        
        msg = (f"🟢 LONG TRAP CONFIRMED\n"
               f"Coin: {symbol}\n"
               f"Sweep: {range_low}\n"
               f"Entry: {entry}\n"
               f"SL: {sl}\n"
               f"TP1 (1:3): {tp1}\n"
               f"TP2 (1:5): {tp2}")
        notify(msg)
        try:
            exchange.create_order(symbol, 'market', 'buy', 1)
        except Exception as e:
            print(f"Order Error: {e}")

while True:
    for coin in PAIRS:
        try:
            scan_asset(coin)
        except Exception as err:
            print(f"Error {coin}: {err}")
    time.sleep(300)
