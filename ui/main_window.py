"""Main application window with Quest System v3 UI."""
import asyncio
from pathlib import Path
from typing import Optional, List

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QLabel, 
    QCheckBox, QFileDialog, QSplitter,
    QListWidget, QListWidgetItem, QGroupBox, QGridLayout, QMessageBox,
    QDialog, QScrollArea, QComboBox, QTabWidget,
    QProgressBar, QFrame, QToolTip
)
from PySide6.QtCore import Qt, QTimer, QRect
from PySide6.QtGui import QPixmap, QFont
from qasync import asyncSlot, asyncClose

from core.engine import GameEngine
from core.database import db_manager
from media.video_client import VideoClient
from ui.startup_dialog import StartupDialog
from ui.video_action_dialog import VideoActionDialog


class QuestTrackerWidget(QGroupBox):
    """Widget per tracciare le quest attive."""
    
    def __init__(self, parent=None):
        super().__init__("📋 Quest Tracker", parent)
        self.setMaximumHeight(200)
        
        layout = QVBoxLayout(self)
        
        # Lista quest attive
        self.quest_list = QListWidget()
        self.quest_list.setStyleSheet("""
            QListWidget {
                background-color: #2d2d2d;
                border: 1px solid #444;
                border-radius: 4px;
                color: #fff;
            }
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #444;
            }
        """)
        layout.addWidget(self.quest_list)
        
        # Label dettaglio quest selezionata
        self.lbl_quest_detail = QLabel("Nessuna quest attiva")
        self.lbl_quest_detail.setWordWrap(True)
        self.lbl_quest_detail.setStyleSheet("color: #aaa; font-size: 11px;")
        layout.addWidget(self.lbl_quest_detail)
        
        self.quest_list.currentRowChanged.connect(self._on_quest_selected)
    
    def _on_quest_selected(self, row):
        """Mostra dettaglio quando selezionata."""
        if row >= 0:
            item = self.quest_list.item(row)
            if item:
                tooltip = item.toolTip()
                self.lbl_quest_detail.setText(tooltip)
    
    def update_quests(self, quest_states: List[dict]):
        """Aggiorna lista quest."""
        self.quest_list.clear()
        
        for quest in quest_states:
            status_icon = "🟢" if quest['status'] == 'active' else "✅" if quest['status'] == 'completed' else "🔴"
            item_text = f"{status_icon} {quest['title']}"
            
            item = QListWidgetItem(item_text)
            item.setToolTip(f"Stage: {quest.get('stage', 'N/A')}\n{quest.get('description', '')}")
            
            # Colore diverso per completate
            if quest['status'] == 'completed':
                item.setForeground(Qt.gray)
            
            self.quest_list.addItem(item)


class GlobalEventWidget(QGroupBox):
    """Widget per mostrare evento globale attivo."""
    
    def __init__(self, parent=None):
        super().__init__("🌍 Active Event", parent)
        
        layout = QVBoxLayout(self)
        
        self.lbl_event = QLabel("No active events")
        self.lbl_event.setWordWrap(True)
        self.lbl_event.setStyleSheet("color: #aaa; font-size: 11px; padding: 5px;")
        
        layout.addWidget(self.lbl_event)
        layout.addStretch()
    
    def set_event(self, title: str, description: str, icon: str = "🌍"):
        """Mostra evento attivo."""
        if title:
            self.setTitle(f"{icon} Active Event")
            self.lbl_event.setText(f"<b>{title}</b><br/>{description}")
            self.lbl_event.setStyleSheet("color: #4CAF50; font-size: 11px; padding: 5px; background-color: #1a3a1a; border-radius: 4px;")
        else:
            self.setTitle("🌍 Active Event")
            self.lbl_event.setText("No active events")
            self.lbl_event.setStyleSheet("color: #aaa; font-size: 11px; padding: 5px;")


