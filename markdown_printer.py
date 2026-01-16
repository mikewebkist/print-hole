"""
Markdown to ESC/POS converter and preview renderer.
Parses Markdown and generates native ESC/POS commands for thermal printer.
"""

import re
from typing import List, Tuple
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import base64

# Printer specifications
PRINT_WIDTH_DOTS = 576
DPI = 203
FONT_A_WIDTH = 12
FONT_A_HEIGHT = 24
FONT_B_WIDTH = 9
FONT_B_HEIGHT = 17
CHARS_PER_LINE_FONT_A = 48
CHARS_PER_LINE_FONT_B = 64
DEFAULT_LINE_SPACING = 30

# ESC/POS Commands
CMD_INIT = b'\x1b\x40'
CMD_FONT_A = b'\x1b\x4d\x00'
CMD_FONT_B = b'\x1b\x4d\x01'
CMD_BOLD_ON = b'\x1b\x45\x01'
CMD_BOLD_OFF = b'\x1b\x45\x00'
CMD_DOUBLE_HEIGHT = b'\x1b\x21\x10'
CMD_DOUBLE_WIDTH = b'\x1b\x21\x20'
CMD_DOUBLE_WH = b'\x1b\x21\x30'
CMD_NORMAL = b'\x1b\x21\x00'
CMD_UNDERLINE_ON = b'\x1b\x2d\x01'
CMD_UNDERLINE_OFF = b'\x1b\x2d\x00'
CMD_DEFAULT_SPACING = b'\x1b\x32'

# Font size presets
class FontSize:
    SMALL = 'small'     # 1x - normal
    MEDIUM = 'medium'   # 2x height
    LARGE = 'large'     # 2x width + height


def get_font_settings(size: str) -> Tuple[bytes, int, int]:
    """
    Get ESC/POS command, char width multiplier, and chars per line for font size.
    Returns (command, height_multiplier, chars_per_line)
    """
    if size == FontSize.LARGE:
        return CMD_DOUBLE_WH, 2, 24  # Double W+H, 24 chars/line
    elif size == FontSize.MEDIUM:
        return CMD_DOUBLE_HEIGHT, 2, 48  # Double H, 48 chars/line
    else:  # SMALL
        return CMD_NORMAL, 1, 48  # Normal, 48 chars/line


def word_wrap(text: str, max_chars: int) -> List[str]:
    """Wrap text to fit within max_chars per line."""
    words = text.split()
    lines = []
    current_line = []
    current_length = 0
    
    for word in words:
        word_length = len(word)
        
        # If single word is longer than max, split it
        if word_length > max_chars:
            if current_line:
                lines.append(' '.join(current_line))
                current_line = []
                current_length = 0
            
            # Split long word
            for i in range(0, word_length, max_chars):
                lines.append(word[i:i + max_chars])
            continue
        
        # Check if word fits on current line
        new_length = current_length + word_length + (1 if current_line else 0)
        
        if new_length <= max_chars:
            current_line.append(word)
            current_length = new_length
        else:
            # Start new line
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
            current_length = word_length
    
    if current_line:
        lines.append(' '.join(current_line))
    
    return lines if lines else ['']


# Character substitutions for thermal printer compatibility
# Maps Unicode characters to ASCII equivalents
CHAR_SUBSTITUTIONS = {
    # Bullets and list markers
    '•': '-',
    '◦': '-',
    '▪': '-',
    '▫': '-',
    '●': '*',
    '○': 'o',
    '■': '#',
    '□': '[ ]',
    '✓': '[x]',
    '✔': '[x]',
    '✗': '[ ]',
    '✘': '[ ]',
    # Arrows
    '→': '->',
    '←': '<-',
    '↑': '^',
    '↓': 'v',
    '⇒': '=>',
    '⇐': '<=',
    # Quotes
    '"': '"',
    '"': '"',
    ''': "'",
    ''': "'",
    '«': '<<',
    '»': '>>',
    # Dashes
    '–': '-',
    '—': '--',
    '―': '-',
    # Ellipsis
    '…': '...',
    # Math symbols
    '×': 'x',
    '÷': '/',
    '±': '+/-',
    '≈': '~',
    '≠': '!=',
    '≤': '<=',
    '≥': '>=',
    '°': ' deg',
    '′': "'",
    '″': '"',
    # Fractions
    '½': '1/2',
    '⅓': '1/3',
    '¼': '1/4',
    '¾': '3/4',
    '⅔': '2/3',
    # Currency (keep $ as-is, it's ASCII)
    '€': 'EUR',
    '£': 'GBP',
    '¥': 'JPY',
    '¢': 'c',
    # Other common symbols
    '©': '(c)',
    '®': '(R)',
    '™': '(TM)',
    '·': '-',
    '†': '+',
    '‡': '++',
    '§': 'S',
    '¶': 'P',
    # Spacing
    '\u00a0': ' ',  # Non-breaking space
    '\u2003': ' ',  # Em space
    '\u2002': ' ',  # En space
    '\u2009': ' ',  # Thin space
}


