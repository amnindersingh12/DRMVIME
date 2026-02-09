// Popup script
// Update queue count
function updateStatus() {
    chrome.runtime.sendMessage({ action: 'getQueue' }, (queue) => {
        const count = queue ? queue.length : 0;
        document.getElementById('queueCount').textContent = count;
    });
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
                const status = lesson.status === 'downloaded' ? '✅' : '⏳';
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

// Update status on load
updateStatus();
setInterval(updateStatus, 2000);
