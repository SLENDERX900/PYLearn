from fileinput import filename
import requests
import pandas as pd
import json   
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
nltk.download('vader_lexicon')
from datetime import datetime, timezone
import time
import re
import sys
import argparse
import random

WATCHLIST = ["NVDA", "TSLA", "GME" , "AMD" , "PLTR" , "MSFT" , "AAPL" , "AMZN" , "GOOGLE" , "META" , "NFLX" , "INTC" , "BIDU" , "BABA" , "TWTR" , "ETH" , "BTC" , "HOOD" ]
COMMON_WORDS_IGNORE = {"it", "for" ,"a" , "is" , "on" , "go" ,"edit" }

SUBREDDITS = ["wallstreetbets" , "stocks" , "investing" , "cryptocurrency" , "StockMarket", "RobinHoodPennyStocks","SatoshiStreetBets", "TrumpWallStreetBets", "ValueInvesting", "StockAnalysis" , "IPO" , "tendies" , "CryptoMarkets" , "WallStreetOGs", "ShortSqueeze", "StonkMarket" , "MemeStocks" , "BTFD" , "APES" , "WAGMI" ]
FOURCHAN = ["biz" , "pol" , "gme" , "stocks" , "wallstreetbets" , "ctrades" , "Trump" , "America"] 

# --- LIVE MIRRORS (optional real-time scanner) ---
MIRRORS = [
    "https://redlib.catsarch.com",
    "https://redlib.zaggy.nl",
    "https://teddit.net",
    "https://libreddit.kavin.rocks",
    "https://reddit.invak.id"
]

# Simple list of keywords to watch in titles
# FIREHOSE TEST MODE: Expanded to catch everything (was: KEYWORDS = WATCHLIST)
KEYWORDS = [
    # Your Tickers
    "NVDA", "TSLA", "GME", "AMD", "PLTR", "MSFT", "AAPL", "AMZN", "GOOGLE", "META", "NFLX", "INTC", "BIDU", "BABA", "TWTR", "ETH", "BTC", "HOOD",
    # Action words (catches trading activity)
    "buy", "sell", "hold", "moon", "yolo", "hodl", "pump", "dump", "short", "long",
    # General financial chatter
    "market", "crash", "money", "profit", "loss", "gain", "trade", "invest", "portfolio","buy","sell",
    # Weekend topics
    "crypto", "Bitcoin", "AI", "stocks", "earnings",
    # Single letters (catches $A, $B, etc. for ticker mentions)
    "A", "B", "C", "D", "E", "F", "G", "H", "I", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"
]

# --- USER AGENT ROTATION (Anti-block strategy) ---
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/121.0.0.0",
]

def get_live_posts(subreddit, mirror_url, retries=3):
    """
    Fetches the latest posts from a specific mirror using standard JSON.
    Includes user-agent rotation, random delays, and retry logic.
    No API key required.
    """
    url = f"{mirror_url}/r/{subreddit}/new.json"
    
    for attempt in range(retries):
        try:
            # Rotating user-agent to avoid blocks
            user_agent = random.choice(USER_AGENTS)
            
            headers = {
                "User-Agent": user_agent,
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Accept-Encoding": "gzip, deflate",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": f"{mirror_url}/r/{subreddit}",
                "X-Requested-With": "XMLHttpRequest",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1"
            }
            
            # Random delay between 0.5 and 2.5 seconds to avoid rate limits
            time.sleep(random.uniform(0.5, 2.5))
            
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                # Navigate the JSON structure: data -> children -> [posts]
                return data['data']['children']
            elif response.status_code == 429:
                # Rate limited; backoff exponentially
                backoff = 2 ** attempt
                print(f"    [429] Rate limited on {subreddit}. Backing off {backoff}s...")
                time.sleep(backoff)
            else:
                print(f"    [HTTP {response.status_code}] {subreddit} attempt {attempt + 1}/{retries}")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
        except Exception as e:
            print(f"    [Error] {subreddit}: {str(e)[:50]}")
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    
    return None


