"""Luna RPG v3 - Entry point."""
import sys
import asyncio

from PySide6.QtWidgets import QApplication
from qasync import QEventLoop

from ui.main_window import MainWindow


def main():
    """Main entry point."""
    # Crea applicazione Qt
    app = QApplication(sys.argv)
    app.setApplicationName("Luna RPG v3")
    app.setApplicationVersion("3.0.0")
    
    # Integrazione asyncio con Qt
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    # Crea finestra
    window = MainWindow()
    window.show()
    
    # Esegui con gestione pulita
    try:
        loop.run_forever()
    finally:
        loop.close()
    
    sys.exit(0)


if __name__ == "__main__":
    main()
