// Background script - captures network requests AND extracts keys automatically
let capturedData = {
  mpd: null,
  license: null,
  timestamp: null
};

let courseQueue = []; // Queue of all captured lessons

// Listen for network requests
chrome.webRequest.onBeforeRequest.addListener(
  function (details) {
    const url = details.url;

    // Capture MPD URL
    if (url.includes('.mpd') && url.includes('mediacdn.testbook.com')) {
      capturedData.mpd = url;
      capturedData.timestamp = Date.now();
      console.log('📥 Captured MPD:', url);

      // Save to storage
      chrome.storage.local.set({ capturedData });

      // Update badge
      chrome.action.setBadgeText({ text: 'MPD' });
      chrome.action.setBadgeBackgroundColor({ color: '#4CAF50' });
    }

    // Capture License URL
    if (url.includes('getlicense') && url.includes('token=')) {
      capturedData.license = url;
      capturedData.timestamp = Date.now();
      console.log('🔐 Captured License:', url.substring(0, 100) + '...');

      // Save to storage
      chrome.storage.local.set({ capturedData });

      // Update badge
      chrome.action.setBadgeText({ text: 'BOTH' });
      chrome.action.setBadgeBackgroundColor({ color: '#2196F3' });

      // Auto-extract keys if we have both URLs
      if (capturedData.mpd && capturedData.license) {
        // Check for duplicates in local queue first
        const isDuplicate = courseQueue.some(lesson => lesson.mpd_url === capturedData.mpd);

        if (isDuplicate) {
          console.log('⚠️ Duplicate detected locally - skipping');
          chrome.notifications.create({
            type: 'basic',
            iconUrl: 'icon128.png',
            title: '⚠️ Already Captured',
            message: 'This video is already in your queue',
            priority: 1
          });

          // Clear current capture
          capturedData = { mpd: null, license: null, timestamp: null };
          chrome.storage.local.set({ capturedData });
        } else {
          // Not a duplicate, proceed with extraction (polling will wait for title)
          extractAndCacheKeys(capturedData.mpd, capturedData.license);
        }
      }
    }
  },
  { urls: ["<all_urls>"] }
);

