// Nếu đã đăng nhập (có token) mà vẫn mở login.html -> chuyển thẳng sang index.html
if (window.location.pathname.endsWith("login.html") && getToken()) {
  window.location.href = "index.html";
}

function switchAuthTab(tab) {
  clearErrors();
  dismissToast();
  const btnLogin = document.getElementById("tabBtnLogin");
  const btnRegister = document.getElementById("tabBtnRegister");
  const tabContentLogin = document.getElementById("tabContentLogin");
  const tabContentRegister = document.getElementById("tabContentRegister");

  if (tab === "login") {
    tabContentLogin.classList.remove("hidden");
    tabContentRegister.classList.add("hidden");
    btnLogin.className = "flex-1 py-2.5 px-4 rounded-xl text-xs font-bold transition-all shadow-sm bg-white text-indigo-600";
    btnRegister.className = "flex-1 py-2.5 px-4 rounded-xl text-xs font-bold transition-all text-slate-500 hover:text-slate-800";
  } else {
    tabContentLogin.classList.add("hidden");
    tabContentRegister.classList.remove("hidden");
    btnRegister.className = "flex-1 py-2.5 px-4 rounded-xl text-xs font-bold transition-all shadow-sm bg-white text-indigo-600";
    btnLogin.className = "flex-1 py-2.5 px-4 rounded-xl text-xs font-bold transition-all text-slate-500 hover:text-slate-800";
  }
}

function togglePasswordVisibility(inputId, btn) {
  const input = document.getElementById(inputId);
  const icon = btn.querySelector("i");
  if (input.type === "password") {
    input.type = "text";
    icon.className = "fa-regular fa-eye-slash text-indigo-600 text-xs";
  } else {
    input.type = "password";
    icon.className = "fa-regular fa-eye text-slate-400 text-xs";
  }
}

function checkPasswordStrength(password) {
  const bar = document.getElementById("pwdStrengthBar");
  const label = document.getElementById("pwdStrengthLabel");
  if (!bar || !label) return;

  if (!password) {
    bar.style.width = "0%";
    bar.className = "h-full bg-slate-300 w-0";
    label.textContent = "Độ bảo mật";
    label.className = "text-[10px] text-slate-400 font-semibold";
    return;
  }

  let score = 0;
  if (password.length >= 8) score++;
  if (/[A-Z]/.test(password)) score++;
  if (/[0-9]/.test(password)) score++;
  if (/[^A-Za-z0-9]/.test(password)) score++;

  if (score <= 1) {
    bar.style.width = "25%";
    bar.className = "h-full bg-rose-500";
    label.textContent = "Yếu";
    label.className = "text-[10px] text-rose-500 font-bold";
  } else if (score <= 3) {
    bar.style.width = "65%";
    bar.className = "h-full bg-amber-500";
    label.textContent = "Trung bình";
    label.className = "text-[10px] text-amber-500 font-bold";
  } else {
    bar.style.width = "100%";
    bar.className = "h-full bg-emerald-500";
    label.textContent = "Rất mạnh";
    label.className = "text-[10px] text-emerald-600 font-bold";
  }
}

let toastTimeout;
function showToast(type, title, message) {
  const toast = document.getElementById("globalToast");
  const icon = document.getElementById("toastIcon");
  const titleEl = document.getElementById("toastTitle");
  const msgEl = document.getElementById("toastMessage");
  if (!toast) return;

  clearTimeout(toastTimeout);
  toast.className = "mb-6 p-4 rounded-xl border text-sm flex items-start gap-3 fade-in shadow-md transition-all";

  if (type === "success") {
    toast.classList.add("bg-emerald-50", "border-emerald-200", "text-emerald-800");
    icon.className = "fa-solid fa-circle-check mt-0.5 text-base text-emerald-600";
  } else if (type === "error") {
    toast.classList.add("bg-rose-50", "border-rose-200", "text-rose-800");
    icon.className = "fa-solid fa-circle-xmark mt-0.5 text-base text-rose-600";
  } else {
    toast.classList.add("bg-indigo-50", "border-indigo-200", "text-indigo-800");
    icon.className = "fa-solid fa-circle-info mt-0.5 text-base text-indigo-600";
  }

  titleEl.textContent = title;
  msgEl.textContent = message;
  toast.classList.remove("hidden");

  toastTimeout = setTimeout(dismissToast, 5000);
}

function dismissToast() {
  const toast = document.getElementById("globalToast");
  if (toast) toast.classList.add("hidden");
}

function notifyNotice(msg) {
  showToast("info", "Thông Báo", msg);
}

function clearErrors() {
  document.querySelectorAll('[id^="err"]').forEach((el) => {
    el.textContent = "";
    el.classList.add("hidden");
  });
  document.querySelectorAll("input").forEach((input) => {
    input.classList.remove("input-error");
  });
}

function setFieldError(fieldId, errorId, message) {
  const input = document.getElementById(fieldId);
  const err = document.getElementById(errorId);
  if (input) input.classList.add("input-error");
  if (err) {
    err.textContent = message;
    err.classList.remove("hidden");
  }
}

function validateEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}



