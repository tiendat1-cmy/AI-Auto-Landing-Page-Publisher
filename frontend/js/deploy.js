/**
 * Trang tiến trình xuất bản Landing Page.
 *
 * Luồng thật:
 *   1. GET  /projects/{id}         – lấy tên dự án để hiển thị.
 *   2. POST /projects/{id}/deploy  – render, tạo repo, push GitHub, bật Pages.
 *
 * Progress bar chỉ là mô phỏng thời gian chờ; trạng thái thành công/thất bại
 * hoàn toàn phụ thuộc vào response thật của backend (không còn fallback giả).
 */
(function () {
  "use strict";

  const TOTAL_STEPS = 4;
  const STEP_PROGRESS = [18, 38, 62, 84];

  const state = {
    projectId: null,
    projectName: "",
    deploying: false,
    elapsed: 0,
    currentStep: 1,
    elapsedTimer: null,
    progressTimer: null,
    stepTimers: [],
  };

  const $ = (id) => document.getElementById(id);

  function escapeHtml(value) {
    const div = document.createElement("div");
    div.appendChild(document.createTextNode(value === null || value === undefined ? "" : String(value)));
    return div.innerHTML;
  }

  function notify(message, type = "info", title = "") {
    if (typeof window.showToast === "function") {
      window.showToast(message, type, title);
      return;
    }
    const palette = {
      success: "bg-emerald-600 text-white",
      error: "bg-rose-600 text-white",
      warning: "bg-amber-500 text-white",
      info: "bg-slate-800 text-white",
    };
    const toast = document.createElement("div");
    toast.className = `fixed bottom-5 right-5 z-50 max-w-sm px-4 py-3 rounded-xl shadow-lg text-xs font-semibold ${palette[type] || palette.info}`;
    toast.textContent = title ? `${title}: ${message}` : message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3500);
  }

  function getProjectIdFromUrl() {
    const params = new URLSearchParams(window.location.search);
    return params.get("project_id") || params.get("id") || "";
  }

  function updateProgressUI(percent, labelText) {
    const bar = $("progress-bar");
    const percentEl = $("progress-percent");
    const labelEl = $("progress-label");
    if (bar) bar.style.width = `${Math.max(0, Math.min(100, percent))}%`;
    if (percentEl) percentEl.textContent = `${Math.round(percent)}%`;
    if (labelEl && labelText) labelEl.textContent = labelText;
  }

  function setStepState(stepNumber, stepState) {
    const stepEl = $(`step-${stepNumber}`);
    if (!stepEl) return;
    const badge = stepEl.querySelector(".step-badge");
    const statusText = stepEl.querySelector(".step-status");

    stepEl.classList.remove(
      "border-indigo-200", "bg-indigo-50/40",
      "border-emerald-200", "bg-emerald-50/40",
      "border-rose-200", "bg-rose-50/40",
      "border-slate-200", "bg-slate-50/60", "opacity-65"
    );

    if (stepState === "active") {
      stepEl.classList.add("border-indigo-200", "bg-indigo-50/40");
      if (badge) {
        badge.className = "step-badge w-8 h-8 rounded-full bg-indigo-600 text-white flex items-center justify-center text-sm font-bold";
        badge.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
      }
      if (statusText) {
        statusText.className = "step-status text-xs font-semibold text-indigo-600";
        statusText.textContent = "Đang chạy";
      }
    } else if (stepState === "done") {
      stepEl.classList.add("border-emerald-200", "bg-emerald-50/40");
      if (badge) {
        badge.className = "step-badge w-8 h-8 rounded-full bg-emerald-600 text-white flex items-center justify-center text-sm font-bold";
        badge.innerHTML = '<i class="fa-solid fa-check"></i>';
      }
      if (statusText) {
        statusText.className = "step-status text-xs font-semibold text-emerald-600";
        statusText.textContent = "Hoàn tất";
      }
    } else if (stepState === "error") {
      stepEl.classList.add("border-rose-200", "bg-rose-50/40");
      if (badge) {
        badge.className = "step-badge w-8 h-8 rounded-full bg-rose-600 text-white flex items-center justify-center text-sm font-bold";
        badge.innerHTML = '<i class="fa-solid fa-xmark"></i>';
      }
      if (statusText) {
        statusText.className = "step-status text-xs font-semibold text-rose-600";
        statusText.textContent = "Thất bại";
      }
    } else {
      stepEl.classList.add("border-slate-200", "bg-slate-50/60", "opacity-65");
      if (badge) {
        badge.className = "step-badge w-8 h-8 rounded-full bg-slate-200 text-slate-600 flex items-center justify-center text-sm font-bold";
        badge.textContent = String(stepNumber);
      }
      if (statusText) {
        statusText.className = "step-status text-xs font-medium text-slate-400";
        statusText.textContent = "Chờ xử lý";
      }
    }
  }

  function setElapsed(seconds) {
    const timerEl = $("countdown-timer");
    if (timerEl) timerEl.textContent = String(seconds);
  }

  function scheduleStep(callback, delay) {
    const timer = setTimeout(callback, delay);
    state.stepTimers.push(timer);
  }

  function startProgressSimulation() {
    stopTimers();
    state.elapsed = 0;
    state.currentStep = 1;
    setElapsed(0);
    updateProgressUI(8, "Đang khởi tạo quy trình xuất bản...");
    setStepState(1, "active");
    for (let i = 2; i <= TOTAL_STEPS; i++) setStepState(i, "pending");

    state.elapsedTimer = setInterval(() => {
      state.elapsed += 1;
      setElapsed(state.elapsed);
    }, 1000);

    state.progressTimer = setInterval(() => {
      const bar = $("progress-bar");
      const current = parseFloat((bar?.style.width || "8").replace("%", "")) || 8;
      if (current < 92) updateProgressUI(current + 1);
    }, 1800);

    scheduleStep(() => {
      if (state.currentStep !== 1) return;
      setStepState(1, "done");
      setStepState(2, "active");
      state.currentStep = 2;
      updateProgressUI(STEP_PROGRESS[1], "Đang tạo kho lưu trữ GitHub Repository...");
    }, 5000);

    scheduleStep(() => {
      if (state.currentStep !== 2) return;
      setStepState(2, "done");
      setStepState(3, "active");
      state.currentStep = 3;
      updateProgressUI(STEP_PROGRESS[2], "Đang đẩy mã nguồn & tài nguyên lên GitHub...");
    }, 12000);

    scheduleStep(() => {
      if (state.currentStep !== 3) return;
      setStepState(3, "done");
      setStepState(4, "active");
      state.currentStep = 4;
      updateProgressUI(STEP_PROGRESS[3], "Đang build trang & kích hoạt GitHub Pages...");
    }, 22000);
  }

  function stopTimers() {
    clearInterval(state.elapsedTimer);
    clearInterval(state.progressTimer);
    state.stepTimers.forEach((timer) => clearTimeout(timer));
    state.elapsedTimer = null;
    state.progressTimer = null;
    state.stepTimers = [];
  }

  function showResultPanels({ success, error }) {
    $("result-box")?.classList.remove("hidden");
    $("success-panel")?.classList.toggle("hidden", !success);
    $("error-panel")?.classList.toggle("hidden", !error);
    $("retry-btn")?.classList.toggle("hidden", !error);
    $("visit-site-btn")?.classList.toggle("hidden", !success);
    $("view-deployments-btn")?.classList.toggle("hidden", !success && !error);
  }

  function handleDeploySuccess(pagesUrl, deployData = {}) {
    stopTimers();
    for (let i = 1; i <= TOTAL_STEPS; i++) setStepState(i, "done");
    updateProgressUI(100, "Hoàn tất xuất bản 100%");

    const iconWrap = $("status-icon-wrapper");
    const mainIcon = $("status-main-icon");
    if (iconWrap) iconWrap.className = "w-16 h-16 rounded-2xl bg-emerald-100 text-emerald-600 flex items-center justify-center text-2xl mb-4";
    if (mainIcon) mainIcon.className = "fa-solid fa-circle-check";

    const badge = $("countdown-badge");
    if (badge) {
      badge.className = "inline-flex items-center gap-2 px-3.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 mb-3";
      badge.innerHTML = `<i class="fa-solid fa-bolt"></i><span>Hoàn tất trong ${state.elapsed} giây</span>`;
    }

    const title = $("deploy-title");
    const subtitle = $("deploy-subtitle");
    if (title) title.textContent = "Landing Page đã lên sóng!";
    if (subtitle) subtitle.textContent = "Bạn có thể truy cập và chia sẻ đường dẫn công khai ngay bây giờ.";

    const urlInput = $("published-url-input");
    const visitBtn = $("visit-site-btn");
    const historyBtn = $("view-deployments-btn");
    if (urlInput) urlInput.value = pagesUrl;
    if (visitBtn) visitBtn.href = pagesUrl;
    if (historyBtn) {
      historyBtn.href = `deployments.html${state.projectId ? `?project_id=${encodeURIComponent(state.projectId)}` : ""}`;
    }

    const commitSha = String(deployData.commit_sha || "").trim();
    const repoUrl = String(deployData.repo_url || "").trim();
    const metaRow = $("deploy-meta-row");
    const commitWrap = $("deploy-commit-wrap");
    const commitEl = $("deploy-commit-sha");
    const repoLink = $("deploy-repo-link");
    if (commitSha && commitWrap && commitEl) {
      commitEl.textContent = commitSha.slice(0, 7);
      commitWrap.title = commitSha;
      commitWrap.classList.remove("hidden");
    }
    if (repoUrl && repoLink) {
      repoLink.href = repoUrl;
      repoLink.classList.remove("hidden");
    }
    if (metaRow && (commitSha || repoUrl)) {
      metaRow.classList.remove("hidden");
    }

    showResultPanels({ success: true, error: false });
    try {
      sessionStorage.setItem(
        "flash_toast",
        JSON.stringify({
          type: "success",
          title: "Xuất bản thành công",
          message: "Landing Page đã được deploy lên GitHub Pages.",
        })
      );
    } catch (error) {
      /* sessionStorage có thể bị chặn – không ảnh hưởng luồng chính */
    }
    notify("Xuất bản Landing Page thành công!", "success", "Hoàn tất");
  }

  function handleDeployError(message) {
    stopTimers();
    setStepState(state.currentStep || 1, "error");
    const percentText = $("progress-percent")?.textContent || "0%";
    updateProgressUI(parseFloat(percentText.replace("%", "")) || 20, "Quá trình xuất bản bị gián đoạn");

    const iconWrap = $("status-icon-wrapper");
    const mainIcon = $("status-main-icon");
    if (iconWrap) iconWrap.className = "w-16 h-16 rounded-2xl bg-rose-100 text-rose-600 flex items-center justify-center text-2xl mb-4";
    if (mainIcon) mainIcon.className = "fa-solid fa-triangle-exclamation";

    const badge = $("countdown-badge");
    if (badge) {
      badge.className = "inline-flex items-center gap-2 px-3.5 py-1 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 mb-3";
      badge.innerHTML = '<i class="fa-solid fa-circle-xmark"></i><span>Deploy thất bại</span>';
    }

    const title = $("deploy-title");
    if (title) title.textContent = "Không thể xuất bản Landing Page";

    // Phân loại lỗi GitHub để hiển thị hướng dẫn thân thiện
    const errorText = $("error-message-text");
    const lowerMsg = (message || "").toLowerCase();

    let friendlyHint = "";
    if (lowerMsg.includes("rate limit") || lowerMsg.includes("giới hạn tốc độ")) {
      friendlyHint = '<p class="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-xl px-3 py-2 mt-2 flex items-start gap-2"><i class="fa-solid fa-clock mt-0.5 shrink-0"></i><span>GitHub API đang bị giới hạn tốc độ. Vui lòng chờ vài phút rồi thử lại.</span></p>';
    } else if (lowerMsg.includes("đã tồn tại") || lowerMsg.includes("already exists") || lowerMsg.includes("trùng")) {
      friendlyHint = '<p class="text-xs text-blue-700 bg-blue-50 border border-blue-200 rounded-xl px-3 py-2 mt-2 flex items-start gap-2"><i class="fa-solid fa-copy mt-0.5 shrink-0"></i><span>Tên repo đã tồn tại trên GitHub. Hãy đổi tên chiến dịch rồi deploy lại.</span></p>';
    } else if (lowerMsg.includes("token") || lowerMsg.includes("hết hạn") || lowerMsg.includes("không hợp lệ")) {
      friendlyHint = '<p class="text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-xl px-3 py-2 mt-2 flex items-start gap-2"><i class="fa-solid fa-key mt-0.5 shrink-0"></i><span>GitHub Token không hợp lệ hoặc đã hết hạn. Vui lòng cập nhật GITHUB_TOKEN trong file .env của backend.</span></p>';
    }

    if (errorText) {
      errorText.innerHTML = `<span>${escapeHtml(message || "")}</span>${friendlyHint}`;
    }

    showResultPanels({ success: false, error: true });
    notify(message, "error", "Deploy thất bại");
  }

  function resetDeployUI() {
    const iconWrap = $("status-icon-wrapper");
    const mainIcon = $("status-main-icon");
    if (iconWrap) iconWrap.className = "w-16 h-16 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center text-2xl mb-4 shadow-inner";
    if (mainIcon) mainIcon.className = "fa-solid fa-cloud-arrow-up fa-bounce";

    const badge = $("countdown-badge");
    if (badge) {
      badge.className = "inline-flex items-center gap-2 px-3.5 py-1 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 mb-3";
      badge.innerHTML = '<i class="fa-regular fa-clock"></i><span>Đã xử lý: <strong id="countdown-timer">0</strong> giây</span>';
    }

    const title = $("deploy-title");
    if (title) title.textContent = "Đang xuất bản Landing Page của bạn...";
    const subtitle = $("deploy-subtitle");
    if (subtitle) subtitle.textContent = "Hệ thống đang render HTML, tạo GitHub Repository và kích hoạt GitHub Pages. Vui lòng không đóng trình duyệt.";

    showResultPanels({ success: false, error: false });
    $("result-box")?.classList.add("hidden");
  }

  async function loadProjectInfo() {
    if (!state.projectId) return;
    try {
      const response = await apiRequest(`/projects/${state.projectId}`);
      const project = response?.data || {};
      state.projectName = project.product_name || project.campaign_name || "";
      if (state.projectName) {
        const title = $("deploy-title");
        if (title) title.textContent = `Đang xuất bản "${state.projectName}"...`;
      }
    } catch (error) {
      // Không chặn deploy nếu chỉ lỗi phần hiển thị tên dự án.
      console.debug("Không tải được thông tin dự án:", error.message);
    }
  }

  async function triggerDeploy() {
    if (state.deploying) return;

    if (!getToken()) {
      const prefix = window.location.pathname.includes("/pages/") ? "../" : "";
      window.location.href = `${prefix}login.html`;
      return;
    }

    if (!state.projectId) {
      handleDeployError("Thiếu mã dự án (?id=...). Vui lòng mở trang xuất bản từ danh sách dự án.");
      return;
    }

    state.deploying = true;
    resetDeployUI();
    startProgressSimulation();
    loadProjectInfo();

    try {
      const result = await apiRequest(`/projects/${state.projectId}/deploy`, {
        method: "POST",
      });

      const deployData = result?.data || result || {};
      const pagesUrl =
        deployData.github_pages_url ||
        "";

      if (!pagesUrl) {
        throw new Error("Backend không trả về đường dẫn GitHub Pages sau khi deploy.");
      }

      handleDeploySuccess(pagesUrl, deployData);
    } catch (error) {
      console.error("Lỗi deploy:", error);
      handleDeployError(error.message || "Máy chủ trả về lỗi khi xuất bản.");
    } finally {
      state.deploying = false;
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    state.projectId = getProjectIdFromUrl();

    const editBtn = $("back-edit-btn");
    if (editBtn && state.projectId) {
      editBtn.href = `edit-project.html?id=${encodeURIComponent(state.projectId)}`;
    }
    const historyBtn = $("view-deployments-btn");
    if (historyBtn && state.projectId) {
      historyBtn.href = `deployments.html?project_id=${encodeURIComponent(state.projectId)}`;
    }

    const copyBtn = $("copy-url-btn");
    if (copyBtn) {
      copyBtn.addEventListener("click", async () => {
        const input = $("published-url-input");
        if (!input || !input.value) return;
        try {
          await navigator.clipboard.writeText(input.value);
          copyBtn.innerHTML = '<i class="fa-solid fa-check mr-1"></i>Đã chép';
          setTimeout(() => {
            copyBtn.innerHTML = '<i class="fa-regular fa-copy mr-1"></i>Sao chép';
          }, 2000);
        } catch (error) {
          notify("Trình duyệt không cho phép sao chép tự động.", "warning", "Sao chép");
        }
      });
    }

    $("retry-btn")?.addEventListener("click", triggerDeploy);
    triggerDeploy();
  });
})();
