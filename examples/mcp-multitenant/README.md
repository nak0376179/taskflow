# マルチテナント MCP サーバー PoC(Cognito 型認証・グループ分離・招待制)

本番想定(Cognito 認証、グループ=テナントで完全分離、招待制、DynamoDB)を
モックで再現した MCP 2026-07-28 仕様の PoC です。

## 本番との対応関係

| 本番 | この PoC | 差し替えポイント |
|---|---|---|
| Cognito(JWT) | `mock_auth.py` の固定トークン | `verify_token` を Cognito JWKS での JWT 検証に置換 |
| DynamoDB | `db.py`(インメモリ) | 同じ PK/SK 設計なので boto3 呼び出しに置換するだけ |
| グループ=テナント | `GROUP#<gid>` パーティション | そのまま |
| 招待制 | `invite_user`(owner 限定ツール) | そのまま |

## 権限モデル

- 誰でも `create_group` でグループを作成でき、作成者が **owner** になる
- 他人のグループへの参加は owner による `invite_user` のみ(招待制)
- タスクの参照・追加・更新は **member 以上**、削除と招待は **owner のみ**
- 権限判定はすべてサーバー側で、**検証済みトークンの本人情報**に対して行う。
  LLM が引数に何を渡してきても、非メンバーのグループには届かない
- 未所属グループへのアクセスは「存在しない」と同じエラーにして、
  他テナントのグループの存在自体を漏らさない

## 設計上の選択: メンバーシップは DB で解決

トークンの `cognito:groups` クレームではなく、リクエストごとに DB で
メンバーシップを解決しています。招待が**トークンリフレッシュを待たず即時に**
効くためです。トークン主導にしたい場合は `require_member` をクレーム参照に
変えるだけです。

## ブラウザ Playground(見ながら試す)

サーバーを起動して http://localhost:8766/ を開くと、操作 UI が使えます。

- 右上でユーザー(alice / bob / carol)を切り替え — Bearer トークンが切り替わる
- グループの作成・招待、タスクの追加・優先度変更・削除をボタン操作で実行
- 「グループID を直接指定 → 覗いてみる」で、未招待グループへのアクセスが
  サーバーに拒否される様子を体験できる
- 画面下部の操作ログに全 MCP 呼び出しが記録され、拒否は赤で表示。
  「生の JSON-RPC を見る」でリクエスト/レスポンスの生データも確認できる

この UI はフレームワークなしの静的 HTML 1 枚で、ブラウザの `fetch` から
MCP エンドポイントを直接呼んでいます(2026-07-28 のステートレス +
JSON 応答モードだから可能な構成)。LLM を挟む本番構成では、この UI の
ボタンの位置に Claude が入り、自然言語 → `tools/call` に変換されます。

## 実行方法

```bash
cd examples/mcp-multitenant
python3 -m venv venv && source venv/bin/activate
pip install mcp==2.0.0 fastapi uvicorn
uvicorn server:app --port 8766 &
python test_scenario.py
```

## 検証済みシナリオ(test_scenario.py)

1. alice がグループ作成 → 自動的に owner
2. alice がタスク追加
3. 未招待の bob は同じ group_id を指定しても **DENIED**
4. member でない bob は招待も **DENIED**
5. owner の alice が bob を招待
6. 招待後の bob は参照・追加が可能に
7. member の bob は削除(owner 限定)は **DENIED**
8. owner の alice は削除できる
9. carol は自分のグループを持てる(テナント完全分離)、alice のグループは **DENIED**
10. トークン無し / 不正トークンは MCP に到達する前に HTTP 401

実行結果: `All 6 permission checks behaved as expected ✔`

## この上に自然言語レイヤーを載せるには

このサーバーはそのまま Claude API の MCP コネクタや Claude Code
(`.mcp.json`)に接続できます。利用者のチャット「先週から止まってる
タスクの担当を佐藤さんに変えて」→ LLM が `list_tasks` → `update_task`
と呼び出し、各呼び出しは利用者本人の Bearer トークンで認可されます。
LLM に権限を渡すのではなく、**利用者の権限の範囲でしか動けない道具**を
LLM に持たせる構図です。
