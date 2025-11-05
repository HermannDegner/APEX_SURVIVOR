"""
GameDisplayクラスの単体テスト（実装準拠版）

Phase 5.1.4: 表示機能の検証
"""
import pytest
import yaml


class TestGameDisplaySmoke:
    """スモークテスト - 基本的な動作確認"""
    
    @pytest.mark.smoke
    def test_display_can_be_created(self, test_config_path):
        """Displayが作成できる"""
        from display.game_display import GameDisplay
        
        with open(test_config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        display = GameDisplay(config)
        
        assert display is not None
        assert display.config is not None
