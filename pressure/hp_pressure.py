"""
HP Pressure Calculator

クラッシュによる即死の恐怖を計算
"""


def calculate_hp_pressure(hp: int, max_hp: int) -> float:
    """
    HP状態からの圧力を計算
    
    Args:
        hp: 現在のHP
        max_hp: 最大HP
        
    Returns:
        HP圧力 (0.0 ~ 2.0程度)
    """
    hp_ratio = hp / max_hp
    
    # HP低い → クラッシュで即死のリスク
    # (1 - hp_ratio)^2 で非線形に増加
    crash_death_fear = (1.0 - hp_ratio) ** 2 * 2.0
    
    return crash_death_fear
