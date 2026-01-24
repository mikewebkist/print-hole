/**
 * Print Hole - Frontend JavaScript
 * Handles preview updates, image paste/upload, and print functionality.
 */

// DOM Elements
const modeRadios = document.querySelectorAll('input[name="mode"]');
const textSection = document.getElementById('textSection');
const imageSection = document.getElementById('imageSection');
const drawSection = document.getElementById('drawSection');
const aiSection = document.getElementById('aiSection');
const textInput = document.getElementById('textInput');
const fontSize = document.getElementById('fontSize');
const printerSelect = document.getElementById('printerSelect');
const rotationRadios = document.querySelectorAll('input[name="rotation"]');
const aiRotationRadios = document.querySelectorAll('input[name="aiRotation"]');
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const imageInfo = document.getElementById('imageInfo');
const imageName = document.getElementById('imageName');
const clearImage = document.getElementById('clearImage');
const aiPrompt = document.getElementById('aiPrompt');
const generateBtn = document.getElementById('generateBtn');
const aiImageInfo = document.getElementById('aiImageInfo');
const clearAiImage = document.getElementById('clearAiImage');
const drawCanvas = document.getElementById('drawCanvas');
const clearCanvasBtn = document.getElementById('clearCanvas');
const undoCanvasBtn = document.getElementById('undoCanvas');
const brushSizeInput = document.getElementById('brushSize');
const brushSizeValue = document.getElementById('brushSizeValue');
const previewPlaceholder = document.getElementById('previewPlaceholder');
const previewImage = document.getElementById('previewImage');
const lengthBadge = document.getElementById('lengthBadge');
const lengthWarning = document.getElementById('lengthWarning');
const rolloInfo = document.getElementById('rolloInfo');
const printBtn = document.getElementById('printBtn');
const confirmModal = new bootstrap.Modal(document.getElementById('confirmModal'));
const confirmLength = document.getElementById('confirmLength');
const confirmPrint = document.getElementById('confirmPrint');
const errorToast = new bootstrap.Toast(document.getElementById('errorToast'));
const errorMessage = document.getElementById('errorMessage');
const successToast = new bootstrap.Toast(document.getElementById('successToast'));

// State
let currentMode = 'text';
let currentImageData = null;
let currentAiImageData = null;
let previewDebounceTimer = null;
let currentLengthInches = 0;
let currentPrinter = 'usb';

// Drawing state
let isDrawing = false;
let lastX = 0;
let lastY = 0;
let drawingHistory = [];
let brushSize = 8;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupPrinterSelect();
    setupModeToggle();
    setupTextInput();
    setupImageInput();
    setupDrawInput();
    setupAiInput();
    setupPrintButton();
});

// Printer Selection
function setupPrinterSelect() {
    printerSelect.addEventListener('change', (e) => {
        currentPrinter = e.target.value;
        
        // Update UI hints based on printer
        const isRollo = currentPrinter === 'rollo';
        
        // Show info about Rollo's fixed paper size
        if (rolloInfo) {
            rolloInfo.classList.toggle('d-none', !isRollo);
        }
        
        // Update preview if there's content
        if (currentMode === 'text' && textInput.value) {
            updatePreview();
        } else if (currentMode === 'image' && currentImageData) {
            updatePreview();
        } else if (currentMode === 'draw') {
            updateDrawPreview();
        } else if (currentMode === 'ai' && currentAiImageData) {
            updateAiPreview();
        }
    });
}

// Mode Toggle
function setupModeToggle() {
    modeRadios.forEach(radio => {
        radio.addEventListener('change', (e) => {
            currentMode = e.target.value;
            
            // Hide all sections first
            textSection.classList.add('d-none');
            imageSection.classList.add('d-none');
            drawSection.classList.add('d-none');
            aiSection.classList.add('d-none');
            
            if (currentMode === 'text') {
                textSection.classList.remove('d-none');
                updatePreview();
            } else if (currentMode === 'image') {
                imageSection.classList.remove('d-none');
                if (currentImageData) {
                    updatePreview();
                } else {
                    resetPreview();
                }
            } else if (currentMode === 'draw') {
                drawSection.classList.remove('d-none');
                updateDrawPreview();
            } else if (currentMode === 'ai') {
                aiSection.classList.remove('d-none');
                if (currentAiImageData) {
                    updateAiPreview();
                } else {
                    resetPreview();
                }
            }
        });
    });
}

// Text Input
function setupTextInput() {
    // Debounced preview update
    textInput.addEventListener('input', () => {
        clearTimeout(previewDebounceTimer);
        previewDebounceTimer = setTimeout(updatePreview, 500);
    });
    
    fontSize.addEventListener('change', updatePreview);
}

