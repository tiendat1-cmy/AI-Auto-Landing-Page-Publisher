// Đổi thành URL Render khi deploy production
const API_BASE_URL = "http://127.0.0.1:8000";
const TOKEN_KEY = "lp_access_token";

function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
}

function removeToken() {
  localStorage.removeItem(TOKEN_KEY);
}

/**
 * Hàm gọi API dùng chung cho toàn bộ Frontend:
 * - Tự động đính kèm Header Authorization: Bearer <token>
 * - Tự động đăng xuất & chuyển về login.html nếu Backend trả về 401 (token sai/hết hạn)
 */
async function apiRequest(endpoint, options = {}) {
  const token = getToken();
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  const data = await response.json().catch(() => ({}));

  // Nếu gọi các API cần xác thực mà bị 401 -> xóa token và chuyển về trang đăng nhập
  if (response.status === 401 && !endpoint.includes("/auth/login")) {
    removeToken();
    window.location.href = "login.html";
    throw new Error("Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.");
  }

  if (!response.ok) {
    // Bóc tách message lỗi chuẩn từ FastAPI (hỗ trợ cả string lẫn object error.message)
    const errorMsg =
      data?.detail?.error?.message ||
      (typeof data?.detail === "string" ? data.detail : null) ||
      "Đã xảy ra lỗi kết nối máy chủ.";
    throw new Error(errorMsg);
  }

  return data;
}