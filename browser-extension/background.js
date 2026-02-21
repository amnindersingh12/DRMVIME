// TwinVine background.js v2.0
// Pure network-based capture: no DOM scraping at all.
// Captures MPD, License, API IDs, and PDF URLs from network requests,
// then fetches lesson title from Testbook's API directly.

const SERVER_URL = 'http://localhost:8765';

let capturedData = {
  mpd: null,
  license: null,
  timestamp: null,
  pdfUrl: null,
  pdfFilename: null,
  pageTitle: null,
  moduleId: null,
  lessonId: null,
  parentId: null
};

// Store API-intercepted PDF name (set by content.js, used by iframe handler)
let apiPdfName = null;

// Restore persisted state (SW restarts wipe in-memory variables)
chrome.storage.local.get('capturedData', (result) => {
  if (result.capturedData) {
    Object.assign(capturedData, result.capturedData);
    console.log('🔄 Restored state:', capturedData.pageTitle || '(no title)', capturedData.moduleId || '(no moduleId)');
  }
});

let courseQueue = [];

// ─── URL Capture ────────────────────────────────────────────────────────────

chrome.webRequest.onBeforeRequest.addListener(
  function (details) {
    const url = details.url;

    // 1. Capture MPD URL and extract PDF URL from lesson ID
    if (url.includes('.mpd') && url.includes('mediacdn.testbook.com')) {
      capturedData.mpd = url;
      capturedData.timestamp = Date.now();
      
      // Clear old PDF data to prevent reuse
      capturedData.pdfUrl = null;
      capturedData.pdfFilename = null;
      capturedData.pageTitle = null;
      
      console.log('📥 Captured MPD:', url);
      console.log('🧹 Cleared old PDF data');
      
      // Immediately ask content script to find and download PDF
      console.log('🔍 Requesting content script to find PDF...');
      chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (tabs[0]) {
          chrome.tabs.sendMessage(tabs[0].id, { type: 'FIND_AND_DOWNLOAD_PDF' }).catch(e => {
            console.log('ℹ️  Content script message failed (may not be ready yet)');
          });
        }
      });
      
      // Extract lesson ID from MPD URL: .../wv/{lessonId}/...
      const lessonIdMatch = url.match(/\/wv\/([a-f0-9]{24})\//);
      if (lessonIdMatch) {
        const lessonId = lessonIdMatch[1];
        console.log('📚 Extracted lesson ID from MPD:', lessonId);
        capturedData.lessonId = lessonId;
        
        // Wait longer for Angular to render and content.js to find PDF on page
        setTimeout(() => {
          chrome.storage.local.get('capturedData', (result) => {
            const data = result.capturedData || {};
            console.log('🔍 Checking PDF status after 5s delay...');
            console.log('   Current PDF URL:', data.pdfUrl || 'none');
            console.log('   Current title:', data.pageTitle || 'none');
            console.log('   Expected lesson ID in PDF:', lessonId);
            
            // Only fetch from API if page didn't provide PDF or if lesson IDs don't match
            if (!data.pdfUrl) {
              console.log('⚠️ No PDF found on page, fetching from API...');
              fetchPdfFromLesson(lessonId);
            } else if (!data.pdfUrl.includes(lessonId)) {
              console.log('⚠️ PDF has wrong lesson ID, fetching correct one from API...');
              fetchPdfFromLesson(lessonId);
            } else {
              console.log('✅ PDF already captured from page with correct lesson ID');
            }
          });
        }, 5000); // Increased to 5 seconds for content script to find PDF
      }
      
      chrome.storage.local.set({ capturedData });
      chrome.action.setBadgeText({ text: 'MPD' });
      chrome.action.setBadgeBackgroundColor({ color: '#4CAF50' });
    }

    // 2. Capture Testbook API calls with moduleId/lessonId
    if (url.includes('api.testbook.com/api/') && (url.includes('moduleId=') || url.includes('lessonId='))) {
      try {
        const parsed = new URL(url);
        const moduleId = parsed.searchParams.get('moduleId');
        const lessonId = parsed.searchParams.get('lessonId');
        const parentId = parsed.searchParams.get('parentId');
        if (moduleId) capturedData.moduleId = moduleId;
        if (lessonId) capturedData.lessonId = lessonId;
        if (parentId) capturedData.parentId = parentId;
        console.log(`📚 Captured API IDs: module=${moduleId}, lesson=${lessonId}, parent=${parentId}`);
        chrome.storage.local.set({ capturedData });
      } catch (_) { }
    }

    // 3. Capture PDF info from pdf-viewer URL
    if (url.includes('pdf-viewer') && (url.includes('testbook.com') || url.includes('?n='))) {
      try {
        const parsed = new URL(url);
        const n = parsed.searchParams.get('n');
        const u = parsed.searchParams.get('u');
        if (n) {
          capturedData.pdfFilename = n;
          capturedData.pageTitle = n.replace(/_\d+\.pdf$/i, '').replace(/\.pdf$/i, '').trim();
          console.log('📄 Captured PDF name:', capturedData.pageTitle);
        }
        if (u && u.startsWith('http')) {
          capturedData.pdfUrl = u;
          console.log('📄 Captured PDF URL:', u.substring(0, 80));
        }
        chrome.storage.local.set({ capturedData });
      } catch (_) { }
    }

    // 4. Capture direct PDF downloads
    if (url.includes('mediacdn.testbook.com') && url.includes('/pdfs/')) {
      capturedData.pdfUrl = url;
      console.log('📄 Captured direct PDF URL:', url.substring(0, 80));
      chrome.storage.local.set({ capturedData });
    }

    // 5. Capture License URL → triggers key extraction
    if (url.includes('getlicense') && url.includes('token=')) {
      capturedData.license = url;
      capturedData.timestamp = Date.now();
      console.log('🔐 Captured License:', url.substring(0, 80) + '...');
      chrome.storage.local.set({ capturedData });
      chrome.action.setBadgeText({ text: 'BOTH' });
      chrome.action.setBadgeBackgroundColor({ color: '#2196F3' });

      if (capturedData.mpd && capturedData.license) {
        const isDuplicate = courseQueue.some(l => l.mpd_url === capturedData.mpd);
        if (isDuplicate) {
          console.log('⚠️ Duplicate — skipping');
          _notify('⚠️ Already Captured', 'This video is already in your queue', 1);
          _resetCapturedData();
        } else {
          extractAndCacheKeys(capturedData.mpd, capturedData.license);
        }
      }
    }
  },
  { urls: ['<all_urls>'] }
);

