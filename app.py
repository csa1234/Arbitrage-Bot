from binance.client import Client
from flask import Flask, render_template
from flask_socketio import SocketIO
import math
import os
import time

TAKER_FEE_RATE = 0.0005
START_ASSET = 'USDT'
MAX_PATH_LENGTH = 5
MIN_PROFIT_PERCENT = -5.0
MAX_CYCLES = 200
TOP_USDT_PAIRS_LIMIT = 0
USE_DEPTH_FOR_SLIPPAGE = False
ORDERBOOK_DEPTH_LIMIT = 5
SIM_BASE_TRADE_SIZE = 1.0
SIM_QUOTE_TRADE_SIZE_IN_QUOTE = 100.0
SYMBOL_METADATA_TTL_SECONDS = 300


def load_env_from_file(path=".env"):
    try:
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                if key and value and key not in os.environ:
                    os.environ[key] = value
    except Exception as exc:
        print(f"Error loading env file {path}: {exc}")


load_env_from_file()

API_KEY = os.getenv("BINANCE_API_KEY", "YOUR_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET", "YOUR_API_SECRET")

client = Client(API_KEY, API_SECRET)
app = Flask(__name__)
socketio = SocketIO(app)

ARBITRAGE_DATA = {}


def build_symbol_metadata():
    try:
        exchange_info = client.get_exchange_info()
        symbols = exchange_info['symbols']
        metadata = {}
        for symbol in symbols:
            if symbol.get('status') != 'TRADING':
                continue
            name = symbol.get('symbol')
            base = symbol.get('baseAsset')
            quote = symbol.get('quoteAsset')
            if not name or not base or not quote:
                continue
            metadata[name] = (base, quote)
        return metadata
    except Exception as e:
        print(f"Error fetching exchange info: {e}")
        return {}


def get_top_usdt_bases(symbol_metadata, limit_count):
    if not limit_count or limit_count <= 0:
        return None
    try:
        tickers_24h = client.get_ticker()
    except Exception as e:
        print(f"Error fetching 24h tickers: {e}")
        return None
    usdt_tickers = []
    for ticker in tickers_24h:
        symbol = ticker.get('symbol')
        if not symbol or symbol not in symbol_metadata:
            continue
        if not symbol.endswith(START_ASSET):
            continue
        quote_volume = float(ticker.get('quoteVolume', 0) or 0)
        if quote_volume <= 0:
            continue
        usdt_tickers.append((symbol, quote_volume))
    usdt_tickers.sort(key=lambda item: item[1], reverse=True)
    usdt_tickers = usdt_tickers[:limit_count]
    bases = set()
    for symbol, _ in usdt_tickers:
        base, _ = symbol_metadata.get(symbol, (None, None))
        if base:
            bases.add(base)
    if not bases:
        return None
    return bases


def simulate_sell_base_for_quote(bids, fee_rate):
    remaining = SIM_BASE_TRADE_SIZE
    if remaining <= 0:
        return None
    total_quote = 0.0
    for price_str, qty_str in bids:
        price = float(price_str)
        qty = float(qty_str)
        if qty >= remaining:
            total_quote += remaining * price
            remaining = 0.0
            break
        total_quote += qty * price
        remaining -= qty
    if remaining > 0:
        return None
    avg_price = total_quote / SIM_BASE_TRADE_SIZE
    return avg_price * (1 - fee_rate)


def simulate_buy_base_with_quote(asks, fee_rate):
    remaining_quote = SIM_QUOTE_TRADE_SIZE_IN_QUOTE
    if remaining_quote <= 0:
        return None
    total_base = 0.0
    for price_str, qty_str in asks:
        price = float(price_str)
        qty = float(qty_str)
        cost = price * qty
        if cost >= remaining_quote:
            base_bought = remaining_quote / price
            total_base += base_bought
            remaining_quote = 0.0
            break
        total_base += qty
        remaining_quote -= cost
    if remaining_quote > 0 or total_base <= 0:
        return None
    rate_quote_to_base = (total_base / SIM_QUOTE_TRADE_SIZE_IN_QUOTE) * (1 - fee_rate)
    return rate_quote_to_base


def get_rates_from_depth(symbol, fee_rate):
    try:
        depth = client.get_order_book(symbol=symbol, limit=ORDERBOOK_DEPTH_LIMIT)
    except Exception as e:
        print(f"Error fetching order book for {symbol}: {e}")
        return None, None
    bids = depth.get('bids') or []
    asks = depth.get('asks') or []
    if not bids or not asks:
        return None, None
    rate_base_to_quote = simulate_sell_base_for_quote(bids, fee_rate)
    rate_quote_to_base = simulate_buy_base_with_quote(asks, fee_rate)
    return rate_base_to_quote, rate_quote_to_base