class CompanionStatusWidget(QGroupBox):
    """Widget compatto per stato di tutte le companion."""
    
    def __init__(self, parent=None):
        super().__init__("👥 All Companions", parent)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        layout.setContentsMargins(8, 12, 8, 8)
        
        self.companion_bars = {}
        
        # Stile per le barre
        self.setStyleSheet("""
            QProgressBar {
                border: 1px solid #444;
                border-radius: 3px;
                text-align: center;
                color: white;
                font-size: 10px;
            }
            QProgressBar::chunk {
                background-color: #E91E63;
                border-radius: 2px;
            }
            QLabel {
                color: #ddd;
                font-size: 11px;
            }
        """)
    
    def set_companions(self, companions: dict):
        """Inizializza le barre per ogni companion."""
        # Pulisci layout esistente
        while self.layout().count():
            item = self.layout().takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.companion_bars = {}
        
        for name in companions.keys():
            # Container per questa companion
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setSpacing(2)
            container_layout.setContentsMargins(0, 0, 0, 5)
            
            # Nome + Stato emotivo
            header = QHBoxLayout()
            name_label = QLabel(f"<b>{name}</b>")
            name_label.setStyleSheet("color: #fff; font-size: 12px;")
            
            emotion_label = QLabel("😐 --")
            emotion_label.setStyleSheet("color: #aaa; font-size: 10px;")
            
            header.addWidget(name_label)
            header.addStretch()
            header.addWidget(emotion_label)
            
            # Barra affinità
            affinity_bar = QProgressBar()
            affinity_bar.setRange(0, 100)
            affinity_bar.setValue(0)
            affinity_bar.setTextVisible(True)
            affinity_bar.setFormat("%v/100")
            affinity_bar.setMaximumHeight(16)
            
            # Cambia colore in base all'affinità
            affinity_bar.setStyleSheet("""
                QProgressBar::chunk {
                    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #4CAF50, stop:0.5 #FFC107, stop:1 #E91E63);
                    border-radius: 2px;
                }
            """)
            
            container_layout.addLayout(header)
            container_layout.addWidget(affinity_bar)
            
            self.layout().addWidget(container)
            
            self.companion_bars[name] = {
                'emotion': emotion_label,
                'affinity': affinity_bar
            }
        
        self.layout().addStretch()
    
    def update_companion(self, name: str, affinity: int, emotion: str, emotion_icon: str = "😐"):
        """Aggiorna dati di una companion."""
        if name in self.companion_bars:
            bars = self.companion_bars[name]
            bars['affinity'].setValue(affinity)
            bars['emotion'].setText(f"{emotion_icon} {emotion}")
            
            # Cambia colore barra in base al livello
            if affinity < 25:
                color = "#4CAF50"  # Verde (straniero)
            elif affinity < 50:
                color = "#FFC107"  # Giallo (amico)
            elif affinity < 75:
                color = "#FF9800"  # Arancione (intimo)
            else:
                color = "#E91E63"  # Rosa (innamorata)
            
            bars['affinity'].setStyleSheet(f"""
                QProgressBar::chunk {{
                    background-color: {color};
                    border-radius: 2px;
                }}
            """)


