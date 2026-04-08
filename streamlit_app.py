import streamlit as st
import pandas as pd
import requests
import os
import json
import time
import google.generativeai as genai
from datetime import datetime

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="QuantTrader Lite",
    page_icon="📈",
    layout="wide",
)

# ── Constants ─────────────────────────────────────────────────────────────────
TRADE_LOG = "trade_log.json"

COINS = {
    "Bitcoin (BTC)":   {"cg": "bitcoin",     "binance": "BTCUSDT",  "cc": "BTC"},
    "Ethereum (ETH)":  {"cg": "ethereum",    "binance": "ETHUSDT",  "cc": "ETH"},
    "Solana (SOL)":    {"cg": "solana",      "binance": "SOLUSDT",  "cc": "SOL"},
    "BNB":             {"cg": "binancecoin", "binance": "BNBUSDT",  "cc": "BNB"},
}

# ── Gemini Setup ──────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyDrbJNjYgmayCayE-zyEMVUXuYs4kRg4bc")
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel("gemini-2.0-flash")


# ── Price Fetching (3 fallback sources) ───────────────────────────────────────
def fetch_coingecko(cg_id):
    """CoinGecko free API — primary source."""
    headers = {"User-Agent": "QuantTraderLite/1.0"}
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {"ids": cg_id, "vs_currencies": "usd", "include_24hr_change": "true"}
    r = requests.get(url, params=params, headers=headers, timeout=10)
    r.raise_for_status()
    data = r.json()
    return data[cg_id]["usd"], data[cg_id]["usd_24h_change"]


def fetch_binance(symbol):
    """Binance public API — no key needed."""
    url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    d = r.json()
    price  = float(d["lastPrice"])
    change = float(d["priceChangePercent"])
    return price, change


def fetch_cryptocompare(cc_symbol):
    """CryptoCompare free API — final fallback."""
    url = "https://min-api.cryptocompare.com/data/pricemultifull"
    params = {"fsyms": cc_symbol, "tsyms": "USD"}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()["RAW"][cc_symbol]["USD"]
    return data["PRICE"], data["CHANGEPCT24HOUR"]


def get_price(coin_label):
    """Try CoinGecko → Binance → CryptoCompare, return (price, change, source)."""
    ids = COINS[coin_label]
    errors = []

    try:
        p, c = fetch_coingecko(ids["cg"])
        return p, c, "CoinGecko"
    except Exception as e:
        errors.append(f"CoinGecko: {e}")

    try:
        p, c = fetch_binance(ids["binance"])
        return p, c, "Binance"
    except Exception as e:
        errors.append(f"Binance: {e}")

    try:
        p, c = fetch_cryptocompare(ids["cc"])
        return p, c, "CryptoCompare"
    except Exception as e:
        errors.append(f"CryptoCompare: {e}")

    raise RuntimeError("All price sources failed:\n" + "\n".join(errors))


# ── Trend Analysis from History ───────────────────────────────────────────────
def compute_trend(logs, coin_id):
    """Compute trend, avg price, volatility from trade log."""
    coin_logs = [l for l in logs if l.get("coin") == coin_id]
    if len(coin_logs) < 2:
        return None
    prices = [l["price"] for l in coin_logs[-10:]]
    avg    = sum(prices) / len(prices)
    latest = prices[-1]
    oldest = prices[0]
    trend  = "UPTREND" if latest > oldest else "DOWNTREND" if latest < oldest else "SIDEWAYS"
    pct    = ((latest - oldest) / oldest) * 100
    high   = max(prices)
    low    = min(prices)
    return {
        "trend":      trend,
        "pct_move":   round(pct, 2),
        "avg_price":  round(avg, 2),
        "high":       high,
        "low":        low,
        "n_points":   len(prices),
    }


# ── Gemini AI with Trend Context ──────────────────────────────────────────────
def ask_gemini(coin_label, price, change_24h, trend_data=None):
    trend_block = ""
    if trend_data:
        trend_block = (
            f"\nRecent session trend ({trend_data['n_points']} data points):\n"
            f"  Direction: {trend_data['trend']}\n"
            f"  Move: {trend_data['pct_move']:+.2f}%\n"
            f"  Session High: ${trend_data['high']:,.2f}\n"
            f"  Session Low:  ${trend_data['low']:,.2f}\n"
            f"  Avg Price:    ${trend_data['avg_price']:,.2f}\n"
        )

    prompt = (
        f"You are a conservative crypto trading signal agent.\n"
        f"Analyze the following market data and give a trading signal.\n\n"
        f"Coin: {coin_label}\n"
        f"Current Price: ${price:,.2f}\n"
        f"24h Change: {change_24h:.2f}%\n"
        f"{trend_block}\n"
        f"Rules:\n"
        f"- BUY only if trend is clearly bullish and 24h change > +1%\n"
        f"- SELL only if trend is clearly bearish and 24h change < -1%\n"
        f"- HOLD in all uncertain or sideways conditions\n"
        f"- Never risk more than 2% of portfolio per trade\n\n"
        f"Reply in EXACTLY this format (no extra text):\n"
        f"SIGNAL: [BUY/SELL/HOLD] | RISK: [LOW/MEDIUM/HIGH] | REASON: [one concise sentence]"
    )
    response = gemini_model.generate_content(prompt)
    return response.text.strip()


