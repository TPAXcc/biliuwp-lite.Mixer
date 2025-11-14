import os
import json
import subprocess
import requests
import concurrent.futures
import zipfile
import fnmatch
from tkinter import Tk, Button, Label, StringVar, filedialog
from tqdm import tqdm
import sys
import ctypes

class FFMPEGMergerGUI:
    def __init__(self, master):
        self.master = master
        master.title("FFMPEG 视频音频合并工具")
        
        self.label = Label(master, text="请选择包含视频和音频文件的文件夹:")
        self.label.pack()

        self.folder_path_var = StringVar()
        self.folder_path_label = Label(master, textvariable=self.folder_path_var)
        self.folder_path_label.pack()

        self.select_button = Button(master, text="选择文件夹", command=self.select_folder)
        self.select_button.pack()

        self.merge_button = Button(master, text="开始合并", command=self.start_merge)
        self.merge_button.pack()

        # 新增输出路径标签和按钮
        self.output_path_label = Label(master, text="请选择输出文件夹:")
        self.output_path_label.pack()

        self.output_path_var = StringVar()
        self.output_path_label = Label(master, textvariable=self.output_path_var)
        self.output_path_label.pack()

        self.select_output_button = Button(master, text="选择输出文件夹", command=self.select_output_folder)
        self.select_output_button.pack()

        # 设置默认输出路径
        default_output_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "导出视频")
        if not os.path.exists(default_output_dir):
            os.makedirs(default_output_dir)
        self.output_path_var.set(default_output_dir)

        # 立即检查并下载 FFmpeg，并传递当前脚本所在目录
        current_dir = os.path.dirname(os.path.realpath(__file__))
        self.ensure_ffmpeg_installed(current_dir)
        
        # 关键修复：设置FFmpeg使用UTF-8路径
        os.environ["FFMPEG_UTF8_PATHS"] = "1"

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
            tasks = []
            for root, dirs, files in os.walk(base_dir):
                if 'info.json' in files:
                    info_path = os.path.join(root, 'info.json')
                    try:
                        # 使用系统默认编码读取JSON文件（解决中文路径问题）
                        with open(info_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        
                        # 检查必要的字段是否存在
                        if ('VideoPath' in data and 
                            isinstance(data['VideoPath'], list) and 
                            len(data['VideoPath']) >= 2 and
                            'EpisodeTitle' in data):
                            
                            # 获取Index字段（如果不存在则使用0）
                            index = str(data.get('Index', '0')).strip()
                            # 确保Index是数字格式，如果不是则使用0
                            if not index.isdigit():
                                index = '0'
                            
                            # 规范化路径 - 关键修复！
                            video_file = os.path.normpath(os.path.join(root, data['VideoPath'][0]))
                            audio_file = os.path.normpath(os.path.join(root, data['VideoPath'][1]))
                            episode_title = data['EpisodeTitle']
                            
                            # 处理文件名中的非法字符（Windows文件名不允许使用某些字符）
                            episode_title = self.sanitize_filename(episode_title)
                            
                            # 修改输出文件名格式：P Index EpisodeTitle.mp4
                            output_file = os.path.normpath(os.path.join(output_dir, f"P{index} {episode_title}.mp4"))

                            # 添加到任务列表
                            tasks.append((video_file, audio_file, output_file))
                    except json.JSONDecodeError:
                        print(f"警告：{info_path} 文件格式错误，跳过处理")
                    except Exception as e:
                        print(f"处理 {info_path} 时出错: {str(e)}")

            # 使用线程池来并发处理所有任务
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = [executor.submit(self.handle_ffmpeg_operations, *task) for task in tasks]
                concurrent.futures.wait(futures)

            self.label.config(text="合并完成！")
        else:
            self.label.config(text="请先选择文件夹！")

    def sanitize_filename(self, filename):
        """移除Windows文件名中的非法字符"""
        # Windows文件名不允许的字符: \ / : * ? " < > |
        invalid_chars = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']
        for char in invalid_chars:
            filename = filename.replace(char, '')
        # 移除结尾的句点和空格（Windows不允许）
        filename = filename.rstrip('. ')
        return filename

    def handle_ffmpeg_operations(self, video_path, audio_path, output_path):
        # 检查文件是否存在
        if not os.path.exists(video_path):
            print(f"错误：视频文件不存在 - {video_path}")
            return
        if not os.path.exists(audio_path):
            print(f"错误：音频文件不存在 - {audio_path}")
            return
        
        # 关键修复1：将路径转换为UTF-8编码的字节串
        # 这是解决中文路径问题的核心
        video_path_utf8 = video_path.encode('utf-8')
        audio_path_utf8 = audio_path.encode('utf-8')
        output_path_utf8 = output_path.encode('utf-8')
        
        # 关键修复2：获取FFmpeg路径
        ffmpeg_path = self.find_ffmpeg(os.path.dirname(os.path.realpath(__file__)))
        if not ffmpeg_path:
            print("错误：未找到ffmpeg可执行文件")
            return
        
        # 关键修复3：直接使用字节串构建命令（避免编码转换问题）
        command = [
            ffmpeg_path.encode('utf-8'), 
            b"-i", video_path_utf8, 
            b"-i", audio_path_utf8,
            b"-c", b"copy", 
            b"-map", b"0:v:0", 
            b"-map", b"1:a:0",
            b"-y", 
            output_path_utf8
        ]
        
        # 打印实际执行的命令（用于调试）
        print(f"执行命令: {' '.join([arg.decode('utf-8', errors='replace') for arg in command])}")
        
        self.execute_ffmpeg_command(command, output_path)

    def execute_ffmpeg_command(self, command, output_path):
        # 关键修复4：使用STARTUPINFO隐藏控制台窗口（Windows专属）
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0  # 隐藏窗口

        # 关键修复5：使用字节串调用，避免编码问题
        # 移除shell=True，直接传递字节串命令
        process = subprocess.Popen(
            command, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            startupinfo=startupinfo
        )
        
        # 实时读取并打印 FFmpeg 的输出（使用UTF-8解码）
        while True:
            line = process.stderr.readline()
            if not line:
                break
            try:
                # 尝试用UTF-8解码
                print(line.decode('utf-8', errors='replace').strip())
            except:
                # 失败则用系统编码
                print(line.decode(sys.getfilesystemencoding(), errors='replace').strip())
        
        # 等待 ffmpeg 进程结束
        process.wait()
        
        if process.returncode == 0:
            print(f"文件 {output_path} 合并成功！")
        else:
            print(f"合并 {output_path} 失败！错误码：{process.returncode}")
            # 打印完整的错误信息
            try:
                stderr = process.stderr.read().decode('utf-8', errors='replace')
            except:
                stderr = process.stderr.read().decode(sys.getfilesystemencoding(), errors='replace')
            if stderr:
                print("FFmpeg 详细错误信息:")
                print(stderr)

    def download_ffmpeg(self, url, destination_folder):
        response = requests.get(url, stream=True)
        response.raise_for_status()

        total_size_in_bytes = int(response.headers.get('content-length', 0))
        block_size = 1024  # 1 Kibibyte
        progress_bar = tqdm(total=total_size_in_bytes, unit='iB', unit_scale=True)

        with open('ffmpeg.zip', 'wb') as file:
            for data in response.iter_content(block_size):
                progress_bar.update(len(data))
                file.write(data)

        progress_bar.close()
        if total_size_in_bytes != 0 and progress_bar.n != total_size_in_bytes:
            raise Exception("错误，下载出现问题")

        # 解压 ffmpeg 到指定文件夹
        with zipfile.ZipFile('ffmpeg.zip', 'r') as zip_ref:
            zip_ref.extractall(destination_folder)

        # 清理临时文件
        os.remove('ffmpeg.zip')

    def find_ffmpeg(self, start_path):
        # 遍历 start_path 及其子目录寻找 ffmpeg.exe
        for dirpath, dirnames, filenames in os.walk(start_path):
            for filename in fnmatch.filter(filenames, 'ffmpeg.exe'):
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
                [ffmpeg_path.encode('utf-8'), b"-version"], 
                check=True, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE
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
    root = Tk()
    gui = FFMPEGMergerGUI(root)
    root.mainloop()
