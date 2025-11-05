"""
Multi-Conflict Pressure Calculator

多重構造的葛藤: 3つの死が折り重なる
1. クラッシュによる死 (即死)
2. 敗北による死 (ルール死)
3. 賞金への執着
"""


def calculate_multi_conflict_pressure(
    hp: int,
    max_hp: int,
    current_rank: int,
    score_gap_from_first: int,
    alive_count: int,
    total_score: int,
    reversal_impossibility: float
) -> float:
    """
    多重葛藤からの圧力を計算
    
    Args:
        hp: 現在のHP
        max_hp: 最大HP
        current_rank: 現在の順位
        score_gap_from_first: 1位との点差
        alive_count: 生存プレイヤー数
        total_score: 総合スコア
        reversal_impossibility: 逆転不可能性スコア
        
    Returns:
        多重葛藤圧力
    """
    hp_ratio = hp / max_hp
    
    # === 状況分析 ===
    is_winning = (current_rank <= 2)  # 1-2位
    is_losing = (current_rank >= 5)   # 5位以下
    
    # スコア差の確認
    if alive_count > 1:
        large_gap = (score_gap_from_first > 20)
        very_large_gap = (score_gap_from_first > 50)
    else:
        large_gap = False
        very_large_gap = False
    
    # === 葛藤1: クラッシュによる即死の恐怖 ===
    crash_death_fear = (1.0 - hp_ratio) ** 2 * 2.0
    
    # === 葛藤2: 敗北による死の恐怖 ===
    if is_losing or large_gap:
        defeat_death_fear = 1.2
        if very_large_gap:
            defeat_death_fear = 2.0
        # 逆転不可能性を加算
        defeat_death_fear += reversal_impossibility
    elif is_winning and not large_gap:
        defeat_death_fear = 0.3
    else:
        defeat_death_fear = 0.8
    
    # === 葛藤3: 賞金への執着 ===
    money_attachment = 0.0
    if total_score > 0:
        # 10pts (1億円) で +0.1、100pts (10億円) で +1.0
        money_attachment = (total_score / 100.0) ** 0.5 * 1.0
    
    # === 多重葛藤の折り重なり ===
    if is_winning and not large_gap:
        # 【優勢パターン】守りの意識
        total_death_pressure = (
            crash_death_fear * 1.5 +
            defeat_death_fear * 0.2 +
            money_attachment * 0.3
        )
        total_death_pressure *= 0.7  # 全体的に低圧（守り）
        
    elif is_losing or very_large_gap:
        # 【劣勢パターン】攻めの意識
        total_death_pressure = (
            crash_death_fear * 0.4 +
            defeat_death_fear * 1.5 +
            money_attachment * 0.15
        )
        total_death_pressure *= 1.1  # 全体的に高圧（攻め）
        
    elif large_gap and not is_losing:
        # 【中位だが差がある】やや攻め
        total_death_pressure = (
            crash_death_fear * 0.8 +
            defeat_death_fear * 1.8 +
            money_attachment * 0.4
        )
        total_death_pressure *= 1.2
        
    else:
        # 【中位・競争中】中立
        total_death_pressure = (
            crash_death_fear * 1.0 +
            defeat_death_fear * 1.0 +
            money_attachment * 0.3
        )
    
    # === 終盤戦の多重葛藤強化 ===
    if alive_count <= 3:
        base_endgame_multiplier = (4 - alive_count) * 0.3
        
        if is_winning and hp_ratio > 0.4:
            # 【優勢・終盤】守りの圧力が極大化
            endgame_pressure = base_endgame_multiplier * 1.2
            total_death_pressure *= 0.9  # 慎重に
        elif is_losing or hp_ratio <= 0.4:
            # 【劣勢・終盤】攻めの圧力が極大化
            endgame_pressure = base_endgame_multiplier * 2.0
            total_death_pressure *= 1.15  # やるしかない
        else:
            # 【中位・終盤】最も葛藤が激しい
            endgame_pressure = base_endgame_multiplier * 2.5
        
        total_death_pressure += endgame_pressure
    
    # === 負債による絶望的圧力 ===
    if total_score < 0:
        debt_despair = abs(total_score) / 50.0 * 2.0
        total_death_pressure += debt_despair
    
    return total_death_pressure
