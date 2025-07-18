# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

### 作業時の注意
- 必ず日本語で出力すること。

## プロジェクト概要

GigaFile便のアップロード・ダウンロード管理を行うPython GUI アプリケーション。TkinterベースのデスクトップアプリケーションでPyInstallerで実行可能ファイルを生成。

### Git規約
- **ブランチ命名**: [feature/fix/hotfix]/[issue-number]-[description]
- **コミットメッセージ**: [feat/fix/docs/style/refactor]: 変更内容の簡潔な説明
- **PR**: テンプレートに従って詳細な説明を記載

## 開発コマンド

### アプリケーション実行
```bash
python3 gigafiledl.py
```

### ダウンロード専用版実行
```bash
python3 dlonly.py
```

### ビルド (macOS)
```bash
./build.sh
```

### 依存関係インストール
```bash
pip3 install -r requirements.txt
```

## アーキテクチャ

### メインファイル構成
- `gigafiledl.py`: メインアプリケーション（1,195行）
  - `GFile`クラス: GigaFile便API クライアント（埋め込み）
  - `GigaFileManager`クラス: Tkinter GUI メインクラス
- `dlonly.py`: ダウンロード専用簡易版(このファイルは無視すること)
- `GigaFile Manager.spec`: PyInstaller設定ファイル

### スレッド設計
- メインスレッド: GUI（Tkinter）
- ワーカースレッド: ダウンロード・アップロード処理
- Queueを使用した進行状況の通信

### 主要機能
- **ダウンロード**: 複数URL一括、パスワード対応、自動解凍（ZIP/7z/tar/gz）
- **アップロード**: 複数ファイル自動ZIP化、進行状況表示
- **クロスプラットフォーム**: Windows/macOS/Linux対応

## ビルド設定

### PyInstaller設定
- `--onefile`: 単一実行可能ファイル
- 大量のモジュール除外設定でサイズ最適化
- プラットフォーム固有の設定あり

### GitHub Actions
- マトリックスビルド: Windows/macOS(Intel/ARM)/Linux
- リリース自動作成機能
- アーティファクト自動アップロード

## 重要な考慮事項

### 依存関係
- Python 3.11+ 必須
- macOSでは`unar`コマンド必要: `brew install unar`
- 解凍機能にはシステムコマンド依存

### 一時ファイル処理
- 環境に応じたtemp ディレクトリ選択
- PyInstaller frozen 状態を考慮した処理
- アップロード後の自動ZIP削除

### エラーハンドリング
- 包括的なtry-catch ブロック
- ユーザーフレンドリーなエラー表示
- ネットワークエラー対応

## コード特徴

- 単一ファイルアプリケーション設計
- 日本語UI・ドキュメント
- AI生成コードベース（README記載）
- イベント駆動GUI（定期的進行状況チェック）