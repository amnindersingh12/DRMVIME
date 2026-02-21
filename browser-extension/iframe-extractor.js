// TwinVine iframe-extractor.js
// Runs INSIDE iframes to extract PDF links and send them to parent
// This bypasses cross-origin restrictions by running in the iframe's context

(function() {
    'use strict';
    
    // Only run if we're in an iframe
    if (window === window.top) return;
    
    console.log('[TwinVine] Iframe extractor loaded in:', window.location.href);
    
    let lastExtractedUrls = new Set();
    
    function extractAndSendPdfs() {
        const pdfLinks = [...document.querySelectorAll('a.pdf-bg')];
        if (pdfLinks.length === 0) return;
        
        const pdfs = pdfLinks.map(a => {
            const fullName = a.textContent.trim();
            const params = new URLSearchParams(a.href.split('?')[1]);
            const realUrl = decodeURIComponent(params.get('u') || '');
            
            // Extract actual filename from URL
            let filename = '';
            if (realUrl) {
                try {
                    const urlObj = new URL(realUrl);
                    filename = urlObj.pathname.split('/').pop() || '';
                    // If no extension, try to get from search params or add .pdf
                    if (!filename.includes('.')) {
                        filename = fullName.replace(/[^a-zA-Z0-9\s-_]/g, '').trim() + '.pdf';
                    }
                } catch (e) {
                    filename = fullName.replace(/[^a-zA-Z0-9\s-_]/g, '').trim() + '.pdf';
                }
            }
            
            return { 
                name: fullName,
                filename: filename,
                url: realUrl 
            };
        }).filter(pdf => pdf.url && pdf.name);
        
        // Filter out already sent PDFs
        const newPdfs = pdfs.filter(pdf => !lastExtractedUrls.has(pdf.url));
        if (newPdfs.length === 0) return;
        
        newPdfs.forEach(pdf => lastExtractedUrls.add(pdf.url));
        
        console.log('[TwinVine] Extracted PDFs from iframe:', newPdfs);
        
        // Send to extension via chrome.runtime (works cross-origin)
        chrome.runtime.sendMessage({
            type: 'IFRAME_PDFS_EXTRACTED',
            pdfs: newPdfs,
            sourceUrl: window.location.href
        }, (response) => {
            if (chrome.runtime.lastError) {
                console.error('[TwinVine] Error sending message:', chrome.runtime.lastError.message);
            } else {
                console.log('[TwinVine] Message sent successfully');
            }
        });
    }
    
    // Run extraction when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', extractAndSendPdfs);
    } else {
        extractAndSendPdfs();
    }
    
    // Also observe for dynamically added content
    const observer = new MutationObserver(() => {
        extractAndSendPdfs();
    });
    
    if (document.body) {
        observer.observe(document.body, { childList: true, subtree: true });
    } else {
        document.addEventListener('DOMContentLoaded', () => {
            observer.observe(document.body, { childList: true, subtree: true });
        });
    }
    
    // Poll periodically as backup
    setInterval(extractAndSendPdfs, 2000);
})();