# ── Trade Execution (Kraken CLI sandbox) ──────────────────────────────────────
def execute_trade(signal, coin_label):
    amounts = {
        "Bitcoin (BTC)":  "0.001",
        "Ethereum (ETH)": "0.01",
        "Solana (SOL)":   "0.5",
        "BNB":            "0.05",
    }
    pairs = {
        "Bitcoin (BTC)":  "XBTUSD",
        "Ethereum (ETH)": "ETHUSD",
        "Solana (SOL)":   "SOLUSD",
        "BNB":            "BNBUSD",
    }
    amount = amounts.get(coin_label, "0.01")
    pair   = pairs.get(coin_label, "XBTUSD")

    if "BUY" in signal:
        # Uncomment for real Kraken CLI:
        # import subprocess
        # r = subprocess.run(["kraken","order","buy",pair,amount,"--sandbox"], capture_output=True, text=True)
        # return r.stdout or f"BUY {amount} {pair} sent (sandbox)"
        return f"[SANDBOX] BUY {amount} {pair} — queued via Kraken CLI"
    elif "SELL" in signal:
        # Uncomment for real Kraken CLI:
        # import subprocess
        # r = subprocess.run(["kraken","order","sell",pair,amount,"--sandbox"], capture_output=True, text=True)
        # return r.stdout or f"SELL {amount} {pair} sent (sandbox)"
        return f"[SANDBOX] SELL {amount} {pair} — queued via Kraken CLI"
    return "HOLD — no trade executed"


