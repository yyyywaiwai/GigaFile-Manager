#!/bin/bash

echo "Building GigaFile Manager GUI with Nuitka..."

# ビルドディレクトリをクリーンアップ
rm -rf build-nuitka-gui dist-nuitka-gui

# GUI用ビルドディレクトリ作成
mkdir -p build-nuitka-gui dist-nuitka-gui

# NuitkaでGUIアプリケーションをビルド（macOS .app形式）
echo "Building GUI application..."
python3 -m nuitka \
    --standalone \
    --macos-create-app-bundle \
    --macos-app-icon=icon.ico \
    --enable-plugin=tk-inter \
    --output-dir=dist-nuitka-gui \
    --output-filename="GigaFile Manager" \
    --include-package=tkinter \
    --include-package=requests \
    --include-package=urllib3 \
    --include-package=bs4 \
    --include-package=requests_toolbelt \
    --include-package=tqdm \
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
    --nofollow-import-to=kivy \
    --nofollow-import-to=pygame \
    --nofollow-import-to=selenium \
    --nofollow-import-to=scrapy \
    --nofollow-import-to=django \
    --nofollow-import-to=flask \
    --nofollow-import-to=fastapi \
    --nofollow-import-to=pytest \
    --nofollow-import-to=coverage \
    --nofollow-import-to=black \
    --nofollow-import-to=flake8 \
    --nofollow-import-to=mypy \
    --nofollow-import-to=pylint \
    --remove-output \
    --assume-yes-for-downloads \
    gigafiledl.py

# .appファイル名をリネーム
if [ -d "dist-nuitka-gui/gigafiledl.app" ]; then
    mv "dist-nuitka-gui/gigafiledl.app" "dist-nuitka-gui/GigaFile Manager.app"
fi

# ビルド結果を確認
if [ -d "dist-nuitka-gui/GigaFile Manager.app" ]; then
    echo "Build successful! Application created at: dist-nuitka-gui/GigaFile Manager.app"
    du -sh "dist-nuitka-gui/GigaFile Manager.app"
    echo ""
    echo "You can run the app by:"
    echo "  - Double-clicking: open 'dist-nuitka-gui/GigaFile Manager.app'"
    echo "  - Command line: ./dist-nuitka-gui/GigaFile\ Manager.app/Contents/MacOS/GigaFile\ Manager"
    echo ""
    echo "App size comparison with PyInstaller version:"
    if [ -d "dist/GigaFile Manager.app" ]; then
        echo "  PyInstaller version:"
        du -sh "dist/GigaFile Manager.app"
        echo "  Nuitka version:"
        du -sh "dist-nuitka-gui/GigaFile Manager.app"
    fi
else
    echo "Build failed. Check the output above for errors."
    exit 1
fi

echo ""
echo "Nuitka GUI build completed successfully!"