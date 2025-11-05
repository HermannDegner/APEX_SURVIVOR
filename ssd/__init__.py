"""
SSD (Semantic Structure Dynamics) Theory Core Module

汎用的なSSD理論の数理計算コア
他のゲームやシミュレーションでも再利用可能
"""

from .core import SSDCore
from .state import SSDState

__all__ = ['SSDCore', 'SSDState']
