# image_loader.py

import requests
from PIL import Image, ImageTk
from io import BytesIO
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_card_image(image_url, size=(100, 150)):
    """
    Loads the card image from the provided image URL.
    
    Args:
        image_url (str): The URL of the card image.
        size (tuple): Desired size of the image (width, height).
    
    Returns:
        ImageTk.PhotoImage: The image to display in the GUI or None if not available.
    """
    if not image_url:
        logger.warning("No image URL provided.")
        return None
    try:
        response = requests.get(image_url)
        response.raise_for_status()
        image_data = BytesIO(response.content)
        pil_image = Image.open(image_data)
        pil_image = pil_image.resize(size, Image.ANTIALIAS)
        return ImageTk.PhotoImage(pil_image)
    except Exception as e:
        logger.error(f"Error loading image from '{image_url}': {e}")
        return None
