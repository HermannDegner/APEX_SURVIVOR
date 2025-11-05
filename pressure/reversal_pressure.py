"""
Reversal Pressure Calculator

逆転可能性からの圧力を計算
"""

from typing import Dict, Tuple


def calculate_reversal_pressure(
    current_rank: int,
    score_gap_from_first: int,
    max_points_per_round: int,
    remaining_rounds: int,
    max_set_bonus: int,
    hp: int = 1
) -> Tuple[float, bool]:
    """
    セット内逆転可能性からの圧力を計算
    
    Args:
        current_rank: 現在の順位
        score_gap_from_first: 1位との点差
        max_points_per_round: ラウンドあたり最大獲得可能点数
        remaining_rounds: 残りラウンド数
        max_set_bonus: セット順位ボーナス
        hp: 現在のHP（HP1なら命がけボーナス+30%）
        
    Returns:
        (逆転不可能性スコア, 逆転可能フラグ)
    """
    # HP1の場合、命がけボーナス(+30%)を考慮
    risk_bonus_multiplier = 1.3 if hp == 1 else 1.0
    
    # セット内で残りラウンドで理論上取れる最大点数（命がけボーナス込み）
    max_possible_gain_in_set = int(
        max_points_per_round * remaining_rounds * risk_bonus_multiplier
    )
    
    # 逆転可能性の判定
    reversal_impossibility = 0.0
    reversal_possible = True
    
    if current_rank > 1 and score_gap_from_first > 0:
        if score_gap_from_first > max_possible_gain_in_set + max_set_bonus:
            reversal_impossibility = 2.0  # 理論上逆転不可能
            reversal_possible = False
        elif score_gap_from_first > max_possible_gain_in_set:
            reversal_impossibility = 1.5  # ボーナス頼み
        elif score_gap_from_first > max_possible_gain_in_set * 0.5:
            reversal_impossibility = 1.0  # 全力必要
        else:
            reversal_impossibility = 0.5  # 逆転可能
    
    return reversal_impossibility, reversal_possible


def calculate_overall_reversal_pressure(
    overall_rank: int,
    overall_gap: int,
    current_set: int,
    total_sets: int,
    max_points_per_round: int,
    total_rounds: int,
    remaining_rounds_this_set: int,
    base_max_set_bonus: int,
    env_bonus_multiplier: float,
    environments: Dict[int, str],
    env_enabled: bool
) -> Tuple[float, bool]:
    """
    総合逆転可能性からの圧力を計算
    
    Returns:
        (総合逆転不可能性スコア, 総合逆転可能フラグ)
    """
    if total_sets <= 1 or overall_rank <= 1 or overall_gap <= 0:
        return 0.0, True
    
    remaining_sets = total_sets - current_set
    
    # 将来の環境ボーナス倍率を推定
    if env_enabled and environments:
        future_bonus_multipliers = []
        for future_set in range(current_set + 1, total_sets + 1):
            env_type = environments.get(future_set, 'normal')
            mult = _get_env_bonus_multiplier(env_type)
            future_bonus_multipliers.append(mult)
        
        avg_future_bonus_mult = (
            sum(future_bonus_multipliers) / len(future_bonus_multipliers)
            if future_bonus_multipliers else 1.0
        )
        future_max_set_bonus = int(base_max_set_bonus * avg_future_bonus_mult)
    else:
        future_max_set_bonus = base_max_set_bonus
    
    # 残りセットで取れる最大点数
    max_per_set = (max_points_per_round * total_rounds) + future_max_set_bonus
    max_possible_gain_overall = max_per_set * remaining_sets
    
    # 現在セットの残り獲得可能点数も加算
    max_possible_gain_in_set = max_points_per_round * remaining_rounds_this_set
    max_possible_gain_overall += max_possible_gain_in_set + int(
        base_max_set_bonus * env_bonus_multiplier
    )
    
    # 総合逆転可能性の判定
    overall_reversal_impossibility = 0.0
    overall_reversal_possible = True
    
    if overall_gap > max_possible_gain_overall:
        overall_reversal_impossibility = 2.0  # 総合逆転不可能
        overall_reversal_possible = False
    elif overall_gap > max_possible_gain_overall * 0.8:
        overall_reversal_impossibility = 1.5  # 非常に厳しい
    elif overall_gap > max_possible_gain_overall * 0.5:
        overall_reversal_impossibility = 1.0  # 厳しい
    else:
        overall_reversal_impossibility = 0.5  # 総合逆転可能
    
    return overall_reversal_impossibility, overall_reversal_possible


def _get_env_bonus_multiplier(env_type: str) -> float:
    """環境タイプからボーナス倍率を取得"""
    env_multipliers = {
        'safe': 0.75,
        'normal': 0.90,
        'mild': 1.10,
        'moderate': 1.30,
        'volatile': 1.20,
        'deadly': 1.8
    }
    return env_multipliers.get(env_type, 1.0)
