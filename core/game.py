"""
ChickenGame - チキンゲームのメインクラス

Phase 4で分離: メインファイルから抽出（1448行）
"""

import random
import yaml
import numpy as np
from typing import List, Tuple, Dict
from collections import Counter

from .player import ChickenPlayer
from display.colors import Colors
from display.formatters import format_money, format_score_with_money, get_risk_level
from display.game_display import GameDisplay


class ChickenGame:
    """チキンゲームのメインクラス"""
    
    def __init__(self, config_path: str):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.players: List[ChickenPlayer] = []
        self._initialize_players()
        
        self.current_set = 0
        self.current_round = 0
        
        # 環境変動システム
        self.base_crash_probs = self.config['game_rules']['crash_probabilities'].copy()
        self.base_success_bonuses = self.config['game_rules']['success_bonuses'].copy()
        self.current_environment = "normal"
        self.current_risk_multiplier = 1.0
        self.current_bonus_multiplier = 1.0
        
        # シード情報を保存
        self.seed_used = None
        
        # ========== 表示系モジュール初期化 (Phase 4) ==========
        self.display = GameDisplay(self.config)
        self.sets_history = []  # セット履歴（分析用）
    
    def _initialize_players(self):
        """プレイヤーを初期化"""
        for p_config in self.config['players']:
            player = ChickenPlayer(
                name=p_config['name'],
                personality=p_config['personality'],
                color=p_config['color'],
                kappa=p_config['ssd_params']['kappa'],
                E_threshold=p_config['ssd_params']['E_threshold'],
                T_base=p_config['ssd_params']['T_base'],
                personality_weights=p_config['personality_weights'],
                opponent_analysis=p_config.get('opponent_analysis', False),
                nash_equilibrium=p_config.get('nash_equilibrium', False),
                config=self.config,
                strategy=p_config.get('strategy', 'ssd'),
                rule_name=p_config.get('rule_name', None),
                band_aware=p_config.get('band_aware', False)
            )
            self.players.append(player)
    
    def _get_env_bonus_multiplier(self) -> float:
        """現在の環境に基づくボーナス倍率を取得"""
        if self.current_environment == "safe":
            return 0.75  # 安全環境は低ボーナス
        elif self.current_environment == "normal":
            return 0.90  # 通常環境は少し低ボーナス
        elif self.current_environment == "mild":
            return 1.10  # やや危険は少し高ボーナス
        elif self.current_environment == "moderate":
            return 1.30  # 中程度の危険は高ボーナス
        elif self.current_environment == "volatile":
            return 1.20  # 不安定は平均的に高ボーナス
        elif self.current_environment == "deadly":
            return 1.8  # 危険地帯は最高ボーナス (+80%)
        return 1.0
    
    def _ai_vote_environment(self, set_num: int, overall_ranks: list) -> str:
        """AIが戦略的に環境を選択（総合順位の逆転可能性を考慮）"""
        from collections import Counter
        
        votes = []
        env_config = self.config['tournament'].get('environment_shifts', {})
        modifiers = env_config.get('modifiers', {})
        
        # 利用可能な環境リスト
        available_envs = ['safe', 'normal', 'mild', 'moderate', 'deadly']
        
        print(f"\n{Colors.BOLD}{Colors.CYAN}━━━ 環境選択フェーズ (SET {set_num}) ━━━{Colors.RESET}")
        print(f"{Colors.YELLOW}各プレイヤーが戦略的に環境を選択します...{Colors.RESET}\n")
        
        for player in self.players:
            if player.state.hp <= 0:
                continue  # 脱落者は投票権なし
            
            # 現在の総合順位と点差を取得
            player_rank = None
            player_score = player.state.total_score + player.state.score
            for rank, (p, score) in enumerate(overall_ranks, 1):
                if p.state.name == player.state.name:
                    player_rank = rank
                    break
            
            if player_rank is None:
                continue
            
            # 1位との点差
            first_place_score = overall_ranks[0][1]
            gap_to_first = first_place_score - player_score
            
            # 残りセット数
            total_sets = self.config['tournament']['sets']
            remaining_sets = total_sets - set_num + 1
            
            # 戦略的判断
            choice = self._choose_environment_strategy(
                player, player_rank, gap_to_first, remaining_sets, 
                player.state.hp, player.state.personality, available_envs, modifiers
            )
            
            votes.append(choice)
            
            # 選択理由の表示
            reason = self._get_environment_choice_reason(
                player, player_rank, gap_to_first, choice, player.state.hp
            )
            print(f"{player.state.name}: {choice} を選択 - {reason}")
        
        # 多数決で決定
        vote_counts = Counter(votes)
        most_common = vote_counts.most_common()
        
        print(f"\n{Colors.BOLD}投票結果:{Colors.RESET}")
        for env, count in most_common:
            print(f"  {env}: {count}票")
        
        # 最多得票が複数ある場合はプレイヤー個性で解消（SSD理論）
        max_votes = most_common[0][1]
        top_choices = [env for env, count in most_common if count == max_votes]
        
        if len(top_choices) > 1:
            # 同票の選択肢についてSSD理論で重み付け
            result = self._resolve_tie_with_personality(top_choices, votes)
            print(f"\n{Colors.YELLOW}→ 同票解消（個性重視）: {result} が選ばれました{Colors.RESET}")
        else:
            result = top_choices[0]
            print(f"\n{Colors.GREEN}→ 多数決: {result} に決定{Colors.RESET}")
        
        return result
    
    def _resolve_tie_with_personality(self, tied_envs: list, all_votes: list) -> str:
        """同票時にプレイヤー個性を反映した解消（SSD理論）
        
        Args:
            tied_envs: 同票になっている環境のリスト
            all_votes: 全プレイヤーの投票結果
            
        Returns:
            選択された環境
        """
        # 環境のリスクレベル定義
        risk_levels = {
            'safe': 1,
            'normal': 2,
            'mild': 3,
            'moderate': 4,
            'deadly': 5
        }
        
        # 各同票環境に対して、投票したプレイヤーの「個性スコア」を集計
        env_personality_scores = {}
        
        for env in tied_envs:
            total_score = 0.0
            vote_count = 0
            
            # この環境に投票したプレイヤーを探す
            for i, vote in enumerate(all_votes):
                if vote == env and i < len(self.players):
                    player = self.players[i]
                    
                    if player.state.hp <= 0:
                        continue  # 脱落者はスキップ
                    
                    # === SSD理論による個性スコア計算 ===
                    
                    # 1. κ（整合性閾値）の影響
                    avg_kappa = np.mean(list(player.state.kappa.values())) if player.state.kappa else 0.5
                    
                    # 2. E（未処理圧力）の影響
                    energy = min(player.state.E, 1.0)
                    
                    # 3. 性格タイプによる重み
                    personality_weights = {
                        'cautious': 0.3,      # 慎重派は影響力低
                        'balanced': 0.5,      # バランス型は中間
                        'aggressive': 0.8,    # 攻撃的は影響力高
                        'conservative': 0.2,  # 保守的は影響力最低
                        'optimistic': 0.6,    # 楽観的は中程度
                        'strategic': 0.7,     # 戦略的は高め
                        'risk_taker': 0.9     # リスクテイカーは最高
                    }
                    personality_weight = personality_weights.get(player.state.personality, 0.5)
                    
                    # 4. HPによる重み（瀕死のプレイヤーは影響力低下）
                    hp_weight = player.state.hp / 5.0
                    
                    # 5. 環境リスクレベルとの整合性
                    env_risk = risk_levels.get(env, 3)
                    risk_coherence = abs(env_risk - 3) / 2.0  # 0.0(normal)～1.0(safe/deadly)
                    
                    # 個性による選好の強さ
                    # κ高い = 積極的 → リスク環境に強い選好
                    # κ低い = 保守的 → 安全環境に強い選好
                    if env_risk >= 4:  # moderate, deadly
                        preference_strength = avg_kappa * 1.5 + energy * 0.3
                    elif env_risk <= 2:  # safe, normal
                        preference_strength = (1.0 - avg_kappa) * 1.5 + (1.0 - energy) * 0.3
                    else:  # mild
                        preference_strength = 0.5 + abs(avg_kappa - 0.5) * 0.5
                    
                    # 総合個性スコア
                    personality_score = (
                        preference_strength * 2.0 +      # 選好の強さが主要因
                        personality_weight * 1.5 +       # 性格タイプ
                        energy * 0.8 +                   # エネルギーレベル
                        hp_weight * 0.5 +                # HP状況
                        risk_coherence * 0.3             # リスク整合性
                    )
                    
                    total_score += personality_score
                    vote_count += 1
            
            # 平均個性スコア（投票数で正規化）
            if vote_count > 0:
                env_personality_scores[env] = total_score / vote_count
            else:
                env_personality_scores[env] = 0.0
        
        # 最も高い個性スコアの環境を選択
        if env_personality_scores:
            chosen_env = max(env_personality_scores, key=env_personality_scores.get)
            
            # デバッグ情報（開発時のみ表示）
            if self.config.get('debug', False):
                print(f"\n{Colors.CYAN}[同票解消詳細]{Colors.RESET}")
                for env, score in env_personality_scores.items():
                    print(f"  {env}: 個性スコア {score:.3f}")
            
            return chosen_env
        else:
            # 万が一スコア計算できない場合は温度Tでソフトマックス
            T = 0.5
            risk_values = [risk_levels.get(env, 3) for env in tied_envs]
            exp_values = np.exp(np.array(risk_values) / T)
            probs = exp_values / np.sum(exp_values)
            return np.random.choice(tied_envs, p=probs)
    
    def _choose_environment_strategy(self, player, rank: int, gap: int, remaining: int, 
                                     hp: int, personality: str, 
                                     available_envs: list, modifiers: dict) -> str:
        """SSD理論に基づく環境選択戦略"""
        
        # === SSD理論による意味圧計算 ===
        
        # 1. 逆転必要性圧力（順位と点差）
        rank_pressure = (rank - 1) / 6.0  # 0.0(1位)～1.0(7位)
        gap_pressure = min(gap / 100.0, 1.0)  # 0.0～1.0
        reversal_need = rank_pressure * 0.7 + gap_pressure * 0.3  # 0.0～1.0
        
        # 2. 時間圧力（残りセット数）
        time_pressure = 1.0 - (remaining / 5.0)  # 0.0(5セット残)～1.0(最終)
        
        # 3. リスク許容度（HP状況）
        hp_safety = hp / 5.0  # 0.0～1.0（HP多い=リスク取れる）
        
        # 4. 最終セットボーナス圧力
        final_set_multiplier = 2.0 if remaining == 1 else 1.0
        
        # === 個性による重み付け（SSD理論） ===
        avg_kappa = np.mean(list(player.state.kappa.values())) if player.state.kappa else 0.5
        energy = min(player.state.E, 1.0)
        
        # κ（カッパ）による個性
        # κ低い（保守的） → 安全志向
        # κ高い（攻撃的） → リスク志向
        conservative_factor = 1.0 - avg_kappa  # 0.0～1.0
        aggressive_factor = avg_kappa  # 0.0～1.0
        
        # 総合リスク意欲の計算（個性反映）
        risk_appetite = (
            reversal_need * aggressive_factor * 1.2 +  # 攻撃的ほど逆転重視
            time_pressure * 0.8 * final_set_multiplier +  # 時間切迫で全員リスク
            hp_safety * aggressive_factor * 0.5 +  # HP余裕×攻撃性
            energy * 0.3 -  # エネルギー高いほど行動的
            conservative_factor * 0.4  # 保守的ほど安全志向
        )
        
        # 1位の特別処理（大差リードなら保守的に）
        if rank == 1 and gap >= 60:
            risk_appetite *= 0.3  # リスク意欲を大幅に減少
        
        # === リスク意欲に基づいて環境を選択 ===
        # SSD理論: 意味圧（risk_appetite）と閾値（κ）の比較
        
        if risk_appetite < avg_kappa * 0.4:
            # 非常に低リスク → safe
            return 'safe'
        elif risk_appetite < avg_kappa * 0.8:
            # 低リスク → normal
            return 'normal'
        elif risk_appetite < avg_kappa * 1.3:
            # 中リスク → mild
            return 'mild'
        elif risk_appetite < avg_kappa * 1.8:
            # 高リスク → moderate
            return 'moderate'
        else:
            # 超高リスク → deadly
            return 'deadly'
    
    def _get_environment_choice_reason(self, player, rank: int, gap: int, 
                                        choice: str, hp: int) -> str:
        """環境選択の理由を生成（SSD理論ベース）"""
        # 個性を反映
        avg_kappa = np.mean(list(player.state.kappa.values())) if player.state.kappa else 0.5
        
        # 基本状況の説明
        if rank == 1:
            if choice in ['safe', 'normal']:
                if avg_kappa < 0.4:
                    return f"大差でリード（+{gap}pts）、保守的に守る [κ={avg_kappa:.2f}]"
                else:
                    return f"トップ維持（+{gap}pts）、慎重に [κ={avg_kappa:.2f}]"
            else:
                return f"リード保持も攻める [κ={avg_kappa:.2f}, 攻撃的]"
        
        elif rank <= 3:
            if choice in ['deadly', 'moderate']:
                if avg_kappa > 0.6:
                    return f"逆転圏内（差{gap}pts）、攻めのチャンス [κ={avg_kappa:.2f}, 攻撃的]"
                else:
                    return f"逆転狙い（差{gap}pts）、やむを得ずリスク [κ={avg_kappa:.2f}]"
            else:
                return f"僅差（差{gap}pts）、慎重に様子見 [κ={avg_kappa:.2f}]"
        
        elif rank <= 5:
            if choice in ['deadly', 'moderate']:
                if avg_kappa > 0.6:
                    return f"大胆勝負（差{gap}pts）[κ={avg_kappa:.2f}, 攻撃的性格]"
                else:
                    return f"背水の陣（差{gap}pts）[κ={avg_kappa:.2f}, 仕方なく]"
            else:
                return f"まだ届く範囲（差{gap}pts）、慎重に [κ={avg_kappa:.2f}]"
        
        else:  # 6-7位
            if choice == 'deadly':
                if avg_kappa > 0.6:
                    return f"奇跡を信じて（差{gap}pts）[κ={avg_kappa:.2f}, 一か八か]"
                else:
                    return f"最後の賭け（差{gap}pts）[κ={avg_kappa:.2f}, 追い詰められた]"
            else:
                return f"諦めモード（差{gap}pts）[κ={avg_kappa:.2f}, 生存優先]"
    
    def _apply_environment_shift(self, set_num: int):
        """環境変動を適用"""
        env_config = self.config['tournament'].get('environment_shifts', {})
        if not env_config.get('enabled', False):
            return
        
        # AI投票が有効な場合
        if env_config.get('ai_voting', False):
            # 総合順位を計算（total_scoreとscoreの合計）
            overall_ranks = sorted(
                [(p, p.state.total_score + p.state.score) for p in self.players],
                key=lambda x: x[1],
                reverse=True
            )
            env_type = self._ai_vote_environment(set_num, overall_ranks)
        else:
            # セットごとの環境タイプを取得（従来の方式）
            set_environments = env_config.get('environments', {})
            env_type = set_environments.get(set_num, 'normal')
        
        if env_type == 'normal':
            # 通常環境（変更なし）
            self.current_environment = "normal"
            self.current_risk_multiplier = 1.0
            self.current_bonus_multiplier = 1.0
            self.config['game_rules']['crash_probabilities'] = self.base_crash_probs.copy()
            self.config['game_rules']['success_bonuses'] = self.base_success_bonuses.copy()
            return
        
        modifiers = env_config['modifiers'].get(env_type, {})
        self.current_environment = env_type
        
        # リスク倍率の取得
        risk_mult = modifiers.get('risk_multiplier', 1.0)
        bonus_mult = modifiers.get('bonus_multiplier', 1.0)
        
        # volatileの場合はラウンドごとにランダム
        if isinstance(risk_mult, list):
            self.current_risk_multiplier = random.uniform(risk_mult[0], risk_mult[1])
        else:
            self.current_risk_multiplier = risk_mult
        
        if isinstance(bonus_mult, list):
            self.current_bonus_multiplier = random.uniform(bonus_mult[0], bonus_mult[1])
        else:
            self.current_bonus_multiplier = bonus_mult
        
        # クラッシュ確率を調整
        new_crash_probs = {}
        for choice, base_prob in self.base_crash_probs.items():
            adjusted = base_prob * self.current_risk_multiplier
            # 確率は0.01-0.95の範囲に制限
            new_crash_probs[choice] = max(0.01, min(0.95, adjusted))
        self.config['game_rules']['crash_probabilities'] = new_crash_probs
        
        # ボーナスを調整
        new_bonuses = {}
        for choice, base_bonus in self.base_success_bonuses.items():
            new_bonuses[choice] = int(base_bonus * self.current_bonus_multiplier)
        self.config['game_rules']['success_bonuses'] = new_bonuses
    
    def _display_environment_status(self):
        """現在の環境状態を表示"""
        env_config = self.config['tournament']['environment_shifts']['modifiers'][self.current_environment]
        desc = env_config.get('description', self.current_environment)
        
        print(f"\n{Colors.BOLD}{Colors.YELLOW}🌍 環境変動: {desc}{Colors.RESET}")
        print(f"{Colors.YELLOW}   リスク倍率: {self.current_risk_multiplier:.2f}x{Colors.RESET}")
        print(f"{Colors.YELLOW}   報酬倍率: {self.current_bonus_multiplier:.2f}x{Colors.RESET}")
        
        # 主要な選択肢のリスクを表示
        crash_probs = self.config['game_rules']['crash_probabilities']
        print(f"{Colors.YELLOW}   主要リスク: ", end="")
        for choice in [3, 5, 8, 10]:
            prob = crash_probs[choice]
            level, color, _ = get_risk_level(choice, prob)
            print(f"{color}{choice}={int(prob*100)}%{Colors.RESET} ", end="")
        print()
    
    def _check_crash(self, choice: int) -> bool:
        """クラッシュ判定"""
        crash_probs = self.config['game_rules']['crash_probabilities']
        if choice not in crash_probs:
            return False
        return random.random() < crash_probs[choice]
    
    def _calculate_scores(self, choices: List[Tuple[ChickenPlayer, int, bool]]) -> Dict[str, int]:
        """スコアを計算（勝者総取り方式）"""
        scores = {}
        rules = self.config['game_rules']
        
        # クラッシュしていないプレイヤーのみ
        valid_choices = [(p, c) for p, c, crashed in choices if not crashed]
        
        if not valid_choices:
            # 全員クラッシュ
            return {p.state.name: 0 for p, _, _ in choices}
        
        # 最高値を見つける
        max_choice = max(c for _, c in valid_choices)
        winners = [p for p, c in valid_choices if c == max_choice]
        
        # 勝者が得るポイント = 他全員の選択値の合計
        total_points = sum(c for _, c in valid_choices)
        winner_points = total_points // len(winners)
        
        # 成功ボーナス
        success_bonuses = rules['success_bonuses']
        
        for player, choice, crashed in choices:
            if crashed:
                # クラッシュペナルティ
                penalty = int(choice * rules['crash_penalty_multiplier'])
                scores[player.state.name] = penalty
            elif player in winners:
                # 勝者
                bonus = success_bonuses.get(choice, 0)
                scores[player.state.name] = winner_points + bonus
            else:
                # 敗者（選択値を失う）
                scores[player.state.name] = -choice
        
        return scores
    
    def _display_round_header(self, set_num: int, round_num: int, total_rounds: int):
        """ラウンドヘッダー表示"""
        is_final = (round_num == total_rounds)
        header = f"\n{'='*60}\n"
        header += f"SET {set_num} - ROUND {round_num}/{total_rounds}"
        if is_final:
            header += f" {Colors.RED}{Colors.BOLD}【最終ラウンド】{Colors.RESET}"
        header += f"\n{'='*60}"
        print(header)
    
    def _display_current_standings(self, set_num: int = 1, total_sets: int = 1, 
                                   round_num: int = 1, total_rounds: int = 5):
        """現在の順位表示（トーナメント情報含む）"""
        sorted_players = sorted(self.players, key=lambda p: p.state.score, reverse=True)
        
        # トーナメントモードの場合、総合順位も計算
        is_tournament = total_sets > 1
        if is_tournament:
            all_sorted = sorted(self.players, key=lambda p: p.state.total_score, reverse=True)
            overall_ranks = {p.state.name: i+1 for i, p in enumerate(all_sorted)}
            overall_first_score = all_sorted[0].state.total_score
            
            # 残りの最大獲得可能ポイントを計算
            rank_bonuses = self.config['tournament'].get('set_rank_bonus', {})
            env_bonus_multiplier = self._get_env_bonus_multiplier()
            best_set_bonus = int(rank_bonuses.get(1, 0) * env_bonus_multiplier)
            max_points_per_round = self.config['game_rules']['max_choice']
            
            remaining_sets = total_sets - set_num + 1
            remaining_rounds_this_set = total_rounds - round_num + 1
            remaining_rounds_other_sets = (remaining_sets - 1) * total_rounds
            total_remaining_rounds = remaining_rounds_this_set + remaining_rounds_other_sets
            
            max_remaining_points = total_remaining_rounds * max_points_per_round + (remaining_sets * best_set_bonus)
        
        print(f"\n{Colors.BOLD}現在の順位:{Colors.RESET}")
        for i, player in enumerate(sorted_players, 1):
            color_name = Colors.get_color(player.state.color)
            # HP表示
            hp_indicator = "❤️ " * player.state.hp if player.state.is_alive else "💀"
            status = "" if player.state.is_alive else f" {Colors.RED}[脱落]{Colors.RESET}"
            
            # トーナメント情報
            tournament_info = ""
            if is_tournament:
                overall_rank = overall_ranks[player.state.name]
                overall_gap = overall_first_score - player.state.total_score
                
                # 勝利可能性判定
                # 注意: 選択肢1でも2%のクラッシュ確率があるため、理論上は誰でも生き残れる
                # ただし現実的な戦略判断のため、総合点での逆転可能性を表示
                can_win_by_score = (player.state.total_score + max_remaining_points) > overall_first_score
                
                # HP的な生存可能性（選択肢1-3を使えば生き残れる想定）
                crash_hp_loss = self.config['game_rules']['crash_hp_loss']
                min_crash_prob = self.config['game_rules']['crash_probabilities'][1]  # 選択肢1 = 2%
                # 全ラウンドで選択肢1を使った場合の期待クラッシュ回数
                expected_crashes = total_remaining_rounds * min_crash_prob
                can_survive = player.state.hp > (expected_crashes * crash_hp_loss)
                
                # 総合判定
                if not player.state.is_alive:
                    # 既に脱落
                    eliminated_mark = f" {Colors.RED}[脱落]{Colors.RESET}"
                elif not can_win_by_score:
                    # 総合点で逆転不可能（ただし選択肢1で生き残れば他が死ぬ可能性も）
                    if can_survive:
                        eliminated_mark = f" {Colors.GRAY}[逆転困難]{Colors.RESET}"
                    else:
                        eliminated_mark = f" {Colors.RED}[逆転困難・HP危険]{Colors.RESET}"
                elif overall_rank == 1 and not can_survive:
                    # トップだがHP危険（選択肢1でも期待値的に死ぬ）
                    eliminated_mark = f" {Colors.YELLOW}[トップ・HP危険]{Colors.RESET}"
                else:
                    # 逆転可能かつ生存可能
                    eliminated_mark = ""
                
                gap_display = f"-{overall_gap}pts" if overall_gap > 0 else "トップ"
                tournament_info = f" {Colors.GRAY}(総合{overall_rank}位: {player.state.total_score}pts {gap_display}){Colors.RESET}{eliminated_mark}"
            
            print(f"{i}位: {color_name}{player.state.name}{Colors.RESET} - {player.state.score}pts {hp_indicator}{status}{tournament_info}")
    
    def _display_choices(self, choices: List[Tuple[ChickenPlayer, int, bool]]):
        """選択結果を表示"""
        print(f"\n{Colors.BOLD}選択結果:{Colors.RESET}")
        sorted_choices = sorted(choices, key=lambda x: x[1], reverse=True)
        
        for player, choice, crashed in sorted_choices:
            color_name = Colors.get_color(player.state.color)
            crash_prob = self.config['game_rules']['crash_probabilities'][choice]
            
            # リスクレベル表示
            level, risk_color, symbol = get_risk_level(choice, crash_prob)
            risk_display = f"{risk_color}[{level} {int(crash_prob*100)}%]{Colors.RESET}"
            
            if crashed:
                status = f"{Colors.RED}💥 CRASH!{Colors.RESET}"
            else:
                status = f"{Colors.GREEN}✓{Colors.RESET}"
            
            print(f"{color_name}{player.state.name}{Colors.RESET}: {choice} {risk_display} {status}")
    
    def _display_scores(self, scores: Dict[str, int]):
        """スコア変動を表示"""
        print(f"\n{Colors.BOLD}スコア変動:{Colors.RESET}")
        for player in self.players:
            if player.state.name not in scores:
                continue  # 脱落者はスコア表示しない
            color_name = Colors.get_color(player.state.color)
            score_change = scores[player.state.name]
            sign = "+" if score_change > 0 else ""
            
            # HP1での成功にボーナス（クラッシュしたら死ぬ状況での成功）
            bonus_text = ""
            if player.state.hp == 1 and score_change > 0:
                # 命がけボーナス: 獲得点数の30%を追加
                risk_bonus = int(abs(score_change) * 0.3)
                if risk_bonus > 0:
                    score_change += risk_bonus
                    player.state.score += risk_bonus
                    bonus_text = f" {Colors.RED}[命がけ+{risk_bonus}pts]{Colors.RESET}"
            
            print(f"{color_name}{player.state.name}{Colors.RESET}: {sign}{score_change}pts (合計: {player.state.score}pts){bonus_text}")
    
    def play_round(self, set_num: int, round_num: int, total_rounds: int):
        """1ラウンドをプレイ"""
        # トーナメント情報
        total_sets = self.config['tournament']['sets']
        
        self._display_round_header(set_num, round_num, total_rounds)
        self._display_current_standings(set_num, total_sets, round_num, total_rounds)
        
        # 生存プレイヤーのみ参加
        alive_players = [p for p in self.players if p.state.is_alive]
        
        if len(alive_players) <= 1:
            print(f"\n{Colors.RED}ゲーム終了: 生存者が1名以下です{Colors.RESET}")
            return
        
        # 現在の順位を計算（生存者のみ）
        sorted_players = sorted(alive_players, key=lambda p: p.state.score, reverse=True)
        ranks = {p.state.name: i+1 for i, p in enumerate(sorted_players)}
        
        # 総合順位を計算（全プレイヤー）
        all_sorted = sorted(self.players, key=lambda p: p.state.total_score, reverse=True)
        overall_ranks = {p.state.name: i+1 for i, p in enumerate(all_sorted)}
        overall_first_score = all_sorted[0].state.total_score
        
        # 1位のスコアを取得（セット内）
        first_place_score = sorted_players[0].state.score
        
        is_final_round = (round_num == total_rounds)
        
        print(f"\n{Colors.BOLD}選択中...{Colors.RESET}\n")
        
        # 全プレイヤーが選択（生存者のみ）
        choices = []
        alive_count = len(alive_players)
        player_contexts = {}  # 脱落時の文脈情報を保存
        
        for player in alive_players:
            current_rank = ranks[player.state.name]
            overall_rank = overall_ranks[player.state.name]
            # 1位との点差を計算（自分が負けている場合は正の値）
            score_gap = first_place_score - player.state.score
            
            # 総合順位の点差を計算
            # 自分が総合1位の場合は、2位との差を負数で渡す
            if overall_rank == 1:
                # 2位のスコアを取得
                overall_second_score = all_sorted[1].state.total_score if len(all_sorted) > 1 else 0
                overall_gap = overall_second_score - player.state.total_score  # 負数になる
            else:
                # 1位との差（正数）
                overall_gap = overall_first_score - player.state.total_score
            
            # 文脈情報を保存
            player_contexts[player.state.name] = {
                'rank': current_rank,
                'score_gap': score_gap,
                'hp_before': player.state.hp,
                'score': player.state.score,
                'overall_rank': overall_rank,
                'overall_gap': overall_gap
            }
            
            # 環境ボーナス倍率を取得
            env_bonus_multiplier = self._get_env_bonus_multiplier()
            
            choice = player.make_choice(round_num, total_rounds, is_final_round, 
                                       current_rank, score_gap, alive_count,
                                       set_num, total_sets, overall_rank, overall_gap,
                                       env_bonus_multiplier)
            crashed = self._check_crash(choice)
            choices.append((player, choice, crashed))
        
        # 結果表示
        self._display_choices(choices)
        
        # スコア計算
        scores = self._calculate_scores(choices)
        self._display_scores(scores)
        
        # 各プレイヤーの結果処理
        crash_hp_loss = self.config['game_rules']['crash_hp_loss']
        for player, choice, crashed in choices:
            score_change = scores[player.state.name]
            success = (score_change > 0)
            player.process_result(crashed, score_change, success)
            
            # クラッシュでHP減少
            if crashed:
                player.state.hp -= crash_hp_loss
                if player.state.hp <= 0:
                    player.state.is_alive = False
                    # 脱落情報を詳細に記録
                    context = player_contexts[player.state.name]
                    player.state.eliminated_set = set_num
                    player.state.eliminated_round = round_num
                    player.state.eliminated_choice = choice
                    player.state.eliminated_hp = context['hp_before']
                    player.state.eliminated_rank = context['rank']
                    player.state.eliminated_score = context['score']
                    player.state.eliminated_gap = context['score_gap']
                    player.state.eliminated_overall_rank = context['overall_rank']
                    player.state.eliminated_overall_gap = context['overall_gap']
                    crash_prob = self.config['game_rules']['crash_probabilities'].get(choice, 0.0)
                    level, _, _ = get_risk_level(choice, crash_prob)
                    player.state.elimination_reason = f"choice {choice} [{level} {crash_prob*100:.0f}%] でクラッシュ"
                    color_name = Colors.get_color(player.state.color)
                    print(f"{color_name}{player.state.name}{Colors.RESET}: 💀 {Colors.RED}HP 0 - 脱落！{Colors.RESET}")
        
        # 他プレイヤーの選択を記録
        for player in alive_players:
            for other_player, other_choice, _ in choices:
                if other_player.state.name != player.state.name:
                    player.state.opponent_choices[other_player.state.name].append(other_choice)
    
    def play_set(self, set_num: int):
        """1セット（5ラウンド）をプレイ"""
        total_rounds = self.config['tournament']['rounds']
        
        # 環境はplay_tournamentまたは前セット終了時に既に設定済み
        
        print(f"\n{'#'*60}")
        print(f"#{' '*20}SET {set_num} START{' '*20}#")
        print(f"{'#'*60}")
        
        # 環境状態を表示
        self._display_environment_status()
        
        for round_num in range(1, total_rounds + 1):
            self.play_round(set_num, round_num, total_rounds)
            for player in self.players:
                player.reset_round_state()
        
        # セット終了
        self._display_set_results(set_num)
        
        # 次セットへの準備
        if set_num < self.config['tournament']['sets']:
            # スコアをリセット（トータルスコアに加算）
            for player in self.players:
                player.reset_set_score()
            
            # 次セットの環境を先に決定（投票または固定）
            next_set_num = set_num + 1
            self._apply_environment_shift(next_set_num)
            
            # 環境が決まった後にHP購入判断
            self._hp_purchase_phase(next_set_num)
    
    def _display_set_results(self, set_num: int):
        """セット結果を表示"""
        print(f"\n{'='*60}")
        print(f"{Colors.BOLD}SET {set_num} 結果{Colors.RESET}")
        print(f"{'='*60}")
        
        # 生存者と脱落者を分ける
        alive_players = [p for p in self.players if p.state.is_alive]
        dead_players = [p for p in self.players if not p.state.is_alive]
        
        sorted_alive = sorted(alive_players, key=lambda p: p.state.score, reverse=True)
        sorted_dead = sorted(dead_players, key=lambda p: p.state.score, reverse=True)
        
        # セット順位ボーナスの取得
        rank_bonuses = self.config['tournament'].get('set_rank_bonus', {})
        
        # 環境リスクによるボーナス倍率
        env_bonus_multiplier = self._get_env_bonus_multiplier()
        bonus_modifier_text = ""
        
        if self.current_environment == "safe":
            bonus_modifier_text = f" {Colors.CYAN}(安全環境 -25%){Colors.RESET}"
        elif self.current_environment == "normal":
            bonus_modifier_text = f" {Colors.CYAN}(通常環境 -10%){Colors.RESET}"
        elif self.current_environment == "mild":
            bonus_modifier_text = f" {Colors.YELLOW}(やや危険 +10%){Colors.RESET}"
        elif self.current_environment == "moderate":
            bonus_modifier_text = f" {Colors.YELLOW}(危険環境 +30%){Colors.RESET}"
        elif self.current_environment == "volatile":
            bonus_modifier_text = f" {Colors.YELLOW}(不安定環境 +20%){Colors.RESET}"
        elif self.current_environment == "deadly":
            bonus_modifier_text = f" {Colors.RED}(危険地帯 +55%){Colors.RESET}"
        
        if bonus_modifier_text:
            print(f"\n{Colors.BOLD}セット順位ボーナス{bonus_modifier_text}{Colors.RESET}")
        
        # 生存者の表示と順位記録
        for i, player in enumerate(sorted_alive, 1):
            color_name = Colors.get_color(player.state.color)
            hp_indicator = "❤️ " * player.state.hp
            
            # セット順位を記録（逆転性追跡用）
            player.state.set_ranks.append(i)
            
            # ボーナスポイントの付与（環境補正）
            base_bonus = rank_bonuses.get(i, 0)
            bonus = int(base_bonus * env_bonus_multiplier)
            
            bonus_text = ""
            if bonus > 0:
                player.state.total_score += bonus
                    
                if env_bonus_multiplier != 1.0:
                    bonus_text = f" {Colors.YELLOW}[+{bonus}pts ボーナス (基本{base_bonus}pts)]{Colors.RESET}"
                else:
                    bonus_text = f" {Colors.YELLOW}[+{bonus}pts ボーナス]{Colors.RESET}"
            
            if i == 1 and len(sorted_alive) > 0:
                player._speak_victory()
                # HP1での勝利は特別演出
                if player.state.hp == 1:
                    print(f"🏆 {Colors.BOLD}1位: {color_name}{player.state.name}{Colors.RESET} - {player.state.score}pts {hp_indicator} {Colors.RED}[命がけの勝利]{Colors.RESET}{bonus_text}")
                else:
                    print(f"🏆 {Colors.BOLD}1位: {color_name}{player.state.name}{Colors.RESET} - {player.state.score}pts {hp_indicator} {Colors.YELLOW}[勝利]{Colors.RESET}{bonus_text}")
            elif i == len(sorted_alive):
                player._speak_defeat()
                print(f"{i}位: {color_name}{player.state.name}{Colors.RESET} - {player.state.score}pts {hp_indicator} {Colors.RED}[敗北]{Colors.RESET}{bonus_text}")
            else:
                print(f"{i}位: {color_name}{player.state.name}{Colors.RESET} - {player.state.score}pts {hp_indicator} {Colors.GRAY}[敗北]{Colors.RESET}{bonus_text}")
        
        # 脱落者の表示と順位記録
        if len(sorted_dead) > 0:
            start_rank = len(sorted_alive) + 1
            for i, player in enumerate(sorted_dead, 1):
                color_name = Colors.get_color(player.state.color)
                hp_indicator = "💀"
                
                # セット順位を記録（逆転性追跡用）
                rank = start_rank + i - 1
                player.state.set_ranks.append(rank)
                
                # 脱落者にもボーナス（順位による、環境補正付き）
                base_bonus = rank_bonuses.get(rank, 0)
                bonus = int(base_bonus * env_bonus_multiplier)
                bonus_text = ""
                if bonus > 0:
                    player.state.total_score += bonus
                    if env_bonus_multiplier != 1.0:
                        bonus_text = f" {Colors.YELLOW}[+{bonus}pts ボーナス (基本{base_bonus}pts)]{Colors.RESET}"
                    else:
                        bonus_text = f" {Colors.YELLOW}[+{bonus}pts ボーナス]{Colors.RESET}"
                
                print(f"{rank}位: {color_name}{player.state.name}{Colors.RESET} - {player.state.score}pts {hp_indicator} {Colors.RED}[敗北]{Colors.RESET} {Colors.GRAY}[脱落]{Colors.RESET}{bonus_text}")
    
    def _hp_purchase_phase(self, next_set_num: int):
        """HP購入フェーズ（次セットの環境を考慮）"""
        hp_cost = self.config['game_rules']['hp_purchase_cost']
        max_hp = self.config['game_rules']['max_hp']
        
        # 現在の総合順位を更新（HP購入判断で使用）
        sorted_players = sorted(self.players, key=lambda p: p.state.total_score, reverse=True)
        top_score = sorted_players[0].state.total_score if sorted_players else 0
        
        for i, player in enumerate(sorted_players, 1):
            player.state.overall_rank = i
            player.state.overall_gap = top_score - player.state.total_score
        
        print(f"\n{'='*60}")
        print(f"{Colors.BOLD}{Colors.YELLOW}HP購入フェーズ{Colors.RESET} {Colors.GRAY}(次セット環境を考慮){Colors.RESET}")
        print(f"{'='*60}")
        print(f"{Colors.CYAN}HP回復: {hp_cost}pts で +1 HP (最大{max_hp}HP){Colors.RESET}")
        
        # 次セットの環境情報を表示
        env_risk_text = ""
        if self.current_environment == "deadly":
            env_risk_text = f" {Colors.RED}[次セット: 危険環境 - HPの価値↑]{Colors.RESET}"
        elif self.current_environment == "moderate":
            env_risk_text = f" {Colors.YELLOW}[次セット: 中程度 - HPは重要]{Colors.RESET}"
        elif self.current_environment == "safe":
            env_risk_text = f" {Colors.CYAN}[次セット: 安全環境 - HPの価値↓]{Colors.RESET}"
        else:
            env_risk_text = f" {Colors.GREEN}[次セット: {self.current_environment}]{Colors.RESET}"
        
        print(env_risk_text)
        print()
        
        for player in self.players:
            if not player.state.is_alive:
                continue
            
            color_name = Colors.get_color(player.state.color)
            
            # 現在の状態表示（総合スコア + 順位情報）
            rank_info = ""
            if player.state.overall_rank is not None:
                rank = player.state.overall_rank
                gap = player.state.overall_gap if player.state.overall_gap is not None else 0
                if rank == 1:
                    rank_info = f" {Colors.GREEN}[1位 +{gap}pts]{Colors.RESET}"
                elif rank <= 3:
                    rank_info = f" {Colors.YELLOW}[{rank}位 -{gap}pts]{Colors.RESET}"
                else:
                    rank_info = f" {Colors.RED}[{rank}位 -{gap}pts]{Colors.RESET}"
            
            print(f"{color_name}{player.state.name}{Colors.RESET}: HP={player.state.hp}, TotalScore={player.state.total_score}pts{rank_info}", end="")
            if player.is_ai:
                avg_kappa = np.mean(list(player.state.kappa.values())) if player.state.kappa else 0
                print(f" {Colors.GRAY}[κ_avg={avg_kappa:.2f}, E={player.state.E:.2f}]{Colors.RESET}")
            else:
                print()

            # 環境を考慮したHP購入判断
            hp_to_buy = player.decide_hp_purchase_with_environment(
                self.current_environment, 
                self.current_risk_multiplier
            )
            
            if hp_to_buy > 0:
                total_cost = hp_to_buy * hp_cost
                # 総合スコアから支払い
                player.state.total_score -= total_cost
                old_hp = player.state.hp
                player.state.hp = min(player.state.hp + hp_to_buy, max_hp)
                actual_gained = player.state.hp - old_hp
                
                # 購入理由の判定
                reason = ""
                if player.state.overall_rank is not None:
                    rank = player.state.overall_rank
                    gap = player.state.overall_gap if player.state.overall_gap is not None else 0
                    
                    if rank == 1 and gap < 30:
                        reason = f" {Colors.GRAY}[トップ維持]{Colors.RESET}"
                    elif rank <= 3 and gap < 40:
                        reason = f" {Colors.GRAY}[逆転狙い - 攻撃優先]{Colors.RESET}"
                    elif rank >= 6 and gap > 80:
                        reason = f" {Colors.GRAY}[生存優先]{Colors.RESET}"
                    elif old_hp <= 2:
                        reason = f" {Colors.RED}[瀕死回復]{Colors.RESET}"
                
                if actual_gained > 1:
                    print(f"  → {Colors.GREEN}HP+{actual_gained} 購入{Colors.RESET} (-{total_cost}pts) → {Colors.BOLD}{player.state.hp}HP{Colors.RESET}, {player.state.total_score}pts {Colors.CYAN}[複数購入]{Colors.RESET}{reason}")
                else:
                    print(f"  → {Colors.GREEN}HP+{actual_gained} 購入{Colors.RESET} (-{total_cost}pts) → {Colors.BOLD}{player.state.hp}HP{Colors.RESET}, {player.state.total_score}pts{reason}")
            else:
                # 購入見送りの理由
                reason = ""
                if player.state.overall_rank is not None:
                    rank = player.state.overall_rank
                    gap = player.state.overall_gap if player.state.overall_gap is not None else 0
                    
                    if rank == 1 and gap > 60:
                        reason = f" {Colors.GRAY}[安全圏]{Colors.RESET}"
                    elif rank <= 3 and gap < 50:
                        reason = f" {Colors.CYAN}[逆転チャンス - スコア温存]{Colors.RESET}"
                    elif player.state.total_score < hp_cost:
                        reason = f" {Colors.RED}[資金不足]{Colors.RESET}"
                    elif player.state.hp >= 4:
                        reason = f" {Colors.GREEN}[HP十分]{Colors.RESET}"
                
                print(f"  → {Colors.GRAY}購入見送り{Colors.RESET}{reason}")
        
        print()  # 空行
    
    def _display_reversal_statistics(self):
        """逆転性の統計を表示"""
        print(f"\n{Colors.BOLD}{Colors.CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}  【逆転性分析】順位変動の統計{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.RESET}\n")
        
        # 各プレイヤーの順位推移を取得
        for player in self.players:
            if len(player.state.set_ranks) == 0:
                continue
            
            color_name = Colors.get_color(player.state.color)
            ranks = player.state.set_ranks
            
            # 統計計算
            best_rank = min(ranks)
            worst_rank = max(ranks)
            avg_rank = sum(ranks) / len(ranks)
            rank_variance = sum((r - avg_rank) ** 2 for r in ranks) / len(ranks)
            rank_std = rank_variance ** 0.5
            
            # 順位変動の計算
            rank_changes = []
            for i in range(1, len(ranks)):
                rank_changes.append(ranks[i] - ranks[i-1])
            
            # 逆転回数（順位が上がった回数）
            comebacks = sum(1 for change in rank_changes if change < 0)
            # 転落回数（順位が下がった回数）
            falls = sum(1 for change in rank_changes if change > 0)
            # 最大の逆転（一気に何位上がったか）
            max_comeback = abs(min(rank_changes)) if rank_changes and min(rank_changes) < 0 else 0
            # 最大の転落
            max_fall = max(rank_changes) if rank_changes and max(rank_changes) > 0 else 0
            
            # 順位推移の表示
            rank_history = " → ".join(str(r) for r in ranks)
            
            # 変動タイプの判定
            if rank_std < 0.5:
                stability = f"{Colors.GREEN}安定型{Colors.RESET}"
            elif rank_std < 1.0:
                stability = f"{Colors.YELLOW}やや変動{Colors.RESET}"
            elif rank_std < 1.5:
                stability = f"{Colors.MAGENTA}変動型{Colors.RESET}"
            else:
                stability = f"{Colors.RED}激動型{Colors.RESET}"
            
            print(f"{Colors.BOLD}{color_name}{player.state.name}{Colors.RESET}")
            print(f"  順位推移: {rank_history}")
            print(f"  最高順位: {Colors.GREEN}{best_rank}位{Colors.RESET} | 最低順位: {Colors.RED}{worst_rank}位{Colors.RESET} | 平均: {avg_rank:.1f}位")
            print(f"  変動タイプ: {stability} (標準偏差: {rank_std:.2f})")
            print(f"  逆転: {Colors.CYAN}{comebacks}回{Colors.RESET} (最大+{max_comeback}位) | 転落: {Colors.RED}{falls}回{Colors.RESET} (最大-{max_fall}位)")
            print()
        
        # 全体の逆転性指標
        all_rank_changes = []
        total_comebacks = 0
        total_falls = 0
        
        for player in self.players:
            if len(player.state.set_ranks) < 2:
                continue
            ranks = player.state.set_ranks
            for i in range(1, len(ranks)):
                change = ranks[i] - ranks[i-1]
                all_rank_changes.append(abs(change))
                if change < 0:
                    total_comebacks += 1
                elif change > 0:
                    total_falls += 1
        
        if all_rank_changes:
            avg_change = sum(all_rank_changes) / len(all_rank_changes)
            max_change = max(all_rank_changes)
            
            # 逆転性スコア（0-100%）
            # 順位変動が大きいほど逆転性が高い
            reversal_score = min(100, (avg_change / len(self.players)) * 100)
            
            print(f"{Colors.BOLD}【総合逆転性】{Colors.RESET}")
            print(f"  平均順位変動: {avg_change:.2f}位/セット")
            print(f"  最大順位変動: {max_change}位")
            print(f"  総逆転回数: {Colors.CYAN}{total_comebacks}回{Colors.RESET} vs 総転落回数: {Colors.RED}{total_falls}回{Colors.RESET}")
            
            # 逆転性の評価
            if reversal_score < 20:
                evaluation = f"{Colors.GREEN}低逆転性{Colors.RESET} - 実力差が明確に反映される"
            elif reversal_score < 40:
                evaluation = f"{Colors.YELLOW}中逆転性{Colors.RESET} - 適度な順位変動がある"
            elif reversal_score < 60:
                evaluation = f"{Colors.MAGENTA}高逆転性{Colors.RESET} - ドラマチックな展開が多い"
            else:
                evaluation = f"{Colors.RED}超高逆転性{Colors.RESET} - 毎回順位が大きく変動する"
            
            print(f"  {Colors.BOLD}逆転性スコア: {reversal_score:.1f}% - {evaluation}{Colors.RESET}")
        
        print(f"{Colors.BOLD}{Colors.CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.RESET}\n")
    
    def _display_game_theory_analysis(self):
        """ゲーム理論的な分析を表示"""
        print(f"\n{Colors.BOLD}{Colors.MAGENTA}╔═════════════════════════════════════════════════════════╗{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.MAGENTA}║           【ゲーム理論分析】戦略の深さ              ║{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.MAGENTA}╚═════════════════════════════════════════════════════════╝{Colors.RESET}\n")
        
        # 各プレイヤーの選択履歴を分析
        total_choices = []
        player_risk_profiles = {}
        
        for player in self.players:
            if len(player.state.choice_history) == 0:
                continue
            
            choices = player.state.choice_history
            total_choices.extend(choices)
            
            # リスクプロファイルの計算
            safe_choices = sum(1 for c in choices if c <= 3)  # 1-3: 安全
            medium_choices = sum(1 for c in choices if 4 <= c <= 6)  # 4-6: 中リスク
            risky_choices = sum(1 for c in choices if c >= 7)  # 7-10: 高リスク
            
            avg_choice = sum(choices) / len(choices) if choices else 0
            
            player_risk_profiles[player.state.name] = {
                'avg_choice': avg_choice,
                'safe': safe_choices,
                'medium': medium_choices,
                'risky': risky_choices,
                'total': len(choices)
            }
        
        # 全体の戦略分布
        if total_choices:
            avg_global_choice = sum(total_choices) / len(total_choices)
            print(f"{Colors.BOLD}1. 戦略的多様性{Colors.RESET}")
            print(f"   平均選択値: {avg_global_choice:.2f} / 10.0")
            print(f"   解釈: ", end="")
            if avg_global_choice < 4.0:
                print(f"{Colors.GREEN}超保守的{Colors.RESET} - リスク回避優勢")
            elif avg_global_choice < 5.5:
                print(f"{Colors.CYAN}バランス型{Colors.RESET} - リスクとリターンの均衡")
            elif avg_global_choice < 7.0:
                print(f"{Colors.YELLOW}やや攻撃的{Colors.RESET} - リターン重視")
            else:
                print(f"{Colors.RED}超攻撃的{Colors.RESET} - 高リスク高リターン")
            print()
        
        # ナッシュ均衡の検討
        print(f"{Colors.BOLD}2. ナッシュ均衡への収束性{Colors.RESET}")
        
        # 各プレイヤーのリスクプロファイルを比較
        risk_variance = []
        for name, profile in player_risk_profiles.items():
            risk_variance.append(profile['avg_choice'])
        
        if len(risk_variance) > 1:
            variance = sum((x - avg_global_choice) ** 2 for x in risk_variance) / len(risk_variance)
            std_dev = variance ** 0.5
            
            print(f"   戦略の標準偏差: {std_dev:.2f}")
            print(f"   解釈: ", end="")
            if std_dev < 1.0:
                print(f"{Colors.GREEN}高収束{Colors.RESET} - プレイヤー間で似た戦略")
            elif std_dev < 2.0:
                print(f"{Colors.YELLOW}中収束{Colors.RESET} - ある程度の戦略的多様性")
            else:
                print(f"{Colors.MAGENTA}低収束{Colors.RESET} - 各プレイヤーが独自戦略")
            print()
        
        # 支配戦略の存在
        print(f"{Colors.BOLD}3. 支配戦略の分析{Colors.RESET}")
        
        # 【修正】「1位以外全員死亡」ルール後の分析
        # 優勝者（is_alive=Trueが1人）とそれ以外で比較
        winner = [p for p in self.players if p.state.is_alive and p.state.total_score == max(p.state.total_score for p in self.players)]
        non_winners = [p for p in self.players if not (p.state.is_alive and p.state.total_score == max(p.state.total_score for p in self.players))]
        
        if winner and non_winners:
            winner_avg = sum(sum(p.state.choice_history) / len(p.state.choice_history) 
                           for p in winner if p.state.choice_history) / len(winner)
            non_winner_avg = sum(sum(p.state.choice_history) / len(p.state.choice_history) 
                               for p in non_winners if p.state.choice_history) / len(non_winners)
            
            print(f"   優勝者の平均選択: {winner_avg:.2f}")
            print(f"   その他の平均選択: {non_winner_avg:.2f}")
            print(f"   差分: {abs(winner_avg - non_winner_avg):.2f}")
            print(f"   解釈: ", end="")
            
            if abs(winner_avg - non_winner_avg) < 0.5:
                print(f"{Colors.CYAN}支配戦略なし{Colors.RESET} - どの戦略も勝利可能")
            elif winner_avg < non_winner_avg:
                print(f"{Colors.GREEN}保守戦略が有利{Colors.RESET} - 慎重なプレイが有効")
            else:
                print(f"{Colors.RED}攻撃戦略が有利{Colors.RESET} - リスクテイクが重要")
            print()
        elif winner:
            # 全員のデータがない場合（稀）
            winner_avg = sum(sum(p.state.choice_history) / len(p.state.choice_history) 
                           for p in winner if p.state.choice_history) / len(winner)
            print(f"   優勝者の平均選択: {winner_avg:.2f}")
            print(f"   {Colors.GRAY}(他プレイヤーのデータ不足){Colors.RESET}")
            print()
        
        # 囚人のジレンマ構造
        print(f"{Colors.BOLD}4. 囚人のジレンマ的構造{Colors.RESET}")
        print(f"   {Colors.YELLOW}協調{Colors.RESET}（全員が安全策） vs {Colors.RED}裏切り{Colors.RESET}（自分だけリスク）")
        
        # 全員が低リスクを選んだラウンドを探す
        # これは実装が複雑なので、概念的な説明に留める
        print(f"   - 全員が慎重 → 誰も大きく稼げない → 膠着状態")
        print(f"   - 1人だけ攻撃 → その人が大きくリード → 裏切りの誘惑")
        print(f"   - 全員が攻撃 → クラッシュ多発 → 共倒れのリスク")
        print(f"   結論: {Colors.MAGENTA}典型的な囚人のジレンマ構造{Colors.RESET}")
        print()
        
        # 情報の非対称性
        print(f"{Colors.BOLD}5. 情報構造{Colors.RESET}")
        print(f"   完全情報ゲーム: ✓ 全員が全ての情報を見れる")
        print(f"   同時手番: ✓ 選択は同時に行われる")
        print(f"   不確実性: ✓ クラッシュ確率が存在")
        print(f"   結論: {Colors.CYAN}完全情報・同時手番・確率的ゲーム{Colors.RESET}")
        print()
        
        # パレート効率性
        print(f"{Colors.BOLD}6. パレート効率性{Colors.RESET}")
        
        # 【修正】「1位以外全員死亡」ルールを考慮
        # 最終的には優勝者のスコアのみが「獲得」となるが、
        # ゲーム全体で生成された富の総量を評価する
        total_generated = sum(p.state.total_score for p in self.players)  # 全プレイヤーの獲得
        winner_takes = sum(p.state.total_score for p in self.players if p.state.is_alive)  # 優勝者のみ
        
        max_possible = len(self.players) * 100  # 理論上の最大（全員生存で平均的に稼ぐ場合）
        efficiency = (total_generated / max_possible) * 100 if max_possible > 0 else 0
        winner_efficiency = (winner_takes / max_possible) * 100 if max_possible > 0 else 0
        
        print(f"   全体で生成された富: {total_generated}pts ({format_money(total_generated)})")
        print(f"   優勝者が獲得: {winner_takes}pts ({format_money(winner_takes)}) {Colors.GRAY}[1位のみ総取り]{Colors.RESET}")
        print(f"   理論上最大: {max_possible}pts")
        print(f"   生成効率: {efficiency:.1f}% {Colors.GRAY}(全プレイヤーの獲得総額){Colors.RESET}")
        print(f"   最終効率: {winner_efficiency:.1f}% {Colors.GRAY}(優勝者のみ){Colors.RESET}")
        print(f"   解釈: ", end="")
        if efficiency < 30:
            print(f"{Colors.RED}低効率{Colors.RESET} - 多くの富が失われた（競争過多・クラッシュ多発）")
        elif efficiency < 60:
            print(f"{Colors.YELLOW}中効率{Colors.RESET} - バランスの取れた競争")
        else:
            print(f"{Colors.GREEN}高効率{Colors.RESET} - 協調的な戦略が機能")
        print()
        
        # ゲーム理論的評価
        print(f"{Colors.BOLD}{Colors.MAGENTA}━━━ 総合評価 ━━━{Colors.RESET}")
        print(f"✓ {Colors.GREEN}多様な均衡{Colors.RESET}: 単一の支配戦略がなく、状況に応じた判断が必要")
        print(f"✓ {Colors.YELLOW}戦略的深さ{Colors.RESET}: リスク・リターン・タイミングの3次元的判断")
        print(f"✓ {Colors.CYAN}社会的ジレンマ{Colors.RESET}: 個人合理性と集団合理性の対立")
        print(f"✓ {Colors.MAGENTA}動的均衡{Colors.RESET}: 各ラウンドで均衡点が移動する")
        print(f"✓ {Colors.RED}意味のある選択{Colors.RESET}: どの選択にも戦略的正当性がある")
        print()
        
        print(f"{Colors.BOLD}{Colors.MAGENTA}╔═════════════════════════════════════════════════════════╗{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.MAGENTA}║  ゲーム理論的に「面白い」ゲーム設計である          ║{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.MAGENTA}╚═════════════════════════════════════════════════════════╝{Colors.RESET}\n")
    
    def play_tournament(self):
        """トーナメント（5セット）をプレイ"""
        total_sets = self.config['tournament']['sets']
        
        print(f"\n{'='*60}")
        print(f"  {Colors.BOLD}APEX SURVIVOR{Colors.RESET}")
        print(f"  ~頂点に立つ者だけが生き残る~")
        print(f"  {Colors.RED}[1位以外全員脱落]{Colors.RESET}")
        print(f"{'='*60}\n")
        
        print(f"{Colors.BOLD}参加プレイヤー:{Colors.RESET}")
        for player in self.players:
            color_name = Colors.get_color(player.state.color)
            print(f"  {color_name}{player.state.name}{Colors.RESET} ({player.state.personality})")
        
        # 究極ルールの明示: 1位以外全員死亡
        print(f"\n{Colors.RED}  ・勝たなければ死ぬ{Colors.RESET}")
        print(f"{Colors.RED}  ・リスクを取っても（クラッシュ）死ぬ{Colors.RESET}")
        print(f"{Colors.RED}  ・2位も最下位も等しく死亡{Colors.RESET}")
        print(f"{Colors.RED}  -> 究極の意味圧:「やるしかない」{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.RED}{'='*60}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.GREEN}[賞金] 10pt = 1億円（優勝者のみ総取り）{Colors.RESET}")
        hp_cost = self.config['game_rules']['hp_purchase_cost']
        hp_cost_money = format_money(hp_cost)
        print(f"{Colors.BOLD}{Colors.CYAN}[HP購入] セット間で{hp_cost}pts ({hp_cost_money})でHP+1 (最大5HP){Colors.RESET}")
        print(f"{Colors.GRAY}  生命保険 vs 賞金温存の究極の選択{Colors.RESET}\n")
        
        # 最初のセットの環境を設定
        self._apply_environment_shift(1)
        
        for set_num in range(1, total_sets + 1):
            self.play_set(set_num)
        
        # Phase 4: 表示をGameDisplayに委譲
        self.display.display_tournament_results(self.players, total_sets)
        self._display_reversal_statistics()
        self._display_game_theory_analysis()
        
        # シード情報を常に表示
        print(f"\n{Colors.CYAN}[INFO] 使用した乱数シード: {self.seed_used}{Colors.RESET}")
        print(f"{Colors.CYAN}[INFO] 再現するには: python chicken_game_ssd_ai.py --seed {self.seed_used}{Colors.RESET}")
    
    def _display_tournament_results(self):
        """トーナメント最終結果 - 1位以外全員死亡ルール"""
        print(f"\n{'#'*60}")
       
        print(f"#{' '*15}トーナメント最終結果{' '*17}#")
        print(f"{'#'*60}\n")
        
        # 途中脱落者と生存者を分ける
        alive_players = [p for p in self.players if p.state.is_alive]
        dead_players = [p for p in self.players if not p.state.is_alive]
        
        # 生存者をスコア順でソート
        sorted_alive = sorted(alive_players, key=lambda p: p.state.total_score, reverse=True)
        sorted_dead = sorted(dead_players, key=lambda p: p.state.total_score, reverse=True)
        
        # 究極の意味圧: 1位以外は全員死亡
        print(f"{Colors.BOLD}{Colors.RED}╔═══════════════════════════════════════════════════════╗{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.RED}║  【究極ルール】1位以外　全員死亡                    ║{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.RED}║  勝たなければ死ぬ、リスクを取っても死ぬ              ║{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.RED}║  この世界に2位はない - 勝者か、死者か               ║{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.RED}╚═══════════════════════════════════════════════════════╝{Colors.RESET}\n")
        
        print(f"{Colors.BOLD}最終順位:{Colors.RESET}\n")
        
        # 1位（唯一の生存者）
        if len(sorted_alive) > 0:
            winner = sorted_alive[0]
            color_name = Colors.get_color(winner.state.color)
            hp_indicator = "❤️ " * winner.state.hp
            money = format_money(winner.state.total_score)
            
            # HP1での勝利は特別演出
            if winner.state.hp == 1:
                print(f"🏆👑🏆 {Colors.BOLD}{Colors.RED}優勝: {color_name}{winner.state.name}{Colors.RESET} - {winner.state.total_score}pts ({Colors.GREEN}{money}{Colors.RESET}) {hp_indicator} 🏆👑🏆")
                print(f"{Colors.RED}{Colors.BOLD}    >>> 命がけの勝利！ - {money}を獲得して生き残った <<<{Colors.RESET}\n")
            else:
                print(f"🏆👑🏆 {Colors.BOLD}{Colors.YELLOW}優勝: {color_name}{winner.state.name}{Colors.RESET} - {winner.state.total_score}pts ({Colors.GREEN}{money}{Colors.RESET}) {hp_indicator} 🏆👑🏆")
                print(f"{Colors.GREEN}    >>> 唯一の生存者 - {money}を獲得して生き残った <<<{Colors.RESET}\n")
            
            # 2位以下の生存者も死亡（状態を更新）
            if len(sorted_alive) > 1:
                print(f"{Colors.RED}━━━ 2位以下：勝利できず死亡（賞金なし） ━━━{Colors.RESET}\n")
                for i, player in enumerate(sorted_alive[1:], 2):
                    # 2位以下を死亡状態に設定
                    player.state.is_alive = False
                    player.state.elimination_reason = "トーナメント終了時: 1位以外全員死亡ルール"
                    
                    color_name = Colors.get_color(player.state.color)
                    money = format_money(player.state.total_score)
                    print(f"💀 {Colors.GRAY}{i}位: {color_name}{player.state.name}{Colors.RESET} - {player.state.total_score}pts ({money}) 💀 {Colors.RED}[敗北・死亡]{Colors.RESET}")
                    print(f"{Colors.GRAY}   「{money}獲得したのに...勝てなかった」{Colors.RESET}")
        
        # 途中脱落者（既に死亡）
        if len(sorted_dead) > 0:
            print(f"\n{Colors.RED}━━━ 途中脱落：クラッシュによる死亡（賞金没収） ━━━{Colors.RESET}\n")
            start_rank = len(sorted_alive)
            for i, player in enumerate(sorted_dead, 1):
                rank = start_rank + i
                color_name = Colors.get_color(player.state.color)
                money = format_money(player.state.total_score)
                print(f"💀 {Colors.GRAY}{rank}位: {color_name}{player.state.name}{Colors.RESET} - {player.state.total_score}pts ({money}) 💀 {Colors.RED}[途中脱落]{Colors.RESET}")
                
                # 脱落詳細を表示
                if player.state.eliminated_set > 0:
                    print(f"{Colors.GRAY}   📍 SET {player.state.eliminated_set} - ROUND {player.state.eliminated_round}で脱落{Colors.RESET}")
                    print(f"{Colors.GRAY}   💥 {player.state.elimination_reason}{Colors.RESET}")
                    
                    # 脱落時の状況を詳細表示
                    print(f"{Colors.GRAY}   📊 脱落時の状況:{Colors.RESET}")
                    print(f"{Colors.GRAY}      - HP: {player.state.eliminated_hp} → 0 (致命的){Colors.RESET}")
                    print(f"{Colors.GRAY}      - セット順位: {player.state.eliminated_rank}位 (スコア: {player.state.eliminated_score}pts){Colors.RESET}")
                    if player.state.eliminated_rank > 1:
                        print(f"{Colors.GRAY}      - セット1位との点差: {player.state.eliminated_gap}pts{Colors.RESET}")
                    
                    # 総合順位情報
                    if player.state.eliminated_overall_rank > 0:
                        print(f"{Colors.GRAY}      - 総合順位: {player.state.eliminated_overall_rank}位 (総合スコア: {player.state.total_score}pts){Colors.RESET}")
                        if player.state.eliminated_overall_rank > 1 and player.state.eliminated_overall_gap > 0:
                            print(f"{Colors.GRAY}      - 総合1位との点差: {player.state.eliminated_overall_gap}pts{Colors.RESET}")
                    
                    # 選択理由を推測（セット順位と総合順位の両方を考慮）
                    hp_was_low = player.state.eliminated_hp <= 2
                    
                    # セット内状況
                    set_winning = player.state.eliminated_rank <= 2
                    set_losing = player.state.eliminated_rank >= 4
                    set_large_gap = player.state.eliminated_gap > 30
                    set_reversal_possible = player.state.eliminated_reversal_possible
                    
                    # 総合状況
                    overall_winning = player.state.eliminated_overall_rank <= 2
                    overall_losing = player.state.eliminated_overall_rank >= 4
                    overall_large_gap = player.state.eliminated_overall_gap > 50
                    overall_reversal_possible = player.state.eliminated_overall_reversal_possible
                    
                    # リスクレベル
                    high_risk = player.state.eliminated_choice >= 7
                    medium_risk = player.state.eliminated_choice >= 5
                    safe_choice = player.state.eliminated_choice <= 3
                    
                    print(f"{Colors.GRAY}   🤔 選択理由の推測:{Colors.RESET}")
                    
                    # === 総合順位が優先（全体の勝利が目標） ===
                    
                    # パターン1: 総合上位 & セット劣勢
                    if overall_winning and set_losing:
                        if safe_choice:
                            print(f"{Colors.GRAY}      → 総合上位を守るため安全策も運悪くクラッシュ（不運）{Colors.RESET}")
                        elif medium_risk:
                            print(f"{Colors.GRAY}      → 総合上位キープのため適度なリスク（堅実）{Colors.RESET}")
                        else:
                            print(f"{Colors.GRAY}      → 総合では上位だがセット内で焦りすぎた可能性{Colors.RESET}")
                    
                    # パターン2: 総合劣勢 & セット上位
                    elif overall_losing and set_winning:
                        if high_risk:
                            print(f"{Colors.GRAY}      → セット上位でも総合劣勢、高リスクで総合逆転狙い（背水の陣）{Colors.RESET}")
                        elif not overall_reversal_possible:
                            print(f"{Colors.GRAY}      → セット勝利も総合逆転不可能、絶望的な状況で高リスク選択{Colors.RESET}")
                        else:
                            print(f"{Colors.GRAY}      → セット勝利より総合逆転を優先した攻めの姿勢{Colors.RESET}")
                    
                    # パターン3: 両方上位（理想的）
                    elif overall_winning and set_winning:
                        if hp_was_low and high_risk:
                            print(f"{Colors.GRAY}      → 両方上位で有利だがHP=1で高リスク（欲張りすぎ）{Colors.RESET}")
                        elif safe_choice:
                            print(f"{Colors.GRAY}      → 両方上位で安全策を選ぶも運悪くクラッシュ（不運）{Colors.RESET}")
                        else:
                            print(f"{Colors.GRAY}      → 有利な状況でリスク管理ミス{Colors.RESET}")
                    
                    # パターン4: 両方劣勢（絶望的）
                    elif overall_losing and set_losing:
                        if not overall_reversal_possible and not set_reversal_possible:
                            print(f"{Colors.GRAY}      → セット・総合とも逆転不可能、絶望的状況で最後の賭け{Colors.RESET}")
                        elif high_risk:
                            print(f"{Colors.GRAY}      → 両方劣勢で高リスク選択、一か八かの大勝負（背水の陣）{Colors.RESET}")
                        elif overall_large_gap:
                            print(f"{Colors.GRAY}      → 総合で大差、セットでも劣勢という二重苦での攻勢{Colors.RESET}")
                        else:
                            print(f"{Colors.GRAY}      → 両方劣勢で逆転を狙うも失敗{Colors.RESET}")
                    
                    # パターン5: セット上位のみ考慮（総合順位不明 or 単一セット）
                    elif set_winning:
                        if hp_was_low and high_risk:
                            print(f"{Colors.GRAY}      → セット上位でHP=1、逃げ切り狙いも失敗（欲張り）{Colors.RESET}")
                        elif safe_choice:
                            print(f"{Colors.GRAY}      → セット上位で安全策も運悪くクラッシュ（不運）{Colors.RESET}")
                        else:
                            print(f"{Colors.GRAY}      → セット上位でリスク管理ミス{Colors.RESET}")
                    
                    # パターン6: セット劣勢のみ
                    elif set_losing:
                        if not set_reversal_possible:
                            print(f"{Colors.GRAY}      → セット内逆転不可能な状況で高リスク選択（絶望的）{Colors.RESET}")
                        elif set_large_gap and high_risk:
                            print(f"{Colors.GRAY}      → セット内で大差、高リスクで逆転狙い（背水の陣）{Colors.RESET}")
                        else:
                            print(f"{Colors.GRAY}      → セット劣勢で逆転を狙うも失敗{Colors.RESET}")
                    
                    # パターン7: 中位
                    else:
                        if hp_was_low and high_risk:
                            print(f"{Colors.GRAY}      → HP=1で高リスク選択（ギャンブル）{Colors.RESET}")
                        elif safe_choice:
                            print(f"{Colors.GRAY}      → 安全策を取るも運悪くクラッシュ（不運）{Colors.RESET}")
                        else:
                            print(f"{Colors.GRAY}      → リスクとリターンのバランスを取るも失敗{Colors.RESET}")
                    
                    if player.state.total_score > 0:
                        print(f"{Colors.GRAY}   💸 {money}を失って死亡...{Colors.RESET}")
                else:
                    print(f"{Colors.GRAY}   「リスクの代償...」{Colors.RESET}")
        
        # 逆転性統計の計算
        self._display_reversal_statistics()
        
        # ゲーム理論的分析の表示
        self._display_game_theory_analysis()
        
        # 最終メッセージ
        print(f"\n{Colors.BOLD}{Colors.RED}╔═══════════════════════════════════════════════════════╗{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.RED}║  生存者: 1名 / 死亡者: {len(self.players)-1}名                          ║{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.RED}║  「勝たなければ死ぬ」- これが究極の意味圧           ║{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.RED}╚═══════════════════════════════════════════════════════╝{Colors.RESET}")
        
        # シード情報を常に表示
        print(f"\n{Colors.CYAN}[INFO] 使用した乱数シード: {self.seed_used}{Colors.RESET}")
        print(f"{Colors.CYAN}[INFO] 再現するには: python chicken_game_ssd_ai.py --seed {self.seed_used}{Colors.RESET}")
        
        print(f"{'#'*60}\n")