# ── Log Helpers ───────────────────────────────────────────────────────────────
def log_trade(coin_label, coin_id, price, change, signal, trade_result, source):
    entry = {
        "timestamp":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "coin":       coin_id,
        "coin_label": coin_label,
        "price":      price,
        "change_24h": round(change, 2),
        "signal":     signal,
        "trade":      trade_result,
        "source":     source,
    }
    with open(TRADE_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def load_logs():
    if not os.path.exists(TRADE_LOG):
        return []
    with open(TRADE_LOG) as f:
        return [json.loads(line) for line in f if line.strip()]


def parse_signal(raw):
    for word in ["BUY", "SELL", "HOLD"]:
        if word in raw:
            return word
    return "HOLD"


def signal_icon(sig):
    return {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}.get(sig, "⚪")


def trend_icon(t):
    return {"UPTREND": "📈", "DOWNTREND": "📉", "SIDEWAYS": "➡️"}.get(t, "")


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Agent Settings")
    coin_label   = st.selectbox("Coin", list(COINS.keys()))
    coin_id      = COINS[coin_label]["cg"]
    auto_refresh = st.toggle("🔄 Auto-refresh every 60s", value=False)
    st.divider()
    st.markdown("**Tech Stack**")
    st.markdown(
        "- 🤖 AI: Gemini 2.0 Flash\n"
        "- 📡 Data: CoinGecko → Binance → CryptoCompare\n"
        "- ⚙️ Execution: Kraken CLI (sandbox)\n"
        "- 🖥️ UI: Streamlit"
    )
    st.divider()
    if st.button("🗑️ Clear Trade Log", use_container_width=True):
        if os.path.exists(TRADE_LOG):
            os.remove(TRADE_LOG)
        st.rerun()


# ── Header ────────────────────────────────────────────────────────────────────
st.title("📈 QuantTrader Lite")
st.caption(
    "AI Trading Signal Agent · Gemini 2.0 Flash + Multi-Source Price Data + "
    "Kraken CLI (sandbox) · Lablab.ai AI Trading Agents Hackathon 2026"
)
st.divider()

# ── Load Logs ─────────────────────────────────────────────────────────────────
logs = load_logs()

# ── Run Agent Button ──────────────────────────────────────────────────────────
col_btn, _ = st.columns([1, 4])
with col_btn:
    run_now = st.button("⚡ Run Agent Now", use_container_width=True, type="primary")

if run_now:
    with st.spinner(f"Fetching {coin_label} price..."):
        try:
            price, change, source = get_price(coin_label)
            st.toast(f"✅ Price fetched from {source}", icon="📡")
        except RuntimeError as e:
            st.error(f"❌ All price sources failed:\n\n{e}")
            st.stop()

    with st.spinner("Analyzing trend and asking Gemini AI..."):
        trend_data   = compute_trend(logs, coin_id)
        signal_raw   = ask_gemini(coin_label, price, change, trend_data)
        trade_result = execute_trade(signal_raw, coin_label)
        entry        = log_trade(coin_label, coin_id, price, change, signal_raw, trade_result, source)
        logs.append(entry)
        sig = parse_signal(signal_raw)
        st.success(
            f"✅ {entry['timestamp']} · {coin_label} · "
            f"{signal_icon(sig)} **{sig}** · Source: {source}"
        )

# ── Dashboard ─────────────────────────────────────────────────────────────────
if logs:
    latest     = logs[-1]
    sig        = parse_signal(latest["signal"])
    icon       = signal_icon(sig)
    trend_data = compute_trend(logs, latest["coin"])

    # ── Metric Cards ──────────────────────────────────────────────────────────
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("💰 Price (USD)",   f"${latest['price']:,.2f}")
    m2.metric("📊 24h Change",    f"{latest['change_24h']:.2f}%",
              delta=f"{latest['change_24h']:.2f}%")
    m3.metric("🤖 Signal",        f"{icon} {sig}")
    m4.metric("📋 Trades Logged", len(logs))
    if trend_data:
        m5.metric(
            f"{trend_icon(trend_data['trend'])} Trend",
            trend_data["trend"],
            delta=f"{trend_data['pct_move']:+.2f}%",
        )
    else:
        m5.metric("📈 Trend", "Need more data")

    st.divider()

    # ── Trend Analysis Panel ──────────────────────────────────────────────────
    if trend_data:
        st.subheader("📊 Trend Analysis")
        t1, t2, t3, t4 = st.columns(4)
        t1.metric("Direction",    f"{trend_icon(trend_data['trend'])} {trend_data['trend']}")
        t2.metric("Session Move", f"{trend_data['pct_move']:+.2f}%")
        t3.metric("Session High", f"${trend_data['high']:,.2f}")
        t4.metric("Session Low",  f"${trend_data['low']:,.2f}")

    # ── AI Reasoning ─────────────────────────────────────────────────────────
    st.subheader("🤖 Gemini AI Reasoning")
    if sig == "BUY":
        st.success(latest["signal"])
    elif sig == "SELL":
        st.error(latest["signal"])
    else:
        st.warning(latest["signal"])

    # ── Price Chart (all coins or filtered) ──────────────────────────────────
    df = pd.DataFrame(logs)
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    st.subheader("📉 Price History — All Coins")
    tab1, tab2, tab3, tab4 = st.tabs(["Bitcoin", "Ethereum", "Solana", "BNB"])
    tab_map = {
        "Bitcoin":  ("bitcoin",    tab1),
        "Ethereum": ("ethereum",   tab2),
        "Solana":   ("solana",     tab3),
        "BNB":      ("binancecoin",tab4),
    }
    for name, (cid, tab) in tab_map.items():
        with tab:
            subset = df[df["coin"] == cid]
            if len(subset) >= 1:
                st.line_chart(subset.set_index("timestamp")["price"], use_container_width=True)
                if len(subset) >= 2:
                    delta_pct = ((subset["price"].iloc[-1] - subset["price"].iloc[0])
                                 / subset["price"].iloc[0] * 100)
                    st.caption(
                        f"Session: ${subset['price'].min():,.2f} low · "
                        f"${subset['price'].max():,.2f} high · "
                        f"{delta_pct:+.2f}% overall"
                    )
            else:
                st.info(f"No data for {name} yet. Select it and run the agent.")

    # ── Signal Distribution ───────────────────────────────────────────────────
    st.subheader("📊 Signal Distribution")
    sig_counts = df["signal"].apply(parse_signal).value_counts()
    col_a, col_b = st.columns([1, 2])
    with col_a:
        for s, count in sig_counts.items():
            pct = round(count / len(df) * 100)
            st.metric(f"{signal_icon(s)} {s}", f"{count}  ({pct}%)")
    with col_b:
        st.bar_chart(sig_counts)

    # ── Trade History Table ───────────────────────────────────────────────────
    st.subheader("📋 Trade History (last 20)")
    disp = df[["timestamp", "coin_label", "price", "change_24h", "signal", "source", "trade"]].tail(20).copy()
    disp["signal"] = disp["signal"].apply(
        lambda x: f"{signal_icon(parse_signal(x))} {parse_signal(x)}"
    )
    disp["price"]      = disp["price"].apply(lambda x: f"${x:,.2f}")
    disp["change_24h"] = disp["change_24h"].apply(lambda x: f"{x:+.2f}%")
    disp.columns       = ["Time", "Coin", "Price", "24h %", "Signal", "Source", "Order"]
    st.dataframe(disp[::-1], use_container_width=True, hide_index=True)

else:
    st.info("No trades logged yet. Click **⚡ Run Agent Now** to start.")

# ── Auto-refresh ──────────────────────────────────────────────────────────────
if auto_refresh:
    st.caption("🔄 Auto-refreshing in 60 seconds...")
    time.sleep(60)
    st.rerun()