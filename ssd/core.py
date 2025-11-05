"""
SSD Core - SSD理論の数理計算コア

主要な機能:
1. 戦略選択 (Strategy Selection)
2. 整合学習 (Coherence Learning)
3. 温度更新 (Temperature Update)
4. 跳躍判定 (Jump Detection)

理論的背景:
- 整合流: j = (G0 + g*κ) * p
- 整合仕事: W = p*j - ρ*j²
- 慣性更新: dκ/dt = η*W - λ(κ - κ_min)
- 圧力蓄積: dE/dt = α[|p| - |J|]+ - β*E
- 温度動態: T = T_base + c1*E + c2*(1 - S/S_max)
- 跳躍確率: P = 1 - exp(-h*Δt), h = h0*exp((E-Θ)/γ)
"""

import numpy as np
from typing import Dict, List
from .state import SSDState


class SSDCore:
    """SSD理論の計算コア（ゲーム非依存）"""
    
    def __init__(self,
                 strategies: Dict[str, Dict],
                 kappa_init: float = 0.3,
                 kappa_min: float = 0.1,
                 T_base: float = 0.8,
                 T_min: float = 0.5,
                 T_max: float = 5.0,
                 eta: float = 0.5,
                 rho: float = 0.2,
                 lambda_forget: float = 0.05,
                 lambda_forget_other: float = 0.02,
                 alpha: float = 0.3,
                 beta_E: float = 0.1,
                 c1: float = 0.5,
                 c2: float = 0.3,
                 jump_threshold: float = 2.0,
                 jump_base_rate: float = 0.1,
                 jump_gamma: float = 0.5):
        """
        Parameters:
            strategies: 戦略定義 {'strategy_name': {...}}
            kappa_init: 初期整合慣性
            kappa_min: 最小整合慣性
            T_base: 基底温度
            T_min/T_max: 温度範囲
            eta: 学習率（慣性更新）
            rho: 抵抗損失係数
            lambda_forget: 自己忘却率
            lambda_forget_other: 他戦略忘却率
            alpha: 圧力感度
            beta_E: 圧力減衰率
            c1/c2: 温度係数
            jump_threshold: 跳躍閾値
            jump_base_rate: 基底跳躍率
            jump_gamma: 跳躍感度
        """
        self.strategies = strategies
        self.kappa_init = kappa_init
        self.kappa_min = kappa_min
        self.T_base = T_base
        self.T_min = T_min
        self.T_max = T_max
        self.eta = eta
        self.rho = rho
        self.lambda_forget = lambda_forget
        self.lambda_forget_other = lambda_forget_other
        self.alpha = alpha
        self.beta_E = beta_E
        self.c1 = c1
        self.c2 = c2
        self.jump_threshold = jump_threshold
        self.jump_base_rate = jump_base_rate
        self.jump_gamma = jump_gamma
        
    def initialize_state(self) -> SSDState:
        """SSD状態を初期化"""
        state = SSDState()
        state.kappa = {s: self.kappa_init for s in self.strategies.keys()}
        state.E = 0.0
        state.T = self.T_base
        return state
    
    def choose_strategy(self, state: SSDState, meaning_pressure: float = 0.0,
                       pressure_thresholds: Dict[str, float] = None) -> str:
        """
        意味圧に基づいて戦略を選択
        
        Args:
            state: SSD状態
            meaning_pressure: 外部からの意味圧
            pressure_thresholds: 圧力閾値 {'high': 5.0, 'medium': 3.0, 'low': 1.5}
        
        Returns:
            選択された戦略名
        """
        if pressure_thresholds is None:
            pressure_thresholds = {'high': 5.0, 'medium': 3.0, 'low': 1.5}
        
        # 整合慣性の調整（意味圧による）
        kappa_adjusted = state.kappa.copy()
        
        if meaning_pressure > pressure_thresholds['high']:
            # 高圧: 高リスク戦略を強化
            for strategy in kappa_adjusted:
                if 'high' in strategy.lower():
                    kappa_adjusted[strategy] *= 1.8
                elif 'medium' in strategy.lower():
                    kappa_adjusted[strategy] *= 1.3
                elif 'low' in strategy.lower():
                    kappa_adjusted[strategy] *= 0.5
                    
        elif meaning_pressure > pressure_thresholds['medium']:
            # 中圧: やや攻撃的
            for strategy in kappa_adjusted:
                if 'high' in strategy.lower():
                    kappa_adjusted[strategy] *= 1.3
                elif 'medium' in strategy.lower():
                    kappa_adjusted[strategy] *= 1.2
                elif 'low' in strategy.lower():
                    kappa_adjusted[strategy] *= 0.8
                    
        elif meaning_pressure < pressure_thresholds['low']:
            # 低圧: 安全策
            for strategy in kappa_adjusted:
                if 'low' in strategy.lower():
                    kappa_adjusted[strategy] *= 2.0
                elif 'medium' in strategy.lower():
                    kappa_adjusted[strategy] *= 0.8
                elif 'high' in strategy.lower():
                    kappa_adjusted[strategy] *= 0.4
        
        # ソフトマックスで戦略選択
        strategy_names = list(self.strategies.keys())
        kappa_values = np.array([kappa_adjusted[s] for s in strategy_names])
        
        probabilities = np.exp(kappa_values / state.T)
        probabilities /= probabilities.sum()
        
        return np.random.choice(strategy_names, p=probabilities)
    
    def update(self, state: SSDState, reward: float, 
               learning_modifiers: Dict[str, float] = None):
        """
        結果を受けてSSD状態を更新
        
        Args:
            state: SSD状態（in-place更新）
            reward: 得られた報酬
            learning_modifiers: 学習修正係数 {'learning_speed': 1.0, ...}
        """
        if not state.last_strategy:
            return
        
        if learning_modifiers is None:
            learning_modifiers = {}
        
        # 報酬の正規化
        normalized_reward = np.tanh(reward / 50.0)
        
        # 【STEP 1】整合仕事の計算
        # W_align = p*j - ρ*j²
        j_approx = normalized_reward
        W_align = normalized_reward - self.rho * (normalized_reward ** 2)
        
        # 【STEP 2】整合慣性（κ）の更新
        # dκ/dt = η*W - λ(κ - κ_min)
        kappa_current = state.kappa[state.last_strategy]
        learning_speed = learning_modifiers.get('learning_speed', 1.0)
        
        dkappa = (self.eta * W_align * learning_speed - 
                 self.lambda_forget * (kappa_current - self.kappa_min))
        
        state.kappa[state.last_strategy] += dkappa
        state.kappa[state.last_strategy] = max(self.kappa_min, 
                                               state.kappa[state.last_strategy])
        
        # 他戦略の忘却
        for strategy in state.kappa:
            if strategy != state.last_strategy:
                state.kappa[strategy] -= (self.lambda_forget_other * 
                                         (state.kappa[strategy] - self.kappa_min))
                state.kappa[strategy] = max(self.kappa_min, state.kappa[strategy])
        
        # 【STEP 3】未処理圧力（E）の蓄積
        # dE/dt = α[|p| - |J|]+ - β*E
        expected_reward = np.tanh(kappa_current)
        pressure_gap = abs(normalized_reward - expected_reward)
        pressure_sensitivity = learning_modifiers.get('pressure_sensitivity', 1.0)
        
        dE = (self.alpha * max(pressure_gap, 0) * pressure_sensitivity - 
             self.beta_E * state.E)
        state.E += dE
        state.E = max(0, state.E)
        
        # 【STEP 4】温度の更新
        self._update_temperature(state, learning_modifiers)
        
        # 【STEP 5】跳躍判定
        jumped = self._check_jump(state, learning_modifiers)
        if jumped:
            state.jump_count += 1
    
    def _update_temperature(self, state: SSDState, 
                           modifiers: Dict[str, float]):
        """温度を更新"""
        kappa_values = np.array(list(state.kappa.values()))
        kappa_prob = kappa_values / kappa_values.sum()
        entropy = -np.sum(kappa_prob * np.log(kappa_prob + 1e-10))
        
        temp_sensitivity = modifiers.get('temperature_sensitivity', 1.0)
        c1 = self.c1 * temp_sensitivity
        
        max_entropy = np.log(len(state.kappa))
        normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0
        
        state.T = (self.T_base + c1 * state.E + 
                  self.c2 * (1 - normalized_entropy))
        state.T = max(self.T_min, min(self.T_max, state.T))
    
    def _check_jump(self, state: SSDState, 
                   modifiers: Dict[str, float]) -> bool:
        """整合跳躍の判定（確率的発火モデル）"""
        threshold_modifier = modifiers.get('jump_threshold_modifier', 1.0)
        
        # 動的閾値: Θ = Θ0 + a1*κ̄
        kappa_mean = np.mean(list(state.kappa.values()))
        a1 = 0.5
        Theta = self.jump_threshold * threshold_modifier + a1 * kappa_mean
        
        if state.E > Theta:
            # 発火強度: h = h0 * exp((E - Θ) / γ) * exp(-κ̄ * 2)
            h = (self.jump_base_rate * 
                np.exp((state.E - Theta) / self.jump_gamma))
            kappa_suppression = np.exp(-kappa_mean * 2.0)
            h *= kappa_suppression
            
            # 跳躍確率: P = 1 - exp(-h * Δt)
            jump_prob = 1.0 - np.exp(-h * 1.0)
            
            if np.random.random() < jump_prob:
                # 跳躍発生: 圧力リセット、温度上昇
                state.E = 0.0
                state.T = min(self.T_max, state.T * 1.5)
                return True
        
        return False
    
    def calculate_strategy_probabilities(self, state: SSDState) -> Dict[str, float]:
        """各戦略の選択確率を計算（分析用）"""
        strategy_names = list(self.strategies.keys())
        kappa_values = np.array([state.kappa[s] for s in strategy_names])
        
        probabilities = np.exp(kappa_values / state.T)
        probabilities /= probabilities.sum()
        
        return {name: prob for name, prob in zip(strategy_names, probabilities)}
