"""
Requirements from Attilla Danko:
    * Link the html page for the chart with each use of a chart
"""

import csv
from datetime import datetime
import time
import requests
import random

from jinja2 import Template
import tweepy

user_agent = "Mozilla/5.0 (iPhone; CPU iPhone OS 12_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/12.0 Mobile/15E148 Safari/604.1"

def twitter_api():
    keys = {}
    with open("tables/keys.csv", "r") as f:
        keys = csv.DictReader(f).__next__()

    auth = tweepy.OAuthHandler(keys["API_key"], keys["API_secret_key"])
    auth.set_access_token(keys["Access_token"],  keys["Access_token_secret"])


    return tweepy.API(auth)

def read_locations():
   locations = []
   with open("tables/locations.csv", "r") as f:
      reader = csv.reader(f)
      for line in reader:
          locations.append(line)

   return locations

def tweet_body(location_row):
    args = {
      "location_name": location_row[0],
      "location_id": location_row[1]
    }

    with open("templates/greetings.j2", "r") as f:
        greetings = Template(f.read()).render(**args).split('\n')
        greeting = greetings[random.randint(0, len(greetings)-1)]

    args["greeting"] = greeting

    with open("templates/tweet.j2", "r") as f:
        body = Template(f.read()).render(**args)
    
    return body


def download_chart(key):
    filename = f"{key}csk.gif"
    url = f"https://www.cleardarksky.com/c/{filename}?c=212425"
    response = requests.get(url, headers={"User-Agent": user_agent})
    if response.status_code == 200:
        with open(filename, "wb") as f:
            f.write(response.content)
    else:
        print(f"Error getting image for {key}: response: {response.status_code}")

    return filename


def wait_until(hour_24):
    now = datetime.now()
    five = now.replace(hour=hour_24, minute=0, second=0, microsecond=0)

    # If it's already past 5pm today
    if now > five:
        # Wait until five tomorrow (add one day to posix timestamp,
        # make new datetime from resulting posix timestamp)
        five = datetime.fromtimestamp(five.timestamp() + (24 * 60 * 60))

    print(f"Sleeping until {five}")
    time.sleep(five.timestamp() - now.timestamp())

def read_last_mention_handled_id():
    tweet_id = 0

    try:
        with open("last_mention_handled.txt", "r") as f:
            tweet_id = int(f.read())
    except Exception as e:
        print(f"Did not get last mention handled id: {e}, using 0")

    return tweet_id


def find_key_from_query(query):
    """Find CSK key based off of plaintext query"""

    query_url = f"https://www.cleardarksky.com/cgi-bin/find_chart.py?keys={'+'.join(query)}&type=text&Mn=Solar%2520Power&doit=Find"
    
    response = requests.get(url, headers={"User-Agent": user_agent}) 
    if response.status_code != 200:
        print(f"Error getting {query_url}: response: {response.status_code}")
        return

    # TODO 
    # get html from response
    # find line with key on it (has key.html in line)
    # grab key from line ("../c/(.*)key.html")


def find_title_from_key(key):
    # TODO
    # get page using key
    # title is in <title> (e.g. <title>Joey's Observator Clear Sky Chart</title>)


def handle_add(api, query, tweet_id):
    key = find_key_from_query(query)
    title = find_title_from_key(key)
    add_to_locations_file(key, title) 

    api.update_status(
        status=f"{title} has been added to the list!",
        in_reply_to_status_id=tweet_id
    )

def handle_show(api, query, tweet_id):
    key = find_key_from_query(query)
    chart = download_chart(key)
    title = find_title_from_key(key)

    api.update_with_media(
        status=f"Here is the Clear Sky Chart for {title}",
        in_reply_to_status_id=tweet_id,
        filename=chart
    )

def daily_loop(api, time_to_start):
    locations = read_locations()

    wait_until(time_to_start)

    while True:
        for location in locations:
            body = tweet_body(location)
            filename = download_chart(location[1])
            api.update_with_media(filename=filename, status=body)
            print(f"Posting tweet:\n{body}")

        print("Sleeping for 24h...")
        time.sleep(24 * 60 * 60)

def mentions_handler(api, since_id):

    while True:
        new_since_id = since_id

        for tweet in tweepy.Cursor(api.mentions_timeline, since_id=new_since_id).items():
            new_since_id = max(tweet.id, new_since_id)

            tokens = tweet.text.lower().split()
        
            if "add" in tokens:
                query = tokens[tokens.index("add")+1:]
                handle_add(api, query, tweet.id)
            else if "show" in tokens:
                query = tokens[tokens.index("show")+1:]
                handle_show(api, query, tweet.id)

        time.sleep(10)
        # TODO write new_since_id to file if it has changed

if __name__ == "__main__":
    api = twitter_api()
    print("Successfully setup Twitter API")

    last_mention_handled = read_last_mention_handled_id()

    daily_post_thread = Thread(target=daily_loop, args=(api, 5,))
    mentions_handler_thread = Thread(target=mentions_handler, args=(api, last_mention_handled,))

    daily_post_thread.start()
    mentions_handler_thread.start()
