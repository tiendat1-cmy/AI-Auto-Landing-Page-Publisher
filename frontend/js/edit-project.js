/**
 * Logic Form chỉnh sửa Landing Page & Xem trước trực tiếp (Live Preview)
 * Hỗ trợ:
 *   - Tự động điền dữ liệu cũ từ API (GET /api/v1/projects/{id})
 *   - Xem trước trực tiếp trước khi lưu (Live Preview) trong iframe
 *   - Thay đổi kích thước khung xem: Desktop, Tablet, Mobile
 *   - Gửi yêu cầu cập nhật (PUT /projects/{id} hoặc /api/v1/projects/{id})
 *   - Hiển thị thông báo, commit SHA, và phiên bản mới sau khi cập nhật thành công
 */

// Xác định API Host (hỗ trợ cả chạy qua backend 8000 hoặc Live Server độc lập)
const API_BASE = window.location.origin.includes('5500') || window.location.origin.includes('3000') || window.location.protocol === 'file:'
  ? 'http://127.0.0.1:8000'
  : window.location.origin;

let currentProjectId = 1;
let initialProjectData = null;
let debounceTimer = null;

// Khởi chạy khi DOM sẵn sàng
document.addEventListener('DOMContentLoaded', () => {
    initProjectId();
    setupEventListeners();
    loadProjectData(currentProjectId);
});

/**
 * Lấy project_id từ URL query parameter (?id=... hoặc ?project_id=...)
 */
function initProjectId() {
    const urlParams = new URLSearchParams(window.location.search);
    const idParam = urlParams.get('id') || urlParams.get('project_id');
    if (idParam && !isNaN(parseInt(idParam))) {
        currentProjectId = parseInt(idParam);
    }
    const idInput = document.getElementById('project-id-input');
    if (idInput) {
        idInput.value = currentProjectId;
    }
}

/**
 * Gắn các sự kiện cho form, nút xem trước, chuyển đổi thiết bị và nút lưu
 */
function setupEventListeners() {
    // Sự kiện đổi ID dự án
    const btnLoadProject = document.getElementById('btn-load-project');
    if (btnLoadProject) {
        btnLoadProject.addEventListener('click', () => {
            const idInput = document.getElementById('project-id-input');
            const newId = parseInt(idInput.value);
            if (newId && newId > 0) {
                currentProjectId = newId;
                // Cập nhật URL mà không reload trang
                const newUrl = new URL(window.location.href);
                newUrl.searchParams.set('project_id', currentProjectId);
                window.history.pushState({}, '', newUrl);
                loadProjectData(currentProjectId);
            }
        });
    }

    // Lắng nghe thay đổi input trong Form để tự động live preview
    const form = document.getElementById('edit-landing-page-form');
    if (form) {
        form.addEventListener('input', (e) => {
            // Đồng bộ ô chọn màu và mã hex
            if (e.target.id === 'color_theme') {
                document.getElementById('color_theme_hex').value = e.target.value;
            } else if (e.target.id === 'color_theme_hex') {
                if (/^#[0-9A-Fa-f]{6}$/.test(e.target.value)) {
                    document.getElementById('color_theme').value = e.target.value;
                }
            }
            debouncedPreview();
        });

        // Xử lý submit form (nút Lưu & Cập nhật Website)
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            await saveAndUpdateLandingPage();
        });
    }

    // Nút xem trước thủ công
    const btnRefreshPreview = document.getElementById('btn-refresh-preview');
    if (btnRefreshPreview) {
        btnRefreshPreview.addEventListener('click', () => {
            triggerPreview();
        });
    }

    // Nút reset về dữ liệu ban đầu
    const btnResetForm = document.getElementById('btn-reset-form');
    if (btnResetForm) {
        btnResetForm.addEventListener('click', () => {
            if (initialProjectData) {
                populateForm(initialProjectData);
                triggerPreview();
                showToast('Đã khôi phục lại dữ liệu ban đầu của dự án', 'info');
            }
        });
    }

    // Bộ chọn thiết bị xem trước (Desktop, Tablet, Mobile)
    const deviceButtons = document.querySelectorAll('.btn-device-view');
    const previewWrapper = document.getElementById('preview-frame-wrapper');
    deviceButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            deviceButtons.forEach(b => {
                b.classList.remove('bg-indigo-600', 'text-white', 'shadow-sm');
                b.classList.add('text-slate-600', 'hover:bg-slate-100');
            });
            btn.classList.add('bg-indigo-600', 'text-white', 'shadow-sm');
            btn.classList.remove('text-slate-600', 'hover:bg-slate-100');

            const device = btn.dataset.device;
            previewWrapper.className = 'w-full h-full flex items-center justify-center p-2 sm:p-4 overflow-auto';
            const frame = document.getElementById('preview-iframe');
            if (device === 'desktop') {
                frame.className = 'w-full h-full border-0 bg-white rounded-xl shadow-inner viewport-desktop';
            } else if (device === 'tablet') {
                frame.className = 'h-[720px] border-0 bg-white viewport-tablet';
            } else if (device === 'mobile') {
                frame.className = 'h-[640px] border-0 bg-white viewport-mobile';
            }
        });
    });

    // Preset màu sắc nhanh
    const colorBadges = document.querySelectorAll('.color-swatch');
    colorBadges.forEach(swatch => {
        swatch.addEventListener('click', () => {
            const hex = swatch.dataset.color;
            document.getElementById('color_theme').value = hex;
            document.getElementById('color_theme_hex').value = hex;
            debouncedPreview();
        });
    });

    // Đóng modal thông báo thành công
    const btnCloseModal = document.getElementById('btn-close-modal');
    if (btnCloseModal) {
        btnCloseModal.addEventListener('click', () => {
            document.getElementById('success-modal').classList.add('hidden');
        });
    }
}

