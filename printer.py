"""
Printer interface for thermal printers via CUPS.
Supports Kitchen_MD (markdown), Kitchen_Art (images), and Rollo X1040 (stickers).
"""

import os
import subprocess
import tempfile
import configparser
from pathlib import Path
from typing import Tuple
from PIL import Image


# Printer specifications (for preview calculations)
PRINT_WIDTH_DOTS = 576
PRINT_WIDTH_BYTES = 72  # 576 / 8
DPI = 203
FONT_A_WIDTH = 12
FONT_A_HEIGHT = 24
FONT_B_WIDTH = 9
FONT_B_HEIGHT = 17
CHARS_PER_LINE_FONT_A = 48
CHARS_PER_LINE_FONT_B = 64
DEFAULT_LINE_SPACING = 30

# CUPS printer names for kitchen thermal printer
KITCHEN_MD_PRINTER = 'Kitchen_MD'
KITCHEN_ART_PRINTER = 'Kitchen_Art'


def _check_cups_printer(printer_name: str) -> Tuple[bool, str]:
    """Check if a CUPS printer is available."""
    try:
        result = subprocess.run(
            ['lpstat', '-p', printer_name],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            return False, f"Printer '{printer_name}' not found. Check CUPS configuration."
        if 'disabled' in result.stdout.lower():
            return False, f"Printer '{printer_name}' is disabled."
        return True, ""
    except subprocess.TimeoutExpired:
        return False, "Timeout checking printer status"
    except FileNotFoundError:
        return False, "CUPS not installed (lpstat not found)"
    except Exception as e:
        return False, f"Error checking printer: {str(e)}"


def _print_to_cups(printer_name: str, file_path: str, options: list = None) -> Tuple[bool, str]:
    """Print a file to a CUPS printer."""
    try:
        cmd = ['lp', '-d', printer_name]
        if options:
            for opt in options:
                cmd.extend(['-o', opt])
        cmd.append(file_path)
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            return False, f"Print failed: {result.stderr}"
        
        return True, ""
    except subprocess.TimeoutExpired:
        return False, "Timeout sending print job"
    except Exception as e:
        return False, f"Print error: {str(e)}"


class ThermalPrinter:
    """Interface for 80mm USB thermal printer via CUPS queues."""
    
    def __init__(self):
        self.md_printer = KITCHEN_MD_PRINTER
        self.art_printer = KITCHEN_ART_PRINTER
    
    def print_image(self, image: Image.Image, cut: bool = True) -> Tuple[bool, str]:
        """Print a PIL Image via Kitchen_Art CUPS queue."""
        available, error = _check_cups_printer(self.art_printer)
        if not available:
            return False, error
        
        try:
            # Ensure image is 1-bit mode for thermal printing
            if image.mode != '1':
                image = image.convert('1')
            
            # Resize if wider than print width
            if image.width > PRINT_WIDTH_DOTS:
                ratio = PRINT_WIDTH_DOTS / image.width
                new_height = int(image.height * ratio)
                image = image.resize((PRINT_WIDTH_DOTS, new_height), Image.Resampling.LANCZOS)
                image = image.convert('1')
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                tmp_path = tmp.name
                image.save(tmp_path, 'PNG')
            
            try:
                success, error = _print_to_cups(self.art_printer, tmp_path)
                return success, error
            finally:
                try:
                    os.unlink(tmp_path)
                except:
                    pass
        
        except Exception as e:
            return False, f"Print error: {str(e)}"
    
    def print_text_commands(self, commands: list, cut: bool = True) -> Tuple[bool, str]:
        """
        Print text/markdown via Kitchen_MD CUPS queue.
        Commands are converted to plain text for the CUPS queue to handle.
        """
        available, error = _check_cups_printer(self.md_printer)
        if not available:
            return False, error
        
        try:
            # Extract text content from commands
            text_content = []
            for cmd_type, data in commands:
                if cmd_type == 'text':
                    text_content.append(data)
            
            full_text = ''.join(text_content)
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(suffix='.txt', delete=False, mode='w', encoding='utf-8') as tmp:
                tmp_path = tmp.name
                tmp.write(full_text)
            
            try:
                success, error = _print_to_cups(self.md_printer, tmp_path)
                return success, error
            finally:
                try:
                    os.unlink(tmp_path)
                except:
                    pass
        
        except Exception as e:
            return False, f"Print error: {str(e)}"


# Rollo X1040 configuration
ROLLO_PRINTER_NAME = 'Rollo_X1040'
ROLLO_PAPER_WIDTH_INCHES = 4.0
ROLLO_PAPER_HEIGHT_INCHES = 6.0
ROLLO_DPI = 203
ROLLO_PRINT_WIDTH_DOTS = int(ROLLO_PAPER_WIDTH_INCHES * ROLLO_DPI)  # 812 dots
ROLLO_PRINT_HEIGHT_DOTS = int(ROLLO_PAPER_HEIGHT_INCHES * ROLLO_DPI)  # 1218 dots


class RolloPrinter:
    """Interface for Rollo X1040 network printer via CUPS."""
    
    def __init__(self):
        self.printer_name = ROLLO_PRINTER_NAME
    
    def print_image(self, image: Image.Image, cut: bool = True) -> Tuple[bool, str]:
        """
        Print a PIL Image to the Rollo printer via CUPS.
        The image is resized to fit the fixed 4x6 inch sticker size.
        Auto-rotates to maximize coverage on the sticker.
        """
        available, error = _check_cups_printer(self.printer_name)
        if not available:
            return False, error
        
        try:
            # Convert to RGB if necessary (Rollo handles color/grayscale)
            if image.mode == '1':
                image = image.convert('L')
            elif image.mode == 'RGBA':
                # Create white background for transparency
                background = Image.new('RGB', image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[3])
                image = background
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            img_width, img_height = image.size
            
            # Auto-rotate to maximize coverage on 4x6" sticker (portrait orientation)
            # Paper is 4" wide x 6" tall, so aspect ratio is 4/6 = 0.667
            paper_aspect = ROLLO_PAPER_WIDTH_INCHES / ROLLO_PAPER_HEIGHT_INCHES  # 0.667
            image_aspect = img_width / img_height
            
            # If image is landscape (wider than tall) and paper is portrait,
            # rotate the image 90 degrees to better fill the paper
            if image_aspect > 1.0 and paper_aspect < 1.0:
                # Landscape image on portrait paper - rotate to fill better
                image = image.rotate(90, expand=True)
                img_width, img_height = image.size
            elif image_aspect < 1.0 and paper_aspect > 1.0:
                # Portrait image on landscape paper - rotate to fill better
                image = image.rotate(90, expand=True)
                img_width, img_height = image.size
            
            # Scale image to fit within Rollo paper size while maintaining aspect ratio
            
            # Calculate scale to fit within paper bounds
            width_scale = ROLLO_PRINT_WIDTH_DOTS / img_width
            height_scale = ROLLO_PRINT_HEIGHT_DOTS / img_height
            scale = min(width_scale, height_scale)
            
            if scale < 1.0:
                # Image is larger than paper, scale down
                new_width = int(img_width * scale)
                new_height = int(img_height * scale)
                image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Create a white canvas of the exact sticker size
            canvas = Image.new('RGB', (ROLLO_PRINT_WIDTH_DOTS, ROLLO_PRINT_HEIGHT_DOTS), (255, 255, 255))
            
            # Center the image on the canvas
            paste_x = (ROLLO_PRINT_WIDTH_DOTS - image.width) // 2
            paste_y = (ROLLO_PRINT_HEIGHT_DOTS - image.height) // 2
            canvas.paste(image, (paste_x, paste_y))
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                tmp_path = tmp.name
                canvas.save(tmp_path, 'PNG')
            
            try:
                success, error = _print_to_cups(
                    self.printer_name,
                    tmp_path,
                    ['media=Custom.4x6in', 'fit-to-page']
                )
                return success, error
            finally:
                # Clean up temp file
                try:
                    os.unlink(tmp_path)
                except:
                    pass
        
        except subprocess.TimeoutExpired:
            return False, "Timeout sending print job"
        except Exception as e:
            return False, f"Print error: {str(e)}"
    
    def print_text_commands(self, commands: list, cut: bool = True) -> Tuple[bool, str]:
        """
        For Rollo, we don't support ESC/POS text commands directly.
        Text should be rendered as an image first.
        """
        return False, "Rollo printer requires image-based printing. Text is rendered as an image."


def get_printer(printer_type: str = 'usb') -> ThermalPrinter:
    """
    Get a printer instance.
    
    Args:
        printer_type: 'usb' for USB thermal printer, 'rollo' for Rollo X1040
    
    Returns:
        ThermalPrinter or RolloPrinter instance
    """
    if printer_type == 'rollo':
        return RolloPrinter()
    return ThermalPrinter()
