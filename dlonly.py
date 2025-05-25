#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import os
from pathlib import Path
import queue
import re
from gfile import GFile

class GigaFileDownloader:
    def __init__(self, root):
        self.root = root
        self.root.title("GigaFile Downloader")
        self.root.geometry("800x600")
        
        # ダウンロードディレクトリ
        self.download_dir = tk.StringVar(value=str(Path.home() / "Downloads"))
        
        # プログレスキュー
        self.progress_queue = queue.Queue()
        
        # アクティブなダウンロード
        self.active_downloads = {}
        
        self.setup_ui()
        self.check_progress()
        
    def setup_ui(self):
        # メインフレーム
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # ディレクトリ選択フレーム
        dir_frame = ttk.LabelFrame(main_frame, text="ダウンロード先", padding="5")
        dir_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Entry(dir_frame, textvariable=self.download_dir, width=60).grid(row=0, column=0, padx=(0, 5))
        ttk.Button(dir_frame, text="参照", command=self.browse_directory).grid(row=0, column=1)
        
        # URL入力フレーム
        url_frame = ttk.LabelFrame(main_frame, text="ダウンロードURL (1行に1つ、パスワード付きは 'URL パスワード' 形式)", padding="5")
        url_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        # URLテキストエリア
        self.url_text = tk.Text(url_frame, height=8, width=70)
        url_scrollbar = ttk.Scrollbar(url_frame, orient="vertical", command=self.url_text.yview)
        self.url_text.configure(yscrollcommand=url_scrollbar.set)
        
        self.url_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        url_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # ボタンフレーム
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=(0, 10))
        
        self.download_button = ttk.Button(button_frame, text="ダウンロード開始", command=self.start_downloads)
        self.download_button.grid(row=0, column=0, padx=(0, 5))
        
        ttk.Button(button_frame, text="クリア", command=self.clear_urls).grid(row=0, column=1, padx=(0, 5))
        ttk.Button(button_frame, text="すべて停止", command=self.stop_all_downloads).grid(row=0, column=2)
        
        # プログレスフレーム
        progress_frame = ttk.LabelFrame(main_frame, text="ダウンロード状況", padding="5")
        progress_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        # プログレステーブル
        columns = ("URL", "ファイル名", "状態", "進行率")
        self.progress_tree = ttk.Treeview(progress_frame, columns=columns, show="headings", height=10)
        
        for col in columns:
            self.progress_tree.heading(col, text=col)
            
        self.progress_tree.column("URL", width=200)
        self.progress_tree.column("ファイル名", width=150)
        self.progress_tree.column("状態", width=100)
        self.progress_tree.column("進行率", width=100)
        
        progress_scrollbar = ttk.Scrollbar(progress_frame, orient="vertical", command=self.progress_tree.yview)
        self.progress_tree.configure(yscrollcommand=progress_scrollbar.set)
        
        self.progress_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        progress_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # ログフレーム
        log_frame = ttk.LabelFrame(main_frame, text="ログ", padding="5")
        log_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.log_text = tk.Text(log_frame, height=6, width=70)
        log_scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scrollbar.set)
        
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # グリッド設定
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(3, weight=1)
        main_frame.rowconfigure(4, weight=1)
        url_frame.columnconfigure(0, weight=1)
        url_frame.rowconfigure(0, weight=1)
        progress_frame.columnconfigure(0, weight=1)
        progress_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
    def browse_directory(self):
        directory = filedialog.askdirectory(initialdir=self.download_dir.get())
        if directory:
            self.download_dir.set(directory)
            
    def clear_urls(self):
        self.url_text.delete(1.0, tk.END)
        
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
            
    def start_single_download(self, url_data, download_dir):
        url, password = url_data
        display_text = f"{url} [PW]" if password else url
        
        # プログレステーブルにエントリ追加
        item_id = self.progress_tree.insert("", "end", values=(display_text, "取得中...", "準備中", "0%"))
        
        # ダウンロードスレッド開始
        thread = threading.Thread(target=self.download_worker, args=(url, password, download_dir, item_id))
        thread.daemon = True
        thread.start()
        
        self.active_downloads[item_id] = thread
        
    def download_worker(self, url, password, download_dir, item_id):
        try:
            display_text = f"{url} [PW]" if password else url
            self.progress_queue.put(("update", item_id, display_text, "接続中...", "開始", "0%"))
            
            # GFileインスタンス作成（パスワードがある場合はkeyパラメータに渡す）
            gfile = GFile(url, progress=False, mute=True, key=password)
            
            self.progress_queue.put(("update", item_id, display_text, "ダウンロード中...", "進行中", "0%"))
            
            # ダウンロード実行
            downloaded_files = gfile.download(odir=download_dir)
            
            if downloaded_files:
                filename = str(downloaded_files[0]) if downloaded_files else "不明"
                self.progress_queue.put(("update", item_id, display_text, filename, "完了", "100%"))
                pw_text = " [パスワード付き]" if password else ""
                self.progress_queue.put(("log", f"ダウンロード完了{pw_text}: {url} -> {filename}"))
            else:
                self.progress_queue.put(("update", item_id, display_text, "エラー", "失敗", "0%"))
                pw_text = " [パスワード付き]" if password else ""
                self.progress_queue.put(("log", f"ダウンロード失敗{pw_text}: {url}"))
                
        except Exception as e:
            display_text = f"{url} [PW]" if password else url
            self.progress_queue.put(("update", item_id, display_text, "エラー", "失敗", "0%"))
            pw_text = " [パスワード付き]" if password else ""
            self.progress_queue.put(("log", f"ダウンロードエラー{pw_text}: {url} - {str(e)}"))
        finally:
            if item_id in self.active_downloads:
                del self.active_downloads[item_id]
            
            # すべてのダウンロードが完了したらボタンを有効化
            if not self.active_downloads:
                self.progress_queue.put(("enable_button",))
                
    def stop_all_downloads(self):
        # 実際の停止処理は困難なため、ログにメッセージを表示
        self.log_message("ダウンロード停止が要求されました。進行中のダウンロードは完了まで継続されます。")
        
    def check_progress(self):
        try:
            while True:
                try:
                    message = self.progress_queue.get_nowait()
                    
                    if message[0] == "update":
                        _, item_id, url, filename, status, progress = message
                        self.progress_tree.item(item_id, values=(url, filename, status, progress))
                        
                    elif message[0] == "log":
                        self.log_message(message[1])
                        
                    elif message[0] == "enable_button":
                        self.download_button.config(state="normal")
                        self.log_message("すべてのダウンロードが完了しました。")
                        
                except queue.Empty:
                    break
                    
        except Exception as e:
            print(f"Progress check error: {e}")
            
        # 100ms後に再チェック
        self.root.after(100, self.check_progress)

def main():
    root = tk.Tk()
    app = GigaFileDownloader(root)
    root.mainloop()

if __name__ == "__main__":
    main()