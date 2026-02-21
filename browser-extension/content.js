// TwinVine content.js v2.1 — runs inside Testbook pages
// Writes directly to chrome.storage.local (NOT sendMessage — SW may not be alive!)

(function () {
    const BRAND = ['testbook', 'testbook.com', 'login', 'signup', 'home', 'dashboard', 'lesson', 'video', 'live', 'download', 'pdf'];
    const isBrand = t => BRAND.includes(t.toLowerCase().replace(/[^a-z0-9.]/g, ''));
    const isHash = t => /^[a-f0-9]{15,40}$/i.test(t.trim()) || t.trim() === '';

    let lastTitle = '';
    let lastPdf = '';

    // ┌─────────────────────────────────────────────────────────────┐
    // │ MESSAGE LISTENER - responds to background script requests  │
    // └─────────────────────────────────────────────────────────────┘
    chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
        if (msg.type === 'FIND_AND_DOWNLOAD_PDF') {
            console.log('📨 [TwinVine] Received: Find and download PDF');
            findAndDownloadPdf();
        }
    });

    // ┌─────────────────────────────────────────────────────────────┐
    // │ AUTO FIND AND DOWNLOAD PDF                                  │
    // └─────────────────────────────────────────────────────────────┘
    function findAndDownloadPdf() {
        console.log('🔍 [TwinVine] Scanning for PDF in iframe...');
        
        function extractPdfFromIframe() {
            console.log('📍 [TwinVine] extractPdfFromIframe called');
            
            const iframe = document.querySelector('iframe');
            if (!iframe) {
                console.log('❌ No iframe element found');
                return null;
            }
            
            const iframeDoc = iframe.contentDocument || iframe.contentWindow?.document;
            if (!iframeDoc) {
                console.log('❌ Cannot access iframe document');
                return null;
            }
            
            const pdfLinks = [...iframeDoc.querySelectorAll('a.pdf-bg')];
            
            if (pdfLinks.length === 0) {
                console.log('❌ No a.pdf-bg links found');
                return null;
            }
            
            console.log(`✅ Found ${pdfLinks.length} PDF links!`);
            
            // EXACT WORKING CODE FROM CONSOLE
            const pdfs = pdfLinks.map(a => {
                const fullName = a.textContent.trim();
                const params = new URLSearchParams(a.href.split('?')[1]);
                const realUrl = decodeURIComponent(params.get('u'));
                return {
                    name: fullName,
                    url: realUrl
                };
            });
            
            return pdfs[0]; // Return first PDF
        }
        
        // Strategy: Wait for iframe content to be ready
        function waitForIframeContent() {
            const iframe = document.querySelector('iframe');
            
            if (!iframe) {
                console.log('⏳ Iframe not in DOM yet, waiting...');
                setTimeout(waitForIframeContent, 500);
                return;
            }
            
            // Iframe exists, try to access its document
            const iframeDoc = iframe.contentDocument || iframe.contentWindow?.document;
            
            if (!iframeDoc || iframeDoc.readyState !== 'complete') {
                console.log('⏳ Iframe not loaded yet, waiting for load event...');
                
                iframe.addEventListener('load', () => {
                    console.log('✅ Iframe loaded!');
                    setTimeout(() => {
                        const pdf = extractPdfFromIframe();
                        if (pdf) {
                            processPdf(pdf);
                        }
                    }, 500); // Extra delay after load
                }, { once: true });
                
                return;
            }
            
            // Iframe doc is ready, try extraction
            console.log('✅ Iframe document ready');
            const pdf = extractPdfFromIframe();
            
            if (pdf) {
                processPdf(pdf);
            } else {
                // Content might still be loading inside iframe
                console.log('⏳ PDF links not ready, waiting 1s...');
                setTimeout(() => {
                    const pdfRetry = extractPdfFromIframe();
                    if (pdfRetry) {
                        processPdf(pdfRetry);
                    } else {
                        console.log('❌ [TwinVine] Failed to find PDF after retries');
                    }
                }, 1000);
            }
        }
        
        function processPdf(pdf) {
            console.log('✅ [TwinVine] Extracted PDF!');
            console.log(`   Name: ${pdf.name}`);
            console.log(`   URL: ${pdf.url.substring(0, 80)}...`);
            
            const urlFilename = pdf.url.split('/').pop().split('?')[0] || 'document.pdf';
            
            // Send PDF data to server (no auto-download)
            sendPdfToServer(pdf.name, pdf.url, urlFilename);
        }
        
        // Start the process
        waitForIframeContent();
    }

    function storePdfData(title, pdfUrl, pdfFilename) {
        chrome.storage.local.get('capturedData', (result) => {
            const data = result.capturedData || {};
            data.pageTitle = title;
            data.pdfUrl = pdfUrl;
            data.pdfFilename = pdfFilename;
            chrome.storage.local.set({ capturedData: data });
            console.log('💾 [TwinVine] Stored PDF data in chrome.storage.local');
            
            // Verify write
            setTimeout(() => {
                chrome.storage.local.get('capturedData', (verify) => {
                    if (verify.capturedData && verify.capturedData.pdfUrl) {
                        console.log('✅ [TwinVine] Verified PDF data stored');
                    }
                });
            }, 100);
        });
    }
    
    function sendPdfToServer(pdfName, pdfUrl, filename) {
        console.log('📋 [TwinVine] Sending PDF to server (no download)...');
        
        const storageKey = `twinvine_sent_${pdfUrl}`;
        if (sessionStorage.getItem(storageKey)) {
            console.log('⏭️  [TwinVine] Already sent this PDF this session');
            return;
        }
        
        sessionStorage.setItem(storageKey, 'true');
        
        // Send to background script to call server
        chrome.runtime.sendMessage({
            type: 'SAVE_PDF_TO_SERVER',
            pdfName: pdfName,
            pdfUrl: pdfUrl,
            pdfFilename: filename,
            pageTitle: pdfName
        });
        
        console.log('📋 [TwinVine] New PDF detected, will be queued for server download');
    }

    // Save PDF data to auto_queue.json
    function saveToAutoQueue(pdfName, pdfUrl, pdfData) {
        const queueEntry = {
            type: "pdf",
            filename: pdfName.replace('.pdf', ''),
            pdf_url: pdfUrl,
            pdf_name: pdfName,
            metadata: {
                display_name: pdfData.name || pdfName,
                source_url: window.location.href,
                lesson_id: extractLessonId(window.location.href)
            },
            captured_at: new Date().toISOString(),
            status: "pending"
        };

        console.log('💾 [TwinVine] Saving PDF to auto_queue.json:', pdfName);

        // Send to background script to write to file
        chrome.runtime.sendMessage({
            type: 'SAVE_TO_AUTO_QUEUE',
            data: queueEntry
        });
    }

    // Extract lesson ID from URL
    function extractLessonId(url) {
        const match = url.match(/lesson\/([a-f0-9]{24})/);
        return match ? match[1] : null;
    }

    function checkPage() {
        let title = '';
        let pdfUrl = '';
        let pdfFilename = '';
        let foundPdfLinks = [];

        // Search ALL links and get their computed href (a.href)
        const allLinks = document.querySelectorAll('a');
        console.log(`🔍 [TwinVine] Scanning ${allLinks.length} links...`);
        
        for (const a of allLinks) {
            // Use a.href to get the COMPUTED full URL
            const href = a.href || '';
            
            // Look for pdf-viewer URLs
            if (href.includes('pdf-viewer') || href.includes('.pdf')) {
                console.log('✅ Found PDF link:', href);
                
                // Highlight it
                a.style.outline = '3px solid #00ff00';
                a.style.backgroundColor = 'rgba(0, 255, 0, 0.15)';
                a.style.boxShadow = '0 0 15px rgba(0, 255, 0, 0.8)';
                
                // Extract filename and URL from pdf-viewer parameters
                const n = href.match(/[?&]n=([^&]+)/);
                const u = href.match(/[?&]u=([^&]+)/);
                
                if (n) {
                    pdfFilename = decodeURIComponent(n[1]);
                    console.log('📄 PDF filename:', pdfFilename);
                    
                    // Use PDF filename as the title
                    title = pdfFilename.replace(/_\d+\.pdf$/i, '').replace(/\.pdf$/i, '').trim();
                    console.log('📝 Title extracted from PDF:', title);
                }
                
                if (u) {
                    pdfUrl = decodeURIComponent(u[1]);
                    console.log('📎 PDF URL:', pdfUrl);
                }
                
                foundPdfLinks.push({
                    element: a,
                    href: href,
                    pdfUrl: pdfUrl,
                    pdfFilename: pdfFilename,
                    title: title,
                    text: a.textContent?.trim().substring(0, 50)
                });
                
                // Break after first link - we only need the first one
                break;
            }
        }
        
        if (foundPdfLinks.length > 0) {
            console.log(`✨ [TwinVine] Found first PDF link`);
            console.log(`   Title: ${title}`);
            console.log(`   File: ${pdfFilename}`);
            console.log(`   URL: ${pdfUrl}`);
            
            // Send this info to background script for server queuing
            if (title && pdfUrl && pdfFilename) {
                chrome.runtime.sendMessage({
                    type: 'SAVE_PDF_TO_SERVER',
                    pdfUrl: pdfUrl,
                    pdfFilename: pdfFilename,
                    pageTitle: title
                });
            }
            
            // Also store for later use
            chrome.storage.local.get('capturedData', (result) => {
                const data = result.capturedData || {};
                data.pageTitle = title;
                data.pdfUrl = pdfUrl;
                data.pdfFilename = pdfFilename;
                chrome.storage.local.set({ capturedData: data });
                console.log('💾 Stored in local storage:', { title, pdfFilename, pdfUrl });
                
                // Verify it was written
                setTimeout(() => {
                    chrome.storage.local.get('capturedData', (verify) => {
                        if (verify.capturedData && verify.capturedData.pageTitle) {
                            console.log('✅ Verified storage write:', verify.capturedData.pageTitle);
                        } else {
                            console.error('❌ Storage write failed!');
                        }
                    });
                }, 100);
            });
            
            // Auto-download the PDF
            const storageKey = `twinvine_clicked_${pdfUrl}`;
            if (!sessionStorage.getItem(storageKey)) {
                console.log('🚀 [TwinVine] Auto-downloading PDF...');
                
                sessionStorage.setItem(storageKey, 'true');
                
                setTimeout(() => {
                    // Create and trigger download
                    const downloadLink = document.createElement('a');
                    downloadLink.href = pdfUrl;
                    downloadLink.download = pdfFilename;
                    downloadLink.style.display = 'none';
                    document.body.appendChild(downloadLink);
                    
                    downloadLink.click();
                    document.body.removeChild(downloadLink);
                    console.log('✅ [TwinVine] PDF download started!');
                }, 300);
            } else {
                console.log('⏭️ PDF already downloaded this session');
            }
        } else {
            console.log('⏳ Waiting for PDF links to render...');
        }

        // 2. Active module in sidebar
        if (!title) {
            const m = document.querySelector('.module-info.active .module-info__name');
            if (m) { const t = (m.innerText || '').trim(); if (t && !isHash(t) && !isBrand(t)) title = t; }
        }

        // 3. Heading elements
        if (!title) {
            for (const sel of ['h1', 'h2', 'h3', '.lesson__title', '[class*="title"]']) {
                const el = document.querySelector(sel);
                if (el) {
                    const t = (el.innerText || '').trim();
                    if (t.length > 2 && t.length < 80 && !isHash(t) && !isBrand(t)) { title = t; break; }
                }
            }
        }

        // 4. document.title
        if (!title) {
            const dt = document.title.replace(/\s*[-|]\s*Testbook.*$/i, '').replace(/^Testbook\s*[-|]\s*/i, '').trim();
            if (dt.length > 2 && !isBrand(dt) && !isHash(dt)) title = dt;
        }

        // Write DIRECTLY to chrome.storage.local — NOT sendMessage!
        // sendMessage fails silently when the service worker isn't running.
        if ((title && title !== lastTitle) || (pdfUrl && pdfUrl !== lastPdf)) {
            const titleChanged = title && title !== lastTitle;
            lastTitle = title || lastTitle;
            lastPdf = pdfUrl || lastPdf;

            console.log('📝 [TwinVine] Writing to storage:', lastTitle, lastPdf ? '+ PDF' : '');

            chrome.storage.local.get(['capturedData', 'downloadedPdfs'], (result) => {
                const data = result.capturedData || {};
                const downloadedPdfs = result.downloadedPdfs || [];
                
                // If title changed, clear old PDF data (new lesson)
                if (titleChanged && !pdfUrl) {
                    console.log('🔄 [TwinVine] New lesson detected, clearing old PDF data');
                    data.pdfUrl = null;
                    data.pdfFilename = null;
                }
                
                data.pageTitle = lastTitle;
                if (lastPdf) data.pdfUrl = lastPdf;
                if (pdfFilename) data.pdfFilename = pdfFilename;
                chrome.storage.local.set({ capturedData: data });
                
                // Auto-trigger PDF save to server if we have a new PDF
                if (lastPdf && !downloadedPdfs.includes(lastPdf)) {
                    console.log('🚀 [TwinVine] New PDF detected, sending to server');
                    chrome.runtime.sendMessage({
                        type: 'SAVE_PDF_TO_SERVER',
                        pdfUrl: lastPdf,
                        pdfFilename: pdfFilename || 'document.pdf',
                        pageTitle: lastTitle
                    });
                    downloadedPdfs.push(lastPdf); // Mark as processed
                    chrome.storage.local.set({ downloadedPdfs });
                } else if (lastPdf && downloadedPdfs.includes(lastPdf)) {
                    console.log('⏭️ [TwinVine] PDF already processed, skipping:', pdfFilename);
                }
            });
        }
    }

    // Run immediately
    checkPage();

    // MutationObserver for SPA navigation (Angular app)
    const observer = new MutationObserver(() => {
        console.log('🔄 [TwinVine] DOM changed, re-checking page...');
        checkPage();
    });
    observer.observe(document.body, { childList: true, subtree: true });

    // Poll every 1 second for first 10 seconds, then every 5 seconds
    let pollCount = 0;
    const pollInterval = setInterval(() => {
        pollCount++;
        const interval = pollCount < 10 ? 1 : 5;
        
        if (pollCount % (interval * 2) === 0) { // Log less frequently
            console.log(`⏱️ [TwinVine] Polling check #${pollCount}...`);
        }
        
        checkPage();
    }, 500); // Check every 500ms for responsiveness

    // Global function for manual PDF extraction with detailed logging
    window.twinvineDebugPdf = function() {
        console.log('🔍 [TwinVine DEBUG] Scanning entire page for ANY links...\n');
        
        const allLinks = document.querySelectorAll('a');
        console.log(`Found ${allLinks.length} total <a> links on page\n`);
        
        let pdfCount = 0;
        allLinks.forEach((link, idx) => {
            const href = link.getAttribute('href') || '';
            const fullHref = link.href || '';
            const text = (link.textContent || '').substring(0, 50);
            const classes = link.className || '';
            
            if (href || fullHref) {
                // Show ALL links with details
                if (pdfCount < 20) { // Limit output
                    console.log(`[${idx}] ${text || '(no text)'}`);
                    console.log(`    href="${href}"`);
                    console.log(`    full="${fullHref}"`);
                    console.log(`    class="${classes}"`);
                }
                
                // Count PDF-related links
                if (fullHref.includes('pdf') || href.includes('pdf') || text.toLowerCase().includes('pdf')) {
                    pdfCount++;
                    console.log(`    ⭐ PDF LINK FOUND!`);
                }
            }
        });
        
        console.log(`\n📊 Total PDF-related links: ${pdfCount}`);
        
        // Also check for button elements that might trigger downloads
        const buttons = document.querySelectorAll('button');
        console.log(`\nFound ${buttons.length} total <button> elements`);
        buttons.forEach((btn, idx) => {
            const text = (btn.textContent || '').toLowerCase();
            if (text.includes('pdf') || text.includes('download')) {
                console.log(`[${idx}] Button: "${btn.textContent}"`);
            }
        });
        
        return { totalLinks: allLinks.length, pdfLinks: pdfCount };
    };
    
    console.log('💡 [TwinVine] Debug tip: Run window.twinvineDebugPdf() in console to see all links');

    // Also listen for API interceptor data
    window.addEventListener('message', (event) => {
        if (event.source !== window || !event.data) return;
        
        // Handle API intercepted data
        if (event.data.type === 'TWINVINE_API_DATA') {
            const { title, pdfUrl, pdfFilename } = event.data;
            if (title && title !== lastTitle) {
                lastTitle = title;
                console.log('🚀 [TwinVine] API intercepted title:', title);
                
                chrome.storage.local.get('capturedData', (result) => {
                    const data = result.capturedData || {};
                    
                    if (title.toLowerCase().endsWith('.pdf')) {
                        data.pdfFilename = title;
                        data.pageTitle = title;
                        console.log('📋 [TwinVine] Set API filename as pdfFilename:', title);
                        
                        // Send directly to background.js for immediate use
                        chrome.runtime.sendMessage({ type: 'API_PDF_NAME', name: title });
                    } else {
                        data.pageTitle = title;
                    }
                    
                    if (pdfUrl) data.pdfUrl = pdfUrl;
                    if (pdfFilename) data.pdfFilename = pdfFilename;
                    chrome.storage.local.set({ capturedData: data });
                });
            }
        }
        
        // Handle iframe PDFs extracted by api-interceptor
        if (event.data.type === 'TWINVINE_IFRAME_PDFS') {
            const pdfs = event.data.pdfs || [];
            console.log('📄 [TwinVine] Iframe PDFs received:', pdfs.length);
            
            pdfs.forEach(pdf => {
                console.log(`   📎 ${pdf.name}: ${pdf.url.substring(0, 60)}...`);
            });
            
            // Store all PDFs and save to auto_queue.json
            if (pdfs.length > 0) {
                chrome.storage.local.get('capturedData', (result) => {
                    const data = result.capturedData || {};
                    data.iframePdfs = pdfs;
                    
                    // Only set pdfUrl if not already set
                    if (!data.pdfUrl && pdfs[0]) {
                        data.pdfUrl = pdfs[0].url;
                        
                        // Priority: existing pdfFilename > API title > iframe filename
                        if (!data.pdfFilename) {
                            if (lastTitle && lastTitle.toLowerCase().endsWith('.pdf')) {
                                data.pdfFilename = lastTitle;
                                console.log('🎯 [TwinVine] Using API-intercepted filename:', lastTitle);
                            } else {
                                data.pdfFilename = pdfs[0].name + '.pdf';
                                console.log('📝 [TwinVine] Using iframe fallback filename:', data.pdfFilename);
                            }
                        } else {
                            console.log('✅ [TwinVine] Keeping existing filename:', data.pdfFilename);
                        }
                    }
                    
                    // Save to auto_queue.json with API intercepted name
                    if (data.apiPdfName && data.pdfUrl) {
                        saveToAutoQueue(data.apiPdfName, data.pdfUrl, pdfs[0]);
                    }
                    
                    chrome.storage.local.set({ capturedData: data });
                });
            }
        }
    });
})();
