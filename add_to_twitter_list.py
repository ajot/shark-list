import os
import sys
import requests
from dotenv import load_dotenv
from requests_oauthlib import OAuth1

# Load environment variables from .env
load_dotenv()

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("ACCESS_TOKEN_SECRET")
LIST_ID = os.getenv("LIST_ID")

if not all([API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET, LIST_ID]):
    print("❌ Missing one or more required values in .env:")
    print("   API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET, LIST_ID")
    sys.exit(1)

BASE_URL = "https://api.twitter.com/2"

# OAuth1 user-context auth
auth = OAuth1(
    API_KEY,
    API_SECRET,
    ACCESS_TOKEN,
    ACCESS_TOKEN_SECRET,
)

def get_user_id(username: str) -> str:
    """Look up the user ID for a given Twitter handle."""
    url = f"{BASE_URL}/users/by/username/{username}"
    response = requests.get(url, auth=auth)

    if response.status_code != 200:
        raise Exception(f"Error fetching user: {response.status_code} - {response.text}")

    data = response.json().get("data")
    if not data:
        raise Exception(f"User '{username}' not found.")
    return data["id"]

def add_to_list(user_id: str):
    """Add the user ID to the Twitter list."""
    url = f"{BASE_URL}/lists/{LIST_ID}/members"
    payload = {"user_id": user_id}

    response = requests.post(url, auth=auth, json=payload)

    if response.status_code == 200:
        print(f"✅ Added user {user_id} to list {LIST_ID}")
        print(response.text)
    else:
        raise Exception(f"Error adding to list: {response.status_code} - {response.text}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python add_to_twitter_list.py <twitter_handle>")
        sys.exit(1)

    handle = sys.argv[1].lstrip("@")
    print(f"🔍 Looking up {handle}...")

    try:
        user_id = get_user_id(handle)
        print(f"➡️  Found user_id: {user_id}")
        add_to_list(user_id)
    except Exception as e:
        print(f"❌ {e}")