/**
 * Tải dữ liệu cũ của project từ API và điền vào form
 */
async function loadProjectData(projectId) {
    showFormLoading(true);
    setPreviewStatus('Đang tải dữ liệu dự án...');

    try {
        const response = await fetch(`${API_BASE}/api/v1/projects/${projectId}`);
        if (!response.ok) {
            throw new Error(`Không thể tải thông tin dự án (Mã lỗi ${response.status})`);
        }
        const data = await response.json();
        initialProjectData = data;

        populateForm(data);
        showFormLoading(false);
        showToast(`Đã tải thành công dữ liệu dự án #${projectId}`, 'success');

        // Tự động kích hoạt xem trước
        triggerPreview();

    } catch (error) {
        showFormLoading(false);
        setPreviewStatus(`Lỗi kết nối: ${error.message}`);
        showToast(`Lỗi: ${error.message}`, 'error');
        console.error('Error fetching project:', error);
    }
}

/**
 * Điền sẵn dữ liệu cũ vào các trường input
 */
function populateForm(data) {
    document.getElementById('campaign_name').value = data.campaign_name || '';
    document.getElementById('product_name').value = data.product_name || '';
    document.getElementById('product_description').value = data.product_description || '';
    document.getElementById('price').value = data.price !== null && data.price !== undefined ? data.price : '';
    
    const themeColor = data.color_theme || '#6366f1';
    document.getElementById('color_theme').value = themeColor;
    document.getElementById('color_theme_hex').value = themeColor;

    document.getElementById('image_url').value = data.image_url || '';
    document.getElementById('facebook_url').value = data.facebook_url || '';
    document.getElementById('tiktok_url').value = data.tiktok_url || '';
    document.getElementById('instagram_url').value = data.instagram_url || '';
    document.getElementById('repo_url').value = data.repo_url || '';
    document.getElementById('github_pages_url').value = data.github_pages_url || '';

    // Dữ liệu mở rộng từ raw_json_data
    const raw = data.raw_json_data || {};
    document.getElementById('headline').value = raw.headline || data.product_name || '';
    document.getElementById('subheadline').value = raw.subheadline || '';
    document.getElementById('cta_text').value = raw.cta_text || 'Đặt Mua Ngay';
    document.getElementById('change_summary').value = 'Cập nhật landing page: text, giá, link social';

    // Cập nhật text badge trạng thái
    const badge = document.getElementById('project-status-badge');
    if (badge) {
        badge.textContent = `Trạng thái: ${data.status || 'draft'}`;
    }
}

