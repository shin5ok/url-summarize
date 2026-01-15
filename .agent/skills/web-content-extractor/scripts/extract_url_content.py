#!/usr/bin/env python3
"""
Web Content Extractor

Headless ブラウザ（Playwright）を使用して、X.com、note.com などの
動的コンテンツを抽出するスクリプト。
"""

import argparse
import json
import re
import sys
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout


class ContentExtractor:
    """URL からコンテンツを抽出するクラス"""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout * 1000  # milliseconds
        self.playwright = None
        self.browser = None

    def __enter__(self):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def detect_url_type(self, url: str) -> str:
        """URL のタイプを検出する"""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        if 'x.com' in domain or 'twitter.com' in domain:
            return 'x.com'
        elif 'note.com' in domain:
            return 'note.com'
        else:
            return 'generic'

    def extract(self, url: str) -> dict:
        """URL からコンテンツを抽出する"""
        url_type = self.detect_url_type(url)
        
        try:
            if url_type == 'x.com':
                result = self._extract_xcom(url)
            elif url_type == 'note.com':
                result = self._extract_note(url)
            else:
                result = self._extract_generic(url)
            
            result['url'] = url
            result['type'] = url_type
            result['extracted_at'] = datetime.now().isoformat()
            return result
            
        except PlaywrightTimeout:
            return {
                'url': url,
                'type': url_type,
                'error': 'ページの読み込みがタイムアウトしました',
                'extracted_at': datetime.now().isoformat()
            }
        except Exception as e:
            return {
                'url': url,
                'type': url_type,
                'error': str(e),
                'extracted_at': datetime.now().isoformat()
            }

    def _extract_xcom(self, url: str) -> dict:
        """X.com (Twitter) からコンテンツを抽出（ステルスモード強化版）"""
        # X.com のアンチボット対策を回避するための設定
        context = self.browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='ja-JP',
            timezone_id='Asia/Tokyo',
            color_scheme='light',
            # クッキーを有効化
            ignore_https_errors=True,
        )
        page = context.new_page()
        
        # webdriver フラグを隠す
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['ja-JP', 'ja', 'en-US', 'en']
            });
            window.chrome = { runtime: {} };
        """)
        
        tweet_data = {}
        
        def handle_response(response):
            """ネットワークレスポンスをインターセプト"""
            try:
                if 'TweetResultByRestId' in response.url or 'TweetDetail' in response.url:
                    try:
                        json_data = response.json()
                        tweet_data['raw_api'] = json_data
                    except Exception:
                        pass
            except Exception:
                pass
        
        page.on('response', handle_response)
        
        try:
            # networkidle ではなく domcontentloaded を使用（タイムアウト回避）
            page.goto(url, wait_until='domcontentloaded', timeout=self.timeout)
            
            # コンテンツが読み込まれるまで待機
            try:
                page.wait_for_selector('[data-testid="tweetText"]', timeout=10000)
            except PlaywrightTimeout:
                # セレクタが見つからなくても続行
                pass
            
            # 追加の待機時間
            page.wait_for_timeout(2000)
            
            html = page.content()
            soup = BeautifulSoup(html, 'lxml')
            
            # ツイート本文を取得
            content = ''
            tweet_text_elem = soup.find('div', {'data-testid': 'tweetText'})
            if tweet_text_elem:
                content = tweet_text_elem.get_text(strip=True)
            
            # ユーザー名を取得
            author = ''
            user_elem = soup.find('div', {'data-testid': 'User-Name'})
            if user_elem:
                author = user_elem.get_text(strip=True)
            
            # 日時を取得
            timestamp = ''
            time_elem = soup.find('time')
            if time_elem and time_elem.get('datetime'):
                timestamp = time_elem.get('datetime')
            
            # API レスポンスからより詳細な情報を取得
            if 'raw_api' in tweet_data:
                try:
                    api_data = tweet_data['raw_api']
                    # API 構造に応じてデータを抽出（X.com の API は頻繁に変更されるため柔軟に）
                    if isinstance(api_data, dict):
                        data_path = api_data.get('data', {})
                        if 'tweetResult' in data_path:
                            tweet_result = data_path['tweetResult'].get('result', {})
                            legacy = tweet_result.get('legacy', {})
                            if legacy.get('full_text'):
                                content = legacy['full_text']
                except Exception:
                    pass
            
            # コンテンツが取得できなかった場合の警告
            if not content:
                return {
                    'title': 'X.com ポスト',
                    'content': '',
                    'author': author,
                    'timestamp': timestamp,
                    'warning': 'X.com のアンチボット対策により、コンテンツを取得できませんでした。Antigravity の browser_subagent を使用してください。'
                }
            
            return {
                'title': f"{author} のポスト" if author else 'X.com ポスト',
                'content': content,
                'author': author,
                'timestamp': timestamp
            }
            
        finally:
            context.close()

    def _extract_note(self, url: str) -> dict:
        """note.com から記事コンテンツを抽出"""
        context = self.browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()
        
        try:
            page.goto(url, wait_until='networkidle', timeout=self.timeout)
            page.wait_for_timeout(2000)
            
            html = page.content()
            soup = BeautifulSoup(html, 'lxml')
            
            # タイトルを取得
            title = ''
            title_elem = soup.find('h1', class_=re.compile(r'.*title.*', re.I))
            if not title_elem:
                title_elem = soup.find('h1')
            if title_elem:
                title = title_elem.get_text(strip=True)
            
            # 本文を取得
            content = ''
            # note.com の記事本文は通常 article タグまたは特定のクラスにある
            article_elem = soup.find('div', class_=re.compile(r'.*note-body.*|.*article.*', re.I))
            if not article_elem:
                article_elem = soup.find('article')
            if not article_elem:
                # フォールバック: メインコンテンツエリアを探す
                article_elem = soup.find('div', class_=re.compile(r'.*content.*', re.I))
            
            if article_elem:
                # 不要な要素を除去
                for tag in article_elem.find_all(['script', 'style', 'nav', 'footer']):
                    tag.decompose()
                content = article_elem.get_text(separator='\n', strip=True)
            
            # 著者を取得
            author = ''
            author_elem = soup.find('a', class_=re.compile(r'.*creator.*|.*author.*', re.I))
            if not author_elem:
                author_elem = soup.find('div', class_=re.compile(r'.*creator.*|.*author.*', re.I))
            if author_elem:
                author = author_elem.get_text(strip=True)
            
            return {
                'title': title,
                'content': content,
                'author': author,
                'timestamp': ''
            }
            
        finally:
            context.close()

    def _extract_generic(self, url: str) -> dict:
        """汎用的なコンテンツ抽出"""
        context = self.browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()
        
        try:
            page.goto(url, wait_until='networkidle', timeout=self.timeout)
            page.wait_for_timeout(2000)
            
            html = page.content()
            soup = BeautifulSoup(html, 'lxml')
            
            # 不要な要素を除去
            for tag in soup.find_all(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                tag.decompose()
            
            # タイトルを取得
            title = ''
            title_elem = soup.find('h1')
            if not title_elem:
                title_elem = soup.find('title')
            if title_elem:
                title = title_elem.get_text(strip=True)
            
            # メインコンテンツを取得
            content = ''
            main_elem = soup.find('main')
            if not main_elem:
                main_elem = soup.find('article')
            if not main_elem:
                main_elem = soup.find('div', class_=re.compile(r'.*content.*|.*main.*|.*article.*', re.I))
            if not main_elem:
                main_elem = soup.find('body')
            
            if main_elem:
                content = main_elem.get_text(separator='\n', strip=True)
                # 長すぎる場合は切り詰め
                if len(content) > 10000:
                    content = content[:10000] + '...(省略)'
            
            # 著者を取得（メタタグから）
            author = ''
            author_meta = soup.find('meta', attrs={'name': 'author'})
            if author_meta and author_meta.get('content'):
                author = author_meta['content']
            
            return {
                'title': title,
                'content': content,
                'author': author,
                'timestamp': ''
            }
            
        finally:
            context.close()


def format_as_markdown(data: dict) -> str:
    """抽出結果を Markdown 形式でフォーマット"""
    lines = []
    
    if data.get('error'):
        lines.append(f"# エラー\n\n{data['error']}")
        return '\n'.join(lines)
    
    if data.get('title'):
        lines.append(f"# {data['title']}")
    
    lines.append(f"\n**URL**: {data.get('url', '')}")
    lines.append(f"**タイプ**: {data.get('type', '')}")
    
    if data.get('author'):
        lines.append(f"**著者**: {data['author']}")
    
    if data.get('timestamp'):
        lines.append(f"**日時**: {data['timestamp']}")
    
    lines.append(f"\n## コンテンツ\n\n{data.get('content', '')}")
    
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(
        description='Headless ブラウザを使用して URL からコンテンツを抽出'
    )
    parser.add_argument('url', help='抽出対象の URL')
    parser.add_argument(
        '--format', 
        choices=['json', 'markdown'], 
        default='json',
        help='出力形式 (default: json)'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=30,
        help='ページ読み込みタイムアウト（秒）(default: 30)'
    )
    
    args = parser.parse_args()
    
    with ContentExtractor(timeout=args.timeout) as extractor:
        result = extractor.extract(args.url)
    
    if args.format == 'json':
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(format_as_markdown(result))


if __name__ == '__main__':
    main()
