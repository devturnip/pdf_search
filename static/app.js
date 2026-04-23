const statusEl = document.getElementById('status');
const queryInput = document.getElementById('queryInput');
const imageInput = document.getElementById('imageInput');
const searchBtn = document.getElementById('searchBtn');
const reindexBtn = document.getElementById('reindexBtn');
const managePdfsBtn = document.getElementById('managePdfsBtn');
const pdfManager = document.getElementById('pdfManager');
const pdfList = document.getElementById('pdfList');
const pdfUploadInput = document.getElementById('pdfUploadInput');
const uploadPdfBtn = document.getElementById('uploadPdfBtn');
const resultsInfo = document.getElementById('resultsInfo');
const resultsGrid = document.getElementById('resultsGrid');
const modeBtns = document.querySelectorAll('.mode-btn');
const modal = document.getElementById('imageModal');
const modalImg = document.getElementById('modalImg');
const modalCaption = document.getElementById('modalCaption');
const modalHighlightOverlay = document.getElementById('modalHighlightOverlay');
const modalClose = document.querySelector('.modal-close');

let currentMode = 'exact';
let pdfManagerOpen = false;

async function loadStatus() {
    try {
        const res = await fetch('/api/status');
        const data = await res.json();
        statusEl.textContent = `${data.total_pdfs} PDFs · ${data.total_pages} pages · ${data.ready ? 'Ready' : 'Indexing...'}`;
    } catch (e) {
        statusEl.textContent = 'Error loading status';
    }
}

modeBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        modeBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentMode = btn.dataset.mode;
        if (currentMode === 'image') {
            queryInput.style.display = 'none';
            imageInput.style.display = 'block';
            searchBtn.textContent = 'Search Image';
        } else {
            queryInput.style.display = 'block';
            imageInput.style.display = 'none';
            searchBtn.textContent = 'Search';
        }
    });
});

searchBtn.addEventListener('click', performSearch);
queryInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') performSearch();
});
imageInput.addEventListener('change', () => {
    if (imageInput.files.length > 0) performSearch();
});

async function performSearch() {
    resultsGrid.innerHTML = '<div class="loading">Searching...</div>';
    resultsInfo.textContent = '';

    try {
        let res;
        if (currentMode === 'image') {
            const file = imageInput.files[0];
            if (!file) {
                resultsGrid.innerHTML = '<div class="loading">Please select an image</div>';
                return;
            }
            const formData = new FormData();
            formData.append('file', file);
            res = await fetch(`/api/search/image?top_k=20`, {
                method: 'POST',
                body: formData
            });
        } else {
            const query = queryInput.value.trim();
            if (!query) {
                resultsGrid.innerHTML = '';
                return;
            }
            res = await fetch('/api/search/text', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query, mode: currentMode, top_k: 20 })
            });
        }

        const data = await res.json();
        renderResults(data);
    } catch (e) {
        resultsGrid.innerHTML = `<div class="loading">Error: ${e.message}</div>`;
    }
}

function renderResults(data) {
    resultsInfo.textContent = `${data.total} results · ${data.mode}${data.query ? ' · "' + data.query + '"' : ''}`;
    resultsGrid.innerHTML = '';

    if (!data.results || data.results.length === 0) {
        resultsGrid.innerHTML = '<div class="loading">No results found</div>';
        return;
    }

    data.results.forEach(r => {
        const card = document.createElement('div');
        card.className = 'result-card';
        const highlightHtml = buildHighlightOverlay(r.highlights, r.page_width, r.page_height);
        card.innerHTML = `
            <div class="image-container">
                <img src="${r.thumbnail_url}" alt="Page ${r.page_num + 1}" loading="lazy">
                ${highlightHtml}
            </div>
            <div class="result-meta">
                <div class="pdf-name">${escapeHtml(r.pdf_name)}</div>
                <div class="page-num">Page ${r.page_num + 1}</div>
                <div class="score">Score: ${r.score}</div>
                <div class="snippet">${escapeHtml(r.text_snippet)}</div>
            </div>
        `;
        card.addEventListener('click', () => openModal(r.full_image_url, `${r.pdf_name} — Page ${r.page_num + 1}`, r.highlights, r.page_width, r.page_height));
        resultsGrid.appendChild(card);
    });
}

function buildHighlightOverlay(highlights, pageWidth, pageHeight) {
    if (!highlights || highlights.length === 0 || !pageWidth || !pageHeight) {
        return '';
    }
    const boxes = highlights.map(h => {
        const left = (h.x0 / pageWidth) * 100;
        const top = (h.y0 / pageHeight) * 100;
        const width = ((h.x1 - h.x0) / pageWidth) * 100;
        const height = ((h.y1 - h.y0) / pageHeight) * 100;
        return `<div class="highlight-box" style="left:${left.toFixed(2)}%;top:${top.toFixed(2)}%;width:${width.toFixed(2)}%;height:${height.toFixed(2)}%;"></div>`;
    }).join('');
    return `<div class="highlight-overlay">${boxes}</div>`;
}

