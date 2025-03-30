from pathlib import Path
import json
import yfinance as yf
import pandas as pd
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import plotly.express as px

CONFIG_PATH = Path("config.json")

def load_config(path=CONFIG_PATH):
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "tickers": ["NDAQ", "SPY"],
        "timezone": "Asia/Seoul",
        "chart_type": "line",
        "period": "1y",
        "theme": "default",
        "main_indicator": ["sma5", "sma20", "sma60", "sma120", "vwap"],
        "sub_indicator": "williams_r"
    }

def save_config(path, config):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)

def fetch_market_data(ticker: str, period: str, timezone: str = "Asia/Seoul") -> pd.DataFrame:
    interval_map = {
        "1d": "1m", "5d": "1d", "1mo": "1d", "3mo": "1d",
        "6mo": "1d", "1y": "1d", "5y": "1d"
    }
    interval = interval_map.get(period, "1d")
    df = yf.download(ticker, period=period, interval=interval, progress=False)

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]

    if isinstance(df.index, pd.DatetimeIndex):
        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC').tz_convert(timezone)
        else:
            df.index = df.index.tz_convert(timezone)

    return df

def create_thumbnail(ticker, timezone="Asia/Seoul", force_update=False):
    plots_dir = Path('plots')
    plots_dir.mkdir(exist_ok=True)
    thumb_path = plots_dir / f'{ticker}.png'

    if force_update or not thumb_path.exists():
        df = fetch_market_data(ticker, "5y", timezone)
        if not df.empty:
            df_plot = df.reset_index()
            fig = px.line(df_plot, x=df_plot.columns[0], y="Close")
            fig.update_layout(
                margin=dict(l=0, r=0, t=0, b=0),
                xaxis=dict(visible=False),
                yaxis=dict(visible=False),
                showlegend=False
            )
            fig.write_image(str(thumb_path), width=200, height=120)

    return str(thumb_path)

def init_figure(ticker, sub_indicator, theme):
    is_dark = "dark" in theme.lower()
    template = "plotly_dark" if is_dark else "plotly"
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.7, 0.3],
        vertical_spacing=0.03,
        subplot_titles=[f"{ticker.upper()} Chart", sub_indicator.replace('_', ' ').title()]
    )
    fig.update_layout(
        template=template,
        margin=dict(t=40, b=40),
        dragmode="zoom",
        xaxis_rangeslider_visible=False
    )
    fig.update_xaxes(fixedrange=False)
    fig.update_yaxes(autorange=True, fixedrange=False)
    return fig

def price_trace(df, chart_type, date_col):
    if chart_type == "line":
        return go.Scatter(
            x=df[date_col],
            y=df["Close"],
            name="Close",
            mode="lines"
        )
    else:
        return go.Candlestick(
            x=df[date_col],
            open=df["Open"], high=df["High"],
            low=df["Low"], close=df["Close"],
            name="Candlestick"
        )

def add_sma(fig, df, periods, date_col):
    for p in periods:
        df[f"SMA{p}"] = df["Close"].rolling(p).mean()
        fig.add_trace(go.Scatter(
            x=df[date_col],
            y=df[f"SMA{p}"],
            mode="lines",
            name=f"SMA{p}",
            line=dict(width=1)
        ), row=1, col=1)

def add_vwap(fig, df, date_col):
    vwap = (df["Volume"] * (df["High"] + df["Low"] + df["Close"]) / 3).cumsum() / df["Volume"].cumsum()
    fig.add_trace(go.Scatter(
        x=df[date_col],
        y=vwap,
        name="VWAP",
        mode="lines",
        line=dict(color="purple", width=1)
    ), row=1, col=1)

def add_williams_r(fig, df, date_col, period=14):
    high = df["High"].rolling(period).max()
    low = df["Low"].rolling(period).min()
    df["Williams %R"] = (high - df["Close"]) / (high - low) * -100

    fig.add_trace(go.Scatter(
        x=df[date_col],
        y=df["Williams %R"],
        name="Williams %R",
        mode="lines",
        line=dict(color='orange', width=1)
    ), row=2, col=1)

    for level in [-20, -80]:
        fig.add_shape(
            type="line",
            x0=df[date_col].iloc[0],
            x1=df[date_col].iloc[-1],
            y0=level,
            y1=level,
            line=dict(color="gray", dash="dot"),
            row=2, col=1
        )

def add_mfi(fig, df, date_col, period=14):
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    mf = tp * df["Volume"]
    direction = tp.diff() > 0

    pos_mf = mf.where(direction, 0).rolling(period).sum()
    neg_mf = mf.where(~direction, 0).rolling(period).sum()

    mfi = 100 - (100 / (1 + (pos_mf / neg_mf)))
    df["MFI"] = mfi

    fig.add_trace(go.Scatter(
        x=df[date_col],
        y=df["MFI"],
        name="MFI",
        mode="lines",
        line=dict(color="green", width=1)
    ), row=2, col=1)

    for level in [20, 80]:
        fig.add_shape(
            type="line",
            x0=df[date_col].iloc[0],
            x1=df[date_col].iloc[-1],
            y0=level,
            y1=level,
            line=dict(color="gray", dash="dot"),
            row=2, col=1
        )

def add_stoch_rsi(fig, df, date_col, period=14, smooth_k=3, smooth_d=3):
    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    min_rsi = rsi.rolling(period).min()
    max_rsi = rsi.rolling(period).max()

    stoch_rsi = (rsi - min_rsi) / (max_rsi - min_rsi)
    k = stoch_rsi.rolling(smooth_k).mean() * 100
    d = k.rolling(smooth_d).mean()

    df["StochRSI_K"] = k
    df["StochRSI_D"] = d

    fig.add_trace(go.Scatter(
        x=df[date_col],
        y=df["StochRSI_K"],
        name="%K",
        mode="lines",
        line=dict(color="blue", width=1)
    ), row=2, col=1)

    fig.add_trace(go.Scatter(
        x=df[date_col],
        y=df["StochRSI_D"],
        name="%D",
        mode="lines",
        line=dict(color="orange", width=1)
    ), row=2, col=1)

    for level in [20, 80]:
        fig.add_shape(
            type="line",
            x0=df[date_col].iloc[0],
            x1=df[date_col].iloc[-1],
            y0=level,
            y1=level,
            line=dict(color="gray", dash="dot"),
            row=2, col=1
        )

def create_plot_html(df, ticker, chart_type="line", theme="default", main_indicator=[], sub_indicator="williams_r"):
    if df.empty:
        return "<h2>No data available.</h2>"

    df = df.reset_index()
    date_col = df.columns[0]
    fig = init_figure(ticker, sub_indicator, theme)

    fig.add_trace(price_trace(df, chart_type, date_col), row=1, col=1)

    for indicator in main_indicator:
        if "sma" in indicator:
            period = int(indicator[3:])
            add_sma(fig, df, [period], date_col)
        elif indicator == "vwap":
            add_vwap(fig, df, date_col)

    if sub_indicator == "williams_r":
        add_williams_r(fig, df, date_col)
    elif sub_indicator == "mfi":
        add_mfi(fig, df, date_col)
    elif sub_indicator == "stoch_rsi":
        add_stoch_rsi(fig, df, date_col)

    return fig.to_html(include_plotlyjs='cdn')