import streamlit as st
import sys
import os
sys.path.append(os.path.abspath("../ingestor"))
from splitter import process_video
import time

def main():
    st.title("Advanced CU")
    st.write("This tool will:")
    st.write("1. Download the video")
    st.write("2. Split it into 15-second segments")
    st.write("3. Extract frames (1 FPS) and audio from each segment")
    st.write("4. Instruct our agent to replicate what's been done")
    
    # Input for video URL
    video_url = st.text_input("Video URL (YouTube or other supported platforms)")
    
    # Input for output directory
    output_dir = "../ingestor/video_parts"
    
    if st.button("Process Video"):
        if video_url:
            try:
                # Create progress placeholder
                progress_text = st.empty()
                
                # Create a progress bar
                progress_bar = st.progress(0)
                
                # Process the video with progress updates
                progress_text.text("Downloading video...")
                progress_bar.progress(10)
                
                # Call the process_video function
                process_video(video_url, output_dir)
                
                # Update progress
                progress_bar.progress(100)
                progress_text.text("Processing complete!")
                
                # Show results
                segments = [d for d in os.listdir(output_dir) 
                          if os.path.isdir(os.path.join(output_dir, d)) 
                          and d.startswith("segment_")]
                
                if segments:
                    st.success(f"Successfully processed {len(segments)} segments to {output_dir}")
                    
                    # Show example frames from first segment
                    if len(segments) > 0:
                        first_segment = segments[0]
                        frames_dir = os.path.join(output_dir, first_segment, "frames")
                        if os.path.exists(frames_dir):
                            st.write(f"Sample frames from {first_segment}:")
                            frames = sorted([f for f in os.listdir(frames_dir) if f.endswith('.jpg')])[:3]
                            cols = st.columns(len(frames))
                            for idx, frame in enumerate(frames):
                                with cols[idx]:
                                    st.image(os.path.join(frames_dir, frame), 
                                           caption=f"Frame {idx+1}",
                                           use_container_width=True)
                # add next part here

                
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
        else:
            st.error("Please enter a video URL")

if __name__ == "__main__":
    main()
