"""
ChickenPlayer - SSD理論ベースのチキンゲームプレイヤー

Phase 4で分離: メインファイルから抽出（1144行）
"""

import random
import numpy as np
from typing import List, Dict

from .state import PlayerState
from display.colors import Colors
from ssd.core import SSDCore
from strategy import SSDStrategy, RuleStrategy
from pressure import MeaningPressureCalculator


class ChickenPlayer:
    """SSD理論ベースのチキンゲームプレイヤー"""
    
    def __init__(self, name: str, personality: str, color: str, 
                 kappa: float, E_threshold: float, T_base: float, 
                 personality_weights: dict, opponent_analysis: bool, 
                 nash_equilibrium: bool, config: dict, 
                 strategy: str = 'ssd', rule_name: str = None, 
                 band_aware: bool = False):
        
        self.is_ai = personality != 'human'
        self.config = config
        self.pressure_calc = MeaningPressureCalculator(config)
        self.jump_threshold = E_threshold  # 属性として保存（_speak_choiceで使用）
        starting_hp = self.config['game_rules']['starting_hp']
        starting_score = self.config['game_rules'].get('starting_score', 0)
        
        # 戦略の定義
        self.strategies = {
            'low_risk': {'range': (1, 4)},
            'medium_risk': {'range': (5, 7)},
            'high_risk': {'range': (8, 10)}
        }
        
        # SSDパラメータの初期化
        ssd_cfg = self.config['ssd_theory']
        
        # ========== SSDCore初期化 (Phase 1.5) ==========
        self.ssd_core = SSDCore(
            strategies=self.strategies,
            kappa_init=kappa,
            kappa_min=ssd_cfg['learning'].get('kappa_min', 0.1),
            T_base=T_base,
            T_min=ssd_cfg['semantic_jump'].get('T_min', 0.1),
            T_max=ssd_cfg['semantic_jump'].get('T_max', 5.0),
            eta=ssd_cfg['learning'].get('eta', 0.1),
            rho=ssd_cfg['learning'].get('rho', 0.05),
            lambda_forget=ssd_cfg['learning'].get('lambda_forget', 0.01),
            lambda_forget_other=ssd_cfg['learning'].get('lambda_forget_other', 0.005),
            alpha=ssd_cfg['meaning_pressure'].get('alpha', 0.1),
            beta_E=ssd_cfg['meaning_pressure'].get('beta_E', 0.05),
            c1=ssd_cfg['semantic_jump'].get('c1', 0.2),
            c2=ssd_cfg['semantic_jump'].get('c2', 0.1),
            jump_threshold=E_threshold,
            jump_base_rate=ssd_cfg['semantic_jump'].get('jump_base_rate', 0.1),
            jump_gamma=ssd_cfg['semantic_jump'].get('jump_gamma', 1.0)
        )
        
        # SSD状態を初期化
        self.ssd_state = self.ssd_core.initialize_state()
        self.ssd_state.E = ssd_cfg['learning'].get('E_initial', 0.0)
        
        # PlayerState（ゲーム状態の管理）
        # ※ SSDStateはssd_coreで管理、PlayerStateはゲーム固有の状態
        self.state = PlayerState(
            name=name,
            color=color,
            personality=personality,
            hp=starting_hp,
            score=starting_score,
            total_score=starting_score
        )
        
        # パラメータ設定
        self.comment_prob = self.config['comments']['probability']
        self.personality_weights = personality_weights
        self.opponent_analysis_enabled = opponent_analysis
        self.nash_equilibrium_enabled = nash_equilibrium # 今は直接使わないが互換性のため残す
        self.strategy = strategy
        self.rule_name = rule_name
        self.band_aware = band_aware
        
        # ========== 戦略モジュール初期化 (Phase 3) ==========
        # SSD戦略
        self.ssd_strategy = SSDStrategy(
            config=self.config,
            personality_weights=self.personality_weights,
            nash_enabled=self.nash_equilibrium_enabled,
            band_aware=self.band_aware
        )
        
        # ルール戦略
        if self.rule_name:
            self.rule_strategy = RuleStrategy(
                config=self.config,
                rule_name=self.rule_name
            )
        else:
            self.rule_strategy = None
        
    def _get_color_text(self, text: str) -> str:
        """色付きテキストを返す"""
        color = Colors.get_color(self.state.color)
        return f"{color}{text}{Colors.RESET}"
    
    def _speak_choice(self, choice: int):
        """選択時のコメント"""
        if random.random() > self.comment_prob:
            return
            
        comments = self.config['comments']['choice_comments']
        
        # HP瀕死の場合（死の意味圧）
        max_hp = self.config['game_rules']['max_hp']
        if self.state.hp <= max_hp * 0.4:  # HP 40%以下
            comment = random.choice(comments['death_pressure'])
        # 高額賞金がある場合（賞金の意味圧）
        elif self.state.total_score >= 50:  # 5億円以上
            if random.random() < 0.5:  # 50%の確率で賞金への言及
                comment = random.choice(comments.get('money_pressure', comments['death_pressure']))
            else:
                # 通常コメント
                if choice <= 4:
                    comment = random.choice(comments['low_risk'])
                elif choice <= 7:
                    comment = random.choice(comments['medium_risk'])
                else:
                    comment = random.choice(comments['high_risk'])
        # 負債がある場合（借金の意味圧）
        elif self.state.total_score <= -30:  # -3億円以下
            if random.random() < 0.5:
                comment = random.choice(comments.get('debt_pressure', comments['desperate']))
            else:
                comment = random.choice(comments['desperate'])
        # 意味圧が極めて高い場合（大差で負けている時）
        elif self.ssd_state.E > self.jump_threshold * 2.0:
            comment = random.choice(comments['desperate'])
        # ナッシュ均衡型は専用コメント
        elif self.nash_equilibrium_enabled:
            comment = random.choice(comments['nash'])
        elif choice <= 4:
            comment = random.choice(comments['low_risk'])
        elif choice <= 7:
            comment = random.choice(comments['medium_risk'])
        elif choice <= 9:
            comment = random.choice(comments['high_risk'])
        else:
            comment = random.choice(comments['extreme_risk'])
        
        print(f"{self._get_color_text(self.state.name)}: {comment}")
    
    def _speak_success(self, choice: int):
        """成功時のコメント"""
        if random.random() > self.comment_prob:
            return
            
        comments = self.config['comments']['success_comments']
        if choice >= 10:
            comment = random.choice(comments['extreme_risk'])
        elif choice >= 8:
            comment = random.choice(comments['high_risk'])
        else:
            comment = random.choice(comments['normal'])
        
        print(f"{self._get_color_text(self.state.name)}: {comment}")
    
    def _speak_crash(self):
        """クラッシュ時のコメント"""
        if random.random() > self.comment_prob:
            return
            
        comments = self.config['comments']['crash_comments']
        comment = random.choice(comments)
        print(f"{self._get_color_text(self.state.name)}: {comment}")
    
    def _speak_victory(self):
        """勝利時のコメント"""
        if random.random() > self.comment_prob:
            return
            
        comments = self.config['comments']['victory_comments']
        comment = random.choice(comments)
        print(f"{self._get_color_text(self.state.name)}: {comment}")
    
    def _speak_defeat(self):
        """敗北時のコメント"""
        if random.random() > self.comment_prob:
            return
            
        comments = self.config['comments']['defeat_comments']
        comment = random.choice(comments)
        print(f"{self._get_color_text(self.state.name)}: {comment}")
    
    def _analyze_opponents(self) -> Dict[str, float]:
        """他プレイヤーの行動パターンを分析"""
        analysis_config = self.config['opponent_analysis']
        opponent_tendencies = {}
        
        for opponent_name, choices in self.state.opponent_choices.items():
            if len(choices) < analysis_config['min_history_length']:
                # 履歴不足の場合は中立値
                opponent_tendencies[opponent_name] = 5.5
                continue
            
            # 直近の選択に重みをつけて平均計算
            recent_weight = analysis_config['recent_weight']
            total_weight = 0
            weighted_sum = 0
            
            for i, choice in enumerate(choices):
                # 新しい選択ほど高い重み
                weight = recent_weight if i >= len(choices) - 3 else 1.0
                weighted_sum += choice * weight
                total_weight += weight
            
            avg_choice = weighted_sum / total_weight if total_weight > 0 else 5.5
            opponent_tendencies[opponent_name] = avg_choice
        
        return opponent_tendencies
    
    def _adjust_for_opponent_analysis(self, choice_scores: List[float]) -> List[float]:
        """他プレイヤー分析に基づいて選択確率を調整"""
        if not self.opponent_analysis_enabled:
            return choice_scores
        
        analysis_config = self.config['opponent_analysis']
        opponent_tendencies = self._analyze_opponents()
        
        if not opponent_tendencies:
            return choice_scores
        
        # 全対戦相手の平均的な攻撃性を計算
        avg_opponent_choice = sum(opponent_tendencies.values()) / len(opponent_tendencies)
        
        # 相手が攻撃的なら、さらに上を狙う（計算型の戦略）
        if avg_opponent_choice >= analysis_config['aggressive_threshold']:
            # 相手より1-2高い値を狙う
            target_range_start = int(min(9, avg_opponent_choice + 0.5))
            target_range_end = int(min(10, avg_opponent_choice + 2))
            for i in range(target_range_start - 1, target_range_end):
                if 0 <= i < 10:
                    choice_scores[i] *= 1.4
        
        # 相手が慎重なら、中リスクで勝てる
        elif avg_opponent_choice <= analysis_config['conservative_threshold']:
            # 相手より少し高い安全圏を狙う
            target_range_start = int(min(6, avg_opponent_choice + 1))
            target_range_end = int(min(8, avg_opponent_choice + 3))
            for i in range(target_range_start - 1, target_range_end):
                if 0 <= i < 10:
                    choice_scores[i] *= 1.3
        
        return choice_scores
    
    # ========================================================================
    # DEPRECATED: 以下のメソッドは Phase 3 で strategy/ モジュールに移動しました
    # 2024-11-05: strategy/ssd_strategy.py と strategy/rule_strategy.py を参照
    # ========================================================================
    # 削除されたメソッド:
    # - _risk_score()
    # - _leverage_score()
    # - _calibrate_bands()
    # - _rule_choice()
    # - _get_rule_comment()
    # - _calculate_hp_aware_nash_strategy()
    # - _calculate_choice_probabilities()
    # ========================================================================
    
    def make_choice(self, round_num: int, total_rounds: int,
                   is_final_round: bool, current_rank: int, 
                   score_gap_from_first: int, alive_count: int = 7,
                   current_set: int = 1, total_sets: int = 1,
                   overall_rank: int = 1, overall_gap: int = 0,
                   env_bonus_multiplier: float = 1.0) -> int:
        """1-10の選択を行う（Phase 3: 戦略モジュール統合版）"""
        
        # 残りラウンド数を計算
        remaining_rounds = total_rounds - round_num
        
        # 意味圧を計算
        # 意味圧を計算（Phase 7.3: モジュール化されたpressure/を使用）
        pressure_result = self.pressure_calc.calculate(
            round_num=round_num,
            total_rounds=total_rounds,
            is_final_round=is_final_round,
            hp=self.state.hp,
            total_score=self.state.total_score,
            current_rank=current_rank,
            score_gap_from_first=score_gap_from_first,
            remaining_rounds=remaining_rounds,
            current_set=current_set,
            total_sets=total_sets,
            overall_rank=overall_rank,
            overall_gap=overall_gap,
            alive_count=alive_count,
            env_bonus_multiplier=env_bonus_multiplier
        )
        meaning_pressure = pressure_result['pressure']
        # ルールベースAIの場合
        if self.rule_strategy:
            choice, comment = self.rule_strategy.make_choice(
                round_num=round_num,
                total_rounds=total_rounds,
                is_final_round=is_final_round,
                current_rank=current_rank,
                score_gap_from_first=score_gap_from_first,
                hp=self.state.hp,
                opponent_choices=self.state.opponent_choices
            )
            
            self.state.current_choice = choice
            self.state.choice_history.append(choice)
            self._speak_choice(choice)
            return choice
        
        # SSD AIの場合
        # 【STEP 1】戦略の選択
        chosen_strategy = self._choose_strategy(meaning_pressure, alive_count)
        
        # 【STEP 2】SSDStrategyで選択肢の確率分布を計算
        choice_probabilities = self.ssd_strategy.make_choice(
            state=self.state,
            ssd_state=self.ssd_state,
            meaning_pressure=meaning_pressure,
            chosen_strategy=chosen_strategy
        )
        
        # 【STEP 3】確率分布に基づいて選択
        import numpy as np
        choice = np.random.choice(range(1, 11), p=choice_probabilities)
        
        self.state.current_choice = choice
        self.state.choice_history.append(choice)
        
        self._speak_choice(choice)
        return choice

    def _choose_strategy(self, meaning_pressure: float, alive_count: int = 7) -> str:
        """SSDに基づいて戦略を選択（SSDCore使用版 - Phase 1.5）"""
        # SSDCoreに戦略選択を委譲
        strategy = self.ssd_core.choose_strategy(
            self.ssd_state,
            meaning_pressure=meaning_pressure,
            pressure_thresholds={'high': 5.0, 'medium': 3.0, 'low': 1.5}
        )
        
        # SSDStateを更新
        self.ssd_state.last_strategy = strategy
        
        return strategy

    def update_ssd(self, score_change: int):
        """結果を処理して学習（SSDCore使用版 - Phase 1.5）"""
        if not self.ssd_state.last_strategy:
            return
        
        # SSDCoreに学習を委譲
        learning_modifiers = {
            'learning_speed': self.personality_weights.get('learning_speed', 1.0),
            'pressure_sensitivity': self.personality_weights.get('pressure_sensitivity', 1.0),
            'temperature_sensitivity': self.personality_weights.get('temperature_sensitivity', 1.0),
            'jump_threshold_modifier': self.personality_weights.get('jump_threshold_modifier', 1.0)
        }
        
        self.ssd_core.update(self.ssd_state, score_change, learning_modifiers)
        
    
    def _update_temperature(self):
        """温度を更新（SSDCoreに委譲）"""
        # このメソッドは互換性のため残すが、実際はSSDCore.updateで更新される
        pass
    
    def _maybe_jump(self):
        """整合跳躍の判定（SSDCoreに委譲）"""
        # このメソッドは互換性のため残すが、実際はSSDCore.updateで判定される
        pass

    def process_result(self, crashed: bool, score_change: int, success: bool):
        """結果を処理して学習"""
        self.state.crashed = crashed
        self.state.round_score = score_change
        self.state.score += score_change
        self.state.success_history.append(success)
        
        # コメント
        if crashed:
            self._speak_crash()
        elif success and self.state.current_choice >= 8:
            self._speak_success(self.state.current_choice)
        
        # 新しい学習メソッドを呼び出す
        self.update_ssd(score_change)
    
    def reset_round_state(self):
        """ラウンド状態をリセット"""
        self.state.current_choice = 0
        self.state.crashed = False
        self.state.round_score = 0
    
    def reset_set_score(self):
        """セットスコアを保存してリセット"""
        self.state.total_score += self.state.score
        self.state.score = 0
        # 温度をリセット（学習は保持） - SSDCore経由
        self.ssd_state.reset_temperature()
        # NOTE: PlayerStateにはTがないため同期不要
        # HPはリセットしない（購入制に変更）
        # 生存状態は維持
    
    def decide_hp_purchase(self) -> int:
        """HP購入判断（SSD理論ベース）"""
        hp_cost = self.config['game_rules']['hp_purchase_cost']
        max_hp = self.config['game_rules']['max_hp']
        
        current_hp = self.state.hp
        current_score = self.state.score
        
        # 購入可能な最大HP数
        max_affordable = current_score // hp_cost
        max_needed = max_hp - current_hp
        max_purchasable = min(max_affordable, max_needed)
        
        if max_purchasable <= 0:
            return 0
        
        # === SSD理論による意味圧計算 ===
        
        # 1. HP欠損による意味圧（生存リスク）- 死への恐怖を強く反映
        hp_ratio = current_hp / max_hp
        
        # HP=1の時は極めて強い購入圧力
        if current_hp == 1:
            hp_pressure = 10.0  # 非常に高い圧力
        elif current_hp == 2:
            hp_pressure = 5.0   # 高い圧力
        else:
            hp_deficit = max_hp - current_hp
            hp_pressure = (hp_deficit / max_hp) * 2.0  # 通常の圧力
        
        # 2. スコア余裕度（リソース制約圧力）
        score_threshold = hp_cost * 2  # 最低2HP分の余裕が欲しい
        if current_score < score_threshold:
            resource_pressure = (score_threshold - current_score) / score_threshold
        else:
            resource_pressure = 0.0
        
        # 3. 総合意味圧
        total_pressure = hp_pressure - resource_pressure * 0.5  # リソース不足は購入を抑制
        
        # 現在の未処理圧E（ゲームでの累積圧力を使用）
        E_current = self.state.E
        
        # === 整合性判断（κとの比較）===
        # HP購入の整合性 = 「生き残るためにリソースを使う」という行動の妥当性
        purchase_coherence = total_pressure  # 圧力が高いほど購入は整合的
        
        # κ（整合性閾値）の平均値を使用
        avg_kappa = np.mean(list(self.ssd_state.kappa.values())) if self.ssd_state.kappa else 0.5

        # κ（整合性閾値）より高ければ購入が妥当
        if purchase_coherence < avg_kappa:
            # 整合性が低い → 購入しない（または少なく）
            if current_hp <= 1:
                # ただし瀕死なら最低限購入
                return min(1, max_purchasable)
            return 0
        
        # === 温度パラメータTによるランダム性 ===
        
        # 各購入数の評価値を計算
        purchase_scores = []
        for num_hp in range(max_purchasable + 1):
            # 購入後の状態評価
            hp_after = current_hp + num_hp
            score_after = current_score - (num_hp * hp_cost)
            
            # HP価値: 生存確率の向上
            hp_value = (hp_after / max_hp) ** 1.5 * 100  # HPが多いほど価値が高い
            
            # スコア価値: 残りスコアの重要性
            score_value = max(0, score_after) * 0.5  # スコアも重要
            
            # 意味圧による修正（圧力が高いほどHP重視）
            pressure_weight = 1.0 + total_pressure * 0.5
            
            total_value = hp_value * pressure_weight + score_value
            purchase_scores.append(total_value)
        
        # 温度Tでソフトマックス
        T = self.state.T
        # ゼロ除算を避けるための微小値
        epsilon = 1e-9
        exp_scores = np.exp(np.array(purchase_scores) / (T * 50))
        probabilities = exp_scores / (np.sum(exp_scores) + epsilon)
        
        # 確率分布に従って購入数を決定
        chosen_purchase = np.random.choice(len(purchase_scores), p=probabilities)
        
        return chosen_purchase
    
    def decide_hp_purchase_with_environment(self, next_environment: str, risk_multiplier: float) -> int:
        """環境を考慮したHP購入判断（SSD理論ベース）- 購入数を返す"""
        hp_cost = self.config['game_rules']['hp_purchase_cost']
        max_hp = self.config['game_rules']['max_hp']
        
        current_hp = self.state.hp
        current_score = self.state.total_score
        
        # 購入可能な最大数を計算
        max_affordable = current_score // hp_cost
        max_needed = max_hp - current_hp
        max_purchasable = min(max_affordable, max_needed)
        
        if max_purchasable <= 0:
            return 0
        
        # === SSD理論による意味圧計算 ===
        
        # 1. 生存圧力（HP欠損による死の恐怖）
        hp_ratio = current_hp / max_hp
        survival_pressure = (1.0 - hp_ratio) ** 2  # 0.0～1.0
        
        # 2. 環境リスク圧力
        env_risk_pressure = 0.0
        if next_environment == "deadly":
            env_risk_pressure = 1.0  # 最大リスク
        elif next_environment == "moderate":
            env_risk_pressure = 0.6
        elif next_environment == "mild":
            env_risk_pressure = 0.3
        elif next_environment == "normal":
            env_risk_pressure = 0.2
        else:  # safe
            env_risk_pressure = 0.1
        
        # 3. 逆転圧力（順位と差による戦略的圧力）
        reversal_pressure = 0.0
        
        # HP1の場合、命がけボーナス(+30%)があるため逆転可能性が高まる
        # → HP購入の緊急度が下がる（攻撃でポイント稼ぐ選択肢が魅力的）
        hp1_risk_bonus = 1.3 if current_hp == 1 else 1.0
        
        if not self.state.is_alive:
            # 脱落済み：逆転不可能 → 生存優先
            reversal_pressure = 1.0
        elif self.state.overall_rank is not None:
            my_rank = self.state.overall_rank
            my_gap = self.state.overall_gap if self.state.overall_gap is not None else 0
            
            # 順位による基礎圧力（1位=安定、下位=不安定）
            rank_factor = (my_rank - 1) / 6.0  # 0.0(1位)～1.0(7位)
            
            # 点差による緊急度（正規化）
            # HP1なら命がけボーナスで逆転可能性アップ → 差が実質的に小さく感じる
            effective_gap = my_gap / hp1_risk_bonus
            gap_factor = min(effective_gap / 100.0, 1.0)  # 0.0～1.0
            
            # 1位：防衛的圧力（差が小さいと攻撃優先）
            if my_rank == 1:
                reversal_pressure = -0.5 * (1.0 - gap_factor)  # -0.5～0.0
            # 2-3位：逆転チャンス（差が小さいと攻撃優先）
            # HP1ならさらに攻撃優先（命がけで稼げる）
            elif my_rank <= 3:
                base_pressure = -0.8 * (1.0 - gap_factor)  # -0.8～0.0
                # HP1ならさらに攻撃優先度を上げる（HP購入しない方向）
                if current_hp == 1:
                    reversal_pressure = base_pressure * 1.3  # より攻撃的に
                else:
                    reversal_pressure = base_pressure
            # 4-5位：状況次第
            elif my_rank <= 5:
                reversal_pressure = -0.3 * (1.0 - gap_factor)  # -0.3～0.0
            # 6-7位：生存優先（諦めモード）
            else:
                reversal_pressure = 0.5 * gap_factor  # 0.0～0.5
        
        # 4. リソース圧力（スコア不足）
        resource_ratio = min(current_score / (hp_cost * 3), 1.0)  # 0.0～1.0
        resource_pressure = 1.0 - resource_ratio
        
        # === 個性による重み付け（SSD理論） ===
        avg_kappa = np.mean(list(self.ssd_state.kappa.values())) if self.ssd_state.kappa else 0.5
        
        # κ（カッパ）による個性反映
        # κ低い（保守的） → 生存圧力を重視
        # κ高い（攻撃的） → 逆転圧力を重視
        conservative_factor = 1.0 - avg_kappa  # 0.0～1.0（保守度）
        aggressive_factor = avg_kappa  # 0.0～1.0（攻撃度）
        
        # E（エネルギー）による活性度
        # E高い → 積極的にHP購入（行動意欲）
        energy_factor = min(self.ssd_state.E, 1.0)  # 0.0～1.0
        
        # 総合意味圧の計算（個性反映）
        total_meaning_pressure = (
            survival_pressure * (1.0 + conservative_factor * 0.5) +  # 保守的ほど生存重視
            env_risk_pressure * (1.0 + conservative_factor * 0.3) +  # 保守的ほどリスク回避
            reversal_pressure * aggressive_factor +  # 攻撃的ほど逆転重視
            resource_pressure * 0.5 -  # リソース不足は全員共通
            energy_factor * 0.2  # エネルギー高いほど行動的
        )
        
        # κを閾値として判断（SSD理論の核心）
        # 意味圧 > κ → 行動（HP購入）
        # 意味圧 < κ → 非行動（見送り）
        
        if total_meaning_pressure > avg_kappa * 2.5:
            # 非常に高圧力 → 最大購入
            purchase_count = max_purchasable
        elif total_meaning_pressure > avg_kappa * 1.5:
            # 高圧力 → 半分程度購入
            purchase_count = max(1, (max_purchasable + 1) // 2)
        elif total_meaning_pressure > avg_kappa * 0.8:
            # 通常圧力 → 1個購入
            purchase_count = 1
        else:
            # 圧力不足 → 見送り
            purchase_count = 0
        
        # 緊急時の安全装置（κに関係なく）
        # HP=1 かつ deadly環境 → 強制的に最低1購入
        if current_hp == 1 and next_environment == "deadly" and purchase_count == 0 and max_purchasable > 0:
            purchase_count = 1
        
        return purchase_count


class ChickenGame:
    """チキンゲームのメインクラス"""
    

