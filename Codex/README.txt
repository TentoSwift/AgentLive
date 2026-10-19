ClaudeLive 用 Codex カスタムシンボル
作成・整理日: 2026-10-19

SF Symbols Beta の「Codex」コレクションに11種類を登録済みです。
既存の codex-openai と codex-openai.badge.checkmark を残し、
質問・返答・返答完了・サブエージェントのシンボルをアプリの
「コンポーネントと結合」で作成しました。
ツール完了の5種類は、現在のアプリで使っている共通のツール図形を
Codex専用の名前で複製しています。これらにはClaudeのロゴは含みません。

編集用データ
  このフォルダ直下の SVG: ロゴ、状態、返答、サブエージェント（6種類）
  Tools/: ツール完了（5種類）
  いずれもSF Symbolsで読み込み・編集できるカスタムシンボルSVGです。

Xcode用データ
  Codex.xcassets/: 11種類の .symbolset をまとめたアセットカタログ
  symbol-mapping.json: SVG名とアプリ用アセット名の対応表
  アプリ内の Widget/Assets.xcassets にも取り込み済みです。
  Codexセッションではこれらのシンボルと青紫（#7C83FF）のアクセントを使用します。
  Claude Codeセッションでは従来のClaudeシンボルとオレンジを使用します。

アプリ用アセット名と用途
  CodexMark               基本ロゴ・作業中
  CodexBadgeCheckmark     完了
  CodexBadgeQuestionmark  質問待ち
  CodexBubbleReply        返答
  CodexBubbleReplyDone    返答完了
  CodexTaskRunning        サブエージェント実行中
  CodexBashCheckmark      ターミナル実行完了
  CodexReadCheckmark      ファイル読取完了
  CodexEditCheckmark      編集完了
  CodexGrepCheckmark      検索完了
  CodexWebFetchCheckmark  Web取得完了

人型の入力者アイコン、許可待ち、入力待ち、エラー、圧縮中の
共通SF Symbolsは新規作成の対象にしていません。
独自の8コマPNGアニメーションはこの一式には含めていません。