// Auto-extract keys and add to queue
async function extractAndCacheKeys(mpdUrl, licenseUrl) {
  console.log('🔑 Starting auto-extraction...');

  // Prompt user for lesson name AFTER capturing URLs
  let pageTitle = '';

  try {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tabs[0]) {
      // Show notification that we're ready to extract
      chrome.notifications.create({
        type: 'basic',
        iconUrl: 'icon128.png',
        title: '📥 URLs Captured!',
        message: 'Enter lesson name in the prompt...',
        priority: 1
      });

      // Inject a prompt into the page to ask for lesson name
      const result = await chrome.scripting.executeScript({
        target: { tabId: tabs[0].id },
        func: () => {
          return prompt('📝 Enter lesson name for this video:', '');
        }
      });

      if (result && result[0] && result[0].result) {
        pageTitle = result[0].result.trim();
        console.log('✅ User entered lesson name:', pageTitle);
      } else {
        console.log('⚠️  User cancelled or left empty - will use generic name');
      }
    }
  } catch (e) {
    console.log('Could not prompt user:', e);
  }

  try {
    // Send to native app to extract keys
    const response = await fetch('http://localhost:8765/extract-keys', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        mpd_url: mpdUrl,
        license_url: licenseUrl,
        page_title: pageTitle  // Send the extracted title from browser tab
      })
    });

    const data = await response.json();

    if (data.success) {
      // Success - add to queue
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

      // Save queue
      chrome.storage.local.set({ courseQueue });

      console.log(`✅ Keys extracted! Queue now has ${courseQueue.length} lessons`);

      // Update badge with count
      chrome.action.setBadgeText({ text: String(courseQueue.length) });
      chrome.action.setBadgeBackgroundColor({ color: '#4CAF50' });

      // Show success notification
      chrome.notifications.create({
        type: 'basic',
        iconUrl: 'icon128.png',
        title: '✅ Lesson Captured!',
        message: `Lesson ${data.lesson_number}: ${data.filename}\nQueue: ${courseQueue.length} lessons`,
        priority: 1
      });

      // Clear current capture
      capturedData = { mpd: null, license: null, timestamp: null };
      chrome.storage.local.set({ capturedData });

    } else {
      // Handle errors
      console.error('❌ Key extraction failed:', data.error);

      if (data.error === 'token_expired') {
        // Token expired - notify user
        chrome.notifications.create({
          type: 'basic',
          iconUrl: 'icon128.png',
          title: '⚠️ Token Expired',
          message: 'Please refresh the page and play the video again.',
          priority: 2
        });

        chrome.action.setBadgeText({ text: '⚠️' });
        chrome.action.setBadgeBackgroundColor({ color: '#FF5722' });

      } else if (data.error === 'duplicate') {
        // Duplicate - notify user
        console.log('⚠️ Duplicate video detected');

        chrome.notifications.create({
          type: 'basic',
          iconUrl: 'icon128.png',
          title: '⚠️ Already Captured',
          message: `This video is already in queue as: ${data.existing_lesson}`,
          priority: 1
        });

        // Keep current badge count
        chrome.action.setBadgeText({ text: String(courseQueue.length) });
        chrome.action.setBadgeBackgroundColor({ color: '#FF9800' });

        // Clear current capture
        capturedData = { mpd: null, license: null, timestamp: null };
        chrome.storage.local.set({ capturedData });

      } else {
        // Other error
        chrome.notifications.create({
          type: 'basic',
          iconUrl: 'icon128.png',
          title: '❌ Extraction Failed',
          message: data.message || 'Unknown error occurred',
          priority: 2
        });

        chrome.action.setBadgeText({ text: '❌' });
        chrome.action.setBadgeBackgroundColor({ color: '#f44336' });
      }
    }

  } catch (error) {
    console.error('❌ Error connecting to server:', error);

    // Server not running or connection error
    chrome.notifications.create({
      type: 'basic',
      iconUrl: 'icon128.png',
      title: '❌ Server Not Running',
      message: 'Please start the server: python twinvine_server.py',
      priority: 2
    });

    // Fallback: just save URLs to queue
    const lesson = {
      mpd_url: mpdUrl,
      license_url: licenseUrl,
      captured_at: new Date().toISOString(),
      status: 'needs_keys'
    };

    courseQueue.push(lesson);
    chrome.storage.local.set({ courseQueue });

    chrome.action.setBadgeText({ text: String(courseQueue.length) });
    chrome.action.setBadgeBackgroundColor({ color: '#FF9800' });
  }
}

// Listen for messages from popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'getCapturedData') {
    sendResponse(capturedData);
  } else if (request.action === 'getQueue') {
    sendResponse(courseQueue);
  } else if (request.action === 'clearData') {
    capturedData = { mpd: null, license: null, timestamp: null };
    chrome.storage.local.set({ capturedData });
    chrome.action.setBadgeText({ text: courseQueue.length > 0 ? String(courseQueue.length) : '' });
    sendResponse({ success: true });
  } else if (request.action === 'clearQueue') {
    courseQueue = [];
    chrome.storage.local.set({ courseQueue });
    chrome.action.setBadgeText({ text: '' });
    sendResponse({ success: true });
  } else if (request.action === 'exportQueue') {
    // Export queue as JSON for download script
    const blob = new Blob([JSON.stringify(courseQueue, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    chrome.downloads.download({
      url: url,
      filename: 'twinvine_course_queue.json',
      saveAs: true
    });
    sendResponse({ success: true });
  }
  return true;
});

// Load queue on startup
chrome.storage.local.get(['courseQueue'], (result) => {
  if (result.courseQueue) {
    courseQueue = result.courseQueue;
    if (courseQueue.length > 0) {
      chrome.action.setBadgeText({ text: String(courseQueue.length) });
      chrome.action.setBadgeBackgroundColor({ color: '#FF9800' });
    }
  }
});

// Initialize
chrome.action.setBadgeText({ text: '' });
console.log('TwinVine Auto-Capture initialized - using browser tab title!');