// 1. XỬ LÝ ĐĂNG NHẬP -> GỌI POST /auth/login
async function handleLoginSubmit(e) {
  e.preventDefault();
  clearErrors();

  const email = document.getElementById("loginIdentifier").value.trim();
  const password = document.getElementById("loginPassword").value;

  let hasError = false;
  if (!email) {
    setFieldError("loginIdentifier", "errLoginIdentifier", "Vui lòng nhập địa chỉ email.");
    hasError = true;
  } else if (!validateEmail(email)) {
    setFieldError("loginIdentifier", "errLoginIdentifier", "Địa chỉ email không đúng định dạng.");
    hasError = true;
  }

  if (!password) {
    setFieldError("loginPassword", "errLoginPassword", "Vui lòng nhập mật khẩu.");
    hasError = true;
  }
  if (hasError) return;

  const btn = document.getElementById("btnLoginSubmit");
  const btnText = document.getElementById("loginBtnText");
  const spinner = document.getElementById("loginSpinner");

  btn.disabled = true;
  btnText.textContent = "Đang xác thực...";
  spinner.classList.remove("hidden");

  try {
    const res = await apiRequest("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });

    const token = res?.data?.access_token;
    if (!token) throw new Error("Không nhận được JWT Token từ máy chủ.");

    // Lưu token vào localStorage & chuyển sang trang Dashboard (index.html)
    setToken(token);
    showToast("success", "Đăng nhập thành công", "Đang chuyển hướng vào bảng điều khiển...");
    setTimeout(() => {
      window.location.href = "index.html";
    }, 500);
  } catch (err) {
    showToast("error", "Đăng nhập thất bại", err.message);
    setFieldError("loginPassword", "errLoginPassword", err.message);
  } finally {
    btn.disabled = false;
    btnText.textContent = "Đăng nhập vào bảng điều khiển";
    spinner.classList.add("hidden");
  }
}

// 2. XỬ LÝ ĐĂNG KÝ -> GỌI POST /auth/register
async function handleRegisterSubmit(e) {
  e.preventDefault();
  clearErrors();

  const full_name = document.getElementById("regFullname").value.trim();
  const email = document.getElementById("regEmail").value.trim();
  const password = document.getElementById("regPassword").value;
  const confirmPassword = document.getElementById("regConfirmPassword").value;
  const terms = document.getElementById("regTerms").checked;

  let hasError = false;
  if (full_name.length < 2) {
    setFieldError("regFullname", "errRegFullname", "Họ và tên phải có tối thiểu 2 ký tự.");
    hasError = true;
  }
  if (!email) {
    setFieldError("regEmail", "errRegEmail", "Vui lòng nhập địa chỉ email.");
    hasError = true;
  } else if (!validateEmail(email)) {
    setFieldError("regEmail", "errRegEmail", "Địa chỉ email không đúng định dạng.");
    hasError = true;
  }
  if (password.length < 8) {
    setFieldError("regPassword", "errRegPassword", "Mật khẩu phải có tối thiểu 8 ký tự.");
    hasError = true;
  }
  if (password !== confirmPassword) {
    setFieldError("regConfirmPassword", "errRegConfirmPassword", "Mật khẩu xác nhận không khớp.");
    hasError = true;
  }
  if (!terms) {
    const errTerms = document.getElementById("errRegTerms");
    errTerms.textContent = "Bạn cần đồng ý với Điều khoản dịch vụ.";
    errTerms.classList.remove("hidden");
    hasError = true;
  }
  if (hasError) return;

  const btn = document.getElementById("btnRegSubmit");
  const btnText = document.getElementById("regBtnText");
  const spinner = document.getElementById("regSpinner");

  btn.disabled = true;
  btnText.textContent = "Đang tạo tài khoản...";
  spinner.classList.remove("hidden");

  try {
    await apiRequest("/auth/register", {
      method: "POST",
      body: JSON.stringify({ full_name, email, password }),
    });

    document.getElementById("formRegister").reset();
    switchAuthTab("login");
    document.getElementById("loginIdentifier").value = email;
    showToast("success", "Đăng ký thành công", "Tài khoản đã được tạo! Vui lòng đăng nhập.");
  } catch (err) {
    setFieldError("regEmail", "errRegEmail", err.message);
    showToast("error", "Đăng ký không thành công", err.message);
  } finally {
    btn.disabled = false;
    btnText.textContent = "Đăng ký tài khoản";
    spinner.classList.add("hidden");
  }
}

// 3. BẢO VỆ TRANG DASHBOARD (Chưa đăng nhập -> đá về login.html)
async function requireAuth() {
  const token = getToken();
  if (!token) {
    window.location.href = "login.html";
    return null;
  }

  try {
    // Gọi GET /auth/me (tự gắn Authorization: Bearer <token> qua apiRequest)
    const res = await apiRequest("/auth/me", { method: "GET" });
    return res.data;
  } catch (err) {
    removeToken();
    window.location.href = "login.html";
    return null;
  }
}

// 4. ĐĂNG XUẤT -> XÓA TOKEN & CHUYỂN VỀ TRANG ĐĂNG NHẬP
function handleLogout() {
  removeToken();
  window.location.href = "login.html";
}