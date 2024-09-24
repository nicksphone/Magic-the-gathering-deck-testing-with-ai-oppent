# image_downloader.py

import os
import requests

def download_image(image_url, card_name):
    """
    Download the card image from the given URL and save it locally.
    Returns the local path to the image.
    """
    if image_url:
        response = requests.get(image_url)
        if response.status_code == 200:
            image_folder = "card_images"
            os.makedirs(image_folder, exist_ok=True)  # Create the folder if it doesn't exist
            safe_card_name = card_name.replace('/', '_')  # Replace '/' to prevent file path issues
            image_path = os.path.join(image_folder, f"{safe_card_name}.jpg")
            
            with open(image_path, 'wb') as img_file:
                img_file.write(response.content)
            print(f"Image saved for {card_name}")
            return image_path
        else:
            print(f"Error downloading image for {card_name}: {response.status_code}")
    return None
