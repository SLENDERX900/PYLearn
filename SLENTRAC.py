import requests
import pandas as pd
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
nltk.download('vader_lexicon')
from datetime import datetime
import time
import re

WATCHLIST = ["NVDA", "TSLA", "GME" , "AMD" , "PLTR" , "MSFT" , "AAPL" , "AMZN" , "GOOGLE" , "META" , "NFLX" , "INTC" , "BIDU" , "BABA" , "TWTR" , "ETH" , "BTC" , "HOOD" ]
COMMON_WORDS_IGNORE = {"it", "for" ,"a" , "is" , "on" , "go" ,"edit" }

SUBREDDITS = ["wallstreetbets" , "stocks" , "investing" , "cryptocurrency" , "StockMarket", "RobinHoodPennyStocks","SatoshiStreetBets", "TrumpWallStreetBets", "ValueInvesting", "StockAnalysis" , "IPO" , "tendies" , "CryptoMarkets" , "WallStreetOGs", "ShortSqueeze", "StonkMarket" , "MemeStocks" , "BTFD" , "APES" , "WAGMI" ]
FOURCHAN = ["biz" , "pol" , "gme" , "stocks" , "wallstreetbets", "X" , "ctrades" , "Trump" , "America"] 
# --- SETUP NLP ---
try:
    nltk.data.find('sentiment/vader_lexicon.zip')
except LookupError:
    nltk.download('vader_lexicon')

sia = SentimentIntensityAnalyzer()
sia.lexicon.update({
    'moon': 3.0, 'mooning': 3.0, 'bull': 2.0, 'bullish': 2.0,
    'bear': -2.0, 'bearish': -2.0, 'bagholder': -2.5, 'tendies': 2.5,
    'rug': -3.0, 'rugpull': -3.5, 'gem': 2.0, 'scam': -3.0,
    'dump': -2.5, 'pump': -1.0, 'yolo': 1.5, 'diamond': 2.0, 'rekt': -3.0
})

# --- HELPER FUNCTIONS ---
def clean_text(text):
    if not text: return ""
    return text.replace('<br>', ' ').replace('&gt;', '')

def check_ticker_match(text, ticker):
    text = text.upper()
    ticker = ticker.upper()
    if ticker in COMMON_WORDS_IGNORE:
        pattern = r'\$' + re.escape(ticker) + r'\b'
    else:
        pattern = r'(\$|\b)' + re.escape(ticker) + r'\b'
    return re.search(pattern, text) is not None

def get_sentiment(text):
    return sia.polarity_scores(text)['compound']

# --- NO-LOGIN SCRAPERS ---

def scan_reddit_public():
    """
    Scrapes Reddit using the public .json endpoints (No API key required).
    """
    print(f"--- Scanning Reddit (Public JSON Mode): {SUBREDDITS} ---")
    data = []
    
    # Fake browser header to avoid being blocked
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}

    for sub in SUBREDDITS:
        url = f"https://www.reddit.com/r/{sub}/hot.json?limit=25"
        
        try:
        response = requests.get(url, headers=headers)
            
            if response.status_code != 200:
                print(f"Failed to scan r/{sub} (Status: {response.status_code})")
                continue
                
            posts = response.json()['data']['children']
            
            for post in posts:
                p_data = post['data']
                title = p_data.get('title', '')
                selftext = p_data.get('selftext', '')
                full_text = clean_text(f"{title} {selftext}")
                
                for ticker in WATCHLIST:
                    if check_ticker_match(full_text, ticker):
                        score = get_sentiment(full_text)
                        data.append({
                            'Source': f'Reddit (r/{sub})',
                            'Ticker': ticker,
                            'Sentiment': score,
                            'Timestamp': datetime.utcfromtimestamp(p_data.get('created_utc', 0))
                        })
            
            # CRITICAL: Sleep to respect Reddit's rate limits for public access
            time.sleep(2) 
            
        except Exception as e:
            print(f"Error scanning r/{sub}: {e}")
            
    return data

def scan_4chan():
    """
    Scrapes 4chan using their public API.
    """
    print(f"--- Scanning 4chan: /biz/ ---")
    data = []
    url = f"https://a.4cdn.org/biz/catalog.json"
    
    try:
        response = requests.get(url)
        if response.status_code != 200: return []
            
        pages = response.json()
        for page in pages:
            for thread in page['threads']:
                sub = thread.get('sub', '')
                com = thread.get('com', '')
                full_text = clean_text(f"{sub} {com}")
                
                for ticker in WATCHLIST:
                    if check_ticker_match(full_text, ticker):
                        score = get_sentiment(full_text)
                        data.append({
                            'Source': f'4chan (/biz/)',
                            'Ticker': ticker,
                            'Sentiment': score,
                            'Timestamp': datetime.now() 
                        })
    except Exception as e:
        print(f"4chan Error: {e}")

    return data

# --- MAIN ---
def main():
    print("Starting No-Login Sentiment Tracker...\n")
    
    # No credentials needed anymore
    reddit_data = scan_reddit_public()
    fourchan_data = scan_4chan()
    
    all_data = reddit_data + fourchan_data
    
    if not all_data:
        print("\nNo mentions found. Try adding more tickers.")
        return

    df = pd.DataFrame(all_data)
    
    print("\n--- SENTIMENT REPORT ---")
    summary = df.groupby('Ticker')['Sentiment'].agg(
        Count='count',
        Avg_Sentiment='mean',
        Min='min',
        Max='max'
    ).sort_values(by='Count', ascending=False)
    
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    print(summary)
    
    # Save to CSV
    filename = f'sentiment_{datetime.now().strftime("%Y%m%d")}.csv'
    df.to_csv(filename, index=False)
    print(f"Data saved to {filename}")

if __name__ == "__main__":
    main()

import pandas as pd
import matplotlib.pyplot as plt
import glob
import os

# --- CONFIGURATION ---
# This finds the most recent CSV file in your folder automatically
list_of_files = glob.glob('sentiment_*.csv') 
if not list_of_files:
    print("No CSV files found! Run the tracker first.")
    exit()

# Pick the latest file
latest_file = max(list_of_files, key=os.path.getctime)
print(f"Plotting data from: {latest_file}")

# --- LOAD DATA ---
df = pd.read_csv(latest_file)

# Calculate Average Sentiment per Ticker
summary = df.groupby('Ticker')['Sentiment'].mean()

# --- PLOT ---
plt.figure(figsize=(10, 6))

# Color logic: Green for positive, Red for negative
colors = ['#2ecc71' if x >= 0 else '#e74c3c' for x in summary.values]

# Create Bar Chart
bars = summary.plot(kind='bar', color=colors, edgecolor='black')

# Styling
plt.title(f'Market Sentiment Snapshot ({latest_file})', fontsize=15, fontweight='bold')
plt.xlabel('Ticker', fontsize=12)
plt.ylabel('Sentiment Score (-1 to +1)', fontsize=12)
plt.axhline(0, color='black', linewidth=1) # The zero line
plt.grid(axis='y', linestyle='--', alpha=0.5)
plt.ylim(-1, 1) # Fix y-axis from -1 to 1

# Add value labels on top of bars
for i, v in enumerate(summary.values):
    plt.text(i, v + (0.05 if v > 0 else -0.1), str(round(v, 2)), 
             ha='center', fontweight='bold')

plt.tight_layout()

# Show the plot
plt.show()








