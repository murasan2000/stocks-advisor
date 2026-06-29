# Stocks Advisor - チャットUI

ジョブAPI（`/api/v1/jobs`）と連携するチャット形式のフロントエンドです。

## 開発

```bash
cd web
npm install
npm run dev   # http://localhost:5173（/api は localhost:8000 へプロキシ）
```

バックエンドを先に起動しておくこと（リポジトリルートで `uv run python -m app.servers.api`）。

## ビルド・Lint

```bash
npm run build   # tsc 型チェック + vite build
npm run lint    # ESLint
```