// ─── Content Script Message Listener (fallback) ─────────────────────────────

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  // Store API-intercepted PDF name
  if (msg.type === 'API_PDF_NAME') {
    apiPdfName = msg.name;
    console.log('📋 [BACKGROUND] Stored API PDF name:', apiPdfName);
    return;
  }

  // Reload extension (for development)
  if (msg.type === 'RELOAD_EXTENSION') {
    console.log('🔄 [Extension] Reloading...');
    sendResponse({ success: true, message: 'Reloading extension' });
    setTimeout(() => {
      chrome.runtime.reload();
    }, 100);
    return;
  }
  
  // PDFs extracted from iframe (cross-origin safe)
  if (msg.type === 'IFRAME_PDFS_EXTRACTED') {
    const pdfs = msg.pdfs || [];
    if (pdfs.length === 0) return;

    const pdf = pdfs[0];
    
    // Use API-intercepted name (priority) or fallback to extracted filename
    const pdfName = apiPdfName || pdf.filename || (pdf.name + '.pdf');
    const pdfUrl = pdf.url;

    console.log('📄 [IFRAME] PDF captured');
    console.log('   📋 API Name:', apiPdfName || '(none)');
    console.log('   📁 Using:', pdfName);
    console.log('   🔗 URL:', pdfUrl.substring(0, 80) + '...');

    // Update storage
    capturedData.pdfUrl = pdfUrl;
    capturedData.pdfFilename = pdfName;
    capturedData.iframePdfs = pdfs;
    chrome.storage.local.set({ capturedData });

    // Save to auto_queue.json via the local server
    fetch(`${SERVER_URL}/save-pdf`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pdf_url: pdfUrl, pdf_name: pdfName })
    })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        console.log('✅ [IFRAME] Saved to queue:', data.filename);
        chrome.action.setBadgeText({ text: String(data.queue_length) });
        chrome.action.setBadgeBackgroundColor({ color: '#4CAF50' });
        _notify('📄 PDF Saved!', `${data.filename}`, 1);
        // Clear the API name for next lesson
        apiPdfName = null;
      } else if (data.error === 'duplicate') {
        console.log('⚠️ [IFRAME] PDF already in queue:', data.existing);
      } else {
        console.error('❌ [IFRAME] Server error:', data.error);
      }
    })
    .catch(e => {
      console.error('❌ [IFRAME] Server not running:', e.message);
      _notify('❌ Server Not Running', 'Start with: uv run python twinvine.py server', 2);
    });
    
    return;
  }
  
  // Save PDF to server when detected
  if (msg.type === 'SAVE_PDF_TO_SERVER') {
    console.log('📄 [MESSAGE] Saving PDF to server:', msg.pdfFilename);
    console.log('   Title:', msg.pageTitle);
    console.log('   URL:', msg.pdfUrl?.substring(0, 60) + '...');
    capturedData.pageTitle = msg.pageTitle;
    capturedData.pdfUrl = msg.pdfUrl;
    capturedData.pdfFilename = msg.pdfFilename;
    chrome.storage.local.set({ capturedData });
    savePdfToServer(msg.pdfUrl, msg.pdfFilename, msg.pageTitle);
    return;
  }
  
  // From content.js / api-interceptor.js
  if (msg.type === 'PAGE_INFO' && msg.title) {
    console.log('📩 [MESSAGE] Page info from content script:', msg.title);
    capturedData.pageTitle = msg.title;
    capturedData.pdfUrl = msg.pdfUrl || capturedData.pdfUrl;
    capturedData.pdfFilename = msg.pdfFilename || capturedData.pdfFilename;
    console.log('   PDF Filename:', msg.pdfFilename);
    chrome.storage.local.set({ capturedData });
    return;
  }

  // From popup.js
  switch (msg.action) {
    case 'getCapturedData':
      sendResponse(capturedData);
      break;
    case 'getQueue':
      sendResponse(courseQueue);
      break;
    case 'clearData':
      _resetCapturedData();
      chrome.action.setBadgeText({ text: courseQueue.length > 0 ? String(courseQueue.length) : '' });
      sendResponse({ success: true });
      break;
    case 'clearQueue':
      courseQueue = [];
      chrome.storage.local.set({ courseQueue });
      chrome.action.setBadgeText({ text: '' });
      sendResponse({ success: true });
      break;
    case 'clearPdfs':
      chrome.storage.local.set({ downloadedPdfs: [] });
      console.log('🗑️ Cleared downloaded PDFs list');
      sendResponse({ success: true });
      break;
    case 'exportQueue': {
      const blob = new Blob([JSON.stringify(courseQueue, null, 2)], { type: 'application/json' });
      const blobUrl = URL.createObjectURL(blob);
      chrome.downloads.download({ url: blobUrl, filename: 'twinvine_queue.json', saveAs: true });
      sendResponse({ success: true });
      break;
    }
  }
  return true;
});

