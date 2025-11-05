"""
Meaning Pressure Calculator

全圧力を統合して意味圧を計算
"""

from typing import Dict
from .hp_pressure import calculate_hp_pressure
from .reversal_pressure import (
    calculate_reversal_pressure,
    calculate_overall_reversal_pressure
)
from .elimination_pressure import calculate_elimination_line_pressure
from .multi_conflict_pressure import calculate_multi_conflict_pressure


class MeaningPressureCalculator:
    """意味圧計算クラス（Phase 2: 責任分離版）"""
    
    def __init__(self, config: Dict):
        self.config = config
    
    def calculate(
        self,
        # ラウンド情報
        round_num: int,
        total_rounds: int,
        is_final_round: bool,
        # プレイヤー状態
        hp: int,
        total_score: int,
        # セット内状態
        current_rank: int,
        score_gap_from_first: int,
        remaining_rounds: int,
        # トーナメント状態
        current_set: int,
        total_sets: int,
        overall_rank: int,
        overall_gap: int,
        # ゲーム状態
        alive_count: int,
        env_bonus_multiplier: float
    ) -> Dict:
        """
        意味圧を計算
        
        Returns:
            {
                'pressure': float,  # 総合意味圧
                'set_reversal_possible': bool,  # セット内逆転可能
                'overall_reversal_possible': bool  # 総合逆転可能
            }
        """
        config = self.config['ssd_theory']['meaning_pressure']
        game_rules = self.config['game_rules']
        tournament = self.config['tournament']
        
        # 基本圧力
        pressure = config['base_weight']
        
        # ラウンド進行による圧力
        round_progress = round_num / total_rounds
        pressure += config['round_progression_weight'] * round_progress
        
        # === 1. 逆転可能性圧力 ===
        max_points_per_round = game_rules['success_bonuses'].get(10, 20)
        rank_bonuses = tournament.get('set_rank_bonus', {})
        base_max_set_bonus = rank_bonuses.get(1, 30)
        max_set_bonus = int(base_max_set_bonus * env_bonus_multiplier)
        
        # セット内逆転圧力
        set_reversal_impossibility, set_reversal_possible = calculate_reversal_pressure(
            current_rank=current_rank,
            score_gap_from_first=score_gap_from_first,
            max_points_per_round=max_points_per_round,
            remaining_rounds=remaining_rounds,
            max_set_bonus=max_set_bonus,
            hp=hp
        )
        
        # 総合逆転圧力
        env_shifts = tournament.get('environment_shifts', {})
        environments = env_shifts.get('environments', {})
        
        overall_reversal_impossibility, overall_reversal_possible = calculate_overall_reversal_pressure(
            overall_rank=overall_rank,
            overall_gap=overall_gap,
            current_set=current_set,
            total_sets=total_sets,
            max_points_per_round=max_points_per_round,
            total_rounds=total_rounds,
            remaining_rounds_this_set=remaining_rounds,
            base_max_set_bonus=base_max_set_bonus,
            env_bonus_multiplier=env_bonus_multiplier,
            environments=environments,
            env_enabled=env_shifts.get('enabled', False)
        )
        
        # 使用する逆転不可能性（より厳しい方を採用）
        if total_sets > 1 and overall_rank <= 2:
            # 総合上位なら、セット内劣勢でも希望がある
            reversal_impossibility = set_reversal_impossibility * 0.5
        else:
            reversal_impossibility = max(
                set_reversal_impossibility,
                overall_reversal_impossibility
            )
        
        # === 2. 排除ライン圧力 ===
        elimination_pressure = calculate_elimination_line_pressure(
            overall_rank=overall_rank,
            overall_gap=overall_gap,
            current_set=current_set,
            total_sets=total_sets,
            max_points_per_round=max_points_per_round,
            total_rounds=total_rounds,
            remaining_rounds_this_set=remaining_rounds,
            base_max_set_bonus=base_max_set_bonus,
            env_bonus_multiplier=env_bonus_multiplier,
            environments=environments,
            env_enabled=env_shifts.get('enabled', False),
            debug=self.config.get('debug', False),
            player_name=""  # 呼び出し側で設定
        )
        
        pressure += elimination_pressure
        
        # === 3. 多重葛藤圧力 ===
        max_hp = game_rules['max_hp']
        multi_conflict_pressure = calculate_multi_conflict_pressure(
            hp=hp,
            max_hp=max_hp,
            current_rank=current_rank,
            score_gap_from_first=score_gap_from_first,
            alive_count=alive_count,
            total_score=total_score,
            reversal_impossibility=reversal_impossibility
        )
        
        pressure += multi_conflict_pressure
        
        # === 4. 順位とスコア差による追加圧力 ===
        if current_rank > 1:
            rank_pressure = config['score_gap_weight'] * (current_rank - 1) * 0.5
            gap_pressure = min(abs(score_gap_from_first) / 20.0, 5.0)
            pressure += rank_pressure + gap_pressure
        
        # === 5. 最終ラウンド補正 ===
        if is_final_round:
            final_config = tournament['final_round']
            
            # 最終セット最終ラウンドの特別判断
            if current_set == total_sets:
                if current_rank == 1:
                    # 1位: 守りに徹する
                    pressure *= 0.7
                elif current_rank <= 3:
                    # 2-3位: 逆転狙い
                    pressure *= final_config['finality_weight']
                else:
                    # 4位以下: 背水の陣
                    pressure *= final_config['desperation_bonus']
            else:
                # 通常の最終ラウンド
                pressure *= final_config['finality_weight']
        
        return {
            'pressure': pressure,
            'set_reversal_possible': set_reversal_possible,
            'overall_reversal_possible': overall_reversal_possible
        }
