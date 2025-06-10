import whisper
import datetime
import os
from pathlib import Path
import warnings
import subprocess
import torch
import numpy as np
from collections import Counter

warnings.filterwarnings("ignore")

# 设置 FFmpeg 路径
os.environ["PATH"] += os.pathsep + r"D:\fzwork\ffmpeg-2023-11-05-git-44a0148fad-essentials_build\bin"

def format_timestamp(seconds):
    """优化时间戳格式转换效率"""
    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    milliseconds = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{int(seconds):02d},{milliseconds:03d}"

def create_srt(result):
    """优化SRT创建效率，减少字符串操作次数"""
    segments = []
    for i, segment in enumerate(result["segments"], start=1):
        start_time = format_timestamp(segment["start"])
        end_time = format_timestamp(segment["end"])
        text = segment["text"].strip()
        segments.append(f"{i}\n{start_time} --> {end_time}\n{text}\n")
    return "\n".join(segments)

def optimize_transcription_settings():
    """为CPU环境优化的转录参数设置"""
    return {
        'language': "ja",
        'fp16': False,  # CPU上必须关闭
        'temperature': 0.0,
        'beam_size': 2,  # 减少束搜索大小以加快速度
        'best_of': 2,   # 减少采样次数
        'patience': 1.0,
        'length_penalty': 1.0,
        'suppress_tokens': [-1],
        'initial_prompt': "日语音频转录。",
        'condition_on_previous_text': False,  # 关闭此选项可提高速度
        'compression_ratio_threshold': 2.4,
        'logprob_threshold': -1.0,
        'no_speech_threshold': 0.6,
        'word_timestamps': False  # 关闭词级时间戳可显著提高速度
    }

def process_mp3_files():
    input_dir = r"D:\fzwork\ai\mp3sub"
    output_dir = r"D:\fzwork\ai\mp3sub\srt_output"
    
    os.makedirs(output_dir, exist_ok=True)
    
    # 验证 FFmpeg
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        print("FFmpeg 验证成功！")
    except Exception as e:
        print(f"FFmpeg 错误: {e}\n请确保FFmpeg路径正确配置！")
        return

    # CPU优化设置
    device = "cpu"
    print("正在加载优化后的Whisper模型...")
    
    # 使用更小的模型以提高速度
    model_size = "tiny"  # 在CPU上推荐使用tiny或small
    model = whisper.load_model(model_size, device=device)
    
    # 获取优化的转录参数
    transcription_params = optimize_transcription_settings()
    print(f"已加载 {model_size} 模型并应用CPU优化参数设置")

    mp3_files = list(Path(input_dir).glob("*.mp3"))
    
    if not mp3_files:
        print(f"在目录 {input_dir} 中未找到MP3文件！")
        return
    
    print(f"找到 {len(mp3_files)} 个MP3文件")
    
    # 文件处理统计
    success_count = 0
    fail_count = 0
    logprobs = []
    
    # 按文件大小排序：先处理小文件以快速获得结果
    files_by_size = sorted(mp3_files, key=lambda f: f.stat().st_size)
    
    for i, audio_file in enumerate(files_by_size, 1):
        print(f"\n[{i}/{len(mp3_files)}] 正在处理: {audio_file.name} "
              f"({audio_file.stat().st_size/1024/1024:.1f} MB)")
        
        if not audio_file.exists():
            print(f"错误：文件不存在 - {audio_file}")
            fail_count += 1
            continue
            
        try:
            # 尝试多线程加速（如果您的CPU支持）
            # 注意：Windows上可能效果有限，但可能略有帮助
            torch.set_num_threads(4)  # 根据CPU核心数调整
            
            result = model.transcribe(
                str(audio_file.absolute()),
                **transcription_params
            )
            
            srt_filename = f"{audio_file.stem}.srt"
            srt_path = Path(output_dir) / srt_filename
            
            with open(srt_path, "w", encoding="utf-8") as f:
                f.write(create_srt(result))
            
            # 收集置信度信息用于统计
            file_logprobs = [seg.get("avg_logprob", 0) for seg in result["segments"]]
            if file_logprobs:
                file_avg_logprob = sum(file_logprobs) / len(file_logprobs)
                logprobs.append(file_avg_logprob)
                print(f"✓ 完成！平均置信度: {file_avg_logprob:.3f}")
            else:
                print(f"✓ 完成！未获取到置信度数据")
            
            print(f"字幕已保存到: {srt_path}")
            success_count += 1
            
        except Exception as e:
            print(f"✗ 处理失败: {str(e)}")
            print(f"出错文件: {audio_file.absolute()}")
            fail_count += 1
            
        finally:
            # 清理内存
            torch.cuda.empty_cache() if torch.cuda.is_available() else None
            gc.collect()
    
    # 打印处理统计
    print("\n" + "="*40)
    print(f"处理完成统计:")
    print(f"- 成功: {success_count}/{len(mp3_files)}")
    print(f"- 失败: {fail_count}/{len(mp3_files)}")
    
    if logprobs:
        avg_logprob = np.mean(logprobs)
        min_logprob = min(logprobs)
        max_logprob = max(logprobs)
        print(f"\n置信度分析:")
        print(f"- 平均置信度: {avg_logprob:.3f}")
        print(f"- 最低置信度: {min_logprob:.3f}")
        print(f"- 最高置信度: {max_logprob:.3f}")
    
    print(f"\n全部字幕文件保存在: {output_dir}")

if __name__ == "__main__":
    import gc  # 用于内存清理
    import time
    
    start_time = time.time()
    
    print("\n=== 系统性能优化 ===")
    print("CUDA 可用:", torch.cuda.is_available())
    print("CPU 核心数:", os.cpu_count())
    print("===================")
    
    process_mp3_files()
    
    end_time = time.time()
    print(f"\n总运行时间: {end_time - start_time:.2f} 秒")