class MilestoneTrackerWidget(QGroupBox):
    """Widget per mostrare i milestone delle companion."""
    
    def __init__(self, parent=None):
        super().__init__("❤️ Relationship Milestones", parent)
        
        layout = QVBoxLayout(self)
        
        # Tab per ogni companion
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                background-color: #2d2d2d;
                border: 1px solid #444;
            }
            QTabBar::tab {
                background-color: #3d3d3d;
                color: #aaa;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #4CAF50;
                color: white;
            }
        """)
        layout.addWidget(self.tabs)
        
        self.companion_widgets = {}
    
    def set_companions(self, companions_data: dict):
        """Inizializza tab per ogni companion."""
        # Pulisci tab esistenti
        while self.tabs.count() > 0:
            self.tabs.removeTab(0)
        
        self.companion_widgets = {}
        
        for name, data in companions_data.items():
            widget = QWidget()
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(widget)
            
            layout = QVBoxLayout(widget)
            layout.setAlignment(Qt.AlignTop)
            
            # Affinità progress bar
            affinity_layout = QHBoxLayout()
            affinity_layout.addWidget(QLabel("Affinità:"))
            
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(0)
            bar.setTextVisible(True)
            bar.setStyleSheet("""
                QProgressBar {
                    border: 2px solid #444;
                    border-radius: 5px;
                    text-align: center;
                    color: white;
                }
                QProgressBar::chunk {
                    background-color: #E91E63;
                    border-radius: 3px;
                }
            """)
            affinity_layout.addWidget(bar)
            
            lbl_affinity_value = QLabel("0/100")
            affinity_layout.addWidget(lbl_affinity_value)
            layout.addLayout(affinity_layout)
            
            # Stato emotivo
            emotional_layout = QHBoxLayout()
            emotional_layout.addWidget(QLabel("Stato:"))
            lbl_emotional = QLabel("default")
            lbl_emotional.setStyleSheet("color: #FFC107; font-weight: bold;")
            emotional_layout.addWidget(lbl_emotional)
            emotional_layout.addStretch()
            layout.addLayout(emotional_layout)
            
            # Separatore
            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            line.setStyleSheet("background-color: #444;")
            layout.addWidget(line)
            
            # Lista milestone
            lbl_milestones = QLabel("Milestones:")
            layout.addWidget(lbl_milestones)
            
            milestone_list = QListWidget()
            milestone_list.setStyleSheet("""
                QListWidget {
                    background-color: transparent;
                    border: none;
                }
                QListWidget::item {
                    padding: 3px;
                    color: #666;
                }
            """)
            layout.addWidget(milestone_list)
            
            self.tabs.addTab(scroll, name)
            
            self.companion_widgets[name] = {
                'progress_bar': bar,
                'lbl_affinity': lbl_affinity_value,
                'lbl_emotional': lbl_emotional,
                'milestone_list': milestone_list
            }
    
    def update_companion(self, name: str, affinity: int, emotional_state: str, 
                        milestones: List[dict]):
        """Aggiorna UI per una companion."""
        if name not in self.companion_widgets:
            return
        
        widgets = self.companion_widgets[name]
        
        # Aggiorna affinità
        widgets['progress_bar'].setValue(affinity)
        widgets['lbl_affinity'].setText(f"{affinity}/100")
        
        # Cambia colore barra in base all'affinità
        if affinity >= 75:
            widgets['progress_bar'].setStyleSheet("""
                QProgressBar::chunk { background-color: #9C27B0; }
            """)
        elif affinity >= 50:
            widgets['progress_bar'].setStyleSheet("""
                QProgressBar::chunk { background-color: #E91E63; }
            """)
        
        # Aggiorna stato emotivo
        widgets['lbl_emotional'].setText(emotional_state)
        
        # Aggiorna milestone
        widgets['milestone_list'].clear()
        for m in milestones:
            status = "✅" if m.get('reached') else "⬜"
            icon = m.get('icon', '🎯')
            item_text = f"{status} {icon} {m.get('name', 'Unknown')}"
            
            item = QListWidgetItem(item_text)
            if m.get('reached'):
                item.setForeground(Qt.green)
            widgets['milestone_list'].addItem(item)


class AchievementWidget(QGroupBox):
    """Widget per mostrare gli achievement sbloccati."""
    
    def __init__(self, parent=None):
        super().__init__("🏆 Achievements", parent)
        self.setMaximumHeight(150)
        
        layout = QVBoxLayout(self)
        
        # Contatore
        self.lbl_count = QLabel("0 / 10 sbloccati")
        layout.addWidget(self.lbl_count)
        
        # Lista achievement
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: #2d2d2d;
                border: 1px solid #444;
            }
            QListWidget::item {
                padding: 3px;
            }
        """)
        layout.addWidget(self.list_widget)
    
    def add_achievement(self, title: str, description: str, icon: str = "🏆"):
        """Aggiunge achievement sbloccato."""
        item = QListWidgetItem(f"{icon} {title}")
        item.setToolTip(description)
        item.setForeground(Qt.yellow)
        self.list_widget.addItem(item)
        
        # Aggiorna contatore
        count = self.list_widget.count()
        self.lbl_count.setText(f"{count} sbloccati")
        
        # Mostra notifica
        QToolTip.showText(
            self.mapToGlobal(self.rect().center()),
            f"🏆 Achievement Sbloccato!\n{title}",
            self,
            QRect(),
            3000
        )


class HaremProgressWidget(QGroupBox):
    """Widget per mostrare progresso verso True Harem Ending."""
    
    def __init__(self, parent=None):
        super().__init__("🎯 True Harem Progress", parent)
        self.setMaximumHeight(150)
        
        layout = QVBoxLayout(self)
        
        # Progresso totale
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)  # Sarà aggiornato dinamicamente
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%v / %m conquistate")
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #FFD700;
                border-radius: 5px;
                text-align: center;
                color: #FFD700;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #FFD700,
                    stop:1 #FFA500
                );
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # Stato singole companion (container per layout dinamico)
        self.status_layout = QHBoxLayout()
        self.companion_labels = {}  # name -> QLabel
        layout.addLayout(self.status_layout)
        
        # Messaggio finale
        self.lbl_final = QLabel("Conquista tutti i target per il True Harem Ending!")
        self.lbl_final.setStyleSheet("color: #888; font-style: italic; font-size: 10px;")
        self.lbl_final.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_final)
        
        self.total_targets = 0
    
    def set_companions(self, companion_names: List[str]):
        """Inizializza il widget con la lista dei companion del mondo."""
        # Pulisci layout esistente
        while self.status_layout.count():
            item = self.status_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.companion_labels = {}
        self.total_targets = len(companion_names)
        
        # Aggiorna range progress bar
        self.progress_bar.setRange(0, max(1, self.total_targets))
        
        # Crea label per ogni companion
        for name in companion_names:
            lbl = QLabel(f"🔒 {name}")
            lbl.setStyleSheet("color: #666;")
            lbl.setAlignment(Qt.AlignCenter)
            self.status_layout.addWidget(lbl)
            self.companion_labels[name] = lbl
        
        # Aggiorna messaggio
        if self.total_targets > 0:
            self.lbl_final.setText(f"Conquista tutti e {self.total_targets} per il True Harem Ending!")
    
    def update_progress(self, conquered: List[str]):
        """Aggiorna progresso."""
        count = len(conquered)
        self.progress_bar.setValue(count)
        
        # Aggiorna icone
        for name in conquered:
            if name in self.companion_labels:
                self.companion_labels[name].setText(f"✅ {name}")
                self.companion_labels[name].setStyleSheet("color: #4CAF50; font-weight: bold;")
        
        # Vittoria!
        if self.total_targets > 0 and count >= self.total_targets:
            self.lbl_final.setText("🎉 TRUE HAREM ENDING UNLOCKED! 🎉")
            self.lbl_final.setStyleSheet("color: #FFD700; font-weight: bold; font-size: 12px;")


