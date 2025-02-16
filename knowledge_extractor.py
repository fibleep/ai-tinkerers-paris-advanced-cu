import base64
import gc
import json
import os
from typing import Dict, List, Optional

import whisperx
from langchain.cache import SQLiteCache
from langchain.globals import set_llm_cache
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage

# Set up LangChain caching
set_llm_cache(SQLiteCache(database_path=".langchain.db"))

# Prompts
_DESCRIBE_IMAGE_PROMPT = """
You are a helpful assistant that describes images.

You are given an image and you need to describe it in detail.

You are a part of a COMPUTER USE pipeline, you need to describe SPECIFIC details of the image that are relevant to the computer use.

### GUIDELINES
- Extract the name of the application that is being used
- Find the URL if it is present
- Extract form details, but make sure that it can generalize to other forms - we need a general "The input form with the label 'Name' has value 'John Doe'"
- Be as specific as possible

### OUTPUT
Your output should be structured into XML format, omit any details that are not relevant to the computer use.
Omit any of your comments, only output the XML, between <xml> and </xml> tags.
"""

_STEPS_CREATION_PROMPT = """
You are a helpful assistant that creates steps from a segment of a video.

A segment is only a part of the bigger whole, 

You are given a text and you need to create steps from it.

Make sure that it's generic! It should capture the general action, that will be later automated with AI

### GUIDELINES
- You will receive an audio transcription and a list of image descriptions
- You will need to understand the user's intent and create a list of steps that will help you achieve the goal of this segment
- You will need to create a list of steps that will help you achieve the goal of this segment

### OUTPUT
Your output is an xml structure between <xml> and </xml> tags.

An example is:
<xml>
<step>
    <description>
            The user is on the home page of a website, the intent is to login
            The site is https://www.google.com
    </description>
    <steps>
        <step>
            <referenced_frames>
                1, 2, 3
            </referenced_frames>
            <description>
                The user clicks on the login button, the url is https://www.google.com, the login button is labeled "Login", it's a button with a plus icon, 
                it's blue and in the top right corner of the page
                They are redirected to the login page
            </description>
        </step>
    </steps>
</step>
</xml>

You should make this as robust as possible!

Return your output between <xml> and </xml> tags.

Here is your input:

Audio transcription:
{audio_text}

Image descriptions:
{image_descriptions}
"""

_GENERAL_TOOL_CREATION_PROMPT = """
You are a helpful assistant that creates general tools from a transcription of segments of a video

Your goal is to use all the knowledge about the different segments of the video to create a generic
description of what the user would like to automate

Some steps will be very specific to the video, you need to add guidance to the generic description
about what the real goal is.

This is a TUTORIAL, some values will be presented as examples - you need to generalize them!

Your output should be in xml format, between <xml> and </xml> tags.

### EXAMPLE
<xml>
<tool>
    <description>
        The user wants to automate the process of ordering a pizza from pizza hut
    </description>
    <guidance>
        In step 5, the user clicked on the "Hawaiian" pizza, but it might not be the pizza they want to order
        every time, so make sure to generalize the tool
        They specifically mentioned in the audio that this is a tool for ordering pizza, you can ignore other cuisines
    </guidance>
</tool>

### GUIDELINES
Be as robust as possible!

This is guidance for a computer use agent, it should detail what it should look for on a page and how it should interact with it
Include links, the logical actions and the core of what's happening in the steps

Return your output between <xml> and </xml> tags.

Try to avoid terminal use as much as possible, it's better to use a GUI.

Here are the steps of the requested action:
{steps}
"""