function openModal(src, caption, highlights, pageWidth, pageHeight) {
    modalImg.src = src;
    modalCaption.textContent = caption;
    modalHighlightOverlay.innerHTML = '';
    if (highlights && highlights.length > 0 && pageWidth && pageHeight) {
        modalHighlightOverlay.innerHTML = highlights.map(h => {
            const left = (h.x0 / pageWidth) * 100;
            const top = (h.y0 / pageHeight) * 100;
            const width = ((h.x1 - h.x0) / pageWidth) * 100;
            const height = ((h.y1 - h.y0) / pageHeight) * 100;
            return `<div class="highlight-box" style="left:${left.toFixed(2)}%;top:${top.toFixed(2)}%;width:${width.toFixed(2)}%;height:${height.toFixed(2)}%;"></div>`;
        }).join('');
    }
    modal.classList.add('active');
}

modalClose.addEventListener('click', () => {
    modal.classList.remove('active');
    modalImg.src = '';
    modalHighlightOverlay.innerHTML = '';
});

modal.addEventListener('click', (e) => {
    if (e.target === modal) {
        modal.classList.remove('active');
        modalImg.src = '';
        modalHighlightOverlay.innerHTML = '';
    }
});

reindexBtn.addEventListener('click', async () => {
    reindexBtn.disabled = true;
    reindexBtn.textContent = 'Indexing...';
    try {
        const res = await fetch('/api/reindex', { method: 'POST' });
        const data = await res.json();
        alert(`Re-indexed ${data.total_pages} pages.`);
        loadStatus();
        if (pdfManagerOpen) loadPdfList();
    } catch (e) {
        alert('Re-index failed: ' + e.message);
    } finally {
        reindexBtn.disabled = false;
        reindexBtn.textContent = 'Re-index';
    }
});

/* PDF Manager */
managePdfsBtn.addEventListener('click', () => {
    pdfManagerOpen = !pdfManagerOpen;
    pdfManager.style.display = pdfManagerOpen ? 'block' : 'none';
    managePdfsBtn.textContent = pdfManagerOpen ? 'Hide PDFs' : 'Manage PDFs';
    if (pdfManagerOpen) loadPdfList();
});

async function loadPdfList() {
    pdfList.innerHTML = '<div class="loading">Loading PDFs...</div>';
    try {
        const res = await fetch('/api/pdfs');
        const data = await res.json();
        renderPdfList(data.pdfs);
    } catch (e) {
        pdfList.innerHTML = `<div class="loading">Error loading PDFs: ${e.message}</div>`;
    }
}

function renderPdfList(pdfs) {
    pdfList.innerHTML = '';
    if (!pdfs || pdfs.length === 0) {
        pdfList.innerHTML = '<div class="loading">No PDFs found</div>';
        return;
    }

    pdfs.forEach(pdf => {
        const item = document.createElement('div');
        item.className = 'pdf-item';
        const badgeClass = pdf.indexed ? 'indexed' : 'not-indexed';
        const badgeText = pdf.indexed ? 'Indexed' : 'Not Indexed';
        item.innerHTML = `
            <div class="pdf-item-info">
                <div class="pdf-item-name">${escapeHtml(pdf.name)}</div>
                <div class="pdf-item-meta">
                    ${pdf.pages > 0 ? pdf.pages + ' pages' : 'Not processed'}
                    <span class="pdf-item-badge ${badgeClass}">${badgeText}</span>
                </div>
            </div>
            <div class="pdf-item-actions">
                <a href="/api/download/${encodeURIComponent(pdf.name)}" class="btn-small btn-outline" download>Download</a>
                <button class="btn-small btn-danger" data-name="${escapeHtml(pdf.name)}">Delete</button>
            </div>
        `;
        item.querySelector('.btn-danger').addEventListener('click', () => deletePdf(pdf.name));
        pdfList.appendChild(item);
    });
}

async function deletePdf(name) {
    if (!confirm(`Are you sure you want to delete "${name}"?\n\nThis will remove the file and all associated data permanently.`)) {
        return;
    }

    try {
        const res = await fetch(`/api/pdfs/${encodeURIComponent(name)}`, { method: 'DELETE' });
        const data = await res.json();
        if (res.ok) {
            alert(data.message);
            loadPdfList();
            loadStatus();
        } else {
            alert('Delete failed: ' + (data.detail || data.message));
        }
    } catch (e) {
        alert('Delete failed: ' + e.message);
    }
}

uploadPdfBtn.addEventListener('click', () => {
    pdfUploadInput.click();
});

pdfUploadInput.addEventListener('change', async () => {
    const file = pdfUploadInput.files[0];
    if (!file) return;

    uploadPdfBtn.disabled = true;
    uploadPdfBtn.textContent = 'Uploading...';

    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        const data = await res.json();
        if (res.ok) {
            alert(data.message);
            loadPdfList();
            loadStatus();
        } else {
            alert('Upload failed: ' + (data.detail || data.message));
        }
    } catch (e) {
        alert('Upload failed: ' + e.message);
    } finally {
        uploadPdfBtn.disabled = false;
        uploadPdfBtn.textContent = '+ Upload PDF';
        pdfUploadInput.value = '';
    }
});

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

loadStatus();
