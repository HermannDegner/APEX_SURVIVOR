# 開発者ガイド - APEX SURVIVOR

プロジェクトへの貢献方法とベストプラクティス

---

## 🚀 クイックスタート

### 開発環境のセットアップ

```bash
# 1. リポジトリのクローン
git clone https://github.com/yourusername/apex-survivor.git
cd apex-survivor/casino

# 2. 仮想環境の作成（推奨）
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 依存関係のインストール
pip install -r requirements.txt

# 4. テストの実行
pytest tests/ -v

# 5. カバレッジの確認
pytest tests/ --cov=core --cov=display --cov-report=html
```

---

## 📁 プロジェクト構造

### ディレクトリの役割

```
casino/
├── chicken_game_ssd_ai.py    # エントリーポイント（変更は最小限に）
├── chicken_game_config.yaml  # 設定ファイル
├── requirements.txt          # Python依存関係
├── pytest.ini               # pytest設定
│
├── core/                    # コアロジック（ビジネスロジック）
│   ├── state.py            # 状態管理のみ
│   ├── player.py           # プレイヤーAIロジック
│   └── game.py             # ゲーム進行制御
│
├── ssd/                     # SSD理論実装（再利用可能）
│   ├── core.py
│   └── state.py
│
├── strategy/                # 戦略パターン（拡張しやすい）
│   ├── ssd_strategy.py
│   └── rule_strategy.py
│
├── pressure/                # 意味圧計算（モジュラー）
│   ├── rank_pressure.py
│   ├── score_pressure.py
│   └── ...
│
├── display/                 # 表示系（UI分離）
│   ├── colors.py
│   ├── formatters.py
│   └── game_display.py
│
├── tests/                   # テストスイート
│   ├── test_*.py
│   └── conftest.py
│
└── docs/                    # ドキュメント
    ├── ARCHITECTURE.md
    └── ...
```

---

## 🔧 開発ワークフロー

### 1. 機能追加の流れ

```bash
# 1. Issue作成
# GitHubで機能要望や不具合を報告

# 2. ブランチ作成
git checkout -b feature/new-strategy

# 3. コード実装
# - 型ヒントを使用
# - Docstringを記述
# - テストを書く

# 4. テスト実行
pytest tests/ -v
pytest tests/ --cov=core --cov=display

# 5. コミット
git add .
git commit -m "Add new strategy implementation"

# 6. プッシュ
git push origin feature/new-strategy

# 7. プルリクエスト作成
# - 変更内容を説明
# - テスト結果を添付
```

### 2. コミットメッセージ規約

```
<type>: <subject>

<body>

<footer>
```

**Type:**
- `feat:` 新機能
- `fix:` バグ修正
- `docs:` ドキュメント
- `style:` フォーマット
- `refactor:` リファクタリング
- `test:` テスト追加
- `chore:` ビルド・設定

**例:**
```
feat: Add aggressive strategy module

- Implement AggressiveStrategy class
- Add tests for edge cases
- Update documentation

Closes #123
```

---

## 🎨 コーディング規約

### Pythonスタイルガイド

```python
# 1. インポート順序
import os                    # 標準ライブラリ
import sys

import numpy as np           # サードパーティ
import yaml

from core import Player      # ローカル
from ssd import SSDCore


# 2. 型ヒント使用
def make_choice(
    round_num: int,
    total_rounds: int,
    current_rank: int
) -> int:
    """選択を行う
    
    Args:
        round_num: 現在のラウンド番号
        total_rounds: 総ラウンド数
        current_rank: 現在の順位
    
    Returns:
        1-10の選択値
    """
    pass


# 3. Docstring必須（主要関数）
class MyClass:
    """クラスの説明
    
    より詳細な説明がここに入る
    
    Attributes:
        attr1: 属性1の説明
        attr2: 属性2の説明
    """
    
    def __init__(self):
        """初期化"""
        pass


# 4. プライベートメソッド
class Example:
    def public_method(self):
        """公開メソッド"""
        self._private_method()
    
    def _private_method(self):
        """内部メソッド（アンダースコア接頭辞）"""
        pass


# 5. 定数は大文字
MAX_ROUNDS = 5
DEFAULT_HP = 3
```

### 命名規則

| 要素 | 規則 | 例 |
|------|------|-----|
| クラス | PascalCase | `ChickenPlayer`, `SSDCore` |
| 関数 | snake_case | `make_choice`, `calculate_pressure` |
| 変数 | snake_case | `round_num`, `total_score` |
| 定数 | UPPER_SNAKE_CASE | `MAX_HP`, `DEFAULT_SEED` |
| プライベート | _prefix | `_internal_method` |
| モジュール | snake_case | `ssd_strategy.py` |

---

## 🧪 テストの書き方

### テストファイル構造

