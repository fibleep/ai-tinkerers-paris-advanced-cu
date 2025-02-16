import streamlit as st
import shutil
import asyncio
import sys
import os
sys.path.append(os.path.abspath("../"))
from knowledge_extractor import process_video_segments
from ingestor.splitter import process_video
import time

def main():
    st.title("Advanced CU")
    st.write("This tool will:")
    st.write("1. Download or upload the video")
    st.write("2. Split it into 15-second segments")
    st.write("3. Extract frames (1 FPS) and audio from each segment")
    st.write("4. Instruct our agent to replicate what's been done")
    
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
        for item in os.listdir(output_dir):
            item_path = os.path.join(output_dir, item)
            if os.path.isfile(item_path) or os.path.islink(item_path):
                os.remove(item_path)  # Delete file or symbolic link
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)  # Delete directory and its conten
        if video_input:
            try:
                # Create progress placeholder
                progress_text = st.empty()
                progress_bar = st.progress(0)
                
                # Process the video with progress updates
                progress_text.text("Processing video...")
                progress_bar.progress(10)
                
                # Call the process_video function
                process_video(video_input, output_dir)
                
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

                progress_text2 = st.text("Extracting information...")
                progress_bar2 = st.progress(0)
                
                xml_instructions = process_video_segments("../ingestor/video_parts", limit=3)

                progress_text2 = st.text("Done!")
                progress_bar2.progress(100)

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
    #xml_file_path = os.path.join(output_dir, "../claude-computer-use-macos/first_steps.xml")
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
        
        try:
            sys.path.append(os.path.abspath("../claude-computer-use-macos"))
            from xml_task_agent import execute_automation
            asyncio.run(execute_automation("steps.xml"))
            st.success("Agent executed successfully!")
        except Exception as e:
            st.error(f"Failed to run agent: {str(e)}")

            
if __name__ == "__main__":
    main()
