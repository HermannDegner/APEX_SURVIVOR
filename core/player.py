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
    
    def _calculate_meaning_pressure(self, round_num: int, total_rounds: int,
                                   is_final_round: bool, current_rank: int,
                                   score_gap_from_first: int, alive_count: int = 7,
                                   remaining_rounds: int = 0, current_set: int = 1,
                                   total_sets: int = 1, overall_rank: int = 1,
                                   overall_gap: int = 0, env_bonus_multiplier: float = 1.0) -> float:
        """意味圧を計算"""
        config = self.config['ssd_theory']['meaning_pressure']
        
        # 基本圧力
        pressure = config['base_weight']
        
        # ラウンド進行による圧力増加
        round_progress = round_num / total_rounds
        pressure += config['round_progression_weight'] * round_progress
        
        # ========================================================
        # 逆転可能性の計算（拡張版）
        # ========================================================
        # セット内逆転可能性
        max_points_per_round = self.config['game_rules']['success_bonuses'].get(10, 20)
        rank_bonuses = self.config['tournament'].get('set_rank_bonus', {})
        base_max_set_bonus = rank_bonuses.get(1, 30)
        
        # 環境補正されたボーナス（引数で受け取る）
        max_set_bonus = int(base_max_set_bonus * env_bonus_multiplier)
        
        # HP1の場合、命がけボーナス(+30%)を考慮した最大獲得可能点数
        risk_bonus_multiplier = 1.3 if self.state.hp == 1 else 1.0
        
        # セット内で残りラウンドで理論上取れる最大点数（命がけボーナス込み）
        max_possible_gain_in_set = int(max_points_per_round * remaining_rounds * risk_bonus_multiplier)
        
        # セット内逆転可能性の判定
        set_reversal_impossibility = 0.0
        if current_rank > 1 and score_gap_from_first > 0:
            if score_gap_from_first > max_possible_gain_in_set + max_set_bonus:
                set_reversal_impossibility = 2.0  # 理論上逆転不可能
            elif score_gap_from_first > max_possible_gain_in_set:
                set_reversal_impossibility = 1.5  # ボーナス頼み
            elif score_gap_from_first > max_possible_gain_in_set * 0.5:
                set_reversal_impossibility = 1.0  # 全力必要
            else:
                set_reversal_impossibility = 0.5  # 逆転可能
        
        # 総合逆転可能性（残りセットがある場合）
        overall_reversal_impossibility = 0.0
        if total_sets > 1 and overall_rank > 1 and overall_gap > 0:
            remaining_sets = total_sets - current_set
            
            # 残りセットの環境を考慮した最大獲得可能ボーナス
            # 将来の環境は不明なので、残りセットの平均的なボーナスを推定
            env_shifts = self.config['tournament'].get('environment_shifts', {})
            if env_shifts.get('enabled', False):
                environments = env_shifts.get('environments', {})
                
                # 残りセットの環境ボーナス倍率を計算
                future_bonus_multipliers = []
                for future_set in range(current_set + 1, total_sets + 1):
                    env_type = environments.get(future_set, 'normal')
                    if env_type == "safe":
                        future_bonus_multipliers.append(0.75)
                    elif env_type == "normal":
                        future_bonus_multipliers.append(0.90)
                    elif env_type == "mild":
                        future_bonus_multipliers.append(1.10)
                    elif env_type == "moderate":
                        future_bonus_multipliers.append(1.30)
                    elif env_type == "volatile":
                        future_bonus_multipliers.append(1.20)
                    elif env_type == "deadly":
                        future_bonus_multipliers.append(1.8)
                    else:
                        future_bonus_multipliers.append(1.0)
                
                # 平均的なボーナス倍率
                avg_future_bonus_mult = sum(future_bonus_multipliers) / len(future_bonus_multipliers) if future_bonus_multipliers else 1.0
                future_max_set_bonus = int(base_max_set_bonus * avg_future_bonus_mult)
            else:
                # 環境変動なしの場合
                future_max_set_bonus = base_max_set_bonus
            
            # 残りセットで取れる最大点数
            # - 各セットで最高順位 + 全ラウンド最高選択肢成功
            max_per_set = (max_points_per_round * total_rounds) + future_max_set_bonus
            max_possible_gain_overall = max_per_set * remaining_sets
            
            # 現在セットでの残り獲得可能点数も加算（現在の環境ボーナスを使用）
            max_possible_gain_overall += max_possible_gain_in_set + max_set_bonus
            
            if overall_gap > max_possible_gain_overall:
                overall_reversal_impossibility = 2.0  # 総合逆転不可能
            elif overall_gap > max_possible_gain_overall * 0.8:
                overall_reversal_impossibility = 1.5  # 非常に厳しい
            elif overall_gap > max_possible_gain_overall * 0.5:
                overall_reversal_impossibility = 1.0  # 厳しい
            else:
                overall_reversal_impossibility = 0.5  # 総合逆転可能
        
        # 使用する逆転不可能性（より厳しい方を採用）
        # ただし、総合順位が良好ならセット内の絶望感は軽減
        if total_sets > 1 and overall_rank <= 2:
            # 総合上位なら、セット内劣勢でも希望がある
            reversal_impossibility = set_reversal_impossibility * 0.5
        else:
            # 通常は両方を考慮
            reversal_impossibility = max(set_reversal_impossibility, overall_reversal_impossibility)
        
        # 逆転可能性を状態に保存（脱落推測用）
        self.state.eliminated_reversal_possible = (set_reversal_impossibility < 1.5)
        self.state.eliminated_overall_reversal_possible = (overall_reversal_impossibility < 1.5)
        
        # ========================================================
        # 【重要】逆転不可能ライン接近による意味圧
        # ========================================================
        # 逆転不可能ライン = 死亡確定ライン
        # このラインに近づいている場合、リスクを取ってでも逆転を狙う必要がある
        elimination_line_pressure = 0.0
        
        if total_sets > 1 and overall_rank > 1 and overall_gap > 0:
            # 残りで最大限獲得した場合に、トップに届くかどうか
            remaining_sets = total_sets - current_set
            
            # 環境を考慮した平均的な最大獲得可能点数を推定
            # 環境変動がある場合は、将来の環境ボーナスを考慮
            env_shifts = self.config['tournament'].get('environment_shifts', {})
            if env_shifts.get('enabled', False):
                environments = env_shifts.get('environments', {})
                future_bonus_multipliers = []
                for future_set in range(current_set + 1, total_sets + 1):
                    env_type = environments.get(future_set, 'normal')
                    if env_type == "deadly":
                        future_bonus_multipliers.append(1.8)
                    elif env_type == "moderate":
                        future_bonus_multipliers.append(1.3)
                    elif env_type == "mild":
                        future_bonus_multipliers.append(1.1)
                    else:
                        future_bonus_multipliers.append(1.0)
                avg_multiplier = sum(future_bonus_multipliers) / len(future_bonus_multipliers) if future_bonus_multipliers else 1.0
            else:
                avg_multiplier = 1.0
            
            # 平均的な1セットあたりの最大獲得可能点数
            avg_max_per_set = (max_points_per_round * total_rounds) + int(base_max_set_bonus * avg_multiplier)
            
            # 残りセット全てで最大獲得 + 現在セットの残り最大獲得
            max_possible_gain_overall = avg_max_per_set * remaining_sets + max_possible_gain_in_set + max_set_bonus
            
            # 逆転不可能ラインまでの余裕
            margin_to_elimination = max_possible_gain_overall - overall_gap
            
            # 閾値を残りセット数に応じて調整
            # 残りが多いうちは余裕があるので、閾値を緩く設定
            critical_threshold = avg_max_per_set * 0.3   # 0.3セット分で非常に危険
            danger_threshold = avg_max_per_set * 0.7     # 0.7セット分で危険
            warning_threshold = avg_max_per_set * 1.2    # 1.2セット分で注意
            
            if margin_to_elimination <= 0:
                # すでに逆転不可能 = 死亡確定
                elimination_line_pressure = 5.0  # 絶望的な状況で最大圧力
            elif margin_to_elimination < critical_threshold:
                # 非常に危険: わずかなミスで逆転不可能
                elimination_line_pressure = 3.0  # 強い圧力
            elif margin_to_elimination < danger_threshold:
                # 危険: 余裕がなくなってきた
                elimination_line_pressure = 2.0  # 中程度の圧力
            elif margin_to_elimination < warning_threshold:
                # 注意: そろそろ攻めないと危ない
                elimination_line_pressure = 1.0  # 軽い圧力
            
            # デバッグ出力
            if self.config.get('debug', False) and elimination_line_pressure > 0:
                status = "逆転不可能" if margin_to_elimination <= 0 else f"余裕{margin_to_elimination:.0f}pts"
                print(f"[{self.state.name}] 逆転不可能ライン接近: {status}, 圧力+{elimination_line_pressure:.1f}")
        
        # ========================================================
        # 多重構造的葛藤: 3つの死が折り重なる
        # ========================================================
        # 1. クラッシュによる死 (即死) - HP減少による物理的死の恐怖
        # 2. 敗北による死 (ルール死) - 1位以外全員死亡という究極の圧力
        # 3. 賞金への執着 - 稼いだ金額を失うことへの恐怖
        # ========================================================
        
        max_hp = self.config['game_rules']['max_hp']
        hp_ratio = self.state.hp / max_hp
        
        # === 状況分析 ===
        is_winning = (current_rank <= 2)  # 1-2位
        is_losing = (current_rank >= 5)   # 5位以下
        
        # スコア差の確認（1位との差）
        if alive_count > 1:
            score_gap = score_gap_from_first  # 正の値 = 負けている（1位との差）
            large_gap = (score_gap > 20)  # 20pts以上の差
            very_large_gap = (score_gap > 50)  # 50pts以上の絶望的な差
        else:
            score_gap = 0
            large_gap = False
            very_large_gap = False
        
        # === 葛藤1: クラッシュによる即死の恐怖 ===
        # HP低い → クラッシュで即死のリスク
        crash_death_fear = (1.0 - hp_ratio) ** 2 * 2.0  # 2.5 → 2.0 (さらに恐怖を減少)
        
        # === 葛藤2: 敗北による死の恐怖 ===
        # 「1位以外全員死亡」という究極のプレッシャー
        # 順位が低い & スコア差がある → 敗北の恐怖
        # **逆転可能性も考慮**
        if is_losing or large_gap:
            # 劣勢: 敗北が見えている
            defeat_death_fear = 1.2  # 1.5 → 1.2 (さらに攻撃性を抑制)
            if very_large_gap:
                defeat_death_fear = 2.0  # 2.5 → 2.0
            
            # 逆転不可能性を加算
            # 理論上逆転不可能なら、さらに絶望的な圧力
            defeat_death_fear += reversal_impossibility
            
        elif is_winning and not large_gap:
            # 優勢: 敗北の恐怖は小さい
            defeat_death_fear = 0.3  # 0.4 → 0.3
        else:
            # 中位: 中程度の恐怖
            defeat_death_fear = 0.8  # 1.0 → 0.8
        
        # === 葛藤3: 賞金への執着 ===
        # 稼いだ金額が大きいほど失いたくない
        money_attachment = 0.0
        if self.state.total_score > 0:
            # 10pts (1億円) で +0.1、100pts (10億円) で +1.0
            money_attachment = (self.state.total_score / 100.0) ** 0.5 * 1.0  # 1.2 → 1.0
        
        # === 多重葛藤の折り重なり ===
        # 3つの恐怖がどう相互作用するか
        
        if is_winning and not large_gap:
            # 【優勢パターン】1-2位 & 差が小さい
            # - クラッシュ死の恐怖: 高 (「勝てる位置なのに死ぬのは愚か」)
            # - 敗北死の恐怖: 低 (「このまま逃げ切れる」)
            # - 賞金執着: 高 (「稼いだ金を守りたい」)
            # → 守りの意識: クラッシュを恐れて慎重に
            total_death_pressure = crash_death_fear * 1.5 + defeat_death_fear * 0.2 + money_attachment * 0.3
            total_death_pressure *= 0.7  # 全体的に低圧（守り）- 0.6→0.7でさらに緩和
            
        elif is_losing or very_large_gap:
            # 【劣勢パターン】5位以下 or 大差で負け
            # - クラッシュ死の恐怖: 中 (「どのみち負ける」)
            # - 敗北死の恐怖: 高 (「このままでは確実に死ぬ」)
            # - 賞金執着: 低 (「賞金より生存」)
            # → 攻めの意識: 敗北死を避けるためリスクを取る
            total_death_pressure = crash_death_fear * 0.4 + defeat_death_fear * 1.5 + money_attachment * 0.15
            total_death_pressure *= 1.1  # 全体的に高圧（攻め）- 1.3→1.1でさらに緩和
            
        elif large_gap and not is_losing:
            # 【中位だが差がある】3-4位 & 20pts差
            # - クラッシュ死の恐怖: 中
            # - 敗北死の恐怖: 中-高 (「追いつかなければ死ぬ」)
            # - 賞金執着: 中
            # → 攻守のジレンマ: やや攻め
            total_death_pressure = crash_death_fear * 0.8 + defeat_death_fear * 1.8 + money_attachment * 0.4
            total_death_pressure *= 1.2  # やや高圧
            
        else:
            # 【中位・競争中】3-4位 & 差が小さい
            # - 全ての恐怖がバランス
            # → 中立: 状況に応じて判断
            total_death_pressure = crash_death_fear * 1.0 + defeat_death_fear * 1.0 + money_attachment * 0.3
        
        pressure += total_death_pressure
        
        # === 終盤戦の多重葛藤強化 ===
        # 2-3名まで絞られると、全ての恐怖が増幅される
        if alive_count <= 3:
            # 終盤戦では3つの死がより鮮明に
            base_endgame_multiplier = (4 - alive_count) * 0.3  # 0.4 → 0.3
            
            if is_winning and hp_ratio > 0.4:
                # 【優勢・終盤】
                # - 「あと少しで勝てる」vs「1回のミスで終わる」
                # → 守りの圧力が極大化
                endgame_pressure = base_endgame_multiplier * 1.2  # 1.5 → 1.2
                # さらにクラッシュ死への恐怖を強化（守り意識）
                pressure *= 0.9  # 全体的な意味圧を下げる（慎重に）- 0.85→0.9
                
            elif is_losing or hp_ratio <= 0.4:
                # 【劣勢・終盤】
                # - 「もう負けしかない」vs「今攻めなければ終わり」
                # → 攻めの圧力が極大化（背水の陣）
                endgame_pressure = base_endgame_multiplier * 2.0  # 2.5 → 2.0
                # 敗北死への恐怖が支配的（攻め意識）
                pressure *= 1.15  # 全体的な意味圧を上げる（やるしかない）- 1.3→1.15
                
            else:
                # 【中位・終盤】
                # - 最も葛藤が激しい状態
                # - 守れば負ける、攻めれば死ぬ
                endgame_pressure = base_endgame_multiplier * 2.5
            
            pressure += endgame_pressure
        
        # === 負債による絶望的圧力 ===
        # マイナススコアは「敗北死」の恐怖をさらに強化
        if self.state.total_score < 0:
            # 負債がある = 既に負けている状態
            # -50pts (-5億円) で +2.0の追加圧力
            debt_despair = abs(self.state.total_score) / 50.0 * 2.0
            pressure += debt_despair
            # 「失うものがない」状態 → より攻撃的に
        
        # === 逆転不可能ライン接近による圧力 ===
        # 逆転不可能ライン = 死亡確定ライン
        # このラインに近づくと、リスクを取ってでも逆転を狙う必要がある
        pressure += elimination_line_pressure
        
        # === 順位とスコア差による敗北死の追加圧力 ===
        # （既に多重葛藤で処理済みだが、細かい調整として追加）
        if current_rank > 1:
            # 順位が低いほど圧力増加
            rank_pressure = config['score_gap_weight'] * (current_rank - 1) * 0.5
            
            # 1位との点差による圧力（点差が大きいほど絶望的）
            # 10点差で+0.5、50点差で+2.5の圧力（多重葛藤と重複しないよう減少）
            gap_pressure = min(abs(score_gap_from_first) / 20.0, 5.0)
            
            pressure += rank_pressure + gap_pressure
        
        # 最終ラウンドの特別圧力
        if is_final_round:
            final_config = self.config['tournament']['final_round']
            
            # 【最終セット最終ラウンドの特別判断】
            is_final_set = (current_set == total_sets)
            
            if is_final_set:
                # 総合順位での逆転可能性を再計算
                # 残りは「このラウンドだけ」なので、獲得可能な最大点数は限られる
                max_points_this_round = 10 * env_bonus_multiplier  # 最大選択肢 × 環境ボーナス
                
                # デバッグ出力（最終セット最終ラウンドのみ）
                if self.config.get('debug', False):
                    print(f"\n[DEBUG] {self.state.name} 最終判断:")
                    print(f"  総合順位: {overall_rank}位, 総合1位との差: {overall_gap}pts")
                    print(f"  セット内順位: {current_rank}位, セット内1位との差: {score_gap_from_first}pts")
                    print(f"  現在の総合スコア: {self.state.total_score}pts")
                    print(f"  最大獲得可能: {max_points_this_round}pts")
                
                # セット順位ボーナスも考慮
                rank_bonuses = self.config['tournament'].get('set_rank_bonus', {})
                current_set_bonus = int(rank_bonuses.get(current_rank, 0) * env_bonus_multiplier)
                
                # 現在のセット内順位を守った場合の総合スコア予測
                # total_scoreには既に現在のセットの途中経過が含まれているので、
                # セットスコアを二重計上しないよう、ボーナスのみ追加
                predicted_total_if_safe = (
                    self.state.total_score +  # 現在の総合スコア（セット途中経過含む）
                    current_set_bonus          # セット順位ボーナス
                )
                
                # 総合1位のプレイヤーの推定スコア
                # （overall_gapは自分と総合1位の差、負数なら自分が総合1位）
                estimated_overall_first_score = self.state.total_score + overall_gap
                
                # 総合逆転に必要な追加点数
                if overall_gap > 0:  # 自分が総合1位でない
                    points_needed_for_overall_win = overall_gap + 1
                    
                    # このラウンドで逆転可能か？
                    # セット順位ボーナスも含めた最大獲得可能ポイント
                    best_round_score = max_points_this_round  # ラウンドでの最大点数
                    best_set_bonus = int(rank_bonuses.get(1, 0) * env_bonus_multiplier)  # 1位ボーナス
                    max_possible_gain = best_round_score + best_set_bonus
                    
                    # 【重要】総合1位も頑張った場合の最大スコアを推定
                    # 総合1位がこのラウンドで最大獲得+セット1位を取った場合
                    estimated_max_first_score = estimated_overall_first_score + max_possible_gain
                    
                    if self.config.get('debug', False):
                        print(f"  逆転必要点数: {points_needed_for_overall_win}pts")
                        print(f"  最大獲得(ラウンド): {best_round_score}pts")
                        print(f"  最大獲得(ボーナス): {best_set_bonus}pts")
                        print(f"  合計獲得可能: {max_possible_gain}pts")
                        print(f"  現在総合: {self.state.total_score}pts, 総合1位: {estimated_overall_first_score}pts")
                        print(f"  総合1位の最大可能: {estimated_max_first_score}pts")
                        print(f"  守った場合の最終総合: 約{predicted_total_if_safe}pts")
                    
                    # 【重要】守るだけで総合1位確定の判定
                    # 総合1位がどんなに頑張っても届かない場合のみ超安全策
                    if predicted_total_if_safe > estimated_max_first_score:
                        # 【守るだけで総合1位確定】
                        if current_rank == 1:
                            pressure *= 0.02  # 極度に安全策（守るだけで優勝）
                            if self.config.get('debug', False):
                                print(f"  判定: 守るだけで総合1位確定 → 超超安全策")
                        else:
                            pressure *= 0.1  # セット内順位も守る
                            if self.config.get('debug', False):
                                print(f"  判定: 守れば総合1位 → 超安全策")
                    elif points_needed_for_overall_win > max_possible_gain:
                        # 【総合逆転不可能】セット内順位を守る方が重要
                        if current_rank == 1:
                            # セット内1位 → 守りに徹する
                            # 最終ラウンドなら超安全策
                            if is_final_round:
                                pressure *= 0.01  # 超安全策（守るだけで良い）
                                if self.config.get('debug', False):
                                    print(f"  判定: 総合逆転不可能・セット1位・最終ラウンド → 超守り (pressure={pressure:.4f})")
                            else:
                                pressure *= 0.1  # 圧力を大幅に減少（安全策）
                                if self.config.get('debug', False):
                                    print(f"  判定: 総合逆転不可能・セット1位 → 守り (pressure={pressure:.4f})")
                        else:
                            # セット内2位以下 → セット順位を上げる努力は継続
                            # ただし、総合では意味がないので過度なリスクは避ける
                            pressure *= 0.7
                            if self.config.get('debug', False):
                                print(f"  判定: 総合逆転不可能 → セット順位狙い")
                    else:
                        # 【総合逆転可能】だが、どの程度のリスクが必要か？
                        
                        # 現在のセット順位を守った場合の獲得ポイント
                        current_position_bonus = int(rank_bonuses.get(current_rank, 0) * env_bonus_multiplier)
                        
                        # セット順位を守るだけで総合逆転できるか？
                        # セット内1位の場合：守るだけで1位ボーナスが確実
                        # score_gap_from_firstは「1位との差」なので、自分が1位なら0
                        # 実際には、2位との差が重要だが、ここでは取得できない
                        # → セット内1位なら保守的に見積もって、ボーナスほぼ確定と判断
                        if current_rank == 1:
                            # セット内1位 → 守れば確実にボーナス獲得
                            # ラウンドでのマイナスを考慮（選択1-2なら-2pts程度）
                            expected_safe_gain = current_position_bonus - 2  # ボーナス - 微減
                        else:
                            # セット内2位以下 → 順位が変動する可能性
                            safe_round_score = 3 * env_bonus_multiplier
                            expected_safe_gain = safe_round_score + current_position_bonus

                        if self.config.get('debug', False):
                            print(f"  安全策での獲得: {expected_safe_gain}pts (セット{current_rank}位ボーナス{current_position_bonus})")
                        
                        if expected_safe_gain >= points_needed_for_overall_win:
                            # 【安全策で逆転可能】セット内順位を守れば総合1位
                            if current_rank == 1:
                                # セット内1位 → 守るだけで総合優勝
                                pressure *= 0.05  # 極度に安全策
                                if self.config.get('debug', False):
                                    print(f"  判定: セット1位キープで総合優勝確定 → 超安全策")
                            else:
                                # セット内2位以下でも、守れば逆転
                                pressure *= 0.3
                                if self.config.get('debug', False):
                                    print(f"  判定: 現順位キープで総合逆転 → 安全策")
                        else:
                            # 【リスク必要】積極的に攻めないと逆転できない
                            pressure *= final_config['finality_weight']
                            if current_rank > 1:
                                desperation = final_config['desperation_bonus'] * (current_rank - 1)
                                gap_desperation = score_gap_from_first / 20.0
                                pressure += desperation + gap_desperation
                            if self.config.get('debug', False):
                                print(f"  判定: リスクを取らないと逆転不可 → 攻撃")
                else:
                    # 【総合1位キープ】
                    # 2位以下が逆転できるかチェック
                    # overall_gap < 0 なので、abs(overall_gap)が自分の2位へのリード
                    lead_over_second = abs(overall_gap) if overall_gap < 0 else 0
                    
                    # 2位の最大獲得可能ポイント
                    best_round_score = max_points_this_round
                    best_set_bonus = int(rank_bonuses.get(1, 0) * env_bonus_multiplier)
                    max_possible_gain = best_round_score + best_set_bonus
                    
                    # 2位が最大限頑張っても追いつけない = 総合1位確定
                    is_guaranteed_win = (lead_over_second > max_possible_gain)
                    
                    # HP状態を確認（残りラウンドとの関係で絶対死なないか）
                    # 残りラウンド数を正確に計算（現在のラウンドを含む）
                    # 現在のラウンドでもクラッシュする可能性があるため、
                    # 現在のセット内の残りラウンド + 残りセット × 全ラウンド数
                    crash_hp_loss = self.config['game_rules']['crash_hp_loss']
                    # このラウンドを含めた残りラウンド数
                    # ROUND 1なら5ラウンド(1,2,3,4,5), ROUND 5なら1ラウンド(5)
                    current_set_remaining = total_rounds - round_num + 1
                    remaining_sets_count = total_sets - current_set
                    total_remaining_rounds = current_set_remaining + (remaining_sets_count * total_rounds)
                    
                    # 最大で total_remaining_rounds 回クラッシュする可能性
                    max_possible_crashes = total_remaining_rounds
                    # 絶対死なないHP = クラッシュ回数 × HP損失 + 1
                    safe_hp_threshold = max_possible_crashes * crash_hp_loss + 1
                    has_hp_buffer = (self.state.hp >= safe_hp_threshold)
                    
                    if self.config.get('debug', False):
                        print(f"  2位へのリード: {lead_over_second}pts, 2位の最大可能: {max_possible_gain}pts")
                        print(f"  総合1位確定: {is_guaranteed_win}, 残りラウンド: {total_remaining_rounds}, 安全HP閾値: {safe_hp_threshold}")
                        print(f"  HP余裕: {has_hp_buffer} (HP={self.state.hp}, クラッシュしても死なない)")
                    
                    if is_guaranteed_win and has_hp_buffer:
                        # 【総合1位確定 + HP余裕】お金稼ぎモード
                        # クラッシュしても死なないし、優勝は確定
                        # → ポイント（お金）を稼ぐために攻撃的に
                        pressure *= 1.5  # 通常より攻撃的
                        if self.config.get('debug', False):
                            print(f"  判定: 総合1位確定・HP余裕 → お金稼ぎモード (pressure={pressure:.4f})")
                    elif is_guaranteed_win:
                        # 【総合1位確定 だがHP少ない】安全策
                        if current_rank == 1:
                            pressure *= 0.05  # 極度に安全策
                        else:
                            pressure *= 0.3   # セット内順位を守る程度の圧力
                        if self.config.get('debug', False):
                            print(f"  判定: 総合1位確定・HP少ない → 安全策")
                    else:
                        # 【総合1位だが2位が追いつける】守りに徹する
                        if current_rank == 1:
                            pressure *= 0.05  # 極度に安全策
                        else:
                            pressure *= 0.3   # セット内順位を守る程度の圧力
                        if self.config.get('debug', False):
                            print(f"  判定: 総合1位維持 → 守り")
            else:
                # 最終セットではない → 通常の最終ラウンド処理
                pressure *= final_config['finality_weight']
                
                if current_rank > 1:
                    desperation = final_config['desperation_bonus'] * (current_rank - 1)
                    gap_desperation = score_gap_from_first / 20.0
                    pressure += desperation + gap_desperation
        
        return pressure
    
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
        meaning_pressure = self._calculate_meaning_pressure(
            round_num, total_rounds, is_final_round, current_rank, score_gap_from_first, 
            alive_count, remaining_rounds, current_set, total_sets, overall_rank, overall_gap,
            env_bonus_multiplier
        )
        
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
        self.state.T = self.ssd_state.T
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
    

