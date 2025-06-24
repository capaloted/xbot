import os
import random
import time
import logging
from pathlib import Path

import tweepy

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

# --- Environment / config ---------------------------------------------------

BEARER_TOKEN = os.getenv("AAAAAAAAAAAAAAAAAAAAAIrl2gEAAAAA60e8eQO17qxEuK2C3Q0q%2FueFeEI%3DORUbrbmG0nUDnCjOjWdMSzTsaLPyUBy7cfALddFdgWPqVBlj1Z")
API_KEY = os.getenv("5CoYNLJOORnWXtK9aR5CsEdwJ")
API_SECRET = os.getenv("oFb20vzJxTKuQPyYvLNNOjPvNKKwDdogYp4qm7p0P1VKH3GOs7")
ACCESS_TOKEN = os.getenv("1349003522394759171-K9QsS1VwScYqfxYHFIhzATvnLD6rtJ")
ACCESS_SECRET = os.getenv("yJOkaixPwn1t6ehARZ85uQ1dJoqsLCqB7qGc0eGg8GEpZ")

KEYWORDS = [kw.strip() for kw in os.getenv("KEYWORDS", "").split(",") if kw.strip()]
if not KEYWORDS:
    raise RuntimeError("KEYWORDS env var is required (comma‑separated list).")

REPLY_TEXT = os.getenv("REPLY_TEXT", "Do you want me {username} ?")
IMAGE_DIR = Path(os.getenv("IMAGE_DIR", "./images"))
MAX_REPLIES_PER_WINDOW = int(os.getenv("MAX_REPLIES_PER_WINDOW", "30"))
WINDOW_SEC = 3600  # 1 hour
POLL_INTERVAL = WINDOW_SEC // MAX_REPLIES_PER_WINDOW  # seconds between polls

STATE_FILE = Path(os.getenv("STATE_FILE", "since_id.txt"))

# --- Twitter clients --------------------------------------------------------

client_v2 = tweepy.Client(bearer_token=BEARER_TOKEN,
                          consumer_key=API_KEY,
                          consumer_secret=API_SECRET,
                          access_token=ACCESS_TOKEN,
                          access_token_secret=ACCESS_SECRET,
                          wait_on_rate_limit=True)

auth_v1 = tweepy.OAuth1UserHandler(API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET)
api_v1 = tweepy.API(auth_v1)

my_user = client_v2.get_me().data
MY_USER_ID = my_user.id
MY_USERNAME = my_user.username
logging.info(f"Authenticated as @{MY_USERNAME} ({MY_USER_ID})")

query = " OR ".join(KEYWORDS) + " -is:retweet -is:reply"

def load_since_id() -> int | None:
    if STATE_FILE.exists():
        try:
            return int(STATE_FILE.read_text().strip())
        except ValueError:
            return None
    return None

def save_since_id(since_id: int):
    STATE_FILE.write_text(str(since_id))

def choose_random_image() -> str | None:
    images = [p for p in IMAGE_DIR.glob("*") if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif"}]
    if images:
        return str(random.choice(images))
    return None

def reply_to_tweet(tweet: tweepy.Tweet):
    """Reply to a tweet with text and optional image."""
    try:
        user = client_v2.get_user(id=tweet.author_id).data
        screenname = user.username
    except Exception:
        screenname = "unknown"

    text = REPLY_TEXT.format(username=f"@{screenname}")

    media_id = None
    image_path = choose_random_image()
    if image_path:
        try:
            media = api_v1.media_upload(image_path)
            media_id = media.media_id
            logging.info(f"Uploaded media {media_id} from {image_path}")
        except Exception as e:
            logging.warning(f"Failed to upload media: {e}")

    try:
        client_v2.create_tweet(
            in_reply_to_tweet_id=tweet.id,
            text=text,
            media_ids=[media_id] if media_id else None,
        )
        logging.info(f"Replied to https://twitter.com/{screenname}/status/{tweet.id}")
    except tweepy.TweepyException as e:
        logging.error(f"Failed to reply: {e}")

def main():
    since_id = load_since_id()
    while True:
        try:
            resp = client_v2.search_recent_tweets(
                query=query,
                since_id=since_id,
                max_results=100,
                tweet_fields=["author_id", "id", "created_at"],
            )
            tweets = resp.data or []
            # handle newest first
            for tw in reversed(tweets):
                reply_to_tweet(tw)
                since_id = max(since_id or 0, tw.id)
                save_since_id(since_id)
        except tweepy.TweepyException as e:
            logging.error(f"Search failed: {e}")

        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
