"""Dialog for video action input."""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QTextEdit, QPushButton, QGroupBox
)
from PySide6.QtCore import Qt


class VideoActionDialog(QDialog):
    """Dialog per inserire l'azione desiderata per il video."""
    
    def __init__(self, character: str, location: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"🎬 Video Action - {character}")
        self.resize(500, 350)
        
        self.character = character
        self.location = location
        self.action_text = ""
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Info
        info = QLabel(f"<b>Character:</b> {self.character}<br><b>Location:</b> {self.location}")
        info.setStyleSheet("color: #666; padding: 5px;")
        layout.addWidget(info)
        
        # Context help
        help_box = QGroupBox("💡 Esempi")
        help_layout = QVBoxLayout(help_box)
        help_text = QLabel(
            "Scrivi liberamente cosa vuoi che faccia il personaggio.<br><br>"
            "<i>Esempi:</i><br>"
            "• Si sistema i capelli dietro l'orecchio<br>"
            "• Si gira lentamente verso di me<br>"
            "• Si china in avanti con le mani sulle ginocchia<br>"
            "• Alza la mano e mi fa cenno di avvicinarmi"
        )
        help_text.setWordWrap(True)
        help_text.setStyleSheet("font-size: 11px; color: #555;")
        help_layout.addWidget(help_text)
        layout.addWidget(help_box)
        
        # Input
        input_label = QLabel("📝 Descrivi l'azione:")
        input_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(input_label)
        
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText(
            "Es: Luna si sistema i capelli dietro l'orecchio, "
            "con lo sguardo verso di me in modo provocante..."
        )
        self.text_edit.setMinimumHeight(100)
        self.text_edit.setStyleSheet("""
            QTextEdit {
                font-size: 13px;
                padding: 8px;
                border: 2px solid #ccc;
                border-radius: 6px;
            }
            QTextEdit:focus {
                border-color: #ff9800;
            }
        """)
        layout.addWidget(self.text_edit)
        
        # Default action hint
        default_hint = QLabel("<i>Se lasci vuoto, verrà usata l'azione di default 'posing'</i>")
        default_hint.setStyleSheet("color: #888; font-size: 10px;")
        layout.addWidget(default_hint)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_cancel = QPushButton("❌ Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        
        btn_generate = QPushButton("▶ Generate Video")
        btn_generate.setStyleSheet("""
            QPushButton {
                background-color: #ff9800;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #f57c00;
            }
        """)
        btn_generate.clicked.connect(self._on_generate)
        btn_layout.addWidget(btn_generate)
        
        layout.addLayout(btn_layout)
    
    def _on_generate(self):
        """Conferma e chiudi."""
        self.action_text = self.text_edit.toPlainText().strip()
        self.accept()
    
    def get_action(self) -> str:
        """Restituisce l'azione inserita."""
        return self.action_text