def build_market_graph(symbol_metadata, tickers, fee_rate, top_usdt_bases=None):
    graph = {}
    for ticker in tickers:
        symbol = ticker.get('symbol')
        if symbol not in symbol_metadata:
            continue
        base, quote = symbol_metadata[symbol]
        if USE_DEPTH_FOR_SLIPPAGE:
            rate_base_to_quote, rate_quote_to_base = get_rates_from_depth(symbol, fee_rate)
        else:
            bid_price = float(ticker.get('bidPrice', 0) or 0)
            ask_price = float(ticker.get('askPrice', 0) or 0)
            if bid_price <= 0 or ask_price <= 0:
                continue
            rate_base_to_quote = bid_price * (1 - fee_rate)
            rate_quote_to_base = (1.0 / ask_price) * (1 - fee_rate)
        if not rate_base_to_quote or not rate_quote_to_base:
            continue
        if rate_base_to_quote <= 0 or rate_quote_to_base <= 0:
            continue
        if base not in graph:
            graph[base] = {}
        if quote not in graph:
            graph[quote] = {}
        if quote not in graph[base] or graph[base][quote] < rate_base_to_quote:
            graph[base][quote] = rate_base_to_quote
        if base not in graph[quote] or graph[quote][base] < rate_quote_to_base:
            graph[quote][base] = rate_quote_to_base
    return graph


def find_arbitrage_cycles(graph, start_asset, max_path_length, min_profit_percent, max_cycles):
    cycles = []
    path = [start_asset]

    def dfs(current_asset, accumulated_rate, depth, leg_rates):
        if depth >= max_path_length:
            return
        neighbors = graph.get(current_asset, {})
        for neighbor, rate in neighbors.items():
            if neighbor == start_asset and depth >= 1:
                total_rate = accumulated_rate * rate
                profit_percent = (total_rate - 1.0) * 100
                if profit_percent >= min_profit_percent:
                    cycle_path = path + [start_asset]
                    cycle_leg_rates = leg_rates + [rate]
                    cycles.append(
                        {
                            'path': cycle_path,
                            'profit_percent': profit_percent,
                            'total_return': total_rate,
                            'leg_rates': cycle_leg_rates,
                        }
                    )
                continue
            if neighbor in path:
                continue
            path.append(neighbor)
            dfs(neighbor, accumulated_rate * rate, depth + 1, leg_rates + [rate])
            path.pop()

    dfs(start_asset, 1.0, 0, [])
    cycles.sort(key=lambda c: c['profit_percent'], reverse=True)
    return cycles[:max_cycles]


def calculate_arbitrage():
    symbol_metadata = build_symbol_metadata()
    top_usdt_bases = get_top_usdt_bases(symbol_metadata, TOP_USDT_PAIRS_LIMIT)
    last_symbol_refresh = time.time()
    while True:
        try:
            now = time.time()
            if now - last_symbol_refresh >= SYMBOL_METADATA_TTL_SECONDS:
                symbol_metadata = build_symbol_metadata()
                top_usdt_bases = get_top_usdt_bases(symbol_metadata, TOP_USDT_PAIRS_LIMIT)
                last_symbol_refresh = now
            tickers = client.get_orderbook_ticker()
            if not isinstance(tickers, list):
                tickers = [tickers]
            market_graph = build_market_graph(symbol_metadata, tickers, TAKER_FEE_RATE, top_usdt_bases)
            if START_ASSET not in market_graph:
                time.sleep(1)
                continue
            arbitrage_cycles = find_arbitrage_cycles(
                market_graph,
                START_ASSET,
                MAX_PATH_LENGTH,
                MIN_PROFIT_PERCENT,
                MAX_CYCLES,
            )
            ARBITRAGE_DATA.clear()
            for cycle in arbitrage_cycles:
                path_str = " -> ".join(cycle['path'])
                ARBITRAGE_DATA[path_str] = cycle
            print(f"Cycles found: {len(arbitrage_cycles)}")
            socketio.emit('update_arbitrage', ARBITRAGE_DATA)
        except Exception as e:
            print(f"Error calculating arbitrage: {e}")
        time.sleep(1)


@app.route('/')
def index():
    return render_template('index.html')


@socketio.on('connect')
def on_connect():
    socketio.emit('update_arbitrage', ARBITRAGE_DATA)


if __name__ == '__main__':
    socketio.start_background_task(calculate_arbitrage)
    socketio.run(app, debug=True)
