# logger.py

import logging

class Logger:
    """
    Logs game actions and events.
    """
    def __init__(self):
        self.logs = []
        logging.basicConfig(filename='game.log', level=logging.INFO, format='%(message)s')

    def record(self, message):
        self.logs.append(message)
        logging.info(message)