/**
 * Gom toàn bộ dữ liệu từ Form thành payload object
 */
function collectFormData() {
    const priceVal = document.getElementById('price').value.trim();
    const parsedPrice = priceVal !== '' ? parseFloat(priceVal) : null;

    return {
        campaign_name: document.getElementById('campaign_name').value.trim(),
        product_name: document.getElementById('product_name').value.trim(),
        product_description: document.getElementById('product_description').value.trim(),
        price: parsedPrice,
        color_theme: document.getElementById('color_theme_hex').value.trim() || document.getElementById('color_theme').value,
        image_url: document.getElementById('image_url').value.trim(),
        facebook_url: document.getElementById('facebook_url').value.trim(),
        tiktok_url: document.getElementById('tiktok_url').value.trim(),
        instagram_url: document.getElementById('instagram_url').value.trim(),
        repo_url: document.getElementById('repo_url').value.trim(),
        github_pages_url: document.getElementById('github_pages_url').value.trim(),
        change_summary: document.getElementById('change_summary').value.trim(),
        raw_json_data: {
            headline: document.getElementById('headline').value.trim(),
            subheadline: document.getElementById('subheadline').value.trim(),
            cta_text: document.getElementById('cta_text').value.trim(),
        }
    };
}

/**
 * Kích hoạt preview có debounce (tránh gửi request liên tục khi đang gõ)
 */
function debouncedPreview() {
    if (debounceTimer) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
        triggerPreview();
    }, 350);
}

/**
 * Gọi API xem trước (POST /api/v1/projects/{id}/preview) và render vào iframe
 */
async function triggerPreview() {
    const payload = collectFormData();
    setPreviewStatus('Đang cập nhật xem trước...');

    try {
        const response = await fetch(`${API_BASE}/api/v1/projects/${currentProjectId}/preview`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload),
        });

        if (!response.ok) {
            throw new Error(`Lỗi render preview (HTTP ${response.status})`);
        }

        const data = await response.json();
        const iframe = document.getElementById('preview-iframe');
        iframe.srcdoc = data.rendered_html;

        setPreviewStatus('Xem trước trực tiếp (Live Preview)');
    } catch (error) {
        console.warn('Lỗi gọi API preview, sử dụng fallback render trực tiếp:', error);
        fallbackClientPreview(payload);
    }
}

/**
 * Render trực tiếp trên Client nếu server bận hoặc offline
 */
function fallbackClientPreview(payload) {
    const iframe = document.getElementById('preview-iframe');
    const priceStr = payload.price ? `${Number(payload.price).toLocaleString('vi-VN')} ₫` : '';
    const theme = payload.color_theme || '#6366f1';
    const img = payload.image_url || 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=800';

    const fallbackHtml = `
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;800&display=swap" rel="stylesheet">
    </head>
    <body class="bg-slate-50 font-sans p-6 text-slate-800">
        <div class="max-w-2xl mx-auto bg-white rounded-3xl p-8 shadow-xl border border-slate-100">
            <span class="inline-block px-3 py-1 rounded-full text-xs font-bold text-white mb-4" style="background-color: ${theme}">
                ${payload.campaign_name || 'Chiến dịch'}
            </span>
            <h1 class="text-3xl font-extrabold text-slate-950 mb-3">${payload.product_name || 'Tên sản phẩm'}</h1>
            <p class="text-slate-600 mb-6">${payload.product_description || 'Mô tả sản phẩm...'}</p>
            ${priceStr ? `<div class="text-2xl font-black mb-6 text-slate-900">Giá: ${priceStr}</div>` : ''}
            <img src="${img}" class="w-full h-64 object-cover rounded-2xl mb-6 shadow">
            <div class="flex gap-4">
                <button class="px-6 py-3 rounded-xl text-white font-bold" style="background-color: ${theme}">
                    ${payload.raw_json_data?.cta_text || 'Đặt Mua Ngay'}
                </button>
            </div>
        </div>
    </body>
    </html>
    `;
    iframe.srcdoc = fallbackHtml;
    setPreviewStatus('Xem trước (chế độ nhanh)');
}

