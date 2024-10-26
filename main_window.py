# main_window.py
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                         QPushButton, QLabel, QStackedWidget, QMenuBar, QMenu,
                         QAction, QStatusBar)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from deck_builder import DeckBuilderApp
from game_play import GamePlayApp

class MTGGameWindow(QMainWindow):
  def __init__(self):
      super().__init__()
      self.setWindowTitle("Magic: The Gathering - Deck Testing")
      self.setGeometry(100, 100, 1200, 800)
      
      # Create central widget and main layout
      self.central_widget = QWidget()
      self.setCentralWidget(self.central_widget)
      self.main_layout = QVBoxLayout(self.central_widget)
      
      # Create stacked widget for different screens
      self.stacked_widget = QStackedWidget()
      self.main_layout.addWidget(self.stacked_widget)
      
      # Create menu bar
      self.create_menu_bar()
      
      # Create status bar
      self.statusBar = QStatusBar()
      self.setStatusBar(self.statusBar)
      
      # Create main menu screen
      self.create_main_menu()
      
      # Initialize game components
      self.deck_builder = None
      self.game_play = None

  def create_menu_bar(self):
      menubar = self.menuBar()
      
      # File menu
      file_menu = menubar.addMenu('File')
      
      new_game = QAction('New Game', self)
      new_game.setShortcut('Ctrl+N')
      new_game.triggered.connect(self.start_new_game)
      file_menu.addAction(new_game)
      
      deck_builder = QAction('Deck Builder', self)
      deck_builder.setShortcut('Ctrl+D')
      deck_builder.triggered.connect(self.open_deck_builder)
      file_menu.addAction(deck_builder)
      
      exit_action = QAction('Exit', self)
      exit_action.setShortcut('Ctrl+Q')
      exit_action.triggered.connect(self.close)
      file_menu.addAction(exit_action)
      
      # Help menu
      help_menu = menubar.addMenu('Help')
      
      rules = QAction('Game Rules', self)
      rules.triggered.connect(self.show_rules)
      help_menu.addAction(rules)
      
      about = QAction('About', self)
      about.triggered.connect(self.show_about)
      help_menu.addAction(about)

  def create_main_menu(self):
      menu_widget = QWidget()
      menu_layout = QVBoxLayout(menu_widget)
      menu_layout.setAlignment(Qt.AlignCenter)
      
      # Title
      title = QLabel("Magic: The Gathering\nDeck Testing")
      title.setAlignment(Qt.AlignCenter)
      title.setStyleSheet("font-size: 24px; font-weight: bold; margin: 20px;")
      menu_layout.addWidget(title)
      
      # Buttons
      button_style = """
          QPushButton {
              font-size: 16px;
              padding: 10px 20px;
              min-width: 200px;
              margin: 5px;
          }
      """
      
      new_game_btn = QPushButton("New Game")
      new_game_btn.clicked.connect(self.start_new_game)
      new_game_btn.setStyleSheet(button_style)
      menu_layout.addWidget(new_game_btn)
      
      deck_builder_btn = QPushButton("Deck Builder")
      deck_builder_btn.clicked.connect(self.open_deck_builder)
      deck_builder_btn.setStyleSheet(button_style)
      menu_layout.addWidget(deck_builder_btn)
      
      exit_btn = QPushButton("Exit")
      exit_btn.clicked.connect(self.close)
      exit_btn.setStyleSheet(button_style)
      menu_layout.addWidget(exit_btn)
      
      self.stacked_widget.addWidget(menu_widget)

  def start_new_game(self):
      if not self.game_play:
          self.game_play = GamePlayApp()
          self.stacked_widget.addWidget(self.game_play)
      self.stacked_widget.setCurrentWidget(self.game_play)
      self.statusBar.showMessage("Game started")

  def open_deck_builder(self):
      if not self.deck_builder:
          self.deck_builder = DeckBuilderApp()
          self.stacked_widget.addWidget(self.deck_builder)
      self.stacked_widget.setCurrentWidget(self.deck_builder)
      self.statusBar.showMessage("Deck Builder opened")

  def show_rules(self):
      # Implement rules dialog
      pass

  def show_about(self):
      # Implement about dialog
      pass

# Created/Modified files during execution:
print("Created main_window.py")
