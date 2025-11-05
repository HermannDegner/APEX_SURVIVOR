"""
ChickenGameクラスの拡張テスト

Phase 5.2: エッジケース・統合テスト
"""
import pytest
import yaml
import random
import numpy as np


class TestChickenGameEdgeCases:
    """エッジケースのテスト"""
    
    @pytest.mark.unit
    def test_game_with_seed_reproducibility(self, test_config_path):
        """同じシードで同じ結果を得る"""
        from core.game import ChickenGame
        
        seed = 99999
        
        # 1回目
        random.seed(seed)
        np.random.seed(seed)
        game1 = ChickenGame(test_config_path)
        initial_players_1 = len(game1.players)
        
        # 2回目
        random.seed(seed)
        np.random.seed(seed)
        game2 = ChickenGame(test_config_path)
        initial_players_2 = len(game2.players)
        
        assert initial_players_1 == initial_players_2
    
    @pytest.mark.unit
    def test_game_has_display(self, test_config_path, fixed_seed):
        """ゲームにDisplayが存在する"""
        from core.game import ChickenGame
        
        game = ChickenGame(test_config_path)
        
        assert hasattr(game, 'display')
        assert game.display is not None


class TestChickenGameIntegration:
    """統合テスト"""
    
    @pytest.mark.integration
    @pytest.mark.parametrize("seed", [12345, 54321, 99999])
    def test_tournament_with_multiple_seeds(self, test_config_path, seed):
        """複数のシードでトーナメントが完走する"""
        from core.game import ChickenGame
        
        random.seed(seed)
        np.random.seed(seed)
        
        game = ChickenGame(test_config_path)
        
        try:
            game.play_tournament()
        except Exception as e:
            pytest.fail(f"Tournament failed with seed {seed}: {e}")
        
        # ゲーム終了後の状態確認
        assert game.players is not None
        assert len(game.players) > 0
    
    @pytest.mark.integration
    @pytest.mark.slow
    def test_tournament_player_scores_increase(self, test_config_path, fixed_seed):
        """トーナメント後にプレイヤーのスコアが増加している"""
        from core.game import ChickenGame
        
        game = ChickenGame(test_config_path)
        
        # 初期スコア
        initial_scores = [p.state.total_score for p in game.players]
        
        # トーナメント実行
        game.play_tournament()
        
        # 最終スコア
        final_scores = [p.state.total_score for p in game.players]
        
        # 少なくとも一部のプレイヤーのスコアが増加している
        assert any(final > initial for final, initial in zip(final_scores, initial_scores))
    
    @pytest.mark.integration
    def test_game_players_have_names(self, test_config_path, fixed_seed):
        """全プレイヤーに名前がある"""
        from core.game import ChickenGame
        
        game = ChickenGame(test_config_path)
        
        for player in game.players:
            assert hasattr(player, 'state')
            assert hasattr(player.state, 'name')
            assert player.state.name is not None
            assert len(player.state.name) > 0


class TestChickenGameConfiguration:
    """設定テスト"""
    
    @pytest.mark.unit
    def test_game_loads_config(self, test_config_path, fixed_seed):
        """ゲームが設定を読み込む"""
        from core.game import ChickenGame
        
        game = ChickenGame(test_config_path)
        
        assert hasattr(game, 'config')
        assert game.config is not None
        assert isinstance(game.config, dict)
    
    @pytest.mark.unit
    def test_game_has_players_list(self, test_config_path, fixed_seed):
        """ゲームにプレイヤーリストがある"""
        from core.game import ChickenGame
        
        game = ChickenGame(test_config_path)
        
        assert hasattr(game, 'players')
        assert isinstance(game.players, list)
        assert len(game.players) > 0


class TestChickenGameStateMachine:
    """状態遷移テスト"""
    
    @pytest.mark.unit
    def test_initial_game_state(self, test_config_path, fixed_seed):
        """ゲーム初期状態が正しい"""
        from core.game import ChickenGame
        
        game = ChickenGame(test_config_path)
        
        # 全プレイヤーが生存している
        alive_count = sum(1 for p in game.players if p.state.is_alive)
        assert alive_count == len(game.players)
    
    @pytest.mark.integration
    @pytest.mark.slow
    def test_game_state_changes_during_tournament(self, test_config_path, fixed_seed):
        """トーナメント中にゲーム状態が変化する"""
        from core.game import ChickenGame
        
        game = ChickenGame(test_config_path)
        
        initial_alive = sum(1 for p in game.players if p.state.is_alive)
        
        game.play_tournament()
        
        # トーナメント終了後の生存者数（変化している可能性がある）
        final_alive = sum(1 for p in game.players if p.state.is_alive)
        
        # 生存者数は減少するか同じ
        assert final_alive <= initial_alive


class TestChickenGamePerformance:
    """パフォーマンステスト"""
    
    @pytest.mark.slow
    def test_tournament_completes_in_reasonable_time(self, test_config_path, fixed_seed):
        """トーナメントが妥当な時間で完了する"""
        import time
        from core.game import ChickenGame
        
        game = ChickenGame(test_config_path)
        
        start_time = time.time()
        game.play_tournament()
        end_time = time.time()
        
        elapsed = end_time - start_time
        
        # 10秒以内に完了する（妥当な時間）
        assert elapsed < 10.0, f"Tournament took {elapsed:.2f}s, expected < 10s"


class TestChickenGameRobustness:
    """堅牢性テスト"""
    
    @pytest.mark.unit
    def test_game_handles_config_file(self, test_config_path, fixed_seed):
        """ゲームが設定ファイルを正しく処理する"""
        from core.game import ChickenGame
        
        # 設定ファイルが存在する
        import os
        assert os.path.exists(test_config_path)
        
        # ゲームが作成できる
        game = ChickenGame(test_config_path)
        assert game is not None
    
    @pytest.mark.integration
    def test_multiple_game_instances(self, test_config_path, fixed_seed):
        """複数のゲームインスタンスが作成できる"""
        from core.game import ChickenGame
        
        games = []
        for i in range(3):
            game = ChickenGame(test_config_path)
            games.append(game)
        
        assert len(games) == 3
        assert all(g is not None for g in games)