/**
 * Thực hiện yêu cầu PUT /projects/{id} để:
 * sửa text, giá, link social -> render lại HTML -> push commit mới lên GitHub -> lưu phiên bản mới.
 */
async function saveAndUpdateLandingPage() {
    const btnSave = document.getElementById('btn-save-project');
    const originalBtnText = btnSave.innerHTML;
    
    // Đổi trạng thái nút bấm sang Loading
    btnSave.disabled = true;
    btnSave.innerHTML = `
        <svg class="animate-spin -ml-1 mr-3 h-5 w-5 text-white inline-block" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        Đang render HTML & push GitHub...
    `;

    const payload = collectFormData();

    try {
        // Gửi yêu cầu PUT /api/v1/projects/{id}
        const response = await fetch(`${API_BASE}/api/v1/projects/${currentProjectId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload),
        });

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || `Lỗi cập nhật (HTTP ${response.status})`);
        }

        const result = await response.json();

        // Cập nhật iframe với HTML chính thức vừa được render và lưu
        if (result.rendered_html) {
            const iframe = document.getElementById('preview-iframe');
            iframe.srcdoc = result.rendered_html;
        }

        // Cập nhật dữ liệu gốc để nút Reset hoạt động đúng
        if (result.project) {
            initialProjectData = result.project;
        }

        // Hiển thị modal chúc mừng thành công với commit SHA và phiên bản mới
        showSuccessModal(result);
        showToast('Cập nhật Landing Page và push commit GitHub thành công!', 'success');

    } catch (error) {
        showToast(`Lỗi: ${error.message}`, 'error');
        alert(`Không thể cập nhật website:\n${error.message}`);
        console.error('Save error:', error);
    } finally {
        // Khôi phục nút bấm
        btnSave.disabled = false;
        btnSave.innerHTML = originalBtnText;
    }
}

/**
 * Hiển thị Modal thông báo thành công với số phiên bản và commit SHA
 */
function showSuccessModal(result) {
    const modal = document.getElementById('success-modal');
    if (!modal) return;

    document.getElementById('modal-version-number').textContent = `v${result.version_number || 'Mới'}`;
    document.getElementById('modal-commit-sha').textContent = result.commit_sha || 'N/A';
    
    const pagesUrl = result.project?.github_pages_url || result.project?.repo_url || '#';
    const linkBtn = document.getElementById('modal-website-link');
    if (linkBtn) {
        linkBtn.href = pagesUrl;
        linkBtn.textContent = pagesUrl !== '#' ? 'Mở Website GitHub Pages ↗' : 'Xem thông tin dự án';
    }

    const versionLink = document.getElementById('modal-versions-link');
    if (versionLink) {
        versionLink.href = `${API_BASE}/api/v1/projects/${currentProjectId}/versions`;
    }

    modal.classList.remove('hidden');
}

/**
 * Hiển thị thông báo Toast góc dưới
 */
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    const bgColors = {
        success: 'bg-emerald-600 text-white',
        error: 'bg-rose-600 text-white',
        info: 'bg-slate-900 text-white',
    };

    toast.className = `px-4 py-3 rounded-xl shadow-lg font-medium text-sm flex items-center gap-3 transition-all transform duration-300 translate-y-4 opacity-0 ${bgColors[type] || bgColors.info}`;
    toast.innerHTML = `
        <span>${type === 'success' ? '✓' : type === 'error' ? '✕' : 'ℹ'}</span>
        <span>${message}</span>
    `;

    container.appendChild(toast);

    // Kích hoạt animation xuất hiện
    requestAnimationFrame(() => {
        toast.classList.remove('translate-y-4', 'opacity-0');
    });

    // Tự biến mất sau 4 giây
    setTimeout(() => {
        toast.classList.add('opacity-0', 'translate-y-4');
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

function showFormLoading(isLoading) {
    const overlay = document.getElementById('form-loading-overlay');
    if (overlay) {
        if (isLoading) overlay.classList.remove('hidden');
        else overlay.classList.add('hidden');
    }
}

function setPreviewStatus(text) {
    const el = document.getElementById('preview-status-text');
    if (el) el.textContent = text;
}