// Image Input
function setupImageInput() {
    // Click to upload
    dropZone.addEventListener('click', () => fileInput.click());
    
    // File input change
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleImageFile(e.target.files[0]);
        }
    });
    
    // Drag and drop
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('drag-over');
    });
    
    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('drag-over');
    });
    
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('drag-over');
        
        if (e.dataTransfer.files.length > 0) {
            handleImageFile(e.dataTransfer.files[0]);
        }
    });
    
    // Paste handler (works globally)
    document.addEventListener('paste', (e) => {
        const items = e.clipboardData?.items;
        if (!items) return;
        
        for (const item of items) {
            if (item.type.startsWith('image/')) {
                e.preventDefault();
                const file = item.getAsFile();
                handleImageFile(file);
                
                // Switch to image mode if not already
                if (currentMode !== 'image') {
                    document.getElementById('modeImage').click();
                }
                break;
            }
        }
    });
    
    // Rotation change
    rotationRadios.forEach(radio => {
        radio.addEventListener('change', () => {
            if (currentImageData) {
                updatePreview();
            }
        });
    });
    
    // Clear image
    clearImage.addEventListener('click', () => {
        currentImageData = null;
        imageInfo.classList.add('d-none');
        fileInput.value = '';
        resetPreview();
    });
}

// Draw Input
function setupDrawInput() {
    const ctx = drawCanvas.getContext('2d');
    
    // Initialize canvas with white background
    clearCanvas();
    
    // Get position from mouse or touch event
    function getPosition(e) {
        const rect = drawCanvas.getBoundingClientRect();
        const scaleX = drawCanvas.width / rect.width;
        const scaleY = drawCanvas.height / rect.height;
        
        if (e.touches && e.touches.length > 0) {
            return {
                x: (e.touches[0].clientX - rect.left) * scaleX,
                y: (e.touches[0].clientY - rect.top) * scaleY
            };
        }
        return {
            x: (e.clientX - rect.left) * scaleX,
            y: (e.clientY - rect.top) * scaleY
        };
    }
    
    function startDrawing(e) {
        e.preventDefault();
        isDrawing = true;
        const pos = getPosition(e);
        lastX = pos.x;
        lastY = pos.y;
        
        // Draw a dot for single clicks
        ctx.beginPath();
        ctx.arc(lastX, lastY, brushSize / 2, 0, Math.PI * 2);
        ctx.fillStyle = '#000';
        ctx.fill();
    }
    
    function draw(e) {
        if (!isDrawing) return;
        e.preventDefault();
        
        const pos = getPosition(e);
        
        ctx.beginPath();
        ctx.moveTo(lastX, lastY);
        ctx.lineTo(pos.x, pos.y);
        ctx.strokeStyle = '#000';
        ctx.lineWidth = brushSize;
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        ctx.stroke();
        
        lastX = pos.x;
        lastY = pos.y;
    }
    
    function stopDrawing(e) {
        if (isDrawing) {
            e.preventDefault();
            isDrawing = false;
            saveToHistory();
            updateDrawPreview();
        }
    }
    
    // Mouse events
    drawCanvas.addEventListener('mousedown', startDrawing);
    drawCanvas.addEventListener('mousemove', draw);
    drawCanvas.addEventListener('mouseup', stopDrawing);
    drawCanvas.addEventListener('mouseout', stopDrawing);
    
    // Touch events
    drawCanvas.addEventListener('touchstart', startDrawing, { passive: false });
    drawCanvas.addEventListener('touchmove', draw, { passive: false });
    drawCanvas.addEventListener('touchend', stopDrawing, { passive: false });
    drawCanvas.addEventListener('touchcancel', stopDrawing, { passive: false });
    
    // Clear button
    clearCanvasBtn.addEventListener('click', () => {
        clearCanvas();
        saveToHistory();
        updateDrawPreview();
    });
    
    // Undo button
    undoCanvasBtn.addEventListener('click', () => {
        if (drawingHistory.length > 1) {
            drawingHistory.pop();
            const img = new Image();
            img.onload = () => {
                ctx.clearRect(0, 0, drawCanvas.width, drawCanvas.height);
                ctx.drawImage(img, 0, 0);
                updateDrawPreview();
            };
            img.src = drawingHistory[drawingHistory.length - 1];
        } else {
            clearCanvas();
            updateDrawPreview();
        }
    });
    
    // Brush size
    brushSizeInput.addEventListener('input', (e) => {
        brushSize = parseInt(e.target.value);
        brushSizeValue.textContent = brushSize;
    });
}

