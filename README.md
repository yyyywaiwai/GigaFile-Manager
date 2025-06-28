# GigaFile Manager

GigaFile Manager は、GigaFile便の操作を簡単にするデスクトップアプリケーションです。ファイルのアップロードとダウンロードを直感的なGUIインターフェースで管理できます。また、CLI版も提供されており、スクリプトや自動化にも対応しています。
99%AI製なのでコードがクッソ汚いです。

## 特徴

### 📥 ダウンロード機能
- **複数URL対応**: 複数のGigaFileのURLを一括でダウンロード
- **パスワード対応**: パスワード付きファイルにも対応（`URL パスワード`形式で入力）
- **自動展開**: ZIP、7z、tar、gzファイルの自動展開
- **進捗表示**: リアルタイムでダウンロード進捗を表示
- **速度表示**: ダウンロード速度とETA（残り時間）を表示
- **フォルダ分け**: ファイルIDごとにフォルダを作成して整理

### 📤 アップロード機能
- **自動ZIP化**: 複数ファイル選択時に自動でZIP圧縮
- **バッチアップロード**: 複数ファイルの一括アップロード

### 🔧 その他の機能
- **処理状況表示**: すべての操作の進捗をリアルタイム表示
- **URL管理**: アップロード完了URLの一括コピー機能
- **クロスプラットフォーム**: Windows、macOS、Linuxで動作

## インストール

### 事前ビルド版のダウンロード（推奨）

[Releases](https://github.com/yyyywaiwai/GigaFile-Manager/releases)から最新版をダウンロードしてください。

#### GUI版（デスクトップアプリケーション）
- **Windows**: `gigafile-manager-windows-x64.zip`
- **macOS (Apple Silicon)**: `gigafile-manager-macos-arm64.zip`
- **macOS (Intel)**: `gigafile-manager-macos-intel.zip`
- **Linux**: `gigafile-manager-linux-x64.tar.gz`

#### CLI版（コマンドライン）
**ポータブル版（単一ファイル）**:
- **Windows**: `gigafile-portable-windows-x64.exe`
- **macOS (Apple Silicon)**: `gigafile-portable-macos-arm64`
- **macOS (Intel)**: `gigafile-portable-macos-intel`
- **Linux**: `gigafile-portable-linux-x64`

**高速起動版（フォルダ）**:
- **Windows**: `gigafile-cli-windows-x64.zip`
- **macOS (Apple Silicon)**: `gigafile-cli-macos-arm64.zip`
- **macOS (Intel)**: `gigafile-cli-macos-intel.zip`
- **Linux**: `gigafile-cli-linux-x64.tar.gz`

### ソースからのビルド

#### 必要な環境
- Python 3.11以上
- pip

#### 手順

1. リポジトリをクローン
```bash
git clone https://github.com/yyyywaiwai/GigaFile-Manager.git
cd GigaFile-Manager
```

2. 依存関係をインストール
```bash
pip install -r requirements.txt
```

3. アプリケーションを実行
```bash
python gigafiledl.py
```

#### スタンドアロン実行ファイルの作成

**GUI版**:
```bash
# macOS/Linux
./build.sh

# Windows
pyinstaller --windowed --name="GigaFile Manager" --onedir --icon=icon.ico gigafiledl.py
```

**CLI版**:
```bash
# macOS/Linux
./build-cli.sh

# Windows（PowerShell）
pyinstaller --onefile --name="gigafile-portable" --console --strip gigafilecli.py
pyinstaller --onedir --name="gigafile" --console --strip --optimize=2 gigafilecli.py
```

## 使用方法

### GUI版（デスクトップアプリケーション）

#### ダウンロード

1. **ダウンロード先の設定**: 「参照」ボタンでダウンロード先フォルダを選択
2. **URLの入力**: テキストエリアにGigaFileのURLを1行に1つずつ入力
   - 通常: `https://xx.gigafile.nu/xxxxxxxx`
   - パスワード付き: `https://xx.gigafile.nu/xxxxxxxx password123`
3. **ダウンロード開始**: 「ダウンロード開始」ボタンをクリック

#### アップロード

1. **ファイルの追加**: 
   - 「ファイル追加」: 個別ファイルを選択
   - 「フォルダ追加」: フォルダ内のすべてのファイルを追加
2. **設定の確認**: 複数ファイル時の自動ZIP化の設定を確認
3. **アップロード開始**: 「アップロード開始」ボタンをクリック

#### URL管理

- **個別コピー**: 処理状況テーブルの完了したアップロードをダブルクリック
- **選択コピー**: 複数選択して「選択した完了URLをコピー」
- **一括コピー**: 「すべての完了URLをコピー」ですべてのURLを取得

### CLI版（コマンドライン）

#### 基本的な使用方法

```bash
# ヘルプの表示
gigafile --help

# サブコマンドのヘルプ
gigafile download --help
gigafile upload --help
```

#### ダウンロード

```bash
# 単一ファイルのダウンロード
gigafile download https://xx.gigafile.nu/xxxxxxxx

# パスワード付きファイルのダウンロード
gigafile download https://xx.gigafile.nu/xxxxxxxx --password mypassword
# または
gigafile download "https://xx.gigafile.nu/xxxxxxxx mypassword"

# 出力ディレクトリを指定
gigafile download https://xx.gigafile.nu/xxxxxxxx --output-dir ./downloads

# URLリストファイルからダウンロード
gigafile download --file urls.txt --output-dir ./downloads
```

**URLリストファイルの例（urls.txt）**:
```
https://xx.gigafile.nu/xxxxxxxx
https://xx.gigafile.nu/yyyyyyyy password123
# コメント行は無視されます
https://xx.gigafile.nu/zzzzzzzz
```

#### アップロード

```bash
# 単一ファイルのアップロード
gigafile upload file.txt

# 複数ファイルのアップロード（自動ZIP化）
gigafile upload file1.txt file2.txt --auto-zip

# ディレクトリ内のファイルをアップロード
gigafile upload --directory ./photos --pattern "*.jpg" --auto-zip

# Globパターンでファイル選択
gigafile upload "*.pdf" "docs/*.txt" --auto-zip

# アップロードスレッド数を指定
gigafile upload file.txt --threads 8
```

#### 主要オプション

**ダウンロード**:
- `--output-dir, -o`: 出力ディレクトリ（デフォルト: `./GFM-downloads`）
- `--file, -f`: URLリストファイル
- `--password, -p`: パスワード

**アップロード**:
- `--directory, -d`: アップロードするディレクトリ
- `--pattern`: ファイルパターン（デフォルト: `*`）
- `--auto-zip`: 複数ファイル時に自動ZIP化
- `--threads, -t`: アップロードスレッド数（デフォルト: 4）

## 設定

### 対応ファイル形式

**ダウンロード時の自動展開**:
- ZIP (.zip)
- 7-Zip (.7z)
- Gzip (.gz)
- Tar (.tar)

**アップロード時の自動圧縮**:
- 複数ファイル選択時にZIP形式で自動圧縮

## トラブルシューティング

### よくある問題

**Q: ダウンロードが失敗する**
- URLが正しいGigaFile便のURLかを確認
- パスワード付きファイルの場合、パスワードが正しいかを確認
- インターネット接続を確認

**Q: 自動展開されない**
- `unar`コマンドがシステムにインストールされているかを確認
- macOSの場合: `brew install unar`

## クレジット
- GigaFile便のダウンロード/アップロード処理: [gfile by fireattack](https://github.com/fireattack/gfile)

**注意**: このツールはGigaFile便の非公式クライアントです。GigaFile便の利用規約を遵守してご利用ください。
