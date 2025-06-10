import subprocess
import os
from pathlib import Path
import whisper
import warnings
import torch
import json
import gc

warnings.filterwarnings("ignore")

FFMPEG_PATH = r"D:\fzwork\ffmpeg-2023-11-05-git-44a0148fad-essentials_build\bin"
os.environ["PATH"] += os.pathsep + FFMPEG_PATH

class VideoProcessor:
    def __init__(self, url, base_output_dir=None):
        self.url = url
        self.base_output_dir = Path(base_output_dir) if base_output_dir else Path(__file__).parent / "video_output"
        self.video_info = None
        self.video_dir = None
        self.setup_directories()

    def setup_directories(self):
        try:
            cmd = ['yt-dlp', '-j', self.url]
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.video_info = json.loads(result.stdout)
            
            safe_title = "".join(c for c in self.video_info['title'] if c.isalnum() or c in (' ', '-', '_'))
            self.video_dir = self.base_output_dir / safe_title
            self.video_dir.mkdir(parents=True, exist_ok=True)
            (self.video_dir / "subtitles").mkdir(exist_ok=True)
            
            print(f"创建目录: {self.video_dir}")
            return True
        except Exception as e:
            print(f"设置目录时出错: {e}")
            return False

    def download_video_and_thumbnail(self):
        try:
            command = [
                'yt-dlp',
                self.url,
                '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                '--write-sub',
                '--sub-lang', 'zh-Hans,ja',
                '--convert-subs', 'srt',
                '--write-thumbnail',
                '-o', str(self.video_dir / '%(title)s.%(ext)s'),
                '--merge-output-format', 'mp4',
                '--ffmpeg-location', FFMPEG_PATH
            ]
            
            print("\n开始下载视频和封面...")
            subprocess.run(command, check=True)
            video_file = next(self.video_dir.glob("*.mp4"))
            return str(video_file)
        except Exception as e:
            print(f"下载出错: {str(e)}")
            return None

    def cut_video(self, input_video, start_time, end_time=None):
        try:
            output_video = self.video_dir / f"{Path(input_video).stem}_cut.mp4"
            command = [
                os.path.join(FFMPEG_PATH, "ffmpeg"),
                '-i', input_video,
                '-ss', start_time,
            ]
            
            if end_time:
                command.extend(['-to', end_time, '-c', 'copy'])
            else:
                command.extend(['-c', 'copy'])
                
            command.extend([str(output_video), '-y'])
            
            print(f"\n截取视频 ({start_time} - {end_time if end_time else '结束'})...")
            subprocess.run(command, check=True)
            return str(output_video)
        except Exception as e:
            print(f"截取视频出错: {str(e)}")
            return None

    def extract_audio(self, input_video):
        try:
            output_audio = self.video_dir / f"{Path(input_video).stem}.mp3"
            command = [
                os.path.join(FFMPEG_PATH, "ffmpeg"),
                '-i', input_video,
                '-vn',
                '-acodec', 'libmp3lame',
                '-q:a', '2',
                str(output_audio),
                '-y'
            ]
            
            print("\n提取音频中...")
            subprocess.run(command, check=True)
            return str(output_audio)
        except Exception as e:
            print(f"提取音频出错: {str(e)}")
            return None

    def generate_subtitle(self, audio_file):
        try:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            model_size = "medium" if torch.cuda.is_available() else "tiny"
            model = whisper.load_model(model_size, device=device)
            
            transcription_params = {
                'language': "ja",
                'fp16': torch.cuda.is_available(),
                'temperature': 0.0,
                'beam_size': 5,
                'best_of': 5,
                'word_timestamps': True,
                'initial_prompt': "日语音频转录。"
            }
            
            result = model.transcribe(audio_file, **transcription_params)
            srt_path = self.video_dir / "subtitles" / f"{Path(audio_file).stem}.srt"
            
            with open(srt_path, "w", encoding="utf-8") as f:
                segments = []
                for i, segment in enumerate(result["segments"], start=1):
                    start = self.format_timestamp(segment["start"])
                    end = self.format_timestamp(segment["end"])
                    text = segment["text"].strip()
                    segments.append(f"{i}\n{start} --> {end}\n{text}\n")
                f.write("\n".join(segments))
            
            return str(srt_path)
        except Exception as e:
            print(f"生成字幕时出错: {str(e)}")
            return None
        finally:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            gc.collect()

    @staticmethod
    def format_timestamp(seconds):
        total_seconds = int(seconds)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},000"

def main():
    try:
        print("\n=== YouTube视频处理工具 ===")
        url = input("\n请输入YouTube视频URL: ").strip()
        want_cut = input("\n是否需要截取视频片段？(y/n): ").lower() == 'y'
        
        cut_params = {}
        if want_cut:
            start = input("开始时间 (HH:MM:SS，留空从开头): ").strip()
            end = input("结束时间 (HH:MM:SS，留空到结尾): ").strip()
            cut_params['start_time'] = start if start else "00:00:00"
            cut_params['end_time'] = end if end else None

        processor = VideoProcessor(url)
        video_file = processor.download_video_and_thumbnail()
        
        if want_cut and video_file:
            video_file = processor.cut_video(video_file, **cut_params)
        
        if video_file:
            audio_file = processor.extract_audio(video_file)
            if audio_file:
                processor.generate_subtitle(audio_file)
        
        print(f"\n处理完成！文件保存在: {processor.video_dir}")
        
    except Exception as e:
        print(f"\n处理出错: {e}")
    finally:
        input("\n按回车键退出...")

if __name__ == "__main__":
    main()