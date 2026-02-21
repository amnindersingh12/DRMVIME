// TwinVine api-interceptor.js
// Runs in the MAIN world (true page context) to intercept API responses
// before the Testbook frontend even renders them.
// NOTE: iframe PDF extraction is handled by iframe-extractor.js (cross-origin safe)

(function () {
    // ========== XHR/FETCH INTERCEPTION ==========
    const OriginalXHR = window.XMLHttpRequest;
    class MonkeyXHR extends OriginalXHR {
        constructor() {
            super();
            this.addEventListener('load', function () {
                try {
                    if (this.responseType === '' || this.responseType === 'text') {
                        const data = JSON.parse(this.responseText);
                        analyzeApiResponse(this.responseURL, data);
                    }
                } catch (_) { }
            });
        }
    }
    window.XMLHttpRequest = MonkeyXHR;

    const originalFetch = window.fetch;
    window.fetch = async function (...args) {
        const response = await originalFetch.apply(this, args);
        const clone = response.clone();
        clone.json().then(data => {
            analyzeApiResponse(args[0], data);
        }).catch(() => { });
        return response;
    };

    function analyzeApiResponse(url, data) {
        let title = '';
        let pdfUrl = '';
        let pdfFilename = '';

        const urlStr = typeof url === 'string' ? url : (url && url.url ? url.url : '');
        if (!urlStr.includes('testbook.com/api/')) return;

        // Helper to decide if a title is valid (not placeholder)
        const isValidTitle = (t) => {
            if (!t) return false;
            const trimmed = t.trim();
            if (trimmed.length < 3 || trimmed.length > 100) return false;
            if (/^[a-f0-9]{20,32}$/i.test(trimmed)) return false;
            const lower = trimmed.toLowerCase();
            if (lower.includes('testbook')) return false;
            if (lower.includes('coming soon')) return false;
            return true;
        };

        // Recursively search the JSON for title and pdf fields
        function searchObj(obj) {
            if (!obj || typeof obj !== 'object') return;

            // PDF detection (same as before)
            if (obj.pdfUrl || obj.pdfUrlHtml || obj.pdf_url) {
                pdfUrl = obj.pdfUrl || obj.pdfUrlHtml || obj.pdf_url;
                if (pdfUrl && pdfUrl.startsWith('http')) {
                    const n = pdfUrl.match(/[\/=]([^/=]+?\.pdf)/i);
                    if (n) pdfFilename = decodeURIComponent(n[1]);
                }
            }

            // Title detection – prioritize known fields
            const possibleKeys = ['title', 'name', 'lessonTitle', 'lesson_name', 'moduleName', 'topicName'];
            for (const key of possibleKeys) {
                if (obj[key] && typeof obj[key] === 'string' && isValidTitle(obj[key])) {
                    title = obj[key].trim();
                }
            }

            // Special handling for videos/sync payload – it often nests under data.lesson.title
            if (urlStr.includes('/videos/sync') && obj.lesson && typeof obj.lesson === 'object') {
                if (obj.lesson.title && isValidTitle(obj.lesson.title)) {
                    title = obj.lesson.title.trim();
                }
                if (obj.lesson.name && isValidTitle(obj.lesson.name)) {
                    title = obj.lesson.name.trim();
                }
            }

            // Recurse deeper
            for (const key in obj) {
                if (typeof obj[key] === 'object') {
                    searchObj(obj[key]);
                }
            }
        }

        searchObj(data);

        if (title || pdfUrl) {
            window.postMessage({
                type: 'TWINVINE_API_DATA',
                title: title,
                pdfUrl: pdfUrl,
                pdfFilename: pdfFilename,
                sourceUrl: urlStr
            }, '*');
        }
    }
})();
