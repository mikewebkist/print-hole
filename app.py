"""
Print Hole - Flask application for thermal printer web interface.
"""

from flask import Flask, render_template, request, jsonify
import base64
from io import BytesIO

from image_processor import (
    process_image,
    image_to_base64,
    base64_to_image,
    RotationMode,
    PRINT_WIDTH_DOTS,
    DPI
)
from markdown_printer import (
    parse_markdown,
    generate_preview,
    preview_to_base64,
    FontSize
)
from printer import get_printer

app = Flask(__name__)

# Maximum print length warning threshold (inches)
MAX_LENGTH_INCHES = 12.0


@app.route('/')
def index():
    """Serve the single-page application."""
    return render_template('index.html')


@app.route('/api/preview', methods=['POST'])
def preview():
    """
    Generate preview for text or image content.
    
    Request JSON:
    {
        "mode": "text" | "image",
        "content": string (markdown text or base64 image),
        "fontSize": "small" | "medium" | "large" (for text mode),
        "rotation": "auto" | "original" | "square" (for image mode)
    }
    
    Response JSON:
    {
        "preview": string (base64 PNG),
        "lengthInches": float,
        "warning": bool (true if > 12 inches)
    }
    """
    try:
        data = request.get_json()
        mode = data.get('mode', 'text')
        content = data.get('content', '')
        
        if not content:
            return jsonify({
                'preview': '',
                'lengthInches': 0,
                'warning': False
            })
        
        if mode == 'text':
            # Process markdown text
            font_size = data.get('fontSize', 'small')
            if font_size not in ('small', 'medium', 'large'):
                font_size = 'small'
            
            preview_image, length_inches = generate_preview(content, font_size)
            preview_base64 = preview_to_base64(preview_image)
        
        else:
            # Process image
            rotation = data.get('rotation', 'auto')
            if rotation not in ('auto', 'original', 'square'):
                rotation = 'auto'
            
            # Decode base64 image
            image = base64_to_image(content)
            
            # Process image
            rotation_mode = RotationMode(rotation)
            processed_image, length_inches = process_image(image, rotation_mode)
            preview_base64 = image_to_base64(processed_image)
        
        return jsonify({
            'preview': preview_base64,
            'lengthInches': round(length_inches, 2),
            'warning': length_inches > MAX_LENGTH_INCHES
        })
    
    except Exception as e:
        return jsonify({
            'error': str(e)
        }), 400


@app.route('/api/print', methods=['POST'])
def print_content():
    """
    Print text or image content.
    
    Request JSON:
    {
        "mode": "text" | "image",
        "content": string (markdown text or base64 image),
        "fontSize": "small" | "medium" | "large" (for text mode),
        "rotation": "auto" | "original" | "square" (for image mode)
    }
    
    Response JSON:
    {
        "success": bool,
        "error": string (if failed)
    }
    """
    try:
        data = request.get_json()
        mode = data.get('mode', 'text')
        content = data.get('content', '')
        
        if not content:
            return jsonify({
                'success': False,
                'error': 'No content to print'
            })
        
        printer = get_printer()
        
        if mode == 'text':
            # Parse markdown and send ESC/POS commands
            font_size = data.get('fontSize', 'small')
            if font_size not in ('small', 'medium', 'large'):
                font_size = 'small'
            
            commands, _ = parse_markdown(content, font_size)
            success, error = printer.print_text_commands(commands)
        
        else:
            # Process and print image
            rotation = data.get('rotation', 'auto')
            if rotation not in ('auto', 'original', 'square'):
                rotation = 'auto'
            
            image = base64_to_image(content)
            rotation_mode = RotationMode(rotation)
            processed_image, _ = process_image(image, rotation_mode)
            
            success, error = printer.print_image(processed_image)
        
        return jsonify({
            'success': success,
            'error': error if not success else ''
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    # Run on all interfaces for local network access
    app.run(host='0.0.0.0', port=5000, debug=True)
