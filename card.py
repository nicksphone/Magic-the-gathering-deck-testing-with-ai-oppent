from PyQt5.QtGui import QPixmap
import os

class Card:
  def __init__(self, card_data):
      # Unpack card data tuple or use dictionary
      if isinstance(card_data, tuple):
          self.id, self.name, self.mana_cost, self.type_line, self.power, \
          self.toughness, self.abilities, self.image_path = card_data
      else:
          self.id = card_data.get('id', 0)
          self.name = card_data.get('name', '')
          self.mana_cost = card_data.get('mana_cost', '')
          self.type_line = card_data.get('type_line', '')
          self.power = card_data.get('power', '')
          self.toughness = card_data.get('toughness', '')
          self.abilities = card_data.get('abilities', '')
          self.image_path = card_data.get('image_path', '')

      self.is_tapped = False
      self.summoning_sickness = True
      self.damage_marked = 0
      self.counters = {}
      self.enchantments = []
      self.equipment = []

  def tap(self):
      self.is_tapped = True

  def untap(self):
      self.is_tapped = False

  def is_land(self):
      return 'Land' in self.type_line

  def is_creature(self):
      return 'Creature' in self.type_line

  def is_instant(self):
      return 'Instant' in self.type_line

  def is_sorcery(self):
      return 'Sorcery' in self.type_line

  def get_power(self):
      try:
          return int(self.power)
      except (ValueError, TypeError):
          return 0

  def get_toughness(self):
      try:
          return int(self.toughness)
      except (ValueError, TypeError):
          return 0

  def get_mana_types(self):
      """Returns list of mana types this land can produce"""
      if 'Forest' in self.type_line:
          return ['G']
      elif 'Mountain' in self.type_line:
          return ['R']
      elif 'Plains' in self.type_line:
          return ['W']
      elif 'Island' in self.type_line:
          return ['U']
      elif 'Swamp' in self.type_line:
          return ['B']
      return ['C']  # Colorless mana by default

  def get_pixmap(self):
      """Returns QPixmap for card image"""
      if self.image_path and os.path.exists(self.image_path):
          return QPixmap(self.image_path)
      else:
          # Return default card back image
          default_image = os.path.join('card_images', 'card_back.jpg')
          if os.path.exists(default_image):
              return QPixmap(default_image)
          else:
              # Create a blank pixmap if no image available
              pixmap = QPixmap(223, 310)  # Standard card size
              pixmap.fill()
              return pixmap

  def __str__(self):
      return f"{self.name} ({self.type_line})"
