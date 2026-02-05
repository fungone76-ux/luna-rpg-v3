"""Async Google Cloud Text-to-Speech client."""
import asyncio
import os
import tempfile
from pathlib import Path
from typing import Optional

import pygame
from google.cloud import texttospeech
from google.oauth2 import service_account

from config.settings import Settings

# Mappa voci (invariata dalla V2)
VOICE_MAP = {
    "Luna": {"name": "en-US-Journey-F", "lang": "en-US"},
    "Stella": {"name": "en-US-Standard-A", "lang": "en-US"},
    "Maria": {"name": "en-GB-Neural2-A", "lang": "en-GB"},
    "Narrator": {"name": "it-IT-Neural2-A", "lang": "it-IT"}
}


class AudioClient:
    """Client async per Text-to-Speech."""
    
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self.enabled = False
        self.client: Optional[texttospeech.TextToSpeechClient] = None
        
        self._init_client()
    
    def _init_client(self) -> None:
        """Inizializza il client Google."""
        cred_path = self.settings.google_credentials_path
        
        if not cred_path.exists():
            print(f"[!] Audio disabled: credentials not found at {cred_path}")
            return
        
        try:
            credentials = service_account.Credentials.from_service_account_file(str(cred_path))
            self.client = texttospeech.TextToSpeechClient(credentials=credentials)
            
            # Init pygame mixer
            try:
                pygame.mixer.init(frequency=24000, buffer=4096)
                self.enabled = True
                print("[OK] Audio client initialized")
            except Exception as e:
                print(f"[!] Pygame init error: {e}")
                
        except Exception as e:
            print(f"[!] Audio client error: {e}")
    
    async def speak(self, text: str, character_name: str = "Narrator") -> bool:
        """Genera e riproduce audio in modo async.
        
        Args:
            text: Testo da pronunciare
            character_name: Nome del personaggio per selezione voce
            
        Returns:
            True se successo
        """
        print(f"[SND] TTS Request: enabled={self.enabled}, text_len={len(text) if text else 0}")
        
        if not self.enabled:
            print("[!] TTS disabled (client not initialized)")
            return False
        if not self.client:
            print("[!] TTS client not available")
            return False
        if not text:
            print("[!] TTS no text provided")
            return False
        
        # Tronca testo lungo
        text = text[:400]
        
        voice_config = VOICE_MAP.get(character_name, VOICE_MAP["Narrator"])
        print(f"[SND] TTS Using voice: {voice_config['name']} for {character_name}")
        
        try:
            # Esegui sincronizzazione in thread separato
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, 
                self._generate_and_play,
                text, 
                voice_config
            )
            print("[SND] TTS completed successfully")
            return True
            
        except Exception as e:
            print(f"[ERR] TTS Error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _generate_and_play(self, text: str, voice_config: dict) -> None:
        """Sincrono: genera e riproduce."""
        print(f"[SND] Generating TTS for: '{text[:50]}...'" if len(text) > 50 else f"[SND] Generating TTS for: '{text}'")
        
        synthesis_input = texttospeech.SynthesisInput(text=text)
        
        voice = texttospeech.VoiceSelectionParams(
            language_code=voice_config["lang"],
            name=voice_config["name"],
            ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
        )
        
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=1.0
        )
        
        # Genera
        print("[SND] Calling Google TTS API...")
        response = self.client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )
        print(f"[SND] TTS response received: {len(response.audio_content)} bytes")
        
        # Salva e riproduce
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
            temp_path = fp.name
            fp.write(response.audio_content)
            print(f"[SND] Audio saved to: {temp_path}")
        
        try:
            print("[SND] Loading audio with pygame...")
            pygame.mixer.music.load(temp_path)
            print("[SND] Playing audio...")
            pygame.mixer.music.play()
            
            # Attendi fine
            print("[SND] Waiting for playback to finish...")
            duration = 0
            while pygame.mixer.music.get_busy():
                import time
                time.sleep(0.1)
                duration += 0.1
            
            print(f"[SND] Playback finished (duration: {duration:.1f}s)")
            pygame.mixer.music.unload()
            
        finally:
            # Pulizia
            try:
                os.remove(temp_path)
                print("[SND] Temp file cleaned up")
            except Exception as e:
                print(f"[!] Failed to cleanup temp file: {e}")
    
    def stop(self) -> None:
        """Ferma riproduzione."""
        if self.enabled:
            pygame.mixer.music.stop()