```python
"""
test_feature.py - 機能のテスト

テストモジュールの説明
"""
import pytest


class TestFeatureName:
    """機能名のテストグループ"""
    
    @pytest.mark.unit
    def test_basic_functionality(self, fixed_seed):
        """基本機能のテスト"""
        # Arrange (準備)
        player = create_player()
        
        # Act (実行)
        result = player.make_choice()
        
        # Assert (検証)
        assert 1 <= result <= 10
    
    @pytest.mark.parametrize("input,expected", [
        (1, 10),
        (5, 50),
        (10, 100),
    ])
    def test_with_parameters(self, input, expected):
        """パラメータ化テスト"""
        result = calculate(input)
        assert result == expected
    
    @pytest.mark.integration
    @pytest.mark.slow
    def test_integration_scenario(self):
        """統合テスト（時間がかかる）"""
        game = ChickenGame()
        game.play_tournament()
        assert game.players is not None
```

### フィクスチャの使用

```python
# conftest.py
import pytest

@pytest.fixture
def test_config():
    """テスト用設定"""
    return {
        'rounds': 5,
        'players': 7
    }

@pytest.fixture
def sample_player(test_config):
    """サンプルプレイヤー"""
    return ChickenPlayer(config=test_config)
```

### テストマーカー

```python
@pytest.mark.unit          # 単体テスト
@pytest.mark.integration   # 統合テスト
@pytest.mark.slow          # 時間のかかるテスト
@pytest.mark.smoke         # スモークテスト
```

---

## 🔌 拡張ポイント

### 新しい戦略の追加

```python
# strategy/my_strategy.py

from typing import Tuple

class MyStrategy:
    """カスタム戦略の実装"""
    
    def __init__(self, config: dict):
        self.config = config
    
    def make_choice(
        self,
        round_num: int,
        total_rounds: int,
        current_rank: int,
        **kwargs
    ) -> Tuple[int, str]:
        """選択を決定
        
        Returns:
            (choice, comment): 選択値とコメント
        """
        # 独自のロジック実装
        choice = self._calculate_choice(round_num)
        comment = "My custom strategy!"
        
        return choice, comment
    
    def _calculate_choice(self, round_num: int) -> int:
        """選択値の計算"""
        # 実装
        return 5
```

### 新しい意味圧の追加

```python
# pressure/custom_pressure.py

def calculate_custom_pressure(
    player_state: dict,
    game_state: dict
) -> float:
    """カスタム圧力計算
    
    Args:
        player_state: プレイヤー状態
        game_state: ゲーム状態
    
    Returns:
        0.0-1.0の圧力値
    """
    # 独自の圧力計算
    pressure = 0.5
    
    return pressure
```

---

## 📊 パフォーマンス考慮

### 最適化のポイント

```python
# ❌ 避けるべき
for player in players:
    for round in rounds:
        for choice in range(1, 11):
            calculate()  # O(n³)

# ✅ 推奨
precalculated = [calculate(i) for i in range(1, 11)]
for player in players:
    for round in rounds:
        use(precalculated[choice])  # O(n²)
```

### プロファイリング

```python
import cProfile
import pstats

# プロファイリング実行
cProfile.run('game.play_tournament()', 'stats.prof')

# 結果分析
stats = pstats.Stats('stats.prof')
stats.sort_stats('cumulative')
stats.print_stats(20)
```

---

## 🐛 デバッグ方法

### ログの使用

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def make_choice(self):
    logger.debug(f"Making choice for {self.name}")
    choice = self._calculate()
    logger.info(f"Chose: {choice}")
    return choice
```

### デバッグ実行

```bash
# 詳細ログ付き実行
python chicken_game_ssd_ai.py --seed 12345 --verbose

# 特定シードでデバッグ
python -m pdb chicken_game_ssd_ai.py --seed 12345
```

---

## 📚 参考資料

### 内部ドキュメント
- [ARCHITECTURE.md](ARCHITECTURE.md) - アーキテクチャ
- [API_REFERENCE.md](API_REFERENCE.md) - APIリファレンス
- [SSD_THEORY.md](SSD_THEORY.md) - SSD理論詳細

### 外部リンク
- [Python PEP 8](https://pep8-ja.readthedocs.io/)
- [pytest documentation](https://docs.pytest.org/)
- [NumPy documentation](https://numpy.org/doc/)

---

## 💡 よくある質問

### Q: テストが失敗する
**A:** 
```bash
# キャッシュをクリア
pytest --cache-clear

# 詳細ログを見る
pytest -vv --tb=long
```

### Q: カバレッジを上げたい
**A:**
```bash
# カバレッジレポート確認
pytest --cov=core --cov-report=html
# htmlcov/index.htmlを開く

# 未テスト部分を特定
pytest --cov=core --cov-report=term-missing
```

### Q: 新しい環境を追加したい
**A:**
```yaml
# chicken_game_config.yamlに追加
environments:
  MyCustomEnv:
    crash_rates: [0.01, 0.03, ...]
    score_multiplier: 1.5
    bonus_multiplier: 1.2
```

---

## 🤝 コントリビューター

コントリビューションは大歓迎です！

### コントリビューションの種類
- 🐛 バグ報告
- 💡 機能提案
- 📝 ドキュメント改善
- 🧪 テスト追加
- ♻️ リファクタリング
- 🎨 UI改善

### 連絡先
- Issue: GitHub Issues
- Discussion: GitHub Discussions
- Email: contact@example.com

---

**Developer Guide Version: 1.0**  
**Last Updated: 2025-11-05**
