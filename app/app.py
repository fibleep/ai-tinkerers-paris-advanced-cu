import streamlit as st
from stqdm import stqdm
import shutil
import asyncio
import sys
import os
from pathlib import Path
sys.path.append(os.path.abspath("../"))
from knowledge_extractor import process_video_segments
from ingestor.splitter import process_video
import time

# Add these imports at the top
from concurrent.futures import ThreadPoolExecutor
from functools import partial

def run_async_in_thread(coro, steps_path):
    """Helper function to run async code in a thread"""
    async def wrapped():
        try:
            # Add the correct path to the claude-computer-use-macos directory
            claude_path = Path(__file__).parent.parent / "claude-computer-use-macos"
            sys.path.append(str(claude_path))
            
            from main import main
            await main(steps_path)
            return True, None
        except Exception as e:
            return False, str(e)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(wrapped())
    finally:
        loop.close()

def main():
    st.title("Doppelgänger")
    st.image("https://upload.wikimedia.org/wikipedia/commons/2/2d/Dante_Gabriel_Rossetti_-_How_They_Met_Themselves_%281860-64_circa%29.jpg", width=300)
    st.write("This tool will:")
    st.write("1. Download a video tutorial showing how to do something")
    st.write("2. Split it into 15-second segments")
    st.write("3. Extract frames (1 FPS) and audio from each segment")
    st.write("4. Replicate what's been done")
    
    # Input method selection
    input_method = st.radio("Choose input method:", ["YouTube URL", "Local File"])
    
    # Input based on selection
    video_input = None
    if input_method == "YouTube URL":
        video_url = st.text_input("Video URL (YouTube)")
        if video_url:
            video_input = video_url
    else:
        uploaded_file = st.file_uploader("Choose a video file", type=['mp4', 'avi', 'mov', 'mkv'])
        if uploaded_file:
            video_input = uploaded_file
    
    # Input for output directory
    output_dir = "../ingestor/video_parts"
    
    if st.button("Process Video"):
        # Clear output directory
        if os.path.exists(output_dir):
            for item in stqdm(os.listdir(output_dir), desc="Cleaning output directory"):
                item_path = os.path.join(output_dir, item)
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    os.remove(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                    
        if video_input:
            try:
                # Process the video
                with st.spinner("Processing video..."):
                    process_video(video_input, output_dir)
                
                # Get segments and show progress
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

                # Process video segments with progress bar
                with st.spinner("Extracting information..."):
                    # Assuming process_video_segments can be modified to accept a progress callback
                    xml_instructions = process_video_segments("../ingestor/video_parts", limit=3)

                xml_file_path = "steps.xml"
                
                try:
                    with open(xml_file_path, 'w') as file:
                        file.write(xml_instructions)
                except Exception as e:
                    st.error(f"Error saving information to XML: {str(e)}")
                
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
        else:
            st.error("Please provide a video input (URL or file)")

    # Add XML editing section
    st.header("Generated Instructions")
    st.write("Review and edit the generated instructions if needed:")
    
    # Try to read the XML file
    xml_file_path = "steps.xml"
    try:
        if os.path.exists(xml_file_path):
            with open(xml_file_path, 'r') as file:
                initial_xml = file.read()
        else:
            initial_xml = "No instructions generated yet."
    except Exception as e:
        initial_xml = f"Error reading XML file: {str(e)}"
    
    # Create an editable text area with the XML content
    edited_xml = st.text_area("Edit Instructions XML", value=initial_xml, height=300)
    
    # Add a button to save changes
    if st.button("Save XML Changes"):
        try:
            with open(xml_file_path, 'w') as file:
                file.write(edited_xml)
            st.success("XML instructions updated successfully!")
        except Exception as e:
            st.error(f"Error saving XML: {str(e)}")

    # Add a button to proceed to the next step
    if st.button("Trigger agent"):
        with st.spinner("Running agent..."):
            try:
                # Get absolute path to steps.xml
                steps_path = os.path.abspath("./steps.xml")
                
                # Create a thread pool executor
                with ThreadPoolExecutor() as executor:
                    # Run the async code in a separate thread
                    future = executor.submit(run_async_in_thread, None, steps_path)
                    success, error = future.result()
                    
                    if success:
                        st.success("Agent executed successfully!")
                    else:
                        st.error(f"Failed to run agent: {error}")
                        
            except Exception as e:
                st.error(f"Failed to run agent: {str(e)}")

if __name__ == "__main__":
    main()
