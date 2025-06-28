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

# GFile module integrated
import concurrent.futures
import functools
import io
import math
import time
import uuid
from os import rename
from subprocess import run
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from requests_toolbelt import MultipartEncoder, StreamingIterator
from tqdm import tqdm
from urllib3.util.retry import Retry
import subprocess


def requests_retry_session(
    retries=5,
    backoff_factor=0.2,
    status_forcelist=None, # (500, 502, 504)
    session=None,
):
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session


def size_str_to_bytes(size_str):
    if isinstance(size_str, int):
        return size_str
    m = re.search(r'^(?P<num>\d+) ?((?P<unit>[KMGTPEZY]?)(iB|B)?)$', size_str, re.IGNORECASE)
    assert m
    units = ("B", "K", "M", "G", "T", "P", "E", "Z", "Y")
    unit = (m['unit'] or 'B').upper()
    return int(math.pow(1024, units.index(unit)) * int(m['num']))


def split_file(input_file, out, target_size=None, start=0, chunk_copy_size=1024*1024):
    input_file = Path(input_file)
    size = 0

    input_size = input_file.stat().st_size
    if target_size is None:
        output_size = input_size - start
    else:
        output_size = min( target_size, input_size - start)

    with open(input_file, 'rb') as f:
        f.seek(start)
        while True:
            if size == output_size: break
            if size > output_size:
                raise Exception(f'Size ({size}) is larger than {target_size} bytes!')
            current_chunk_size = min(chunk_copy_size, output_size - size)
            chunk = f.read(current_chunk_size)
            if not chunk: break
            size += len(chunk)
            out.write(chunk)


def bytes_to_size_str(bytes):
   if bytes == 0:
       return "0B"
   units = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
   i = int(math.floor(math.log(bytes, 1024)))
   p = math.pow(1024, i)
   return f"{bytes/p:.02f} {units[i]}"


def requests_retry_session(
    retries=5,
    backoff_factor=0.2,
    status_forcelist=None, # (500, 502, 504)
    session=None,
):
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session


