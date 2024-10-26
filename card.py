from PyQt5.QtGui import QPixmap
import os

class Card:
  def __init__(self, card_data):
      """
      Initialize a card with either tuple data or dictionary data
      card_data can be either:
      - tuple: (id, name, mana_cost, type_line, power, toughness, abilities, image_path)
      - dict: Scryfall API response format
      """
      if isinstance(card_data, tuple):
          self.id = card_data[0]
          self.name = card_data[1]
          self.mana_cost = card_data[2]
          self.type_line = card_data[3]
          self.power = card_data[4]
          self.toughness = card_data[5]
          self.oracle_text = card_data[6]
          self.image_path = card_data[7]
      else:
          self.id = card_data.get('id', 0)
          self.name = card_data.get('name', '')
          self.mana_cost = card_data.get('mana_cost', '')
          self.type_line = card_data.get('type_line', '')
          self.power = card_data.get('power', '')
          self.toughness = card_data.get('toughness', '')
          self.oracle_text = card_data.get('oracle_text', '')
          self.image_path = card_data.get('image_path', '')

      # Game state attributes
      self.is_tapped = False
      self.summoning_sickness = True
      self.damage_marked = 0
      self.counters = {}
      self.enchantments = []
      self.equipment = []
      self.can_attack = False

  def tap(self):
      """Tap the card"""
      self.is_tapped = True

  def untap(self):
      """Untap the card"""
      self.is_tapped = False

  def is_land(self):
      """Check if card is a land"""
      return 'Land' in self.type_line

  def is_creature(self):
      """Check if card is a creature"""
      return 'Creature' in self.type_line

  def is_instant(self):
      """Check if card is an instant"""
      return 'Instant' in self.type_line

  def is_sorcery(self):
      """Check if card is a sorcery"""
      return 'Sorcery' in self.type_line

  def get_power(self):
      """Get creature's power"""
      try:
          return int(self.power)
      except (ValueError, TypeError):
          return 0

  def get_toughness(self):
      """Get creature's toughness"""
      try:
          return int(self.toughness)
      except (ValueError, TypeError):
          return 0

  def get_cmc(self):
      """Get converted mana cost"""
      if not self.mana_cost:
          return 0
      # Count number of mana symbols
      return len(self.mana_cost.replace('{', '').replace('}', ''))

  def get_mana_types(self):
      """Get mana types this card can produce"""
      if not self.is_land():
          return []
          
      mana_types = []
      if 'Plains' in self.type_line:
          mana_types.append('W')
      if 'Island' in self.type_line:
          mana_types.append('U')
      if 'Swamp' in self.type_line:
          mana_types.append('B')
      if 'Mountain' in self.type_line:
          mana_types.append('R')
      if 'Forest' in self.type_line:
          mana_types.append('G')
      
      # If no basic land types, return colorless
      return mana_types if mana_types else ['C']

  def get_pixmap(self):
      """Get card image as QPixmap"""
      if self.image_path and os.path.exists(self.image_path):
          return QPixmap(self.image_path)
      else:
          # Return default card back image
          default_image = os.path.join('card_images', 'card_back.jpg')
          if os.path.exists(default_image):
              return QPixmap(default_image)
          else:
              # Create blank pixmap if no image available
              pixmap = QPixmap(223, 310)  # Standard card size
              pixmap.fill()
              return pixmap

  def __str__(self):
      """String representation of card"""
      return f"{self.name} ({self.type_line})"

  def to_dict(self):
      """Convert card to dictionary format"""
      return {
          'id': self.id,
          'name': self.name,
          'mana_cost': self.mana_cost,
          'type_line': self.type_line,
          'power': self.power,
          'toughness': self.toughness,
          'oracle_text': self.oracle_text,
          'image_path': self.image_path
      }
