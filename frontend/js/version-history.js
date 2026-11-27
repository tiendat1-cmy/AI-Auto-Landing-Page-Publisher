/**
 * [FE] Trang lịch sử phiên bản Landing Page.
 *
 * Luồng nghiệp vụ:
 *   1. GET  /projects/{id}                                   -> thông tin dự án.
 *   2. GET  /api/v1/projects/{id}/versions                   -> danh sách snapshot.
 *   3. GET  /api/v1/projects/{id}/versions/{version_id}      -> xem chi tiết snapshot.
 *   4. POST /api/v1/projects/{id}/versions/{version_id}/restore -> khôi phục phiên bản.
 *
 * Mọi request đều đi qua window.apiRequest để tự gắn Authorization: Bearer <token>.
 */
(function () {
  'use strict';

  const API_PREFIX = '';
  const state = {
    projectId: null,
    project: null,
    versions: [],
    restoreTarget: null,
    restoring: false,
    detailSeq: 0,
  };

  const $ = (id) => document.getElementById(id);

  document.addEventListener('DOMContentLoaded', init);

  // ── Khởi tạo ──────────────────────────────────────────────────────
  function init() {
    bindEvents();

    const params = new URLSearchParams(window.location.search);
    const id = params.get('id') || params.get('project_id');

    if (!id) {
      showError('Đường dẫn thiếu tham số ?id=<project_id>. Hãy mở trang từ danh sách dự án.');
      return;
    }
    if (!/^\d+$/.test(String(id))) {
      showError(`ID dự án "${id}" không hợp lệ.`);
      return;
    }

    state.projectId = String(id);
    updateProjectLinks();
    loadPage();
  }

  function bindEvents() {
    $('btn-retry-versions')?.addEventListener('click', loadPage);

    $('version-list')?.addEventListener('click', handleListClick);

    $('btn-cancel-restore')?.addEventListener('click', closeRestoreModal);
    $('btn-confirm-restore')?.addEventListener('click', confirmRestore);
    document.querySelectorAll('[data-close-restore-modal]').forEach((el) => {
      el.addEventListener('click', closeRestoreModal);
    });

    document.querySelectorAll('[data-close-detail-modal]').forEach((el) => {
      el.addEventListener('click', closeDetailModal);
    });

    document.addEventListener('keydown', (event) => {
      if (event.key !== 'Escape') return;
      closeRestoreModal();
      closeDetailModal();
    });
  }

  function updateProjectLinks() {
    const editHref = `edit-project.html?id=${encodeURIComponent(state.projectId || '')}`;
    const backEdit = $('btn-back-edit');
    if (backEdit) backEdit.href = editHref;
    const emptyEdit = $('btn-empty-edit');
    if (emptyEdit) emptyEdit.href = editHref;
  }

  // ── Tải dữ liệu ───────────────────────────────────────────────────
  async function loadPage() {
    if (!state.projectId) return;

    setLoading(true);
    hideError();

    try {
      const [projectResponse, versionsResponse] = await Promise.all([
        apiRequest(`${API_PREFIX}/projects/${state.projectId}`),
        apiRequest(`/api/v1/projects/${state.projectId}/versions`),
      ]);

      state.project = projectResponse?.data || projectResponse?.project || {};
      state.versions = normalizeVersionList(versionsResponse);

      renderProjectMeta();
      renderVersions();
    } catch (error) {
      console.error('Lỗi tải lịch sử phiên bản:', error);
      showError(error.message || 'Không thể tải lịch sử phiên bản.');
    } finally {
      setLoading(false);
    }
  }

  function normalizeVersionList(payload) {
    const list = Array.isArray(payload) ? payload : payload?.data || [];
    return [...list].sort((a, b) => (b.version_number || 0) - (a.version_number || 0));
  }

  function renderProjectMeta() {
    const project = state.project || {};
    const title = project.product_name || project.campaign_name || 'Landing Page';
    const titleEl = $('version-project-title');
    if (titleEl) titleEl.textContent = title;

    const totalEl = $('stat-total-versions');
    if (totalEl) totalEl.textContent = String(state.versions.length);

    const latest = state.versions[0];
    const latestEl = $('stat-latest-version');
    if (latestEl) latestEl.textContent = latest ? `v${latest.version_number}` : '—';

    const timeEl = $('stat-latest-time');
    if (timeEl) timeEl.textContent = latest ? formatDateTime(latest.created_at) : '—';

    document.title = `Lịch sử phiên bản - ${title}`;
  }

  function renderVersions() {
    const listEl = $('version-list');
    const emptyEl = $('version-empty');
    if (!listEl || !emptyEl) return;

    if (!state.versions.length) {
      listEl.innerHTML = '';
      listEl.classList.add('hidden');
      emptyEl.classList.remove('hidden');
      return;
    }

    emptyEl.classList.add('hidden');
    listEl.classList.remove('hidden');
    listEl.innerHTML = state.versions.map(renderVersionItem).join('');
  }

  function renderVersionItem(version, index) {
    const isLatest = index === 0;
    const versionNumber = Number(version.version_number) || 0;
    const summary = version.change_summary || 'Không có ghi chú thay đổi';
    const sha = version.commit_sha || '';
    const shortSha = sha ? sha.slice(0, 7) : '—';
    const createdAt = formatDateTime(version.created_at);
    const createdBy = formatCreator(version) || '—';
    const creatorTitle = version.created_by_email
      ? ` title="${escapeHtml(version.created_by_email)}"`
      : '';

    const restoreButton = isLatest
      ? `
        <button type="button" disabled title="Đây đã là phiên bản mới nhất"
          class="inline-flex items-center justify-center gap-1.5 px-3.5 py-2 rounded-xl border border-slate-200 bg-slate-50 text-slate-400 text-[11px] font-bold cursor-not-allowed">
          <i class="fa-solid fa-check"></i>
          <span>Mới nhất</span>
        </button>`
      : `
        <button type="button" data-action="restore" data-version-id="${version.id}"
          class="inline-flex items-center justify-center gap-1.5 px-3.5 py-2 rounded-xl border border-amber-200 bg-amber-50 hover:bg-amber-100 text-amber-700 text-[11px] font-bold transition">
          <i class="fa-solid fa-clock-rotate-left"></i>
          <span>Khôi phục</span>
        </button>`;

    return `
      <article class="p-4 sm:p-5 hover:bg-slate-50/70 transition flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div class="flex items-start gap-3.5 min-w-0">
          <div class="w-12 h-12 rounded-xl ${isLatest ? 'bg-emerald-50 border-emerald-200 text-emerald-700' : 'bg-indigo-50 border-indigo-100 text-indigo-700'} border flex items-center justify-center text-xs font-extrabold shrink-0">
            v${versionNumber}
          </div>
          <div class="min-w-0">
            <div class="flex flex-wrap items-center gap-2">
              <h4 class="text-sm font-bold text-slate-800 truncate max-w-full">${escapeHtml(summary)}</h4>
              ${isLatest ? '<span class="text-[10px] px-2 py-0.5 rounded-full font-bold bg-emerald-50 text-emerald-600 border border-emerald-200">Hiện tại</span>' : ''}
            </div>
            <div class="flex flex-wrap items-center gap-x-3 gap-y-1.5 mt-1.5 text-[11px] text-slate-400">
              <span class="inline-flex items-center gap-1.5">
                <i class="fa-regular fa-clock"></i>
                <span>${escapeHtml(createdAt)}</span>
              </span>
              <button type="button" data-action="copy-sha" data-sha="${escapeHtml(sha)}"
                class="inline-flex items-center gap-1.5 font-mono hover:text-indigo-600 transition ${sha ? '' : 'pointer-events-none'}"
                title="${sha ? 'Sao chép commit SHA' : 'Không có commit SHA'}">
                <i class="fa-solid fa-code-commit"></i>
                <span>${escapeHtml(shortSha)}</span>
                ${sha ? '<i class="fa-regular fa-copy text-[10px]"></i>' : ''}
              </button>
              <span class="inline-flex items-center gap-1.5"${creatorTitle}>
                <i class="fa-regular fa-user"></i>
                <span>Tạo bởi ${escapeHtml(createdBy)}</span>
              </span>
            </div>
          </div>
        </div>

        <div class="flex items-center gap-2 shrink-0 lg:pl-4">
          <button type="button" data-action="detail" data-version-id="${version.id}"
            class="inline-flex items-center justify-center gap-1.5 px-3.5 py-2 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-slate-600 text-[11px] font-bold transition">
            <i class="fa-solid fa-eye"></i>
            <span>Xem chi tiết</span>
          </button>
          ${restoreButton}
        </div>
      </article>
    `;
  }

  // ── Xử lý thao tác trên danh sách ─────────────────────────────────
  function handleListClick(event) {
    const button = event.target.closest('[data-action]');
    if (!button) return;

    const action = button.dataset.action;
    const versionId = Number(button.dataset.versionId);

    if (action === 'copy-sha') {
      copyToClipboard(button.dataset.sha || '');
      return;
    }

    const version = state.versions.find((item) => Number(item.id) === versionId);
    if (!version) return;

    if (action === 'detail') {
      openDetailModal(version);
    } else if (action === 'restore') {
      openRestoreModal(version);
    }
  }

  async function copyToClipboard(text) {
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      window.showToast?.('Đã sao chép commit SHA vào clipboard.', 'success', 'Sao chép');
    } catch (error) {
      window.showToast?.('Trình duyệt không cho phép sao chép tự động.', 'warning', 'Sao chép');
    }
  }

  // ── Modal khôi phục ───────────────────────────────────────────────
  function openRestoreModal(version) {
    state.restoreTarget = version;
    const label = $('restore-version-label');
    if (label) label.textContent = `phiên bản v${version.version_number}`;
    $('restore-modal')?.classList.remove('hidden');
  }

  function closeRestoreModal() {
    if (state.restoring) return;
    state.restoreTarget = null;
    $('restore-modal')?.classList.add('hidden');
  }

  async function confirmRestore() {
    if (!state.restoreTarget || state.restoring) return;

    const version = state.restoreTarget;
    setRestoring(true);

    try {
      const response = await apiRequest(
        `/api/v1/projects/${state.projectId}/versions/${version.id}/restore`,
        { method: 'POST' }
      );

      state.restoreTarget = null;
      $('restore-modal')?.classList.add('hidden');

      const newVersion = response?.new_version;
      const warnings = Array.isArray(response?.warnings)
        ? response.warnings.filter(Boolean)
        : [];

      let message =
        response?.message ||
        `Đã khôi phục từ phiên bản v${version.version_number}${newVersion ? `, tạo phiên bản v${newVersion.version_number}` : ''}.`;
      if (warnings.length) {
        message += ` Lưu ý: ${warnings.join(' ')}`;
      }

      window.showToast?.(
        escapeHtml(message),
        warnings.length ? 'warning' : 'success',
        warnings.length ? 'Khôi phục một phần' : 'Khôi phục thành công'
      );
      await loadPage();
    } catch (error) {
      console.error('Lỗi khôi phục phiên bản:', error);
      window.showToast?.(
        error.message || 'Không thể khôi phục phiên bản này.',
        'error',
        'Khôi phục thất bại'
      );
    } finally {
      setRestoring(false);
    }
  }

  function setRestoring(restoring) {
    state.restoring = restoring;
    const button = $('btn-confirm-restore');
    const spinner = $('restore-spinner');
    const icon = $('restore-icon');
    const label = $('restore-btn-text');

    if (button) button.disabled = restoring;
    spinner?.classList.toggle('hidden', !restoring);
    icon?.classList.toggle('hidden', restoring);
    if (label) label.textContent = restoring ? 'Đang khôi phục...' : 'Khôi phục ngay';
  }

  // ── Modal chi tiết phiên bản ──────────────────────────────────────
  async function openDetailModal(version) {
    const modal = $('version-detail-modal');
    if (!modal) return;

    const seq = ++state.detailSeq;
    modal.classList.remove('hidden');

    setText('detail-modal-title', `Chi tiết phiên bản v${version.version_number}`);
    setText('detail-modal-meta', buildMetaLine(version));
    setText('detail-version-number', `v${version.version_number}`);
    setText('detail-commit-sha', version.commit_sha || '—');
    setText('detail-created-at', formatDateTime(version.created_at));
    setText('detail-change-summary', version.change_summary || 'Không có ghi chú thay đổi');

    const frame = $('detail-preview-frame');
    if (frame) frame.srcdoc = '<p style="font-family:sans-serif;padding:24px;color:#64748b">Đang tải bản xem trước...</p>';

    try {
      const response = await apiRequest(
        `/api/v1/projects/${state.projectId}/versions/${version.id}`
      );
      if (seq !== state.detailSeq) return;

      const detail = response?.data || response || {};
      setText('detail-modal-title', `Chi tiết phiên bản v${detail.version_number || version.version_number}`);
      setText('detail-modal-meta', buildMetaLine({ ...version, ...detail }));
      setText('detail-version-number', `v${detail.version_number || version.version_number}`);
      setText('detail-commit-sha', detail.commit_sha || '—');
      setText('detail-created-at', formatDateTime(detail.created_at || version.created_at));
      setText('detail-change-summary', detail.change_summary || 'Không có ghi chú thay đổi');

      if (frame) {
        frame.srcdoc =
          detail.html_snapshot ||
          '<p style="font-family:sans-serif;padding:24px;color:#64748b">Phiên bản này không có HTML snapshot.</p>';
      }
    } catch (error) {
      if (seq !== state.detailSeq) return;
      if (frame) {
        frame.srcdoc = '<p style="font-family:sans-serif;padding:24px;color:#b91c1c">Không tải được nội dung phiên bản.</p>';
      }
      window.showToast?.(error.message || 'Không tải được chi tiết phiên bản.', 'error', 'Lỗi');
    }
  }

  function closeDetailModal() {
    state.detailSeq += 1;
    $('version-detail-modal')?.classList.add('hidden');
    const frame = $('detail-preview-frame');
    if (frame) frame.srcdoc = '';
  }

  // ── Trạng thái tải / lỗi ──────────────────────────────────────────
  function setLoading(loading) {
    $('version-loading')?.classList.toggle('hidden', !loading);
  }

  function showError(message) {
    const box = $('version-error');
    const text = $('version-error-message');
    if (text) text.textContent = message;
    box?.classList.remove('hidden');
    $('version-loading')?.classList.add('hidden');
    $('version-list')?.classList.add('hidden');
    $('version-empty')?.classList.add('hidden');
  }

  function hideError() {
    $('version-error')?.classList.add('hidden');
  }

  // ── Helpers ───────────────────────────────────────────────────────
  function setText(id, value) {
    const el = $(id);
    if (el) el.textContent = value ?? '—';
  }

  function formatCreator(version) {
    if (!version) return '';
    return (
      version.created_by_name ||
      version.created_by_email ||
      (version.created_by ? `#${version.created_by}` : '')
    );
  }

  function buildMetaLine(version) {
    const parts = [];
    const creator = formatCreator(version);
    if (creator) parts.push(`Tạo bởi ${creator}`);
    const createdAt = formatDateTime(version?.created_at);
    if (createdAt && createdAt !== '—') parts.push(createdAt);
    return parts.join(' • ') || '—';
  }

  function formatDateTime(value) {
    if (!value) return '—';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString('vi-VN', { hour12: false });
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }
})();
