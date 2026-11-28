/**
 * Trang Danh sách dự án – dữ liệu thật từ FastAPI.
 *
 * Endpoints:
 *   GET    /projects?page=1&page_size=100  – danh sách dự án của người dùng.
 *   DELETE /projects/{id}                 – xóa mềm dự án và repository GitHub.
 *
 * Các thao tác Xem trước / Chỉnh sửa / Xuất bản điều hướng tới trang tương ứng.
 */
(function () {
  "use strict";

  const PAGE_SIZE = 10;
  const STATUS_MAP = {
    draft: { label: "Nháp", bg: "bg-amber-50", text: "text-amber-700", border: "border-amber-200", icon: "fa-pen-ruler" },
    deploying: { label: "Đang deploy", bg: "bg-blue-50", text: "text-blue-700", border: "border-blue-200", icon: "fa-cloud-arrow-up" },
    published: { label: "Đã xuất bản", bg: "bg-emerald-50", text: "text-emerald-700", border: "border-emerald-200", icon: "fa-globe" },
    failed: { label: "Lỗi", bg: "bg-rose-50", text: "text-rose-700", border: "border-rose-200", icon: "fa-triangle-exclamation" },
  };

  const state = {
    projects: [],
    page: 1,
    filter: "",
    deleteTarget: null,
    deleting: false,
  };

  const $ = (id) => document.getElementById(id);

  function escapeHtml(value) {
    const div = document.createElement("div");
    div.appendChild(document.createTextNode(value === null || value === undefined ? "" : String(value)));
    return div.innerHTML;
  }

  function formatDate(value) {
    if (!value) return "—";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "—";
    return date.toLocaleString("vi-VN", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function projectName(project) {
    return project.campaign_name || project.product_name || `Dự án #${project.id}`;
  }

  function statusBadge(status) {
    const config = STATUS_MAP[status] || {
      label: status || "—",
      bg: "bg-slate-50",
      text: "text-slate-600",
      border: "border-slate-200",
      icon: "fa-circle-info",
    };
    return `<span class="inline-flex items-center gap-1 text-[10px] px-2.5 py-0.5 rounded-full font-semibold ${config.bg} ${config.text} border ${config.border}">
      <i class="fa-solid ${config.icon} text-[9px]"></i>${escapeHtml(config.label)}
    </span>`;
  }

  function actionButton({ href, onClick, title, icon, className }) {
    if (href) {
      return `<a href="${escapeHtml(href)}" title="${escapeHtml(title)}" class="w-8 h-8 rounded-lg border flex items-center justify-center transition ${className}">
        <i class="fa-solid ${icon} text-xs"></i>
      </a>`;
    }
    return `<button type="button" data-action="${escapeHtml(onClick)}" title="${escapeHtml(title)}" class="w-8 h-8 rounded-lg border flex items-center justify-center transition ${className}">
      <i class="fa-solid ${icon} text-xs"></i>
    </button>`;
  }

  function getFiltered() {
    return state.projects.filter((project) => {
      if (project.status === "deleted" || project.deleted_at) return false;
      if (state.filter && project.status !== state.filter) return false;
      return true;
    });
  }

  function render() {
    const container = $("project-list");
    const pagination = $("pagination");
    if (!container) return;

    const filtered = getFiltered();
    const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
    if (state.page > totalPages) state.page = totalPages;
    const start = (state.page - 1) * PAGE_SIZE;
    const pageItems = filtered.slice(start, start + PAGE_SIZE);

    if (filtered.length === 0) {
      const hasProjects = state.projects.length > 0;
      container.innerHTML = `
        <div class="p-10 text-center">
          <div class="w-14 h-14 mx-auto rounded-2xl bg-indigo-50 text-indigo-500 flex items-center justify-center text-2xl mb-3">
            <i class="fa-solid ${hasProjects ? "fa-filter-circle-xmark" : "fa-folder-open"}"></i>
          </div>
          <p class="text-sm font-bold text-slate-700">${hasProjects ? "Không có dự án phù hợp bộ lọc" : "Chưa có dự án nào"}</p>
          <p class="text-xs text-slate-400 mt-1">${hasProjects ? "Hãy chọn trạng thái khác hoặc bỏ bộ lọc." : "Tạo Landing Page đầu tiên bằng AI để bắt đầu quản lý."}</p>
          <a href="create.html" class="inline-flex items-center gap-2 mt-4 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold transition">
            <i class="fa-solid fa-plus"></i>
            <span>Tạo dự án mới</span>
          </a>
        </div>
      `;
      pagination?.classList.add("hidden");
      return;
    }

    const rows = pageItems
      .map((project) => {
        const pagesUrl = project.github_pages_url || "";
        const previewHref = `preview.html?id=${encodeURIComponent(project.id)}`;
        const editHref = `edit-project.html?id=${encodeURIComponent(project.id)}`;
        const deployHref = `deploy.html?id=${encodeURIComponent(project.id)}`;

        const openAction = pagesUrl
          ? actionButton({
              href: pagesUrl,
              title: "Mở website đã xuất bản",
              icon: "fa-arrow-up-right-from-square",
              className: "border-emerald-200 text-emerald-600 hover:bg-emerald-50",
            })
          : "";

        return `
          <tr class="hover:bg-slate-50/80 transition-colors">
            <td class="py-4 px-4 sm:px-6">
              <div class="flex items-center gap-3 min-w-0">
                <div class="w-10 h-10 rounded-xl bg-indigo-50 border border-indigo-100 text-indigo-600 flex items-center justify-center shrink-0">
                  <i class="fa-solid fa-laptop-code"></i>
                </div>
                <div class="min-w-0">
                  <div class="font-bold text-slate-900 truncate max-w-[280px]">${escapeHtml(projectName(project))}</div>
                  <div class="text-[11px] text-slate-400 mt-0.5">Tạo ${escapeHtml(formatDate(project.created_at))}</div>
                </div>
              </div>
            </td>
            <td class="py-4 px-4">${statusBadge(project.status)}</td>
            <td class="py-4 px-4">
              ${
                pagesUrl
                  ? `<a href="${escapeHtml(pagesUrl)}" target="_blank" rel="noopener noreferrer" class="text-xs font-mono text-indigo-600 hover:underline inline-flex items-center gap-1 max-w-[220px]">
                       <span class="truncate">${escapeHtml(pagesUrl.replace(/^https?:\/\//, ""))}</span>
                       <i class="fa-solid fa-arrow-up-right-from-square text-[9px] shrink-0"></i>
                     </a>`
                  : '<span class="text-xs text-slate-400">Chưa xuất bản</span>'
              }
            </td>
            <td class="py-4 px-4 text-right pr-6">
              <div class="flex items-center justify-end gap-1.5">
                ${openAction}
                ${actionButton({ href: `project-detail.html?id=${encodeURIComponent(project.id)}`, title: "Chi tiết", icon: "fa-circle-info", className: "border-slate-200 text-slate-500 hover:text-indigo-600 hover:border-indigo-200 hover:bg-indigo-50/50" })}
                ${actionButton({ href: previewHref, title: "Xem trước", icon: "fa-eye", className: "border-slate-200 text-slate-500 hover:text-indigo-600 hover:border-indigo-200 hover:bg-indigo-50/50" })}
                ${actionButton({ href: editHref, title: "Chỉnh sửa", icon: "fa-pen-to-square", className: "border-slate-200 text-slate-500 hover:text-indigo-600 hover:border-indigo-200 hover:bg-indigo-50/50" })}
                ${actionButton({ href: deployHref, title: "Xuất bản lên GitHub Pages", icon: "fa-cloud-arrow-up", className: "border-indigo-200 text-indigo-600 hover:bg-indigo-50" })}
                ${actionButton({ onClick: "delete", title: "Xóa dự án", icon: "fa-trash-can", className: "border-rose-200 text-rose-500 hover:bg-rose-50" })}
              </div>
            </td>
          </tr>
        `;
      })
      .join("");

    container.innerHTML = `
      <div class="overflow-x-auto custom-scrollbar">
        <table class="w-full text-sm text-left border-collapse">
          <thead>
            <tr class="border-b border-slate-200 bg-slate-50/70 text-slate-500 text-[11px] font-bold uppercase tracking-wider">
              <th class="py-3.5 px-4 sm:px-6">Dự án</th>
              <th class="py-3.5 px-4">Trạng thái</th>
              <th class="py-3.5 px-4">GitHub Pages</th>
              <th class="py-3.5 px-4 text-right pr-6">Thao tác</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100">${rows}</tbody>
        </table>
      </div>
    `;

    if (totalPages <= 1) {
      pagination?.classList.add("hidden");
    } else if (pagination) {
      pagination.classList.remove("hidden");
      const info = $("page-info");
      if (info) info.textContent = `Trang ${state.page} / ${totalPages}`;
      const prev = $("btn-prev");
      const next = $("btn-next");
      if (prev) prev.disabled = state.page <= 1;
      if (next) next.disabled = state.page >= totalPages;
    }
  }

  function showLoading() {
    const container = $("project-list");
    if (!container) return;
    container.innerHTML = `
      <div class="p-10 text-center">
        <i class="fa-solid fa-spinner fa-spin text-2xl text-indigo-400 mb-3"></i>
        <p class="text-sm text-slate-400 font-semibold">Đang tải danh sách dự án...</p>
      </div>
    `;
  }

  function showError(message) {
    const container = $("project-list");
    if (!container) return;
    container.innerHTML = `
      <div class="p-10 text-center">
        <div class="w-14 h-14 mx-auto rounded-2xl bg-rose-50 text-rose-500 flex items-center justify-center text-2xl mb-3">
          <i class="fa-solid fa-triangle-exclamation"></i>
        </div>
        <p class="text-sm font-bold text-rose-700">Không thể tải danh sách dự án</p>
        <p class="text-xs text-slate-500 mt-1" id="projects-error-message"></p>
        <button type="button" id="btn-retry-projects" class="inline-flex items-center gap-2 mt-4 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold transition">
          <i class="fa-solid fa-rotate-right"></i>
          <span>Thử lại</span>
        </button>
      </div>
    `;
    const messageEl = $("projects-error-message");
    if (messageEl) messageEl.textContent = message || "Vui lòng kiểm tra backend FastAPI.";
    $("btn-retry-projects")?.addEventListener("click", loadProjects);
    $("pagination")?.classList.add("hidden");
  }

  async function loadProjects() {
    showLoading();
    try {
      const response = await apiRequest("/projects?page=1&page_size=100");
      const data = response?.data;
      state.projects = Array.isArray(data) ? data : Array.isArray(data?.items) ? data.items : [];
      state.page = 1;
      render();
    } catch (error) {
      console.error("Lỗi tải danh sách dự án:", error);
      showError(error.message || "Vui lòng kiểm tra backend FastAPI.");
      window.showToast?.(error.message || "Không tải được danh sách dự án.", "error", "Lỗi dữ liệu");
    }
  }

  // ── Xóa dự án ─────────────────────────────────────────────────────
  function openDeleteModal(project) {
    state.deleteTarget = project;
    const nameEl = $("delete-project-name");
    if (nameEl) nameEl.textContent = projectName(project);
    $("delete-project-modal")?.classList.remove("hidden");
    $("delete-project-modal")?.classList.add("flex");
  }

  function closeDeleteModal() {
    if (state.deleting) return;
    $("delete-project-modal")?.classList.add("hidden");
    $("delete-project-modal")?.classList.remove("flex");
    state.deleteTarget = null;
  }

  function setDeleting(deleting) {
    state.deleting = deleting;
    const button = $("btn-confirm-delete-project");
    const spinner = $("delete-project-spinner");
    const icon = $("delete-project-icon");
    const label = $("delete-project-btn-text");
    if (button) button.disabled = deleting;
    spinner?.classList.toggle("hidden", !deleting);
    icon?.classList.toggle("hidden", deleting);
    if (label) label.textContent = deleting ? "Đang xóa..." : "Xóa vĩnh viễn";
  }

  async function confirmDelete() {
    const project = state.deleteTarget;
    if (!project || state.deleting) return;

    setDeleting(true);
    try {
      const response = await apiRequest(`/projects/${project.id}`, { method: "DELETE" });
      (response.warnings || []).forEach((warning) => {
        console.warn(warning);
        window.showToast?.(warning, "warning", "Cảnh báo");
      });
      window.showToast?.(
        response.message || "Đã xóa dự án thành công.",
        "success",
        "Đã xóa dự án"
      );
      setDeleting(false);
      closeDeleteModal();
      await loadProjects();
    } catch (error) {
      console.error("Lỗi xóa dự án:", error);
      window.showToast?.(error.message || "Không thể xóa dự án.", "error", "Xóa thất bại");
      setDeleting(false);
    }
  }

  function handleListClick(event) {
    const button = event.target.closest("button[data-action='delete']");
    if (!button) return;
    const row = button.closest("tr");
    const index = Array.from(row.parentElement.children).indexOf(row);
    const filtered = getFiltered();
    const start = (state.page - 1) * PAGE_SIZE;
    const project = filtered[start + index];
    if (project) openDeleteModal(project);
  }

  // ── Init ──────────────────────────────────────────────────────────
  document.addEventListener("DOMContentLoaded", () => {
    $("status-filters")?.addEventListener("click", (event) => {
      const btn = event.target.closest(".filter-btn");
      if (!btn) return;
      state.filter = btn.getAttribute("data-status") || "";
      state.page = 1;
      document.querySelectorAll(".filter-btn").forEach((item) => item.classList.remove("active"));
      btn.classList.add("active");
      render();
    });

    $("btn-prev")?.addEventListener("click", () => {
      if (state.page > 1) {
        state.page -= 1;
        render();
      }
    });

    $("btn-next")?.addEventListener("click", () => {
      const totalPages = Math.ceil(getFiltered().length / PAGE_SIZE);
      if (state.page < totalPages) {
        state.page += 1;
        render();
      }
    });

    $("project-list")?.addEventListener("click", handleListClick);
    $("btn-cancel-delete-project")?.addEventListener("click", closeDeleteModal);
    $("btn-confirm-delete-project")?.addEventListener("click", confirmDelete);

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeDeleteModal();
    });

    loadProjects();
  });
})();
