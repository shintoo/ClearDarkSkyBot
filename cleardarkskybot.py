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


def download_chart(location_row):
    filename = f"{location_row[1]}csk.gif"
    url = f"https://www.cleardarksky.com/c/{filename}?c=212425"
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 12_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/12.0 Mobile/15E148 Safari/604.1"})
    if response.status_code == 200:
        with open(filename, "wb") as f:
            f.write(response.content)
    else:
        print(f"Error getting image for {location_row[1]}: response: {response.status_code}")

    return filename


def wait_until_5pm():
    now = datetime.now()
    five = now.replace(hour=17, minute=0, second=0, microsecond=0)

    # If it's already past 5pm today
    if now > five:
        # Wait until five tomorrow (add one day to posix timestamp,
        # make new datetime from resulting posix timestamp)
        five = datetime.fromtimestamp(five.timestamp() + (24 * 60 * 60))

    print(f"Sleeping until {five}")
    time.sleep(five.timestamp() - now.timestamp())

if __name__ == "__main__":
    api = twitter_api()
    print("Successfully setup Twitter API")

    locations = read_locations()

    wait_until_5pm()

    while True:
        for location in locations:
            body = tweet_body(location)
            filename = download_chart(location)
            api.update_with_media(filename=filename, status=body)
            print(f"Posting tweet:\n{body}")

        print("Sleeping for 24h...")
        time.sleep(24 * 60 * 60)