// ─── Fetch PDF from Lesson ──────────────────────────────────────────────────

async function fetchPdfFromLesson(lessonId) {
  console.log('🔍 Fetching PDF for lesson:', lessonId);
  
  const endpoints = [
    `https://api.testbook.com/api/v2/lessons/${lessonId}`,
    `https://api.testbook.com/api/v1/lessons/${lessonId}`,
    `https://api.testbook.com/api/v2/entity/lesson/${lessonId}`,
  ];

  for (const endpoint of endpoints) {
    try {
      console.log(`🌐 Trying: ${endpoint}`);
      const resp = await fetch(endpoint, {
        method: 'GET',
        credentials: 'include',
        headers: { 'Accept': 'application/json' }
      });
      
      if (!resp.ok) {
        console.log(`   ❌ ${resp.status}`);
        continue;
      }
      
      const json = await resp.json();
      console.log('📨 API Response:', JSON.stringify(json).substring(0, 1000));
      
      // Search for PDF info in the response
      const pdfInfo = findPdfInResponse(json, lessonId);
      
      if (pdfInfo.url) {
        // Verify the PDF URL contains the correct lesson ID
        if (!pdfInfo.url.includes(lessonId)) {
          console.log(`⚠️ PDF lesson ID mismatch! Expected ${lessonId}, got different ID in URL`);
          console.log(`   Reconstructing URL with correct lesson ID...`);
          
          // Extract the PDF filename and reconstruct the URL
          const pdfFilenameMatch = pdfInfo.url.match(/\/pdfs\/(.+)$/);
          if (pdfFilenameMatch) {
            const pdfFile = pdfFilenameMatch[1];
            pdfInfo.url = `https://mediacdn.testbook.com/assets/${lessonId}/pdfs/${pdfFile}`;
            console.log(`   ✅ Corrected URL: ${pdfInfo.url}`);
          }
        }
        
        console.log('✅ Found PDF:', pdfInfo.filename);
        
        // Update storage
        chrome.storage.local.get('capturedData', (result) => {
          const data = result.capturedData || {};
          data.pdfUrl = pdfInfo.url;
          data.pdfFilename = pdfInfo.filename;
          chrome.storage.local.set({ capturedData: data });
          
          // Auto-download the PDF
          chrome.storage.local.get('downloadedPdfs', (dlResult) => {
            const downloadedPdfs = dlResult.downloadedPdfs || [];
            if (!downloadedPdfs.includes(pdfInfo.url)) {
              console.log('🚀 Auto-downloading PDF from lesson API');
              savePdfToServer(pdfInfo.url, pdfInfo.filename, data.pageTitle || '');
            }
          });
        });
        
        return pdfInfo;
      }
    } catch (e) {
      console.log(`   ❌ ${e.message}`);
    }
  }
  
  console.log('⚠️ No PDF found in API, will rely on page scraping');
  return { url: null, filename: null };
}