function clearCanvas() {
    const ctx = drawCanvas.getContext('2d');
    ctx.fillStyle = '#fff';
    ctx.fillRect(0, 0, drawCanvas.width, drawCanvas.height);
}

function saveToHistory() {
    drawingHistory.push(drawCanvas.toDataURL('image/png'));
    // Limit history to 20 states
    if (drawingHistory.length > 20) {
        drawingHistory.shift();
    }
}

async function updateDrawPreview() {
    const canvasData = drawCanvas.toDataURL('image/png');
    
    try {
        const response = await fetch('/api/preview', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                mode: 'image',
                content: canvasData,
                rotation: 'original'
            })
        });
        
        const data = await response.json();
        
        if (data.error) {
            showError(data.error);
            return;
        }
        
        // Show preview
        if (data.preview) {
            previewImage.src = 'data:image/png;base64,' + data.preview;
            previewImage.classList.remove('d-none');
            previewPlaceholder.classList.add('d-none');
            printBtn.disabled = false;
        }
        
        // Update length display
        currentLengthInches = data.lengthInches;
        lengthBadge.textContent = data.lengthInches.toFixed(1) + '"';
        
        // Warning
        if (data.warning) {
            lengthBadge.classList.remove('bg-secondary', 'bg-success');
            lengthBadge.classList.add('bg-danger');
            lengthWarning.classList.remove('d-none');
        } else {
            lengthBadge.classList.remove('bg-danger', 'bg-secondary');
            lengthBadge.classList.add('bg-success');
            lengthWarning.classList.add('d-none');
        }
        
    } catch (error) {
        showError('Failed to update preview: ' + error.message);
    }
}

// AI Input
function setupAiInput() {
    // Generate button
    generateBtn.addEventListener('click', generateAiImage);
    
    // AI rotation change - re-process existing image
    aiRotationRadios.forEach(radio => {
        radio.addEventListener('change', () => {
            if (currentAiImageData) {
                updateAiPreview();
            }
        });
    });
    
    // Clear AI image
    clearAiImage.addEventListener('click', () => {
        currentAiImageData = null;
        aiImageInfo.classList.add('d-none');
        resetPreview();
    });
}

// Generate AI image
async function generateAiImage() {
    const prompt = aiPrompt.value.trim();
    
    if (!prompt) {
        showError('Please enter a prompt to generate an image');
        return;
    }
    
    generateBtn.disabled = true;
    generateBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Generating...';
    
    try {
        const rotation = document.querySelector('input[name="aiRotation"]:checked').value;
        
        const response = await fetch('/api/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                prompt: prompt,
                rotation: rotation
            })
        });
        
        const data = await response.json();
        
        if (data.error) {
            showError(data.error);
            return;
        }
        
        // Store the generated image data (original, not processed)
        currentAiImageData = 'data:image/png;base64,' + data.image;
        aiImageInfo.classList.remove('d-none');
        
        // Show preview
        previewImage.src = 'data:image/png;base64,' + data.preview;
        previewImage.classList.remove('d-none');
        previewPlaceholder.classList.add('d-none');
        printBtn.disabled = false;
        
        // Update length display
        currentLengthInches = data.lengthInches;
        lengthBadge.textContent = data.lengthInches.toFixed(1) + '"';
        
        // Warning
        if (data.warning) {
            lengthBadge.classList.remove('bg-secondary', 'bg-success');
            lengthBadge.classList.add('bg-danger');
            lengthWarning.classList.remove('d-none');
        } else {
            lengthBadge.classList.remove('bg-danger', 'bg-secondary');
            lengthBadge.classList.add('bg-success');
            lengthWarning.classList.add('d-none');
        }
        
    } catch (error) {
        showError('Failed to generate image: ' + error.message);
    } finally {
        generateBtn.disabled = false;
        generateBtn.innerHTML = '<i class="bi bi-stars"></i> Generate Image';
    }
}

// Update AI preview (when rotation changes)
async function updateAiPreview() {
    if (!currentAiImageData) {
        resetPreview();
        return;
    }
    
    try {
        const rotation = document.querySelector('input[name="aiRotation"]:checked').value;
        
        const response = await fetch('/api/preview', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                mode: 'image',
                content: currentAiImageData,
                rotation: rotation
            })
        });
        
        const data = await response.json();
        
        if (data.error) {
            showError(data.error);
            return;
        }
        
        // Show preview
        if (data.preview) {
            previewImage.src = 'data:image/png;base64,' + data.preview;
            previewImage.classList.remove('d-none');
            previewPlaceholder.classList.add('d-none');
            printBtn.disabled = false;
        }
        
        // Update length display
        currentLengthInches = data.lengthInches;
        lengthBadge.textContent = data.lengthInches.toFixed(1) + '"';
        
        // Warning
        if (data.warning) {
            lengthBadge.classList.remove('bg-secondary', 'bg-success');
            lengthBadge.classList.add('bg-danger');
            lengthWarning.classList.remove('d-none');
        } else {
            lengthBadge.classList.remove('bg-danger', 'bg-secondary');
            lengthBadge.classList.add('bg-success');
            lengthWarning.classList.add('d-none');
        }
        
    } catch (error) {
        showError('Failed to update preview: ' + error.message);
    }
}