def run_mirror_monitor(poll_interval=60, max_seen=5000):
    """
    Optional real-time scanner that polls anonymous Reddit mirrors for new posts.
    Call `run_mirror_monitor()` manually to start; it is NOT invoked automatically.
    """
    print("--- SLENTRAC (NO-API MODE) MIRROR MONITOR READY ---")
    print("Scanning mirrors for live market chatter...")

    # Keep track of posts we've already seen so we don't print duplicates
    seen_post_ids = set()

    while True:
        current_time = datetime.now().strftime("%H:%M:%S")
        print(f"\n[{current_time}] Scanning...")

        # 1. Find a working mirror with better headers
        active_mirror = None
        for mirror in MIRRORS:
            try:
                # Quick test to see if mirror is alive
                test_headers = {
                    "User-Agent": random.choice(USER_AGENTS),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
                }
                requests.get(mirror, headers=test_headers, timeout=5)
                active_mirror = mirror
                print(f"  ✓ Active mirror: {mirror}")
                break
            except:
                continue
        
        if not active_mirror:
            print("  ! All mirrors seem busy. Retrying in 120s...")
            time.sleep(min(poll_interval * 2, 120))
            continue

        # 2. Scan Subreddits with detailed metrics
        total_words_scanned = 0
        posts_checked = 0
        posts_matched = 0
        
        for sub in SUBREDDITS:
            print(f"\n[SCANNING] ------------------- r/{sub} -------------------")
            posts = get_live_posts(sub, active_mirror)
            
            if not posts:
                print(f"  > r/{sub}: No data found (Skipping)")
                continue

            print(f"  > Found {len(posts)} incoming posts. Checking titles...")

            for post_wrapper in posts:
                post = post_wrapper['data']
                post_id = post.get('id')
                title = post.get('title', '')
                body_text = post.get('selftext', '')  # This is the "Deep" part
                
                # Combine title and body for a full analysis
                full_text = f"{title} {body_text}"
                word_count = len(full_text.split())
                total_words_scanned += word_count
                posts_checked += 1
                
                # If we haven't seen this post yet
                # NOTE: Memory behavior:
                # - FIRST RUN: Will show all ~25 posts from cache (new posts)
                # - SUBSEQUENT RUNS: Only shows brand new posts not yet cached
                # - If paused 10-20 min: Small subreddits may have zero new posts (saturated)
                # Solution: Restart script to clear seen_post_ids, or increase poll_interval
                if post_id and post_id not in seen_post_ids:
                    seen_post_ids.add(post_id)
                    
                    # Case-insensitive keyword check
                    title_upper = title.upper()
                    matched_keywords = [str(key).upper() for key in KEYWORDS if str(key).upper() in title_upper]
                    if any(str(key).upper() in title_upper for key in KEYWORDS):
                        posts_matched += 1
                        print(f"  [TARGET FOUND] {title[:50]}...")
                        print(f"     -> Matched: {matched_keywords}")
                        print(f"     -> Deep Scan: Reading {word_count} words of analysis...")
                        
                        # Show a snippet of the body text so you KNOW it read it
                        if len(body_text) > 0:
                            snippet = body_text[:100].replace('\n', ' ')
                            print(f"     -> Snippet: \"{snippet}...\"")
                        else:
                            print(f"     -> (Post has no body text, image/link only)")

        print(f"\n[METRICS] Posts Checked: {posts_checked} | Matched Keywords: {posts_matched} | Total Words: {total_words_scanned}")

        # 3. Clean up memory (optional)
        if len(seen_post_ids) > max_seen:
            seen_post_ids.clear()

        # 4. Sleep to be polite
        print(f"Sleeping {poll_interval}s...")
        time.sleep(poll_interval)

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
    total_words_scanned = 0
    
    # Fake browser header to avoid being blocked
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}

    for sub in SUBREDDITS:
        print(f"\n[SCANNING] ------------------- r/{sub} -------------------")
        url = f"https://www.reddit.com/r/{sub}/hot.json?limit=25"
        
        # Retry logic with exponential backoff for rate limits
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Random delay to avoid thundering herd (0.5-3 seconds)
                delay = random.uniform(0.5, 3.0)
                time.sleep(delay)
                
                response = requests.get(url, headers=headers, timeout=15)
                
                if response.status_code == 429:
                    # Rate limited - exponential backoff
                    backoff = (2 ** attempt) * 5  # 5s, 10s, 20s
                    print(f"  > [429] Rate limited! Backing off {backoff}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(backoff)
                    continue
                elif response.status_code != 200:
                    print(f"  > Failed to scan r/{sub} (Status: {response.status_code})")
                    break
                
                # Success! Process posts
                posts = response.json()['data']['children']
                print(f"  > Found {len(posts)} incoming posts. Diving in...")
                
                for post in posts:
                    p_data = post['data']
                    title = p_data.get('title', '')
                    selftext = p_data.get('selftext', '')
                    full_text = clean_text(f"{title} {selftext}")
                    
                    # Count words scanned
                    word_count = len(full_text.split())
                    total_words_scanned += word_count
                    
                    for ticker in WATCHLIST:
                        if check_ticker_match(full_text, ticker):
                            score = get_sentiment(full_text)
                            print(f"  [TARGET FOUND] {title[:40]}...")
                            print(f"     -> Deep Scan: Reading {word_count} words of analysis...")
                            
                            # Show snippet
                            if len(selftext) > 0:
                                snippet = selftext[:100].replace('\n', ' ')
                                print(f"     -> Snippet: \"{snippet}...\"")
                            else:
                                print(f"     -> (Post has no body text, image/link only)")
                            
                            data.append({
                                'Source': f'Reddit (r/{sub})',
                                'Ticker': ticker,
                                'Sentiment': score,
                                'Timestamp': datetime.fromtimestamp(p_data.get('created_utc', 0), tz=timezone.utc)
                            })
                
                # Success - break out of retry loop
                break
                
            except Exception as e:
                print(f"  > Error scanning r/{sub}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Backoff on exception
    
    print(f"\n[METRICS] Total Words Processed from Reddit: {total_words_scanned}")
            
    return data

def scan_4chan():
    """
    Scrapes 4chan using their public API.
    """
    print(f"\n--- Scanning 4chan: /biz/ ---")
    data = []
    total_words_scanned = 0
    url = f"https://a.4cdn.org/biz/catalog.json"
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    # Retry logic with exponential backoff for rate limits
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Random delay to avoid thundering herd (0.5-3 seconds)
            delay = random.uniform(0.5, 3.0)
            time.sleep(delay)
            
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 429:
                # Rate limited - exponential backoff
                backoff = (2 ** attempt) * 5  # 5s, 10s, 20s
                print(f"  > [429] Rate limited! Backing off {backoff}s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(backoff)
                continue
            elif response.status_code != 200:
                print(f"  > 4chan not responding (Status: {response.status_code})")
                break
            
            print(f"  > Found {len(response.json())} pages of threads. Scanning...")
            pages = response.json()
            threads_found = 0
            
            for page in pages:
                for thread in page['threads']:
                    threads_found += 1
                    sub = thread.get('sub', '')
                    com = thread.get('com', '')
                    full_text = clean_text(f"{sub} {com}")
                    
                    word_count = len(full_text.split())
                    total_words_scanned += word_count
                    
                    for ticker in WATCHLIST:
                        if check_ticker_match(full_text, ticker):
                            score = get_sentiment(full_text)
                            print(f"  [TARGET FOUND] {sub[:40]}...")
                            print(f"     -> Deep Scan: Reading {word_count} words of analysis...")
                            
                            if len(com) > 0:
                                snippet = com[:100].replace('\n', ' ')
                                print(f"     -> Snippet: \"{snippet}...\"")
                            else:
                                print(f"     -> (Thread has minimal text)")
                            
                            data.append({
                                'Source': f'4chan (/biz/)',
                                'Ticker': ticker,
                                'Sentiment': score,
                                'Timestamp': datetime.now() 
                            })
            
            print(f"  > Scanned {threads_found} threads")
            break  # Success - exit retry loop
            
        except Exception as e:
            print(f"  > 4chan Error: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Backoff on exception
    
    print(f"[METRICS] Total Words Processed from 4chan: {total_words_scanned}")

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
    
    import os
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(script_dir, f'sentiment_{datetime.now().strftime("%Y%m%d")}.csv')
    df.to_csv(filename, index=False)
    print(f"Data saved to {filename}")

# --- PLOTTING FUNCTION ---
def plot_sentiment(filename):
    """Generate and save sentiment plot to GRAPHYYYY.png"""
    import pandas as pd
    import matplotlib.pyplot as plt
    import os
    
    # 1. Read Data
    df = pd.read_csv(filename)
    # Use the 'Sentiment' column produced by the tracker
    summary = df.groupby('Ticker')['Sentiment'].mean()

    # 2. Clear any old plots (CRITICAL STEP)
    plt.clf()
    plt.close()
    
    # 3. Create a tall figure
    fig, ax = plt.subplots(figsize=(10, 8)) # 10 inches wide, 8 inches tall
    
    # 4. Plot using PURE Matplotlib (Not Pandas)
    bars = ax.bar(summary.index, summary.values, color='purple', edgecolor='black')

    # 5. Compute dynamic y-limits with padding so labels don't hit the title
    data_min = summary.min() if not summary.empty else -1.0
    data_max = summary.max() if not summary.empty else 1.0
    bottom = min(-1.0, data_min - 0.05)
    top = max(1.0, data_max + 0.15)
    ax.set_ylim(bottom, top)

    # 6. Add Values on Top with safe offsets and clipping disabled
    v_range = top - bottom if (top - bottom) != 0 else 1.0
    for bar in bars:
        height = bar.get_height()
        offset = 0.03 * v_range
        if height >= 0:
            y_pos = min(height + offset, top - 0.02 * v_range)
            va = 'bottom'
        else:
            y_pos = max(height - offset, bottom + 0.02 * v_range)
            va = 'top'
        ax.text(bar.get_x() + bar.get_width()/2., y_pos,
                f'{height:.2f}',
                ha='center', va=va, fontweight='bold', clip_on=False)

    # 7. Clean Title
    clean_name = os.path.basename(filename)
    ax.set_title(f"SENTIMENT SCAN: {clean_name}", fontsize=14, pad=24)
    ax.set_ylabel("Sentiment Score (-1 to +1)")
    
    # 8. Add a line at 0
    ax.axhline(0, color='black', linewidth=1)

    # 9. Save to GRAPHYYYY.png in the script directory (overwrites previous)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    graph_filename = os.path.join(script_dir, "GRAPHYYYY.png")
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    plt.savefig(graph_filename, dpi=150, bbox_inches='tight')
    
    print(f"SUCCESS! Graph saved and overwrote: {graph_filename}")

def run_watch_loop(watch_interval=300):
    """Continuously run tracker → plot loop to see live graph updates"""
    print(f"\n=== WATCH MODE (updates every {watch_interval}s / {watch_interval//60}m) ===")
    print("Press Ctrl+C to stop.\n")
    
    import glob
    import os
    iteration = 0
    while True:
        iteration += 1
        print(f"\n{'='*60}")
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] WATCH LOOP #{iteration}")
        print(f"{'='*60}\n")
        
        # Run tracker
        print(">>> Running tracker...")
        main()
        
        # Generate plot from latest CSV
        print("\n>>> Regenerating graph...")
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            list_of_files = glob.glob(os.path.join(script_dir, 'sentiment_*.csv'))
            if list_of_files:
                latest_file = max(list_of_files, key=os.path.getctime)
                plot_sentiment(latest_file)
            else:
                print("No CSV files found.")
        except Exception as e:
            print(f"Plot error: {e}")
        
        # Sleep until next update
        print(f"\nNext update in {watch_interval}s ({watch_interval//60}m)...")
        time.sleep(watch_interval)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="SLENTRAC - Sentiment Tracker for Market Intelligence",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\nExamples:\n  python SLENTRAC.py --tracker              # Run sentiment tracker (default)\n  python SLENTRAC.py --monitor              # Start real-time mirror monitor\n  python SLENTRAC.py --plot                 # Generate plot from latest CSV\n  python SLENTRAC.py --all                  # Run tracker + plot\n  python SLENTRAC.py --watch                # Live graph updates (every 5m)\n  python SLENTRAC.py --watch --watch-interval 120  # Custom update interval (seconds)"
    )
    
    parser.add_argument('--tracker', action='store_true', help='Run sentiment tracker')
    parser.add_argument('--monitor', action='store_true', help='Start real-time mirror monitor')
    parser.add_argument('--plot', action='store_true', help='Generate visualization from latest CSV')
    parser.add_argument('--all', action='store_true', help='Run tracker, then plot')
    parser.add_argument('--watch', action='store_true', help='Continuous watch mode: tracker + plot loop')
    parser.add_argument('--poll-interval', type=int, default=60, help='Mirror poll interval in seconds (default: 60)')
    parser.add_argument('--watch-interval', type=int, default=300, help='Watch loop update interval in seconds (default: 300 = 5m)')
    
    args = parser.parse_args()
    
    # If no flags given, default to tracker
    if not args.tracker and not args.monitor and not args.plot and not args.all and not args.watch:
        args.tracker = True
    
    # Run watch mode (continuous loop)
    if args.watch:
        try:
            run_watch_loop(watch_interval=args.watch_interval)
        except KeyboardInterrupt:
            print("\n>>> Watch mode stopped by user.")
    
    # Run tracker
    elif args.tracker or args.all:
        print("\n=== RUNNING SENTIMENT TRACKER ===")
        main()
    
    # Run plot (requires CSV already generated)
    if args.plot or args.all:
        print("\n=== GENERATING PLOT ===")
        try:
            import pandas as pd
            import matplotlib.pyplot as plt
            import glob
            import os
            script_dir = os.path.dirname(os.path.abspath(__file__))
            list_of_files = glob.glob(os.path.join(script_dir, 'sentiment_*.csv'))
            if list_of_files:
                latest_file = max(list_of_files, key=os.path.getctime)
                print(f"Plotting data from: {latest_file}")
                # Call plot_sentiment if defined later in file
                if 'plot_sentiment' in globals():
                    plot_sentiment(latest_file)
                else:
                    print("Plot function not available in current context.")
            else:
                print("No CSV files found. Run tracker first.")
        except Exception as e:
            print(f"Cannot plot: {e}")
    
    # Run mirror monitor
    if args.monitor and not args.watch:
        print(f"\n=== STARTING MIRROR MONITOR (poll every {args.poll_interval}s) ===")
        try:
            run_mirror_monitor(poll_interval=args.poll_interval)
        except KeyboardInterrupt:
            print("\n>>> Monitor stopped by user.")


