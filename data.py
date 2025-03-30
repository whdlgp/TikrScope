from pathlib import Path
import json
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

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
        "theme": "default"
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

def create_plot_html(df, ticker, period, chart_type="line", timezone="Asia/Seoul", theme="default", sma_periods=[]):
    if df.empty:
        return "<h2>No data available.</h2>"
    
    df_plot = df.reset_index()

    is_dark = "dark" in theme.lower()
    plotly_template = "plotly_dark" if is_dark else "plotly"

    if chart_type == "line":
        fig = px.line(
            df_plot, x=df_plot.columns[0], y="Close",
            title=f"{ticker.upper()} Closing Prices ({period})",
            labels={df_plot.columns[0]: f"Time ({timezone})", "Close": "Close Price (USD)"}
        )
        fig.update_layout(
            template=plotly_template,
            xaxis=dict(rangeslider=dict(visible=True)),
            yaxis=dict(autorange=True, fixedrange=False),
        )
    else:
        fig = go.Figure(data=[go.Candlestick(
            x=df_plot[df_plot.columns[0]],
            open=df_plot["Open"], high=df_plot["High"],
            low=df_plot["Low"], close=df_plot["Close"]
        )])
        fig.update_layout(
            template=plotly_template,
            title=f"{ticker.upper()} Candlestick Chart ({period})",
            xaxis_title=f"Time ({timezone})",
            yaxis_title="Price (USD)",
            xaxis=dict(rangeslider=dict(visible=True)),
            yaxis=dict(autorange=True, fixedrange=False),
        )

    for p in sma_periods:
        df_plot[f"SMA{p}"] = df_plot["Close"].rolling(p).mean()
        fig.add_trace(go.Scatter(
            x=df_plot[df_plot.columns[0]],
            y=df_plot[f"SMA{p}"],
            mode="lines",
            name=f"SMA{p}",
            line=dict(width=1)
        ))

    return fig.to_html(include_plotlyjs='cdn')