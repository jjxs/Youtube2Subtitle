import os
import subprocess
from pathlib import Path
import shutil
import tempfile
import re
FFMPEG_PATH = r"D:\fzwork\ffmpeg-2023-11-05-git-44a0148fad-essentials_build\bin"
os.environ["PATH"] += os.pathsep + FFMPEG_PATH
def find_matching_files(directory):
    # 支持的视频格式
    video_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.wmv'}
    # 支持的字幕格式
    subtitle_extensions = {'.srt', '.ass', '.ssa'}
    
    videos = []
    subtitles = []
    
    # 遍历目录下的所有文件
    for file in os.listdir(directory):
        path = os.path.join(directory, file)
        if os.path.isfile(path):
            ext = os.path.splitext(file)[1].lower()
            if ext in video_extensions:
                videos.append(path)
            elif ext in subtitle_extensions:
                subtitles.append(path)
    
    # 匹配视频和字幕文件
    matches = []
    for video in videos:
        video_name = os.path.splitext(os.path.basename(video))[0]
        matching_sub = None
        
        # 查找匹配的字幕文件
        for subtitle in subtitles:
            sub_name = os.path.splitext(os.path.basename(subtitle))[0]
            if video_name == sub_name:
                matching_sub = subtitle
                break
        
        if matching_sub:
            matches.append((video, matching_sub))
    
    return matches

def parse_srt_time(time_str):
    """将SRT时间格式转换为秒"""
    # 格式: 00:00:20,000
    time_str = time_str.replace(',', '.')
    parts = time_str.split(':')
    hours = int(parts[0])
    minutes = int(parts[1])
    seconds = float(parts[2])
    return hours * 3600 + minutes * 60 + seconds

def parse_srt_file(srt_path):
    """解析SRT字幕文件"""
    subtitles = []
    
    try:
        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        try:
            with open(srt_path, 'r', encoding='gbk') as f:
                content = f.read()
        except:
            with open(srt_path, 'r', encoding='latin-1') as f:
                content = f.read()
    
    # 分割字幕块
    blocks = re.split(r'\n\s*\n', content.strip())
    
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) >= 3:
            # 第一行是序号
            # 第二行是时间
            time_line = lines[1]
            if '-->' in time_line:
                times = time_line.split(' --> ')
                start_time = parse_srt_time(times[0].strip())
                end_time = parse_srt_time(times[1].strip())
                
                # 第三行及以后是字幕文本
                text = ' '.join(lines[2:]).strip()
                # 清理HTML标签
                text = re.sub(r'<[^>]+>', '', text)
                
                if text:
                    subtitles.append({
                        'start': start_time,
                        'end': end_time,
                        'text': text
                    })
    
    return subtitles

def create_drawtext_filter(subtitles):
    """创建drawtext滤镜链"""
    if not subtitles:
        return "null"
    
    filters = []
    for i, sub in enumerate(subtitles):
        # 转义特殊字符
        text = sub['text'].replace("'", "\\'").replace(":", "\\:")
        text = text.replace("[", "\\[").replace("]", "\\]")
        
        filter_str = f"drawbox=x=0:y=h*3/4:w=iw:h=ih/4:color=black@0.5,drawtext=text='{text}':fontsize=40:fontcolor=white:x=(w-text_w)/2:y=h*3/4+(h/4-text_h)/2:enable='between(t,{sub['start']},{sub['end']})'"
        filters.append(filter_str)
    
    # 将所有drawtext滤镜连接起来
    if len(filters) == 1:
        return filters[0]
    else:
        # 创建滤镜链
        result = filters[0]
        for i in range(1, len(filters)):
            result += f",{filters[i]}"
        return result

