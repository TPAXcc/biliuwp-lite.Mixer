import os
import json
import subprocess
import requests
import concurrent.futures
import zipfile
import fnmatch
from tkinter import Tk, Button, Label, StringVar, filedialog, messagebox
from tqdm import tqdm
import sys
import ctypes
import shutil
import tempfile
import time
import uuid  # 新增导入


class FFMPEGMergerGUI:
    def __init__(self, master):
        self.master = master
        master.title("FFMPEG 视频音频合并工具")

        self.label = Label(master, text="请选择包含视频和音频文件的文件夹:")
        self.label.pack(pady=10)

        self.folder_path_var = StringVar()
        self.folder_path_label = Label(
            master, textvariable=self.folder_path_var, wraplength=400
        )
        self.folder_path_label.pack(pady=5)

        self.select_button = Button(
            master, text="选择文件夹", command=self.select_folder, width=20
        )
        self.select_button.pack(pady=5)

        self.merge_button = Button(
            master, text="开始合并", command=self.start_merge, width=20
        )
        self.merge_button.pack(pady=10)

        # 新增输出路径标签和按钮
        self.output_path_label = Label(master, text="请选择输出文件夹:")
        self.output_path_label.pack(pady=5)

        self.output_path_var = StringVar()
        self.output_path_label = Label(
            master, textvariable=self.output_path_var, wraplength=400
        )
        self.output_path_label.pack(pady=5)

        self.select_output_button = Button(
            master, text="选择输出文件夹", command=self.select_output_folder, width=20
        )
        self.select_output_button.pack(pady=5)

        # 设置默认输出路径
        default_output_dir = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "导出视频"
        )
        if not os.path.exists(default_output_dir):
            os.makedirs(default_output_dir)
        self.output_path_var.set(default_output_dir)

        # 关键修复：设置FFmpeg使用UTF-8路径
        os.environ["FFMPEG_UTF8_PATHS"] = "1"

        # 初始化缓存目录
        self.init_cache_dir()

        # 立即检查并下载 FFmpeg，并传递当前脚本所在目录
        current_dir = os.path.dirname(os.path.realpath(__file__))
        self.ensure_ffmpeg_installed(current_dir)

    def init_cache_dir(self):
        """初始化C盘缓存目录"""
        try:
            # 尝试创建C盘缓存目录
            self.cache_root = r"C:\FFMPEG_CACHE"
            if not os.path.exists(self.cache_root):
                os.makedirs(self.cache_root)
            print(f"缓存目录已设置: {self.cache_root}")
        except Exception as e:
            print(f"创建C盘缓存目录失败: {str(e)}")
            # 备用方案：使用系统临时目录
            self.cache_root = tempfile.gettempdir()
            print(f"改用系统临时目录: {self.cache_root}")

    def select_folder(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.folder_path_var.set(folder_selected)

    def select_output_folder(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.output_path_var.set(folder_selected)

    def start_merge(self):
        base_dir = self.folder_path_var.get()
        output_dir = self.output_path_var.get()
        if base_dir:
            if not os.path.exists(output_dir):
                try:
                    os.makedirs(output_dir)
                    print(f"已创建输出目录: {output_dir}")
                except Exception as e:
                    messagebox.showerror("错误", f"无法创建输出目录: {str(e)}")
                    return

            tasks = []
            for root, dirs, files in os.walk(base_dir):
                if "info.json" in files:
                    info_path = os.path.join(root, "info.json")
                    try:
                        # 使用系统默认编码读取JSON文件（解决中文路径问题）
                        with open(info_path, "r", encoding="utf-8") as f:
                            data = json.load(f)

                        # 检查必要的字段是否存在
                        if (
                            "VideoPath" in data
                            and isinstance(data["VideoPath"], list)
                            and len(data["VideoPath"]) >= 2
                            and "EpisodeTitle" in data
                        ):

                            # 获取Index字段（如果不存在则使用0）
                            index = str(data.get("Index", "0")).strip()
                            # 确保Index是数字格式，如果不是则使用0
                            if not index.isdigit():
                                index = "0"

                            # 规范化路径 - 关键修复！
                            video_file = os.path.normpath(
                                os.path.join(root, data["VideoPath"][0])
                            )
                            audio_file = os.path.normpath(
                                os.path.join(root, data["VideoPath"][1])
                            )
                            episode_title = data["EpisodeTitle"]

                            # 处理文件名中的非法字符（Windows文件名不允许使用某些字符）
                            episode_title = self.sanitize_filename(episode_title)

                            # 修改输出文件名格式：P Index EpisodeTitle.mp4
                            output_file = os.path.normpath(
                                os.path.join(
                                    output_dir, f"P{index} {episode_title}.mp4"
                                )
                            )

                            # 添加到任务列表
                            tasks.append((video_file, audio_file, output_file))
                    except json.JSONDecodeError:
                        print(f"警告：{info_path} 文件格式错误，跳过处理")
                    except Exception as e:
                        print(f"处理 {info_path} 时出错: {str(e)}")

            if not tasks:
                messagebox.showinfo("提示", "未找到有效的合并任务")
                return

            # 使用线程池来并发处理所有任务
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = [
                    executor.submit(self.handle_ffmpeg_operations, *task)
                    for task in tasks
                ]

                # 实时显示进度
                with tqdm(total=len(tasks), desc="合并进度") as pbar:
                    for future in concurrent.futures.as_completed(futures):
                        pbar.update(1)
                        try:
                            future.result()
                        except Exception as e:
                            print(f"任务执行出错: {str(e)}")

                # 等待所有任务完成
                concurrent.futures.wait(futures)

            self.label.config(text="合并完成！")
            messagebox.showinfo("完成", "所有文件合并完成！")
        else:
            self.label.config(text="请先选择文件夹！")
            messagebox.showwarning("警告", "请先选择包含视频和音频的文件夹")

    def sanitize_filename(self, filename):
        """移除Windows文件名中的非法字符"""
        # Windows文件名不允许的字符: \ / : * ? " < > |
        invalid_chars = ["\\", "/", ":", "*", "?", '"', "<", ">", "|"]
        for char in invalid_chars:
            filename = filename.replace(char, "")
        # 移除结尾的句点和空格（Windows不允许）
        filename = filename.rstrip(". ")
        return filename

    def handle_ffmpeg_operations(self, video_path, audio_path, output_path):
        """处理FFmpeg操作，包含缓存逻辑"""
        # 检查文件是否存在
        if not os.path.exists(video_path):
            print(f"错误：视频文件不存在 - {video_path}")
            return
        if not os.path.exists(audio_path):
            print(f"错误：音频文件不存在 - {audio_path}")
            return

        # 确保输出目录存在
        output_dir = os.path.dirname(output_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # 检查文件是否在C盘
        video_on_c = self.is_on_c_drive(video_path)
        audio_on_c = self.is_on_c_drive(audio_path)
        output_on_c = self.is_on_c_drive(output_path)

        # 如果任意文件不在C盘，使用缓存
        if not (video_on_c and audio_on_c and output_on_c):
            # ====== 关键修复1：使用唯一临时目录名 ======
            temp_dir = tempfile.mkdtemp(
                prefix=f"merge_{int(time.time())}_{os.getpid()}_{uuid.uuid4().hex}_",
                dir=self.cache_root,
            )
            try:
                print(f"创建缓存目录: {temp_dir}")

                # 复制文件到缓存
                temp_video = self.copy_to_cache(video_path, temp_dir)
                temp_audio = self.copy_to_cache(audio_path, temp_dir)
                temp_output = os.path.join(temp_dir, os.path.basename(output_path))

                # 执行合并（使用缓存中的文件）
                self.handle_ffmpeg_merge(temp_video, temp_audio, temp_output)

                # ====== 关键修复2：确保文件句柄已释放 ======
                self.ensure_file_released(temp_video)
                self.ensure_file_released(temp_audio)

                # 将结果复制回输出路径
                if os.path.exists(temp_output):
                    print(f"复制结果到: {output_path}")
                    shutil.copy2(temp_output, output_path)
                else:
                    raise FileNotFoundError(f"合并结果不存在: {temp_output}")

            except Exception as e:
                print(f"缓存处理出错: {str(e)}")
                raise
            finally:
                # ====== 关键修复3：智能清理缓存 ======
                self.cleanup_cache_safely(temp_dir)
        else:
            # 直接合并（所有文件都在C盘）
            self.handle_ffmpeg_merge(video_path, audio_path, output_path)

    def is_on_c_drive(self, path):
        """检查路径是否在C盘"""
        if os.name != "nt":
            return True  # 非Windows系统默认返回True

        drive = os.path.splitdrive(os.path.abspath(path))[0].lower()
        return drive == "c:"

    def copy_to_cache(self, source_path, cache_dir):
        """将文件复制到缓存目录，返回缓存中的路径"""
        filename = os.path.basename(source_path)
        dest_path = os.path.join(cache_dir, filename)

        print(f"复制文件到缓存: {source_path} -> {dest_path}")
        shutil.copy2(source_path, dest_path)
        return dest_path

    def ensure_file_released(self, file_path, max_attempts=5, delay=0.5):
        """确保文件句柄已释放"""
        for i in range(max_attempts):
            try:
                # 尝试以只读模式打开文件
                with open(file_path, "rb") as f:
                    f.seek(0)
                # 能成功打开说明文件已释放
                return
            except Exception as e:
                if i < max_attempts - 1:
                    print(f"文件 {file_path} 仍被占用，等待 {delay} 秒后重试...")
                    time.sleep(delay)
                else:
                    print(f"警告：无法释放文件 {file_path}，可能影响后续操作")

    def cleanup_cache_safely(self, cache_dir):
        """安全清理缓存目录，带重试机制"""
        if not os.path.exists(cache_dir):
            return

        print(f"开始清理缓存目录: {cache_dir}")

        # 先尝试释放目录中所有文件
        for root, _, files in os.walk(cache_dir, topdown=False):
            for file in files:
                file_path = os.path.join(root, file)
                self.ensure_file_released(file_path)

        # 尝试清理目录
        max_retries = 5
        for i in range(max_retries):
            try:
                shutil.rmtree(cache_dir)
                print(f"成功清理缓存目录: {cache_dir}")
                return
            except Exception as e:
                if "being used by another process" in str(e) or (
                    os.name == "nt" and hasattr(e, "winerror") and e.winerror == 32
                ):
                    wait_time = (i + 1) * 0.5  # 递增等待时间
                    print(
                        f"清理缓存尝试 {i+1}/{max_retries} 失败: 文件被占用，等待 {wait_time:.1f} 秒后重试..."
                    )
                    time.sleep(wait_time)
                else:
                    print(f"清理缓存失败 (非占用错误): {str(e)}")
                    break
        else:
            # 所有重试都失败
            print(f"警告: 无法完全清理缓存目录 {cache_dir}，可能残留临时文件")

    def handle_ffmpeg_merge(self, video_path, audio_path, output_path):
        """执行实际的FFmpeg合并操作"""
        # 关键修复1：将路径转换为UTF-8编码的字节串
        video_path_utf8 = video_path.encode("utf-8")
        audio_path_utf8 = audio_path.encode("utf-8")
        output_path_utf8 = output_path.encode("utf-8")

        # 关键修复2：获取FFmpeg路径
        ffmpeg_path = self.find_ffmpeg(os.path.dirname(os.path.realpath(__file__)))
        if not ffmpeg_path:
            print("错误：未找到ffmpeg可执行文件")
            return

        # 关键修复3：直接使用字节串构建命令（避免编码转换问题）
        command = [
            ffmpeg_path.encode("utf-8"),
            b"-i",
            video_path_utf8,
            b"-i",
            audio_path_utf8,
            b"-c",
            b"copy",
            b"-map",
            b"0:v:0",
            b"-map",
            b"1:a:0",
            b"-y",
            output_path_utf8,
        ]

        # 打印实际执行的命令（用于调试）
        print(
            f"执行命令: {' '.join([arg.decode("utf-8", errors="replace") for arg in command])}"
        )

        self.execute_ffmpeg_command(command, output_path)

    def execute_ffmpeg_command(self, command, output_path):
        # 关键修复4：使用STARTUPINFO隐藏控制台窗口（Windows专属）
        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0  # 隐藏窗口

        # 关键修复5：使用字节串调用，避免编码问题
        # 移除shell=True，直接传递字节串命令
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            startupinfo=startupinfo,
        )

        # 实时读取并打印 FFmpeg 的输出（使用UTF-8解码）
        while True:
            line = process.stderr.readline()
            if not line:
                break
            try:
                # 尝试用UTF-8解码
                print(line.decode("utf-8", errors="replace").strip())
            except:
                # 失败则用系统编码
                print(
                    line.decode(sys.getfilesystemencoding(), errors="replace").strip()
                )

        # 等待 ffmpeg 进程结束
        process.wait()

        if process.returncode == 0:
            print(f"文件 {output_path} 合并成功！")
        else:
            print(f"合并 {output_path} 失败！错误码：{process.returncode}")
            # 打印完整的错误信息
            try:
                stderr = process.stderr.read().decode("utf-8", errors="replace")
            except:
                stderr = process.stderr.read().decode(
                    sys.getfilesystemencoding(), errors="replace"
                )
            if stderr:
                print("FFmpeg 详细错误信息:")
                print(stderr)
            raise RuntimeError(f"FFmpeg合并失败: {stderr}")

    def download_ffmpeg(self, url, destination_folder):
        response = requests.get(url, stream=True)
        response.raise_for_status()

        total_size_in_bytes = int(response.headers.get("content-length", 0))
        block_size = 1024  # 1 Kibibyte
        progress_bar = tqdm(total=total_size_in_bytes, unit="iB", unit_scale=True)

        with open("ffmpeg.zip", "wb") as file:
            for data in response.iter_content(block_size):
                progress_bar.update(len(data))
                file.write(data)

        progress_bar.close()
        if total_size_in_bytes != 0 and progress_bar.n != total_size_in_bytes:
            raise Exception("错误，下载出现问题")

        # 解压 ffmpeg 到指定文件夹
        with zipfile.ZipFile("ffmpeg.zip", "r") as zip_ref:
            zip_ref.extractall(destination_folder)

        # 清理临时文件
        os.remove("ffmpeg.zip")

    def find_ffmpeg(self, start_path):
        # 遍历 start_path 及其子目录寻找 ffmpeg.exe
        for dirpath, dirnames, filenames in os.walk(start_path):
            for filename in fnmatch.filter(filenames, "ffmpeg.exe"):
                ffmpeg_path = os.path.join(dirpath, filename)
                # 返回规范化路径
                return os.path.normpath(ffmpeg_path)
        return None

    def detect_ffmpeg(self):
        current_dir = os.path.dirname(os.path.realpath(__file__))
        ffmpeg_path = self.find_ffmpeg(current_dir)
        if ffmpeg_path is None:
            return False
        try:
            # 关键修复6：使用字节串调用版本检查
            result = subprocess.run(
                [ffmpeg_path.encode("utf-8"), b"-version"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"FFmpeg检测失败: {str(e)}")
            return False

    def ensure_ffmpeg_installed(self, base_dir):
        if not self.detect_ffmpeg():
            print("未找到 ffmpeg。尝试下载...")
            ffmpeg_folder = os.path.join(base_dir, "ffmpeg")
            if not os.path.exists(ffmpeg_folder):
                os.makedirs(ffmpeg_folder)

            url = "https://ghproxy.vip/https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
            self.download_ffmpeg(url, ffmpeg_folder)
            print("ffmpeg 已下载并解压完成。")


if __name__ == "__main__":
    # ====== 关键修复：高 DPI 缩放支持 ======
    if os.name == "nt":
        # 1. 启用高 DPI 感知（进程级）
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except:
            pass  # 兼容旧版 Windows

        # 2. 获取系统 DPI 缩放比例
        try:
            # 获取主显示器的 DPI
            hdc = ctypes.windll.user32.GetDC(0)
            dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # 88 = LOGPIXELSX
            ctypes.windll.user32.ReleaseDC(0, hdc)

            # 计算缩放因子 (DPI / 96)
            scaling_factor = dpi / 96.0

            # 3. 创建 Tkinter 窗口
            root = Tk()

            # 4. 设置 Tkinter 的缩放比例
            if scaling_factor > 1.0:
                # 应用缩放因子到所有 Tkinter 控件
                root.tk.call("tk", "scaling", scaling_factor)

            # 5. 设置窗口大小和位置（可选，但推荐）
            window_width = int(500 * scaling_factor)
            window_height = int(400 * scaling_factor)
            screen_width = root.winfo_screenwidth()
            screen_height = root.winfo_screenheight()
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            root.geometry(f"{window_width}x{window_height}+{x}+{y}")

        except Exception as e:
            print(f"高 DPI 设置失败，使用默认设置: {str(e)}")
            root = Tk()
    else:
        root = Tk()

    # ====== 增强 UI 可读性 ======
    # 设置默认字体大小（根据缩放比例调整）
    default_font_size = (
        max(10, int(10 * scaling_factor)) if "scaling_factor" in locals() else 10
    )
    root.option_add("*Font", f"Helvetica {default_font_size}")

    # 设置按钮和标签的内边距
    root.option_add("*Button.pad", 10)
    root.option_add("*Label.pad", 5)

    # 创建 GUI
    gui = FFMPEGMergerGUI(root)
    root.mainloop()
