"""
Printer interface for 80mm USB thermal printer using ESC/POS commands.
Direct USB communication without python-escpos to avoid image banding.
Also supports network printers via CUPS (e.g., Rollo X1040).
"""

import os
import time
import subprocess
import tempfile
import configparser
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image

try:
    import usb.core
    import usb.util
    USB_AVAILABLE = True
except ImportError:
    USB_AVAILABLE = False


# ESC/POS Commands from 80MM_Printer_Programmer_Manual.txt
CMD_INIT = b'\x1b\x40'              # ESC @ - Initialize printer
CMD_FONT_A = b'\x1b\x4d\x00'        # ESC M 0 - Font A (12x24)
CMD_FONT_B = b'\x1b\x4d\x01'        # ESC M 1 - Font B (9x17)
CMD_BOLD_ON = b'\x1b\x45\x01'       # ESC E 1 - Bold on
CMD_BOLD_OFF = b'\x1b\x45\x00'      # ESC E 0 - Bold off
CMD_DOUBLE_HEIGHT = b'\x1b\x21\x10' # ESC ! 0x10 - Double height
CMD_DOUBLE_WIDTH = b'\x1b\x21\x20'  # ESC ! 0x20 - Double width
CMD_DOUBLE_WH = b'\x1b\x21\x30'     # ESC ! 0x30 - Double width+height
CMD_NORMAL = b'\x1b\x21\x00'        # ESC ! 0x00 - Normal mode
CMD_UNDERLINE_ON = b'\x1b\x2d\x01'  # ESC - 1 - Underline on
CMD_UNDERLINE_OFF = b'\x1b\x2d\x00' # ESC - 0 - Underline off
CMD_LINE_SPACING = b'\x1b\x33'      # ESC 3 n - Set line spacing
CMD_DEFAULT_SPACING = b'\x1b\x32'   # ESC 2 - Default line spacing (30 dots)
CMD_CUT = b'\x1d\x56\x00'           # GS V 0 - Full cut
CMD_PARTIAL_CUT = b'\x1d\x56\x01'   # GS V 1 - Partial cut
CMD_FEED = b'\x1b\x4a'              # ESC J n - Feed n dots

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
    }
    
    if config_path.exists():
        parser = configparser.ConfigParser()
        parser.read(config_path)
        
        if 'printer' in parser:
            vendor = parser['printer'].get('vendor_id', '')
            product = parser['printer'].get('product_id', '')
            
            # Parse hex values (0x0483) or decimal
            if vendor:
                config['vendor_id'] = int(vendor, 16) if vendor.startswith('0x') else int(vendor)
            if product:
                config['product_id'] = int(product, 16) if product.startswith('0x') else int(product)
            
            config['profile'] = parser['printer'].get('profile', None)
    
    return config


def image_to_raster(image: Image.Image) -> bytes:
    """
    Convert a 1-bit PIL Image to ESC/POS raster format.
    Uses GS v 0 command for raster bit image printing.
    """
    # Ensure 1-bit mode
    if image.mode != '1':
        image = image.convert('1')
    
    width = image.width
    height = image.height
    
    # Width in bytes (8 pixels per byte)
    width_bytes = (width + 7) // 8
    
    # Get raw pixel data
    pixels = image.load()
    
    # Build raster data
    raster_data = bytearray()
    
    for y in range(height):
        for x_byte in range(width_bytes):
            byte = 0
            for bit in range(8):
                x = x_byte * 8 + bit
                if x < width:
                    # In PIL mode '1', 0 = black, 255 = white
                    # In ESC/POS raster, 1 = print (black), 0 = no print (white)
                    pixel = pixels[x, y]
                    if pixel == 0:  # Black pixel
                        byte |= (0x80 >> bit)
            raster_data.append(byte)
    
    # Build GS v 0 command
    # Format: GS v 0 m xL xH yL yH d1...dk
    # m = 0 (normal density)
    # xL xH = width in bytes (little endian)
    # yL yH = height in dots (little endian)
    m = 0
    xL = width_bytes & 0xFF
    xH = (width_bytes >> 8) & 0xFF
    yL = height & 0xFF
    yH = (height >> 8) & 0xFF
    command = bytes([0x1D, 0x76, 0x30, m, xL, xH, yL, yH]) + bytes(raster_data)
    
    return command


