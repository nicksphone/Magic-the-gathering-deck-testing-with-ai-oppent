iimport tkinter as tk
from tkinter import filedialog, messagebox
import sqlite3
import json

class DeckBuilderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Magic: The Gathering Deck Tester")
        self.deck = []
        self.create_widgets()
        
    def create_widgets(self):
        # Create a frame for the deck management section
        self.deck_frame = tk.Frame(self.root)
        self.deck_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Deck upload button
        self.upload_button = tk.Button(self.deck_frame, text="Upload Deck", command=self.upload_deck)
        self.upload_button.pack(pady=5)
        
        # Card search entry
        self.search_label = tk.Label(self.deck_frame, text="Search and Add Cards:")
        self.search_label.pack(pady=5)
        self.search_entry = tk.Entry(self.deck_frame)
        self.search_entry.pack(pady=5)
        
        # Search button
        self.search_button = tk.Button(self.deck_frame, text="Add Card", command=self.search_card)
        self.search_button.pack(pady=5)
        
        # Deck listbox
        self.deck_listbox = tk.Listbox(self.deck_frame)
        self.deck_listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Save deck button
        self.save_button = tk.Button(self.deck_frame, text="Save Deck", command=self.save_deck)
        self.save_button.pack(pady=5)
        
        # Load deck button
        self.load_button = tk.Button(self.deck_frame, text="Load Deck", command=self.load_deck)
        self.load_button.pack(pady=5)
        
        # Start game button
        self.start_button = tk.Button(self.root, text="Start Game", command=self.start_game)
        self.start_button.pack(side=tk.BOTTOM, pady=10)

    # Function to upload a deck from a file
    def upload_deck(self):
        file_path = filedialog.askopenfilename(filetypes=[("Deck files", "*.txt *.csv")])
        if file_path:
            with open(file_path, 'r') as file:
                cards = file.readlines()
                for card_name in cards:
                    card_name = card_name.strip()
                    card = fetch_and_store_card(card_name)
                    if card:
                        self.deck.append(card)
                        self.deck_listbox.insert(tk.END, card_name)

    # Function to search for a card and add it to the deck
    def search_card(self):
        card_name = self.search_entry.get()
        if card_name:
            card = fetch_and_store_card(card_name)
            if card:
                self.deck.append(card)
                self.deck_listbox.insert(tk.END, card_name)
                messagebox.showinfo("Card Added", f"'{card_name}' added to your deck.")
            else:
                messagebox.showerror("Card Not Found", f"Could not find '{card_name}'.")
        else:
            messagebox.showwarning("Input Required", "Please enter a card name.")
    
    # Function to save the deck to a file
    def save_deck(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
        if file_path:
            with open(file_path, 'w') as file:
                deck_data = [card[1] for card in self.deck]  # Save just the card names
                json.dump(deck_data, file)
                messagebox.showinfo("Deck Saved", "Your deck has been saved successfully.")
    
    # Function to load a deck from a file
    def load_deck(self):
        file_path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if file_path:
            with open(file_path, 'r') as file:
                deck_data = json.load(file)
                self.deck_listbox.delete(0, tk.END)  # Clear current deck
                self.deck = []
                for card_name in deck_data:
                    card = fetch_and_store_card(card_name)
                    if card:
                        self.deck.append(card)
                        self.deck_listbox.insert(tk.END, card_name)

    # Placeholder function for starting the game
    def start_game(self):
        if not self.deck:
            messagebox.showwarning("Empty Deck", "Please add cards to your deck before starting the game.")
            return
        self.deck_frame.destroy()
        self.start_button.destroy()
        self.game_app = GamePlayApp(self.root, self.deck)

# Initialize the application
if __name__ == "__main__":
    root = tk.Tk()
    app = DeckBuilderApp(root)
    root.mainloop()
