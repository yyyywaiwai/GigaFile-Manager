#!/bin/bash

echo "Building minimal GigaFile CLI..."

# ビルドディレクトリをクリーンアップ
rm -rf build-cli dist-cli gigafilecli.spec

# CLI用ビルドディレクトリ作成
mkdir -p build-cli dist-cli

# 最小限のPyInstallerでCLIアプリケーションをビルド
pyinstaller --onefile \
    --name="gigafile" \
    --distpath=dist-cli \
    --workpath=build-cli \
    --noconfirm \
    --console \
    --strip \
    --noupx \
    --exclude-module=tkinter \
    --exclude-module=torch \
    --exclude-module=torchvision \
    --exclude-module=transformers \
    --exclude-module=cv2 \
    --exclude-module=opencv-python \
    --exclude-module=matplotlib \
    --exclude-module=pandas \
    --exclude-module=numpy \
    --exclude-module=scipy \
    --exclude-module=sklearn \
    --exclude-module=tensorflow \
    --exclude-module=jedi \
    --exclude-module=IPython \
    --exclude-module=jupyter \
    --exclude-module=notebook \
    --exclude-module=altair \
    --exclude-module=gradio \
    --exclude-module=timm \
    --exclude-module=PIL \
    --exclude-module=Pillow \
    --exclude-module=sympy \
    --exclude-module=numba \
    --exclude-module=llvmlite \
    --exclude-module=PyQt5 \
    --exclude-module=PyQt6 \
    --exclude-module=PySide2 \
    --exclude-module=PySide6 \
    --exclude-module=wx \
    --exclude-module=gi \
    --exclude-module=gtk \
    --exclude-module=kivy \
    --exclude-module=pygame \
    --exclude-module=selenium \
    --exclude-module=scrapy \
    --exclude-module=django \
    --exclude-module=flask \
    --exclude-module=fastapi \
    --exclude-module=sqlalchemy \
    --exclude-module=pymongo \
    --exclude-module=psycopg2 \
    --exclude-module=mysql \
    --exclude-module=redis \
    --exclude-module=celery \
    --exclude-module=pytest \
    --exclude-module=unittest \
    --exclude-module=nose \
    --exclude-module=coverage \
    --exclude-module=black \
    --exclude-module=flake8 \
    --exclude-module=mypy \
    --exclude-module=pylint \
    --exclude-module=setuptools \
    --exclude-module=distutils \
    --exclude-module=wheel \
    --exclude-module=pip \
    --exclude-module=conda \
    --exclude-module=anaconda \
    --exclude-module=jupyter_core \
    --exclude-module=ipython_genutils \
    --exclude-module=traitlets \
    --exclude-module=jsonschema \
    --exclude-module=pyzmq \
    --exclude-module=tornado \
    --exclude-module=statsmodels \
    --exclude-module=seaborn \
    --exclude-module=plotly \
    --exclude-module=bokeh \
    --exclude-module=dash \
    --exclude-module=streamlit \
    --exclude-module=pydantic \
    --exclude-module=yaml \
    --exclude-module=toml \
    --exclude-module=configparser \
    --exclude-module=argcomplete \
    --exclude-module=click \
    --exclude-module=typer \
    --exclude-module=fire \
    --exclude-module=docopt \
    --exclude-module=rich \
    --exclude-module=colorama \
    --exclude-module=termcolor \
    --exclude-module=pygments \
    --exclude-module=prompt_toolkit \
    gigafilecli.py

# ビルド結果を確認
if [ -f "dist-cli/gigafilecli" ]; then
    echo "Build successful! CLI application created at: dist-cli/gigafilecli"
    ls -lh dist-cli/gigafilecli
    echo "File size:"
    du -sh dist-cli/gigafilecli
    echo ""
    echo "You can run the CLI with: ./dist-cli/gigafilecli --help"
    echo "Or copy to /usr/local/bin for system-wide access: sudo cp dist-cli/gigafilecli /usr/local/bin/"
else
    echo "Build failed. Check the output above for errors."
    exit 1
fi