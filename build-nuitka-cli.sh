#!/bin/bash

echo "Building minimal GigaFile CLI with Nuitka..."

# ビルドディレクトリをクリーンアップ
rm -rf build-nuitka-cli dist-nuitka-cli

# CLI用ビルドディレクトリ作成
mkdir -p build-nuitka-cli dist-nuitka-cli

# Nuitkaでスタンドアロン版（ディレクトリ版）をビルド
echo "Building standalone version..."
python3 -m nuitka \
    --standalone \
    --output-dir=dist-nuitka-cli \
    --output-filename=gigafile \
    --include-package=requests \
    --include-package=urllib3 \
    --include-package=bs4 \
    --include-package=requests_toolbelt \
    --include-package=tqdm \
    --nofollow-import-to=tkinter \
    --nofollow-import-to=torch \
    --nofollow-import-to=torchvision \
    --nofollow-import-to=transformers \
    --nofollow-import-to=cv2 \
    --nofollow-import-to=opencv-python \
    --nofollow-import-to=matplotlib \
    --nofollow-import-to=pandas \
    --nofollow-import-to=numpy \
    --nofollow-import-to=scipy \
    --nofollow-import-to=sklearn \
    --nofollow-import-to=tensorflow \
    --nofollow-import-to=jedi \
    --nofollow-import-to=IPython \
    --nofollow-import-to=jupyter \
    --nofollow-import-to=notebook \
    --nofollow-import-to=altair \
    --nofollow-import-to=gradio \
    --nofollow-import-to=timm \
    --nofollow-import-to=PIL \
    --nofollow-import-to=Pillow \
    --nofollow-import-to=sympy \
    --nofollow-import-to=numba \
    --nofollow-import-to=llvmlite \
    --nofollow-import-to=PyQt5 \
    --nofollow-import-to=PyQt6 \
    --nofollow-import-to=PySide2 \
    --nofollow-import-to=PySide6 \
    --nofollow-import-to=wx \
    --nofollow-import-to=gi \
    --nofollow-import-to=gtk \
    --nofollow-import-to=kivy \
    --nofollow-import-to=pygame \
    --nofollow-import-to=selenium \
    --nofollow-import-to=scrapy \
    --nofollow-import-to=django \
    --nofollow-import-to=flask \
    --nofollow-import-to=fastapi \
    --nofollow-import-to=sqlalchemy \
    --nofollow-import-to=pymongo \
    --nofollow-import-to=psycopg2 \
    --nofollow-import-to=mysql \
    --nofollow-import-to=redis \
    --nofollow-import-to=celery \
    --nofollow-import-to=pytest \
    --nofollow-import-to=unittest \
    --nofollow-import-to=nose \
    --nofollow-import-to=coverage \
    --nofollow-import-to=black \
    --nofollow-import-to=flake8 \
    --nofollow-import-to=mypy \
    --nofollow-import-to=pylint \
    --nofollow-import-to=setuptools \
    --nofollow-import-to=distutils \
    --nofollow-import-to=wheel \
    --nofollow-import-to=pip \
    --nofollow-import-to=conda \
    --nofollow-import-to=anaconda \
    --nofollow-import-to=jupyter_core \
    --nofollow-import-to=ipython_genutils \
    --nofollow-import-to=traitlets \
    --nofollow-import-to=jsonschema \
    --nofollow-import-to=pyzmq \
    --nofollow-import-to=tornado \
    --nofollow-import-to=statsmodels \
    --nofollow-import-to=seaborn \
    --nofollow-import-to=plotly \
    --nofollow-import-to=bokeh \
    --nofollow-import-to=dash \
    --nofollow-import-to=streamlit \
    --nofollow-import-to=pydantic \
    --nofollow-import-to=yaml \
    --nofollow-import-to=toml \
    --nofollow-import-to=configparser \
    --nofollow-import-to=argcomplete \
    --nofollow-import-to=click \
    --nofollow-import-to=typer \
    --nofollow-import-to=fire \
    --nofollow-import-to=docopt \
    --nofollow-import-to=rich \
    --nofollow-import-to=colorama \
    --nofollow-import-to=termcolor \
    --nofollow-import-to=pygments \
    --nofollow-import-to=prompt_toolkit \
    --remove-output \
    --assume-yes-for-downloads \
    gigafilecli.py

# スタンドアロン版の結果を確認
if [ -f "dist-nuitka-cli/gigafilecli.dist/gigafile" ]; then
    echo "Standalone build successful! CLI application created at: dist-nuitka-cli/gigafilecli.dist/"
    ls -lh dist-nuitka-cli/gigafilecli.dist/gigafile
    echo "Directory size:"
    du -sh dist-nuitka-cli/gigafilecli.dist
    echo ""
    echo "You can run the CLI with: ./dist-nuitka-cli/gigafilecli.dist/gigafile --help"
    echo ""
    
    # スタンドアロン版を保護用ディレクトリに移動
    echo "Protecting standalone build..."
    mkdir -p dist-nuitka-cli/standalone-final
    cp -r dist-nuitka-cli/gigafilecli.dist dist-nuitka-cli/standalone-final/
    echo "Standalone version backed up to: dist-nuitka-cli/standalone-final/gigafilecli.dist/"
    echo ""
    
    # ポータブル単一ファイル版も作成
    echo "Building portable single-file version..."
    python3 -m nuitka \
        --onefile \
        --output-dir=dist-nuitka-cli \
        --output-filename=gigafile-portable \
        --include-package=requests \
        --include-package=urllib3 \
        --include-package=bs4 \
        --include-package=requests_toolbelt \
        --include-package=tqdm \
        --nofollow-import-to=tkinter \
        --nofollow-import-to=torch \
        --nofollow-import-to=transformers \
        --nofollow-import-to=matplotlib \
        --nofollow-import-to=pandas \
        --nofollow-import-to=numpy \
        --nofollow-import-to=scipy \
        --nofollow-import-to=sklearn \
        --nofollow-import-to=tensorflow \
        --nofollow-import-to=PyQt5 \
        --nofollow-import-to=PyQt6 \
        --nofollow-import-to=wx \
        --nofollow-import-to=kivy \
        --remove-output \
        --assume-yes-for-downloads \
        gigafilecli.py
    
    if [ -f "dist-nuitka-cli/gigafile-portable" ]; then
        echo "Portable version created: dist-nuitka-cli/gigafile-portable"
        ls -lh dist-nuitka-cli/gigafile-portable
        echo ""
        echo "You can copy to /usr/local/bin for system-wide access:"
        echo "sudo cp dist-nuitka-cli/gigafile-portable /usr/local/bin/gigafile"
    fi
else
    echo "Build failed. Check the output above for errors."
    exit 1
fi

echo ""
echo "Nuitka build completed successfully!"
echo "Standalone version: dist-nuitka-cli/standalone-final/gigafilecli.dist/gigafile"
echo "Portable version: dist-nuitka-cli/gigafile-portable"
echo ""
echo "両方のビルド結果が利用可能です:"
echo "- スタンドアロン版（ディレクトリ）: ./dist-nuitka-cli/standalone-final/gigafilecli.dist/gigafile"
echo "- ポータブル版（単一ファイル）: ./dist-nuitka-cli/gigafile-portable"