# deck_builder.py (updated)
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                         QLabel, QLineEdit, QListWidget, QComboBox, 
                         QSpinBox, QScrollArea, QGridLayout)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap

class CardWidget(QWidget):
  clicked = pyqtSignal(object)
  
  def __init__(self, card, parent=None):
      super().__init__(parent)
      self.card = card
      self.setup_ui()
      
  def setup_ui(self):
      layout = QVBoxLayout(self)
      
      # Card image
      image_label = QLabel()
      pixmap = self.card.get_pixmap().scaled(223, 310, Qt.KeepAspectRatio, 
                                           Qt.SmoothTransformation)
      image_label.setPixmap(pixmap)
      layout.addWidget(image_label)
      
      # Card name
      name_label = QLabel(self.card.name)
      name_label.setAlignment(Qt.AlignCenter)
      layout.addWidget(name_label)
      
  def mousePressEvent(self, event):
      if event.button() == Qt.LeftButton:
          self.clicked.emit(self.card)

class DeckBuilderApp(QWidget):
  def __init__(self, parent=None):
      super().__init__(parent)
      self.deck = []
      self.setup_ui()
      
  def setup_ui(self):
      main_layout = QHBoxLayout(self)
      
      # Left panel - Card browser
      browser_layout = QVBoxLayout()
      
      # Search and filters
      search_layout = QHBoxLayout()
      
      self.search_input = QLineEdit()
      self.search_input.setPlaceholderText("Search cards...")
      self.search_input.textChanged.connect(self.filter_cards)
      
      self.color_filter = QComboBox()
      self.color_filter.addItems(["All Colors", "White", "Blue", "Black", "Red", "Green"])
      self.color_filter.currentTextChanged.connect(self.filter_cards)
      
      self.type_filter = QComboBox()
      self.type_filter.addItems(["All Types", "Creature", "Instant", "Sorcery", "Enchantment", "Artifact", "Land"])
      self.type_filter.currentTextChanged.connect(self.filter_cards)
      
      self.cmc_filter = QSpinBox()
      self.cmc_filter.setSpecialValueText("Any CMC")
      self.cmc_filter.valueChanged.connect(self.filter_cards)
      
      search_layout.addWidget(self.search_input)
      search_layout.addWidget(self.color_filter)
      search_layout.addWidget(self.type_filter)
      search_layout.addWidget(self.cmc_filter)
      
      browser_layout.addLayout(search_layout)
      
      # Card grid
      self.card_grid = QGridLayout()
      self.card_scroll = QScrollArea()
      self.card_scroll.setWidgetResizable(True)
      card_widget = QWidget()
      card_widget.setLayout(self.card_grid)
      self.card_scroll.setWidget(card_widget)
      
      browser_layout.addWidget(self.card_scroll)
      
      # Right panel - Deck view
      deck_layout = QVBoxLayout()
      
      # Deck stats
      stats_layout = QHBoxLayout()
      self.card_count_label = QLabel("Cards: 0")
      self.avg_cmc_label = QLabel("Avg CMC: 0.00")
      stats_layout.addWidget(self.card_count_label)
      stats_layout.addWidget(self.avg_cmc_label)
      
      deck_layout.addLayout(stats_layout)
      
      # Deck list
      self.deck_list = QListWidget()
      deck_layout.addWidget(self.deck_list)
      
      # Deck controls
      control_layout = QHBoxLayout()
      
      save_button = QPushButton("Save Deck")
      save_button.clicked.connect(self.save_deck)
      
      load_button = QPushButton("Load Deck")
      load_button.clicked.connect(self.load_deck)
      
      clear_button = QPushButton("Clear Deck")
      clear_button.clicked.connect(self.clear_deck)
      
      control_layout.addWidget(save_button)
      control_layout.addWidget(load_button)
      control_layout.addWidget(clear_button)
      
      deck_layout.addLayout(control_layout)
      
      # Add panels to main layout
      main_layout.addLayout(browser_layout, stretch=2)
      main_layout.addLayout(deck_layout, stretch=1)
      
  def filter_cards(self):
      # Implement card filtering based on search and filter criteria
      query = self.search_input.text().lower()
      color = self.color_filter.currentText()
      card_type = self.type_filter.currentText()
      cmc = self.cmc_filter.value()
      
      # Clear current grid
      self.clear_card_grid()
      
      # Filter and display cards
      filtered_cards = self.filter_card_database(query, color, card_type, cmc)
      self.display_cards(filtered_cards)
      
  def filter_card_database(self, query, color, card_type, cmc):
      # Implement database filtering
      pass
      
  def display_cards(self, cards):
      # Display filtered cards in grid
      pass
      
  def clear_card_grid(self):
      # Clear the card grid
      while self.card_grid.count():
          item = self.card_grid.takeAt(0)
          if item.widget():
              item.widget().deleteLater()
              
  def add_card_to_deck(self, card):
      self.deck.append(card)
      self.update_deck_list()
      self.update_deck_stats()
      
  def update_deck_list(self):
      self.deck_list.clear()
      for card in self.deck:
          self.deck_list.addItem(card.name)
          
  def update_deck_stats(self):
      # Update deck statistics
      count = len(self.deck)
      self.card_count_label.setText(f"Cards: {count}")
      
      if count > 0:
          avg_cmc = sum(card.get_cmc() for card in self.deck) / count
          self.avg_cmc_label.setText(f"Avg CMC: {avg_cmc:.2f}")
          
  def save_deck(self):
      # Implement deck saving
      pass
      
  def load_deck(self):
      # Implement deck loading
      pass
      
  def clear_deck(self):
      self.deck.clear()
      self.update_deck_list()
      self.update_deck_stats()

# Created/Modified files during execution:
print("Modified deck_builder.py")