function findPdfInResponse(obj, lessonId, depth = 0) {
  if (!obj || typeof obj !== 'object' || depth > 5) {
    return { url: null, filename: null };
  }

  // Look for PDF-related fields
  for (const key in obj) {
    const val = obj[key];
    
    // Direct PDF URL fields
    if ((key === 'pdfUrl' || key === 'pdf_url' || key === 'pdfLink' || key === 'attachmentUrl') && 
        typeof val === 'string' && val.includes('.pdf')) {
      let filename = val.split('/').pop().split('?')[0];
      let url = val;
      
      // If URL doesn't have full domain, construct it
      if (url.startsWith('/')) {
        url = `https://mediacdn.testbook.com${url}`;
      }
      
      return { url, filename };
    }
    
    // PDF filename field
    if ((key === 'pdfName' || key === 'pdfFilename' || key === 'attachmentName') && typeof val === 'string') {
      const filename = val;
      // Keep searching for URL in the same object level
      const urlSearch = findPdfInResponse(obj, lessonId, depth + 1);
      if (urlSearch.url) {
        return { url: urlSearch.url, filename: filename || urlSearch.filename };
      }
    }
    
    // Attachment/resource arrays
    if ((key === 'attachments' || key === 'resources' || key === 'pdfs') && Array.isArray(val)) {
      for (const item of val) {
        if (item && typeof item === 'object') {
          const result = findPdfInResponse(item, lessonId, depth + 1);
          if (result.url) return result;
        }
      }
    }
    
    // Recurse into objects
    if (typeof val === 'object' && val !== null) {
      const result = findPdfInResponse(val, lessonId, depth + 1);
      if (result.url) return result;
    }
  }

  return { url: null, filename: null };
}

