"""
This file includes code derived from the holdings_dl project
by PiperBatey, available at:
    https://github.com/PiperBatey/holdings_dl
Licensed under the MIT License.

Modifications have been made by whdlgp/TikrScope to integrate 
additional functionality (e.g. search query generation and news retrieval).
For full details, see the original repository and its LICENSE file.
"""

import math
import time
import io
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
import yfinance as yf
import feedparser
from urllib.parse import quote
from datetime import datetime, timedelta

def get_etf_description(etf_symbol, headless=True, wait_time=15, min_weight=0.01):
    options = Options()
    options.headless = headless
    driver = webdriver.Firefox(options=options)
    driver.implicitly_wait(wait_time)

    def to_float_weight(x):
        x = str(x).strip()
        if x.endswith("%"):
            try:
                return float(x[:-1]) / 100.0
            except ValueError:
                return None
        return None

    try:
        url = ("https://www.schwab.wallst.com/schwab/Prospect/research/etfs/schwabETF"
               f"/index.asp?type=holdings&symbol={etf_symbol}")
        driver.get(url)

        try:
            show_sixty = driver.find_element(By.XPATH, "//a[@perpage='60']")
            show_sixty.click()
        except Exception as e:
            print(f"Show 60 items not found for {etf_symbol}: {e}")
            return []

        wait_driver = WebDriverWait(driver, 30, poll_frequency=1)
        page_elt = wait_driver.until(EC.visibility_of_element_located((By.CLASS_NAME, "paginationContainer")))
        pages_text = page_elt.text.split()
        if len(pages_text) < 5:
            print(f"Unexpected pagination format for {etf_symbol}: {pages_text}")
            return []
        total_holdings = float(pages_text[4])
        num_pages = int(math.ceil(total_holdings / 60.0))

        time.sleep(0.5)
        first_html = io.StringIO(driver.page_source)
        first_tables = pd.read_html(first_html, match="Symbol")
        if not first_tables:
            print(f"No table on first page for {etf_symbol}")
            return []
        df_first = first_tables[1] if len(first_tables) > 1 else first_tables[0]
        df_list = [df_first]

        def filter_and_check(df_raw):
            if len(df_raw.columns) < 5:
                return pd.DataFrame(), True
            df_raw.columns = ["Symbol", "Description", "Portfolio Weight", "Shares Held", "Market Value"]
            df_raw["WeightFloat"] = df_raw["Portfolio Weight"].apply(to_float_weight)
            df_filtered = df_raw[df_raw["WeightFloat"] >= min_weight].copy()
            stop = df_filtered.empty
            return df_filtered, stop

        filtered_df, stop_now = filter_and_check(df_first)
        current_page = 2
        while current_page <= num_pages and not stop_now:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            try:
                next_button = driver.find_element(By.XPATH, f"//li[@pagenumber='{current_page}']")
                driver.execute_script("arguments[0].click();", next_button)
            except Exception as e:
                print(f"Could not click page {current_page} for {etf_symbol}: {e}")
                break
            while True:
                time.sleep(0.25)
                new_html = io.StringIO(driver.page_source)
                next_tables = pd.read_html(new_html, match="Symbol")
                if not next_tables:
                    print(f"No table on page {current_page} for {etf_symbol}, stopping.")
                    stop_now = True
                    break
                candidate_df = next_tables[1] if len(next_tables) > 1 else next_tables[0]
                if not candidate_df.equals(df_list[-1]):
                    df_list.append(candidate_df)
                    new_filtered, stop_now = filter_and_check(candidate_df)
                    filtered_df = pd.concat([filtered_df, new_filtered], ignore_index=True)
                    break
            current_page += 1

        if not filtered_df.empty:
            filtered_df.drop_duplicates(inplace=True)
        else:
            return []
        descriptions = []
        seen = set()
        for desc in filtered_df["Description"]:
            d = str(desc).strip()
            if d not in seen:
                seen.add(d)
                descriptions.append(d)
        return descriptions
    except Exception as ex:
        print(f"Error retrieving {etf_symbol}: {ex}")
        return []
    finally:
        driver.quit()

def build_search_queries(ticker_symbol, headless=True, min_weight=0.01):
    ticker = yf.Ticker(ticker_symbol)
    try:
        info = ticker.info
    except Exception:
        info = {}
    queries = set()

    queries.add(ticker_symbol)
    long_name = info.get("longName") or info.get("shortName")
    if long_name:
        queries.add(long_name)

    if info.get("quoteType", "").upper() == "ETF":
        queries.add(f"{ticker_symbol} ETF")
        if long_name and "ETF" not in long_name.upper():
            queries.add(f"{long_name} ETF")

        holdings = get_etf_description(ticker_symbol, headless=headless, min_weight=min_weight)
        for holding in holdings:
            queries.add(f"{holding} stock")
    return list(queries)

def fetch_news_for_queries(queries, days=5):
    news_items = []
    cutoff = datetime.now() - timedelta(days=days)
    for query in queries:
        q_encoded = quote(query)
        rss_url = f"https://news.google.com/rss/search?q={q_encoded}"
        feed = feedparser.parse(rss_url)
        for entry in feed.entries:

            published_struct = getattr(entry, "published_parsed", None)
            if not published_struct:
                continue
            published_dt = datetime(*published_struct[:6])
            if published_dt < cutoff:
                continue
            news_items.append({
                "query": query,
                "title": entry.title,
                "link": entry.link,
                "published": published_dt,
                "summary": entry.summary
            })

    seen_links = set()
    unique_news = []
    for item in news_items:
        if item["link"] not in seen_links:
            seen_links.add(item["link"])
            unique_news.append(item)
    unique_news.sort(key=lambda x: x["published"], reverse=True)
    return unique_news

if __name__ == "__main__":
    #ticker = "SCHF"  # Replace with test ticker name
    ticker = "NVDA"
    print(f"Processing ticker: {ticker}")
    
    queries = build_search_queries(ticker, headless=True, min_weight=0.01)
    print("Search queries:")
    for q in queries:
        print(f"- {q}")
    
    news = fetch_news_for_queries(queries, days=5)
    
    print("\nNews Results (sorted by most recent):")
    for item in news:
        print(f"[{item['published']:%Y-%m-%d %H:%M:%S}] ({item['query']}) {item['title']}")
        print(f"Link: {item['link']}")
        print("-" * 80)
