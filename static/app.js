(() => {
  const loginView = document.getElementById("loginView");
  const loginForm = document.getElementById("loginForm");
  const loginUser = document.getElementById("loginUser");
  const loginPassword = document.getElementById("loginPassword");
  const loginSubmitBtn = document.getElementById("loginSubmitBtn");
  const loginError = document.getElementById("loginError");

  const userBar = document.getElementById("userBar");
  const currentUserEl = document.getElementById("currentUser");
  const logoutBtn = document.getElementById("logoutBtn");
  const appActions = document.getElementById("appActions");
  const guestNotice = document.getElementById("guestNotice");

  const mainPanes = document.getElementById("mainPanes");
  const mainFooter = document.getElementById("mainFooter");
  const inputEl = document.getElementById("input");
  const outputEl = document.getElementById("output");
  const statusEl = document.getElementById("status");
  const logicVersionEl = document.getElementById("logicVersion");
  const confirmBtn = document.getElementById("confirmBtn");
  const logicBtn = document.getElementById("logicBtn");

  let debounceMs = 800;
  let timer = null;
  let requestSeq = 0;
  let lastAutoOutput = "";
  let lastLogicVersion = "";
  let converting = false;
  let currentUser = null; // { username: string, role: string }

  function setStatus(message, isError = false) {
    statusEl.textContent = message || "";
    statusEl.classList.toggle("error", Boolean(isError));
  }

  function showLoginView(errorMessage = "") {
    currentUser = null;
    loginView.hidden = false;
    userBar.hidden = true;
    appActions.hidden = true;
    mainPanes.hidden = true;
    mainFooter.hidden = true;
    loginPassword.value = "";
    if (errorMessage) {
      loginError.textContent = errorMessage;
      loginError.hidden = false;
    } else {
      loginError.hidden = true;
    }
  }

  function showAppView(user) {
    currentUser = user;
    loginView.hidden = true;
    loginError.hidden = true;
    userBar.hidden = false;
    appActions.hidden = false;
    mainPanes.hidden = false;
    mainFooter.hidden = false;

    const roleName = user.role === "admin" ? "管理者" : "ゲスト";
    currentUserEl.textContent = `${user.username} (${roleName})`;

    if (user.role === "guest") {
      confirmBtn.hidden = true;
      logicBtn.hidden = true;
      guestNotice.hidden = false;
    } else {
      confirmBtn.hidden = false;
      logicBtn.hidden = false;
      guestNotice.hidden = true;
    }
  }

  async function checkAuth() {
    try {
      const res = await fetch("/api/auth/me");
      if (!res.ok) {
        showLoginView();
        return;
      }
      const data = await res.json();
      if (data.authenticated && data.username) {
        showAppView({ username: data.username, role: data.role });
        await Promise.all([loadUiConfig(), loadLogic()]);
      } else {
        showLoginView();
      }
    } catch (err) {
      showLoginView();
    }
  }

  async function loadUiConfig() {
    const res = await fetch("/api/ui-config");
    if (res.status === 401) {
      showLoginView("セッションが切れました。再ログインしてください。");
      return;
    }
    if (!res.ok) return;
    const data = await res.json();
    if (typeof data.debounce_ms === "number") {
      debounceMs = data.debounce_ms;
    }
  }

  async function loadLogic() {
    const res = await fetch("/api/logic");
    if (res.status === 401) {
      showLoginView("セッションが切れました。再ログインしてください。");
      return;
    }
    if (!res.ok) return;
    const data = await res.json();
    lastLogicVersion = data.version_id || "";
    logicVersionEl.textContent = lastLogicVersion
      ? `現行ロジック: ${lastLogicVersion}`
      : "";
  }

  async function handleLogin(e) {
    e.preventDefault();
    loginError.hidden = true;
    loginSubmitBtn.disabled = true;
    loginSubmitBtn.textContent = "ログイン中…";

    const username = loginUser.value;
    const password = loginPassword.value;

    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || "ログインに失敗しました");
      }
      showAppView({ username: data.username, role: data.role });
      await Promise.all([loadUiConfig(), loadLogic()]);
    } catch (err) {
      loginError.textContent = err.message || "ログインに失敗しました";
      loginError.hidden = false;
    } finally {
      loginSubmitBtn.disabled = false;
      loginSubmitBtn.textContent = "ログイン";
    }
  }

  async function handleLogout() {
    try {
      await fetch("/api/auth/logout", { method: "POST" });
    } catch (err) {
      // 無視
    }
    inputEl.value = "";
    outputEl.value = "";
    lastAutoOutput = "";
    showLoginView();
  }

  async function convertNow() {
    if (!currentUser) return;
    const text = inputEl.value;
    if (!text.trim()) {
      outputEl.value = "";
      lastAutoOutput = "";
      setStatus("");
      return;
    }

    const seq = ++requestSeq;
    converting = true;
    setStatus("変換中…");
    confirmBtn.disabled = true;
    logicBtn.disabled = true;

    try {
      const res = await fetch("/api/convert", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (res.status === 401) {
        showLoginView("セッションが切れました。再ログインしてください。");
        return;
      }
      const data = await res.json().catch(() => ({}));
      if (seq !== requestSeq) return;
      if (!res.ok) {
        throw new Error(data.detail || `変換に失敗しました (${res.status})`);
      }
      outputEl.value = data.output || "";
      lastAutoOutput = data.output || "";
      lastLogicVersion = data.logic_version_id || lastLogicVersion;
      logicVersionEl.textContent = lastLogicVersion
        ? `現行ロジック: ${lastLogicVersion}`
        : "";
      setStatus("変換完了");
    } catch (err) {
      if (seq !== requestSeq) return;
      setStatus(err.message || String(err), true);
    } finally {
      if (seq === requestSeq) {
        converting = false;
        confirmBtn.disabled = false;
        logicBtn.disabled = false;
      }
    }
  }

  function scheduleConvert() {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => {
      convertNow();
    }, debounceMs);
  }

  loginForm.addEventListener("submit", handleLogin);
  logoutBtn.addEventListener("click", handleLogout);

  inputEl.addEventListener("input", () => {
    setStatus("入力中…");
    scheduleConvert();
  });

  confirmBtn.addEventListener("click", async () => {
    if (converting || !currentUser || currentUser.role !== "admin") return;
    const inputText = inputEl.value;
    const confirmed = outputEl.value;
    if (!inputText.trim() || !confirmed.trim()) {
      setStatus("入力と変換結果の両方が必要です", true);
      return;
    }
    confirmBtn.disabled = true;
    setStatus("保存中…");
    try {
      const res = await fetch("/api/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          input_text: inputText,
          auto_output: lastAutoOutput,
          confirmed_output: confirmed,
        }),
      });
      if (res.status === 401) {
        showLoginView("セッションが切れました。再ログインしてください。");
        return;
      }
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || `保存に失敗しました (${res.status})`);
      }
      setStatus(`保存しました (${data.id.slice(0, 8)}…)`);
    } catch (err) {
      setStatus(err.message || String(err), true);
    } finally {
      confirmBtn.disabled = false;
    }
  });

  logicBtn.addEventListener("click", async () => {
    if (converting || !currentUser || currentUser.role !== "admin") return;
    logicBtn.disabled = true;
    confirmBtn.disabled = true;
    setStatus("ロジック更新中…");
    try {
      const res = await fetch("/api/logic/update", { method: "POST" });
      if (res.status === 401) {
        showLoginView("セッションが切れました。再ログインしてください。");
        return;
      }
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || `更新に失敗しました (${res.status})`);
      }
      lastLogicVersion = data.version_id || "";
      logicVersionEl.textContent = lastLogicVersion
        ? `現行ロジック: ${lastLogicVersion}`
        : "";
      setStatus(`ロジック更新完了（例 ${data.example_count} 件）`);
    } catch (err) {
      setStatus(err.message || String(err), true);
    } finally {
      logicBtn.disabled = false;
      confirmBtn.disabled = false;
    }
  });

  checkAuth();
})();