// ─── Fetch lesson title from Testbook API ────────────────────────────────────

async function fetchLessonTitle(moduleId, lessonId, parentId) {
  // Try LESSON-specific endpoints first (these return "Average - 01")
  // Module endpoint returns the category "Subjects" — only use as last resort
  const endpoints = [
    lessonId ? `https://api.testbook.com/api/v2/lessons/${lessonId}` : null,
    lessonId ? `https://api.testbook.com/api/v1/lessons/${lessonId}` : null,
    lessonId ? `https://api.testbook.com/api/v2/entity/lesson/${lessonId}` : null,
    lessonId ? `https://api.testbook.com/api/v1/entity/lesson/${lessonId}` : null,
    (lessonId && parentId) ? `https://api.testbook.com/api/v2/classes/${parentId}/lessons/${lessonId}` : null,
    moduleId ? `https://api.testbook.com/api/v2/modules/${moduleId}` : null,
  ].filter(Boolean);

  for (const endpoint of endpoints) {
    try {
      console.log(`🌐 Trying: ${endpoint}`);
      const resp = await fetch(endpoint, {
        method: 'GET',
        credentials: 'include',
        headers: { 'Accept': 'application/json' }
      });
      if (!resp.ok) { console.log(`   ❌ ${resp.status}`); continue; }
      const json = await resp.json();
      
      // Log full response for debugging
      const dump = JSON.stringify(json).substring(0, 3000);
      console.log('📨 Response:', dump);

      // If module endpoint: search for matching lesson inside
      if (endpoint.includes('/modules/') && lessonId) {
        const lessonTitle = findLessonInModule(json, lessonId);
        if (lessonTitle) {
          console.log('✅ Found lesson inside module:', lessonTitle);
          return lessonTitle;
        }
        // Don't return the module-level "Subjects" — keep trying other endpoints
        continue;
      }

      // Generic deep title search
      const title = deepFindTitle(json);
      if (title) {
        console.log('✅ Found title:', title);
        return title;
      }
    } catch (e) {
      console.log(`   ❌ ${e.message}`);
    }
  }
  return '';
}

// Search inside a module response for a specific lesson by its ID
function findLessonInModule(obj, targetLessonId) {
  if (!obj || typeof obj !== 'object') return '';

  // Check if this object IS the lesson we're looking for
  if ((obj._id === targetLessonId || obj.id === targetLessonId || obj.lessonId === targetLessonId)) {
    for (const key of ['title', 'name', 'topicName', 'lessonName', 'heading']) {
      if (obj[key] && typeof obj[key] === 'string') {
        const t = obj[key].trim();
        if (t.length > 2 && !/^[a-f0-9]{20,40}$/i.test(t)) return t;
      }
    }
  }

  // Recurse into arrays and objects
  for (const key in obj) {
    if (typeof obj[key] === 'object') {
      const found = findLessonInModule(obj[key], targetLessonId);
      if (found) return found;
    }
  }
  return '';
}

function deepFindTitle(obj, depth = 0) {
  if (!obj || typeof obj !== 'object' || depth > 4) return '';

  // Prefer lesson-specific fields first
  for (const key of ['topicName', 'lessonName', 'heading', 'title', 'name']) {
    if (obj[key] && typeof obj[key] === 'string') {
      const t = obj[key].trim();
      if (t.length > 2 && t.length < 100 && !/^[a-f0-9]{20,40}$/i.test(t) && !t.toLowerCase().includes('testbook')) {
        return t;
      }
    }
  }

  // Dive into wrapper keys
  for (const key of ['data', 'result', 'response', 'lesson', 'module', 'video', 'details']) {
    if (obj[key] && typeof obj[key] === 'object') {
      const found = deepFindTitle(obj[key], depth + 1);
      if (found) return found;
    }
  }

  // Search arrays
  if (Array.isArray(obj)) {
    for (const item of obj) {
      const found = deepFindTitle(item, depth + 1);
      if (found) return found;
    }
  }

  return '';
}

