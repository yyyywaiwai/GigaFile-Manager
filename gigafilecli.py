#!/usr/bin/env python3
import argparse
import os
import sys
from pathlib import Path
import re
import zipfile
import tempfile
from datetime import datetime
import glob

# PyInstaller multiprocessing support
import multiprocessing
if sys.platform.startswith('win') and getattr(sys, 'frozen', False):
    # Windows frozen application support
    multiprocessing.freeze_support()

# GFile module integrated
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

        # upload second to second last chunk(s) - シングルスレッド版（PyInstaller対応）
        self.upload_failed = False
        
        try:
            # シングルスレッドで順次アップロード（PyInstaller環境で安定）
            for i in range(1, chunks):
                if self.failed or self.upload_failed:
                    break
                try:
                    self.upload_chunk(i, chunks)
                except Exception as e:
                    print(f"Upload chunk {i} failed: {e}")
                    self.upload_failed = True
                    break
                
        except KeyboardInterrupt:
            print('\nUser cancelled the operation.')
            self.upload_failed = True
            return


        if self.pbar:
            for bar in self.pbar:
                bar.close()
        print('')
        
        if self.failed or self.upload_failed:
            print('Upload failed.')
            return None
        elif 'url' not in self.data:
            print('Something went wrong. Upload failed.', self.data)
            return None
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


def is_valid_gigafile_url(url):
    pattern = r'^https?:\/\/\d+?\.gigafile\.nu\/[a-z0-9-]+$'
    return re.match(pattern, url) is not None


def create_zip_file(file_paths, output_path=None):
    try:
        # 一時ファイルを作成
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            zip_filename = f"files_{timestamp}.zip"
            temp_dir = tempfile.gettempdir()
            output_path = os.path.join(temp_dir, zip_filename)
        
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in file_paths:
                if os.path.isfile(file_path):
                    # ファイル名のみをアーカイブ内のパスとして使用
                    arcname = os.path.basename(file_path)
                    zipf.write(file_path, arcname)
                    
        print(f"ZIP化完了: {os.path.basename(output_path)}")
        return output_path
        
    except Exception as e:
        print(f"ZIP化エラー: {str(e)}")
        return None


def cmd_download(args):
    """ダウンロードコマンドの実行"""
    urls = []
    
    if args.url:
        # 単一URLまたはURL パスワード 形式
        parts = args.url.split()
        if len(parts) >= 2:
            url = parts[0]
            password = parts[1]
        else:
            url = args.url
            password = args.password
        
        if not is_valid_gigafile_url(url):
            print(f"エラー: 無効なGigaFileのURL: {url}")
            return 1
        
        urls.append((url, password))
    
    elif args.file:
        # ファイルからURL読み込み
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    # URL パスワード 形式かチェック
                    parts = line.split()
                    if len(parts) >= 2:
                        url = parts[0]
                        password = parts[1]
                    else:
                        url = line
                        password = None
                    
                    if not is_valid_gigafile_url(url):
                        print(f"警告: 無効なURL (行 {line_num}): {url}")
                        continue
                    
                    urls.append((url, password))
        except FileNotFoundError:
            print(f"エラー: ファイルが見つかりません: {args.file}")
            return 1
        except Exception as e:
            print(f"エラー: ファイル読み込み失敗: {e}")
            return 1
    else:
        print("エラー: ダウンロードするURLまたはファイルを指定してください")
        return 1
    
    if not urls:
        print("エラー: ダウンロードするURLが指定されていません")
        return 1
    
    # 出力ディレクトリの作成
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"{len(urls)}個のURLのダウンロードを開始します...")
    print(f"出力ディレクトリ: {output_dir}")
    
    success_count = 0
    
    for url, password in urls:
        print(f"\n{'='*60}")
        pw_text = " [パスワード付き]" if password else ""
        print(f"ダウンロード開始{pw_text}: {url}")
        
        try:
            # ファイルIDごとのディレクトリを作成
            url_match = re.search(r'^https?:\/\/\d+?\.gigafile\.nu\/([a-z0-9-]+)$', url)
            if url_match:
                file_id = url_match.group(1)
                file_id_dir = output_dir / file_id
                file_id_dir.mkdir(exist_ok=True)
                download_dir = file_id_dir
            else:
                download_dir = output_dir
            
            # GFileインسタンス作成
            gfile = GFile(url, progress=True, mute=False, key=password)
            
            # ダウンロード実行
            downloaded_files = gfile.download(odir=str(download_dir))
            
            if downloaded_files:
                print(f"ダウンロード完了{pw_text}: {url}")
                success_count += 1
            else:
                print(f"ダウンロード失敗{pw_text}: {url}")
                
        except KeyboardInterrupt:
            print("\n\nユーザーによってキャンセルされました。")
            break
        except Exception as e:
            print(f"ダウンロードエラー{pw_text}: {url} - {str(e)}")
    
    print(f"\n{'='*60}")
    print(f"ダウンロード完了: 成功 {success_count}/{len(urls)}")
    
    return 0 if success_count > 0 else 1


