# Print Hole

A single-page Flask web app for printing to an 80mm USB thermal printer from any device on your local network.

## Features

- **Text Mode**: Type or paste Markdown text with heading, bold, and code block support
- **Image Mode**: Paste, drag-and-drop, or upload images
- **Live Preview**: See exactly what will print with 1-bit dithering preview
- **Length Estimation**: Know how long your print will be (warns if >12")
- **Mobile Friendly**: Responsive Bootstrap UI works on phones and tablets
- **Native Printer Fonts**: Uses ESC/POS commands for crisp text output

## Requirements

- Raspberry Pi (or any Linux system)
- Python 3.8+
- 80mm USB thermal printer (ESC/POS compatible)

## Installation

1. Clone or download this project:
   ```bash
   cd /home/pi/Source/print-hole
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. Configure your printer:
   ```bash
   # Find your printer's USB IDs
   lsusb
   # Look for your printer, e.g.: ID 0483:5720
   
   # Copy and edit the config file
   cp print-hole.conf.example ~/.print-hole.conf
   nano ~/.print-hole.conf
   ```

4. Set up USB permissions (optional, to run without sudo):
   ```bash
   # Create udev rule for your printer
   echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="0483", ATTR{idProduct}=="5720", MODE="0666"' | sudo tee /etc/udev/rules.d/99-thermal-printer.rules
   sudo udevadm control --reload-rules
   # Reconnect the printer
   ```

## Usage

1. Start the server:
   ```bash
   source venv/bin/activate
   python app.py
   ```

2. Open in your browser:
   - Local: http://localhost:5000
   - Network: http://[raspberry-pi-ip]:5000

3. Select Text or Image mode, enter content, and click Print!

## Markdown Support

- `# Heading 1` - Large bold text (2× width + height)
- `## Heading 2` - Medium text (2× height)
- `### Heading 3` - Bold text
- `**bold**` - Bold emphasis
- `` `code` `` - Monospace font (Font B)
- `---` - Horizontal rule

## Image Modes

- **Auto**: Rotates portrait images to landscape for maximum print width
- **Original**: Keeps image orientation unchanged
- **Square**: Center-crops to 1:1 aspect ratio

## Configuration

Edit `~/.print-hole.conf`:

```ini
[printer]
vendor_id = 0x0483
product_id = 0x5720
profile = 
```

## Production Deployment (systemd)

To run Print Hole automatically on startup:

1. **Install gunicorn** (production WSGI server):
   ```bash
   source venv/bin/activate
   pip install gunicorn
   ```

2. **Edit the service file** for your setup:
   ```bash
   # Update paths if not using /home/pi/Source/print-hole
   nano print-hole.service
   ```

3. **Install and enable the service**:
   ```bash
   sudo cp print-hole.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable print-hole
   sudo systemctl start print-hole
   ```

4. **Check status**:
   ```bash
   sudo systemctl status print-hole
   sudo journalctl -u print-hole -f  # View logs
   ```

### Running on Port 80

**Option A: Use iptables redirect (recommended)**
```bash
# Redirect port 80 to 8080 (no root required for the app)
sudo iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 8080
sudo iptables -t nat -A OUTPUT -o lo -p tcp --dport 80 -j REDIRECT --to-port 8080

# Make persistent (Debian/Ubuntu)
sudo apt install iptables-persistent
sudo netfilter-persistent save
```

**Option B: Use nginx as reverse proxy**
```bash
sudo apt install nginx
```

Create `/etc/nginx/sites-available/print-hole`:
```nginx
server {
    listen 80;
    server_name _;
    
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        client_max_body_size 20M;
    }
}
```

Then enable:
```bash
sudo ln -s /etc/nginx/sites-available/print-hole /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo systemctl restart nginx
```

**Option C: Bind directly to port 80** (requires `CAP_NET_BIND_SERVICE`):
```bash
# Edit service file to bind to port 80
sudo setcap 'cap_net_bind_service=+ep' /home/pi/Source/print-hole/venv/bin/gunicorn
# Then change --bind to 0.0.0.0:80 in print-hole.service
```

## Troubleshooting

**Printer not found:**
- Check USB connection: `lsusb`
- Verify vendor/product IDs in config
- Check USB permissions (try running with sudo once to test)

**Print quality issues:**
- For images, try different rotation modes
- For text, adjust font size
- Ensure paper is loaded correctly

## License

MIT

