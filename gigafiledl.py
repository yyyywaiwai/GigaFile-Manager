#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import os
import sys
from pathlib import Path
import queue
import re
import zipfile
import tempfile
from datetime import datetime
from gfile import GFile

class GigaFileManager:
    def __init__(self, root):
        self.root = root
        self.root.title("GigaFile Manager")
        self.root.geometry("1100x900")
        self.root.minsize(1000, 850)
        
        # ディレクトリ設定
        self.download_dir = tk.StringVar(value=str(Path.home() / "Downloads"))
        self.upload_dir = tk.StringVar(value=str(Path.home()))
        
        # プログレスキュー
        self.progress_queue = queue.Queue()
        
        # アクティブな処理
        self.active_downloads = {}
        self.active_uploads = {}
        
        # モード管理
        self.current_mode = tk.StringVar(value="download")
        
        self.setup_ui()
        self.check_progress()
        
    def setup_ui(self):
        # メインフレーム
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # モード選択フレーム
        mode_frame = ttk.LabelFrame(main_frame, text="モード選択", padding="5")
        mode_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Radiobutton(mode_frame, text="ダウンロード", variable=self.current_mode, 
                       value="download", command=self.switch_mode).grid(row=0, column=0, padx=(0, 20))
        ttk.Radiobutton(mode_frame, text="アップロード", variable=self.current_mode, 
                       value="upload", command=self.switch_mode).grid(row=0, column=1)
        
        # ダウンロードフレーム
        self.download_frame = ttk.Frame(main_frame)
        self.download_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # アップロードフレーム
        self.upload_frame = ttk.Frame(main_frame)
        self.upload_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.setup_download_ui()
        self.setup_upload_ui()
        self.setup_common_ui()
        
        # 初期モード設定
        self.switch_mode()
        
    def setup_download_ui(self):
        # ダウンロード先ディレクトリ選択
        dl_dir_frame = ttk.LabelFrame(self.download_frame, text="ダウンロード先", padding="5")
        dl_dir_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Entry(dl_dir_frame, textvariable=self.download_dir, width=60).grid(row=0, column=0, padx=(0, 5))
        ttk.Button(dl_dir_frame, text="参照", command=self.browse_download_directory).grid(row=0, column=1)
        
        # URL入力フレーム
        url_frame = ttk.LabelFrame(self.download_frame, text="ダウンロードURL (1行に1つ、パスワード付きは 'URL パスワード' 形式)", padding="5")
        url_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        # URLテキストエリア
        self.url_text = tk.Text(url_frame, height=10)
        url_scrollbar = ttk.Scrollbar(url_frame, orient="vertical", command=self.url_text.yview)
        self.url_text.configure(yscrollcommand=url_scrollbar.set)
        
        self.url_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        url_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # ダウンロードボタンフレーム
        dl_button_frame = ttk.Frame(self.download_frame)
        dl_button_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 10))
        
        self.download_button = ttk.Button(dl_button_frame, text="ダウンロード開始", command=self.start_downloads)
        self.download_button.grid(row=0, column=0, padx=(0, 5))
        
        ttk.Button(dl_button_frame, text="クリア", command=self.clear_urls).grid(row=0, column=1, padx=(0, 5))
        ttk.Button(dl_button_frame, text="すべて停止", command=self.stop_all_downloads).grid(row=0, column=2)
        
        # グリッド設定
        self.download_frame.columnconfigure(0, weight=1)
        self.download_frame.rowconfigure(1, weight=1)
        self.download_frame.rowconfigure(2, weight=0)  # ボタンフレームは固定サイズ
        dl_dir_frame.columnconfigure(0, weight=1)
        url_frame.columnconfigure(0, weight=1)
        url_frame.rowconfigure(0, weight=1)
        
    def setup_upload_ui(self):
        # アップロード元ディレクトリ選択
        ul_dir_frame = ttk.LabelFrame(self.upload_frame, text="アップロード元", padding="5")
        ul_dir_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Entry(ul_dir_frame, textvariable=self.upload_dir, width=60).grid(row=0, column=0, padx=(0, 5))
        ttk.Button(ul_dir_frame, text="参照", command=self.browse_upload_directory).grid(row=0, column=1)
        
        # ファイル選択フレーム
        file_frame = ttk.LabelFrame(self.upload_frame, text="アップロードファイル", padding="5")
        file_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 5))
        
        # ファイルリスト
        file_list_frame = ttk.Frame(file_frame)
        file_list_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        self.file_listbox = tk.Listbox(file_list_frame, height=10, selectmode=tk.EXTENDED)
        file_scrollbar = ttk.Scrollbar(file_list_frame, orient="vertical", command=self.file_listbox.yview)
        self.file_listbox.configure(yscrollcommand=file_scrollbar.set)
        
        self.file_listbox.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        file_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # ファイル選択ボタン
        file_button_frame = ttk.Frame(file_frame)
        file_button_frame.grid(row=1, column=0, columnspan=3, pady=(0, 10))
        
        ttk.Button(file_button_frame, text="ファイル追加", command=self.add_files).grid(row=0, column=0, padx=(0, 5))
        ttk.Button(file_button_frame, text="フォルダ追加", command=self.add_folder).grid(row=0, column=1, padx=(0, 5))
        ttk.Button(file_button_frame, text="選択削除", command=self.remove_selected_files).grid(row=0, column=2, padx=(0, 5))
        ttk.Button(file_button_frame, text="すべて削除", command=self.clear_files).grid(row=0, column=3)
        
        # アップロード設定フレーム
        upload_settings_frame = ttk.LabelFrame(self.upload_frame, text="アップロード設定", padding="5")
        upload_settings_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # ZIP化設定
        self.auto_zip = tk.BooleanVar(value=True)
        ttk.Checkbutton(upload_settings_frame, text="複数ファイル時に自動ZIP化", variable=self.auto_zip).grid(row=0, column=0, sticky=tk.W)
        
        # アップロードボタンフレーム
        ul_button_frame = ttk.Frame(self.upload_frame)
        ul_button_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 10))
        
        self.upload_button = ttk.Button(ul_button_frame, text="アップロード開始", command=self.start_uploads)
        self.upload_button.grid(row=0, column=0, padx=(0, 5))
        
        ttk.Button(ul_button_frame, text="すべて停止", command=self.stop_all_uploads).grid(row=0, column=1)
        
        # グリッド設定
        self.upload_frame.columnconfigure(0, weight=1)
        self.upload_frame.rowconfigure(1, weight=1)
        self.upload_frame.rowconfigure(2, weight=0)  # 設定フレームは固定サイズ
        self.upload_frame.rowconfigure(3, weight=0)  # ボタンフレームは固定サイズ
        ul_dir_frame.columnconfigure(0, weight=1)
        file_frame.columnconfigure(0, weight=1)
        file_frame.rowconfigure(0, weight=1)
        file_list_frame.columnconfigure(0, weight=1)
        file_list_frame.rowconfigure(0, weight=1)
        upload_settings_frame.columnconfigure(0, weight=1)
        
    def setup_common_ui(self):
        # 共通フレーム（プログレスとログ）
        common_frame = ttk.Frame(self.root)
        common_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=(0, 10))
        
        # プログレスフレーム
        progress_frame = ttk.LabelFrame(common_frame, text="処理状況", padding="5")
        progress_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        # プログレステーブル
        columns = ("種別", "ファイル/URL", "状態", "進行率", "操作")
        self.progress_tree = ttk.Treeview(progress_frame, columns=columns, show="headings", height=10)
        
        for col in columns:
            self.progress_tree.heading(col, text=col)
            
        self.progress_tree.column("種別", width=100)
        self.progress_tree.column("ファイル/URL", width=400)
        self.progress_tree.column("状態", width=100)
        self.progress_tree.column("進行率", width=100)
        self.progress_tree.column("操作", width=80)
        
        progress_scrollbar = ttk.Scrollbar(progress_frame, orient="vertical", command=self.progress_tree.yview)
        self.progress_tree.configure(yscrollcommand=progress_scrollbar.set)
        
        self.progress_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        progress_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # プログレステーブルイベント
        self.progress_tree.bind("<Double-1>", self.on_tree_double_click)
        
        # コピーボタンフレーム
        copy_button_frame = ttk.Frame(progress_frame)
        copy_button_frame.grid(row=1, column=0, columnspan=2, pady=(5, 0))
        
        ttk.Button(copy_button_frame, text="選択した完了URLをコピー", command=self.copy_selected_url).grid(row=0, column=0, padx=(0, 10))
        ttk.Button(copy_button_frame, text="すべての完了URLをコピー", command=self.copy_all_urls).grid(row=0, column=1)
        
        # ログフレーム
        log_frame = ttk.LabelFrame(common_frame, text="ログ", padding="5")
        log_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.log_text = tk.Text(log_frame, height=6)
        log_scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scrollbar.set)
        
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # 共通フレームのグリッド設定
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=2)  # メインフレームを大きく
        self.root.rowconfigure(1, weight=1)  # 共通フレームを小さく
        common_frame.columnconfigure(0, weight=1)
        common_frame.rowconfigure(0, weight=1)
        common_frame.rowconfigure(1, weight=1)
        progress_frame.columnconfigure(0, weight=1)
        progress_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
    def switch_mode(self):
        if self.current_mode.get() == "download":
            self.download_frame.grid()
            self.upload_frame.grid_remove()
        else:
            self.download_frame.grid_remove()
            self.upload_frame.grid()
            
    def browse_download_directory(self):
        directory = filedialog.askdirectory(initialdir=self.download_dir.get())
        if directory:
            self.download_dir.set(directory)
            
    def browse_upload_directory(self):
        directory = filedialog.askdirectory(initialdir=self.upload_dir.get())
        if directory:
            self.upload_dir.set(directory)
            
    def clear_urls(self):
        self.url_text.delete(1.0, tk.END)
        
    def add_files(self):
        files = filedialog.askopenfilenames(
            initialdir=self.upload_dir.get(),
            title="アップロードするファイルを選択"
        )
        for file in files:
            if file not in self.file_listbox.get(0, tk.END):
                self.file_listbox.insert(tk.END, file)
                
    def add_folder(self):
        folder = filedialog.askdirectory(
            initialdir=self.upload_dir.get(),
            title="アップロードするフォルダを選択"
        )
        if folder:
            for root, _, files in os.walk(folder):
                for file in files:
                    file_path = os.path.join(root, file)
                    if file_path not in self.file_listbox.get(0, tk.END):
                        self.file_listbox.insert(tk.END, file_path)
                        
    def remove_selected_files(self):
        selected = self.file_listbox.curselection()
        for i in reversed(selected):
            self.file_listbox.delete(i)
            
    def clear_files(self):
        self.file_listbox.delete(0, tk.END)
        
    def on_tree_double_click(self, _):
        item = self.progress_tree.selection()[0] if self.progress_tree.selection() else None
        if item:
            values = self.progress_tree.item(item, "values")
            if len(values) >= 4 and values[2] == "完了" and values[0] == "アップロード":
                url = values[1]
                if url.startswith("http"):
                    self.copy_to_clipboard(url)
                    self.log_message(f"URLをコピーしました: {url}")
                    
    def copy_selected_url(self):
        selected = self.progress_tree.selection()
        if not selected:
            messagebox.showinfo("情報", "コピーする項目を選択してください。")
            return
            
        urls = []
        for item in selected:
            values = self.progress_tree.item(item, "values")
            if len(values) >= 4 and values[2] == "完了" and values[0] == "アップロード":
                url = values[1]
                if url.startswith("http"):
                    urls.append(url)
                    
        if urls:
            url_text = "\n".join(urls)
            self.copy_to_clipboard(url_text)
            self.log_message(f"{len(urls)}個のURLをコピーしました")
        else:
            messagebox.showinfo("情報", "コピー可能な完了URLが選択されていません。")
            
    def copy_all_urls(self):
        urls = []
        for item in self.progress_tree.get_children():
            values = self.progress_tree.item(item, "values")
            if len(values) >= 4 and values[2] == "完了" and values[0] == "アップロード":
                url = values[1]
                if url.startswith("http"):
                    urls.append(url)
                    
        if urls:
            url_text = "\n".join(urls)
            self.copy_to_clipboard(url_text)
            self.log_message(f"{len(urls)}個のURLをコピーしました")
        else:
            messagebox.showinfo("情報", "コピー可能な完了URLがありません。")
            
    def copy_to_clipboard(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()
        
    def get_urls(self):
        content = self.url_text.get(1.0, tk.END).strip()
        if not content:
            return []
        
        url_data = []
        for line in content.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            # URL パスワード 形式かチェック
            parts = line.split()
            if len(parts) >= 2:
                url = parts[0]
                password = parts[1]
                if self.is_valid_gigafile_url(url):
                    url_data.append((url, password))
            elif len(parts) == 1:
                url = parts[0]
                if self.is_valid_gigafile_url(url):
                    url_data.append((url, None))
        return url_data
        
    def is_valid_gigafile_url(self, url):
        pattern = r'^https?:\/\/\d+?\.gigafile\.nu\/[a-z0-9-]+$'
        return re.match(pattern, url) is not None
        
    def log_message(self, message):
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        
    def start_downloads(self):
        urls = self.get_urls()
        
        if not urls:
            messagebox.showwarning("警告", "有効なGigaFileのURLが入力されていません。")
            return
            
        download_dir = self.download_dir.get()
        if not os.path.exists(download_dir):
            try:
                os.makedirs(download_dir)
            except Exception as e:
                messagebox.showerror("エラー", f"ダウンロードディレクトリを作成できません: {e}")
                return
                
        self.download_button.config(state="disabled")
        self.log_message(f"{len(urls)}個のURLのダウンロードを開始します...")
        
        for url_data in urls:
            self.start_single_download(url_data, download_dir)
            
    def start_uploads(self):
        files = list(self.file_listbox.get(0, tk.END))
        
        if not files:
            messagebox.showwarning("警告", "アップロードするファイルが選択されていません。")
            return
            
        # ファイルの存在確認
        valid_files = []
        for file_path in files:
            if os.path.exists(file_path):
                valid_files.append(file_path)
            else:
                self.log_message(f"ファイルが見つかりません: {file_path}")
                
        if not valid_files:
            messagebox.showerror("エラー", "有効なファイルがありません。")
            return
                
        self.upload_button.config(state="disabled")
        
        # 複数ファイルかつZIP化オプションが有効な場合
        if len(valid_files) > 1 and self.auto_zip.get():
            self.log_message(f"{len(valid_files)}個のファイルをZIP化してアップロードします...")
            zip_file_path = self.create_zip_file(valid_files)
            if zip_file_path:
                self.start_single_upload(zip_file_path, is_temp_file=True)
            else:
                self.upload_button.config(state="normal")
        else:
            self.log_message(f"{len(valid_files)}個のファイルのアップロードを開始します...")
            for file_path in valid_files:
                self.start_single_upload(file_path)
            
    def start_single_download(self, url_data, download_dir):
        url, password = url_data
        display_text = f"{url} [PW]" if password else url
        
        # プログレステーブルにエントリ追加
        item_id = self.progress_tree.insert("", "end", values=("ダウンロード", display_text, "準備中", "0%", ""))
        
        # ダウンロードスレッド開始
        thread = threading.Thread(target=self.download_worker, args=(url, password, download_dir, item_id))
        thread.daemon = True
        thread.start()
        
        self.active_downloads[item_id] = thread
        
    def create_zip_file(self, file_paths):
        try:
            # 一時ファイルを作成（アプリバンドル内では書き込み可能なディレクトリを使用）
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            zip_filename = f"files_{timestamp}.zip"
            
            # 書き込み可能なディレクトリを取得
            if getattr(sys, 'frozen', False):
                # アプリバンドル環境の場合
                temp_dir = tempfile.gettempdir()
            else:
                # 通常の実行環境
                temp_dir = tempfile.gettempdir()
            
            zip_path = os.path.join(temp_dir, zip_filename)
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_path in file_paths:
                    if os.path.isfile(file_path):
                        # ファイル名のみをアーカイブ内のパスとして使用
                        arcname = os.path.basename(file_path)
                        zipf.write(file_path, arcname)
                        
            self.log_message(f"ZIP化完了: {zip_filename}")
            return zip_path
            
        except Exception as e:
            self.log_message(f"ZIP化エラー: {str(e)}")
            messagebox.showerror("エラー", f"ZIP化に失敗しました: {str(e)}")
            return None
            
    def start_single_upload(self, file_path, is_temp_file=False):
        filename = os.path.basename(file_path)
        
        # プログレステーブルにエントリ追加
        item_id = self.progress_tree.insert("", "end", values=("アップロード", filename, "準備中", "0%", ""))
        
        # アップロードスレッド開始
        thread = threading.Thread(target=self.upload_worker, args=(file_path, item_id, is_temp_file))
        thread.daemon = True
        thread.start()
        
        self.active_uploads[item_id] = thread
        
    def download_worker(self, url, password, download_dir, item_id):
        try:
            display_text = f"{url} [PW]" if password else url
            self.progress_queue.put(("update", item_id, "ダウンロード", display_text, "開始", "0%", ""))
            
            # URLからファイルIDを抽出
            file_id_match = re.search(r'^https?:\/\/\d+?\.gigafile\.nu\/([a-z0-9-]+)$', url)
            if not file_id_match:
                self.progress_queue.put(("update", item_id, "ダウンロード", "エラー", "失敗", "0%", ""))
                self.progress_queue.put(("log", f"無効なURL形式: {url}"))
                return
            
            file_id = file_id_match.group(1)
            
            # ファイルIDごとのディレクトリを作成
            file_id_dir = os.path.join(download_dir, file_id)
            os.makedirs(file_id_dir, exist_ok=True)
            
            # GFileインスタンス作成（パスワードがある場合はkeyパラメータに渡す）
            gfile = GFile(url, progress=False, mute=True, key=password)
            
            self.progress_queue.put(("update", item_id, "ダウンロード", display_text, "進行中", "0%", ""))
            
            # ファイルIDディレクトリにダウンロード実行
            downloaded_files = gfile.download(odir=file_id_dir)
            
            if downloaded_files:
                filename = str(downloaded_files[0]) if downloaded_files else "不明"
                self.progress_queue.put(("update", item_id, "ダウンロード", filename, "完了", "100%", ""))
                pw_text = " [パスワード付き]" if password else ""
                self.progress_queue.put(("log", f"ダウンロード完了{pw_text}: {url} -> {filename} (フォルダ: {file_id})"))
            else:
                self.progress_queue.put(("update", item_id, "ダウンロード", "エラー", "失敗", "0%", ""))
                pw_text = " [パスワード付き]" if password else ""
                self.progress_queue.put(("log", f"ダウンロード失敗{pw_text}: {url}"))
                
        except Exception as e:
            display_text = f"{url} [PW]" if password else url
            self.progress_queue.put(("update", item_id, "ダウンロード", "エラー", "失敗", "0%", ""))
            pw_text = " [パスワード付き]" if password else ""
            self.progress_queue.put(("log", f"ダウンロードエラー{pw_text}: {url} - {str(e)}"))
        finally:
            if item_id in self.active_downloads:
                del self.active_downloads[item_id]
            
            # すべてのダウンロードが完了したらボタンを有効化
            if not self.active_downloads:
                self.progress_queue.put(("enable_download_button",))
                
    def upload_worker(self, file_path, item_id, is_temp_file=False):
        try:
            filename = os.path.basename(file_path)
            
            self.progress_queue.put(("update", item_id, "アップロード", filename, "開始", "0%", ""))
            
            # GFileインスタンス作成（アップロード用）
            gfile = GFile(file_path, progress=False, mute=True)
            
            self.progress_queue.put(("update", item_id, "アップロード", filename, "進行中", "50%", ""))
            
            # アップロード実行
            result = gfile.upload()
            
            if result and hasattr(result, 'data') and result.data:
                url = result.get_download_page()
                if url:
                    self.progress_queue.put(("update", item_id, "アップロード", url, "完了", "100%", "コピー"))
                    self.progress_queue.put(("log", f"アップロード完了: {filename} -> {url}"))
                else:
                    self.progress_queue.put(("update", item_id, "アップロード", "エラー", "失敗", "0%", ""))
                    self.progress_queue.put(("log", f"アップロード失敗: {filename} (URLの取得に失敗)"))
            else:
                self.progress_queue.put(("update", item_id, "アップロード", "エラー", "失敗", "0%", ""))
                self.progress_queue.put(("log", f"アップロード失敗: {filename}"))
                
        except Exception as e:
            filename = os.path.basename(file_path)
            self.progress_queue.put(("update", item_id, "アップロード", "エラー", "失敗", "0%", ""))
            self.progress_queue.put(("log", f"アップロードエラー: {filename} - {str(e)}"))
        finally:
            # 一時ファイルの場合は削除
            if is_temp_file and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    self.progress_queue.put(("log", f"一時ファイルを削除: {filename}"))
                except Exception as e:
                    self.progress_queue.put(("log", f"一時ファイル削除エラー: {filename} - {str(e)}"))
                    
            if item_id in self.active_uploads:
                del self.active_uploads[item_id]
            
            # すべてのアップロードが完了したらボタンを有効化
            if not self.active_uploads:
                self.progress_queue.put(("enable_upload_button",))
                
    def stop_all_downloads(self):
        # 実際の停止処理は困難なため、ログにメッセージを表示
        self.log_message("ダウンロード停止が要求されました。進行中のダウンロードは完了まで継続されます。")
        
    def stop_all_uploads(self):
        # 実際の停止処理は困難なため、ログにメッセージを表示
        self.log_message("アップロード停止が要求されました。進行中のアップロードは完了まで継続されます。")
        
    def check_progress(self):
        try:
            while True:
                try:
                    message = self.progress_queue.get_nowait()
                    
                    if message[0] == "update":
                        _, item_id, type_text, filename, status, progress, action = message
                        self.progress_tree.item(item_id, values=(type_text, filename, status, progress, action))
                        
                    elif message[0] == "log":
                        self.log_message(message[1])
                        
                    elif message[0] == "enable_download_button":
                        self.download_button.config(state="normal")
                        self.log_message("すべてのダウンロードが完了しました。")
                        
                    elif message[0] == "enable_upload_button":
                        self.upload_button.config(state="normal")
                        self.log_message("すべてのアップロードが完了しました。")
                        
                except queue.Empty:
                    break
                    
        except Exception as e:
            print(f"Progress check error: {e}")
            
        # 100ms後に再チェック
        self.root.after(100, self.check_progress)

def main():
    root = tk.Tk()
    GigaFileManager(root)
    root.mainloop()

if __name__ == "__main__":
    main()
