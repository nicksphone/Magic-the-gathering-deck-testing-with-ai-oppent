# game_play.py (updated)
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                         QLabel, QGraphicsView, QGraphicsScene, QFrame)
from PyQt5.QtCore import Qt, QRectF, QPointF, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QBrush, QPen, QColor, QTransform
import math

class CardGraphicsItem(QGraphicsItem):
  def __init__(self, card, parent=None):
      super().__init__(parent)
      self.card = card
      self.pixmap = card.get_pixmap()
      self.setAcceptHoverEvents(True)
      self.setAcceptDrops(True)
      self.setFlag(QGraphicsItem.ItemIsMovable)
      self.hover_animation = None
      self.is_tapped = False
      self.original_pos = None
      
  def boundingRect(self):
      return QRectF(0, 0, 63, 88)  # Standard card ratio
      
  def paint(self, painter, option, widget):
      painter.drawPixmap(self.boundingRect(), self.pixmap)
      if self.is_tapped:
          painter.rotate(90)
          
  def hoverEnterEvent(self, event):
      if not self.hover_animation:
          self.hover_animation = QPropertyAnimation(self, b"scale")
          self.hover_animation.setDuration(200)
          self.hover_animation.setStartValue(1.0)
          self.hover_animation.setEndValue(1.2)
          self.hover_animation.setEasingCurve(QEasingCurve.OutQuad)
      self.hover_animation.setDirection(QPropertyAnimation.Forward)
      self.hover_animation.start()
      
  def hoverLeaveEvent(self, event):
      if self.hover_animation:
          self.hover_animation.setDirection(QPropertyAnimation.Backward)
          self.hover_animation.start()

class BattlefieldView(QGraphicsView):
  def __init__(self, parent=None):
      super().__init__(parent)
      self.scene = QGraphicsScene(self)
      self.setScene(self.scene)
      self.setRenderHint(QPainter.Antialiasing)
      self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
      self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
      self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
      self.setFrameStyle(QFrame.NoFrame)
      
      # Set up zones
      self.setup_zones()
      
  def setup_zones(self):
      # Create battlefield zones
      self.zones = {
          'player_lands': QRectF(0, 400, 800, 100),
          'player_creatures': QRectF(0, 300, 800, 100),
          'player_other': QRectF(0, 200, 800, 100),
          'ai_lands': QRectF(0, 0, 800, 100),
          'ai_creatures': QRectF(0, 100, 800, 100),
          'ai_other': QRectF(0, 200, 800, 100)
      }
      
      # Draw zone boundaries
      pen = QPen(QColor(255, 255, 255, 30))
      for zone in self.zones.values():
          self.scene.addRect(zone, pen)

class GamePlayApp(QWidget):
  def __init__(self, parent=None):
      super().__init__(parent)
      self.setup_ui()
      self.setup_game_state()
      
  def setup_ui(self):
      main_layout = QVBoxLayout(self)
      
      # Top info bar
      info_bar = QHBoxLayout()
      self.ai_life_label = QLabel("AI Life: 20")
      self.phase_label = QLabel("Phase: Main 1")
      self.player_life_label = QLabel("Life: 20")
      info_bar.addWidget(self.ai_life_label)
      info_bar.addWidget(self.phase_label)
      info_bar.addWidget(self.player_life_label)
      main_layout.addLayout(info_bar)
      
      # Battlefield
      self.battlefield = BattlefieldView()
      main_layout.addWidget(self.battlefield)
      
      # Hand container
      self.hand_container = QGraphicsView()
      self.hand_scene = QGraphicsScene()
      self.hand_container.setScene(self.hand_scene)
      self.hand_container.setMaximumHeight(150)
      self.hand_container.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
      main_layout.addWidget(self.hand_container)
      
      # Control buttons
      button_layout = QHBoxLayout()
      
      self.phase_button = QPushButton("Next Phase")
      self.phase_button.clicked.connect(self.next_phase)
      
      self.attack_button = QPushButton("Attack")
      self.attack_button.clicked.connect(self.declare_attackers)
      
      self.resolve_button = QPushButton("Resolve")
      self.resolve_button.clicked.connect(self.resolve_stack)
      
      button_layout.addWidget(self.phase_button)
      button_layout.addWidget(self.attack_button)
      button_layout.addWidget(self.resolve_button)
      
      main_layout.addLayout(button_layout)
      
  def setup_game_state(self):
      self.game_state = GameStateManager()
      self.combat_manager = CombatManager()
      self.stack = []
      self.current_phase = "Main 1"
      self.update_phase_label()
      
  def update_phase_label(self):
      self.phase_label.setText(f"Phase: {self.current_phase}")
      
  def next_phase(self):
      # Implement phase progression
      phases = ["Main 1", "Combat", "Main 2", "End"]
      current_index = phases.index(self.current_phase)
      self.current_phase = phases[(current_index + 1) % len(phases)]
      self.update_phase_label()
      
      # Handle phase-specific actions
      if self.current_phase == "End":
          self.end_turn()
          
  def declare_attackers(self):
      if self.current_phase != "Combat":
          return
          
      # Enable creature selection for attacking
      for creature in self.battlefield.get_creatures():
          if creature.can_attack():
              creature.setFlag(QGraphicsItem.ItemIsSelectable, True)
              
  def resolve_stack(self):
      if not self.stack:
          return
          
      spell = self.stack.pop()
      self.resolve_spell(spell)
      
  def resolve_spell(self, spell):
      # Implement spell resolution
      pass
      
  def end_turn(self):
      # Implement end of turn actions
      self.current_phase = "Main 1"
      self.update_phase_label()
      self.game_state.end_turn()
      
  def add_card_to_hand(self, card):
      card_item = CardGraphicsItem(card)
      self.hand_scene.addItem(card_item)
      self.arrange_hand()
      
  def arrange_hand(self):
      cards = self.hand_scene.items()
      card_width = 63
      spacing = 10
      total_width = len(cards) * (card_width + spacing)
      start_x = (self.hand_container.width() - total_width) / 2
      
      for i, card in enumerate(cards):
          pos = QPointF(start_x + i * (card_width + spacing), 10)
          if card.pos() != pos:
              animation = QPropertyAnimation(card, b"pos")
              animation.setDuration(200)
              animation.setStartValue(card.pos())
              animation.setEndValue(pos)
              animation.start()

# Created/Modified files during execution:
print("Modified game_play.py")
