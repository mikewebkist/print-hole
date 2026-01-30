"""
Printer interface for 80mm USB thermal printer using python-escpos.
Also supports network printers via CUPS (e.g., Rollo X1040).
"""

import os
import subprocess
import tempfile
import configparser
from pathlib import Path
from typing import Tuple
from PIL import Image

try:
    from escpos.printer import Usb
    from escpos.exceptions import USBNotFoundError
    ESCPOS_AVAILABLE = True
except ImportError:
    ESCPOS_AVAILABLE = False


# Printer specifications
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


def load_config() -> dict:
    """Load printer configuration from ~/.print-hole.conf"""
    config_path = Path.home() / '.print-hole.conf'
    config = {
        'vendor_id': None,
        'product_id': None,
        'profile': None,
        'in_ep': 0x82,
        'out_ep': 0x01,
    }
    
    if config_path.exists():
        parser = configparser.ConfigParser()
        parser.read(config_path)
        
        if 'printer' in parser:
            vendor = parser['printer'].get('vendor_id', '')
            product = parser['printer'].get('product_id', '')
            in_ep = parser['printer'].get('in_ep', '')
            out_ep = parser['printer'].get('out_ep', '')
            
            # Parse hex values (0x0483) or decimal
            if vendor:
                config['vendor_id'] = int(vendor, 16) if vendor.startswith('0x') else int(vendor)
            if product:
                config['product_id'] = int(product, 16) if product.startswith('0x') else int(product)
            if in_ep:
                config['in_ep'] = int(in_ep, 16) if in_ep.startswith('0x') else int(in_ep)
            if out_ep:
                config['out_ep'] = int(out_ep, 16) if out_ep.startswith('0x') else int(out_ep)
            
            config['profile'] = parser['printer'].get('profile', None)
    
    return config


class ThermalPrinter:
    """Interface for 80mm USB thermal printer using python-escpos."""
    
    def __init__(self):
        self.config = load_config()
        self.printer = None
    
    def connect(self) -> Tuple[bool, str]:
        """Connect to the printer. Returns (success, error_message)."""
        if not ESCPOS_AVAILABLE:
            return False, "python-escpos library not installed. Run: pip install python-escpos"
        
        if not self.config['vendor_id'] or not self.config['product_id']:
            return False, "Printer not configured. Create ~/.print-hole.conf with vendor_id and product_id. Use 'lsusb' to find these values."
        
        try:
            self.printer = Usb(
                idVendor=self.config['vendor_id'],
                idProduct=self.config['product_id'],
                in_ep=self.config['in_ep'],
                out_ep=self.config['out_ep'],
                profile=self.config['profile'] or 'default'
            )
            self.printer.set(density=5)
            return True, ""
            
        except USBNotFoundError:
            return False, f"Printer not found. Check USB connection and verify vendor_id=0x{self.config['vendor_id']:04x}, product_id=0x{self.config['product_id']:04x}"
        except Exception as e:
            return False, f"Failed to connect to printer: {str(e)}"
    
    def disconnect(self):
        """Disconnect from the printer."""
        if self.printer:
            try:
                self.printer.close()
            except Exception:
                pass
            self.printer = None
    
    def print_raw(self, data: bytes) -> Tuple[bool, str]:
        """Send raw ESC/POS commands to printer."""
        success, error = self.connect()
        if not success:
            return False, error
        
        try:
            self.printer._raw(b'\x1b\x40')  # ESC @ - Initialize
            self.printer._raw(data)
            self.printer.ln(3)
            return True, ""
        except Exception as e:
            return False, f"Print error: {str(e)}"
        finally:
            self.disconnect()
    
    def print_image(self, image: Image.Image, cut: bool = True) -> Tuple[bool, str]:
        """Print a PIL Image using python-escpos image method."""
        success, error = self.connect()
        if not success:
            return False, error
        
        try:
            # Ensure image is 1-bit mode
            if image.mode != '1':
                image = image.convert('1')
            
            # Resize if wider than print width
            if image.width > PRINT_WIDTH_DOTS:
                ratio = PRINT_WIDTH_DOTS / image.width
                new_height = int(image.height * ratio)
                image = image.resize((PRINT_WIDTH_DOTS, new_height), Image.Resampling.LANCZOS)
                image = image.convert('1')
            
            # Print image using escpos
            self.printer.image(image, impl='bitImageRaster')
            
            # Feed 4 blank lines (~20mm) before cut for margin
            self.printer.ln(4)
            
            if cut:
                self.printer.cut(mode='PART')
            
            return True, ""
        except Exception as e:
            return False, f"Print error: {str(e)}"
        finally:
            self.disconnect()
    
    def print_text_commands(self, commands: list, cut: bool = True) -> Tuple[bool, str]:
        """
        Print using a list of ESC/POS command tuples.
        Each tuple is (command_type, data) where command_type is:
        - 'raw': raw bytes to send
        - 'text': text string to print
        - 'set': dict of escpos set() parameters (bold, underline, double_height, etc.)
        """
        success, error = self.connect()
        if not success:
            return False, error
        
        try:
            self.printer._raw(b'\x1b\x32')  # ESC 2 - Default line spacing
            
            for cmd_type, data in commands:
                if cmd_type == 'raw':
                    self.printer._raw(data)
                elif cmd_type == 'text':
                    self.printer.text(data)
                elif cmd_type == 'set':
                    self.printer.set(**data)
            
            # Feed 4 blank lines before cut for margin
            self.printer.ln(4)
            
            if cut:
                self.printer.cut(mode='PART')
            
            return True, ""
        except Exception as e:
            return False, f"Print error: {str(e)}"
        finally:
            self.disconnect()


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
    
    def _check_printer_available(self) -> Tuple[bool, str]:
        """Check if the Rollo printer is available via CUPS."""
        try:
            result = subprocess.run(
                ['lpstat', '-p', self.printer_name],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                return False, f"Printer '{self.printer_name}' not found. Check CUPS configuration."
            if 'disabled' in result.stdout.lower():
                return False, f"Printer '{self.printer_name}' is disabled."
            return True, ""
        except subprocess.TimeoutExpired:
            return False, "Timeout checking printer status"
        except FileNotFoundError:
            return False, "CUPS not installed (lpstat not found)"
        except Exception as e:
            return False, f"Error checking printer: {str(e)}"
    
    def print_image(self, image: Image.Image, cut: bool = True) -> Tuple[bool, str]:
        """
        Print a PIL Image to the Rollo printer via CUPS.
        The image is resized to fit the fixed 4x6 inch sticker size.
        Auto-rotates to maximize coverage on the sticker.
        """
        available, error = self._check_printer_available()
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
                # Print using lp command with Rollo-specific options
                result = subprocess.run(
                    [
                        'lp',
                        '-d', self.printer_name,
                        '-o', 'media=Custom.4x6in',
                        '-o', 'fit-to-page',
                        tmp_path
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode != 0:
                    return False, f"Print failed: {result.stderr}"
                
                return True, ""
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
