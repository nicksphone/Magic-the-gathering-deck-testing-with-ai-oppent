# main.py (updated)
import sys
from PyQt5.QtWidgets import QApplication
from main_window import MTGGameWindow

def main():
  app = QApplication(sys.argv)
  
  # Set application-wide stylesheet
  app.setStyleSheet("""
      QMainWindow {
          background-color: #f0f0f0;
      }
      QLabel {
          color: #333333;
      }
      QPushButton {
          background-color: #4a90e2;
          color: white;
          border: none;
          border-radius: 4px;
      }
      QPushButton:hover {
          background-color: #357abd;
      }
      QPushButton:pressed {
          background-color: #2a5f9e;
      }
  """)
  
  window = MTGGameWindow()
  window.show()
  
  sys.exit(app.exec_())

if __name__ == '__main__':
  main()

# Created/Modified files during execution:
print("Modified main.py")
