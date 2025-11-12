import os
import logging
import requests
from requests_oauthlib import OAuth1
from flask import current_app

logger = logging.getLogger(__name__)


class TwitterService:
    """Service for interacting with Twitter API v2"""

    BASE_URL = "https://api.twitter.com/2"

    def __init__(self):
        """Initialize Twitter API authentication"""
        self.auth = OAuth1(
            current_app.config['TWITTER_API_KEY'],
            current_app.config['TWITTER_API_SECRET'],
            current_app.config['TWITTER_ACCESS_TOKEN'],
            current_app.config['TWITTER_ACCESS_TOKEN_SECRET'],
        )
        self.list_id = current_app.config['TWITTER_LIST_ID']

    def get_user_id(self, username: str) -> str:
        """
        Look up the user ID for a given Twitter handle.

        Args:
            username: Twitter handle (with or without @)

        Returns:
            str: Twitter user ID

        Raises:
            Exception: If user not found or API error occurs
        """
        # Remove @ if present
        username = username.lstrip('@')

        url = f"{self.BASE_URL}/users/by/username/{username}"

        try:
            response = requests.get(url, auth=self.auth)

            if response.status_code == 404:
                raise Exception(f"User '@{username}' not found")

            if response.status_code == 429:
                rate_limit_reset = response.headers.get('x-rate-limit-reset', 'unknown')
                remaining = response.headers.get('x-rate-limit-remaining', 'unknown')

                # Convert reset timestamp to readable time
                from datetime import datetime
                try:
                    reset_time = datetime.fromtimestamp(int(rate_limit_reset)).strftime('%Y-%m-%d %H:%M:%S')
                    logger.error(f"Rate limit exceeded: get_user_id(@{username}). Remaining: {remaining}, Reset at: {reset_time} (timestamp: {rate_limit_reset})")
                    raise Exception(f"Twitter API rate limit exceeded. Resets at {reset_time}. Please wait and try again.")
                except:
                    logger.error(f"Rate limit exceeded: get_user_id(@{username}). Remaining: {remaining}, Reset: {rate_limit_reset}")
                    raise Exception("Twitter API rate limit exceeded. Please try again later.")

            if response.status_code != 200:
                logger.error(f"Twitter API error: {response.status_code} - {response.text}")
                raise Exception(f"Error fetching user: {response.status_code}")

            data = response.json().get("data")
            if not data:
                raise Exception(f"User '@{username}' not found")

            logger.info(f"Found user ID {data['id']} for @{username}")
            return data["id"]

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {str(e)}")
            raise Exception(f"Network error while fetching user: {str(e)}")

    def add_to_list(self, user_id: str) -> bool:
        """
        Add a user to the Twitter list.

        Args:
            user_id: Twitter user ID

        Returns:
            bool: True if successful

        Raises:
            Exception: If API error occurs
        """
        url = f"{self.BASE_URL}/lists/{self.list_id}/members"
        payload = {"user_id": user_id}

        try:
            response = requests.post(url, auth=self.auth, json=payload)

            if response.status_code == 429:
                rate_limit_reset = response.headers.get('x-rate-limit-reset', 'unknown')
                remaining = response.headers.get('x-rate-limit-remaining', 'unknown')
                logger.error(f"Rate limit exceeded: add_to_list(user_id={user_id}). Remaining: {remaining}, Reset: {rate_limit_reset}")
                raise Exception("Twitter API rate limit exceeded. Please try again later.")

            # User already in list is considered success
            if response.status_code == 403:
                error_data = response.json()
                if "errors" in error_data:
                    for error in error_data["errors"]:
                        if "already a member" in error.get("message", "").lower():
                            logger.warning(f"User {user_id} already in list")
                            return True

            if response.status_code != 200:
                logger.error(f"Twitter API error: {response.status_code} - {response.text}")
                raise Exception(f"Error adding to list: {response.status_code}")

            logger.info(f"Successfully added user {user_id} to list {self.list_id}")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {str(e)}")
            raise Exception(f"Network error while adding to list: {str(e)}")

    def remove_from_list(self, user_id: str) -> bool:
        """
        Remove a user from the Twitter list.

        Args:
            user_id: Twitter user ID

        Returns:
            bool: True if successful

        Raises:
            Exception: If API error occurs
        """
        url = f"{self.BASE_URL}/lists/{self.list_id}/members/{user_id}"

        try:
            response = requests.delete(url, auth=self.auth)

            if response.status_code == 429:
                rate_limit_reset = response.headers.get('x-rate-limit-reset', 'unknown')
                remaining = response.headers.get('x-rate-limit-remaining', 'unknown')
                logger.error(f"Rate limit exceeded: remove_from_list(user_id={user_id}). Remaining: {remaining}, Reset: {rate_limit_reset}")
                raise Exception("Twitter API rate limit exceeded. Please try again later.")

            if response.status_code == 404:
                logger.warning(f"User {user_id} not found in list")
                return True  # User already not in list

            if response.status_code != 200:
                logger.error(f"Twitter API error: {response.status_code} - {response.text}")
                raise Exception(f"Error removing from list: {response.status_code}")

            logger.info(f"Successfully removed user {user_id} from list {self.list_id}")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {str(e)}")
            raise Exception(f"Network error while removing from list: {str(e)}")

    def get_list_info(self) -> dict:
        """
        Get information about the Twitter list.

        Returns:
            dict: List information

        Raises:
            Exception: If API error occurs
        """
        url = f"{self.BASE_URL}/lists/{self.list_id}"

        try:
            response = requests.get(url, auth=self.auth)

            if response.status_code != 200:
                logger.error(f"Twitter API error: {response.status_code} - {response.text}")
                raise Exception(f"Error fetching list info: {response.status_code}")

            return response.json().get("data", {})

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {str(e)}")
            raise Exception(f"Network error while fetching list info: {str(e)}")

    def get_list_members(self) -> list:
        """
        Get all members of the Twitter list with pagination support.

        Returns:
            list: List of member dictionaries with 'id', 'username', and 'name'

        Raises:
            Exception: If API error occurs
        """
        url = f"{self.BASE_URL}/lists/{self.list_id}/members"
        members = []
        pagination_token = None
        max_results = 100  # Twitter API max per request

        try:
            while True:
                params = {
                    "max_results": max_results,
                    "user.fields": "id,username,name"
                }

                if pagination_token:
                    params["pagination_token"] = pagination_token

                response = requests.get(url, auth=self.auth, params=params)

                if response.status_code == 429:
                    rate_limit_reset = response.headers.get('x-rate-limit-reset', 'unknown')
                    remaining = response.headers.get('x-rate-limit-remaining', 'unknown')
                    logger.error(f"Rate limit exceeded: get_list_members(page={len(members)//max_results + 1}). Remaining: {remaining}, Reset: {rate_limit_reset}")
                    raise Exception("Twitter API rate limit exceeded. Please try again later.")

                if response.status_code != 200:
                    logger.error(f"Twitter API error: {response.status_code} - {response.text}")
                    raise Exception(f"Error fetching list members: {response.status_code}")

                data = response.json()

                # Add members from this page
                page_members = data.get("data", [])
                members.extend(page_members)

                logger.info(f"Fetched {len(page_members)} members (total: {len(members)})")

                # Check if there are more pages
                meta = data.get("meta", {})
                pagination_token = meta.get("next_token")

                if not pagination_token:
                    break  # No more pages

            logger.info(f"Successfully fetched {len(members)} total members from list {self.list_id}")
            return members

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {str(e)}")
            raise Exception(f"Network error while fetching list members: {str(e)}")
