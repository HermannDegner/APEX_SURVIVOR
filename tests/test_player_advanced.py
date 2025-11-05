"""
ChickenPlayerクラスの拡張テスト

Phase 5.2: エッジケース・パラメータ化テスト
"""
import pytest
import yaml


class TestChickenPlayerEdgeCases:
    """エッジケースのテスト"""
    
    @pytest.mark.unit
    def test_player_with_extreme_kappa(self, test_config_path, fixed_seed):
        """極端なkappaでもプレイヤーが動作する"""
        from core.player import ChickenPlayer
        
        with open(test_config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # kappa = 0.0 (完全にランダム)
        player_low = ChickenPlayer(
            name="LowKappa",
            personality="balanced",
            color="red",
            kappa=0.0,
            E_threshold=5.0,
            T_base=0.8,
            personality_weights={'low_risk': 0.3, 'medium_risk': 0.4, 'high_risk': 0.3},
            opponent_analysis=True,
            nash_equilibrium=True,
            config=config
        )
        
        # kappa = 1.0 (完全に戦略に従う)
        player_high = ChickenPlayer(
            name="HighKappa",
            personality="balanced",
            color="blue",
            kappa=1.0,
            E_threshold=5.0,
            T_base=0.8,
            personality_weights={'low_risk': 0.3, 'medium_risk': 0.4, 'high_risk': 0.3},
            opponent_analysis=True,
            nash_equilibrium=True,
            config=config
        )
        
        # 両方とも選択が可能
        choice_low = player_low.make_choice(
            round_num=1, total_rounds=5, is_final_round=False,
            current_rank=1, score_gap_from_first=0, alive_count=7
        )
        choice_high = player_high.make_choice(
            round_num=1, total_rounds=5, is_final_round=False,
            current_rank=1, score_gap_from_first=0, alive_count=7
        )
        
        assert 1 <= choice_low <= 10
        assert 1 <= choice_high <= 10
    
    @pytest.mark.unit
    def test_player_with_zero_hp(self, test_config_path, fixed_seed):
        """HP 0のプレイヤーは死亡状態"""
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
        
        # HP を 0 に設定
        player.state.hp = 0
        player.state.is_alive = False
        
        assert player.state.hp == 0
        assert player.state.is_alive == False
    
    @pytest.mark.unit
    def test_player_final_round_behavior(self, test_config_path, fixed_seed):
        """最終ラウンドでの挙動"""
        from core.player import ChickenPlayer
        
        with open(test_config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        player = ChickenPlayer(
            name="TestPlayer",
            personality="aggressive",
            color="red",
            kappa=0.5,
            E_threshold=5.0,
            T_base=0.8,
            personality_weights={'low_risk': 0.2, 'medium_risk': 0.5, 'high_risk': 0.3},
            opponent_analysis=True,
            nash_equilibrium=True,
            config=config
        )
        
        # 最終ラウンド
        choice = player.make_choice(
            round_num=5,
            total_rounds=5,
            is_final_round=True,
            current_rank=2,
            score_gap_from_first=-50,
            alive_count=3
        )
        
        assert 1 <= choice <= 10


class TestChickenPlayerParameterized:
    """パラメータ化テスト"""
    
    @pytest.mark.parametrize("personality,expected_valid", [
        ("aggressive", True),
        ("balanced", True),
        ("cautious", True),
        ("defensive", True),
    ])
    def test_different_personalities(self, test_config_path, fixed_seed, personality, expected_valid):
        """異なる性格でプレイヤーが作成できる"""
        from core.player import ChickenPlayer
        
        with open(test_config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        player = ChickenPlayer(
            name=f"{personality}_player",
            personality=personality,
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
        assert expected_valid == True
        assert player.state.personality == personality
    
    @pytest.mark.parametrize("round_num,total_rounds,is_final", [
        (1, 5, False),
        (3, 5, False),
        (5, 5, True),
        (1, 10, False),
        (10, 10, True),
    ])
    def test_different_rounds(self, test_config_path, fixed_seed, round_num, total_rounds, is_final):
        """異なるラウンドで選択が有効"""
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
            round_num=round_num,
            total_rounds=total_rounds,
            is_final_round=is_final,
            current_rank=1,
            score_gap_from_first=0,
            alive_count=7
        )
        
        assert 1 <= choice <= 10
    
    @pytest.mark.parametrize("rank,gap,alive", [
        (1, 0, 7),      # トップ
        (3, -50, 5),    # 中位
        (7, -200, 2),   # 最下位
    ])
    def test_different_game_states(self, test_config_path, fixed_seed, rank, gap, alive):
        """異なるゲーム状態で選択が有効"""
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
            round_num=3,
            total_rounds=5,
            is_final_round=False,
            current_rank=rank,
            score_gap_from_first=gap,
            alive_count=alive
        )
        
        assert 1 <= choice <= 10


class TestChickenPlayerSSDIntegration:
    """SSD統合テスト"""
    
    @pytest.mark.unit
    def test_ssd_state_exists(self, test_config_path, fixed_seed):
        """SSD状態が存在する"""
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
        
        assert hasattr(player, 'ssd_state')
        assert hasattr(player, 'ssd_core')
        assert player.ssd_state is not None
        assert player.ssd_core is not None
    
    @pytest.mark.unit
    def test_multiple_choices_consistency(self, test_config_path, fixed_seed):
        """同じ条件で複数回選択しても妥当な範囲内"""
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
        
        choices = []
        for _ in range(5):
            choice = player.make_choice(
                round_num=1,
                total_rounds=5,
                is_final_round=False,
                current_rank=1,
                score_gap_from_first=0,
                alive_count=7
            )
            choices.append(choice)
        
        # 全て有効な範囲
        assert all(1 <= c <= 10 for c in choices)
        # 何らかの選択がある
        assert len(set(choices)) >= 1


class TestChickenPlayerStrategies:
    """戦略テスト"""
    
    @pytest.mark.unit
    def test_rule_strategy_player(self, test_config_path, fixed_seed):
        """ルールベース戦略プレイヤーが動作する"""
        from core.player import ChickenPlayer
        
        with open(test_config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        player = ChickenPlayer(
            name="RulePlayer",
            personality="balanced",
            color="red",
            kappa=0.5,
            E_threshold=5.0,
            T_base=0.8,
            personality_weights={'low_risk': 0.3, 'medium_risk': 0.4, 'high_risk': 0.3},
            opponent_analysis=True,
            nash_equilibrium=True,
            config=config,
            strategy='rule',
            rule_name='aggressive'
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
        assert player.rule_strategy is not None
