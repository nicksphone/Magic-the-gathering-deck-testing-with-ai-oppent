# Import the necessary modules from the game_play.py file
from game_play import GamePlayApp, Card
from PyQt5.QtWidgets import QApplication
import sys

# Define the main function
def main():
    # Sample player deck with creature and spell cards
    player_deck = [
        Card('Fire Elemental', 'creature', mana_cost=3, power=3, toughness=3, abilities=['flying']),
        Card('Healing Light', 'spell', mana_cost=2, ability='heal'),
        Card('Lightning Bolt', 'spell', mana_cost=1, ability='deal_damage'),
        Card('Trample Warrior', 'creature', mana_cost=4, power=4, toughness=4, abilities=['trample']),
        Card('Boost Spell', 'spell', mana_cost=2, ability='boost')
    ]
    
    # Sample AI deck
    ai_deck = [
        Card('AI Warrior', 'creature', mana_cost=2, power=2, toughness=2, abilities=['first strike']),
        Card('AI Spell', 'spell', mana_cost=3, ability='deal_damage')
    ]
    
    # Initialize the application
    app = QApplication(sys.argv)
    
    # Launch the game with the player and AI decks
    game_play = GamePlayApp(player_deck=player_deck, ai_deck=ai_deck)
    game_play.show()
    
    # Run the application
    sys.exit(app.exec_())

# Call the main function to start the game
if __name__ == '__main__':
    main()
