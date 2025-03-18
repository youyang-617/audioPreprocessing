# build.py
import os
import subprocess
import sys
import shutil

def main():
    # 确保所有依赖已安装
    print("安装依赖...")
    subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller", "pydub", "tkinterdnd2"])
    
    # 创建hook文件
    print("创建hook文件...")
    with open("hook-tkinterdnd2.py", "w") as f:
        f.write("from PyInstaller.utils.hooks import collect_data_files\n")
        f.write("datas = collect_data_files('tkinterdnd2')\n")
    
    # 运行pyinstaller
    print("开始打包...")
    cmd = [
        "pyinstaller",
        "--name", "AudioProcessor",
        "--windowed",
        "--onefile",
        "--additional-hooks-dir=.",
        # "--add-data", "ffmpeg/*;.",
        "--icon=icon.ico", 
        "main.py"  # 替换为你的主脚本文件名
    ]
    subprocess.run(cmd)
    
    print("打包完成！可执行文件位于dist目录。")

if __name__ == "__main__":
    main()