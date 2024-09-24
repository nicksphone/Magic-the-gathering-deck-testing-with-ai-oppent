# api.py

import requests

def fetch_card_data(card_name):
    """
    Fetch card data from the Scryfall API.
    """
    url = "https://api.scryfall.com/cards/named"
    params = {'fuzzy': card_name}  # Use 'fuzzy' matching to handle slight typos or different naming conventions
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as err:
        error_details = response.json().get('details', '')
        print(f"HTTP error fetching data for '{card_name}': {err}")
        print(f"Error details: {error_details}")
        return None
    except Exception as err:
        print(f"Error fetching data for '{card_name}': {err}")
        return None
