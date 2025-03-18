import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import os
from threading import Thread
from typing import Dict, Any, Optional

# 导入 tkinterdnd2
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    use_dnd = True
except ImportError:
    use_dnd = False

# 导入 pydub
try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False

# ===== MODEL =====
class AudioProcessor:
    """音频处理核心类（数据模型）"""
    def __init__(self):
        self.audio = None  # 存储音频数据的pydub对象
        self.file_path = ""  # 原始文件路径
        self.original_format = ""  # 原始文件格式扩展名

    def load_audio(self, file_path: str) -> bool:
        """加载音频文件并初始化音频对象"""
        try:
            self.file_path = file_path
            # 提取文件扩展名（不含点）
            self.original_format = os.path.splitext(file_path)[1][1:].lower()  
            self.audio = AudioSegment.from_file(file_path)
            return True
        except Exception as e:
            raise Exception(f"无法加载音频文件: {str(e)}")

    def get_audio_info(self) -> Dict[str, Any]:
        """获取音频信息"""
        if not self.audio:
            return {}
        return {
            "声道数": self.audio.channels,
            "采样率": self.audio.frame_rate,
            "位深度": self.audio.sample_width * 8,
            "时长(秒)": len(self.audio) / 1000.0,
            "最大音量(dBFS)": self.audio.max_dBFS,
            "原始格式": self.original_format
        }

    def process_audio(self, params: Dict[str, Any], progress_callback=None) -> bool:
        """处理音频"""
        try:
            steps = [
                (self._process_channels, 10, 30),
                (self._process_normalization, 30, 50),
                (self._process_sample_rate, 50, 70),
                (self._process_export, 70, 100)
            ]
            
            for step_func, start, end in steps:
                step_func(params)
                if progress_callback:
                    progress_callback(start + (end - start)//2)
            
            return True
        except Exception as e:
            raise Exception(f"处理失败: {str(e)}")
    
    def _process_channels(self, params):
        if params.get("mono", False):
            self.audio = self.audio.set_channels(1)
    
    def _process_normalization(self, params):
        if params.get("normalize", False) and params.get("normalize_value"):
            target_db = float(params["normalize_value"])
            change_in_db = target_db - self.audio.max_dBFS
            self.audio = self.audio.apply_gain(change_in_db)
    
    def _process_sample_rate(self, params):
        if params.get("sample_rate"):
            new_sample_rate = int(params["sample_rate"])
            self.audio = self.audio.set_frame_rate(new_sample_rate)
    
    def _process_export(self, params):
        output_format = params["output_format"]
        export_params = {}
        
        # WAV格式特殊处理：在导出前设置位深度
        if output_format == "wav" and params.get("bit_depth"):
            self.audio = self.audio.set_sample_width(int(params["bit_depth"]) // 8)
        
        # 其他格式保持原有处理
        elif output_format == "mp3" and params.get("bitrate"):
            export_params["bitrate"] = params["bitrate"]
        elif output_format == "flac" and params.get("compression"):
            export_params["compression"] = params["compression"]
        
        # 移除sample_width参数
        self.audio.export(params["output_path"], format=output_format, **export_params)

# ===== CONTROLLER =====
class AudioProcessorController:
    """音频处理控制器"""
    def __init__(self, view):
        self.model = AudioProcessor()  # 核心处理模型
        self.view = view  # 关联的视图对象
        self.processing = False  # 处理状态标志

    def load_audio(self, file_path: str) -> None:
        """加载音频文件"""
        try:
            if not PYDUB_AVAILABLE:
                self.view.show_message("错误", "请安装pydub库: pip install pydub")
                return
            self.model.load_audio(file_path)
            self.view.update_audio_info(self.model.get_audio_info())
        except Exception as e:
            self.view.show_message("错误", str(e))

        
    def process_audio(self, params: Dict[str, Any]) -> None:
        """处理音频"""
        if not self.model.file_path:
            return self.view.show_message("错误", "请先选择音频文件")
        
        # 验证标准化
        if params.get("normalize") and params.get("normalize_value"):
            try:
                db_value = float(params["normalize_value"])
                if db_value >= 0:  # 统一验证负值
                    raise ValueError("必须为负值")
            except ValueError as e:
                error_msg = "必须为数字" if "could not convert" in str(e) else str(e)
                return self.view.show_message("错误", f"音量值{error_msg}")
        
        if self.processing:
            return

        
        # 获取输出路径
        output_format = params["output_format"]
        output_path = self.view.ask_save_path(output_format)  # 调用视图的保存对话框
        params["output_path"] = output_path
        if not output_path:  # 用户取消保存操作
            return
        
        
        # 启动处理线程
        self.processing = True
        self.view.set_processing_state(True)  # 更新UI状态
        self.view.reset_progress()
        
        def process_thread():
            """后台处理线程"""
            try:
                # 调用模型处理并传递进度回调
                self.model.process_audio(params, self.view.update_progress)
                # 使用after方法更新UI线程
                self.view.master.after(0, lambda: [
                    self.view.show_message("成功", "处理完成"),
                    self.view.update_progress(100)
                ])
            except Exception as e:
                self.view.master.after(0, lambda err=str(e): self.view.show_message("错误", err))
            finally:
                # 清理状态
                self.processing = False
                self.view.master.after(0, lambda: [
                    self.view.set_processing_state(False),
                    self.view.reset_progress()
                ])
        
        Thread(target=process_thread).start()

# ===== VIEW =====
class AudioProcessorView:
    """音频处理视图"""
    def __init__(self, master):
        self.master = master
        self.master.title("音频处理工具")
        self.master.geometry("500x600")
        self.controller = AudioProcessorController(self)
        self.param_frames = {}
        self._create_ui()

    def _create_ui(self) -> None:
        """创建UI组件"""
        # 文件选择区域
        file_frame = ttk.LabelFrame(self.master, text="文件选择")
        file_frame.pack(fill=tk.X, padx=10, pady=5)
        self._create_file_frame(file_frame)
        
        # 音频信息区域
        info_frame = ttk.LabelFrame(self.master, text="音频信息")
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        self._create_info_frame(info_frame)
        
        # 可选处理区域
        processing_frame = ttk.LabelFrame(self.master, text="可选处理")
        processing_frame.pack(fill=tk.X, padx=10, pady=5)
        self._create_processing_options(processing_frame)
        
        # 导出设置区域
        export_frame = ttk.LabelFrame(self.master, text="导出设置")
        export_frame.pack(fill=tk.X, padx=10, pady=5)
        self._create_export_options(export_frame)
        
        # 进度条区域
        progress_frame = ttk.LabelFrame(self.master, text="处理进度")
        progress_frame.pack(fill=tk.X, padx=10, pady=5)
        self._create_progress_frame(progress_frame)
        
        # 处理按钮
        self.btn_process = ttk.Button(self.master, text="开始处理", command=self._on_process)
        self.btn_process.pack(pady=10)
        
        if use_dnd:
            self.master.drop_target_register(DND_FILES)
            self.master.dnd_bind('<<Drop>>', self._on_drop)

    def _create_file_frame(self, parent):
        self.btn_choose = ttk.Button(parent, text="选择文件", command=self._on_choose_file)
        self.btn_choose.pack(side=tk.LEFT, padx=5, pady=5)
        self.lbl_file_path = ttk.Label(parent, text="未选择文件")
        self.lbl_file_path.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)

    def _create_info_frame(self, parent):
        self.txt_info = tk.Text(parent, height=6, width=40, state=tk.DISABLED)
        self.txt_info.pack(fill=tk.X, padx=5, pady=5)

    def _create_processing_options(self, parent):
        # 转换单声道
        self.var_mono = tk.BooleanVar(value=False)
        ttk.Checkbutton(parent, text="转换为单声道（左右平均）", variable=self.var_mono).pack(anchor=tk.W, padx=5, pady=2)
        
        # 音量标准化
        normalize_frame = ttk.Frame(parent)
        normalize_frame.pack(fill=tk.X, padx=5, pady=2)
        self.var_normalize = tk.BooleanVar(value=False)
        ttk.Checkbutton(normalize_frame, text="音量峰值标准化到", variable=self.var_normalize).pack(side=tk.LEFT)
        self.entry_normalize = ttk.Entry(normalize_frame, width=5)
        self.entry_normalize.insert(0, "-6.0")
        self.entry_normalize.pack(side=tk.LEFT)
        ttk.Label(normalize_frame, text="dB").pack(side=tk.LEFT)

    def _create_export_options(self, parent):
        # 输出格式
        format_frame = ttk.Frame(parent)
        format_frame.pack(fill=tk.X, padx=5, pady=2)
        ttk.Label(format_frame, text="输出格式:").pack(side=tk.LEFT)
        self.var_format = tk.StringVar(value="wav")
        self.format_combobox = ttk.Combobox(format_frame, textvariable=self.var_format, 
                                           values=["wav", "mp3", "flac"], state="readonly")
        self.format_combobox.pack(side=tk.LEFT)
        self.format_combobox.bind("<<ComboboxSelected>>", self._on_format_change)
        
        # 采样率
        sample_rate_frame = ttk.Frame(parent)
        sample_rate_frame.pack(fill=tk.X, padx=5, pady=2)
        ttk.Label(sample_rate_frame, text="采样率:").pack(side=tk.LEFT)
        self.sample_rate_combobox = ttk.Combobox(sample_rate_frame, 
                                                values=["44100", "48000", "96000"], 
                                                state="readonly")
        self.sample_rate_combobox.set("44100")
        self.sample_rate_combobox.pack(side=tk.LEFT)
        
        # 动态参数容器
        self.param_container = ttk.Frame(parent)
        self.param_container.pack(fill=tk.X, padx=5, pady=5)
        self._create_param_frames()

    def _create_param_frames(self):
        """创建格式专属参数区域"""
        # WAV参数
        wav_frame = ttk.Frame(self.param_container)
        ttk.Label(wav_frame, text="位深度:").pack(side=tk.LEFT)
        self.wav_bit_depth = ttk.Combobox(wav_frame, values=[16, 24, 32], state="readonly")
        self.wav_bit_depth.set(16)
        self.wav_bit_depth.pack(side=tk.LEFT)
        self.param_frames["wav"] = wav_frame
        
        # MP3参数
        mp3_frame = ttk.Frame(self.param_container)
        ttk.Label(mp3_frame, text="码率:").pack(side=tk.LEFT)
        self.mp3_bitrate = ttk.Combobox(mp3_frame, values=[128, 192, 256, 320], state="readonly")
        self.mp3_bitrate.set(192)
        self.mp3_bitrate.pack(side=tk.LEFT)
        ttk.Label(mp3_frame, text="kbps").pack(side=tk.LEFT)
        self.param_frames["mp3"] = mp3_frame
        
        # FLAC参数
        flac_frame = ttk.Frame(self.param_container)
        ttk.Label(flac_frame, text="压缩等级:").pack(side=tk.LEFT)
        self.flac_compression = ttk.Combobox(flac_frame, values=list(range(9)), state="readonly")
        self.flac_compression.set(5)
        self.flac_compression.pack(side=tk.LEFT)
        self.param_frames["flac"] = flac_frame
        
        # 默认显示WAV参数
        self._on_format_change()

    def _create_progress_frame(self, parent):
        self.progress = ttk.Progressbar(parent, orient=tk.HORIZONTAL, length=100, mode='determinate')
        self.progress.pack(fill=tk.X, pady=5)

    def _on_format_change(self, event=None):
        """格式选择变化时的处理"""
        selected = self.var_format.get()
        for fmt, frame in self.param_frames.items():
            frame.pack_forget()
        self.param_frames.get(selected, ttk.Frame()).pack(fill=tk.X)

    def _on_choose_file(self) -> None:
        """选择文件按钮点击事件"""
        file_path = filedialog.askopenfilename(filetypes=[("音频文件", "*.wav *.mp3 *.flac *.aac *.ogg")])
        if file_path:
            self.lbl_file_path.config(text=os.path.basename(file_path))
            self.controller.load_audio(file_path)

    def _on_drop(self, event) -> None:
        """文件拖放事件"""
        file_path = event.data.strip('{}')
        if os.path.isfile(file_path):
            self.lbl_file_path.config(text=os.path.basename(file_path))
            self.controller.load_audio(file_path)

    def _on_process(self) -> None:
        """处理按钮点击事件"""
        params = {
            "mono": self.var_mono.get(),
            "normalize": self.var_normalize.get(),
            "normalize_value": self.entry_normalize.get() if self.var_normalize.get() else None,
            "sample_rate": self.sample_rate_combobox.get(),
            "output_format": self.var_format.get()
        }
        
        # 添加格式专属参数
        fmt = params["output_format"]
        if fmt == "wav":
            params["bit_depth"] = self.wav_bit_depth.get()
        elif fmt == "mp3":
            params["bitrate"] = self.mp3_bitrate.get()
        elif fmt == "flac":
            params["compression"] = self.flac_compression.get()
        
        self.controller.process_audio(params)

    def update_audio_info(self, info: Dict[str, Any]) -> None:
        """更新音频信息"""
        self.txt_info.config(state=tk.NORMAL)
        self.txt_info.delete(1.0, tk.END)
        for key, value in info.items():
            self.txt_info.insert(tk.END, f"{key}: {value}\n")
        self.txt_info.config(state=tk.DISABLED)

    def update_progress(self, value: int) -> None:
        """更新进度条"""
        self.master.after(0, lambda: self.progress.configure(value=value))

    def reset_progress(self) -> None:
        """重置进度条"""
        self.master.after(0, lambda: self.progress.configure(value=0))

    def set_processing_state(self, processing: bool) -> None:
        """设置处理状态"""
        state = tk.DISABLED if processing else "readonly"
        self.btn_choose.config(state=state)
        self.btn_process.config(state=state)
        self.format_combobox.config(state=state)
        self.sample_rate_combobox.config(state=state)

    def ask_save_path(self, format_type: str) -> Optional[str]:
        """获取保存路径（自动填充_processed文件名）"""
        # 获取原始文件路径信息
        original_path = self.controller.model.file_path
        original_dir = os.path.dirname(original_path)
        original_name = os.path.basename(original_path)
        name_without_ext = os.path.splitext(original_name)[0]
        
        # 构造默认文件名（保留原扩展名防止格式转换）
        default_filename = f"{name_without_ext}_processed.{format_type}"
        default_path = os.path.join(original_dir, default_filename)
        
        # 显示保存对话框并预填充文件名
        return filedialog.asksaveasfilename(
            initialfile=default_filename,
            initialdir=original_dir,
            defaultextension=f".{format_type}",
            filetypes=[(f"{format_type.upper()}文件", f"*.{format_type}")]
        )

    def show_message(self, title: str, message: str) -> None:
        """显示消息"""
        if title == "错误":
            messagebox.showerror(title, message)
        else:
            messagebox.showinfo(title, message)

# ===== 主程序 =====
if __name__ == "__main__":
    root = TkinterDnD.Tk() if use_dnd else tk.Tk()
    app = AudioProcessorView(root)
    root.mainloop()