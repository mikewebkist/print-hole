"""
Image processor for thermal printer output.
Handles resizing, rotation modes, and 1-bit dithering.
"""

from PIL import Image
from enum import Enum
from typing import Tuple

# Printer specifications
PRINT_WIDTH_DOTS = 576
DPI = 203


class RotationMode(Enum):
    AUTO = "auto"       # Rotate 90° if height > width (portrait → landscape)
    ORIGINAL = "original"  # No rotation
    SQUARE = "square"   # Center-crop to 1:1 before resize


def center_crop_square(image: Image.Image) -> Image.Image:
    """Center-crop image to a square aspect ratio."""
    width, height = image.size
    
    if width == height:
        return image
    
    # Determine the size of the square (smaller dimension)
    size = min(width, height)
    
    # Calculate crop box (left, upper, right, lower)
    left = (width - size) // 2
    top = (height - size) // 2
    right = left + size
    bottom = top + size
    
    return image.crop((left, top, right, bottom))


def process_image(
    image: Image.Image,
    rotation: RotationMode = RotationMode.AUTO,
    target_width: int = PRINT_WIDTH_DOTS
) -> Tuple[Image.Image, float]:
    """
    Process image for thermal printer output.
    
    Args:
        image: Input PIL Image
        rotation: Rotation mode (AUTO, ORIGINAL, SQUARE)
        target_width: Target width in pixels (default 576 for 80mm printer)
    
    Returns:
        Tuple of (processed 1-bit image, estimated print length in inches)
    """
    # Convert to RGB if necessary (handles RGBA, palette, etc.)
    if image.mode in ('RGBA', 'LA'):
        # Create white background for transparent images
        background = Image.new('RGB', image.size, (255, 255, 255))
        if image.mode == 'RGBA':
            background.paste(image, mask=image.split()[3])
        else:
            background.paste(image, mask=image.split()[1])
        image = background
    elif image.mode != 'RGB':
        image = image.convert('RGB')
    
    # Apply rotation mode
    if rotation == RotationMode.SQUARE:
        image = center_crop_square(image)
    elif rotation == RotationMode.AUTO:
        # Rotate landscape images (wider than tall) 90° so the longer dimension
        # prints along the paper length, maximizing the printed image size
        if image.width > image.height:
            image = image.rotate(90, expand=True)
    # ORIGINAL mode: no rotation
    
    # Resize to target width, maintaining aspect ratio
    if image.width != target_width:
        ratio = target_width / image.width
        new_height = int(image.height * ratio)
        image = image.resize((target_width, new_height), Image.Resampling.LANCZOS)
    
    # Convert to grayscale then 1-bit with Floyd-Steinberg dithering
    image = image.convert('L')  # Grayscale
    image = image.convert('1')  # 1-bit with dithering (default)
    
    # Calculate print length in inches
    length_inches = image.height / DPI
    
    return image, length_inches


def process_image_from_bytes(
    image_data: bytes,
    rotation: str = "auto",
    target_width: int = PRINT_WIDTH_DOTS
) -> Tuple[Image.Image, float]:
    """
    Process image from raw bytes.
    
    Args:
        image_data: Raw image bytes (PNG, JPEG, etc.)
        rotation: Rotation mode string ("auto", "original", "square")
        target_width: Target width in pixels
    
    Returns:
        Tuple of (processed 1-bit image, estimated print length in inches)
    """
    from io import BytesIO
    
    image = Image.open(BytesIO(image_data))
    
    # Convert rotation string to enum
    rotation_mode = RotationMode(rotation.lower())
    
    return process_image(image, rotation_mode, target_width)


def image_to_base64(image: Image.Image, format: str = 'PNG') -> str:
    """Convert PIL Image to base64 string."""
    from io import BytesIO
    import base64
    
    buffer = BytesIO()
    image.save(buffer, format=format)
    buffer.seek(0)
    
    return base64.b64encode(buffer.getvalue()).decode('utf-8')


def base64_to_image(base64_string: str) -> Image.Image:
    """Convert base64 string to PIL Image."""
    from io import BytesIO
    import base64
    
    # Handle data URL format
    if ',' in base64_string:
        base64_string = base64_string.split(',', 1)[1]
    
    image_data = base64.b64decode(base64_string)
    return Image.open(BytesIO(image_data))
