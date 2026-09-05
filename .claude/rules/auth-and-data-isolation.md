# 認証設計・データ分離

出典: `docs/requirements/cpm-dynamic-replanning.md`

- **方式**: Googleアカウントを使ったOAuth。メール/パスワード方式は用意しない（MVPの画面数・実装量を減らすため）
- **実装**: Supabase AuthのGoogleプロバイダを利用する（Google Cloud ConsoleでOAuthクライアントを発行し、Supabaseに登録）
  - フロントエンド: `supabase-js`の`signInWithOAuth({ provider: 'google' })`でログイン導線を実装
  - バックエンド: FastAPI側でSupabaseが発行するJWTを`PyJWT`で自前検証する依存関係（dependency）を用意し、各APIエンドポイントで現在のユーザーを特定する
  - **注意（ハマりどころ）**: Supabaseの新規プロジェクトはデフォルトで非対称鍵（ECC）署名になっている場合がある。`PyJWT`で共有シークレット（HS256）検証する前提のため、**プロジェクト作成時にレガシーのJWT Secret（HS256）を有効化しておくこと**
- **データ分離（重要）**: Project/Task等は`user_id`が一致する行のみ参照・更新できるようにする。バックエンド（FastAPI）はSupabaseに`service_role`キーで接続し、**全クエリで明示的に`user_id`フィルタを書くことをデータ分離の主たる担保とする**（`service_role`キーはRLSを完全にバイパスするため）。Supabase側のRLSは保険として有効にしておくが、正しさの根拠はバックエンドのクエリ実装に置く
- **シードデータとの関係**: [[demo-seed-strategy]] の通り、シードは発表用デモアカウントにのみ適用する。審査員自身のアカウントは新規ユーザーとして空の状態から始まる
