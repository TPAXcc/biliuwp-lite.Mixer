import os
import re
import json
import subprocess
import concurrent.futures
import shutil
import zipfile
import fnmatch
from tqdm import tqdm
from tkinter import Tk, Button, Label, StringVar, filedialog, messagebox, Listbox, Scrollbar, Frame, Toplevel, END

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
        
        if not base_dir or not output_dir:
            self.label.config(text="请先选择输入和输出文件夹！")
            return

        root_info_json_path = os.path.join(base_dir, 'info.json')
        
        if not os.path.isfile(root_info_json_path):
            self.label.config(text="根目录下的 info.json 文件不存在！")
            return

        with open(root_info_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if 'Title' not in data:
            self.label.config(text="根目录下的 info.json 缺少 Title 字段！")
            return

        # 正确初始化 episode_title
        episode_title = data['Title']

        # 定义要被替换的非法字符列表
        illegal_chars = ['/', ':', '[', '\\', '*', '?', '"', '<', '>', '|', ']']

        # 使用循环遍历非法字符并替换
        for char in illegal_chars:
            episode_title = episode_title.replace(char, '')

        # 进一步清理标题，确保没有其他问题字符
        episode_title = re.sub(r'[^\w\s-]', '', episode_title)  # 移除非字母数字字符
        episode_title = re.sub(r'[-\s]+', '-', episode_title).strip('-')  # 替换空白和连字符为单个连字符，并去除开头和结尾的连字符

        # 检查长度，如果太长，则截断
        max_length = 245  # 假设留一些余地给路径中的其他部分
        if len(episode_title) > max_length:
            episode_title = episode_title[:max_length]

        # 使用 episode_title 创建目录
        output_subfolder = os.path.join(output_dir, episode_title)
        os.makedirs(output_subfolder, exist_ok=True)
        
        tasks = []
        confirmations = []
        for root, dirs, files in os.walk(base_dir):
            if 'info.json' in files:
                if root == base_dir:  # Skip the root level's info.json since we already read it.
                    continue
                with open(os.path.join(root, 'info.json'), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if 'VideoPath' not in data:
                        self.label.config(text=f"子目录 {root} 下的 info.json 缺少 VideoPath 字段！")
                        return
                    elif not isinstance(data['VideoPath'], list) or len(data['VideoPath']) < 2:
                        self.label.config(text=f"子目录 {root} 下的 info.json VideoPath 字段格式错误！")
                        return
                    if 'EpisodeTitle' not in data:
                        self.label.config(text=f"子目录 {root} 下的 info.json 缺少 EpisodeTitle 字段！")
                        return

                    video_file = os.path.join(root, data['VideoPath'][0])
                    audio_file = os.path.join(root, data['VideoPath'][1])

                    if not os.path.exists(video_file):
                        self.label.config(text=f"视频文件 {video_file} 不存在！")
                        return
                    elif not os.path.exists(audio_file):
                        self.label.config(text=f"音频文件 {audio_file} 不存在！")
                        return

                    output_file = os.path.join(output_subfolder, f"{data['EpisodeTitle']}.mp4")
                    
                    if os.path.exists(output_file):
                        # 获取输出文件的大小
                        output_size = os.path.getsize(output_file)
                        
                        # 计算视频和音频文件的总大小
                        source_size = os.path.getsize(video_file) + os.path.getsize(audio_file)
                        
                        # 转换大小为常见单位
                        output_size_human = self.human_readable_size(output_size)
                        source_size_human = self.human_readable_size(source_size)
                        
                        confirmations.append((output_file, source_size, output_size, source_size_human, output_size_human))
                    else:
                        tasks.append((video_file, audio_file, output_file))

        if confirmations:
            self.show_confirmation(confirmations)

        # 使用线程池来并发处理所有任务
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = []
            with tqdm(total=len(tasks), desc="正在合并文件") as pbar:
                for task in tasks:
                    future = executor.submit(self.handle_ffmpeg_operations_with_progress, task[0], task[1], task[2], pbar)
                    futures.append(future)
                concurrent.futures.wait(futures)

        self.label.config(text="合并完成！")

    def show_confirmation(self, confirmations):
        top = Toplevel(self.master)
        top.title("确认操作")

        frame = Frame(top)
        frame.pack(side="left", fill="both", expand=True)

        # 添加滚动条
        scrollbar = Scrollbar(frame)
        scrollbar.pack(side="right", fill="y")

        listbox = Listbox(frame, yscrollcommand=scrollbar.set)
        listbox.pack(side="left", fill="both", expand=True)

        # 设置滚动条的回调函数
        scrollbar.config(command=listbox.yview)

        for output_path, source_size, output_size, source_size_human, output_size_human in confirmations:
            item = f"{output_path}\n"
            item += f"  - 源文件大小：{source_size_human}\n"
            item += f"  - 输出文件大小：{output_size_human}\n\n"
            listbox.insert(END, item)

        # 添加确认按钮
        button_frame = Frame(top)
        button_frame.pack(side="bottom")

        confirm_button = Button(button_frame, text="确认", command=lambda: self.confirm_action(confirmations, top))
        confirm_button.pack(side="left")

        cancel_button = Button(button_frame, text="取消", command=top.destroy)
        cancel_button.pack(side="right")

    def confirm_action(self, confirmations, top):
        top.destroy()
        # 用户选择确认后，处理这些确认项
        tasks.extend([(conf[0], conf[1], conf[2]) for conf in confirmations])
        # 更新任务列表并重新启动合并
        self.start_merge()

    def handle_ffmpeg_operations_with_progress(self, video_path, audio_path, output_path, pbar):
        # 由于在多线程环境下，可能需要确保 ffmpeg 路径的正确性
        ffmpeg_path = self.find_ffmpeg(os.path.dirname(os.path.realpath(__file__)))
        command = [
            ffmpeg_path, "-i", video_path, "-i", audio_path,
            "-c", "copy", "-map", "0:v:0", "-map", "1:a:0",
            "-y", output_path
        ]
        self.execute_ffmpeg_command(command, output_path)
        pbar.update(1)

    def execute_ffmpeg_command(self, command, output_path):
        with open(os.devnull, "w") as f:
            process = subprocess.Popen(command, stdout=f, stderr=f)
        
            # 等待 ffmpeg 进程结束
            process.wait()
        
            if process.returncode == 0:
                print(f"文件 {output_path} 合并成功！")
            else:
                print(f"合并 {output_path} 失败！错误码：{process.returncode}")

    def human_readable_size(self, size):
        # 转换大小为常见单位
        for x in ['bytes', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return "%3.1f %s" % (size, x)
            size /= 1024.0
        return "%3.1f %s" % (size, 'TB')

    def download_ffmpeg(self, url, destination_folder):导入fnmatch
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
                return os.path.join(dirpath, filename)
        return None返回None

    def detect_ffmpeg(self):
        current_dir = os.path.dirname(os.path.realpath(__file__))
        ffmpeg_path = self.find_ffmpeg(current_dir)
        try:
            subprocess.run([ffmpeg_path, "-version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
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
