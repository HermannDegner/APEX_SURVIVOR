"""
Elimination Line Pressure Calculator

逆転不可能ライン（死亡確定ライン）接近による圧力
"""

from typing import Dict


def calculate_elimination_line_pressure(
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
    env_enabled: bool,
    debug: bool = False,
    player_name: str = ""
) -> float:
    """
    逆転不可能ライン接近による圧力を計算
    
    Args:
        overall_rank: 総合順位
        overall_gap: 総合1位との点差
        current_set: 現在のセット番号
        total_sets: 総セット数
        max_points_per_round: ラウンドあたり最大獲得可能点数
        total_rounds: 1セットのラウンド数
        remaining_rounds_this_set: 現在セットの残りラウンド数
        base_max_set_bonus: 基本セットボーナス
        env_bonus_multiplier: 環境ボーナス倍率
        environments: 環境設定辞書
        env_enabled: 環境変動が有効か
        debug: デバッグ出力フラグ
        player_name: プレイヤー名（デバッグ用）
        
    Returns:
        排除ライン圧力 (0.0 ~ 5.0)
    """
    if total_sets <= 1 or overall_rank <= 1 or overall_gap <= 0:
        return 0.0
    
    remaining_sets = total_sets - current_set
    
    # 環境を考慮した平均的な最大獲得可能点数を推定
    if env_enabled and environments:
        future_bonus_multipliers = []
        for future_set in range(current_set + 1, total_sets + 1):
            env_type = environments.get(future_set, 'normal')
            mult = _get_env_bonus_multiplier(env_type)
            future_bonus_multipliers.append(mult)
        
        avg_multiplier = (
            sum(future_bonus_multipliers) / len(future_bonus_multipliers)
            if future_bonus_multipliers else 1.0
        )
    else:
        avg_multiplier = 1.0
    
    # 平均的な1セットあたりの最大獲得可能点数
    avg_max_per_set = (
        max_points_per_round * total_rounds +
        int(base_max_set_bonus * avg_multiplier)
    )
    
    # 残りセット全てで最大獲得 + 現在セットの残り最大獲得
    max_possible_gain_in_set = max_points_per_round * remaining_rounds_this_set
    max_set_bonus = int(base_max_set_bonus * env_bonus_multiplier)
    max_possible_gain_overall = (
        avg_max_per_set * remaining_sets +
        max_possible_gain_in_set +
        max_set_bonus
    )
    
    # 逆転不可能ラインまでの余裕
    margin_to_elimination = max_possible_gain_overall - overall_gap
    
    # 閾値を残りセット数に応じて調整
    critical_threshold = avg_max_per_set * 0.3   # 0.3セット分で非常に危険
    danger_threshold = avg_max_per_set * 0.7     # 0.7セット分で危険
    warning_threshold = avg_max_per_set * 1.2    # 1.2セット分で注意
    
    # 圧力の判定
    elimination_line_pressure = 0.0
    
    if margin_to_elimination <= 0:
        # すでに逆転不可能 = 死亡確定
        elimination_line_pressure = 5.0
        status = "逆転不可能"
    elif margin_to_elimination < critical_threshold:
        # 非常に危険: わずかなミスで逆転不可能
        elimination_line_pressure = 3.0
        status = f"余裕{margin_to_elimination:.0f}pts"
    elif margin_to_elimination < danger_threshold:
        # 危険: 余裕がなくなってきた
        elimination_line_pressure = 2.0
        status = f"余裕{margin_to_elimination:.0f}pts"
    elif margin_to_elimination < warning_threshold:
        # 注意: そろそろ攻めないと危ない
        elimination_line_pressure = 1.0
        status = f"余裕{margin_to_elimination:.0f}pts"
    else:
        status = None
    
    # デバッグ出力
    if debug and elimination_line_pressure > 0 and status:
        print(f"[{player_name}] 逆転不可能ライン接近: {status}, "
              f"圧力+{elimination_line_pressure:.1f}")
    
    return elimination_line_pressure


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
