"""
pytest設定ファイル - テスト共通のフィクスチャとセットアップ
"""
import pytest
import random
import numpy as np
import os
import sys

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


@pytest.fixture
def fixed_seed():
    """固定シードのフィクスチャ - 再現可能なテストのため"""
    seed = 12345
    random.seed(seed)
    np.random.seed(seed)
    return seed


@pytest.fixture
def test_config_path():
    """テスト用の設定ファイルパス"""
    return os.path.join(os.path.dirname(__file__), '..', 'chicken_game_config.yaml')


@pytest.fixture
def sample_player_names():
    """テスト用のプレイヤー名リスト"""
    return [
        "Alice", "Bob", "Charlie", "Diana", "Eve",
        "Frank", "Grace", "Henry", "Ivy", "Jack"
    ]


@pytest.fixture
def mock_ssd_state():
    """モックSSDStateオブジェクト"""
    from ssd.state import SSDState
    
    class MockSSDState(SSDState):
        def __init__(self):
            super().__init__(dimension=5)
            # テスト用の固定値を設定
            self.state = np.array([0.5, 0.3, 0.2, 0.4, 0.1])
    
    return MockSSDState()


@pytest.fixture(autouse=True)
def reset_random_state():
    """各テスト後に乱数状態をリセット"""
    yield
    # テスト後のクリーンアップ
    random.seed(None)
    np.random.seed(None)
