---
name: Web Content Summarizer
description: Headless ブラウザを使用して X.com や note.com などの動的 Web ページからコンテンツを抽出し、要約するスキル
---

# Web Content Extractor

Headless ブラウザ（Playwright）を使用して、JavaScript で動的に生成されるコンテンツを含む Web ページからテキストを抽出して、Gemini で要約するスキルです。

## 対応サイト

- **X.com (Twitter)**: ポスト/ツイートの本文、ユーザー名、日時を抽出
- **note.com**: 記事のタイトル、本文、著者を抽出
- **その他 URL**: 汎用的なメインコンテンツ抽出

## セットアップ

スクリプトを使用する前に、仮想環境と依存関係をセットアップしてください:

```bash
cd /Users/kawanos/repos/url-summarize/.agent/skills/web-content-extractor
python3 -m venv venv
./venv/bin/pip install --index-url https://pypi.org/simple/ playwright beautifulsoup4 lxml
./venv/bin/playwright install chromium
```

## 使用方法

### 1. コンテンツ抽出

```bash
/Users/kawanos/repos/url-summarize/.agent/skills/web-content-extractor/venv/bin/python /Users/kawanos/repos/url-summarize/.agent/skills/web-content-extractor/scripts/extract_url_content.py "<URL>"
```

**出力例 (JSON)**:
```json
{
  "url": "https://x.com/user/status/123456789",
  "type": "x.com",
  "title": "ユーザー名のポスト",
  "content": "ツイートの本文がここに...",
  "author": "@username",
  "timestamp": "2025-01-15T12:00:00Z",
  "extracted_at": "2025-01-15T17:00:00+09:00"
}
```

**オプション引数**:
- `--format markdown`: Markdown 形式で出力
- `--timeout <秒>`: ページ読み込みタイムアウト（デフォルト: 30秒）

### 2. 要約の生成

抽出したコンテンツを要約するには、エージェントの LLM 機能を使用してください:

```
抽出結果:
{抽出した JSON または Markdown}

上記のコンテンツを日本語で要約してください。
```

## エージェント向け使用手順

1. ユーザーから URL と共に要約リクエストを受け取る
2. `extract_url_content.py` スクリプトを実行してコンテンツを抽出
3. 抽出されたコンテンツを確認
4. LLM の機能を使用して要約を生成
5. 要約結果をユーザーに提示

## 注意事項

> [!WARNING]
> X.com はアンチボット対策が厳しいため、一部のポストでは取得に失敗する可能性があります。
> その場合はエラーメッセージを確認し、手動でのアクセスを試してください。

> [!NOTE]
> ログインが必要なコンテンツは取得できません。公開されているポストや記事のみが対象です。
