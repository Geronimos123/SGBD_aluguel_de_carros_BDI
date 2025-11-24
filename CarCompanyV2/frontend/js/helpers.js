// js/helpers.js
const API_URL = "http://127.0.0.1:5000";

async function apiFetch(path, options = {}) {
    const url = `${API_URL}${path}`;
    const opts = {
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        ...options
    };
    if (opts.body && typeof opts.body !== "string") {
        opts.body = JSON.stringify(opts.body);
    }
    const res = await fetch(url, opts);
    let payload = null;
    try {
        payload = await res.json();
    } catch (e) {
        // sem json no corpo
    }
    if (!res.ok) {
        const errMsg = (payload && (payload.erro || payload.message)) || `HTTP ${res.status}`;
        const err = new Error(errMsg);
        err.status = res.status;
        err.body = payload;
        throw err;
    }
    return payload;
}

function qparam(name) {
    const params = new URLSearchParams(window.location.search);
    return params.get(name);
}

function formatCurrency(v) {
    return Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

// safe setText helper
function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text ?? "";
}

export { apiFetch, qparam, formatCurrency, setText };
