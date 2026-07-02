"""AI エージェント（LangGraph）。

親エージェント（orchestrator）が意図を判定し、子エージェント（general / company）
へ委任する。各子エージェントは独立したグラフで、単体でも実行できる。
設計方針は リポジトリ直下 CLAUDE.md の「LangGraph / LLM エージェント設計方針」を参照。
"""
