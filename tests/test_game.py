"""
ChickenGameクラスの単体テスト（実装準拠版）

Phase 5.1.3: ゲームロジックの検証
"""
import pytest


class TestChickenGameSmoke:
    """スモークテスト - 基本的な動作確認"""
    
    @pytest.mark.smoke
    def test_game_can_be_created(self, test_config_path, fixed_seed):
        """ゲームが作成できる"""
        from core.game import ChickenGame
        
        game = ChickenGame(test_config_path)
        
        assert game is not None
        assert game.players is not None
        assert len(game.players) > 0
    
    @pytest.mark.smoke
    @pytest.mark.slow
    def test_game_can_run_tournament(self, test_config_path, fixed_seed):
        """トーナメントが実行できる"""
        from core.game import ChickenGame
        
        game = ChickenGame(test_config_path)
        
        # エラーが出ないことを確認
        try:
            game.play_tournament()
        except Exception as e:
            pytest.fail(f"Tournament failed: {e}")