// Handle image file
function handleImageFile(file) {
    if (!file.type.startsWith('image/')) {
        showError('Please select an image file');
        return;
    }
    
    const reader = new FileReader();
    reader.onload = (e) => {
        currentImageData = e.target.result;
        imageName.textContent = file.name || 'Pasted image';
        imageInfo.classList.remove('d-none');
        updatePreview();
    };
    reader.onerror = () => {
        showError('Failed to read image file');
    };
    reader.readAsDataURL(file);
}

// Preview Update
async function updatePreview() {
    const content = currentMode === 'text' ? textInput.value : currentImageData;
    
    if (!content) {
        resetPreview();
        return;
    }
    
    try {
        const response = await fetch('/api/preview', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                mode: currentMode,
                content: content,
                fontSize: fontSize.value,
                rotation: document.querySelector('input[name="rotation"]:checked').value
            })
        });
        
        const data = await response.json();
        
        if (data.error) {
            showError(data.error);
            resetPreview();
            return;
        }
        
        // Show preview
        if (data.preview) {
            previewImage.src = 'data:image/png;base64,' + data.preview;
            previewImage.classList.remove('d-none');
            previewPlaceholder.classList.add('d-none');
            printBtn.disabled = false;
        }
        
        // Update length display
        currentLengthInches = data.lengthInches;
        lengthBadge.textContent = data.lengthInches.toFixed(1) + '"';
        
        // Warning
        if (data.warning) {
            lengthBadge.classList.remove('bg-secondary', 'bg-success');
            lengthBadge.classList.add('bg-danger');
            lengthWarning.classList.remove('d-none');
        } else {
            lengthBadge.classList.remove('bg-danger', 'bg-secondary');
            lengthBadge.classList.add('bg-success');
            lengthWarning.classList.add('d-none');
        }
        
    } catch (error) {
        showError('Failed to generate preview: ' + error.message);
        resetPreview();
    }
}

// Reset preview state
function resetPreview() {
    previewImage.classList.add('d-none');
    previewPlaceholder.classList.remove('d-none');
    lengthBadge.textContent = '0.0"';
    lengthBadge.classList.remove('bg-success', 'bg-danger');
    lengthBadge.classList.add('bg-secondary');
    lengthWarning.classList.add('d-none');
    printBtn.disabled = true;
    currentLengthInches = 0;
}

// Print Button
function setupPrintButton() {
    printBtn.addEventListener('click', () => {
        confirmLength.textContent = currentLengthInches.toFixed(1) + '"';
        confirmModal.show();
    });
    
    confirmPrint.addEventListener('click', async () => {
        confirmModal.hide();
        await sendPrint();
    });
}

// Send print job
async function sendPrint() {
    let content;
    if (currentMode === 'text') {
        content = textInput.value;
    } else if (currentMode === 'image') {
        content = currentImageData;
    } else if (currentMode === 'draw') {
        content = drawCanvas.toDataURL('image/png');
    } else {
        content = currentAiImageData;
    }
    
    if (!content) {
        showError('No content to print');
        return;
    }
    
    printBtn.disabled = true;
    printBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Printing...';
    
    try {
        let rotation = 'original';
        if (currentMode === 'ai') {
            rotation = document.querySelector('input[name="aiRotation"]:checked').value;
        } else if (currentMode === 'draw') {
            rotation = 'original';
        } else {
            rotation = document.querySelector('input[name="rotation"]:checked').value;
        }
        
        const response = await fetch('/api/print', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                mode: currentMode,
                content: content,
                fontSize: fontSize.value,
                rotation: rotation,
                printer: currentPrinter
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            successToast.show();
        } else {
            showError(data.error || 'Print failed');
        }
        
    } catch (error) {
        showError('Failed to send print job: ' + error.message);
    } finally {
        printBtn.disabled = false;
        printBtn.innerHTML = '<i class="bi bi-printer"></i> Print';
    }
}

// Show error toast
function showError(message) {
    errorMessage.textContent = message;
    errorToast.show();
}