def normalize_text(text: str) -> str:
    """
    Normalize Unicode text for thermal printer compatibility.
    Replaces special characters with ASCII equivalents.
    """
    # Apply known substitutions
    for char, replacement in CHAR_SUBSTITUTIONS.items():
        text = text.replace(char, replacement)
    
    # Handle remaining non-ASCII characters
    result = []
    for char in text:
        code = ord(char)
        if code < 128:
            # Standard ASCII - keep as-is
            result.append(char)
        elif code < 256:
            # Extended ASCII (128-255) - printer may support some
            # Try to keep accented Latin characters
            result.append(char)
        else:
            # Unicode beyond Latin-1 - replace with ?
            result.append('?')
    
    return ''.join(result)


class MarkdownToPrinter:
    """Convert Markdown to ESC/POS commands."""
    
    def __init__(self, font_size: str = FontSize.SMALL):
        self.font_size = font_size
        self.base_cmd, self.height_mult, self.chars_per_line = get_font_settings(font_size)
        self.commands: List[Tuple[str, any]] = []
        self.total_dots = 0
        
    def reset(self):
        """Reset state for new document."""
        self.commands = []
        self.total_dots = 0
    
    def add_line(self, height_dots: int):
        """Track line height for length calculation."""
        self.total_dots += height_dots
    
    def get_length_inches(self) -> float:
        """Get total print length in inches."""
        return self.total_dots / DPI
    
    def process_heading(self, text: str, level: int):
        """Process heading (H1, H2, H3+)."""
        if level == 1:
            # H1: Double width + height
            cmd = CMD_DOUBLE_WH
            chars = 24
            height = FONT_A_HEIGHT * 2
        elif level == 2:
            # H2: Double height only
            cmd = CMD_DOUBLE_HEIGHT
            chars = 48
            height = FONT_A_HEIGHT * 2
        else:
            # H3+: Bold
            self.commands.append(('raw', CMD_BOLD_ON))
            lines = word_wrap(text, self.chars_per_line)
            for line in lines:
                self.commands.append(('text', line + '\n'))
                self.add_line(FONT_A_HEIGHT * self.height_mult + DEFAULT_LINE_SPACING)
            self.commands.append(('raw', CMD_BOLD_OFF))
            return
        
        self.commands.append(('raw', cmd))
        lines = word_wrap(text, chars)
        for line in lines:
            self.commands.append(('text', line + '\n'))
            self.add_line(height + DEFAULT_LINE_SPACING)
        self.commands.append(('raw', self.base_cmd))
    
    def process_paragraph(self, text: str):
        """Process regular paragraph text."""
        lines = word_wrap(text, self.chars_per_line)
        for line in lines:
            self.commands.append(('text', line + '\n'))
            self.add_line(FONT_A_HEIGHT * self.height_mult + DEFAULT_LINE_SPACING)
    
    def process_bold(self, text: str):
        """Process bold text inline."""
        self.commands.append(('raw', CMD_BOLD_ON))
        self.commands.append(('text', text))
        self.commands.append(('raw', CMD_BOLD_OFF))
    
    def process_code(self, text: str):
        """Process inline code or code block using Font B."""
        self.commands.append(('raw', CMD_FONT_B))
        # Font B has 64 chars/line
        lines = word_wrap(text, 64)
        for line in lines:
            self.commands.append(('text', line + '\n'))
            self.add_line(FONT_B_HEIGHT + DEFAULT_LINE_SPACING)
        self.commands.append(('raw', CMD_FONT_A))
    
    def process_hr(self):
        """Process horizontal rule as dashes."""
        self.commands.append(('text', '-' * self.chars_per_line + '\n'))
        self.add_line(FONT_A_HEIGHT * self.height_mult + DEFAULT_LINE_SPACING)
    
    def process_newline(self):
        """Add blank line."""
        self.commands.append(('text', '\n'))
        self.add_line(DEFAULT_LINE_SPACING)