def cmd_upload(args):
    """アップロードコマンドの実行"""
    files = []
    
    # ファイル収集
    if args.files:
        for file_pattern in args.files:
            # パターンマッチング
            matched_files = glob.glob(file_pattern)
            if matched_files:
                files.extend(matched_files)
            else:
                # 直接ファイルパスとして扱う
                if os.path.exists(file_pattern):
                    files.append(file_pattern)
                else:
                    print(f"警告: ファイルが見つかりません: {file_pattern}")
    
    if args.directory:
        # ディレクトリからファイル収集
        dir_path = Path(args.directory)
        if not dir_path.exists():
            print(f"エラー: ディレクトリが見つかりません: {args.directory}")
            return 1
        
        pattern = args.pattern or "*"
        for file_path in dir_path.rglob(pattern):
            if file_path.is_file():
                files.append(str(file_path))
    
    # ファイルもディレクトリも指定されていない場合
    if not args.files and not args.directory:
        print("エラー: アップロードするファイルまたはディレクトリを指定してください")
        return 1
    
    # 重複削除と存在確認
    valid_files = []
    seen = set()
    
    for file_path in files:
        abs_path = os.path.abspath(file_path)
        if abs_path in seen:
            continue
        seen.add(abs_path)
        
        if os.path.exists(file_path) and os.path.isfile(file_path):
            valid_files.append(file_path)
        else:
            print(f"警告: ファイルが見つかりません: {file_path}")
    
    if not valid_files:
        print("エラー: アップロードするファイルがありません")
        return 1
    
    print(f"{len(valid_files)}個のファイルのアップロードを開始します...")
    
    # 複数ファイルかつZIP化オプションが有効な場合
    if len(valid_files) > 1 and args.auto_zip:
        print("複数ファイルをZIP化しています...")
        zip_path = create_zip_file(valid_files)
        if not zip_path:
            print("エラー: ZIP化に失敗しました")
            return 1
        
        upload_files = [zip_path]
        is_temp_file = True
    else:
        upload_files = valid_files
        is_temp_file = False
    
    success_count = 0
    urls = []
    
    for file_path in upload_files:
        print(f"\n{'='*60}")
        filename = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        print(f"アップロード開始: {filename} ({bytes_to_size_str(file_size)})")
        
        try:
            # GFileインスタンス作成
            gfile = GFile(file_path, progress=True, mute=False, thread_num=args.threads)
            
            # アップロード実行
            result = gfile.upload()
            
            if result and hasattr(result, 'data') and result.data:
                url = result.get_download_page()
                if url:
                    print(f"アップロード完了: {filename} -> {url}")
                    urls.append(url)
                    success_count += 1
                else:
                    print(f"アップロード失敗: {filename} (URLの取得に失敗)")
            else:
                print(f"アップロード失敗: {filename}")
                
        except KeyboardInterrupt:
            print("\n\nユーザーによってキャンセルされました。")
            break
        except Exception as e:
            print(f"アップロードエラー: {filename} - {str(e)}")
        finally:
            # 一時ファイルの削除
            if is_temp_file and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    print(f"一時ファイルを削除: {filename}")
                except Exception as e:
                    print(f"一時ファイル削除エラー: {e}")
    
    print(f"\n{'='*60}")
    print(f"アップロード完了: 成功 {success_count}/{len(upload_files)}")
    
    # アップロードURLの表示
    if urls:
        print(f"\nアップロードURL:")
        for url in urls:
            print(f"  {url}")
    
    return 0 if success_count > 0 else 1


