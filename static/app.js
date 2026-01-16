/**
 * Print Hole - Frontend JavaScript
 * Handles preview updates, image paste/upload, and print functionality.
 */

// DOM Elements
const modeRadios = document.querySelectorAll('input[name="mode"]');
const textSection = document.getElementById('textSection');
const imageSection = document.getElementById('imageSection');
const textInput = document.getElementById('textInput');
const fontSize = document.getElementById('fontSize');
const rotationRadios = document.querySelectorAll('input[name="rotation"]');
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const imageInfo = document.getElementById('imageInfo');
const imageName = document.getElementById('imageName');
const clearImage = document.getElementById('clearImage');
const previewPlaceholder = document.getElementById('previewPlaceholder');
const previewImage = document.getElementById('previewImage');
const lengthBadge = document.getElementById('lengthBadge');
const lengthWarning = document.getElementById('lengthWarning');
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
let previewDebounceTimer = null;
let currentLengthInches = 0;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupModeToggle();
    setupTextInput();
    setupImageInput();
    setupPrintButton();
});

// Mode Toggle
function setupModeToggle() {
    modeRadios.forEach(radio => {
        radio.addEventListener('change', (e) => {
            currentMode = e.target.value;
            
            if (currentMode === 'text') {
                textSection.classList.remove('d-none');
                imageSection.classList.add('d-none');
                updatePreview();
            } else {
                textSection.classList.add('d-none');
                imageSection.classList.remove('d-none');
                if (currentImageData) {
                    updatePreview();
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
    const content = currentMode === 'text' ? textInput.value : currentImageData;
    
    if (!content) {
        showError('No content to print');
        return;
    }
    
    printBtn.disabled = true;
    printBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Printing...';
    
    try {
        const response = await fetch('/api/print', {
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
