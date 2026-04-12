import streamlit as st
import pandas as pd
import requests
import os
import json
import time
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
    "Bitcoin (BTC)":   {"cg": "bitcoin",     "binance": "BTCUSDT",  "cc": "BTC", "cmc": "1"},
    "Ethereum (ETH)":  {"cg": "ethereum",    "binance": "ETHUSDT",  "cc": "ETH", "cmc": "1027"},
    "Solana (SOL)":    {"cg": "solana",      "binance": "SOLUSDT",  "cc": "SOL", "cmc": "5426"},
    "BNB":             {"cg": "binancecoin", "binance": "BNBUSDT",  "cc": "BNB", "cmc": "1839"},
}

AI_PROVIDERS = ["Groq", "Cerebras", "Cohere", "Mistral"]

# ── Secrets Helper ────────────────────────────────────────────────────────────
def _get_secret(key):
    try:
        return st.secrets[key]
    except Exception:
        return None

GROQ_API_KEY          = _get_secret("GROQ_API_KEY")          or os.environ.get("GROQ_API_KEY", "")
CEREBRAS_API_KEY      = _get_secret("CEREBRAS_API_KEY")      or os.environ.get("CEREBRAS_API_KEY", "")
COHERE_API_KEY        = _get_secret("COHERE_API_KEY")        or os.environ.get("COHERE_API_KEY", "")
MISTRAL_API_KEY       = _get_secret("MISTRAL_API_KEY")       or os.environ.get("MISTRAL_API_KEY", "")
COINMARKETCAP_API_KEY = _get_secret("COINMARKETCAP_API_KEY") or os.environ.get("COINMARKETCAP_API_KEY", "")
CRYPTOCOMPARE_API_KEY = _get_secret("CRYPTOCOMPARE_API_KEY") or os.environ.get("CRYPTOCOMPARE_API_KEY", "")

