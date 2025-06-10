import subprocess
import os
from pathlib import Path

# 设置 FFmpeg 固定路径
FFMPEG_PATH = r"D:\fzwork\ffmpeg-2023-11-05-git-44a0148fad-essentials_build\bin"
FFMPEG_EXE = os.path.join(FFMPEG_PATH, "ffmpeg.exe")

# 将 FFmpeg 路径添加到系统环境变量
os.environ["PATH"] = FFMPEG_PATH + os.pathsep + os.environ["PATH"]

def download_video(url, output_path):
    """下载视频、音频和字幕"""
    try:
        os.makedirs(output_path, exist_ok=True)
        
        command = [
            'yt-dlp',
            url,
            '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            '--write-sub',
            '--sub-lang', 'zh-Hans,ja',
            '--convert-subs', 'srt',
            '-o', os.path.join(output_path, '%(title)s.%(ext)s'),
            '--merge-output-format', 'mp4',
            # 指定 FFmpeg 位置
            '--ffmpeg-location', FFMPEG_PATH
        ]
        
        print("开始下载视频...")
        subprocess.run(command, check=True)
        print("视频下载完成！")
        
        return True
    except Exception as e:
        print(f"下载出错: {str(e)}")
        return False

def cut_video(input_file, output_file, duration=300):
    """截取视频的前5分钟"""
    try:
        command = [
            FFMPEG_EXE,  # 使用完整的 FFmpeg 路径
            '-i', input_file,
            '-t', str(duration),
            '-c', 'copy',
            output_file,
            '-y'
        ]
        
        print("开始截取视频...")
        print(f"执行命令: {' '.join(command)}")  # 打印完整命令便于调试
        subprocess.run(command, check=True)
        print("视频截取完成！")
        
        return True
    except Exception as e:
        print(f"截取视频出错: {str(e)}")
        return False

def extract_audio(input_file, output_file):
    """从视频中提取音频为MP3格式"""
    try:
        command = [
            FFMPEG_EXE,  # 使用完整的 FFmpeg 路径
            '-i', input_file,
            '-vn',
            '-acodec', 'libmp3lame',
            '-q:a', '2',
            output_file,
            '-y'
        ]
        
        print("开始提取音频...")
        print(f"执行命令: {' '.join(command)}")  # 打印完整命令便于调试
        subprocess.run(command, check=True)
        print("音频提取完成！")
        
        return True
    except Exception as e:
        print(f"提取音频出错: {str(e)}")
        return False

def process_video(url, output_path):
    """完整的处理流程"""
    try:
        # 验证 FFmpeg 是否可用
        subprocess.run([FFMPEG_EXE, '-version'], capture_output=True, check=True)
        print("FFmpeg 验证成功！")
    except Exception as e:
        print(f"FFmpeg 错误: {e}")
        print(f"请确认 FFmpeg 路径是否正确: {FFMPEG_PATH}")
        return

    # 创建所需的目录
    output_path = Path(output_path)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 1. 下载视频
    if not download_video(url, str(output_path)):
        return
    
    # 获取下载的视频文件
    video_files = list(output_path.glob("*.mp4"))
    if not video_files:
        print("未找到下载的视频文件！")
        return
    
    input_video = str(video_files[0])
    video_name = video_files[0].stem
    
    # 2. 截取视频
    cut_video_path = output_path / f"{video_name}_5min.mp4"
    if not cut_video(input_video, str(cut_video_path)):
        return
    
    # 3. 提取音频
    audio_path = output_path / f"{video_name}_5min.mp3"
    if not extract_audio(str(cut_video_path), str(audio_path)):
        return
    
    print("\n所有处理完成！")
    print(f"原始视频: {input_video}")
    print(f"截取的视频: {cut_video_path}")
    print(f"提取的音频: {audio_path}")

def verify_environment():
    """验证环境配置"""
    print("\n=== 环境检查 ===")
    
    # 检查 FFmpeg
    try:
        result = subprocess.run(
            [FFMPEG_EXE, '-version'],
            capture_output=True,
            text=True,
            check=True
        )
        print("FFmpeg 已找到：")
        print(result.stdout.split('\n')[0])  # 只打印第一行版本信息
    except Exception as e:
        print(f"FFmpeg 检查失败: {e}")
        print(f"FFmpeg 路径: {FFMPEG_EXE}")
        return False

    # 检查 yt-dlp
    try:
        result = subprocess.run(
            ['yt-dlp', '--version'],
            capture_output=True,
            text=True,
            check=True
        )
        print(f"yt-dlp 版本: {result.stdout.strip()}")
    except Exception as e:
        print(f"yt-dlp 检查失败: {e}")
        print("请确保已安装 yt-dlp (pip install yt-dlp)")
        return False

    print("环境检查完成！")
    print("================")
    return True

if __name__ == "__main__":
    # 首先验证环境
    if not verify_environment():
        print("环境验证失败，请检查配置！")
        exit(1)

    # 设置视频 URL 和输出目录
    video_url = input("请输入YouTube视频URL: ").strip()
    output_directory = r"D:\fzwork\ai\mp3sub\video_output"  # 可以根据需要修改输出目录
    
    print(f"\n视频将保存到: {output_directory}")
    proceed = input("是否继续？(y/n): ").strip().lower()
    
    if proceed == 'y':
        process_video(video_url, output_directory)
    else:
        print("操作已取消")