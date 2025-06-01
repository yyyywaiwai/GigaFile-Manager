echo "Building minimal GigaFile Manager..."

# ビルドディレクトリをクリーンアップ
rm -rf build dist *.spec

# 不要な大きなパッケージを除外してPyInstallerでアプリケーションをビルド
pyinstaller --windowed \
    --name="GigaFile Manager" \
    --onedir \
    --icon=icon.ico \
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
    gigafiledl.py

# ビルド結果を確認
if [ -d "dist/GigaFile Manager.app" ]; then
    echo "Build successful! Application created at: dist/GigaFile Manager.app"
    du -sh "dist/GigaFile Manager.app"
    echo "You can run the app by double-clicking or using: open 'dist/GigaFile Manager.app'"
else
    echo "Build failed. Check the output above for errors."
    exit 1
fi