class ThermalPrinter:
    """Interface for 80mm USB thermal printer with direct USB communication."""
    
    def __init__(self):
        self.config = load_config()
        self.device = None
        self.endpoint = None
    
    def connect(self) -> Tuple[bool, str]:
        """Connect to the printer. Returns (success, error_message)."""
        if not USB_AVAILABLE:
            return False, "pyusb library not installed. Run: pip install pyusb"
        
        if not self.config['vendor_id'] or not self.config['product_id']:
            return False, "Printer not configured. Create ~/.print-hole.conf with vendor_id and product_id. Use 'lsusb' to find these values."
        
        try:
            self.device = usb.core.find(
                idVendor=self.config['vendor_id'],
                idProduct=self.config['product_id']
            )
            
            if self.device is None:
                return False, f"Printer not found. Check USB connection and verify vendor_id=0x{self.config['vendor_id']:04x}, product_id=0x{self.config['product_id']:04x}"
            
            # Detach kernel driver if active
            try:
                if self.device.is_kernel_driver_active(0):
                    self.device.detach_kernel_driver(0)
            except (usb.core.USBError, NotImplementedError):
                pass
            
            # Set configuration
            try:
                self.device.set_configuration()
            except usb.core.USBError:
                pass  # May already be configured
            
            # Find the OUT endpoint
            cfg = self.device.get_active_configuration()
            intf = cfg[(0, 0)]
            
            self.endpoint = usb.util.find_descriptor(
                intf,
                custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
            )
            
            if self.endpoint is None:
                return False, "Could not find printer output endpoint"
            
            return True, ""
            
        except usb.core.USBError as e:
            return False, f"USB error: {str(e)}"
        except Exception as e:
            return False, f"Failed to connect to printer: {str(e)}"
    
    def disconnect(self):
        """Disconnect from the printer."""
        if self.device:
            try:
                usb.util.dispose_resources(self.device)
            except:
                pass
            self.device = None
            self.endpoint = None
    
    def _write(self, data: bytes) -> bool:
        """Write raw bytes to printer in chunks with delays."""
        if not self.endpoint:
            return False
        try:
            chunk_size = 20000  # 8KB chunks
            for i in range(0, len(data), chunk_size):
                chunk = data[i:i + chunk_size]
                self.endpoint.write(chunk, timeout=10000)
                if i + chunk_size < len(data):
                    time.sleep(0.01)  # 10ms pause between chunks
            return True
        except usb.core.USBError:
            return False
    
    def print_raw(self, data: bytes) -> Tuple[bool, str]:
        """Send raw ESC/POS commands to printer."""
        success, error = self.connect()
        if not success:
            return False, error
        
        try:
            self._write(CMD_INIT)
            self._write(data)
            self._write(b'\n\n\n')
            return True, ""
        except Exception as e:
            return False, f"Print error: {str(e)}"
        finally:
            self.disconnect()
    
    def print_image(self, image: Image.Image, cut: bool = True) -> Tuple[bool, str]:
        """Print a PIL Image using raster bit image command."""
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
            
            # Initialize printer
            self._write(CMD_INIT)
            
            # Convert image to raster command and send as one block
            raster_cmd = image_to_raster(image)
            self._write(raster_cmd)
            
            # Feed 4 blank lines (~20mm) before cut for margin
            self._write(b'\n\n\n\n')
            
            if cut:
                self._write(CMD_PARTIAL_CUT)
            
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
        """
        success, error = self.connect()
        if not success:
            return False, error
        
        try:
            self._write(CMD_INIT)
            self._write(CMD_DEFAULT_SPACING)
            
            for cmd_type, data in commands:
                if cmd_type == 'raw':
                    self._write(data)
                elif cmd_type == 'text':
                    self._write(data.encode('utf-8'))
            
            # Feed 4 blank lines before cut for margin
            self._write(b'\n\n\n\n')
            
            if cut:
                self._write(CMD_PARTIAL_CUT)
            
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
