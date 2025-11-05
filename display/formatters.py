"""
Display formatting utilities
"""

from typing import Tuple
from .colors import Colors


def format_money(points: int) -> str:
    """ポイントを金額表示に変換（10pt = 1億円）"""
    oku = points / 10.0
    if oku >= 0:
        return f"¥{oku:.1f}億円"
    else:
        return f"-¥{abs(oku):.1f}億円"


def format_score_with_money(points: int) -> str:
    """ポイントと金額を両方表示"""
    return f"{points}pts ({format_money(points)})"


def get_risk_level(choice: int, crash_prob: float) -> Tuple[str, str, str]:
    """
    リスクレベルを判定
    Returns: (レベル名, 色, 記号)
    """
    if crash_prob <= 0.15:  # 1-3: 5-15%
        return "SAFE", Colors.GREEN, "✓"
    elif crash_prob <= 0.25:  # 4-5: 20-25%
        return "LOW", Colors.CYAN, "▲"
    elif crash_prob <= 0.35:  # 6: 35%
        return "MID", Colors.YELLOW, "⚠"
    elif crash_prob <= 0.55:  # 7-8: 45-55%
        return "HIGH", Colors.RED + Colors.BOLD, "⚠⚠"
    else:  # 9-10: 65-75%
        return "DEADLY", Colors.RED + Colors.BOLD, "💀"


def format_choice_with_risk(choice: int, crash_prob: float) -> str:
    """選択肢をリスクレベル付きで表示"""
    level, color, symbol = get_risk_level(choice, crash_prob)
    return f"{color}{choice} [{level} {int(crash_prob*100)}%] {symbol}{Colors.RESET}"
