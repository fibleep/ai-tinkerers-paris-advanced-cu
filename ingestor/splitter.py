import os
import subprocess

def process_video(url, output_folder="video_parts"):
    # Create output directory
    os.makedirs(output_folder, exist_ok=True)
    
    # Download video using yt-dlp
    print("Downloading video...")
    subprocess.run([
        "yt-dlp",
        "-f", "best",
        "-o", f"{output_folder}/video.mp4",
        url
    ])
    
    # Split into 15-second segments
    print("Splitting video and audio...")
    subprocess.run([
        "ffmpeg",
        "-i", f"{output_folder}/video.mp4",
        "-f", "segment",
        "-segment_time", "15",
        "-reset_timestamps", "1",
        "-c:v", "copy",  # Copy video codec
        "-c:a", "copy",  # Copy audio codec
        f"{output_folder}/temp_segment_%03d.mp4"
    ])
    
    # Process each segment
    segments = sorted([f for f in os.listdir(output_folder) if f.startswith("temp_segment_")])
    for segment in segments:
        segment_path = os.path.join(output_folder, segment)
        segment_name = segment.replace("temp_", "").split('.')[0]
        segment_dir = os.path.join(output_folder, segment_name)
        frames_dir = os.path.join(segment_dir, "frames")
        os.makedirs(frames_dir, exist_ok=True)
        
        # Extract one frame per second
        print(f"Extracting frames for {segment_name}...")
        subprocess.run([
            "ffmpeg",
            "-i", segment_path,
            "-vf", "fps=1",  # One frame per second
            "-frame_pts", "1",  # Add presentation timestamp
            f"{frames_dir}/frame_%d.jpg"
        ])
        
        # Extract audio for this segment
        print(f"Extracting audio for {segment_name}...")
        subprocess.run([
            "ffmpeg",
            "-i", segment_path,
            "-vn",  # Disable video
            "-acodec", "libmp3lame",  # Use MP3 codec
            "-ar", "44100",  # Audio sample rate
            "-ab", "192k",  # Audio bitrate
            f"{segment_dir}/audio.mp3"
        ])
        
        # Remove temporary segment file
        os.remove(segment_path)
    
    # Cleanup original video
    os.remove(f"{output_folder}/video.mp4")
    print("Processing complete!")
