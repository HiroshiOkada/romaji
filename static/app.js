(() => {
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

  function setStatus(message, isError = false) {
    statusEl.textContent = message || "";
    statusEl.classList.toggle("error", Boolean(isError));
  }

  async function loadUiConfig() {
    const res = await fetch("/api/ui-config");
    if (!res.ok) return;
    const data = await res.json();
    if (typeof data.debounce_ms === "number") {
      debounceMs = data.debounce_ms;
    }
  }

  async function loadLogic() {
    const res = await fetch("/api/logic");
    if (!res.ok) return;
    const data = await res.json();
    lastLogicVersion = data.version_id || "";
    logicVersionEl.textContent = lastLogicVersion
      ? `現行ロジック: ${lastLogicVersion}`
      : "";
  }

  async function convertNow() {
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

  inputEl.addEventListener("input", () => {
    setStatus("入力中…");
    scheduleConvert();
  });

  confirmBtn.addEventListener("click", async () => {
    if (converting) return;
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
    if (converting) return;
    logicBtn.disabled = true;
    confirmBtn.disabled = true;
    setStatus("ロジック更新中…");
    try {
      const res = await fetch("/api/logic/update", { method: "POST" });
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

  Promise.all([loadUiConfig(), loadLogic()]).catch((err) => {
    setStatus(err.message || String(err), true);
  });
})();