class MainWindow(QMainWindow):
    """Finestra principale con integrazione Quest System v3."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LUNA RPG v3 - Quest Edition")
        
        # Engine
        self.engine = GameEngine()
        
        # Stato UI
        self.current_image: Optional[Path] = None
        self.last_narrative: str = ""
        self.last_visual_desc: str = ""
        self.image_history: List[Path] = []
        self.video_history: List[Path] = []
        self.is_processing = False
        self._initialized = False
        self._unlocked_achievements = set()
        self.session_logger = None  # Logger per sessione
        
        self._setup_ui()
        self.showMaximized()
        
        QTimer.singleShot(100, self._delayed_init)
    
    def _setup_ui(self):
        """Setup interfaccia con pannelli quest."""
        central = QWidget()
        self.setCentralWidget(central)
        
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Splitter principale (3 pannelli)
        splitter = QSplitter(Qt.Horizontal)
        
        # === PANNELLO SINISTRO: Info & Quest ===
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # Status base
        status_group = QGroupBox("[D] Status")
        status_layout = QGridLayout(status_group)
        
        self.lbl_time = QLabel("⏰ --")
        self.lbl_location = QLabel("📍 --")
        self.lbl_outfit = QLabel("👗 --")
        self.lbl_turn = QLabel("🎲 --")
        self.lbl_affinity = QLabel("❤️ --")
        
        status_layout.addWidget(self.lbl_time, 0, 0)
        status_layout.addWidget(self.lbl_location, 0, 1)
        status_layout.addWidget(self.lbl_outfit, 1, 0)
        status_layout.addWidget(self.lbl_turn, 1, 1)
        status_layout.addWidget(self.lbl_affinity, 2, 0, 1, 2)
        
        left_layout.addWidget(status_group)
        
        # NOVITÀ: Global Event
        self.global_event_widget = GlobalEventWidget()
        left_layout.addWidget(self.global_event_widget)
        
        # NOVITÀ: All Companions Status
        self.companion_status = CompanionStatusWidget()
        left_layout.addWidget(self.companion_status)
        
        # NOVITÀ: Quest Tracker
        self.quest_tracker = QuestTrackerWidget()
        left_layout.addWidget(self.quest_tracker)
        
        # NOVITÀ: Harem Progress
        self.harem_progress = HaremProgressWidget()
        left_layout.addWidget(self.harem_progress)
        
        # NOVITÀ: Achievement
        self.achievement_widget = AchievementWidget()
        left_layout.addWidget(self.achievement_widget)
        
        left_layout.addStretch()
        
        splitter.addWidget(left_panel)
        
        # === PANNELLO CENTRALE: Immagine ===
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(0, 0, 0, 0)
        
        img_group = QGroupBox("[IMG] Visual Scene")
        img_layout = QVBoxLayout(img_group)
        
        self.image_label = QLabel("Waiting for scene...")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(400, 500)
        self.image_label.setStyleSheet("background-color: #1a1a1a; border: 2px solid #444; cursor: pointer;")
        self.image_label.setCursor(Qt.PointingHandCursor)
        self.image_label.mousePressEvent = self._on_image_click
        img_layout.addWidget(self.image_label)
        
        # Image nav
        img_nav = QHBoxLayout()
        self.btn_prev = QPushButton("◀")
        self.btn_prev.clicked.connect(self._show_prev_image)
        self.btn_prev.setEnabled(False)
        
        self.btn_animate = QPushButton("[V] Animate")
        self.btn_animate.clicked.connect(self._on_animate)
        self.btn_animate.setEnabled(False)
        self.btn_animate.setStyleSheet("background-color: #ff9800; color: white; font-weight: bold;")
        
        self.btn_next = QPushButton("▶")
        self.btn_next.clicked.connect(self._show_next_image)
        self.btn_next.setEnabled(False)
        
        img_nav.addWidget(self.btn_prev)
        img_nav.addWidget(self.btn_animate)
        img_nav.addWidget(self.btn_next)
        img_layout.addLayout(img_nav)
        
        # Video history
        video_layout = QHBoxLayout()
        video_layout.addWidget(QLabel("[🎬 Videos]:"))
        self.combo_videos = QComboBox()
        self.combo_videos.setPlaceholderText("Select video...")
        self.combo_videos.currentIndexChanged.connect(self._on_video_selected)
        video_layout.addWidget(self.combo_videos, stretch=1)
        img_layout.addLayout(video_layout)
        
        center_layout.addWidget(img_group)
        
        # Controls
        ctrl_layout = QHBoxLayout()
        self.chk_voice = QCheckBox("[SND] Voice")
        self.chk_voice.setChecked(False)
        ctrl_layout.addWidget(self.chk_voice)
        
        self.lbl_status = QLabel("Ready")
        ctrl_layout.addWidget(self.lbl_status)
        ctrl_layout.addStretch()
        
        btn_save = QPushButton("[SAVE] Save")
        btn_save.clicked.connect(self._on_save)
        ctrl_layout.addWidget(btn_save)
        
        btn_load = QPushButton("[L] Load")
        btn_load.clicked.connect(self._on_load)
        ctrl_layout.addWidget(btn_load)
        
        center_layout.addLayout(ctrl_layout)
        
        splitter.addWidget(center_panel)
        
        # === PANNELLO DESTRO: Story + Milestones ===
        right_splitter = QSplitter(Qt.Vertical)
        
        # Story panel
        story_panel = QWidget()
        story_layout = QVBoxLayout(story_panel)
        story_layout.setContentsMargins(0, 0, 0, 0)
        
        chat_group = QGroupBox("📖 Story")
        chat_layout = QVBoxLayout(chat_group)
        
        self.story_edit = QTextEdit()
        self.story_edit.setReadOnly(True)
        self.story_edit.setStyleSheet("""
            QTextEdit {
                font-family: 'Segoe UI', sans-serif;
                font-size: 15px;
                line-height: 1.6;
                padding: 12px;
                border-radius: 8px;
                background-color: #1e1e1e;
                color: #e0e0e0;
            }
        """)
        self.story_edit.document().setDocumentMargin(12)
        chat_layout.addWidget(self.story_edit)
        story_layout.addWidget(chat_group)
        
        # Input
        input_group = QGroupBox("⌨️ Action")
        input_layout = QHBoxLayout(input_group)
        
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("What do you do?")
        self.input_field.returnPressed.connect(self._on_send)
        self.input_field.setMinimumHeight(50)
        self.input_field.setStyleSheet("""
            QLineEdit {
                font-family: 'Segoe UI', sans-serif;
                font-size: 16px;
                padding: 8px 12px;
                border-radius: 8px;
                border: 2px solid #444;
                background-color: #2d2d2d;
                color: #fff;
            }
            QLineEdit:focus {
                border: 2px solid #4CAF50;
            }
        """)
        input_layout.addWidget(self.input_field)
        
        btn_send = QPushButton("▶ Send")
        btn_send.clicked.connect(self._on_send)
        btn_send.setDefault(True)
        input_layout.addWidget(btn_send)
        
        story_layout.addWidget(input_group)
        
        right_splitter.addWidget(story_panel)
        
        # NOVITÀ: Milestone Tracker
        self.milestone_tracker = MilestoneTrackerWidget()
        right_splitter.addWidget(self.milestone_tracker)
        right_splitter.setSizes([400, 300])
        
        splitter.addWidget(right_splitter)
        
        # Dimensioni splitter
        splitter.setSizes([250, 500, 450])
        main_layout.addWidget(splitter)
        
        self.input_field.setEnabled(False)
    
    def _delayed_init(self):
        """Avvio inizializzazione async."""
        asyncio.create_task(self._async_init())
    
    async def _async_init(self):
        """Inizializzazione asincrona con setup Quest System."""
        try:
            await self.engine.initialize_database()
            
            dialog = StartupDialog(self)
            
            # Carica lista salvataggi nel dialog (DB ora è pronto)
            dialog.load_saves_sync()
            
            if dialog.exec() != QDialog.Accepted:
                self.close()
                return
            
            selection = dialog.get_selection()
            
            # Setup client in base alla modalità scelta nello startup dialog
            use_runpod = selection.get("use_runpod", False)
            runpod_id = selection.get("runpod_id", "")
            
            # Configura i client (SD WebUI in locale, ComfyUI in RunPod)
            self.engine.setup_clients(use_runpod=use_runpod, runpod_id=runpod_id)
            
            # Disabilita il pulsante video se in modalità locale
            if not use_runpod:
                self.btn_animate.setEnabled(False)
                self.btn_animate.setToolTip("Video disabilitato in modalità locale (richiede RunPod)")
                self.btn_animate.setStyleSheet("background-color: #555; color: #888;")
                print("[UI] Video generation disabilitato (modalità locale)")
            else:
                self.btn_animate.setToolTip("Genera video dall'immagine corrente")
            
            # Crea/carica gioco
            async with db_manager.get_session() as db:
                if selection["mode"] == "new":
                    await self.engine.create_game(
                        db,
                        selection["world_id"],
                        selection["companion"]
                    )
                elif selection["mode"] == "load" and selection.get("session_id"):
                    session = await self.engine.load_game(db, selection["session_id"])
                    if not session:
                        QMessageBox.critical(self, "Error", "Failed to load saved game.")
                        self.close()
                        return
                else:
                    QMessageBox.information(self, "Load", "No saved game selected.")
                    self.close()
                    return
            
            # Setup UI Quest System
            self._setup_quest_ui()
            
            self._initialized = True
            self._update_status()
            self.input_field.setEnabled(True)
            
            # Log inizio gioco
            if self.session_logger:
                world_name = self.engine.world_data.get('meta', {}).get('name', 'Unknown')
                char_name = self.engine.state.current.companion_name
                self.session_logger.log_event("GAME", f"=== INIZIO PARTITA ===")
                self.session_logger.log_event("GAME", f"Mondo: {world_name}")
                self.session_logger.log_event("GAME", f"Personaggio: {char_name}")
            
            await self._process_turn("", is_intro=True)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Initialization failed:\n{e}")
            import traceback
            traceback.print_exc()
            self.close()
    
    def _setup_quest_ui(self):
        """Inizializza UI del Quest System."""
        if not self.engine.quest_engine:
            return
        
        # Inizializza milestone tracker con companion
        companions = self.engine.world_data.get("companions", {})
        self.milestone_tracker.set_companions(companions)
        
        # Inizializza companion status widget
        self.companion_status.set_companions(companions)
        
        # Inizializza harem progress con lista nomi companion
        companion_names = list(companions.keys())
        self.harem_progress.set_companions(companion_names)
        
        # Aggiorna UI iniziale
        self._update_quest_ui()
    
    def _update_quest_ui(self):
        """Aggiorna tutta l'UI delle quest."""
        if not self.engine.quest_engine or not self.engine.state:
            return
        
        game_state = self._get_game_state_snapshot()
        
        # 1. Aggiorna Quest Tracker
        quest_states = []
        for quest_id, state in self.engine.quest_engine.active_states.items():
            quest_def = self.engine.quest_engine.quest_definitions.get(quest_id)
            if quest_def:
                quest_states.append({
                    'id': quest_id,
                    'title': quest_def.meta.title,
                    'status': state.status.value,
                    'stage': state.current_stage_id,
                    'description': quest_def.meta.description
                })
        self.quest_tracker.update_quests(quest_states)
        
        # 2. Aggiorna Companion Status per ogni companion
        emotion_icons = {
            'default': '😐',
            'flustered': '😳',
            'after_class': '📚',
            'vulnerable': '🥺',
            'jealous': '😤',
            'seductive': '😏',
            'tsundere': '😠',
            'clingy': '🥰',
            'competitive': '🔥',
            'chatty': '💬',
            'maternal': '🤱',
        }
        
        for char_name in self.engine.world_data.get("companions", {}).keys():
            affinity = self.engine.state.current.affinity.get(char_name, 0)
            emotional = self.engine.quest_engine.get_companion_emotional_state(
                char_name, game_state
            )
            
            # Aggiorna companion status widget
            icon = emotion_icons.get(emotional, '😐')
            self.companion_status.update_companion(char_name, affinity, emotional, icon)
            
            # Aggiorna milestone tracker
            milestones = self.engine.quest_engine.get_ui_milestone_status(
                char_name, game_state
            )
            self.milestone_tracker.update_companion(char_name, affinity, emotional, milestones)
        
        # 3. Aggiorna Harem Progress
        _, conquered = self.engine.quest_engine.check_endgame_victory(game_state)
        self.harem_progress.update_progress(conquered)
        
        # 4. Check achievement
        self._check_achievements()
    
    def _check_achievements(self):
        """Controlla e sblocca achievement."""
        if not self.engine.state:
            return
        
        game = self.engine.state.current
        
        # Achievement: Prima Quest
        if self.engine.quest_engine:
            active_count = len([q for q in self.engine.quest_engine.active_states.values() 
                              if q.status.value == 'active'])
            if active_count > 0 and "first_quest" not in self._unlocked_achievements:
                self._unlock_achievement("First Steps", "Hai attivato la tua prima quest", "🎯")
                self._unlocked_achievements.add("first_quest")
        
        # Achievement: Affinità 50
        for char, aff in game.affinity.items():
            if aff >= 50:
                key = f"affinity_50_{char}"
                if key not in self._unlocked_achievements:
                    self._unlock_achievement(
                        f"{char} Interessata", 
                        f"Hai raggiunto 50 affinità con {char}",
                        "💕"
                    )
                    self._unlocked_achievements.add(key)
        
        # Achievement: Affinità 100
        for char, aff in game.affinity.items():
            if aff >= 100:
                key = f"affinity_100_{char}"
                if key not in self._unlocked_achievements:
                    self._unlock_achievement(
                        f"{char} Conquistata",
                        f"Hai raggiunto il massimo con {char}!",
                        "❤️"
                    )
                    self._unlocked_achievements.add(key)
        
        # Achievement: Harem Master (tutte a 100)
        if self.engine.quest_engine:
            victory, _ = self.engine.quest_engine.check_endgame_victory(
                self._get_game_state_snapshot()
            )
            if victory and "harem_master" not in self._unlocked_achievements:
                self._unlock_achievement(
                    "Harem Master",
                    "Hai conquistato il cuore di tutte e tre!",
                    "👑"
                )
                self._unlocked_achievements.add("harem_master")
    
    def _unlock_achievement(self, title: str, description: str, icon: str):
        """Sblocca un achievement."""
        self.achievement_widget.add_achievement(title, description, icon)
        
        # Mostra anche nella storia
        self._append_story(
            f"<div style='background: #332200; padding: 10px; border-left: 3px solid #FFD700; margin: 10px 0;'>"
            f"<b>🏆 Achievement Unlocked!</b><br>"
            f"<span style='color: #FFD700;'>{icon} {title}</span><br>"
            f"<small style='color: #888;'>{description}</small></div>"
        )
    
    def _get_game_state_snapshot(self) -> dict:
        """Snapshot dello stato per QuestEngine."""
        if not self.engine.state:
            return {}
        game = self.engine.state.current
        return {
            "affinity": game.affinity,
            "location": game.location,
            "time_of_day": game.time_of_day,
            "flags": game.flags,
            "turn_count": game.turn_count,
            "inventory": game.inventory,
            "companion": game.companion_name,
            "current_outfit": game.current_outfit
        }
    
    @asyncSlot()
    async def _on_send(self):
        """Invia azione."""
        if self.is_processing or not self._initialized:
            return
        
        text = self.input_field.text().strip()
        if not text:
            return
        
        # Log input utente
        if self.session_logger:
            self.session_logger.log_user_input(text)
        
        self.input_field.clear()
        self._append_story(f"<b style='color: #4CAF50;'>> You:</b> {text}")
        
        await self._process_turn(text)
    
    @asyncSlot()
    async def _process_turn(self, user_input: str, is_intro: bool = False):
        """Processa turno con aggiornamento UI quest."""
        self.is_processing = True
        self.lbl_status.setText("🤔 Thinking...")
        self.input_field.setEnabled(False)
        
        try:
            async with db_manager.get_session() as db:
                if is_intro:
                    user_input = (
                        "[SYSTEM]: START THE GAME. "
                        "Start with a SHORT hook. Write narration in Italian."
                    )
                
                result = await self.engine.process_turn(
                    db,
                    user_input,
                    generate_image=True,
                    generate_audio=False
                )
                
                if "error" in result:
                    self._append_story(f"<span style='color: red;'>Error: {result['error']}</span>")
                    return
                
                # Mostra testo
                char_name = self.engine.state.current.companion_name
                self._append_story(
                    f"<b style='color: #E91E63;'>{char_name}:</b> {result['text']}"
                )
                
                # Log risposta AI con metadati
                if self.session_logger:
                    metadata = {
                        "character": char_name,
                        "affinity": self.engine.state.current.affinity.get(char_name, 0),
                        "location": self.engine.state.current.location,
                        "outfit": self.engine.state.current.current_outfit,
                        "turn": self.engine.state.current.turn_count,
                        "image": result.get('image_path', 'None'),
                        "visual": result.get('visual_en', 'N/A')[:100] + "..." if result.get('visual_en') else 'N/A'
                    }
                    self.session_logger.log_ai_response(result['text'], metadata)
                
                # Salva contesto video
                self.last_narrative = result.get('text', '')
                self.last_visual_desc = result.get('visual_en', '')
                
                # Mostra immagine
                if result.get("image_path"):
                    self._show_image(result["image_path"])
                    # Abilita il pulsante video SOLO se in RunPod e video disponibile
                    if self.engine._is_runpod_mode and self.engine.video_gen.settings.video_available:
                        self.btn_animate.setEnabled(True)
                
                # Audio
                if self.chk_voice.isChecked() and not is_intro:
                    asyncio.create_task(self._play_audio_async(result['text'], char_name))
                
                # NOVITÀ: Aggiorna UI Quest
                self._update_quest_ui()
                self._update_status()
                
        except Exception as e:
            self._append_story(f"<span style='color: red;'>Error: {e}</span>")
            import traceback
            traceback.print_exc()
        
        finally:
            self.is_processing = False
            self.lbl_status.setText("Ready")
            self.input_field.setEnabled(True)
            self.input_field.setFocus()
    
    def _update_status(self):
        """Aggiorna pannello status base."""
        if not self.engine.state or not self.engine.state.current:
            return
        
        game = self.engine.state.current
        
        self.lbl_time.setText(f"⏰ {game.time_of_day}")
        self.lbl_location.setText(f"📍 {game.location}")
        self.lbl_outfit.setText(f"👗 {game.current_outfit}")
        self.lbl_turn.setText(f"🎲 Turn {game.turn_count}")
        
        aff_text = " | ".join([f"{name}: {val}" for name, val in game.affinity.items()])
        self.lbl_affinity.setText(f"❤️ {aff_text}")
    
    def _append_story(self, html: str):
        """Aggiunge testo alla storia."""
        self.story_edit.append(f"<div style='margin-bottom: 16px;'>{html}</div>")
        scrollbar = self.story_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    async def _play_audio_async(self, text: str, char_name: str):
        """Riproduce audio in background."""
        try:
            await self.engine.audio.speak(text, char_name)
        except Exception as e:
            print(f"[!] TTS error: {e}")
    
    def _show_image(self, path: Path):
        """Mostra immagine."""
        if not path or not path.exists():
            return
        
        self.current_image = path
        self.image_history.append(path)
        
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return
        
        scaled = pixmap.scaled(
            self.image_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.image_label.setPixmap(scaled)
        
        self.btn_animate.setEnabled(True)
        self._update_nav_buttons()
    
    def _update_nav_buttons(self):
        """Aggiorna bottoni navigazione."""
        idx = len(self.image_history) - 1 if self.image_history else -1
        self.btn_prev.setEnabled(idx > 0)
        self.btn_next.setEnabled(False)
    
    def _show_prev_image(self):
        """Mostra immagine precedente."""
        if len(self.image_history) < 2:
            return
        self.image_history.pop()
        prev = self.image_history[-1]
        self._show_image(prev)
    
    def _show_next_image(self):
        """Placeholder."""
        pass
    
    def _on_image_click(self, event):
        """Apre dialog immagine zoomabile."""
        if not self.current_image or not self.current_image.exists():
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"📷 {self.current_image.name}")
        dialog.resize(1200, 900)
        
        layout = QVBoxLayout(dialog)
        
        scroll = QScrollArea()
        scroll.setStyleSheet("background-color: #1a1a1a;")
        
        pixmap = QPixmap(str(self.current_image))
        img_label = QLabel()
        img_label.setPixmap(pixmap)
        img_label.setAlignment(Qt.AlignCenter)
        
        scroll.setWidget(img_label)
        layout.addWidget(scroll)
        
        info = QLabel(f"📁 {self.current_image} | 📐 {pixmap.width()}x{pixmap.height()}px")
        info.setStyleSheet("color: #888; padding: 8px;")
        layout.addWidget(info)
        
        dialog.exec()
    
    @asyncSlot()
    async def _on_animate(self):
        """Genera video."""
        if not self.current_image:
            return
        
        # Controllo: video disponibile solo in RunPod
        if not self.engine._is_runpod_mode:
            QMessageBox.information(
                self, 
                "Video Non Disponibile",
                "La generazione video è disponibile solo in modalità RunPod (Cloud GPU).\n\n"
                "In modalità locale puoi comunque generare immagini con SD WebUI.\n"
                "Per abilitare il video, riavvia e seleziona 'Use RunPod' nelle impostazioni."
            )
            return
        
        if not self.engine.video_gen.settings.video_available:
            QMessageBox.warning(
                self,
                "Video Non Configurato",
                "Il video generation non è configurato correttamente.\n"
                "Verifica che RunPod ID sia corretto."
            )
            return
        
        character = self.engine.state.current.companion_name if self.engine.state else "Luna"
        location = self.engine.state.current.location if self.engine.state else "Unknown"
        
        dialog = VideoActionDialog(character, location, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        
        user_action = dialog.get_action() or "posing"
        
        self.lbl_status.setText("[V] Video: Starting...")
        self.btn_animate.setEnabled(False)
        
        try:
            video_path = await self.engine.generate_video(
                self.current_image,
                action=user_action,
                narrative_context=self.last_narrative,
                visual_description=self.last_visual_desc,
                user_action=user_action
            )
            
            if video_path:
                self.lbl_status.setText("[OK] Video ready!")
                self.video_history.append(video_path)
                self.combo_videos.addItem(f"{video_path.name}", video_path)
                self.combo_videos.setCurrentIndex(self.combo_videos.count() - 1)
                
                import platform, subprocess, os
                if platform.system() == "Windows":
                    os.startfile(str(video_path))
            else:
                self.lbl_status.setText("[ERR] Video generation failed")
        
        except Exception as e:
            self.lbl_status.setText(f"[ERR] Error: {str(e)[:50]}")
        
        finally:
            self.btn_animate.setEnabled(True)
    
    def _on_video_selected(self, index):
        """Apre video selezionato."""
        if index < 0:
            return
        
        video_path = self.combo_videos.itemData(index)
        if video_path and video_path.exists():
            import platform, subprocess, os
            
            self.lbl_status.setText(f"[▶] Playing: {video_path.name[:30]}...")
            
            if platform.system() == "Windows":
                os.startfile(str(video_path))
            elif platform.system() == "Darwin":
                subprocess.call(["open", str(video_path)])
            else:
                subprocess.call(["xdg-open", str(video_path)])
    
    @asyncSlot()
    async def _on_save(self):
        """Salva partita."""
        try:
            async with db_manager.get_session() as db:
                await self.engine.state.save_manual(db)
            self.lbl_status.setText("[SAVE] Saved!")
        except Exception as e:
            self.lbl_status.setText(f"[ERR] Save failed: {e}")
    
    @asyncSlot()
    async def _on_load(self):
        """Carica partita (placeholder)."""
        QMessageBox.information(self, "Load", "Load game - work in progress")
    
    def resizeEvent(self, event):
        """Ridisegna immagine quando resize."""
        super().resizeEvent(event)
        if self.current_image and self.image_label.pixmap():
            pixmap = QPixmap(str(self.current_image))
            scaled = pixmap.scaled(
                self.image_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.image_label.setPixmap(scaled)
    
    @asyncClose
    async def closeEvent(self, event):
        """Cleanup."""
        event.accept()