// ─── Save PDF to Server (No Download) ───────────────────────────────────────

async function savePdfToServer(pdfUrl, pdfFilename, pageTitle) {
  try {
    console.log('📤 Saving PDF to server (no download):', pdfFilename);
    
    // Use API-intercepted name if available (better filename)
    const finalFilename = apiPdfName || pdfFilename;
    console.log('📝 Using filename:', finalFilename);
    
    const response = await fetch(`${SERVER_URL}/save-pdf`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        pdf_url: pdfUrl,
        pdf_name: finalFilename,
        page_title: pageTitle
      })
    });

    if (response.ok) {
      const result = await response.json();
      console.log('✅ PDF saved to server queue:', result.filename);
      console.log('📋 Queue length:', result.queue_length);
      
      _notify(
        '📄 PDF Queued!',
        `Saved: ${result.filename}`,
        1
      );
      
      // Clear API name after use
      apiPdfName = null;
    } else {
      const error = await response.json();
      console.error('❌ Server error saving PDF:', error);
      _notify(
        '❌ PDF Save Failed', 
        error.message || 'Server error',
        2
      );
    }
  } catch (err) {
    console.error('❌ Network error saving PDF:', err);
    _notify(
      '❌ PDF Save Failed',
      'Network error - is server running?',
      2
    );
  }
}

// ─── Key Extraction & Queue ──────────────────────────────────────────────────

