# api.py
import requests

def fetch_card_data(card_name):
    """
    Fetch card data from the Scryfall API.
    """
    url = f"https://api.scryfall.com/cards/named?exact={card_name}"
    response = requests.get(url)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error fetching data for {card_name}: {response.status_code}")
        return None
