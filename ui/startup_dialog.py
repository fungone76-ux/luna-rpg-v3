"""Startup dialog for game creation/loading."""
import asyncio
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QListWidget, QPushButton, QComboBox, QTabWidget,
    QWidget, QCheckBox, QLineEdit, QGroupBox, QFormLayout,
    QMessageBox, QListWidgetItem
)
from PySide6.QtCore import Qt

from core.world_loader import WorldLoader
from core.database import db_manager, SessionModel
from config.settings import get_settings, load_user_prefs, save_user_prefs


class LoadGameDialog(QDialog):
    """Dialog per caricare una partita esistente dal database."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Load Game - Select Save")
        self.resize(500, 400)
        
        self.selected_session_id: Optional[int] = None
        
        self._setup_ui()
        self._load_saves()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Info
        info = QLabel("Seleziona una partita salvata:")
        info.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(info)
        
        # Lista salvataggi
        self.list_saves = QListWidget()
        self.list_saves.setStyleSheet("""
            QListWidget {
                background-color: #2d2d2d;
                border: 1px solid #444;
                border-radius: 4px;
                color: #fff;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #444;
            }
            QListWidget::item:selected {
                background-color: #4CAF50;
            }
        """)
        self.list_saves.itemDoubleClicked.connect(self.accept)
        layout.addWidget(self.list_saves)
        
        # Bottoni
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_cancel = QPushButton("❌ Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        
        btn_load = QPushButton("▶ Load Selected")
        btn_load.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
            }
        """)
        btn_load.clicked.connect(self.accept)
        btn_layout.addWidget(btn_load)
        
        layout.addLayout(btn_layout)
    
    def _load_saves(self):
        """Carica lista salvataggi dal database."""
        try:
            # Esegui query async in modo sincrono per semplicità
            import asyncio
            
            async def fetch_saves():
                async with db_manager.get_session() as db:
                    result = await db.execute(
                        db_manager.async_session.select(SessionModel)
                        .order_by(SessionModel.updated_at.desc())
                    )
                    return result.scalars().all()
            
            # Usa run_sync o crea un nuovo loop
            try:
                loop = asyncio.get_event_loop()
                saves = loop.run_until_complete(self._fetch_saves_async())
            except RuntimeError:
                # No running loop
                saves = asyncio.run(self._fetch_saves_async())
            
            self.list_saves.clear()
            for save in saves:
                item_text = f"{save.companion_name} - {save.world_id} - Turn {save.turn_count}"
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, save.id)
                item.setToolTip(f"Created: {save.created_at}\nUpdated: {save.updated_at}")
                self.list_saves.addItem(item)
            
            if not saves:
                self.list_saves.addItem("Nessuna partita salvata")
                
        except Exception as e:
            self.list_saves.addItem(f"Error loading saves: {e}")
    
    async def _fetch_saves_async(self) -> List[SessionModel]:
        """Fetch saves from database."""
        async with db_manager.get_session() as db:
            from sqlalchemy import select, desc
            result = await db.execute(
                select(SessionModel).order_by(desc(SessionModel.updated_at))
            )
            return list(result.scalars().all())
    
    def accept(self):
        """Conferma selezione."""
        item = self.list_saves.currentItem()
        if item:
            self.selected_session_id = item.data(Qt.UserRole)
        super().accept()
    
    def get_selected_session_id(self) -> Optional[int]:
        """Restituisce ID sessione selezionata."""
        return self.selected_session_id


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
        self.selected_session_id: Optional[int] = None
        self.mode: str = "new"  # 'new' o 'load'
        
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
        
        tabs.addTab(tab_game, "[GM] New Game")
        
        # Tab 2: Load Game (nuovo)
        tab_load = QWidget()
        load_layout = QVBoxLayout(tab_load)
        
        lbl_load = QLabel("📂 Carica partita esistente:")
        lbl_load.setStyleSheet("font-weight: bold; font-size: 14px;")
        load_layout.addWidget(lbl_load)
        
        # Lista salvataggi
        self.list_saves = QListWidget()
        self.list_saves.setStyleSheet("""
            QListWidget {
                background-color: #2d2d2d;
                border: 1px solid #444;
                border-radius: 4px;
                color: #fff;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #444;
            }
            QListWidget::item:selected {
                background-color: #4CAF50;
            }
        """)
        self.list_saves.itemDoubleClicked.connect(self._on_load_selected)
        load_layout.addWidget(self.list_saves)
        
        btn_refresh = QPushButton("🔄 Refresh List")
        btn_refresh.clicked.connect(self._load_saves_list)
        load_layout.addWidget(btn_refresh)
        
        tabs.addTab(tab_load, "[L] Load Game")
        
        # Tab 3: Settings
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
        self._load_saves_list()
    
    def _load_saves_list(self):
        """Carica lista salvataggi nel tab Load."""
        self.list_saves.clear()
        
        # Placeholder - verrà popolato quando il DB è disponibile
        self.list_saves.addItem("Click Refresh to load saves...")
    
    async def _fetch_saves_async(self) -> List[SessionModel]:
        """Fetch saves from database."""
        from sqlalchemy import select, desc
        async with db_manager.get_session() as db:
            result = await db.execute(
                select(SessionModel).order_by(desc(SessionModel.updated_at))
            )
            return list(result.scalars().all())
    
    def load_saves_sync(self):
        """Carica salvataggi (da chiamare quando il DB è inizializzato)."""
        try:
            import asyncio
            
            async def fetch():
                return await self._fetch_saves_async()
            
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Se siamo in un contesto async, crea un task
                    return None  # Non possiamo bloccare
                saves = loop.run_until_complete(fetch())
            except RuntimeError:
                saves = asyncio.run(fetch())
            
            self.list_saves.clear()
            for save in saves:
                updated_str = ""
                if hasattr(save, 'updated_at') and save.updated_at:
                    try:
                        updated_str = save.updated_at.strftime("%Y-%m-%d %H:%M")
                    except:
                        updated_str = str(save.updated_at)[:16]
                
                item_text = f"[{save.id}] {save.companion_name} - {save.world_id} (Turn {save.turn_count}) - {updated_str}"
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, save.id)
                self.list_saves.addItem(item)
            
            if not saves:
                self.list_saves.addItem("No saved games found")
                
        except Exception as e:
            self.list_saves.clear()
            self.list_saves.addItem(f"Error: {e}")
    
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
    
    def _on_load_selected(self):
        """Carica partita selezionata dalla lista."""
        item = self.list_saves.currentItem()
        if item and item.data(Qt.UserRole):
            self.selected_session_id = item.data(Qt.UserRole)
            self.mode = "load"
            self.accept()
    
    def _on_start(self):
        """Conferma e chiudi."""
        # Se siamo sul tab Load e c'è una selezione
        current_tab = self.findChild(QTabWidget).currentIndex()
        if current_tab == 1:  # Tab Load
            item = self.list_saves.currentItem()
            if item and item.data(Qt.UserRole):
                self.selected_session_id = item.data(Qt.UserRole)
                self.mode = "load"
                self.accept()
                return
            else:
                QMessageBox.warning(self, "No Selection", "Please select a saved game to load.")
                return
        
        # Altrimenti New Game
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
            "session_id": self.selected_session_id,
            "use_runpod": self.chk_runpod.isChecked(),
            "runpod_id": self.txt_runpod_url.text().strip()
        }