# ── Session State ─────────────────────────────────────────────────────────────
if "view" not in st.session_state:
    st.session_state.view = "landing"

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
:root {
  --green:#1D9E75; --green-dark:#0F6E56;
  --red:#D85A30; --amber:#EF9F27;
  --bg:#0b0f0e; --surface:#111815; --card:#161d1a;
  --border:rgba(29,158,117,0.22); --border2:rgba(255,255,255,0.07);
  --text:#e8f0ec; --muted:#7a9e8e;
}
html,body,[data-testid="stAppViewContainer"],[data-testid="stApp"] {
  background:var(--bg) !important; color:var(--text) !important;
  font-family:'Space Grotesk',sans-serif !important;
}
[data-testid="stHeader"] { background:transparent !important; }
[data-testid="stSidebar"] { background:var(--surface) !important; border-right:1px solid var(--border2) !important; }
[data-testid="stSidebar"] * { color:var(--text) !important; }
.block-container { padding-top:1rem !important; padding-bottom:2rem !important; }
.stButton > button {
  background:var(--green) !important; color:white !important;
  border:none !important; border-radius:10px !important;
  font-family:'Space Grotesk',sans-serif !important;
  font-weight:600 !important; font-size:15px !important;
  padding:12px 24px !important; transition:all 0.15s !important;
}
.stButton > button:hover { background:var(--green-dark) !important; }
[data-testid="metric-container"] {
  background:var(--card) !important; border:1px solid var(--border2) !important;
  border-radius:10px !important; padding:14px 16px !important;
}
[data-testid="stMetricLabel"] { color:var(--muted) !important; font-size:11px !important; font-family:'JetBrains Mono',monospace !important; }
[data-testid="stMetricValue"] { color:var(--text) !important; font-size:18px !important; font-weight:600 !important; }
.stTabs [data-baseweb="tab-list"] { background:transparent !important; gap:4px; border-bottom:1px solid var(--border2) !important; }
.stTabs [data-baseweb="tab"] { background:transparent !important; color:var(--muted) !important; border-radius:7px 7px 0 0 !important; font-family:'Space Grotesk',sans-serif !important; font-size:13px !important; padding:8px 18px !important; }
.stTabs [aria-selected="true"] { background:var(--card) !important; color:var(--text) !important; border:1px solid var(--border2) !important; border-bottom:none !important; }
[data-testid="stDataFrame"] { background:var(--card) !important; border-radius:10px !important; border:1px solid var(--border2) !important; }
[data-testid="stSelectbox"] > div > div { background:var(--card) !important; border:1px solid var(--border2) !important; color:var(--text) !important; border-radius:8px !important; }
[data-testid="stToggle"] { accent-color:var(--green) !important; }
hr { border-color:var(--border2) !important; }
[data-testid="stAlert"] { border-radius:10px !important; font-family:'JetBrains Mono',monospace !important; font-size:13px !important; }
[data-testid="stCaptionContainer"] { color:var(--muted) !important; font-family:'JetBrains Mono',monospace !important; font-size:11px !important; }
::-webkit-scrollbar { width:6px; }
::-webkit-scrollbar-track { background:var(--bg); }
::-webkit-scrollbar-thumb { background:var(--border); border-radius:3px; }
</style>
""", unsafe_allow_html=True)


# ── Landing Page ──────────────────────────────────────────────────────────────
LANDING_HTML = """
<style>
body::before {
  content:''; position:fixed; inset:0;
  background-image:linear-gradient(rgba(29,158,117,0.04) 1px,transparent 1px),linear-gradient(90deg,rgba(29,158,117,0.04) 1px,transparent 1px);
  background-size:40px 40px; pointer-events:none; z-index:0;
}
.lp { position:relative; z-index:1; max-width:860px; margin:0 auto; padding:60px 24px 40px; text-align:center; }
.hero-tag { display:inline-flex; align-items:center; gap:6px; font-size:12px; font-family:'JetBrains Mono',monospace; color:#1D9E75; background:rgba(29,158,117,0.1); border:1px solid rgba(29,158,117,0.22); border-radius:20px; padding:5px 14px; margin-bottom:28px; }
.dot-live { width:7px; height:7px; border-radius:50%; background:#1D9E75; display:inline-block; animation:blink 1.8s ease-in-out infinite; }
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.3} }
.lp-h1 { font-size:clamp(32px,5vw,56px); font-weight:700; line-height:1.1; letter-spacing:-0.02em; margin-bottom:18px; color:#e8f0ec; }
.lp-h1 span { color:#1D9E75; }
.lp-sub { font-size:16px; color:#7a9e8e; max-width:540px; margin:0 auto 32px; line-height:1.7; }
.terminal { background:#0a0d0c; border:1px solid rgba(29,158,117,0.22); border-radius:12px; overflow:hidden; max-width:640px; margin:0 auto 48px; text-align:left; }
.tbar { background:#111815; padding:10px 14px; display:flex; align-items:center; gap:6px; border-bottom:1px solid rgba(255,255,255,0.07); }
.tdot { width:11px; height:11px; border-radius:50%; }
.ttitle { font-family:'JetBrains Mono',monospace; font-size:11px; color:#7a9e8e; margin-left:8px; }
.tbody { padding:18px 20px; font-family:'JetBrains Mono',monospace; font-size:12.5px; line-height:1.9; }
.t-dim{color:#4a6b5a}.t-grn{color:#1D9E75}.t-yel{color:#EF9F27}.t-wht{color:#e8f0ec}.t-cmt{color:#3a5a4a}
.cur { display:inline-block; width:8px; height:13px; background:#1D9E75; vertical-align:middle; animation:blink 1s step-end infinite; }
.feats { display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:14px; margin:32px 0; text-align:left; }
.feat { background:#161d1a; border:1px solid rgba(255,255,255,0.07); border-radius:12px; padding:20px; }
.feat-t { font-size:14px; font-weight:600; color:#e8f0ec; margin-bottom:5px; }
.feat-d { font-size:12px; color:#7a9e8e; line-height:1.6; }
.stack { display:flex; gap:8px; flex-wrap:wrap; justify-content:center; margin:28px 0; }
.pill { display:flex; align-items:center; gap:6px; background:#161d1a; border:1px solid rgba(255,255,255,0.07); border-radius:8px; padding:7px 12px; font-size:12px; color:#e8f0ec; font-weight:500; }
.pill span { font-family:'JetBrains Mono',monospace; font-size:10px; color:#7a9e8e; }
.sec-label { font-size:10px; font-family:'JetBrains Mono',monospace; color:#7a9e8e; text-transform:uppercase; letter-spacing:0.1em; margin-bottom:14px; }
</style>
<div class="lp">
  <div class="hero-tag"><span class="dot-live"></span> AI Trading Agent — Live</div>
  <div class="lp-h1">Trade smarter with<br><span>multi-AI signals</span></div>
  <p class="lp-sub">Fetches live crypto prices from CoinMarketCap & CryptoCompare, asks Groq / Cerebras / Cohere / Mistral for BUY / SELL / HOLD signals, and executes paper trades via Kraken CLI.</p>
  <div class="terminal">
    <div class="tbar">
      <div class="tdot" style="background:#E24B4A"></div>
      <div class="tdot" style="background:#EF9F27"></div>
      <div class="tdot" style="background:#639922"></div>
      <span class="ttitle">quanttrader — agent running</span>
    </div>
    <div class="tbody">
      <div><span class="t-dim">$</span> <span class="t-grn">streamlit run streamlit_app.py</span></div>
      <div class="t-dim">──────────────────────────────────────</div>
      <div><span class="t-cmt">[price ]</span> <span class="t-wht">CoinMarketCap → ETH: </span><span class="t-grn">$1,582.40</span> <span class="t-dim">+2.14%</span></div>
      <div><span class="t-cmt">[groq  ]</span> <span class="t-wht">Asking llama-3.3-70b-versatile...</span></div>
      <div><span class="t-cmt">[signal]</span> <span class="t-grn">SIGNAL: BUY</span> <span class="t-dim">| RISK: MEDIUM |</span></div>
      <div><span class="t-dim">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;REASON: Uptrend confirmed, bullish momentum.</span></div>
      <div><span class="t-cmt">[kraken]</span> <span class="t-yel">[SANDBOX] BUY 0.01 ETHUSD — queued</span></div>
      <div class="t-dim">──────────────────────────────────────</div>
      <div><span class="t-dim">$</span> <span class="cur"></span></div>
    </div>
  </div>
  <div class="sec-label">Features</div>
  <div class="feats">
    <div class="feat"><div class="feat-t">🧠 4 AI providers</div><div class="feat-d">Switch between Groq, Cerebras, Cohere, and Mistral in the sidebar — each with their own model.</div></div>
    <div class="feat"><div class="feat-t">📡 Multi-source prices</div><div class="feat-d">CoinMarketCap → CryptoCompare → Binance → CoinGecko fallback chain.</div></div>
    <div class="feat"><div class="feat-t">⚙️ Kraken CLI sandbox</div><div class="feat-d">Paper trades submitted in sandbox mode. Real integration, zero risk.</div></div>
    <div class="feat"><div class="feat-t">📊 Live dashboard</div><div class="feat-d">Price charts, signal distribution, full trade history — auto-refreshing.</div></div>
    <div class="feat"><div class="feat-t">🪙 4 coins</div><div class="feat-d">Bitcoin, Ethereum, Solana, BNB — each with their own chart tab.</div></div>
    <div class="feat"><div class="feat-t">🔄 Auto-refresh</div><div class="feat-d">Toggle 60-second auto-refresh for a fully autonomous agent loop.</div></div>
  </div>
  <div class="sec-label">Tech stack</div>
  <div class="stack">
    <div class="pill">⚡ <strong>Groq</strong> <span>llama-3.3-70b</span></div>
    <div class="pill">🧠 <strong>Cerebras</strong> <span>llama3.1-70b</span></div>
    <div class="pill">🪸 <strong>Cohere</strong> <span>command-r-plus</span></div>
    <div class="pill">✦ <strong>Mistral</strong> <span>mistral-large</span></div>
    <div class="pill">📡 <strong>CoinMarketCap</strong> <span>prices</span></div>
    <div class="pill">🔄 <strong>CryptoCompare</strong> <span>fallback</span></div>
    <div class="pill">⚙️ <strong>Kraken CLI</strong> <span>sandbox</span></div>
    <div class="pill">🖥️ <strong>Streamlit</strong> <span>dashboard</span></div>
  </div>
</div>
"""


# ── Price Fetching ─────────────────────────────────────────────────────────────
def fetch_coinmarketcap(cmc_id):
    if not COINMARKETCAP_API_KEY:
        raise RuntimeError("No CoinMarketCap API key")
    headers = {"X-CMC_PRO_API_KEY": COINMARKETCAP_API_KEY, "Accept": "application/json"}
    r = requests.get(
        "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest",
        params={"id": cmc_id, "convert": "USD"},
        headers=headers, timeout=10,
    )
    r.raise_for_status()
    data = r.json()["data"][cmc_id]["quote"]["USD"]
    return data["price"], data["percent_change_24h"]

def fetch_cryptocompare(cc_symbol):
    headers = {}
    if CRYPTOCOMPARE_API_KEY:
        headers["authorization"] = f"Apikey {CRYPTOCOMPARE_API_KEY}"
    r = requests.get(
        "https://min-api.cryptocompare.com/data/pricemultifull",
        params={"fsyms": cc_symbol, "tsyms": "USD"},
        headers=headers, timeout=10,
    )
    r.raise_for_status()
    data = r.json()["RAW"][cc_symbol]["USD"]
    return data["PRICE"], data["CHANGEPCT24HOUR"]

def fetch_binance(symbol):
    r = requests.get(f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}", timeout=10)
    r.raise_for_status()
    d = r.json()
    return float(d["lastPrice"]), float(d["priceChangePercent"])

def fetch_coingecko(cg_id):
    r = requests.get(
        "https://api.coingecko.com/api/v3/simple/price",
        params={"ids": cg_id, "vs_currencies": "usd", "include_24hr_change": "true"},
        headers={"User-Agent": "QuantTraderLite/1.0"}, timeout=10,
    )
    r.raise_for_status()
    d = r.json()
    return d[cg_id]["usd"], d[cg_id]["usd_24h_change"]

def get_price(coin_label):
    ids = COINS[coin_label]
    attempts = [
        (fetch_coinmarketcap,  ids["cmc"],     "CoinMarketCap"),
        (fetch_cryptocompare,  ids["cc"],      "CryptoCompare"),
        (fetch_binance,        ids["binance"], "Binance"),
        (fetch_coingecko,      ids["cg"],      "CoinGecko"),
    ]
    errors = []
    for fn, key, source_name in attempts:
        try:
            p, c = fn(key)
            return p, c, source_name
        except Exception as e:
            errors.append(f"{source_name}: {e}")
    raise RuntimeError("All price sources failed:\n" + "\n".join(errors))


# ── Trend ─────────────────────────────────────────────────────────────────────
def compute_trend(logs, coin_id):
    coin_logs = [l for l in logs if l.get("coin") == coin_id]
    if len(coin_logs) < 2:
        return None
    prices = [l["price"] for l in coin_logs[-10:]]
    avg = sum(prices) / len(prices)
    latest, oldest = prices[-1], prices[0]
    trend = "UPTREND" if latest > oldest else "DOWNTREND" if latest < oldest else "SIDEWAYS"
    return {
        "trend": trend,
        "pct_move": round(((latest - oldest) / oldest) * 100, 2),
        "avg_price": round(avg, 2),
        "high": max(prices),
        "low": min(prices),
        "n_points": len(prices),
    }


# ── AI Signal Prompt ──────────────────────────────────────────────────────────
def build_prompt(coin_label, price, change_24h, trend_data=None):
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
    return (
        f"You are a conservative crypto trading signal agent.\n"
        f"Coin: {coin_label}\nCurrent Price: ${price:,.2f}\n24h Change: {change_24h:.2f}%\n{trend_block}\n"
        f"Rules:\n"
        f"- BUY only if trend is clearly bullish and 24h change > +1%\n"
        f"- SELL only if trend is clearly bearish and 24h change < -1%\n"
        f"- HOLD in all uncertain or sideways conditions\n"
        f"- Never risk more than 2% of portfolio per trade\n\n"
        f"Reply in EXACTLY this format (no extra text):\n"
        f"SIGNAL: [BUY/SELL/HOLD] | RISK: [LOW/MEDIUM/HIGH] | REASON: [one concise sentence]"
    )


# ── Groq ──────────────────────────────────────────────────────────────────────
def ask_groq(prompt):
    if not GROQ_API_KEY:
        raise RuntimeError("No GROQ_API_KEY")
    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
        json={"model": "llama-3.3-70b-versatile", "max_tokens": 100,
              "messages": [{"role": "user", "content": prompt}]},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


# ── Cerebras ──────────────────────────────────────────────────────────────────
def ask_cerebras(prompt):
    if not CEREBRAS_API_KEY:
        raise RuntimeError("No CEREBRAS_API_KEY")
    r = requests.post(
        "https://api.cerebras.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {CEREBRAS_API_KEY}", "Content-Type": "application/json"},
        json={"model": "llama3.1-70b", "max_tokens": 100,
              "messages": [{"role": "user", "content": prompt}]},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


# ── Cohere ────────────────────────────────────────────────────────────────────
def ask_cohere(prompt):
    if not COHERE_API_KEY:
        raise RuntimeError("No COHERE_API_KEY")
    r = requests.post(
        "https://api.cohere.com/v2/chat",
        headers={"Authorization": f"Bearer {COHERE_API_KEY}", "Content-Type": "application/json"},
        json={"model": "command-r-plus", "max_tokens": 100,
              "messages": [{"role": "user", "content": prompt}]},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()["message"]["content"][0]["text"].strip()


# ── Mistral ───────────────────────────────────────────────────────────────────
def ask_mistral(prompt):
    if not MISTRAL_API_KEY:
        raise RuntimeError("No MISTRAL_API_KEY")
    r = requests.post(
        "https://api.mistral.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"},
        json={"model": "mistral-large-latest", "max_tokens": 100,
              "messages": [{"role": "user", "content": prompt}]},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


# ── Route AI call ─────────────────────────────────────────────────────────────
def ask_ai(provider, coin_label, price, change_24h, trend_data=None):
    prompt = build_prompt(coin_label, price, change_24h, trend_data)
    try:
        if provider == "Groq":      return ask_groq(prompt),     "Groq · llama-3.3-70b"
        if provider == "Cerebras":  return ask_cerebras(prompt),  "Cerebras · llama3.1-70b"
        if provider == "Cohere":    return ask_cohere(prompt),    "Cohere · command-r-plus"
        if provider == "Mistral":   return ask_mistral(prompt),   "Mistral · mistral-large"
    except Exception as e:
        return f"SIGNAL: HOLD | RISK: LOW | REASON: {provider} error — {e}", provider
    return "SIGNAL: HOLD | RISK: LOW | REASON: Unknown provider.", provider


# ── Trade Execution ────────────────────────────────────────────────────────────
def execute_trade(signal, coin_label):
    amounts = {"Bitcoin (BTC)": "0.001", "Ethereum (ETH)": "0.01", "Solana (SOL)": "0.5", "BNB": "0.05"}
    pairs   = {"Bitcoin (BTC)": "XBTUSD", "Ethereum (ETH)": "ETHUSD", "Solana (SOL)": "SOLUSD", "BNB": "BNBUSD"}
    amt  = amounts.get(coin_label, "0.01")
    pair = pairs.get(coin_label, "XBTUSD")
    if "BUY"  in signal: return f"[SANDBOX] BUY {amt} {pair} — queued via Kraken CLI"
    if "SELL" in signal: return f"[SANDBOX] SELL {amt} {pair} — queued via Kraken CLI"
    return "HOLD — no trade executed"


# ── Log Helpers ───────────────────────────────────────────────────────────────
def log_trade(coin_label, coin_id, price, change, signal, trade_result, source, ai_provider):
    entry = {
        "timestamp":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "coin":        coin_id,
        "coin_label":  coin_label,
        "price":       price,
        "change_24h":  round(change, 2),
        "signal":      signal,
        "trade":       trade_result,
        "source":      source,
        "ai_provider": ai_provider,
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
    for w in ["BUY", "SELL", "HOLD"]:
        if w in raw:
            return w
    return "HOLD"

def signal_icon(sig): return {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}.get(sig, "⚪")
def trend_icon(t):    return {"UPTREND": "📈", "DOWNTREND": "📉", "SIDEWAYS": "➡️"}.get(t, "")


# ══════════════════════════════════════════════════════════════════════════════
# LANDING VIEW
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.view == "landing":

    st.markdown(LANDING_HTML, unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([2, 1.4, 2])
    with col2:
        if st.button("⚡ Launch Dashboard", use_container_width=True, type="primary"):
            st.session_state.view = "dashboard"
            st.rerun()
    st.markdown(
        "<div style='text-align:center;font-size:11px;color:#4a6b5a;"
        "font-family:JetBrains Mono,monospace;margin-top:40px;"
        "padding-top:20px;border-top:1px solid rgba(255,255,255,0.07);'>"
        "QuantTrader Lite · Lablab.ai AI Trading Agents Hackathon 2026 · Kraken CLI Challenge"
        "</div>",
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD VIEW
# ══════════════════════════════════════════════════════════════════════════════
else:

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        if st.button("← Back to Home", use_container_width=True):
            st.session_state.view = "landing"
            st.rerun()
        st.markdown("---")
        st.markdown("**⚙️ Agent Settings**")
        coin_label   = st.selectbox("Coin", list(COINS.keys()))
        coin_id      = COINS[coin_label]["cg"]
        ai_provider  = st.selectbox("AI Provider", AI_PROVIDERS)
        auto_refresh = st.toggle("🔄 Auto-refresh every 60s", value=False)
        st.markdown("---")
        st.markdown("**API Status**")

        def key_status(name, key):
            ok = "✅" if key else "⚠️ missing"
            st.caption(f"{ok} {name}")

        key_status("Groq",           GROQ_API_KEY)
        key_status("Cerebras",       CEREBRAS_API_KEY)
        key_status("Cohere",         COHERE_API_KEY)
        key_status("Mistral",        MISTRAL_API_KEY)
        key_status("CoinMarketCap",  COINMARKETCAP_API_KEY)
        key_status("CryptoCompare",  CRYPTOCOMPARE_API_KEY)

        st.markdown("---")
        if st.button("🗑️ Clear Trade Log", use_container_width=True):
            if os.path.exists(TRADE_LOG):
                os.remove(TRADE_LOG)
            st.rerun()

    # ── Header ────────────────────────────────────────────────────────────────
    st.title("📈 QuantTrader Lite")
    st.caption(
        f"AI Trading Signal Agent · {ai_provider} + CoinMarketCap/CryptoCompare + "
        "Kraken CLI (sandbox) · Lablab.ai AI Trading Agents Hackathon 2026"
    )
    st.divider()

    logs = load_logs()

    col_btn, _ = st.columns([1, 4])
    with col_btn:
        run_now = st.button("⚡ Run Agent Now", use_container_width=True, type="primary")

    if run_now:
        with st.spinner(f"📡 Fetching {coin_label} price..."):
            try:
                price, change, source = get_price(coin_label)
                st.toast(f"✅ Price from {source}: ${price:,.2f}", icon="📡")
            except RuntimeError as e:
                st.error(f"❌ All price sources failed:\n\n{e}")
                st.stop()

        with st.spinner(f"🧠 Asking {ai_provider} for signal..."):
            trend_data  = compute_trend(logs, coin_id)
            signal_raw, model_used = ask_ai(ai_provider, coin_label, price, change, trend_data)

        trade_result = execute_trade(signal_raw, coin_label)
        entry = log_trade(coin_label, coin_id, price, change, signal_raw, trade_result, source, model_used)
        logs.append(entry)
        sig = parse_signal(signal_raw)
        st.success(
            f"✅ {entry['timestamp']} · {coin_label} · "
            f"{signal_icon(sig)} **{sig}** · {model_used} · Source: {source}"
        )

    # ── Dashboard ─────────────────────────────────────────────────────────────
    if logs:
        latest     = logs[-1]
        sig        = parse_signal(latest["signal"])
        icon       = signal_icon(sig)
        trend_data = compute_trend(logs, latest["coin"])

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("💰 Price (USD)",   f"${latest['price']:,.2f}")
        m2.metric("📊 24h Change",    f"{latest['change_24h']:.2f}%", delta=f"{latest['change_24h']:.2f}%")
        m3.metric("🤖 Signal",        f"{icon} {sig}")
        m4.metric("📋 Trades Logged", len(logs))
        if trend_data:
            m5.metric(f"{trend_icon(trend_data['trend'])} Trend", trend_data["trend"], delta=f"{trend_data['pct_move']:+.2f}%")
        else:
            m5.metric("📈 Trend", "Need more data")

        st.divider()

        if trend_data:
            st.subheader("📊 Trend Analysis")
            t1, t2, t3, t4 = st.columns(4)
            t1.metric("Direction",    f"{trend_icon(trend_data['trend'])} {trend_data['trend']}")
            t2.metric("Session Move", f"{trend_data['pct_move']:+.2f}%")
            t3.metric("Session High", f"${trend_data['high']:,.2f}")
            t4.metric("Session Low",  f"${trend_data['low']:,.2f}")

        st.subheader(f"🧠 {latest.get('ai_provider', 'AI')} Reasoning")
        if sig == "BUY":    st.success(latest["signal"])
        elif sig == "SELL": st.error(latest["signal"])
        else:               st.warning(latest["signal"])

        df = pd.DataFrame(logs)
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        st.subheader("📉 Price History — All Coins")
        tab1, tab2, tab3, tab4 = st.tabs(["Bitcoin", "Ethereum", "Solana", "BNB"])
        tab_map = {
            "Bitcoin":  ("bitcoin",     tab1),
            "Ethereum": ("ethereum",    tab2),
            "Solana":   ("solana",      tab3),
            "BNB":      ("binancecoin", tab4),
        }
        for name, (cid, tab) in tab_map.items():
            with tab:
                subset = df[df["coin"] == cid]
                if len(subset) >= 1:
                    st.line_chart(subset.set_index("timestamp")["price"], use_container_width=True)
                    if len(subset) >= 2:
                        delta_pct = ((subset["price"].iloc[-1] - subset["price"].iloc[0]) / subset["price"].iloc[0] * 100)
                        st.caption(
                            f"Session: ${subset['price'].min():,.2f} low · "
                            f"${subset['price'].max():,.2f} high · {delta_pct:+.2f}% overall"
                        )
                else:
                    st.info(f"No data for {name} yet. Select it and run the agent.")

        st.subheader("📊 Signal Distribution")
        sig_counts = df["signal"].apply(parse_signal).value_counts()
        col_a, col_b = st.columns([1, 2])
        with col_a:
            for s, count in sig_counts.items():
                pct = round(count / len(df) * 100)
                st.metric(f"{signal_icon(s)} {s}", f"{count}  ({pct}%)")
        with col_b:
            st.bar_chart(sig_counts)

        st.subheader("📋 Trade History (last 20)")
        disp = df[["timestamp", "coin_label", "price", "change_24h", "signal", "ai_provider", "source", "trade"]].tail(20).copy()
        disp["signal"]     = disp["signal"].apply(lambda x: f"{signal_icon(parse_signal(x))} {parse_signal(x)}")
        disp["price"]      = disp["price"].apply(lambda x: f"${x:,.2f}")
        disp["change_24h"] = disp["change_24h"].apply(lambda x: f"{x:+.2f}%")
        disp.columns       = ["Time", "Coin", "Price", "24h %", "Signal", "AI Model", "Price Source", "Order"]
        st.dataframe(disp[::-1], use_container_width=True, hide_index=True)

    else:
        st.info("No trades logged yet. Click **⚡ Run Agent Now** to start.")

    if auto_refresh:
        st.caption("🔄 Auto-refreshing in 60 seconds...")
        time.sleep(60)
        st.rerun()
