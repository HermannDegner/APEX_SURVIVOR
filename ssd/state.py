"""
SSD State - SSD理論の状態変数

κ (kappa): 整合慣性 (coherence inertia)
E: 未処理圧力 (unprocessed pressure)
T: 温度 (temperature)
"""

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class SSDState:
    """SSD理論の内部状態"""
    
    # コアパラメータ
    kappa: Dict[str, float] = field(default_factory=dict)  # 整合慣性（戦略ごと）
    E: float = 0.0        # 未処理圧力
    T: float = 0.8        # 温度
    
    # 学習履歴
    last_strategy: str = None       # 最後に選択した戦略
    jump_count: int = 0             # 跳躍回数
    expected_reward: float = 0.0    # 期待報酬
    
    def reset_temperature(self):
        """温度のみリセット（学習は保持）"""
        self.T = 0.8
    
    def reset_all(self):
        """すべての状態をリセット"""
        self.kappa.clear()
        self.E = 0.0
        self.T = 0.8
        self.last_strategy = None
        self.jump_count = 0
        self.expected_reward = 0.0
