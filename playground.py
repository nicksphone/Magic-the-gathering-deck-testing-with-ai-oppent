# playground.py
import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QLabel
from game_state_manager import GameStateManager
from card import Card  # Assuming you have a Card class defined
from ai_player import AIPlayer  # Assuming you have an AIPlayer class defined

class Playground(QMainWindow):
  def __init__(self):
      super().__init__()
      self.setWindowTitle("Magic: The Gathering Playground")
      self.setGeometry(100, 100, 800, 600)

      self.game_state = GameStateManager()
      self.ai_player = AIPlayer(deck=[])  # Initialize with an empty deck for now

      self.initUI()

  def initUI(self):
      layout = QVBoxLayout()

      self.status_label = QLabel("Welcome to the MTG Playground!")
      layout.addWidget(self.status_label)

      self.start_game_button = QPushButton("Start Game")
      self.start_game_button.clicked.connect(self.start_game)
      layout.addWidget(self.start_game_button)

      self.end_turn_button = QPushButton("End Turn")
      self.end_turn_button.clicked.connect(self.end_turn)
      layout.addWidget(self.end_turn_button)

      container = QWidget()
      container.setLayout(layout)
      self.setCentralWidget(container)

  def start_game(self):
      # Initialize game state and start the game
      self.status_label.setText("Game Started!")
      self.game_state.turn_number = 1
      self.game_state.active_player = 'player'
      self.game_state.player_life = 20
      self.game_state.ai_life = 20
      # Load decks, etc.

  def end_turn(self):
      # Logic to end the turn and switch to AI's turn
      self.status_label.setText("Ending turn...")
      self.game_state.active_player = 'ai'
      self.ai_player.take_turn(self.game_state)  # AI takes its turn
      self.status_label.setText("AI's turn!")

if __name__ == '__main__':
  app = QApplication(sys.argv)
  playground = Playground()
  playground.show()
  sys.exit(app.exec_())
