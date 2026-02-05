"""Startup dialog for game creation/loading."""
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QListWidget, QPushButton, QComboBox, QTabWidget,
    QWidget, QCheckBox, QLineEdit, QGroupBox, QFormLayout,
    QFileDialog
)
from PySide6.QtCore import Qt

from core.world_loader import WorldLoader
from config.settings import get_settings, load_user_prefs, save_user_prefs


class StartupDialog(QDialog):
    """Dialog iniziale per selezione mondo/companion."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("LUNA RPG v3 - Session Setup")
        self.resize(600, 500)
        
        self.loader = WorldLoader()
        self.settings = get_settings()
        self.user_prefs = load_user_prefs()
        
        self.selected_world_id: Optional[str] = None
        self.selected_companion: Optional[str] = None
        self.mode: str = "new"  # 'new' o 'load'
        self.load_path: Optional[Path] = None
        
        self._setup_ui()
        self._load_worlds()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Tabs
        tabs = QTabWidget()
        
        # Tab 1: Nuova Partita
        tab_game = QWidget()
        game_layout = QVBoxLayout(tab_game)
        
        # World selector
        lbl_world = QLabel("[WRLD] Select World:")
        lbl_world.setStyleSheet("font-weight: bold; font-size: 14px;")
        game_layout.addWidget(lbl_world)
        
        self.combo_worlds = QComboBox()
        self.combo_worlds.currentIndexChanged.connect(self._on_world_changed)
        game_layout.addWidget(self.combo_worlds)
        
        # Companion selector
        lbl_char = QLabel("👤 Choose Partner:")
        lbl_char.setStyleSheet("font-weight: bold; font-size: 14px; margin-top: 10px;")
        game_layout.addWidget(lbl_char)
        
        self.list_companions = QListWidget()
        game_layout.addWidget(self.list_companions)
        
        # Load button
        btn_load = QPushButton("[L] Load Existing Save")
        btn_load.clicked.connect(self._on_load_click)
        game_layout.addWidget(btn_load)
        
        tabs.addTab(tab_game, "[GM] New Game")
        
        # Tab 2: Settings
        tab_settings = QWidget()
        settings_layout = QVBoxLayout(tab_settings)
        
        # GPU/RunPod
        gpu_group = QGroupBox("GPU Settings")
        gpu_form = QFormLayout()
        
        self.chk_runpod = QCheckBox("Use RunPod (Cloud GPU)")
        self.chk_runpod.setChecked(self.settings.is_runpod)
        self.chk_runpod.toggled.connect(self._toggle_runpod)
        gpu_form.addRow(self.chk_runpod)
        
        self.txt_runpod_url = QLineEdit()
        # Carica da preferenze utente (salvato) o da settings (.env)
        saved_runpod_id = self.user_prefs.get("runpod_id", self.settings.runpod_id)
        self.txt_runpod_url.setText(saved_runpod_id or "")
        self.txt_runpod_url.setPlaceholderText("Pod ID (e.g., abc123)")
        gpu_form.addRow("RunPod ID:", self.txt_runpod_url)
        
        gpu_group.setLayout(gpu_form)
        settings_layout.addWidget(gpu_group)
        
        # Info
        lbl_info = QLabel(
            f"Mode: {self.settings.execution_mode}\n"
            f"Local SD: {self.settings.local_sd_url}\n"
            f"Video: {'Available' if self.settings.video_available else 'Disabled'}"
        )
        lbl_info.setStyleSheet("color: gray; font-size: 11px;")
        settings_layout.addWidget(lbl_info)
        
        settings_layout.addStretch()
        tabs.addTab(tab_settings, "⚙️ Settings")
        
        layout.addWidget(tabs)
        
        # Start button
        btn_start = QPushButton("🚀 START ADVENTURE")
        btn_start.setStyleSheet(
            "background-color: #4CAF50; color: white; padding: 15px; "
            "font-weight: bold; font-size: 16px;"
        )
        btn_start.clicked.connect(self._on_start)
        layout.addWidget(btn_start)
        
        self._toggle_runpod()
    
    def _load_worlds(self):
        """Carica lista mondi."""
        worlds = self.loader.list_worlds()
        
        self.combo_worlds.clear()
        for w in worlds:
            display = f"{w['name']} ({w['genre']})"
            self.combo_worlds.addItem(display, w['id'])
        
        # Seleziona school_life se presente
        for i in range(self.combo_worlds.count()):
            if self.combo_worlds.itemData(i) == "school_life":
                self.combo_worlds.setCurrentIndex(i)
                break
        
        self._on_world_changed()
    
    def _on_world_changed(self):
        """Aggiorna lista companion quando cambia mondo."""
        world_id = self.combo_worlds.currentData()
        if not world_id:
            return
        
        world_data = self.loader.load_world(world_id)
        if world_data:
            companions = list(world_data.get("companions", {}).keys())
            self.list_companions.clear()
            self.list_companions.addItems(companions)
            self.list_companions.setCurrentRow(0)
    
    def _toggle_runpod(self):
        """Abilita/disabilita input RunPod."""
        self.txt_runpod_url.setEnabled(self.chk_runpod.isChecked())
    
    def _on_load_click(self):
        """Dialog caricamento save."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Game", 
            str(Path("storage/saves").absolute()),
            "JSON (*.json)"
        )
        if path:
            self.mode = "load"
            self.load_path = Path(path)
            self.accept()
    
    def _on_start(self):
        """Conferma e chiudi."""
        self.mode = "new"
        self.selected_world_id = self.combo_worlds.currentData()
        
        item = self.list_companions.currentItem()
        self.selected_companion = item.text() if item else "Luna"
        
        # Salva RunPod ID nelle preferenze utente per la prossima volta
        runpod_id = self.txt_runpod_url.text().strip()
        if runpod_id:
            self.user_prefs["runpod_id"] = runpod_id
            save_user_prefs(self.user_prefs)
        
        self.accept()
    
    def get_selection(self) -> dict:
        """Restituisce selezione utente."""
        return {
            "mode": self.mode,
            "world_id": self.selected_world_id,
            "companion": self.selected_companion,
            "load_path": self.load_path,
            "use_runpod": self.chk_runpod.isChecked(),
            "runpod_id": self.txt_runpod_url.text().strip()
        }