def extract_text(tokens) -> str:
    """Extract plain text from mistune tokens."""
    if isinstance(tokens, str):
        return tokens
    
    if tokens is None:
        return ''
    
    text = ''
    for token in tokens:
        if isinstance(token, str):
            text += token
        elif isinstance(token, dict):
            token_type = token.get('type', '')
            if token_type == 'text':
                text += token.get('raw', token.get('text', ''))
            elif token_type == 'codespan':
                text += token.get('raw', token.get('text', ''))
            elif token_type == 'strong':
                text += extract_text(token.get('children', []))
            elif token_type == 'emphasis':
                text += extract_text(token.get('children', []))
            elif 'children' in token:
                text += extract_text(token['children'])
            elif 'raw' in token:
                text += token['raw']
            elif 'text' in token:
                text += token['text']
    return text


def parse_markdown_simple(text: str, font_size: str = FontSize.SMALL) -> Tuple[List[Tuple], float]:
    """
    Simple line-by-line Markdown parser for thermal printer.
    
    Line break rules:
    - Single line break = line break in output
    - Double line break (empty line) = paragraph break (extra spacing)
    
    Supports:
    - # ## ### Headings
    - **bold** text (markers stripped)
    - ``` code blocks ```
    - --- horizontal rules
    """
    import re
    
    # Normalize Unicode characters for printer compatibility
    text = normalize_text(text)
    
    printer = MarkdownToPrinter(font_size)
    printer.commands.append(('raw', printer.base_cmd))
    
    lines = text.split('\n')
    in_code_block = False
    code_buffer = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Code block start/end
        if line.strip().startswith('```'):
            if in_code_block:
                # End code block
                if code_buffer:
                    printer.process_code('\n'.join(code_buffer))
                code_buffer = []
                in_code_block = False
            else:
                # Start code block
                in_code_block = True
            i += 1
            continue
        
        if in_code_block:
            code_buffer.append(line)
            i += 1
            continue
        
        # Empty line = paragraph break
        if not line.strip():
            printer.process_newline()
            i += 1
            continue
        
        # Horizontal rule
        if re.match(r'^-{3,}$|^\*{3,}$|^_{3,}$', line.strip()):
            printer.process_hr()
            i += 1
            continue
        
        # Headings
        heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if heading_match:
            level = len(heading_match.group(1))
            heading_text = heading_match.group(2).strip()
            # Remove trailing #s if present
            heading_text = re.sub(r'\s*#+\s*$', '', heading_text)
            printer.process_heading(heading_text, level)
            i += 1
            continue
        
        # Regular line - process as single line, respecting line breaks
        line_text = line.strip()
        
        # Strip bold markers
        line_text = re.sub(r'\*\*(.+?)\*\*', r'\1', line_text)
        line_text = re.sub(r'__(.+?)__', r'\1', line_text)
        
        # Strip inline code markers
        line_text = re.sub(r'`(.+?)`', r'\1', line_text)
        
        printer.process_paragraph(line_text)
        i += 1
    
    # Handle unclosed code block
    if code_buffer:
        printer.process_code('\n'.join(code_buffer))
    
    return printer.commands, printer.get_length_inches()


def parse_markdown(markdown_text: str, font_size: str = FontSize.SMALL) -> Tuple[List[Tuple], float]:
    """
    Parse Markdown and convert to ESC/POS commands.
    Uses simple line-based parser for reliability.
    
    Args:
        markdown_text: Input Markdown string
        font_size: Font size preset ('small', 'medium', 'large')
    
    Returns:
        Tuple of (list of command tuples, estimated length in inches)
    """
    return parse_markdown_simple(markdown_text, font_size)


