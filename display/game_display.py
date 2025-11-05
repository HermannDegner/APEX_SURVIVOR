"""
ゲーム表示モジュール

ChickenGameの表示系メソッドを集約
- トーナメント結果表示
- ゲーム理論分析表示
- 逆転統計表示
- セット結果表示
- 順位表示
"""

from typing import List, Dict, Tuple
from display.colors import Colors
from display.formatters import format_money, format_score_with_money


class GameDisplay:
    """ゲーム表示クラス"""
    
    def __init__(self, config: Dict):
        """
        Args:
            config: ゲーム設定辞書
        """
        self.config = config
    
    def display_tournament_results(self, players: List, sets_played: int):
        """
        トーナメント最終結果を表示（1位以外全員死亡ルール）
        
        Args:
            players: プレイヤーリスト
            sets_played: プレイ済みセット数
        """
        print(f"\n{'#'*60}")
        print(f"#{' '*15}トーナメント最終結果{' '*17}#")
        print(f"{'#'*60}\n")
        
        # 途中脱落者と生存者を分ける
        alive_players = [p for p in players if p.state.is_alive]
        dead_players = [p for p in players if not p.state.is_alive]
        
        # 生存者をスコア順でソート
        sorted_alive = sorted(alive_players, key=lambda p: p.state.total_score, reverse=True)
        sorted_dead = sorted(dead_players, key=lambda p: p.state.total_score, reverse=True)
        
        # 究極の意味圧: 1位以外は全員死亡
        print(f"{Colors.BOLD}{Colors.RED}╔═══════════════════════════════════════════════════════╗{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.RED}║  【究極ルール】1位以外　全員死亡                    ║{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.RED}║  勝たなければ死ぬ、リスクを取っても死ぬ              ║{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.RED}║  この世界に2位はない - 勝者か、死者か               ║{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.RED}╚═══════════════════════════════════════════════════════╝{Colors.RESET}\n")
        
        # --- 生存者（順位付き）---
        if sorted_alive:
            print(f"{Colors.BOLD}🏆 生存者（スコア順）{Colors.RESET}")
            print(f"{'─'*60}")
            
            for rank, player in enumerate(sorted_alive, 1):
                color_text = Colors.get_color(player.state.color)
                
                # 1位は特別扱い（唯一の勝者）
                if rank == 1:
                    print(f"{Colors.BOLD}{Colors.YELLOW}👑 優勝 👑{Colors.RESET}")
                    print(f"  {color_text}{player.state.name}{Colors.RESET} ({player.state.personality})")
                    print(f"  最終スコア: {Colors.BOLD}{Colors.YELLOW}{format_score_with_money(player.state.total_score)}{Colors.RESET}")
                    print(f"  HP: {'❤️ ' * player.state.hp}")
                    
                    # 賞金総取り
                    total_prize = player.state.total_score
                    print(f"  {Colors.BOLD}{Colors.GREEN}💰 賞金獲得: {format_money(total_prize)}{Colors.RESET}")
                    print(f"  {Colors.BOLD}{Colors.GREEN}✨ 唯一の生存者として勝利！ ✨{Colors.RESET}\n")
                else:
                    # 2位以下も生存しているが...死亡確定
                    print(f"{Colors.BOLD}{Colors.RED}💀 {rank}位: {color_text}{player.state.name}{Colors.RESET} (生存中だが...)")
                    print(f"  スコア: {format_score_with_money(player.state.total_score)}")
                    print(f"  HP: {'❤️ ' * player.state.hp}")
                    print(f"  {Colors.RED}→ 1位でないため、トーナメント終了後に脱落{Colors.RESET}\n")
        
        # --- 途中死亡者 ---
        if sorted_dead:
            print(f"\n{Colors.BOLD}{Colors.RED}💀 途中脱落者{Colors.RESET}")
            print(f"{'─'*60}")
            
            for player in sorted_dead:
                color_text = Colors.get_color(player.state.color)
                print(f"  {color_text}{player.state.name}{Colors.RESET}: {format_score_with_money(player.state.total_score)} (HP 0)")
                print(f"    脱落セット: {player.state.eliminated_set} (ラウンド{player.state.eliminated_round})")
                print(f"    死因: {player.state.elimination_reason}\n")
        
        # --- 統計情報 ---
        print(f"\n{Colors.BOLD}📊 統計情報{Colors.RESET}")
        print(f"{'─'*60}")
        print(f"  総セット数: {sets_played}")
        print(f"  総ラウンド数: {sets_played * self.config['tournament']['rounds']}")
        print(f"  生存者数: {len(sorted_alive)}")
        print(f"  途中脱落者数: {len(sorted_dead)}")
        
        # 最高スコア
        if sorted_alive or sorted_dead:
            all_players_sorted = sorted(players, key=lambda p: p.state.total_score, reverse=True)
            highest_scorer = all_players_sorted[0]
            color_text = Colors.get_color(highest_scorer.state.color)
            print(f"  最高スコア: {color_text}{highest_scorer.state.name}{Colors.RESET} - {format_score_with_money(highest_scorer.state.total_score)}")
        
        # 最多HP
        max_hp_players = sorted(players, key=lambda p: p.state.hp, reverse=True)
        if max_hp_players:
            max_hp = max_hp_players[0].state.hp
            max_hp_names = [p.state.name for p in max_hp_players if p.state.hp == max_hp]
            print(f"  最大HP: {max_hp} HP ({', '.join(max_hp_names)})")
        
        print(f"\n{'='*60}")
        print(f"{Colors.BOLD}ゲーム終了{Colors.RESET}")
        print(f"{'='*60}\n")
    
    def display_game_theory_analysis(self, players: List, sets_history: List[Dict]):
        """
        ゲーム理論的分析を表示
        
        Args:
            players: プレイヤーリスト
            sets_history: セット履歴データ
        """
        print(f"\n{'='*60}")
        print(f"{Colors.BOLD}📈 ゲーム理論分析{Colors.RESET}")
        print(f"{'='*60}\n")
        
        # 各プレイヤーの詳細統計
        for player in players:
            color_text = Colors.get_color(player.state.color)
            print(f"{Colors.BOLD}{color_text}{player.state.name}{Colors.RESET} ({player.state.personality})")
            print(f"{'─'*60}")
            
            # 基本情報
            status = "生存" if player.state.is_alive else f"脱落(Set {player.state.death_set})"
            print(f"  状態: {status}")
            print(f"  最終スコア: {format_score_with_money(player.state.total_score)}")
            print(f"  最終HP: {player.state.hp}")
            
            # 選択統計
            if player.state.choice_history:
                choices = player.state.choice_history
                avg_choice = sum(choices) / len(choices)
                print(f"\n  選択統計:")
                print(f"    平均選択値: {avg_choice:.2f}")
                print(f"    最小/最大: {min(choices)}/{max(choices)}")
                print(f"    総選択回数: {len(choices)}")
                
                # 選択分布（1-3: 低リスク, 4-7: 中リスク, 8-10: 高リスク）
                low_risk = sum(1 for c in choices if c <= 3)
                mid_risk = sum(1 for c in choices if 4 <= c <= 7)
                high_risk = sum(1 for c in choices if c >= 8)
                total = len(choices)
                
                print(f"    リスク分布:")
                print(f"      低リスク(1-3): {low_risk}回 ({low_risk/total*100:.1f}%)")
                print(f"      中リスク(4-7): {mid_risk}回 ({mid_risk/total*100:.1f}%)")
                print(f"      高リスク(8-10): {high_risk}回 ({high_risk/total*100:.1f}%)")
            
            # 成功/失敗統計
            if player.state.success_history:
                successes = sum(player.state.success_history)
                total = len(player.state.success_history)
                success_rate = successes / total * 100 if total > 0 else 0
                
                print(f"\n  成功率: {success_rate:.1f}% ({successes}/{total})")
            
            # SSD状態
            if hasattr(player, 'ssd_state'):
                print(f"\n  SSD状態:")
                print(f"    エントロピー(E): {player.ssd_state.E:.3f}")
                print(f"    温度(T): {player.ssd_state.T:.3f}")
                print(f"    最終戦略: {player.ssd_state.last_strategy}")
            
            print()
    
    def display_reversal_statistics(self, players: List, sets_history: List[Dict]):
        """
        逆転統計を表示
        
        Args:
            players: プレイヤーリスト
            sets_history: セット履歴データ
        """
        print(f"\n{'='*60}")
        print(f"{Colors.BOLD}🔄 逆転統計{Colors.RESET}")
        print(f"{'='*60}\n")
        
        # セット逆転回数
        set_reversals = {}
        for player in players:
            set_reversals[player.state.name] = 0
        
        for set_idx, set_data in enumerate(sets_history):
            if set_idx > 0:
                prev_rankings = sets_history[set_idx - 1].get('final_rankings', [])
                curr_rankings = set_data.get('final_rankings', [])
                
                if prev_rankings and curr_rankings:
                    # 1位が変わったかチェック
                    if prev_rankings[0] != curr_rankings[0]:
                        set_reversals[curr_rankings[0]] = set_reversals.get(curr_rankings[0], 0) + 1
        
        print(f"セット間での1位逆転回数:")
        for name, count in sorted(set_reversals.items(), key=lambda x: x[1], reverse=True):
            if count > 0:
                print(f"  {name}: {count}回")
        
        print()
    
    def display_set_results(self, set_num: int, players: List, total_sets: int):
        """
        セット結果を表示
        
        Args:
            set_num: セット番号
            players: プレイヤーリスト
            total_sets: 総セット数
        """
        print(f"\n{'#'*60}")
        print(f"# SET {set_num} 終了 ")
        print(f"{'#'*60}\n")
        
        # 生存者のみをスコアでソート
        alive_players = [p for p in players if p.state.is_alive]
        sorted_players = sorted(alive_players, key=lambda p: p.state.score, reverse=True)
        
        print(f"{Colors.BOLD}セット{set_num}最終順位:{Colors.RESET}")
        print(f"{'─'*60}")
        
        for rank, player in enumerate(sorted_players, 1):
            color_text = Colors.get_color(player.state.color)
            hp_display = '❤️ ' * player.state.hp
            
            # 順位による装飾
            if rank == 1:
                rank_symbol = "🥇"
            elif rank == 2:
                rank_symbol = "🥈"
            elif rank == 3:
                rank_symbol = "🥉"
            else:
                rank_symbol = f"{rank}位"
            
            print(f"{rank_symbol} {color_text}{player.state.name:10s}{Colors.RESET} | "
                  f"セット: {player.state.score:4d}pts | "
                  f"総合: {player.state.total_score:4d}pts | "
                  f"HP: {hp_display}")
        
        # 脱落者
        dead_in_set = [p for p in players if not p.state.is_alive and p.state.death_set == set_num]
        if dead_in_set:
            print(f"\n{Colors.RED}💀 このセットでの脱落者:{Colors.RESET}")
            for player in dead_in_set:
                color_text = Colors.get_color(player.state.color)
                print(f"  {color_text}{player.state.name}{Colors.RESET} - {player.state.death_reason}")
        
        print(f"\n{'='*60}\n")
    
    def display_current_standings(self, players: List, set_num: int = 1, 
                                 total_sets: int = 1, overall_scores: Dict = None):
        """
        現在の順位を表示
        
        Args:
            players: プレイヤーリスト
            set_num: 現在のセット番号
            total_sets: 総セット数
            overall_scores: 総合スコア辞書
        """
        print(f"\n{Colors.BOLD}現在の順位:{Colors.RESET}")
        
        # 生存者のみ表示
        alive_players = [p for p in players if p.state.is_alive]
        
        # セット内スコアでソート
        sorted_by_set = sorted(alive_players, key=lambda p: p.state.score, reverse=True)
        
        # 総合スコアも取得
        if overall_scores is None:
            overall_scores = {p.state.name: p.state.total_score for p in players}
        
        # 総合順位を計算
        overall_rankings = sorted(overall_scores.items(), key=lambda x: x[1], reverse=True)
        overall_rank_map = {name: rank for rank, (name, _) in enumerate(overall_rankings, 1)}
        
        for rank, player in enumerate(sorted_by_set, 1):
            color_text = Colors.get_color(player.state.color)
            hp_display = '❤️ ' * player.state.hp
            overall_rank = overall_rank_map.get(player.state.name, '?')
            overall_score = overall_scores.get(player.state.name, 0)
            
            # 1位との差分
            if rank == 1:
                gap_text = "トップ"
            else:
                gap = sorted_by_set[0].state.score - player.state.score
                gap_text = f"-{gap}pts"
            
            print(f"{rank}位: {color_text}{player.state.name:10s}{Colors.RESET} - "
                  f"{player.state.score:3d}pts {hp_display} "
                  f"(総合{overall_rank}位: {overall_score}pts {gap_text})")
        
        print()
