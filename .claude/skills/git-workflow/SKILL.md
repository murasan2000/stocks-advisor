---
name: git-workflow
description: Claude が実装作業を行う際のブランチ運用・コミット/push・コミットメッセージ規約。作業を開始する前（ブランチ作成）と、実装が一区切りついた時（commit + push）に必ず使う。作業の消失防止と、コミット履歴からタスク・スコープが分かる状態を保つのが目的。
---

# Git ワークフロー（ブランチ・コミット・push）

Claude Code が実装作業を行う際は、以下を必ず守る。ローカルセッション・
Claude.ai セッションのどちらで作業していても同じルールを適用する。

## 1. 作業開始時に必ずブランチを切る

- `main` 上で直接作業しない。実装に着手する前に必ずブランチを切る。
- ブランチ名: `claude/feature/<topic>`（例: `claude/feature/fix-harness`）
  - `<topic>` は作業内容が分かる kebab-case の短い名前にする。
- 既に作業用ブランチ（`claude/...` や `feature/...`）上にいる場合は切り直さない。

```bash
git switch -c claude/feature/<topic>
```

## 2. 作業が一区切りついたら必ず commit して push する

- 目的は「ローカル or Claude.ai セッションが途中で終了・切断しても、やっていた
  作業がリモートに残っている」状態を常に保つこと（作業消失の防止）。
- 実装が一区切りついた時点（1機能・1修正の実装が終わった、lint/test が通った、
  など）で、指示を待たずに commit → push まで行ってよい。
- push は `.claude/settings.json` で `ask` に設定されているため、実行時に
  確認プロンプトが出る。それ自体は正常な挙動であり、push を省略する理由にはしない。

## 3. コミットメッセージ規約

```
<prefix>-<action>(#issue): <context>
```

- `prefix`: 変更領域。`api` / `web` / `doc` / `infra` など。
- `action`: 変更種別。`add`（新規追加）/ `fix`（修正）/ `bug`（バグ修正）/
  `refactor`（リファクタ）など。
- `issue`: 関連 Issue 番号。紐づく Issue が無い場合は `(#issue)` ごと省略してよい。
- `context`: 何を変更したかが後から読んで分かる説明（日本語可）。多少長くても
  タスク・スコープが伝わることを優先する。

例:
- `api-add(#1): 一覧取得API追加`
- `web-fix(#54): タイムアウト問題を修正`
- `doc-fix(#89): 構築手順書修正`
- `infra-bug(#100): パブリック公開のリソースを閉域に`