def main():
    # PyInstaller multiprocessing support
    if getattr(sys, 'frozen', False):
        multiprocessing.freeze_support()
        
    parser = argparse.ArgumentParser(
        description='GigaFile便のCLIクライアント',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # 単一ファイルのダウンロード
  %(prog)s download https://xx.gigafile.nu/xxxxxxxx

  # パスワード付きファイルのダウンロード  
  %(prog)s download https://xx.gigafile.nu/xxxxxxxx --password mypassword
  %(prog)s download "https://xx.gigafile.nu/xxxxxxxx mypassword"

  # URLリストファイルからダウンロード
  %(prog)s download --file urls.txt --output-dir ./GFM-downloads

  # 単一ファイルのアップロード
  %(prog)s upload file.txt

  # 複数ファイルのアップロード（自動ZIP化）
  %(prog)s upload file1.txt file2.txt --auto-zip

  # ディレクトリ内のすべてのファイルをアップロード
  %(prog)s upload --directory ./photos --pattern "*.jpg" --auto-zip
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='利用可能なコマンド')
    
    # ダウンロードコマンド
    download_parser = subparsers.add_parser('download', help='ファイルのダウンロード')
    download_parser.add_argument('url', nargs='?', help='GigaFileのURL（"URL パスワード"形式も可）')
    download_parser.add_argument('--file', '-f', help='URLリストファイル（1行に1URL）')
    download_parser.add_argument('--password', '-p', help='パスワード（URLで指定されていない場合）')
    download_parser.add_argument('--output-dir', '-o', default='./GFM-downloads', help='出力ディレクトリ（デフォルト: ./GFM-downloads）')
    
    # アップロードコマンド
    upload_parser = subparsers.add_parser('upload', help='ファイルのアップロード')
    upload_parser.add_argument('files', nargs='*', help='アップロードするファイル（複数指定可、glob パターン対応）')
    upload_parser.add_argument('--directory', '-d', help='アップロードするディレクトリ')
    upload_parser.add_argument('--pattern', default='*', help='ディレクトリ指定時のファイルパターン（デフォルト: *）')
    upload_parser.add_argument('--auto-zip', action='store_true', help='複数ファイル時に自動ZIP化')
    upload_parser.add_argument('--threads', '-t', type=int, default=4, help='アップロードスレッド数（デフォルト: 4）')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        if args.command == 'download':
            result = cmd_download(args)
        elif args.command == 'upload':
            result = cmd_upload(args)
        else:
            result = 1
            
        # 明示的に終了処理
        if getattr(sys, 'frozen', False):
            # PyInstaller環境では強制終了
            import atexit
            atexit._run_exitfuncs()
            os._exit(result)
        return result
        
    except KeyboardInterrupt:
        print("\n\n処理がキャンセルされました。")
        if getattr(sys, 'frozen', False):
            os._exit(1)
        return 1
    except Exception as e:
        print(f"予期しないエラー: {e}")
        if getattr(sys, 'frozen', False):
            os._exit(1)
        return 1


if __name__ == "__main__":
    # PyInstaller環境でのmultiprocessing対応
    if getattr(sys, 'frozen', False):
        multiprocessing.freeze_support()
    
    exit_code = main()
    
    # PyInstaller環境では強制終了でresource_trackerエラーを回避
    if getattr(sys, 'frozen', False):
        os._exit(exit_code)
    else:
        sys.exit(exit_code)