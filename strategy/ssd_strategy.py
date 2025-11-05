"""
SSD Strategy - SSD理論ベースの選択戦略

確率分布を計算して選択を行う
"""

import math
import numpy as np
from typing import List, Dict, Set


class SSDStrategy:
    """SSD理論ベースの戦略クラス"""
    
    def __init__(self, config: Dict, personality_weights: Dict, 
                 nash_enabled: bool = False, band_aware: bool = False):
        self.config = config
        self.personality_weights = personality_weights
        self.nash_equilibrium_enabled = nash_enabled
        self.band_aware = band_aware
        
        # 帯戦略（band_awareの場合に使用）
        self._safe_set: Set[int] = set()
        self._push_set: Set[int] = set()
    
    def make_choice(self, state, ssd_state, meaning_pressure: float, chosen_strategy: str = None) -> List[float]:
        """
        意味圧と状態に基づいて選択の確率分布を返す
        
        Args:
            state: プレイヤーの状態オブジェクト (PlayerState)
            ssd_state: SSD状態オブジェクト (SSDState)
            meaning_pressure: 意味圧の値
            chosen_strategy: 選択された戦略（未使用だが互換性のため残す）
            
        Returns:
            選択確率の配列 (10要素)
        """
        self.state = state  # 一時的に保存 (PlayerState)
        self.ssd_state = ssd_state  # SSD状態
        
        # 確率分布を計算
        probabilities = self._calculate_choice_probabilities(meaning_pressure)
        
        return probabilities
    
    def _calculate_choice_probabilities(self, meaning_pressure: float) -> List[float]:
        """選択肢の確率分布を計算（SSD理論ベース）"""
        # ナッシュ均衡戦略を使用する場合（HP考慮型）
        if self.nash_equilibrium_enabled:
            return self._calculate_hp_aware_nash_strategy(meaning_pressure)
        
        # 【超低圧モード】意味圧が極端に低い場合（0.1未満）
        if meaning_pressure < 0.1:
            ultra_safe_probs = [0.0] * 10
            ultra_safe_probs[0] = 0.60  # 1: 60%
            ultra_safe_probs[1] = 0.30  # 2: 30%
            ultra_safe_probs[2] = 0.08  # 3: 8%
            ultra_safe_probs[3] = 0.02  # 4: 2%
            
            if self.config.get('debug', False):
                print(f"🔒 超低圧モード発動！ (pressure={meaning_pressure:.4f})")
                print(f"   確率分布: 1={ultra_safe_probs[0]:.1%}, 2={ultra_safe_probs[1]:.1%}, "
                      f"3={ultra_safe_probs[2]:.1%}, 4={ultra_safe_probs[3]:.1%}")
            
            return ultra_safe_probs
        
        # 帯戦略を知っている場合は帯をキャリブレーション
        if self.band_aware:
            self._calibrate_bands()
        
        # 温度と意味圧による確率調整
        T_adjusted = self.ssd_state.T * (1 + meaning_pressure * 0.3)
        
        # 過去の成功パターンから学習
        choice_scores = [1.0] * 10  # 1-10の基本スコア
        
        # 帯戦略による重み付け
        choice_scores = self._apply_band_strategy(choice_scores, meaning_pressure)
        
        # 直近の履歴から学習
        choice_scores = self._apply_history_learning(choice_scores)
        
        # 性格による傾向
        choice_scores = self._apply_personality_weights(choice_scores)
        
        # === 死への恐怖による調整（HP状態 vs 敗北死の葛藤） ===
        choice_scores = self._apply_hp_fear_adjustment(choice_scores, meaning_pressure)
        
        # Softmax with temperature
        exp_scores = [math.exp(s / T_adjusted) for s in choice_scores]
        total = sum(exp_scores)
        probabilities = [e / total for e in exp_scores]
        
        return probabilities
    
    def _apply_band_strategy(self, choice_scores: List[float], 
                            meaning_pressure: float) -> List[float]:
        """帯戦略による重み付け"""
        if not self.band_aware or not hasattr(self, '_safe_set'):
            return choice_scores
        
        if meaning_pressure > 5.0:
            # 非常に高意味圧：押し帯を優遇
            for i in range(10):
                if (i + 1) in self._push_set:
                    choice_scores[i] *= 1.8
                elif (i + 1) in self._safe_set:
                    choice_scores[i] *= 0.8
        elif meaning_pressure < 1.5:
            # 非常に低意味圧：安全帯を優遇
            for i in range(10):
                if (i + 1) in self._safe_set:
                    choice_scores[i] *= 1.6
                elif (i + 1) in self._push_set:
                    choice_scores[i] *= 0.8
        else:
            # 中間：両帯を緩やかに優遇
            for i in range(10):
                if (i + 1) in (self._safe_set | self._push_set):
                    choice_scores[i] *= 1.3
        
        return choice_scores
    
    def _apply_history_learning(self, choice_scores: List[float]) -> List[float]:
        """履歴から学習して重み付け"""
        history_len = min(len(self.state.choice_history), 
                         len(self.state.success_history))
        
        for i in range(history_len):
            choice = self.state.choice_history[-(i+1)]
            if self.state.success_history[-(i+1)]:
                choice_scores[choice - 1] += 0.5  # 成功した選択肢を強化
        
        return choice_scores
    
    def _apply_personality_weights(self, choice_scores: List[float]) -> List[float]:
        """性格による傾向を適用"""
        weights = self.personality_weights
        
        for i in range(0, 4):  # 1-4: low_risk
            choice_scores[i] *= weights['low_risk']
        for i in range(4, 7):  # 5-7: medium_risk
            choice_scores[i] *= weights['medium_risk']
        for i in range(7, 10):  # 8-10: high_risk
            choice_scores[i] *= weights['high_risk']
        
        return choice_scores
    
    def _apply_hp_fear_adjustment(self, choice_scores: List[float], 
                                  meaning_pressure: float) -> List[float]:
        """HP状態による恐怖調整"""
        max_hp = self.config['game_rules']['max_hp']
        hp_ratio = self.state.hp / max_hp
        
        if hp_ratio <= 0.2:  # HP=1: 次で死ぬ！
            desperate_situation = (meaning_pressure >= 5.0)
            
            if desperate_situation:
                # 【背水の陣】
                choice_scores[0] *= 10.0   # 1も選択肢に
                for i in range(1, 5):
                    choice_scores[i] *= 5.0   # 2-5を強化
                for i in range(5, 8):
                    choice_scores[i] *= 2.0   # 6-8も選択肢に
                for i in range(8, 10):
                    choice_scores[i] *= 0.5   # 9-10は抑制
            else:
                # 【通常のHP=1恐怖】
                choice_scores[0] *= 100.0   # 1を圧倒的に強化
                for i in range(1, 3):
                    choice_scores[i] *= 3.0   # 2-3も強化
                for i in range(3, 5):
                    choice_scores[i] *= 1.2   # 4-5はわずかに強化
                for i in range(5, 7):
                    choice_scores[i] *= 0.3   # 6-7は大幅抑制
                for i in range(7, 10):
                    choice_scores[i] *= 0.01  # 8-10はほぼゼロ
            
        elif hp_ratio <= 0.4:  # HP=2: 強い恐怖
            fear_factor = (1.0 - hp_ratio) * 5.0
            
            for i in range(0, 5):
                choice_scores[i] *= (1 + fear_factor * 0.8)
            for i in range(5, 7):
                choice_scores[i] *= (1 + fear_factor * 0.3)
            for i in range(7, 10):
                choice_scores[i] *= max(0.1, 1.0 - fear_factor * 0.5)
        
        elif hp_ratio <= 0.6:  # HP=3: 警戒状態
            caution_factor = 1.5
            for i in range(0, 7):  # 1-7を強化
                choice_scores[i] *= caution_factor
            for i in range(8, 10):  # 9-10を減少
                choice_scores[i] *= 0.7
        
        return choice_scores
    
    def _calibrate_bands(self):
        """帯戦略のキャリブレーション（簡略版）"""
        # 実装は省略（必要に応じて追加）
        pass
    
    def _calculate_hp_aware_nash_strategy(self, meaning_pressure: float) -> List[float]:
        """HP考慮型ナッシュ均衡戦略（簡略版）"""
        # 実装は省略（必要に応じて追加）
        # 基本的な確率分布を返す
        return [0.1] * 10
