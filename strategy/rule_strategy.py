"""
ルールベース戦略モジュール

動的キャリブレーション版ルールベースAI戦略。
環境変化（クラッシュ確率変更）に自動適応する。
"""

from typing import Dict, Any, Set, Tuple, List


class RuleStrategy:
    """
    ルールベース戦略クラス
    
    各ルール:
    - always7: 環境で最も安全な手を固定
    - hp_guard: HP低下時は安全帯、余裕時は押し帯
    - safe_then_push: 終盤＋ビハインドで徐々に押しへ
    - copycat_plus1: 相手平均+1に追従
    - anti_crash: 最小リスク戦略
    - final_gambler: 最終ラウンドのみ勝負
    """
    
    def __init__(self, config: Dict[str, Any], rule_name: str = 'safe_then_push'):
        """
        Args:
            config: ゲーム設定辞書
            rule_name: 採用するルール名
        """
        self.config = config
        self.rule_name = rule_name
        
        # 帯のキャッシュ
        self._safe_set: Set[int] = set()
        self._push_set: Set[int] = set()
        self._rule_bands_ready = False
    
    def make_choice(self, 
                   round_num: int, 
                   total_rounds: int,
                   is_final_round: bool,
                   current_rank: int,
                   score_gap_from_first: int,
                   hp: int,
                   opponent_choices: Dict[str, List[int]]) -> Tuple[int, str]:
        """
        ルールに基づいて選択を行う
        
        Args:
            round_num: 現在のラウンド番号
            total_rounds: 総ラウンド数
            is_final_round: 最終ラウンドか
            current_rank: 現在の順位
            score_gap_from_first: 1位とのスコア差
            hp: 現在のHP
            opponent_choices: 各対戦相手の選択履歴
        
        Returns:
            (選択値, コメント文字列) のタプル
        """
        # 帯のキャリブレーション（初回のみ）
        self._calibrate_bands()
        
        rem = total_rounds - round_num + 1
        
        # ルールによる選択
        choice = self._execute_rule(
            rem=rem,
            is_final_round=is_final_round,
            current_rank=current_rank,
            hp=hp,
            opponent_choices=opponent_choices
        )
        
        # コメント生成
        comment = self._get_rule_comment(choice, hp)
        
        return choice, comment
    
    def _execute_rule(self,
                     rem: int,
                     is_final_round: bool,
                     current_rank: int,
                     hp: int,
                     opponent_choices: Dict[str, List[int]]) -> int:
        """
        ルールを実行して選択値を返す
        
        Args:
            rem: 残りラウンド数
            is_final_round: 最終ラウンドか
            current_rank: 現在の順位
            hp: 現在のHP
            opponent_choices: 各対戦相手の選択履歴
        
        Returns:
            選択値 (1-10)
        """
        if self.rule_name == 'always7':
            # 「7固定」→「その環境で最も安全な手」
            return self._pick_safest(self._safe_set, rem)
        
        elif self.rule_name == 'hp_guard':
            # HP低い時は安全帯、余裕がある時は押し帯の中でも安全な手
            if hp <= 2:
                return self._pick_safest(self._safe_set, rem)
            # 押し帯と安全帯の重複から選ぶ（なければ押し帯）
            push_safe = list(self._push_set & self._safe_set) or list(self._push_set)
            return self._pick_safest(push_safe, rem)
        
        elif self.rule_name == 'safe_then_push':
            # 最終ラウンド：負けなら押し、勝ち/同点なら安全
            if is_final_round:
                return self._pick_best_push(self._push_set) if current_rank > 1 else self._pick_safest(self._safe_set, rem)
            # 残り少＋ビハインドで徐々に押しへ
            if rem <= 2 and current_rank > 1:
                return self._pick_best_push(self._push_set)
            return self._pick_safest(self._safe_set, rem)
        
        elif self.rule_name == 'copycat_plus1':
            # 帯の中で「相手平均+1」に近い手を選ぶ
            target = 7
            recent = []
            for lst in opponent_choices.values():
                if lst:
                    recent.append(lst[-1])
            if recent:
                target = min(10, max(1, int(round(sum(recent) / len(recent) + 1))))
            
            pool = list(self._safe_set | self._push_set)  # 両帯を候補に
            return min(pool, key=lambda a: (abs(a - target), self._risk_score(a, rem)))
        
        elif self.rule_name == 'anti_crash':
            # 安全帯の中から最小リスク
            return self._pick_safest(self._safe_set, rem)
        
        elif self.rule_name == 'final_gambler':
            # 最終ラウンドで勝負、それ以外は安全
            if is_final_round:
                return self._pick_best_push(self._push_set) if current_rank > 1 else self._pick_safest(self._safe_set, rem)
            return self._pick_safest(self._safe_set, rem)
        
        # デフォルト
        return self._pick_safest(self._safe_set, rem)
    
    def _pick_safest(self, candidates, rem_rounds: int) -> int:
        """候補の中で最も安全な手を選ぶ"""
        if not candidates:
            # フォールバック
            return self.config['game_rules']['min_choice']
        return min(candidates, key=lambda a: self._risk_score(a, rem_rounds))
    
    def _pick_best_push(self, candidates) -> int:
        """候補の中で最も勝ち切り力の高い手を選ぶ"""
        if not candidates:
            # フォールバック
            return self.config['game_rules']['max_choice']
        return max(candidates, key=self._leverage_score)
    
    def _risk_score(self, a: int, rem_rounds: int) -> float:
        """
        リスク指標の計算
        死のコスト = クラッシュ確率 × 残りラウンド比率 × HPペナルティ
        """
        crash_p = self.config['game_rules']['crash_probabilities'].get(a, 0.0)
        total_rounds = self.config['tournament']['rounds']
        hp = max(1, 1)  # HP情報は外から渡されていないのでデフォルト1
        death_cost = (rem_rounds / total_rounds) * (1.0 + 1.5 / hp)
        return crash_p * death_cost
    
    def _leverage_score(self, a: int) -> float:
        """
        レバレッジ指標（勝ち切り力）の計算
        = 生存確率 × (選択値 + ボーナス)
        """
        crash_p = self.config['game_rules']['crash_probabilities'].get(a, 0.0)
        bonus = self.config['game_rules']['success_bonuses'].get(a, 0)
        return (1.0 - crash_p) * (a + bonus)
    
    def _calibrate_bands(self):
        """
        安全帯・押し帯の動的キャリブレーション
        クラッシュ確率に応じて帯を自動生成
        """
        if self._rule_bands_ready:
            return
        
        choices = list(range(
            self.config['game_rules']['min_choice'],
            self.config['game_rules']['max_choice'] + 1
        ))
        
        # 中盤想定の残りラウンド数で評価
        rem_rounds_mid = max(1, self.config['tournament']['rounds'] // 2)
        
        # 各選択肢のリスクとレバレッジを計算
        vals = [(a, self._risk_score(a, rem_rounds_mid), self._leverage_score(a)) 
                for a in choices]
        
        by_risk = sorted(vals, key=lambda x: x[1])  # リスク昇順
        by_lev = sorted(vals, key=lambda x: x[2], reverse=True)  # レバレッジ降順
        
        # 上位1/3を各帯に
        k = max(1, len(vals) // 3)
        self._safe_set = {a for a, _, __ in by_risk[:k]}
        self._push_set = {a for a, _, __ in by_lev[:k]}
        
        # セーフティ：押し帯が空になった場合の保険
        if not self._push_set:
            self._push_set = {by_lev[0][0]}
        
        self._rule_bands_ready = True
    
    def _get_rule_comment(self, choice: int, hp: int) -> str:
        """ルールAIのコメント生成"""
        comments = {
            'always7': "安定の7",
            'safe_then_push': "状況判断",
            'hp_guard': f"HP={hp} 基準",
            'copycat_plus1': "追従+1",
            'anti_crash': "安全第一",
            'final_gambler': "勝負どころ"
        }
        
        return f"{comments.get(self.rule_name, 'ルール実行')} → {choice}"
