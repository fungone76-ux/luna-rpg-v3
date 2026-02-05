"""Test di base per verificare che i moduli si importino correttamente."""
import asyncio
import sys
from pathlib import Path

# Aggiungi root al path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_imports():
    """Test che tutti i moduli si importino."""
    print("Testing imports...")
    
    try:
        from core.models import GameSession, SceneAnalysis, CompositionType
        print("[OK] core.models")
    except Exception as e:
        print(f"[ERR] core.models: {e}")
        return False
    
    try:
        from core.database import db_manager, DatabaseManager
        print("[OK] core.database")
    except Exception as e:
        print(f"[ERR] core.database: {e}")
        return False
    
    try:
        from core.state_manager import StateManager
        print("[OK] core.state_manager")
    except Exception as e:
        print(f"[ERR] core.state_manager: {e}")
        return False
    
    try:
        from core.memory_manager import MemoryManager
        print("[OK] core.memory_manager")
    except Exception as e:
        print(f"[ERR] core.memory_manager: {e}")
        return False
    
    try:
        from core.scene_analyzer import SceneAnalyzer
        print("[OK] core.scene_analyzer")
    except Exception as e:
        print(f"[ERR] core.scene_analyzer: {e}")
        return False
    
    try:
        from core.prompt_builders import (
            SingleCharacterBuilder, MultiCharacterBuilder, NPCBuilder
        )
        print("[OK] core.prompt_builders")
    except Exception as e:
        print(f"[ERR] core.prompt_builders: {e}")
        return False
    
    try:
        from core.world_loader import WorldLoader
        print("[OK] core.world_loader")
    except Exception as e:
        print(f"[ERR] core.world_loader: {e}")
        return False
    
    try:
        from media.llm_client import LLMClient
        print("[OK] media.llm_client")
    except Exception as e:
        print(f"[ERR] media.llm_client: {e}")
        return False
    
    try:
        from media.image_client import ImageClient
        print("[OK] media.image_client")
    except Exception as e:
        print(f"[ERR] media.image_client: {e}")
        return False
    
    try:
        from media.audio_client import AudioClient
        print("[OK] media.audio_client")
    except Exception as e:
        print(f"[ERR] media.audio_client: {e}")
        return False
    
    try:
        from media.video_client import VideoClient
        print("[OK] media.video_client")
    except Exception as e:
        print(f"[ERR] media.video_client: {e}")
        return False
    
    try:
        from config.settings import Settings, get_settings
        print("[OK] config.settings")
    except Exception as e:
        print(f"[ERR] config.settings: {e}")
        return False
    
    return True


def test_models():
    """Test creazione modelli Pydantic."""
    print("\nTesting models...")
    
    from core.models import GameSession, SceneAnalysis, CompositionType
    
    try:
        session = GameSession(
            world_id="test",
            companion_name="Luna",
            affinity={"Luna": 0}
        )
        print(f"[OK] GameSession created: {session.companion_name}")
    except Exception as e:
        print(f"[ERR] GameSession: {e}")
        return False
    
    try:
        scene = SceneAnalysis(
            primary_subject="Luna",
            secondary_subjects=[],
            composition_type=CompositionType.MEDIUM_SHOT
        )
        print(f"[OK] SceneAnalysis created: {scene.primary_subject}")
    except Exception as e:
        print(f"[ERR] SceneAnalysis: {e}")
        return False
    
    return True


def test_settings():
    """Test settings."""
    print("\nTesting settings...")
    
    from config.settings import get_settings
    
    try:
        settings = get_settings()
        print(f"[OK] Settings loaded")
        print(f"   Mode: {settings.execution_mode}")
        print(f"   SD URL: {settings.sd_url}")
        print(f"   Video available: {settings.video_available}")
    except Exception as e:
        print(f"[ERR] Settings: {e}")
        return False
    
    return True


def test_world_loader():
    """Test caricamento mondi."""
    print("\nTesting world loader...")
    
    from core.world_loader import WorldLoader
    
    try:
        loader = WorldLoader()
        worlds = loader.list_worlds()
        print(f"[OK] Found {len(worlds)} worlds:")
        for w in worlds:
            print(f"   - {w['name']} ({w['id']})")
        
        if worlds:
            world_data = loader.load_world(worlds[0]['id'])
            if world_data:
                companions = list(world_data.get("companions", {}).keys())
                print(f"[OK] Loaded world with companions: {companions}")
            else:
                print("[!] Could not load world data")
    except Exception as e:
        print(f"[ERR] World loader: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


async def test_database():
    """Test database."""
    print("\nTesting database...")
    
    from core.database import DatabaseManager
    from sqlalchemy.ext.asyncio import create_async_engine
    
    try:
        # Usa DB in memoria per test
        db = DatabaseManager("sqlite+aiosqlite:///:memory:")
        await db.create_tables()
        print("[OK] Database tables created")
        
        # Test session
        async with db.get_session() as session:
            from core.database import SessionModel
            test_session = SessionModel(
                world_id="test",
                companion_name="Luna",
                affinity={"Luna": 0}
            )
            session.add(test_session)
            await session.flush()
            print(f"[OK] Test session created: {test_session.id}")
        
    except Exception as e:
        print(f"[ERR] Database: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


def test_prompt_builders():
    """Test prompt builders."""
    print("\nTesting prompt builders...")
    
    from core.prompt_builders import (
        SingleCharacterBuilder, MultiCharacterBuilder
    )
    from core.models import SceneAnalysis, CompositionType, GameSession
    
    try:
        builder = SingleCharacterBuilder()
        
        scene = SceneAnalysis(
            primary_subject="Luna",
            composition_type=CompositionType.MEDIUM_SHOT
        )
        
        session = GameSession(
            id=1,
            world_id="school_life",
            companion_name="Luna",
            current_outfit="teacher_suit",
            affinity={"Luna": 0}
        )
        
        world_data = {
            "companions": {
                "Luna": {
                    "wardrobe": {
                        "teacher_suit": "tight grey pencil skirt..."
                    }
                }
            }
        }
        
        result = builder.build(
            scene, "Luna sitting", ["8k", "photorealistic"],
            session, world_data
        )
        
        print(f"[OK] SingleCharacterBuilder:")
        print(f"   Prompt length: {len(result.positive)}")
        print(f"   First 100 chars: {result.positive[:100]}...")
        
    except Exception as e:
        print(f"[ERR] Prompt builders: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


async def main():
    """Run all tests."""
    print("=" * 50)
    print("LUNA RPG v3 - Basic Tests")
    print("=" * 50)
    
    results = []
    
    results.append(("Imports", test_imports()))
    results.append(("Models", test_models()))
    results.append(("Settings", test_settings()))
    results.append(("World Loader", test_world_loader()))
    results.append(("Database", await test_database()))
    results.append(("Prompt Builders", test_prompt_builders()))
    
    print("\n" + "=" * 50)
    print("Results:")
    print("=" * 50)
    
    for name, passed in results:
        status = "[OK] PASS" if passed else "[ERR] FAIL"
        print(f"{status}: {name}")
    
    all_passed = all(r[1] for r in results)
    
    if all_passed:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print("\n[!] Some tests failed.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
