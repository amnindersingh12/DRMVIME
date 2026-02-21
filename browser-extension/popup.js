// Popup script
// Update queue count
function updateStatus() {
    chrome.runtime.sendMessage({ action: 'getQueue' }, (queue) => {
        const count = queue ? queue.length : 0;
        document.getElementById('queueCount').textContent = count;
    });
}

// Reload extension (development helper)
document.addEventListener('DOMContentLoaded', () => {
    document.addEventListener('keydown', (e) => {
        // Ctrl+Shift+R (or Cmd+Shift+R on Mac) to reload
        if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'R') {
            chrome.runtime.sendMessage({ type: 'RELOAD_EXTENSION' }, (response) => {
                console.log('✅ Extension reloaded');
            });
        }
    });
});

// Check if Python server is running
async function checkServer() {
    const dot = document.getElementById('serverDot');
    const text = document.getElementById('serverText');
    const box = document.getElementById('serverStatus');
    try {
        const resp = await fetch('http://localhost:8765/health', { method: 'GET' });
        const data = await resp.json();
        const qlen = data.queue_length ?? 0;
        dot.className = 'dot dot-green';
        box.className = 'server-status server-online';
        text.textContent = `Server online · ${qlen} lesson${qlen !== 1 ? 's' : ''} in queue`;
    } catch (_) {
        dot.className = 'dot dot-red';
        box.className = 'server-status server-offline';
        text.textContent = 'Server offline — run: python twinvine.py server';
    }
}

// View queue
document.getElementById('viewQueue').addEventListener('click', () => {
    chrome.runtime.sendMessage({ action: 'getQueue' }, (queue) => {
        const queueList = document.getElementById('queueList');

        if (!queue || queue.length === 0) {
            queueList.innerHTML = '<div style="padding: 10px; color: #5f6368;">Queue is empty</div>';
        } else {
            let html = '<div style="font-size: 12px;">';
            queue.forEach((lesson, index) => {
                const status = lesson.status === 'downloaded' ? '✅' : lesson.status === 'failed' ? '❌' : '⏳';
                html += `<div style="padding: 5px; border-bottom: 1px solid #ddd;">
          ${status} ${lesson.filename || `Lesson ${index + 1}`}
        </div>`;
            });
            html += '</div>';
            queueList.innerHTML = html;
        }

        queueList.style.display = queueList.style.display === 'none' ? 'block' : 'none';
    });
});

// Clear queue
document.getElementById('clearQueue').addEventListener('click', () => {
    if (confirm('Clear entire queue?')) {
        chrome.runtime.sendMessage({ action: 'clearQueue' }, () => {
            updateStatus();
            alert('Queue cleared!');
        });
    }
});

// Download PDF button
document.getElementById('downloadPdf').addEventListener('click', async () => {
    const btn = document.getElementById('downloadPdf');
    btn.disabled = true;
    btn.textContent = 'Downloading...';
    
    try {
        // Get captured PDF data from storage
        const result = await chrome.storage.local.get('capturedData');
        const data = result.capturedData || {};
        
        if (!data.pdfUrl) {
            alert('❌ No PDF captured yet.\n\nNavigate to a TestBook lesson page with a PDF attachment.');
            btn.disabled = false;
            btn.textContent = '📄 Download PDF';
            return;
        }
        
        // Send to server
        const response = await fetch('http://localhost:8765/download-pdf', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                pdf_url: data.pdfUrl,
                pdf_filename: data.pdfFilename || 'document.pdf',
                page_title: data.pageTitle || ''
            })
        });
        
        const result_data = await response.json();
        
        if (result_data.success) {
            alert(`✅ PDF Downloaded!\n\nFile: ${result_data.filename}\nSize: ${result_data.size_mb} MB\nSaved to: downloads/PDFs/`);
        } else {
            alert(`❌ Download failed: ${result_data.message}`);
        }
    } catch (error) {
        alert(`❌ Error: ${error.message}\n\nMake sure the server is running:\npython twinvine_server.py`);
    } finally {
        btn.disabled = false;
        btn.textContent = '📄 Download PDF';
    }
});

// Update status on load and periodically
updateStatus();
checkServer();
setInterval(updateStatus, 2000);
setInterval(checkServer, 5000);  // check server every 5s