class GFile:
    def __init__(self, uri, progress=False, thread_num=4, chunk_size=1024*1024*10, chunk_copy_size=1024*1024, timeout=10,
                 aria2=False, key=None, mute=False, progress_callback=None, **kwargs) -> None:
        self.uri = uri
        self.chunk_size = size_str_to_bytes(chunk_size)
        self.chunk_copy_size = size_str_to_bytes(chunk_copy_size)
        self.thread_num=thread_num
        self.progress = progress
        self.data = None
        self.pbar = None
        self.timeout = timeout
        self.session = requests_retry_session()
        self.session.request = functools.partial(self.session.request, timeout=self.timeout)
        self.cookies = None
        self.current_chunk = 0
        self.aria2 = aria2
        self.mute = mute
        self.key = key
        self.progress_callback = progress_callback


    def upload_chunk(self, chunk_no, chunks):
        bar = self.pbar[chunk_no % self.thread_num] if self.pbar else None
        with io.BytesIO() as f:
            split_file(self.uri, f, self.chunk_size, start=chunk_no * self.chunk_size, chunk_copy_size=self.chunk_copy_size)
            chunk_size = f.tell()
            f.seek(0)
            fields = {
                "id": self.token,
                "name": Path(self.uri).name,
                "chunk": str(chunk_no),
                "chunks": str(chunks),
                "lifetime": "100",
                "file": ("blob", f, "application/octet-stream"),
            }
            form_data = MultipartEncoder(fields)
            headers = {
                "content-type": form_data.content_type,
            }
            # convert the form-data into a binary string, this way we can control/throttle its read() behavior
            form_data_binary = form_data.to_string()
            del form_data

        size = len(form_data_binary)
        if bar:
            bar.desc = f'chunk {chunk_no + 1}/{chunks}'
            bar.reset(total=size)
            # bar.refresh()

        def gen():
            offset = 0
            while True:
                if offset < size:
                    update_tick = 1024 * 128
                    yield form_data_binary[offset:offset+update_tick]
                    if bar:
                        bar.update(min(update_tick, size - offset))
                        bar.refresh()
                    offset += update_tick
                else:
                    if chunk_no != self.current_chunk:
                        time.sleep(0.01)
                    else:
                        time.sleep(0.1)
                        break
        while True:
            try:
                streamer = StreamingIterator(size, gen())
                resp = self.session.post(f"https://{self.server}/upload_chunk.php", data=streamer, headers=headers)
            except Exception as ex:
                if not self.mute:
                    print(ex)
                    print('Retrying...')
            else:
                break

        resp_data = resp.json()
        self.current_chunk += 1

        # プログレスコールバック実行（アップロード用）
        if self.progress_callback and hasattr(self, 'total_chunks') and hasattr(self, 'file_size'):
            progress_percent = int((self.current_chunk / self.total_chunks) * 100)
            uploaded_size = self.current_chunk * self.chunk_size
            if uploaded_size > self.file_size:
                uploaded_size = self.file_size
            result = self.progress_callback(progress_percent, uploaded_size, self.file_size)
            # コールバックがFalseを返した場合（停止要求）
            if result is False:
                self.failed = True
                return

        if 'url' in resp_data:
            self.data = resp_data
        if 'status' not in resp_data or resp_data['status']:
            print(resp_data)
            self.failed = True


    def upload(self):
        self.token = uuid.uuid1().hex
        self.pbar = None
        self.failed = False
        assert Path(self.uri).exists()
        size = Path(self.uri).stat().st_size
        chunks = math.ceil(size / self.chunk_size)
        
        # プログレスコールバック用の情報を保存
        self.file_size = size
        self.total_chunks = chunks
        
        print(f'Filesize {bytes_to_size_str(size)}, chunk size: {bytes_to_size_str(self.chunk_size)}, total chunks: {chunks}')

        if self.progress:
            self.pbar = []
            for i in range(self.thread_num):
                self.pbar.append(tqdm(total=size, unit="B", unit_scale=True, leave=False, unit_divisor=1024, ncols=100, position=i))

        self.server = re.search(r'var server = "(.+?)"', self.session.get('https://gigafile.nu/').text)[1]

        # upload the first chunk to set cookies properly.
        self.upload_chunk(0, chunks)

        # upload second to second last chunk(s)
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_num) as ex:
            futures = {ex.submit(self.upload_chunk, i, chunks): i for i in range(1, chunks)}
            try:
                for future in concurrent.futures.as_completed(futures):
                    if self.failed:
                        print('Failed!')
                        for future in futures:
                            future.cancel()
                        return
            except KeyboardInterrupt:
                print('\nUser cancelled the operation.')
                for future in futures:
                    future.cancel()
                return


        if self.pbar:
            for bar in self.pbar:
                bar.close()
        print('')
        if 'url' not in self.data:
            print('Something went wrong. Upload failed.', self.data)
        return self # for chain


    def get_download_page(self):
        if not self.data or not 'url' in self.data:
            return
        f = Path(self.uri)
        print(f"Finished at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, filename: {f.name}, size: {bytes_to_size_str(f.stat().st_size)}")
        print(self.data['url'])
        return self.data['url']


    def download(self, odir=None,):
        output = None
        m = re.search(r'^https?:\/\/\d+?\.gigafile\.nu\/([a-z0-9-]+)$', self.uri)
        if not m:
            print('Invalid URL.')
            return
        r = self.session.get(self.uri) # setup cookie

        files_info = []

        try:
            soup = BeautifulSoup(r.text, 'html.parser')
            if soup.select_one('#contents_matomete'):
                print('Matomete mode. Files will be downloaded one by one.')
                for ele in soup.select('.matomete_file'):
                    web_name = ele.select_one('.matomete_file_info > span:nth-child(2)').text.strip()
                    file_id = re.search(r'download\(\d+, *\'(.+?)\'', ele.select_one('.download_panel_btn_dl')['onclick'])[1]
                    size_str = re.search(r'（(.+?)）', ele.select_one('.matomete_file_info > span:nth-child(3)').text.strip())[1]
                    files_info.append((web_name, size_str, file_id))
            else:
                file_id = m[1]
                size_str = soup.select_one('.dl_size').text.strip()
                web_name = soup.select_one('#dl').text.strip()
                files_info.append((web_name, size_str, file_id))
        except Exception as ex:
            print(f'ERROR! Failed to parse the page {self.uri}.')
            print(ex)
            print('Please report it back to the developer.')
            return

        downloaded = []

        if len(files_info) > 1:
            print(f'Found {len(files_info)} files in the page.')

        for idx, (web_name, size_str, file_id) in enumerate(files_info, 1):
            print(f'Name: {web_name}, size: {size_str}, id: {file_id}')
            # only sanitize web filename. User provided output string(s) are on their own.
            if not output:
                filename = re.sub(r'[\\/:*?"<>|]', '_', web_name)
            else:
                if len(files_info) > 1:
                    # if there are more than one files, append idx to the filename
                    filename = output + f'_{idx}'
                else:
                    filename = output

            download_url = self.uri.rsplit('/', 1)[0] + '/download.php?file=' + file_id
            if self.key:
                download_url += f'&dlkey={self.key}'
            if self.aria2:
                cookie_str = "; ".join([f"{cookie.name}={cookie.value}" for cookie in self.session.cookies])
                cmd = ['aria2c', download_url, '--header', f'Cookie: {cookie_str}', '-o', filename]
                cmd.extend(self.aria2.split(' '))
                run(cmd)
                continue

            # 出力ディレクトリを確保
            uploads_dir = Path(odir) if odir else Path('./uploads')
            uploads_dir.mkdir(exist_ok=True)
            
            # 一時ファイルと最終ファイルパスを出力ディレクトリ内に設定
            final_path = uploads_dir / filename
            temp = str(final_path) + '.dl'
            
            with self.session.get(download_url, stream=True) as r:
                r.raise_for_status()
                filesize = int(r.headers['Content-Length'])
                downloaded_size = 0
                
                # GUI進捗コールバックでファイル名とサイズを通知（ダウンロード開始時）
                if self.progress_callback:
                    self.progress_callback(0, web_name, 0, filesize)
                
                if self.progress:
                    desc = filename if len(filename) <= 20 else filename[0:11] + '..' + filename[-7:]
                    self.pbar = tqdm(total=filesize, unit='B', unit_scale=True, unit_divisor=1024, desc=desc)
                
                with open(temp, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=self.chunk_copy_size):
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        # プログレスバー更新
                        if self.pbar: 
                            self.pbar.update(len(chunk))
                        
                        # GUI進捗コールバック実行（ファイル名、ダウンロードサイズ、合計サイズ付き）
                        if self.progress_callback:
                            progress_percent = int((downloaded_size / filesize) * 100) if filesize > 0 else 0
                            result = self.progress_callback(progress_percent, web_name, downloaded_size, filesize)
                            # コールバックがFalseを返した場合（停止要求）
                            if result is False:
                                break
                            
            if self.pbar: self.pbar.close()

            filesize_downloaded = Path(temp).stat().st_size
            print(f'Filesize check: expected: {filesize}; actual: {filesize_downloaded}', end=' ')
            if filesize == filesize_downloaded:
                print("Succeeded.")
                # 一時ファイルを最終ファイル名にリネーム
                rename(temp, final_path)
                filename = final_path
                ext = Path(filename).suffix.lower()
                if ext in ['.zip', '.7z', '.gz', '.tar']:

                    def try_extract(cmd, timeout=30):
                        try:
                            print(f"Running command: {' '.join(map(str, cmd))}")
                            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
                            return result.returncode == 0
                        except Exception as e:
                            print(f"Extraction failed: {e}")
                            return False

                    extracted = False
                    extract_dir = uploads_dir
                    if ext == '.zip' or ext == '.7z' or ext == '.gz' or ext == '.tar':
                        # Try to extract using unar first (unar supports zip, 7z, tar, gz)
                        print(f"Trying to extract {filename} with unar...")
                        cmd = ['unar', '-o', str(extract_dir), filename]
                        result = try_extract(cmd)
                        if result is not False:
                            print(f"Extracted {filename} with unar.")
                            try:
                                Path(filename).unlink()
                                print(f"Deleted archive file: {filename}")
                            except Exception as e:
                                print(f"Failed to delete archive file: {e}")
                            extracted = True
                        if not extracted:
                            print(f"Failed to extract {filename} with unar.")
            else:
                print(f"Downloaded file is corrupt. Please check the broken file at {temp} and delete it yourself if needed.")
            downloaded.append(filename)
        return downloaded

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
        
        # 停止フラグ
        self.stop_downloads = False
        self.stop_uploads = False
        
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
        columns = ("種別", "ファイル/URL", "状態", "進行率", "ファイルサイズ", "操作")
        self.progress_tree = ttk.Treeview(progress_frame, columns=columns, show="headings", height=10)
        
        for col in columns:
            self.progress_tree.heading(col, text=col)
            
        self.progress_tree.column("種別", width=100)
        self.progress_tree.column("ファイル/URL", width=300)
        self.progress_tree.column("状態", width=150)
        self.progress_tree.column("進行率", width=100)
        self.progress_tree.column("ファイルサイズ", width=100)
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
            if len(values) >= 6 and values[2] == "完了" and values[0] == "アップロード":
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
            if len(values) >= 6 and values[2] == "完了" and values[0] == "アップロード":
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
            if len(values) >= 6 and values[2] == "完了" and values[0] == "アップロード":
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
        self.stop_downloads = False
        self.log_message(f"{len(urls)}個のURLのダウンロードを開始します...")
        
        for url_data in urls:
            if self.stop_downloads:
                break
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
        self.stop_uploads = False
        
        # 複数ファイルかつZIP化オプションが有効な場合
        if len(valid_files) > 1 and self.auto_zip.get():
            self.log_message(f"{len(valid_files)}個のファイルをZIP化してアップロードします...")
            zip_file_path = self.create_zip_file(valid_files)
            if zip_file_path and not self.stop_uploads:
                self.start_single_upload(zip_file_path, is_temp_file=True)
            else:
                self.upload_button.config(state="normal")
        else:
            self.log_message(f"{len(valid_files)}個のファイルのアップロードを開始します...")
            for file_path in valid_files:
                if self.stop_uploads:
                    break
                self.start_single_upload(file_path)
            
    def start_single_download(self, url_data, download_dir):
        url, password = url_data
        display_text = f"{url} [PW]" if password else url
        
        # プログレステーブルにエントリ追加
        item_id = self.progress_tree.insert("", "end", values=("ダウンロード", display_text, "準備中", "0%", "", ""))
        
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
        item_id = self.progress_tree.insert("", "end", values=("アップロード", filename, "準備中", "0%", "", ""))
        
        # アップロードスレッド開始
        thread = threading.Thread(target=self.upload_worker, args=(file_path, item_id, is_temp_file))
        thread.daemon = True
        thread.start()
        
        self.active_uploads[item_id] = thread
        
    def download_worker(self, url, password, download_dir, item_id):
        try:
            # 停止チェック
            if self.stop_downloads:
                self.progress_queue.put(("update", item_id, "ダウンロード", "停止", "キャンセル", "0%", "", ""))
                return
                
            display_text = f"{url} [PW]" if password else url
            self.progress_queue.put(("update", item_id, "ダウンロード", display_text, "開始", "0%", "", ""))
            
            # URLからファイルIDを抽出
            file_id_match = re.search(r'^https?:\/\/\d+?\.gigafile\.nu\/([a-z0-9-]+)$', url)
            if not file_id_match:
                self.progress_queue.put(("update", item_id, "ダウンロード", "エラー", "失敗", "0%", "", ""))
                self.progress_queue.put(("log", f"無効なURL形式: {url}"))
                return
            
            file_id = file_id_match.group(1)
            
            # ファイルIDごとのディレクトリを作成
            file_id_dir = os.path.join(download_dir, file_id)
            os.makedirs(file_id_dir, exist_ok=True)
            
            # 速度計算用の変数
            speed_samples = []
            last_update_time = time.time()
            last_downloaded_size = 0
            last_display_update_time = 0
            last_status_text = "進行中"
            
            # プログレス更新用コールバック関数（速度計算付き）
            def progress_callback(percent, current_filename=None, downloaded_size=0, total_size=0):
                nonlocal speed_samples, last_update_time, last_downloaded_size, last_display_update_time, last_status_text
                
                # 停止チェック
                if self.stop_downloads:
                    return False  # ダウンロード停止シグナル
                
                filename_display = current_filename if current_filename else display_text
                current_time = time.time()
                
                # 速度計算（1秒以上経過した場合のみ）
                if current_time - last_update_time >= 1.0 and downloaded_size > last_downloaded_size:
                    speed = (downloaded_size - last_downloaded_size) / (current_time - last_update_time)
                    speed_samples.append(speed)
                    if len(speed_samples) > 5:  # 直近5サンプルの平均を使用
                        speed_samples = speed_samples[-5:]
                    
                    avg_speed = sum(speed_samples) / len(speed_samples)
                    remaining_bytes = total_size - downloaded_size
                    eta_seconds = remaining_bytes / avg_speed if avg_speed > 0 else 0
                    
                    # ETAを時:分:秒形式に変換
                    eta_hours = int(eta_seconds // 3600)
                    eta_minutes = int((eta_seconds % 3600) // 60)
                    eta_secs = int(eta_seconds % 60)
                    eta_str = f"{eta_hours:02d}:{eta_minutes:02d}:{eta_secs:02d}"
                    
                    last_status_text = f"進行中 ({bytes_to_size_str(avg_speed)}/s, ETA {eta_str})"
                    
                    last_update_time = current_time
                    last_downloaded_size = downloaded_size
                    last_display_update_time = current_time
                
                # UIの更新は0.5秒間隔で制限（チカチカ防止）
                if current_time - last_display_update_time >= 0.5:
                    # ファイルサイズ表示
                    file_size_str = bytes_to_size_str(total_size) if total_size > 0 else ""
                    
                    self.progress_queue.put(("update", item_id, "ダウンロード", filename_display, last_status_text, f"{percent}%", file_size_str, ""))
                    last_display_update_time = current_time
                
                return True  # 継続シグナル
            
            # GFileインスタンス作成（パスワードがある場合はkeyパラメータに渡す）
            gfile = GFile(url, progress=False, mute=True, key=password, progress_callback=progress_callback)
            
            self.progress_queue.put(("update", item_id, "ダウンロード", display_text, "進行中", "0%", "", ""))
            
            # ファイルIDディレクトリにダウンロード実行
            downloaded_files = gfile.download(odir=file_id_dir)
            
            # 停止チェック
            if self.stop_downloads:
                self.progress_queue.put(("update", item_id, "ダウンロード", "停止", "キャンセル", "0%", "", ""))
                pw_text = " [パスワード付き]" if password else ""
                self.progress_queue.put(("log", f"ダウンロード停止{pw_text}: {url}"))
                return
            
            if downloaded_files:
                filename = str(downloaded_files[0]) if downloaded_files else "不明"
                self.progress_queue.put(("update", item_id, "ダウンロード", filename, "完了", "100%", "", ""))
                pw_text = " [パスワード付き]" if password else ""
                self.progress_queue.put(("log", f"ダウンロード完了{pw_text}: {url} -> {filename} (フォルダ: {file_id})"))
            else:
                self.progress_queue.put(("update", item_id, "ダウンロード", "エラー", "失敗", "0%", "", ""))
                pw_text = " [パスワード付き]" if password else ""
                self.progress_queue.put(("log", f"ダウンロード失敗{pw_text}: {url}"))
                
        except Exception as e:
            display_text = f"{url} [PW]" if password else url
            self.progress_queue.put(("update", item_id, "ダウンロード", "エラー", "失敗", "0%", "", ""))
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
            # 停止チェック
            if self.stop_uploads:
                self.progress_queue.put(("update", item_id, "アップロード", "停止", "キャンセル", "0%", "", ""))
                return
                
            filename = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            file_size_str = bytes_to_size_str(file_size)
            
            self.progress_queue.put(("update", item_id, "アップロード", filename, "開始", "0%", file_size_str, ""))
            
            # 停止チェック
            if self.stop_uploads:
                self.progress_queue.put(("update", item_id, "アップロード", "停止", "キャンセル", "0%", file_size_str, ""))
                return
            
            # 速度計算用の変数
            speed_samples = []
            last_update_time = time.time()
            last_uploaded_size = 0
            last_display_update_time = 0
            last_status_text = "進行中"
            
            # プログレス更新用コールバック関数（アップロード用）
            def upload_progress_callback(percent, uploaded_size=0, total_size=0):
                nonlocal speed_samples, last_update_time, last_uploaded_size, last_display_update_time, last_status_text
                
                # 停止チェック
                if self.stop_uploads:
                    return False  # アップロード停止シグナル
                
                current_time = time.time()
                
                # 速度計算（1秒以上経過した場合のみ）
                if current_time - last_update_time >= 1.0 and uploaded_size > last_uploaded_size:
                    speed = (uploaded_size - last_uploaded_size) / (current_time - last_update_time)
                    speed_samples.append(speed)
                    if len(speed_samples) > 5:  # 直近5サンプルの平均を使用
                        speed_samples = speed_samples[-5:]
                    
                    avg_speed = sum(speed_samples) / len(speed_samples)
                    remaining_bytes = total_size - uploaded_size
                    eta_seconds = remaining_bytes / avg_speed if avg_speed > 0 else 0
                    
                    # ETAを時:分:秒形式に変換
                    eta_hours = int(eta_seconds // 3600)
                    eta_minutes = int((eta_seconds % 3600) // 60)
                    eta_secs = int(eta_seconds % 60)
                    eta_str = f"{eta_hours:02d}:{eta_minutes:02d}:{eta_secs:02d}"
                    
                    last_status_text = f"進行中 ({bytes_to_size_str(avg_speed)}/s, ETA {eta_str})"
                    
                    last_update_time = current_time
                    last_uploaded_size = uploaded_size
                    last_display_update_time = current_time
                
                # UIの更新は0.5秒間隔で制限（チカチカ防止）
                if current_time - last_display_update_time >= 0.5:
                    self.progress_queue.put(("update", item_id, "アップロード", filename, last_status_text, f"{percent}%", file_size_str, ""))
                    last_display_update_time = current_time
                
                return True  # 継続シグナル
            
            # GFileインスタンス作成（アップロード用、進捗コールバック付き）
            gfile = GFile(file_path, progress=False, mute=True, progress_callback=upload_progress_callback)
            
            self.progress_queue.put(("update", item_id, "アップロード", filename, "進行中", "0%", file_size_str, ""))
            
            # アップロード実行
            result = gfile.upload()
            
            # 停止チェック
            if self.stop_uploads:
                self.progress_queue.put(("update", item_id, "アップロード", "停止", "キャンセル", "0%", file_size_str, ""))
                self.progress_queue.put(("log", f"アップロード停止: {filename}"))
                return
            
            if result and hasattr(result, 'data') and result.data:
                url = result.get_download_page()
                if url:
                    self.progress_queue.put(("update", item_id, "アップロード", url, "完了", "100%", file_size_str, "コピー"))
                    self.progress_queue.put(("log", f"アップロード完了: {filename} -> {url}"))
                else:
                    self.progress_queue.put(("update", item_id, "アップロード", "エラー", "失敗", "0%", file_size_str, ""))
                    self.progress_queue.put(("log", f"アップロード失敗: {filename} (URLの取得に失敗)"))
            else:
                self.progress_queue.put(("update", item_id, "アップロード", "エラー", "失敗", "0%", file_size_str, ""))
                self.progress_queue.put(("log", f"アップロード失敗: {filename}"))
                
        except Exception as e:
            filename = os.path.basename(file_path)
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            file_size_str = bytes_to_size_str(file_size)
            self.progress_queue.put(("update", item_id, "アップロード", "エラー", "失敗", "0%", file_size_str, ""))
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
        self.stop_downloads = True
        self.log_message("ダウンロード停止が要求されました。")
        
        # ボタンを有効化
        self.download_button.config(state="normal")
        
    def stop_all_uploads(self):
        self.stop_uploads = True
        self.log_message("アップロード停止が要求されました。")
        
        # ボタンを有効化
        self.upload_button.config(state="normal")
        
    def check_progress(self):
        try:
            while True:
                try:
                    message = self.progress_queue.get_nowait()
                    
                    if message[0] == "update":
                        _, item_id, type_text, filename, status, progress, file_size, action = message
                        self.progress_tree.item(item_id, values=(type_text, filename, status, progress, file_size, action))
                        
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