# Preview generation using PIL
def generate_preview(
    markdown_text: str,
    font_size: str = FontSize.SMALL,
    width: int = PRINT_WIDTH_DOTS
) -> Tuple[Image.Image, float]:
    """
    Generate a 1-bit preview image simulating thermal printer output.
    
    Args:
        markdown_text: Input Markdown string
        font_size: Font size preset
        width: Image width in pixels
    
    Returns:
        Tuple of (1-bit PIL Image, estimated length in inches)
    """
    # Parse markdown to get structure and length estimate
    commands, length_inches = parse_markdown(markdown_text, font_size)
    
    # Calculate image height based on estimated dots
    height = int(length_inches * DPI) + 50  # Add some padding
    height = max(height, 100)  # Minimum height
    
    # Create image
    image = Image.new('1', (width, height), 1)  # White background
    draw = ImageDraw.Draw(image)
    
    # Try to load a monospace font, fall back to default
    try:
        # Try common monospace fonts
        font_normal = ImageFont.truetype("DejaVuSansMono.ttf", 12)
        font_bold = ImageFont.truetype("DejaVuSansMono-Bold.ttf", 12)
        font_small = ImageFont.truetype("DejaVuSansMono.ttf", 10)
        font_large = ImageFont.truetype("DejaVuSansMono.ttf", 16)
        font_xlarge = ImageFont.truetype("DejaVuSansMono-Bold.ttf", 20)
    except:
        try:
            font_normal = ImageFont.truetype("LiberationMono-Regular.ttf", 12)
            font_bold = ImageFont.truetype("LiberationMono-Bold.ttf", 12)
            font_small = ImageFont.truetype("LiberationMono-Regular.ttf", 10)
            font_large = ImageFont.truetype("LiberationMono-Regular.ttf", 16)
            font_xlarge = ImageFont.truetype("LiberationMono-Bold.ttf", 20)
        except:
            # Use default font
            font_normal = ImageFont.load_default()
            font_bold = font_normal
            font_small = font_normal
            font_large = font_normal
            font_xlarge = font_normal
    
    # Get base settings
    base_cmd, height_mult, chars_per_line = get_font_settings(font_size)
    
    # Select base font based on size
    if font_size == FontSize.LARGE:
        current_font = font_xlarge
        line_height = 28
    elif font_size == FontSize.MEDIUM:
        current_font = font_large
        line_height = 22
    else:
        current_font = font_normal
        line_height = 16
    
    y = 10
    is_bold = False
    is_code = False
    
    for cmd_type, data in commands:
        if cmd_type == 'raw':
            # Handle style changes
            if data == CMD_BOLD_ON:
                is_bold = True
            elif data == CMD_BOLD_OFF:
                is_bold = False
            elif data == CMD_FONT_B:
                is_code = True
                current_font = font_small
            elif data == CMD_FONT_A:
                is_code = False
                if font_size == FontSize.LARGE:
                    current_font = font_xlarge
                elif font_size == FontSize.MEDIUM:
                    current_font = font_large
                else:
                    current_font = font_normal
            elif data == CMD_DOUBLE_WH:
                current_font = font_xlarge
            elif data == CMD_DOUBLE_HEIGHT:
                current_font = font_large
            elif data in (CMD_NORMAL, base_cmd):
                if font_size == FontSize.LARGE:
                    current_font = font_xlarge
                elif font_size == FontSize.MEDIUM:
                    current_font = font_large
                else:
                    current_font = font_normal
        
        elif cmd_type == 'text':
            text = data.rstrip('\n')
            if text:
                font = font_bold if is_bold and not is_code else current_font
                draw.text((10, y), text, font=font, fill=0)
            
            if data.endswith('\n'):
                y += line_height
    
    # Crop to actual content height
    final_height = y + 20
    image = image.crop((0, 0, width, final_height))
    
    # Recalculate length based on actual height
    length_inches = final_height / DPI
    
    return image, length_inches


def preview_to_base64(image: Image.Image) -> str:
    """Convert preview image to base64 PNG string."""
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    buffer.seek(0)
    return base64.b64encode(buffer.getvalue()).decode('utf-8')
