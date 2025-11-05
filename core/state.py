"""
Player state management for APEX SURVIVOR
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from collections import defaultdict


@dataclass
class PlayerState:
    """プレイヤーの状態管理（ゲーム固有の状態のみ）
    
    NOTE: SSD理論関連の状態（kappa, E, T等）はssd.state.SSDStateで管理
    """
    name: str
    color: str
    personality: str

    # ゲーム状態
    score: int = 0
    total_score: int = 0  # トータルスコア（全セット通算）
    hp: int = 3           # HP
    is_alive: bool = True # 生存状態

    # 現在の順位情報（HP購入判断用）
    overall_rank: int = None       # 現在の総合順位
    overall_gap: int = None        # 現在の1位との点差

    # 脱落情報
    eliminated_set: int = 0      # 何セット目で脱落したか
    eliminated_round: int = 0    # 何ラウンド目で脱落したか
    eliminated_choice: int = 0   # 脱落時の選択
    elimination_reason: str = "" # 脱落理由
    eliminated_hp: int = 0       # 脱落時のHP
    eliminated_rank: int = 0     # 脱落時のセット内順位
    eliminated_score: int = 0    # 脱落時のセット内スコア
    eliminated_gap: int = 0      # 脱落時の1位との点差（セット内）
    eliminated_overall_rank: int = 0  # 脱落時の総合順位
    eliminated_overall_gap: int = 0   # 脱落時の総合1位との点差
    eliminated_reversal_possible: bool = True  # セット内逆転可能性
    eliminated_overall_reversal_possible: bool = True  # 総合逆転可能性

    # 学習データ（対戦相手の分析用）
    choice_history: List[int] = field(default_factory=list)
    success_history: List[bool] = field(default_factory=list)
    opponent_choices: Dict[str, List[int]] = field(default_factory=lambda: defaultdict(list))

    # 逆転性追跡用
    set_ranks: List[int] = field(default_factory=list)  # 各セット終了時の順位

    # ラウンド結果
    current_choice: int = 0
    crashed: bool = False
    round_score: int = 0