def merge_video_subtitle(video_path, subtitle_path, output_path):
    """合并视频和字幕"""
    try:
        print("正在解析字幕文件...")
        subtitles = parse_srt_file(subtitle_path)
        print(f"找到 {len(subtitles)} 条字幕")
        
        if not subtitles:
            print("字幕文件为空或解析失败")
            return False
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_video = os.path.join(temp_dir, "input.mp4")
            temp_output = os.path.join(temp_dir, "output.mp4")
            
            # 复制视频文件
            shutil.copy2(video_path, temp_video)
            
            # 创建drawtext滤镜
            drawtext_filter = create_drawtext_filter(subtitles)
            
            print("正在合并视频和字幕...")
            
            # 使用drawtext滤镜添加字幕
            cmd = [
                'ffmpeg', 
                '-i', temp_video,
                '-vf', drawtext_filter,
                '-c:a', 'copy',
                '-c:v', 'libx264',
                '-preset', 'fast',
                temp_output,
                '-y'
            ]
            
            # 执行命令
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                # 复制结果文件到目标位置
                shutil.copy2(temp_output, output_path)
                return True
            else:
                print(f"FFmpeg错误: {result.stderr}")
                # 尝试备用方法：分批处理字幕
                return merge_video_subtitle_batch(video_path, subtitles, output_path)
                
    except Exception as e:
        print(f"处理错误: {str(e)}")
        return False

def merge_video_subtitle_batch(video_path, subtitles, output_path):
    """分批处理字幕（备用方法）"""
    try:
        print("尝试分批处理字幕...")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_video = os.path.join(temp_dir, "input.mp4")
            temp_output = os.path.join(temp_dir, "output.mp4")
            
            shutil.copy2(video_path, temp_video)
            
            # 每次处理10条字幕
            batch_size = 10
            current_input = temp_video
            
            for i in range(0, len(subtitles), batch_size):
                batch = subtitles[i:i+batch_size]
                batch_output = os.path.join(temp_dir, f"batch_{i}.mp4")
                
                # 为这批字幕创建滤镜
                filters = []
                for sub in batch:
                    text = sub['text'].replace("'", "\\'").replace(":", "\\:")
                    text = text.replace("[", "\\[").replace("]", "\\]")
                    filter_str = f"drawtext=text='{text}':fontcolor=white:fontsize=24:x=(w-text_w)/2:y=30:enable='between(t,{sub['start']},{sub['end']})'"
                    filters.append(filter_str)
                
                drawtext_filter = ','.join(filters)
                
                cmd = [
                    'ffmpeg', 
                    '-i', current_input,
                    '-vf', drawtext_filter,
                    '-c:a', 'copy',
                    '-c:v', 'libx264',
                    '-preset', 'ultrafast',
                    batch_output,
                    '-y'
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode != 0:
                    print(f"批次 {i//batch_size + 1} 处理失败")
                    return False
                
                current_input = batch_output
                print(f"完成批次 {i//batch_size + 1}/{(len(subtitles) + batch_size - 1) // batch_size}")
            
            # 复制最终结果
            shutil.copy2(current_input, output_path)
            return True
            
    except Exception as e:
        print(f"分批处理错误: {str(e)}")
        return False

def safe_filename(filename):
    """生成安全的文件名"""
    unsafe_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|', '⧸']
    safe_name = filename
    for char in unsafe_chars:
        safe_name = safe_name.replace(char, '_')
    return safe_name

def main():
    # 获取用户输入的目录路径
    directory = input("请输入要处理的文件夹路径: ").strip()
    
    # 去除可能的引号
    if directory.startswith('"') and directory.endswith('"'):
        directory = directory[1:-1]
    
    # 确保目录存在
    if not os.path.isdir(directory):
        print("指定的文件夹不存在！")
        return
    
    # 找到匹配的视频和字幕文件
    matches = find_matching_files(directory)
    
    if not matches:
        print("没有找到匹配的视频和字幕文件！")
        return
    
    print(f"找到 {len(matches)} 对匹配的文件")
    
    # 处理每对匹配的文件
    for i, (video_path, subtitle_path) in enumerate(matches, 1):
        # 创建输出文件名
        video_name = os.path.splitext(os.path.basename(video_path))[0]
        safe_name = safe_filename(video_name)
        output_path = os.path.join(directory, f"{safe_name}_with_subtitle.mp4")
        
        print(f"\n[{i}/{len(matches)}] 处理文件: {video_name}")
        print(f"视频: {os.path.basename(video_path)}")
        print(f"字幕: {os.path.basename(subtitle_path)}")
        print(f"输出: {os.path.basename(output_path)}")
        
        if merge_video_subtitle(video_path, subtitle_path, output_path):
            print("✓ 合并成功！完整字幕已添加到视频顶部")
        else:
            print("✗ 合并失败！")

if __name__ == "__main__":
    main()