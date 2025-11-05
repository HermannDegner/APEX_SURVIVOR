# APEX SURVIVOR - 頂点に立つ者だけが生き残る

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-37%20passed-success.svg)](tests/)
[![Coverage](https://img.shields.io/badge/coverage-73%25-yellowgreen.svg)](htmlcov/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**デスゲーム型心理戦シミュレーター**  
[SSD理論（Structural Subjectivity Dynamics）](https://github.com/HermannDegner/Structural-Subjectivity-Dynamics)を用いた高度なAI意思決定システム

---

## 🎮 ゲーム概要

### コンセプト
**究極のゼロサムゲーム** - 1位以外全員死亡  
リスクを取らなければ勝てない、しかしリスクを取りすぎれば死ぬ。  
この矛盾した状況で、AIはどのような意思決定を行うのか？

### ゲームルール

#### 基本構造
- **選択**: 各ラウンドで1-10の数字を選択
- **リスク**: 高い数字ほど高リターン・高クラッシュ率
- **勝利条件**: 最高スコアのプレイヤーのみ生存
- **構成**: 5ラウンド × 5セット = 25ラウンド

#### クラッシュシステム
```
選択値  スコア  クラッシュ率
  1      10pt     2%
  3      30pt     8%
  5      50pt    16%
  8      80pt    45%
  10    100pt    65%
```

#### 環境システム
- **Normal** (通常): 基本クラッシュ率
- **Safe** (安全): クラッシュ率-20%, 報酬-10%
- **Deadly** (危険): クラッシュ率+30%, 報酬+80%
- **Volatile** (不安定): ランダム変動
- **Extreme** (極限): クラッシュ率+50%, 報酬+150%

#### HP・復活システム
- 初期HP: 3
- クラッシュでHP-1
- HP=0で脱落
- セット間でHP購入可能（20pts/HP）

---

## 🧠 SSD理論による意思決定

### Structural Subjectivity Dynamics（構造的主観性力学）
AIの内部状態を「意味圧（semantic pressure）」として数値化し、動的に戦略を調整

詳細は [SSD理論リポジトリ](https://github.com/HermannDegner/Structural-Subjectivity-Dynamics) を参照

#### 主要パラメータ
```python
κ (kappa):  戦略の整合性 (0-1)
E:          未処理の意味圧力
T:          温度パラメータ（探索度）
```

#### 意味圧の計算
```
P = α·(順位圧) + β·(スコア差圧) + γ·(時間圧) + δ·(生存圧)
```

#### セマンティックジャンプ
高い意味圧 → 戦略の大胆な転換（慎重→攻撃的）

---

## 📦 インストール

### 必要要件
- Python 3.11+
- NumPy 1.24+
- PyYAML 6.0+

### セットアップ
```bash
# リポジトリのクローン
git clone https://github.com/yourusername/apex-survivor.git
cd apex-survivor/casino

# 依存関係のインストール
pip install -r requirements.txt

# テストの実行
pytest tests/ -v
```

---

## 🚀 使い方

### 基本実行
```bash
# デフォルト設定で実行
python chicken_game_ssd_ai.py

# シード指定で実行（再現可能）
python chicken_game_ssd_ai.py --seed 12345

# カスタム設定で実行
python chicken_game_ssd_ai.py --config my_config.yaml
```

### 設定ファイル
`chicken_game_config.yaml`で詳細設定が可能：
- プレイヤー数・性格
- ラウンド数・セット数
- クラッシュ率・報酬倍率
- SSDパラメータ

---

## 🏗️ アーキテクチャ

### モジュール構成
```
casino/
├── chicken_game_ssd_ai.py     # エントリーポイント (66行)
├── chicken_game_config.yaml   # ゲーム設定
│
├── core/                      # コアゲームロジック
│   ├── __init__.py
│   ├── state.py              # 状態管理 (63行)
│   ├── player.py             # プレイヤーAI (1165行)
│   └── game.py               # ゲーム進行 (1468行)
│
├── ssd/                       # SSD理論実装
│   ├── __init__.py
│   ├── core.py               # SSDコア (400+行)
│   └── state.py              # SSD状態管理
│
├── strategy/                  # 戦略モジュール
│   ├── __init__.py
│   ├── ssd_strategy.py       # SSD戦略 (206行)
│   └── rule_strategy.py      # ルール戦略 (225行)
│
├── pressure/                  # 意味圧計算
│   ├── rank_pressure.py      # 順位圧
│   ├── score_pressure.py     # スコア圧
│   ├── time_pressure.py      # 時間圧
│   ├── survival_pressure.py  # 生存圧
│   └── overall_pressure.py   # 総合圧
│
├── display/                   # 表示系
│   ├── colors.py
│   ├── formatters.py
│   └── game_display.py       # ゲーム表示 (306行)
│
└── tests/                     # テストスイート
    ├── test_player.py
    ├── test_player_advanced.py
    ├── test_game.py
    ├── test_game_advanced.py
    └── test_display.py
```

### データフロー
```
1. ゲーム初期化 (ChickenGame.__init__)
   ↓
2. プレイヤー作成 (ChickenPlayer × N)
   ↓
3. セット開始
   ├─ 環境選択 (AI投票)
   ├─ ラウンド実行 (×5)
   │  ├─ 意味圧計算
   │  ├─ 戦略決定 (SSD/Rule)
   │  ├─ 選択実行 (1-10)
   │  ├─ クラッシュ判定
   │  └─ スコア更新
   ├─ セット結果
   └─ HP購入フェーズ
   ↓
4. 最終結果 (1位のみ生存)
```

---

## 📊 テスト

### テスト統計
```
Total Tests:    37 passed
Coverage:       73%
  - core:       75%
  - display:    66%
Execution Time: 1.59s
```

### テストカテゴリ
- **スモークテスト** (5) - 基本動作確認
- **エッジケース** (5) - 境界値・異常値
- **パラメータ化** (14) - 複数パターン自動テスト
- **統合テスト** (10) - エンドツーエンド検証
- **パフォーマンス** (1) - 性能テスト
- **堅牢性** (2) - エラーハンドリング

### テスト実行
```bash
# 全テスト実行
pytest tests/ -v

# カバレッジ測定
pytest tests/ --cov=core --cov=display --cov-report=html

# 特定カテゴリのみ
pytest tests/ -k "edge" -v          # エッジケースのみ
pytest tests/ -k "parametrize" -v   # パラメータ化のみ
pytest tests/ -m "not slow" -v      # 高速テストのみ
```

---

## 🎯 開発の歴史

### Phase 1-3: 基盤構築
- SSD理論の実装
- 戦略モジュール分離
- 意味圧計算システム

### Phase 4: モジュール化 (完了 ✅)
- メインファイル: 2667行 → **66行** (97.5%削減)
- ChickenPlayer抽出: 1165行
- ChickenGame抽出: 1468行
- 表示系モジュール化: 306行

### Phase 5: テスト充実 (完了 ✅)
- テスト数: 5 → **37** (+640%)
- カバレッジ: 72% → **73%**
- エッジケース・パラメータ化・統合テスト追加

### Phase 6: ドキュメント整備 (進行中 🚧)
- README.md完成
- API ドキュメント
- アーキテクチャ図
- CHANGELOG

---

## 📈 ゲーム理論分析

### 実装された概念
- **囚人のジレンマ**: 協調 vs 裏切り
- **ナッシュ均衡**: 戦略の収束
- **パレート効率**: 全体最適 vs 個人最適
- **支配戦略**: 状況依存の最適解

### 戦略的深さ
```
✓ 多様な均衡: 単一の支配戦略なし
✓ 3次元判断: リスク × リターン × タイミング
✓ 社会的ジレンマ: 個人合理性 vs 集団合理性
✓ 動的均衡: 各ラウンドで均衡点が移動
```

---

## 🤝 コントリビューション

### 開発への参加
1. このリポジトリをフォーク
2. フィーチャーブランチを作成 (`git checkout -b feature/amazing`)
3. 変更をコミット (`git commit -m 'Add amazing feature'`)
4. ブランチにプッシュ (`git push origin feature/amazing`)
5. プルリクエストを作成

### コーディング規約
- Python PEP 8準拠
- 型ヒントの使用推奨
- Docstring必須（主要関数）
- テストカバレッジ70%以上維持

---

## 📝 ライセンス

MIT License - 詳細は[LICENSE](LICENSE)を参照

---

## 👤 作成者

**SSD Theory Research Team**

---

## 🔗 関連リンク

- [SSD理論詳細](docs/SSD_THEORY.md)
- [API リファレンス](docs/API_REFERENCE.md)
- [開発者ガイド](docs/DEVELOPER_GUIDE.md)
- [CHANGELOG](CHANGELOG.md)

---

## 🎓 引用

このプロジェクトを研究で使用する場合：

```bibtex
@software{apex_survivor,
  title={APEX SURVIVOR: SSD-based Decision Making in Death Game Simulation},
  author={SSD Theory Research Team},
  year={2025},
  url={https://github.com/yourusername/apex-survivor}
}
```

---

## 📊 統計情報

- **総コード行数**: 5,000+行
- **モジュール数**: 20+
- **テスト数**: 37
- **カバレッジ**: 73%
- **開発期間**: Phase 1-6
- **最終更新**: 2025年11月5日

---

## 🚀 今後の展開

### 予定機能
- [ ] GUI版の開発
- [ ] リアルタイム対戦モード
- [ ] 機械学習による戦略最適化
- [ ] より詳細な統計分析
- [ ] カスタムAI戦略のプラグインシステム

### 研究課題
- [ ] SSD理論の更なる発展
- [ ] 意味圧の可視化
- [ ] 人間プレイヤーとの比較実験
- [ ] 戦略進化のシミュレーション

---

**「勝たなければ死ぬ、リスクを取っても死ぬ。究極の選択の中で、AIは何を選ぶのか？」**