def _encode_image(image_path: str) -> str:
    """Encode image to base64."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def _call(prompt: str, image_path: Optional[str] = None) -> str:
    """Make a call to Claude with optional image input."""
    model = ChatAnthropic(model="claude-3-5-sonnet-latest")

    if image_path:
        base64_image = _encode_image(image_path)
        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": base64_image,
                    },
                },
            ]
        )
    else:
        message = HumanMessage(content=prompt)

    response = model.invoke([message])
    return response.content


def _transcribe_from_path(audio_path: str, verbose: bool = False) -> Optional[str]:
    """Transcribe audio file to text using WhisperX."""
    try:
        if verbose:
            print(f"Transcribing: {audio_path}")

        device = "cpu"
        model = whisperx.load_model("small", device, compute_type="int8")

        audio = whisperx.load_audio(audio_path)
        result = model.transcribe(audio, batch_size=1)

        del model
        gc.collect()

        transcribed_text = " ".join(
            segment["text"].strip() for segment in result["segments"]
        )

        if verbose:
            print("Transcription complete")

        return transcribed_text

    except Exception as e:
        if verbose:
            print(f"Transcription failed: {str(e)}")
        return None


def _process_segment(segment: Dict) -> tuple[str, str, List[str]]:
    """Process a single video segment."""
    audio_text = _transcribe_from_path(segment["audio"], verbose=True)
    print(f"Transcribed audio: {audio_text}")

    image_descriptions = []
    for idx, image in enumerate(segment["images"]):
        res = _call(_DESCRIBE_IMAGE_PROMPT, image)
        res = res.replace("\n", "")
        image_descriptions.append(f"FRAME {idx}: {res}")

    image_descriptions_parsed = "\n".join(image_descriptions)
    res = _call(
        _STEPS_CREATION_PROMPT.format(
            audio_text=audio_text, image_descriptions=image_descriptions_parsed
        )
    )

    # Extract content between XML tags
    res = res.split("<xml>")[1].split("</xml>")[0] if "<xml>" in res else res
    return res, audio_text, image_descriptions


def _final_xml_creation(main_description: str, tools: str) -> str:
    """Create the final XML structure."""
    return f"""
    <xml>
    <main_description>
    {main_description}
    </main_description>
    {tools}
    </xml>
    """


def process_video_segments(segments_path: str, limit: Optional[int] = None) -> str:
    """
    Process video segments and generate a combined XML description.

    Args:
        segments_path (str): Path to the directory containing video segments
        limit (Optional[int]): Maximum number of segments to process

    Returns:
        str: Combined XML description of the video segments
    """
    # Build knowledge base from directory structure
    knowledge_base = []

    # Get sorted list of segment directories
    segment_dirs = sorted(
        [
            d
            for d in os.listdir(segments_path)
            if os.path.isdir(os.path.join(segments_path, d))
            and d.startswith("segment_")
        ]
    )

    # Limit segments if specified
    if limit:
        segment_dirs = segment_dirs[:limit]

    # Build knowledge base
    for segment_dir in segment_dirs:
        segment_path = os.path.join(segments_path, segment_dir)

        # Get audio file
        audio_file = os.path.join(segment_path, "audio.mp3")

        # Get sorted image files
        image_files = sorted(
            [
                os.path.join(segment_path, f)
                for f in os.listdir(segment_path)
                if f.endswith((".png", ".jpg", ".jpeg"))
                and os.path.isfile(os.path.join(segment_path, f))
            ]
        )

        # Add segment to knowledge base
        segment_data = {"audio": audio_file, "images": image_files}
        knowledge_base.append(segment_data)

    # Process segments
    segment_results = []
    for segment in knowledge_base:
        res, audio_text, image_descriptions = _process_segment(segment)
        segment_results.append(res)

    # Create general tool description
    general_description = _call(
        _GENERAL_TOOL_CREATION_PROMPT.format(steps="\n".join(segment_results))
    )
    general_description = (
        general_description.split("<xml>")[1].split("</xml>")[0]
        if "<xml>" in general_description
        else general_description
    )

    # Create final XML
    final_xml = _final_xml_creation(general_description, "\n".join(segment_results))

    return final_xml


if __name__ == "__main__":
    # Example usage
    result = process_video_segments("ingestor/video_parts", limit=3)
    print(result)
