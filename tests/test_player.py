"""
ChickenPlayerクラスの単体テスト（実装準拠版）

Phase 5.1.2: プレイヤーロジックの検証
"""
import pytest
import yaml


class TestChickenPlayerSmoke:
    """スモークテスト - 基本的な動作確認"""
    
    @pytest.mark.smoke
    def test_player_can_be_created(self, test_config_path, fixed_seed):
        """プレイヤーが作成できる"""
        from core.player import ChickenPlayer
        
        with open(test_config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        player = ChickenPlayer(
            name="TestPlayer",
            personality="balanced",
            color="red",
            kappa=0.5,
            E_threshold=5.0,
            T_base=0.8,
            personality_weights={'low_risk': 0.3, 'medium_risk': 0.4, 'high_risk': 0.3},
            opponent_analysis=True,
            nash_equilibrium=True,
            config=config
        )
        
        assert player is not None
        assert player.state.name == "TestPlayer"
    
    @pytest.mark.smoke
    def test_player_can_make_choice(self, test_config_path, fixed_seed):
        """プレイヤーが選択を行える"""
        from core.player import ChickenPlayer
        
        with open(test_config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        player = ChickenPlayer(
            name="TestPlayer",
            personality="balanced",
            color="red",
            kappa=0.5,
            E_threshold=5.0,
            T_base=0.8,
            personality_weights={'low_risk': 0.3, 'medium_risk': 0.4, 'high_risk': 0.3},
            opponent_analysis=True,
            nash_equilibrium=True,
            config=config
        )
        
        choice = player.make_choice(
            round_num=1,
            total_rounds=5,
            is_final_round=False,
            current_rank=1,
            score_gap_from_first=0,
            alive_count=7
        )
        
        assert 1 <= choice <= 10
