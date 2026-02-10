"""Luna RPG v3 - Entry point."""
import sys
import asyncio
import logging
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import QApplication
from qasync import QEventLoop

from ui.main_window import MainWindow


class SessionLogger:
    """Logger completo per sessione di gioco - UNICO FILE."""
    
    def __init__(self, filepath):
        self.filepath = filepath
        self.terminal_out = sys.stdout
        self.terminal_err = sys.stderr
        self.file = open(filepath, 'w', encoding='utf-8')
        self.start_time = datetime.now()
        self.turn_count = 0
        
        # Header iniziale
        self._write_header()
    
    def _write_header(self):
        """Scrive header del log."""
        self.file.write(f"{'=' * 80}\n")
        self.file.write(f"LUNA RPG v3 - SESSION LOG\n")
        self.file.write(f"Start: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        self.file.write(f"File: {self.filepath.name}\n")
        self.file.write(f"{'=' * 80}\n\n")
        self.file.flush()
    
    def _timestamp(self):
        return datetime.now().strftime('%H:%M:%S.%f')[:-3]
    
    def write(self, message):
        """Scrive su terminale e file."""
        self.terminal_out.write(message)
        self.terminal_out.flush()
        
        lines = message.split('\n')
        for line in lines:
            if line or message.endswith('\n'):
                self.file.write(f"[{self._timestamp()}] {line}\n")
        self.file.flush()
    
    def log_user_input(self, text):
        """Logga input utente in modo evidenziato."""
        self.turn_count += 1
        entry = f"\n{'=' * 80}\n"
        entry += f"TURNO #{self.turn_count} - INPUT UTENTE\n"
        entry += f"{'=' * 80}\n"
        entry += f"{text}\n"
        entry += f"{'=' * 80}\n"
        
        self.terminal_out.write(entry)
        self.terminal_out.flush()
        self.file.write(entry)
        self.file.flush()
    
    def log_ai_response(self, text, metadata=None):
        """Logga risposta AI in modo evidenziato."""
        entry = f"\n[{'=' * 40}]\n"
        entry += f"RISPOSTA PERSONAGGIO\n"
        entry += f"[{'=' * 40}]\n"
        entry += f"{text}\n"
        
        if metadata:
            entry += f"\n--- Metadati ---\n"
            for key, value in metadata.items():
                entry += f"{key}: {value}\n"
        
        entry += f"[{'=' * 40}]\n"
        
        self.terminal_out.write(entry)
        self.terminal_out.flush()
        self.file.write(entry)
        self.file.flush()
    
    def log_event(self, category, message):
        """Logga evento strutturato."""
        timestamp = self._timestamp()
        entry = f"[{timestamp}][{category}] {message}\n"
        
        self.terminal_out.write(entry)
        self.terminal_out.flush()
        self.file.write(entry)
        self.file.flush()
    
    def flush(self):
        self.terminal_out.flush()
        self.file.flush()
    
    def close(self):
        """Chiude il log con footer."""
        end_time = datetime.now()
        duration = end_time - self.start_time
        
        footer = f"\n{'=' * 80}\n"
        footer += f"FINE SESSIONE\n"
        footer += f"End: {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        footer += f"Durata: {duration}\n"
        footer += f"Totale Turni: {self.turn_count}\n"
        footer += f"{'=' * 80}\n"
        
        self.terminal_out.write(footer)
        self.file.write(footer)
        self.file.close()


class StderrLogger:
    """Wrapper per stderr che logga anche su file."""
    
    def __init__(self, session_logger):
        self.session_logger = session_logger
        self.terminal = sys.stderr
    
    def write(self, message):
        self.terminal.write(message)
        self.terminal.flush()
        
        lines = message.split('\n')
        for line in lines:
            if line:
                self.session_logger.log_event("ERROR", line)
    
    def flush(self):
        self.terminal.flush()


# Global logger
session_logger = None


def setup_logging():
    """Configura il logging su un unico file."""
    global session_logger
    
    # Crea cartella logs
    logs_dir = Path('logs')
    logs_dir.mkdir(exist_ok=True)
    
    # Nome file fisso per sessione
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = logs_dir / f'session_{timestamp}.txt'
    
    # Crea logger
    session_logger = SessionLogger(log_file)
    
    # Redirigi stdout e stderr
    sys.stdout = session_logger
    sys.stderr = StderrLogger(session_logger)
    
    # Configura logging module
    logging.basicConfig(
        level=logging.DEBUG,
        format='[%(asctime)s][%(levelname)s] %(message)s',
        datefmt='%H:%M:%S',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8', mode='a'),
        ]
    )
    
    # Log iniziale
    session_logger.log_event("SYSTEM", f"Logging avviato: {log_file}")
    
    return session_logger


def main():
    """Main entry point."""
    # Setup logging
    logger = setup_logging()
    
    try:
        # Crea applicazione Qt
        app = QApplication(sys.argv)
        app.setApplicationName("Luna RPG v3")
        app.setApplicationVersion("3.0.0")
        
        # Integrazione asyncio con Qt
        loop = QEventLoop(app)
        asyncio.set_event_loop(loop)
        
        # Crea finestra con riferimento al logger
        window = MainWindow()
        window.session_logger = logger  # Passa logger alla UI
        window.show()
        
        # Esegui
        try:
            loop.run_forever()
        finally:
            loop.close()
            
    except Exception as e:
        logging.exception("Errore fatale:")
        raise
    finally:
        if session_logger:
            session_logger.close()
            # Ripristina stdout/stderr
            sys.stdout = session_logger.terminal_out
            sys.stderr = session_logger.terminal_err
    
    sys.exit(0)


if __name__ == "__main__":
    main()
