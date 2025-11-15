# biliuwp-lite.Mixer

[![GitHub](https://img.shields.io/badge/GitHub-biliuwp--lite.Mixer-blue.svg)](https://github.com/TPAXcc/biliuwp-lite.Mixer)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 注：主包在上学，无法及时回复issues，有问题先尝试通过 [通义千问](https://tongyi.aliyun.com/) 解决


`biliuwp-lite.Mixer` 是一款轻量级的 GUI 应用程序，专为从 `biliuwp-lite` 下载的视频和音频文件进行合并而设计。该工具通过使用 FFmpeg 实现视频与音频的无缝合并，支持批量处理，使得视频后期制作更加高效便捷。

## 特点

- **图形用户界面**：直观的 UI 设计，方便用户操作。
- **自动重命名视频文件**：通过读取`info.json`实现对导出视频名。
- **批量处理**：自动检测并合并文件夹中的所有符合条件的视频和音频文件。
- **多线程处理**：利用多线程加速合并过程。
- **自动下载 FFmpeg**：如果本地环境中没有安装 FFmpeg，则自动下载并配置。

## 安装

1. 克隆此仓库：

   注：国服用户自行解决网络问题
   ```bash
   git clone https://github.com/TPAXcc/biliuwp-lite.Mixer.git
   cd biliuwp-lite.Mixercd
   ```
2. 安装依赖项：
   ```bash
   pip install -r requirements.txt
   ```

## 技术栈

- **Python**: 主要开发语言。
  - **Tkinter**: 用于创建图形用户界面。
  - **requests**: 用于网络请求。
  - **concurrent.futures**: 提供多线程支持。
  - **tqdm**: 显示进度条。
- **FFmpeg**: 用于视频和音频的编码和合并。

## 许可证

此项目采用 MIT 许可证发布，详情见 LICENSE 文件。

## 贡献

欢迎贡献代码和提出 Issue！

## 致谢

感谢社区成员的支持和贡献！

---