async function extractAndCacheKeys(mpdUrl, licenseUrl) {
  console.log('🔑 Starting auto-extraction...');

  // Read from persistent storage (survives SW restarts)
  const stored = await chrome.storage.local.get('capturedData');
  const saved = stored.capturedData || {};
  let pageTitle   = saved.pageTitle   || '';
  let pdfUrl      = saved.pdfUrl      || '';
  let pdfFilename = saved.pdfFilename || '';
  const moduleId  = saved.moduleId    || '';
  const lessonId  = saved.lessonId    || '';
  const parentId  = saved.parentId    || '';

  console.log(`📦 From storage on START:`);
  console.log(`   Title: "${pageTitle}"`);
  console.log(`   PDF URL: ${pdfUrl ? '✅' : '❌'}`);
  console.log(`   PDF Filename: "${pdfFilename}"`);
  console.log(`   Module: ${moduleId}, Lesson: ${lessonId}`);

  // STEP 1: Wait up to 5s for content script to deliver title from the DOM
  // Content.js can see "Average - 01" directly on the page
  if (!pageTitle) {
    console.log('⏳ Waiting for content script to find title (5s)...');
    for (let i = 0; i < 10; i++) {
      await new Promise(r => setTimeout(r, 500));
      const s2 = await chrome.storage.local.get('capturedData');
      if (s2.capturedData && s2.capturedData.pageTitle) {
        pageTitle   = s2.capturedData.pageTitle;
        pdfUrl      = s2.capturedData.pdfUrl      || pdfUrl;
        pdfFilename = s2.capturedData.pdfFilename || pdfFilename;
        console.log('✅ Got title from content script:', pageTitle);
        break;
      }
    }
  }

  // STEP 2: If still nothing, try Testbook API (might return module-level "Subjects")
  if (!pageTitle && (moduleId || lessonId)) {
    console.log('🌐 Content script had nothing, trying Testbook API...');
    pageTitle = await fetchLessonTitle(moduleId, lessonId, parentId);
  }

  // If still no title but we have a PDF filename, derive title from it
  if (!pageTitle && pdfFilename) {
    const derived = pdfFilename.replace(/_\d+\.pdf$/i, '').replace(/\.pdf$/i, '').trim();
    if (derived.length > 2 && !/^[a-f0-9]{20,40}$/i.test(derived)) {
      pageTitle = derived;
      console.log('🛠️ Derived title from PDF filename:', pageTitle);
    }
  }

  console.log(`📋 Final data being sent to server:`);
  console.log(`   Title: "${pageTitle}"`);
  console.log(`   PDF URL: ${pdfUrl ? '✅ ' + pdfUrl.substring(0, 60) + '...' : '❌ None'}`);
  console.log(`   PDF Filename: "${pdfFilename}"`);


  // Send to local Python server
  try {
    const payload = {
      mpd_url: mpdUrl,
      license_url: licenseUrl,
      page_title: pageTitle,
      pdf_url: pdfUrl,
      pdf_filename: pdfFilename
    };
    
    console.log('📤 Sending payload to server:', JSON.stringify(payload, null, 2));
    
    const response = await fetch(`${SERVER_URL}/extract-keys`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await response.json();

    if (data.success) {
      const lesson = {
        mpd_url: mpdUrl,
        keys: data.keys,
        metadata: data.metadata,
        filename: data.filename,
        lesson_number: data.lesson_number,
        captured_at: new Date().toISOString(),
        status: 'pending'
      };

      courseQueue.push(lesson);
      chrome.storage.local.set({ courseQueue });
      chrome.action.setBadgeText({ text: String(courseQueue.length) });
      chrome.action.setBadgeBackgroundColor({ color: '#4CAF50' });

      _notify(
        '✅ Lesson Captured!',
        `#${data.lesson_number}: ${data.filename}\nQueue: ${courseQueue.length} lessons`,
        1
      );

      _resetCapturedData();
    } else {
      _handleError(data);
    }

  } catch (error) {
    console.error('❌ Server connection failed:', error);
    _notify('❌ Server Not Running', 'Start it with: python twinvine.py server', 2);

    courseQueue.push({
      mpd_url: mpdUrl,
      license_url: licenseUrl,
      captured_at: new Date().toISOString(),
      status: 'needs_keys'
    });
    chrome.storage.local.set({ courseQueue });
    chrome.action.setBadgeText({ text: String(courseQueue.length) });
    chrome.action.setBadgeBackgroundColor({ color: '#FF9800' });
  }
}

// ─── Helpers ────────────────────────────────────────────────────────────────

function _resetCapturedData() {
  capturedData = { mpd: null, license: null, timestamp: null, pdfUrl: null, pdfFilename: null, pageTitle: null, moduleId: null, lessonId: null, parentId: null };
  chrome.storage.local.set({ capturedData });
}

function _handleError(data) {
  console.error('❌ Extraction error:', data.error);
  switch (data.error) {
    case 'token_expired':
      _notify('⚠️ Token Expired', 'Refresh the page and play the video again.', 2);
      chrome.action.setBadgeText({ text: '⚠' });
      chrome.action.setBadgeBackgroundColor({ color: '#FF5722' });
      break;
    case 'duplicate':
      _notify('⚠️ Already Captured', `In queue as: ${data.existing_lesson}`, 1);
      chrome.action.setBadgeText({ text: String(courseQueue.length) });
      chrome.action.setBadgeBackgroundColor({ color: '#FF9800' });
      _resetCapturedData();
      break;
    default:
      _notify('❌ Extraction Failed', data.message || 'Unknown error', 2);
      chrome.action.setBadgeText({ text: 'ERR' });
      chrome.action.setBadgeBackgroundColor({ color: '#f44336' });
  }
}

function _notify(title, message, priority = 1) {
  chrome.notifications.create({
    type: 'basic',
    iconUrl: 'icon128.png',
    title,
    message,
    priority
  });
}

// ─── Startup ────────────────────────────────────────────────────────────────

chrome.storage.local.get(['courseQueue'], (result) => {
  if (result.courseQueue && result.courseQueue.length > 0) {
    courseQueue = result.courseQueue;
    chrome.action.setBadgeText({ text: String(courseQueue.length) });
    chrome.action.setBadgeBackgroundColor({ color: '#FF9800' });
  }
});

chrome.action.setBadgeText({ text: '' });
console.log('🎬 TwinVine v2.0 — network-based title extraction active');
