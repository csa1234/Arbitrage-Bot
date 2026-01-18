# Crypto Arbitrage Monitor

**A high-performance, real-time multi-leg arbitrage detection engine for Binance Spot markets.**

This application scans the entire Binance spot market universe for triangular, quadrangular, and pentagonal (5-leg) arbitrage cycles. It visualizes opportunities in real-time using a modern, avant-garde dashboard.

## 🚀 Key Features

*   **Multi-Leg Cycle Detection**: Identifies complex arbitrage paths (up to 5 hops) starting and ending in USDT.
*   **Real-Time Visualization**: WebSocket-powered dashboard updates instantly as opportunities are found.
*   **Fee & Slippage Awareness**:
    *   Calculates net profit after exchange fees (default 0.05% taker fee).
    *   *Optional*: Simulates order book slippage for realistic profitability estimation.
*   **Full Market Coverage**: Scans all available `TRADING` pairs on Binance Spot.
*   **Avant-Garde UI**: Designed with a "Zero Fluff" philosophy—dark mode, glassmorphism, and immediate data clarity.

## 🛠️ Architecture

*   **Backend**: Python (Flask + Flask-SocketIO).
    *   Uses Depth-First Search (DFS) to traverse the market graph.
    *   Builds a directed graph where edges represent exchange rates (price * (1 - fee)).
*   **Frontend**: HTML5 + Vanilla JS + CSS3.
    *   Socket.IO client for live data streaming.
    *   Client-side filtering and sorting.

## 📦 Installation

1.  **Clone the repository** (or download source).
2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

## ⚙️ Configuration

### 1. Environment Variables
Create a `.env` file in the root directory to securely store your Binance credentials. This is required for fetching market data.

```env
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here
```

### 2. Tuning the Engine (`app.py`)
You can adjust the scanning logic by modifying constants at the top of [app.py](file:///d:/Code/Arbitrage%20Bot/app.py):

| Constant | Default | Description |
| :--- | :--- | :--- |
| `TAKER_FEE_RATE` | `0.0005` | Exchange fee per trade (0.05%). |
| `MIN_PROFIT_PERCENT` | `-5.0` | Minimum profit to track. Set to `0.0` to only see profitable cycles. |
| `MAX_PATH_LENGTH` | `5` | Maximum number of legs in a cycle (e.g., USDT->BTC->ETH->BNB->USDT). |
| `TOP_USDT_PAIRS_LIMIT` | `0` | Set to `0` to scan **ALL** pairs. Set to `50` to limit to top volume pairs. |
| `USE_DEPTH_FOR_SLIPPAGE` | `False` | Set to `True` to simulate execution against order book depth (slower but more accurate). |

## 🏃 Usage

1.  **Start the application**:
    ```bash
    python app.py
    ```
2.  **Open the dashboard**:
    Navigate to `http://127.0.0.1:5000` in your browser.
3.  **Monitor**:
    *   The dashboard will automatically connect and stream opportunities.
    *   Use the **Min Profit Filter** input to hide low-yield cycles.
    *   Click **"Best Cycle"** to highlight the top opportunity.
    *   Click any row to see the detailed breakdown of each leg.

## ⚠️ Disclaimer

**Educational Purpose Only.**
This software is a monitoring tool. It does not execute trades automatically. Cryptocurrency trading involves significant risk. The calculated profits are theoretical and depend on market conditions, latency, and execution speed. The authors are not responsible for financial losses.

---
*Engineered with the "Ultrathink" Protocol.*
