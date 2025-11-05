#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
APEX SURVIVOR - 頂点に立つ者だけが生き残る

デスゲーム型心理戦ゲーム
- 1-10の数字を選択（高い数字ほど高リスク・高リターン）
- 1位以外全員死亡（究極のゼロサムゲーム）
- クラッシュリスク: 段階的（5%-75%）
- 5ラウンド × 5セット構造
- 環境変動システム（Normal/Safe/Deadly/Volatile/Extreme）
- SSD理論AIによる学習と意味圧の蓄積

Phase 4完了: モジュール化完了
- core/player.py: ChickenPlayer (1144行)
- core/game.py: ChickenGame (1446行)
- このファイル: エントリーポイントのみ (<100行)
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import random
import numpy as np

# Phase 4: コアクラスをインポート
from core import ChickenGame


def main():
    import argparse
    import os
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_config_path = os.path.join(script_dir, 'chicken_game_config.yaml')

    parser = argparse.ArgumentParser(description='APEX SURVIVOR - 頂点に立つ者だけが生き残る')
    parser.add_argument('--config', default=default_config_path,
                       help='設定ファイルのパス')
    parser.add_argument('--seed', type=int, help='乱数シード')
    
    args = parser.parse_args()
    
    # シードの設定（指定がない場合はランダムに生成）
    if args.seed is not None:
        seed = args.seed
    else:
        # ランダムシードを生成（0-999999の範囲）
        seed = random.randint(0, 999999)
    
    random.seed(seed)
    np.random.seed(seed)
    
    game = ChickenGame(args.config)
    game.seed_used = seed  # シード情報を保存（常に記録）
    game.play_tournament()


if __name__ == '__main__':
    main()
