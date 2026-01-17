"""
AI Image Generator - Generate clip-art style images using Google's Gemini API.
"""

import os
import configparser
from pathlib import Path
from io import BytesIO
import base64
from urllib import response

from PIL import Image

# Gemini API configuration
GEMINI_API_KEY_ENV = 'GEMINI_API_KEY'
CONFIG_PATH = Path.home() / '.print-hole.conf'


def get_api_key() -> str:
    """
    Get Gemini API key from environment variable or config file.
    
    Priority:
    1. GEMINI_API_KEY environment variable
    2. [gemini] api_key in ~/.print-hole.conf
    
    Returns:
        API key string
        
    Raises:
        ValueError: If no API key is found
    """
    # Check environment variable first
    api_key = os.environ.get(GEMINI_API_KEY_ENV)
    if api_key:
        return api_key
    
    # Check config file
    if CONFIG_PATH.exists():
        config = configparser.ConfigParser()
        config.read(CONFIG_PATH)
        if config.has_option('gemini', 'api_key'):
            api_key = config.get('gemini', 'api_key').strip()
            if api_key:
                return api_key
    
    raise ValueError(
        f"Gemini API key not found. Set {GEMINI_API_KEY_ENV} environment variable "
        f"or add [gemini] api_key to {CONFIG_PATH}"
    )


def generate_image(prompt: str) -> Image.Image:
    """
    Generate a black-and-white clip-art style image from a text prompt.
    
    Args:
        prompt: Text description of the image to generate
        
    Returns:
        PIL Image in grayscale mode
        
    Raises:
        ValueError: If API key is missing or prompt is empty
        RuntimeError: If image generation fails
    """
    if not prompt or not prompt.strip():
        raise ValueError("Prompt cannot be empty")
    
    api_key = get_api_key()
    
    # Import google.genai here to avoid import errors if not installed
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise RuntimeError(
            "google-genai package not installed. "
            "Run: pip install google-genai"
        )
    
    # Create client with API key
    client = genai.Client(api_key=api_key)
    
    # Enhance prompt for clip-art style black and white output
    enhanced_prompt = (
        f"Create a simple black and white clip-art style illustration: {prompt}. "
        "Use bold black lines on white background, high contrast, no gradients, "
        "simple shapes, suitable for thermal printing."
    )
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=[enhanced_prompt],
            # config=types.GenerateImagesConfig(
            #     number_of_images=1,
            #     aspect_ratio="1:1",
            # )
        )
        generated_image = None

        for part in response.parts:
            if part.text is not None:
                print(part.text)
            elif part.inline_data is not None:
                image_data = part.inline_data.data
                generated_image = Image.open(BytesIO(image_data))
                break
        
        if not generated_image:
            raise RuntimeError("No image was generated")
        
        # Convert to grayscale for thermal printing
        grayscale_image = generated_image.convert('L')
        
        return grayscale_image
        
    except Exception as e:
        error_msg = str(e)
        if "API_KEY" in error_msg.upper() or "401" in error_msg:
            raise RuntimeError("Invalid Gemini API key")
        elif "quota" in error_msg.lower() or "429" in error_msg:
            raise RuntimeError("Gemini API quota exceeded. Try again later.")
        else:
            raise RuntimeError(f"Image generation failed: {error_msg}")


def generate_image_base64(prompt: str) -> str:
    """
    Generate image and return as base64-encoded PNG.
    
    Args:
        prompt: Text description of the image
        
    Returns:
        Base64-encoded PNG image string
    """
    image = generate_image(prompt)
    
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    buffer.seek(0)
    
    return base64.b64encode(buffer.getvalue()).decode('utf-8')
