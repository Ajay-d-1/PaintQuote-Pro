/* ════════════════════════════════════════════════════════
   PaintQuote Pro — app.js
   Global JS: quote calculator, toast notifications,
   mobile menu, form helpers
   ════════════════════════════════════════════════════════ */

let currentQuote = null;

// ── Toast Notifications ───────────────────────────────────────

function showToast(message, type = "info", duration = 4000) {
    let container = document.getElementById("toast-container");
    if (!container) {
        container = document.createElement("div");
        container.id = "toast-container";
        container.className = "toast-container";
        document.body.appendChild(container);
    }

    const icons = { success: "✅", error: "❌", warning: "⚠️", info: "ℹ️" };
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `<span>${icons[type] || "ℹ️"}</span><span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add("hiding");
        setTimeout(() => toast.remove(), 300);
    }, duration);
}


// ── Mobile Menu ───────────────────────────────────────────────

function openMobileNav() {
    const nav = document.getElementById("mobile-nav");
    if (nav) nav.classList.add("open");
}

function closeMobileNav() {
    const nav = document.getElementById("mobile-nav");
    if (nav) nav.classList.remove("open");
}


// ── Room Management ───────────────────────────────────────────

function addRoom() {
    const container = document.getElementById("roomsContainer");
    if (!container) return;
    const div = document.createElement("div");
    div.className = "room-row";
    div.innerHTML = `
        <input type="text"   class="room-name"   placeholder="Room name">
        <input type="number" class="room-length"  placeholder="Length (ft)" min="1">
        <input type="number" class="room-width"   placeholder="Width (ft)"  min="1">
        <input type="number" class="room-height"  placeholder="Height (ft)" value="10" min="1">
        <button class="btn-remove" onclick="removeRoom(this)" title="Remove room">✕</button>
    `;
    container.appendChild(div);
    div.querySelector(".room-name").focus();
}

function removeRoom(btn) {
    const rows = document.querySelectorAll(".room-row");
    if (rows.length === 1) {
        showToast("You need at least one room.", "warning");
        return;
    }
    btn.parentElement.remove();
}


// ── Quote Calculator ──────────────────────────────────────────

function calculateQuote(event) {
    if (event) event.preventDefault();
    const clientNameEl = document.getElementById("clientName");
    const clientName   = clientNameEl?.value.trim();

    if (!clientName) {
        shakeElement("clientName");
        clientNameEl?.focus();
        showToast("Please enter the client name.", "warning");
        return;
    }

    const paintGrade = document.getElementById("paintGrade")?.value || "premium";

    const rooms = [];
    document.querySelectorAll(".room-row").forEach(row => {
        const name   = row.querySelector(".room-name")?.value   || "Room";
        const length = parseFloat(row.querySelector(".room-length")?.value)  || 0;
        const width  = parseFloat(row.querySelector(".room-width")?.value)   || 0;
        const height = parseFloat(row.querySelector(".room-height")?.value)  || 10;
        if (length > 0 && width > 0) {
            rooms.push({ name, length, width, height });
        }
    });

    if (rooms.length === 0) {
        showToast("Please add at least one room with dimensions.", "warning");
        return;
    }

    const extras = {
        putty:         document.getElementById("putty")?.checked        || false,
        primer:        document.getElementById("primer")?.checked       || false,
        molding:       document.getElementById("molding")?.checked      || false,
        false_ceiling: document.getElementById("falseCeiling")?.checked || false,
        molding_length: parseFloat(document.getElementById("moldingLengthInput")?.value) || 0
    };

    const btn = document.getElementById("calcBtn");
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span> Calculating…';
    }

    fetch("/api/calculate", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ client_name: clientName, paint_grade: paintGrade, rooms, extras })
    })
    .then(r => r.json())
    .then(data => {
        if (data.error) {
            showToast("Error: " + data.error, "error");
            return;
        }
        currentQuote = data;
        if (typeof savedQuoteId !== "undefined") savedQuoteId = data.id;
        displayResult(data);
        showToast("Quote calculated successfully!", "success");
    })
    .catch(err => {
        showToast("Failed to calculate quote: " + err.message, "error");
    })
    .finally(() => {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = "⚡ Calculate Quote";
        }
    });
}

function displayResult(data) {
    const card      = document.getElementById("resultCard");
    const resultDiv = document.getElementById("quoteResult");
    if (!card || !resultDiv) return;

    const gradeLabel = { economy: "Economy", premium: "Premium", luxury: "Luxury" };
    const gradeName  = gradeLabel[data.paint_grade] || data.paint_grade;

    let html = '<div class="quote-result">';

    // Area & Paint info rows
    html += `<div class="quote-result-item"><span>Total Paintable Area</span><span>${(data.total_area || 0).toFixed(0)} sq ft</span></div>`;
    html += `<div class="quote-result-item"><span>Paint Needed</span><span>${(data.paint_needed_liters || 0).toFixed(1)} litres</span></div>`;
    html += `<div class="quote-result-item"><span>Paint (${gradeName})</span><span>₹${(data.paint_cost || 0).toLocaleString("en-IN", {minimumFractionDigits: 2})}</span></div>`;
    html += `<div class="quote-result-item"><span>Labour</span><span>₹${(data.labor_cost || 0).toLocaleString("en-IN", {minimumFractionDigits: 2})}</span></div>`;

    if ((data.extras_cost || 0) > 0) {
        html += `<div class="quote-result-item"><span>Extras</span><span>₹${(data.extras_cost || 0).toLocaleString("en-IN", {minimumFractionDigits: 2})}</span></div>`;
    }

    const subtotal = data.subtotal || (data.total_cost / 1.18);
    const gst      = data.gst_cost || (data.total_cost - subtotal);

    html += `<div class="quote-result-item subtotal"><span>Subtotal</span><span>₹${subtotal.toLocaleString("en-IN", {minimumFractionDigits: 2})}</span></div>`;
    html += `<div class="quote-result-item gst-row"><span>GST (18%)</span><span>₹${gst.toLocaleString("en-IN", {minimumFractionDigits: 2})}</span></div>`;
    html += `<div class="quote-result-item total-row"><span>💰 Grand Total</span><span>₹${(data.total_cost || 0).toLocaleString("en-IN", {minimumFractionDigits: 2})}</span></div>`;
    html += "</div>";

    resultDiv.innerHTML = html;
    card.classList.remove("hidden");
    card.scrollIntoView({ behavior: "smooth", block: "start" });
}

function saveQuote() {
    if (!currentQuote) return;
    window.location.href = currentQuote.id
        ? `/quote/${currentQuote.id}`
        : "/dashboard";
}

function resetForm() {
    document.getElementById("clientName").value    = "";
    document.getElementById("paintGrade").value   = "premium";
    document.getElementById("roomsContainer").innerHTML = `
        <div class="room-row">
            <input type="text"   class="room-name"   placeholder="Room name" value="Living Room">
            <input type="number" class="room-length"  placeholder="Length (ft)" value="15">
            <input type="number" class="room-width"   placeholder="Width (ft)"  value="12">
            <input type="number" class="room-height"  placeholder="Height (ft)" value="10">
            <button class="btn-remove" onclick="removeRoom(this)" title="Remove room">✕</button>
        </div>
    `;
    document.querySelectorAll('.extras-grid input[type="checkbox"]').forEach(cb => cb.checked = false);
    const moldingDiv = document.getElementById("moldingLength");
    if (moldingDiv) moldingDiv.classList.add("hidden");
    const resultCard = document.getElementById("resultCard");
    if (resultCard) resultCard.classList.add("hidden");
    currentQuote = null;
    if (typeof savedQuoteId !== "undefined") savedQuoteId = null;
    window.scrollTo({ top: 0, behavior: "smooth" });
}


// ── Shake animation ───────────────────────────────────────────

function shakeElement(id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.style.animation = "none";
    el.offsetHeight; // reflow
    el.style.animation = "shake 0.4s ease";
    el.addEventListener("animationend", () => el.style.animation = "", { once: true });
}


// ── DOMContentLoaded init ─────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {

    // Molding length toggle
    const moldingCb = document.getElementById("molding");
    if (moldingCb) {
        moldingCb.addEventListener("change", function () {
            const div = document.getElementById("moldingLength");
            if (div) div.classList.toggle("hidden", !this.checked);
        });
    }

    // Chat input Enter key (works on any page with chatInput)
    const chatInput = document.getElementById("chatInput");
    if (chatInput && typeof quoteId !== "undefined") {
        chatInput.addEventListener("keypress", e => {
            if (e.key === "Enter") sendMessage(quoteId);
        });
    }

    // Auto-scroll chat to bottom
    const chatHistory = document.getElementById("chatHistory");
    if (chatHistory) {
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }
});


// ── Inject shake keyframe ─────────────────────────────────────

const _shakeStyle = document.createElement("style");
_shakeStyle.textContent = `
    @keyframes shake {
        0%, 100% { transform: translateX(0); }
        20%       { transform: translateX(-6px); }
        40%       { transform: translateX(6px); }
        60%       { transform: translateX(-4px); }
        80%       { transform: translateX(4px); }
    }
`;
document.head.appendChild(_shakeStyle);
