"""
cleardarkskybot.py - Daily clear dark sky charts posted to Twitter

Files:
    - tables/keys.csv: Twitter API keys go in here.
    - tables/locations.csv: List of locations go in here. 2 columns: Name and ID (used in URLs)
    - templates/greetings.j2: List of greetings that will be used in tweets.
    - templates/tweet.j2: The body of the tweet, including the greeting and the link to the chart key page.

"""

import csv
import json
from datetime import datetime
import time
import requests
import random
from multithreading import Thread

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

def add_to_locations(key, title):
    locations = read_locations()
    if [title, key] in locations: # Gross I know, eventually will make locations a dict
        return -1

    with open("tables/locations.csv", "a") as f:
        f.write(f"{title},{key}")

def build_key_url(key):
    return f"https://www.cleardarksky.com/c/{key}key.html"

def tweet_body(location_row):
    args = {
      "location_name": location_row[0],
      "location_id": location_row[1]
    }

    with open("templates/greetings.j2", "r") as f:
        greetings = Template(f.read()).render(**args).split('\n')
        greeting = greetings[random.randint(0, len(greetings)-1)]

    args["greeting"] = greeting
    args["key_url"] = build_key_url(location_row[1])

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


def update_last_mention_handled_id(mention_id):
    with open("last_mention_handled.txt", "w") as f:
        f.write(str(mention_id))

def coordinates_from_query(query):
    with open("tables/positionstack.txt", "r") as f:
        key = f.read().strip()

    query_url = f"http://api.positionstack.com/v1/forward?access_key={key}&query={query}"
    print(f"retrieving: {query_url}")
    response = requests.get(query_url, headers={"User-Agent": user_agent})
    response_dict = json.loads(response.text)
    first = response_dict["data"][0]
    latitude = first["latitude"]
    longitude = first["longitude"] * -1 # W

    return latitude, longitude

def find_key_from_query(query):
    """Find CSK key based off of plaintext query"""


    latitude, longitude = coordinates_from_query(query)

    query_url = f"https://www.cleardarksky.com/cgi-bin/find_chart.py?type=llmap&Mn=astrophysics&olat={latitude}&olong={longitude}&olatd=&olatm=&olongd=&olongm=&unit=1"

#    query_url = f"https://www.cleardarksky.com/cgi-bin/find_chart.py?keys={query}&type=text&Mn=Solar%2520Power&doit=Find"
    
    response = requests.get(query_url, headers={"User-Agent": user_agent}) 
    if response.status_code != 200:
        print(f"Error getting {query_url}: response: {response.status_code}")
        return

    pre_trim = response.text[response.text.index("../c/")+5:]
    post_trim = pre_trim[:pre_trim.index("key.html")]
    return post_trim


def find_title_from_key(key):
    url = f"https://www.cleardarksky.com/c/{key}key.html"
    response = requests.get(url, headers={"User-Agnet": user_agent})
    text = response.text
    try:
        title_tag = text.index("<title>")
        clear = text.index("Clear")
        chart_title = response.text[title_tag+7:clear-1]
    except Exception as e:
        print(f"Error finding title: {e}\nresponse:\n{text}\n")
        return None
    return chart_title

def handle_add(api, query, tweet_id):
    key = None
    title = None

    print(f"Handling add for query '{query}'")

    while not key:
        key = find_key_from_query(query)
        if not key:
            print("Bad response getting key, trying again")
            time.sleep(5)
    print(f"Got key: {key}")

    while not title:
        title = find_title_from_key(key)
        if not title:
            print("Bad response getting title, trying again")
            time.sleep(5)

    print(f"Got title: {title}")

    if add_to_locations(key, title) == -1:
        body = f"{title} was the closest found location with Clear Sky Charts available, and it is already being published."
    else:
        body = f"{title} has been added to the list!"

    print(f"Posting tweet:\n{body}")

    api.update_status(
        status=body,
        in_reply_to_status_id=tweet_id
    )

def handle_show(api, query, tweet_id):
    key = None
    title = None

    print(f"Handling show for query '{query}'")

    while not key:
        key = find_key_from_query(query)
        if not key:
            print("Bad response getting key, trying again")
            time.sleep(5)
    print(f"Got key: {key}")

    while not title:
        title = find_title_from_key(key)
        if not title:
            print("Bad response getting title, trying again")
            time.sleep(5)

    chart = download_chart(key)
    infotext = f"How to read this chart: {build_key_url(key)}"
    print(f"Posting tweet:\nHere is the Clear Sky Chart for {title}.\n\n{infotext}\n<file: {chart}>")
    
    api.update_with_media(
        status=f"Here is the Clear Sky Chart for {title}.\n\n{infotext}",
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

def mentions_handler(api):

    since_id = read_last_mention_handled_id()

    print(f"Waiting for a mention...")
    try:
        while True:
            new_since_id = since_id

            for tweet in tweepy.Cursor(api.mentions_timeline, since_id=new_since_id).items():
                new_since_id = max(tweet.id, new_since_id)

                print(f"Received mention:\n'{tweet.text}'\n")

                text = tweet.text.lower()
                tweet_id = 5
                if "add" in text:
                    query = text[text.index("add")+4:]
                    handle_add(api, query, tweet.id)
                elif "show" in text:
                    query = text[text.index("show")+5:]
                    handle_show(api, query, tweet.id)

            update_last_mention_handled_id(new_since_id)
            time.sleep(10)
    except KeyboardInterrupt as e:
        update_last_mention_handled_id(new_since_id)


if __name__ == "__main__":
    api = twitter_api()
    print("Successfully setup Twitter API")

    daily_post_thread = Thread(target=daily_loop, args=(api, 17,))
    mentions_handler_thread = Thread(target=mentions_handler, args=(api,))

    daily_post_thread.start()
    mentions_handler_thread.start()
