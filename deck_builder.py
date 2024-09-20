import wx
import json
import os
from card_retrieval import fetch_and_store_card  # Assuming this handles card retrieval logic

class DeckBuilderApp(wx.Frame):
    def __init__(self, parent, title):
        super(DeckBuilderApp, self).__init__(parent, title=title, size=(400, 300))
        
        self.deck = []
        self.InitUI()
        self.Centre()
        self.Show(True)
        
    def InitUI(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        # Deck upload button
        upload_btn = wx.Button(panel, label="Upload Deck")
        upload_btn.Bind(wx.EVT_BUTTON, self.upload_deck)
        vbox.Add(upload_btn, flag=wx.EXPAND|wx.ALL, border=5)
        
        # Card search input
        search_label = wx.StaticText(panel, label="Search and Add Cards:")
        vbox.Add(search_label, flag=wx.EXPAND|wx.ALL, border=5)
        
        self.search_entry = wx.TextCtrl(panel)
        vbox.Add(self.search_entry, flag=wx.EXPAND|wx.ALL, border=5)
        
        # Search button
        search_btn = wx.Button(panel, label="Add Card")
        search_btn.Bind(wx.EVT_BUTTON, self.search_card)
        vbox.Add(search_btn, flag=wx.EXPAND|wx.ALL, border=5)
        
        # Deck listbox
        self.deck_listbox = wx.ListBox(panel)
        vbox.Add(self.deck_listbox, proportion=1, flag=wx.EXPAND|wx.ALL, border=5)
        
        # Save and Load buttons
        save_btn = wx.Button(panel, label="Save Deck")
        save_btn.Bind(wx.EVT_BUTTON, self.save_deck)
        vbox.Add(save_btn, flag=wx.EXPAND|wx.ALL, border=5)
        
        load_btn = wx.Button(panel, label="Load Deck")
        load_btn.Bind(wx.EVT_BUTTON, self.load_deck)
        vbox.Add(load_btn, flag=wx.EXPAND|wx.ALL, border=5)
        
        # Start game button (placeholder for launching game)
        start_btn = wx.Button(panel, label="Start Game")
        start_btn.Bind(wx.EVT_BUTTON, self.start_game)
        vbox.Add(start_btn, flag=wx.EXPAND|wx.ALL, border=5)
        
        panel.SetSizer(vbox)
    
    def upload_deck(self, event):
        with wx.FileDialog(self, "Open Deck file", wildcard="Text files (*.txt)|*.txt|CSV files (*.csv)|*.csv",
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return  # User cancelled the operation
            
            # Proceed loading the file
            path = fileDialog.GetPath()
            with open(path, 'r') as file:
                cards = file.readlines()
                for card_name in cards:
                    card_name = card_name.strip()
                    card = fetch_and_store_card(card_name)
                    if card:
                        self.deck.append(card)
                        self.deck_listbox.Append(card_name)

    def search_card(self, event):
        card_name = self.search_entry.GetValue()
        if card_name:
            card = fetch_and_store_card(card_name)
            if card:
                self.deck.append(card)
                self.deck_listbox.Append(card_name)
                wx.MessageBox(f"'{card_name}' added to your deck.", "Card Added", wx.OK | wx.ICON_INFORMATION)
            else:
                wx.MessageBox(f"Could not find '{card_name}'.", "Card Not Found", wx.OK | wx.ICON_ERROR)
        else:
            wx.MessageBox("Please enter a card name.", "Input Required", wx.OK | wx.ICON_WARNING)

    def save_deck(self, event):
        with wx.FileDialog(self, "Save Deck", wildcard="JSON files (*.json)|*.json",
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return  # User cancelled the operation
            
            path = fileDialog.GetPath()
            deck_data = [card[1] for card in self.deck]  # Save card names
            with open(path, 'w') as file:
                json.dump(deck_data, file)
            wx.MessageBox("Your deck has been saved successfully.", "Deck Saved", wx.OK | wx.ICON_INFORMATION)

    def load_deck(self, event):
        with wx.FileDialog(self, "Load Deck", wildcard="JSON files (*.json)|*.json",
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return  # User cancelled the operation
            
            path = fileDialog.GetPath()
            with open(path, 'r') as file:
                deck_data = json.load(file)
                self.deck_listbox.Clear()  # Clear current deck
                self.deck = []
                for card_name in deck_data:
                    card = fetch_and_store_card(card_name)
                    if card:
                        self.deck.append(card)
                        self.deck_listbox.Append(card_name)

    def start_game(self, event):
        wx.MessageBox("Game play screen is under development.", "Start Game", wx.OK | wx.ICON_INFORMATION)

# Entry point for wxPython application
if __name__ == "__main__":
    app = wx.App(False)
    frame = DeckBuilderApp(None, "Magic: The Gathering Deck Tester")
    app.MainLoop()
