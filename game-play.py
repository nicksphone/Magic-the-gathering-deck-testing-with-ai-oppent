import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel

class GamePlayApp(QWidget):
    def __init__(self, parent=None, player_deck=None):
        super().__init__(parent)
        self.player_deck = player_deck or []
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Magic: The Gathering - Game Play')
        self.setGeometry(300, 300, 600, 400)

        vbox = QVBoxLayout()

        # Hand display
        hand_label = QLabel(f"Your Hand: {len(self.player_deck)} cards", self)
        vbox.addWidget(hand_label)

        # Battlefield display (placeholder)
        battlefield_label = QLabel("Battlefield: [To be implemented]", self)
        vbox.addWidget(battlefield_label)

        self.setLayout(vbox)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    game_play = GamePlayApp()
    game_play.show()
    sys.exit(app.exec_())
