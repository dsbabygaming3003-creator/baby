(function __Kauwa2FaFullScriptV18Guard(){
    if (window.__KAUWA_2FA_FULL_SCRIPT_V18_ACTIVE) return;
    window.__KAUWA_2FA_FULL_SCRIPT_V18_ACTIVE = true;

    // Restore app-level Mail/CSV state before any page-specific automation runs.
    // WebView site data may be cleared between Instagram and Accounts Center origins,
    // but this native backup is intentionally outside site storage.
    try {
        if (window.Android2FANative && typeof window.Android2FANative.getFloatingData === "function") {
            const raw = window.Android2FANative.getFloatingData();
            if (raw) {
                const saved = JSON.parse(raw);
                Object.keys(saved || {}).forEach(function(k) {
                    if (saved[k] !== null && saved[k] !== undefined) {
                        localStorage.setItem(k, String(saved[k]));
                    }
                });
            }
        }
    } catch (e) {}

/* ==========================================================================
   SECTION 0: EXTENSION BRIDGE FUNCTIONS (কুকিজ ও ক্যাশ হ্যান্ডলার)
========================================================================== */
function getExtensionCookies(callback) {
    if (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.sendMessage) {
        chrome.runtime.sendMessage({ action: "GET_COOKIES" }, (response) => {
            if (response && response.success && callback) {
                callback(response.cookies || []);
            }
        });
    }
}

function clearExtensionData(callback) {
    // 2Fa automatic cleanup must use the Android WebView profile clear so
    // HttpOnly Instagram session cookies are actually removed.
    // The native side preserves the 2Fa queue/password/state/CSV records.
    try {
        if (window.Android2FANative && typeof window.Android2FANative.clearBrowsingData === "function") {
            window.Android2FANative.clearBrowsingData();
            return true;
        }
    } catch (e) {}

    // Browser/extension fallback.
    try {
        if (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.sendMessage) {
            chrome.runtime.sendMessage({ action: "CLEAR_DATA" }, (response) => {
                if (response && response.success && callback) callback();
            });
            return true;
        }
    } catch (e) {}

    if (callback) callback();
    return false;
}


// ==UserScript==
// @name         Cookies Auto Final 🔥
// @namespace    shipon.instagram.emailautofill
// @version      3.4.0
// @description  Fills IG username/email & Password. Circular Draggable Gmail Floating Button.
// @match        https://www.instagram.com/*
// @match        *://accountscenter.instagram.com/*
// @match        *://accountscenter.meta.com/*
// @run-at       document-end
// @grant        none
// ==/UserScript==

(() => {
    "use strict";

    /* =========================================================
       UI PANEL & DRAGGABLE CIRCLE BUTTON SETUP (GMAIL LOGO)
    ========================================================= */
    function createUIPanel() {
        if (document.getElementById("shipon-ig-float-btn")) return;

        const floatBtn = document.createElement("div");
        floatBtn.id = "shipon-ig-float-btn";
        floatBtn.title = "IG Smart Autofill (টেনে যেকোনো জায়গায় নিতে পারবেন)";
        
        const savedPos = JSON.parse(localStorage.getItem("__shiponIG_Btn_Pos") || "null");
        const defaultLeft = "20px";
        const defaultTop = (window.innerHeight - 80) + "px";

        floatBtn.style.cssText = `
            position: fixed;
            left: ${savedPos ? savedPos.left : defaultLeft};
            top: ${savedPos ? savedPos.top : defaultTop};
            width: 48px;
            height: 48px;
            border-radius: 50%;
            background: #ffffff;
            border: 1px solid #dadce0;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.28);
            cursor: grab;
            z-index: 9999999;
            display: flex;
            align-items: center;
            justify-content: center;
            user-select: none;
            touch-action: none;
            transition: transform 0.1s ease;
        `;

        floatBtn.innerHTML = `
            <svg style="pointer-events: none;" width="26" height="26" viewBox="0 0 48 48">
                <path fill="#4caf50" d="M45,16.2l-5,2.75l-5,4.75L35,40h7c1.657,0,3-1.343,3-3V16.2z"></path>
                <path fill="#1e88e5" d="M3,16.2l3.614,1.71L13,23.7V40H6c-1.657,0-3-1.343-3-3V16.2z"></path>
                <polygon fill="#e53935" points="35,11.2 24,19.45 13,11.2 12,17 13,23.7 24,31.95 35,23.7 36,17"></polygon>
                <path fill="#c62828" d="M3,12.298V16.2l10,7.5V11.2L9.876,8.859C8.132,7.553,5.654,8.04,4.508,9.907L3,12.298z"></path>
                <path fill="#fbc02d" d="M45,12.298V16.2l-10,7.5V11.2l3.124-2.341c1.744-1.306,4.222-0.819,5.368,1.048L45,12.298z"></path>
            </svg>
        `;

        const panel = document.createElement("div");
        panel.id = "shipon-ig-panel";
        panel.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 310px;
            max-width: 90vw;
            background: #ffffff !important;
            border: 2px solid #dbdbdb;
            border-radius: 12px;
            padding: 14px 16px;
            z-index: 10000000;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            color: #000000 !important;
            display: none;
        `;

        panel.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #dbdbdb; padding-bottom: 8px; margin-bottom: 8px;">
                <div style="display: flex; align-items: center; gap: 6px;">
                    <span style="font-size: 14px; font-weight: bold; color: #000000 !important;">IG Smart Autofill</span>
                </div>
                <button id="shipon-close-btn" style="background: none; border: none; font-size: 18px; cursor: pointer; color: #555555 !important; font-weight: bold; padding: 0 4px; line-height: 1;">✕</button>
            </div>
            <div id="shipon-content">
                <label style="font-size: 12px; font-weight: bold; display: block; margin-bottom: 4px; color: #000000 !important;">Emails (One per line):</label>
                <textarea id="shipon-emails" placeholder="email1@domain.com&#10;email2@domain.com" style="width: 100%; height: 80px; margin-bottom: 8px; padding: 8px; box-sizing: border-box; font-size: 12px; border: 1px solid #777777; border-radius: 6px; resize: none; color: #000000 !important; background-color: #ffffff !important; font-weight: bold; outline: none;"></textarea>
                
                <label style="font-size: 12px; font-weight: bold; display: block; margin-bottom: 4px; color: #000000 !important;">Password:</label>
                <input type="text" id="shipon-password" placeholder="Your Password" style="width: 100%; margin-bottom: 10px; padding: 8px; box-sizing: border-box; font-size: 12px; border: 1px solid #777777; border-radius: 6px; color: #000000 !important; background-color: #ffffff !important; font-weight: bold; outline: none;" />
                
                <button id="shipon-save" style="width: 100%; background: #0095f6; color: white; border: none; padding: 8px; border-radius: 6px; cursor: pointer; font-weight: bold; font-size: 12px; margin-bottom: 6px;">Save & Start</button>
                <div style="display: flex; gap: 6px; margin-bottom: 6px;">
                    <button id="shipon-previous" style="flex: 1; background: #7c4dff; color: white; border: none; padding: 8px; border-radius: 6px; cursor: pointer; font-weight: bold; font-size: 11px;">Previous</button>
                    <button id="shipon-next" style="flex: 1; background: #ff9800; color: white; border: none; padding: 8px; border-radius: 6px; cursor: pointer; font-weight: bold; font-size: 11px;">Next</button>
                </div>
                <button id="shipon-autofill-toggle" style="width: 100%; background: #16a34a; color: white; border: none; padding: 8px; border-radius: 6px; cursor: pointer; font-weight: bold; font-size: 11px; margin-bottom: 6px;">ON</button>
                <div style="display: flex; gap: 6px;">
                    <button id="shipon-reset" style="flex: 1; background: #ed4956; color: white; border: none; padding: 8px; border-radius: 6px; cursor: pointer; font-weight: bold; font-size: 11px;">Reset Memory</button>
                    <button id="shipon-clear-box" style="flex: 1; background: #666666; color: white; border: none; padding: 8px; border-radius: 6px; cursor: pointer; font-weight: bold; font-size: 11px;">Clear Box</button>
                </div>
            </div>
        `;

        document.body.appendChild(floatBtn);
        document.body.appendChild(panel);

        const emailInput = document.getElementById("shipon-emails");
        const passInput = document.getElementById("shipon-password");
        const closeBtn = document.getElementById("shipon-close-btn");

        emailInput.value = localStorage.getItem("__shiponIG_UI_Emails") || "";
        passInput.value = localStorage.getItem("__shiponIG_UI_Password") || "";
        const autofillToggle = document.getElementById("shipon-autofill-toggle");
        let autofillEnabled = localStorage.getItem("__shiponIG_MailAutofillEnabled") !== "0";
        function refreshAutofillToggle() {
            if (!autofillToggle) return;
            autofillToggle.textContent = autofillEnabled ? "ON" : "OFF";
            autofillToggle.style.background = autofillEnabled ? "#16a34a" : "#dc2626";
        }
        refreshAutofillToggle();

        function togglePanel() {
            panel.style.display = (panel.style.display === "none" || panel.style.display === "") ? "block" : "none";
        }

        closeBtn.addEventListener("click", () => {
            panel.style.display = "none";
        });

        let isDragging = false;
        let startX = 0, startY = 0;
        let initialLeft = 0, initialTop = 0;
        let lastTouchTime = 0;

        function onPointerDown(e) {
            if (e.type === "mousedown" && Date.now() - lastTouchTime < 500) return;
            if (e.type === "touchstart") lastTouchTime = Date.now();

            isDragging = false;
            floatBtn.style.cursor = "grabbing";

            const clientX = e.touches ? e.touches[0].clientX : e.clientX;
            const clientY = e.touches ? e.touches[0].clientY : e.clientY;
            startX = clientX;
            startY = clientY;

            const rect = floatBtn.getBoundingClientRect();
            initialLeft = rect.left;
            initialTop = rect.top;

            const onPointerMove = (moveEvt) => {
                const curX = moveEvt.touches ? moveEvt.touches[0].clientX : moveEvt.clientX;
                const curY = moveEvt.touches ? moveEvt.touches[0].clientY : moveEvt.clientY;
                const dx = curX - startX;
                const dy = curY - startY;

                if (Math.hypot(dx, dy) > 10) {
                    isDragging = true;
                }

                if (isDragging) {
                    if (moveEvt.cancelable) moveEvt.preventDefault();

                    let newX = initialLeft + dx;
                    let newY = initialTop + dy;

                    newX = Math.max(5, Math.min(window.innerWidth - floatBtn.offsetWidth - 5, newX));
                    newY = Math.max(5, Math.min(window.innerHeight - floatBtn.offsetHeight - 5, newY));

                    floatBtn.style.left = `${newX}px`;
                    floatBtn.style.top = `${newY}px`;
                }
            };

            const onPointerUp = () => {
                floatBtn.style.cursor = "grab";
                document.removeEventListener("mousemove", onPointerMove);
                document.removeEventListener("mouseup", onPointerUp);
                document.removeEventListener("touchmove", onPointerMove);
                document.removeEventListener("touchend", onPointerUp);
                document.removeEventListener("touchcancel", onPointerUp);

                if (isDragging) {
                    localStorage.setItem("__shiponIG_Btn_Pos", JSON.stringify({
                        left: floatBtn.style.left,
                        top: floatBtn.style.top
                    }));
                    persistFloatingDataToNative();
                } else {
                    togglePanel();
                }
            };

            document.addEventListener("mousemove", onPointerMove);
            document.addEventListener("mouseup", onPointerUp);
            document.addEventListener("touchmove", onPointerMove, { passive: false });
            document.addEventListener("touchend", onPointerUp);
            document.addEventListener("touchcancel", onPointerUp);
        }

        floatBtn.addEventListener("mousedown", onPointerDown);
        floatBtn.addEventListener("touchstart", onPointerDown, { passive: false });

        // Persist Email/Password while typing as well.
        // This is intentionally independent of the script ON/OFF toggle so values
        // entered while OFF survive the reload that happens when ON is enabled.
        let mailPersistTimer = null;
        function persistMailBoxDraft() {
            localStorage.setItem("__shiponIG_UI_Emails", emailInput.value);
            localStorage.setItem("__shiponIG_UI_Password", passInput.value);
            if (mailPersistTimer) clearTimeout(mailPersistTimer);
            mailPersistTimer = setTimeout(function () {
                persistFloatingDataToNative();
            }, 150);
        }
        emailInput.addEventListener("input", persistMailBoxDraft);
        passInput.addEventListener("input", persistMailBoxDraft);

        document.getElementById("shipon-save").addEventListener("click", () => {
            localStorage.setItem("__shiponIG_UI_Emails", emailInput.value);
            localStorage.setItem("__shiponIG_UI_Password", passInput.value);
            localStorage.setItem("__shiponIG_MailAutofillEnabled", "1");
            persistFloatingDataToNative();
            alert("Saved successfully! Page will reload to apply.");
            location.reload();
        });

        document.getElementById("shipon-autofill-toggle").addEventListener("click", () => {
            autofillEnabled = !autofillEnabled;
            localStorage.setItem("__shiponIG_MailAutofillEnabled", autofillEnabled ? "1" : "0");
            persistFloatingDataToNative();
            refreshAutofillToggle();
            if (autofillEnabled) {
                location.reload();
            }
        });

        document.getElementById("shipon-next").addEventListener("click", () => {
            const emails = (localStorage.getItem("__shiponIG_UI_Emails") || "").split("\n").map(e => e.trim()).filter(Boolean);
            const state = loadState();
            const current = state.current;
            if (!current) return;
            if (!state.skipped.includes(current)) state.skipped.push(current);
            state.completed = state.completed.filter(e => e !== current);
            const idx = emails.indexOf(current);
            const next = emails.find((e, i) => i > idx && !state.completed.includes(e) && !state.skipped.includes(e));
            state.current = next || null;
            saveState(state);
            persistFloatingDataToNative();
            location.reload();
        });

        document.getElementById("shipon-previous").addEventListener("click", () => {
            const emails = (localStorage.getItem("__shiponIG_UI_Emails") || "").split("\n").map(e => e.trim()).filter(Boolean);
            const state = loadState();
            const current = state.current;
            const idx = current ? emails.indexOf(current) : emails.length;
            if (idx <= 0) return;
            const previous = [...emails].slice(0, idx).reverse().find(e => !state.completed.includes(e));
            if (!previous) return;
            state.current = previous;
            saveState(state);
            persistFloatingDataToNative();
            location.reload();
        });

        document.getElementById("shipon-reset").addEventListener("click", () => {
            if (confirm("Are you sure you want to clear all completed records? This will start over from the first email.")) {
                localStorage.removeItem("__shiponIG_EmailState");
                persistFloatingDataToNative();
                alert("Memory Cleared! Redirecting to home page.");
                window.location.href = "https://www.instagram.com/";
            }
        });

        persistFloatingDataToNative();

        document.getElementById("shipon-clear-box").addEventListener("click", () => {
            if (confirm("Are you sure you want to remove the text from the Email and Password box?")) {
                localStorage.removeItem("__shiponIG_UI_Emails");
                localStorage.removeItem("__shiponIG_UI_Password");
                emailInput.value = "";
                passInput.value = "";
                persistFloatingDataToNative();
            }
        });
    }

    function initUI() {
        if (!document.body) {
            requestAnimationFrame(initUI);
            return;
        }
        createUIPanel();
    }
    initUI();


    /* =========================================================
       LOAD EMAILS & PASSWORD FROM UI BOX
    ========================================================= */
    const storedEmails = localStorage.getItem("__shiponIG_UI_Emails") || "";
    const EMAILS = storedEmails.split('\n').map(e => e.trim()).filter(e => e !== ""); 
    const PASSWORD = localStorage.getItem("__shiponIG_UI_Password") || "";
    const MAIL_AUTOFILL_ENABLED = localStorage.getItem("__shiponIG_MailAutofillEnabled") !== "0";

    if (!MAIL_AUTOFILL_ENABLED) {
        console.info("[IG Email Autofill] OFF mode: mail automation is paused.");
        return;
    }

    if (EMAILS.length === 0) {
        console.info("[IG Email Autofill] No emails found. Please add emails in the UI box on screen.");
        return;
    }


    /* =========================================================
       SUCCESS URLs
    ========================================================= */
    const SUCCESS_PATHS = [
        "/accounts/registered",
        "/two_factor",
        "/challenge",
        "/onetap"
    ];

    /* =========================================================
       STATE MANAGEMENT
    ========================================================= */
    const STATE_KEY = "__shiponIG_EmailState";
    
    function loadState() {
        try {
            const state = JSON.parse(localStorage.getItem(STATE_KEY)) || {};
            return {
                completed: Array.isArray(state.completed) ? state.completed : [],
                skipped: Array.isArray(state.skipped) ? state.skipped : [],
                current: typeof state.current === "string" ? state.current : null
            };
        } catch (e) {
            return { completed: [], skipped: [], current: null };
        }
    }

    function saveState(state) {
        const normalized = {
            completed: Array.isArray(state.completed) ? state.completed : [],
            skipped: Array.isArray(state.skipped) ? state.skipped : [],
            current: state.current || null
        };
        localStorage.setItem(STATE_KEY, JSON.stringify(normalized));
        persistFloatingDataToNative();
    }

    function persistFloatingDataToNative() {
        try {
            if (!window.Android2FANative || typeof window.Android2FANative.saveFloatingData !== "function") return;
            const keys = [
                "__shiponIG_UI_Emails", "__shiponIG_UI_Password", "__shiponIG_EmailState",
                "__shiponIG_Btn_Pos", "__shipon_cookie_btn_pos", "ig_saved_csv_data",
                "__shiponIG_MailAutofillEnabled"
            ];
            const out = {};
            keys.forEach(k => { const v = localStorage.getItem(k); if (v !== null) out[k] = v; });
            window.Android2FANative.saveFloatingData(JSON.stringify(out));
        } catch (e) {}
    }
    window.__KAUWA_PERSIST_2FA_FLOATING_DATA = persistFloatingDataToNative;

    function checkSuccessAndMark() {
        const state = loadState();
        const currentPath = location.pathname;

        const isSuccess = SUCCESS_PATHS.some(path => currentPath.includes(path));

        if (isSuccess && state.current) {
            if (!state.completed.includes(state.current)) {
                state.completed.push(state.current);
            }
            state.current = null;
            state.skipped = Array.isArray(state.skipped) ? state.skipped : [];
            saveState(state);
            console.info(`[IG Email Autofill] Success URL reached! Marked email as completed.`);
        }
    }

    /* =========================================================
       CAN'T FIND ACCOUNT - 100% BULLETPROOF & LOCKED VERSION
    ========================================================= */
    let isSkipping = false;

    function checkNoAccountAndSkip() {
        if (isSkipping) return;

        // 🛑 তালা ১: ফর্ম টাইপিং সম্পূর্ণ শেষ না হওয়া পর্যন্ত এই চেকার ভুলেও রান হবে না
        if (!completedForm) return;

        // 🛑 তালা ২: স্ক্রিনে ভাসমান কোনো আসল ডায়ালগ/পপআপ বক্স আছে কি না চেক
        const dialog = document.querySelector('div[role="dialog"], [role="alertdialog"]');
        if (!dialog) return;

        const dialogText = (dialog.innerText || dialog.textContent || "");

        // 🛑 তালা ৩: যদি মেটা হরিজন থাকে, তবে ভুলেও এটি ফেইল্ড নয়! (থামো)
        if (dialogText.toLowerCase().includes("meta horizon")) return;

        // 🎯 তালা ৪: পপআপের ভেতরে "Can't find account" এবং সাথে "Try again" বাটন দুটিই থাকতে হবে
        const hasNoAccountTitle = /can['’]t find account/i.test(dialogText) || /we can['’]t find an account/i.test(dialogText);
        const hasTryAgainBtn = dialogText.toLowerCase().includes("try again");

        // দুটি প্রমাণ একসাথে না মিললে কখনোই মেইল পাস করবে না!
        if (!hasNoAccountTitle || !hasTryAgainBtn) return;

        // 🔒 নিশ্চিত ডেড অ্যাকাউন্ট ধরা পড়েছে, এবার লক করে দাও
        isSkipping = true;

        const state = loadState();
        let targetEmail = state.current || TARGET_EMAIL;

        if (targetEmail) {
            // স্টেট আপডেট (যাতে এই নষ্ট মেইল আর না আসে)
            if (!state.completed.includes(targetEmail)) {
                state.completed.push(targetEmail);
            }
            state.completed.push(`${targetEmail} (No Account)`);
            state.current = null;
            saveState(state);

            // মেইল বক্সে (LocalStorage) ওই নির্দিষ্ট নষ্ট মেইলের পাশে (No Account) লিখে সেভ
            let rawEmails = localStorage.getItem("__shiponIG_UI_Emails") || "";
            let lines = rawEmails.split("\n");
            let updated = lines.map(line => {
                let clean = line.trim();
                if (clean.toLowerCase().includes(targetEmail.toLowerCase()) && !clean.includes("(No Account)")) {
                    return `${clean} (No Account)`;
                }
                return line;
            });
            localStorage.setItem("__shiponIG_UI_Emails", updated.join("\n"));

            console.warn(`[AUTO SKIP] ❌ Confirmed dead email: ${targetEmail}. Reloading to next...`);

            // কোনো বাটনে চাপাচাপি না করে সরাসরি রিডাইরেক্ট হয়ে পরের মেইলে যাওয়া
            window.location.href = `https://www.instagram.com/accounts/login/?mtn=1&_cb=${Date.now()}`;
        } else {
            isSkipping = false;
        }
    }

    function getTargetEmail() {
        const state = loadState();

        if (state.current && EMAILS.includes(state.current) && !state.completed.includes(state.current) && !state.skipped.includes(state.current)) {
            return state.current;
        }

        const nextEmail = EMAILS.find(email => !state.completed.includes(email) && !state.skipped.includes(email));

        if (nextEmail) {
            state.current = nextEmail;
            saveState(state);
        }

        return nextEmail;
    }

    const TARGET_EMAIL = getTargetEmail();

    if (!TARGET_EMAIL) {
        console.info("[IG Email Autofill] All emails are used. Script stopped.");
        try {
            const finalState = loadState();
            if (window.Android2FANative && typeof window.Android2FANative.notifyAllEmailsCompleted === "function") {
                window.Android2FANative.notifyAllEmailsCompleted(finalState.completed.length, EMAILS.length);
            }
        } catch (e) {}
        return;
    }

    /* =========================================================
       INTERNAL SETTINGS
    ========================================================= */
    const FLAG = "__shiponInstagramSmartEmailAutofill";
    const MAX_RETRIES = 150;
    const RETRY_DELAY = 100;

    if (window[FLAG]) return;
    window[FLAG] = true;

    /* =========================================================
       BASIC HELPERS
    ========================================================= */
    const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

    function isVisible(el) {
        if (!el || !el.isConnected) return false;
        const style = getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return (style.display !== "none" && style.visibility !== "hidden" && Number(style.opacity) !== 0 && rect.width > 0 && rect.height > 0);
    }

    function normalize(text) {
        return String(text || "").replace(/\s+/g, " ").trim().toLowerCase();
    }

    /* =========================================================
       FIND INSTAGRAM FIELDS
    ========================================================= */
    function findEmailInput() {
        const inputs = [...document.querySelectorAll('input, textarea, [contenteditable="true"]')].filter(isVisible);
        if (!inputs.length) return null;

        let target = inputs.find(el => normalize(el.getAttribute("placeholder")) === "username, email or mobile number");
        if (target) return target;

        target = inputs.find(el => {
            const p = normalize(el.getAttribute("placeholder"));
            return p.includes("username") && (p.includes("email") || p.includes("mobile"));
        });
        if (target) return target;

        target = inputs.find(el => {
            const a = normalize(el.getAttribute("aria-label"));
            const n = normalize(el.getAttribute("name"));
            const ac = normalize(el.getAttribute("autocomplete"));
            return a.includes("username") || a.includes("email") || n === "username" || n === "email" || ac === "username";
        });
        if (target) return target;

        target = inputs.find(el => {
            const t = normalize(el.getAttribute("type"));
            return t === "text" || t === "email";
        });
        return target || null;
    }

    function findPasswordInput() {
        const inputs = [...document.querySelectorAll('input')].filter(isVisible);
        if (!inputs.length) return null;

        return inputs.find(el => {
            const t = normalize(el.getAttribute("type"));
            const n = normalize(el.getAttribute("name"));
            const ac = normalize(el.getAttribute("autocomplete"));
            return t === "password" || n === "password" || ac === "current-password";
        }) || null;
    }

    /* =========================================================
       REACT-COMPATIBLE VALUE SETTER
    ========================================================= */
    function setNativeValue(element, value) {
        if (!element) return false;
        try {
            const prototype = element instanceof HTMLInputElement ? HTMLInputElement.prototype : element instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : null;
            if (prototype) {
                const descriptor = Object.getOwnPropertyDescriptor(prototype, "value");
                if (descriptor && descriptor.set) { descriptor.set.call(element, value); } 
                else { element.value = value; }
            } else { element.textContent = value; }
            return true;
        } catch (error) {
            try { element.value = value; return true; } catch { return false; }
        }
    }

    function notifyFramework(element) {
        const events = [new Event("input", { bubbles: true, cancelable: true }), new Event("change", { bubbles: true, cancelable: true })];
        for (const event of events) { try { element.dispatchEvent(event); } catch {} }
    }

    /* =========================================================
       HUMAN TYPING SIMULATION ENGINE
    ========================================================= */
    async function typeHuman(element, text) {
        if (!element) return false;

        element.focus();
        try {
            element.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, view: window }));
            element.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, view: window }));
            element.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
        } catch (e) {}

        await sleep(210);

        setNativeValue(element, "");
        notifyFramework(element);
        await sleep(210);

        for (let i = 0; i < text.length; i++) {
            const char = text.charAt(i);
            const partial = text.substring(0, i + 1);

            element.dispatchEvent(new KeyboardEvent('keydown', { key: char, bubbles: true }));

            let typed = false;
            try {
                typed = document.execCommand('insertText', false, char);
            } catch (e) {}

            if (!typed || element.value !== partial) {
                setNativeValue(element, partial);
                notifyFramework(element);
            }

            element.dispatchEvent(new KeyboardEvent('keyup', { key: char, bubbles: true }));
            await sleep(6 + Math.floor(Math.random() * 6));
        }

        element.dispatchEvent(new Event("input", { bubbles: true, cancelable: true }));
        element.dispatchEvent(new Event("change", { bubbles: true, cancelable: true }));
        await sleep(210);

        element.blur();
        return true;
    }

    /* =========================================================
       FILL EMAIL (TYPING) & PASSWORD (INSTANT PASTE)
    ========================================================= */
    let isFilling = false;
    let completedForm = false;

    async function executeHumanFill() {
        if (isFilling || completedForm) return;
        if (!location.pathname.includes("/accounts/login")) return;

        const emailInput = findEmailInput();
        const passInput = findPasswordInput();

        if (!emailInput || !passInput) return;

        isFilling = true;
        await sleep(220);

        const freshEmail = findEmailInput();
        if (freshEmail && String(freshEmail.value || "").trim() !== TARGET_EMAIL.trim()) {
            await typeHuman(freshEmail, TARGET_EMAIL);
            console.info("[IG Email Autofill] Email typed like human:", TARGET_EMAIL);
        }

        await sleep(220);

        const freshPass = findPasswordInput();
        if (freshPass && String(freshPass.value || "").trim() !== PASSWORD.trim()) {
            freshPass.focus();
            try {
                freshPass.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, view: window }));
                freshPass.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, view: window }));
                freshPass.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
            } catch (e) {}
            await sleep(80);

            setNativeValue(freshPass, "");
            let pasted = false;
            try {
                pasted = document.execCommand('insertText', false, PASSWORD);
            } catch (e) {}

            if (!pasted || freshPass.value !== PASSWORD) {
                setNativeValue(freshPass, PASSWORD);
            }
            notifyFramework(freshPass);

            await sleep(100);
            freshPass.blur();
            console.info("[IG Email Autofill] Password pasted instantly.");
        }

        // Verify both fields before stopping the retry engine.
        const finalEmail = findEmailInput();
        const finalPass = findPasswordInput();
        const emailOk = !!finalEmail && String(finalEmail.value || "").trim() === TARGET_EMAIL.trim();
        const passOk = !!finalPass && String(finalPass.value || "").trim() === PASSWORD.trim();

        completedForm = emailOk && passOk;
        isFilling = false;

        if (!completedForm) {
            console.warn("[IG Email Autofill] Fill verification failed; retrying.");
        }
    }

    /* =========================================================
       RETRY ENGINE & OBSERVER
    ========================================================= */
    async function tryFill() {
        if (!location.pathname.includes("/accounts/login")) return;
        if (completedForm || isFilling) return;

        for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
            const emailInput = findEmailInput();
            const passInput = findPasswordInput();

            if (emailInput && passInput) {
                await executeHumanFill();
                if (completedForm) return;
            }
            await sleep(RETRY_DELAY);
        }
    }

    const observer = new MutationObserver(() => {
        if (!location.pathname.includes("/accounts/login")) return;
        if (completedForm || isFilling) return;

        const emailInput = findEmailInput();
        const passInput = findPasswordInput();

        if (emailInput && passInput) {
            executeHumanFill();
        }
    });

    function startObserver() {
        if (!document.documentElement) { setTimeout(startObserver, 50); return; }
        observer.observe(document.documentElement, { 
            childList: true, 
            subtree: true, 
            attributes: true, 
            attributeFilter: ["placeholder", "aria-label", "name", "type", "autocomplete"] 
        });
    }

    /* =========================================================
       SPA / PAGE NAVIGATION WATCHER
    ========================================================= */
    let lastURL = location.href;

    setInterval(() => {
        checkSuccessAndMark();
        checkNoAccountAndSkip();

        if (location.href !== lastURL) {
            lastURL = location.href;
            completedForm = false;
            setTimeout(() => { tryFill(); }, 100);
        }
    }, 100);

    /* =========================================================
       START
    ========================================================= */
    checkSuccessAndMark();
    startObserver();
    tryFill().catch(error => { console.error("[IG Email Autofill] Error:", error); });

})();

// ==UserScript==
// @name         IG Login Final 🔥
// @namespace    https://viayoo.com/
// @version      8.0 (Golden Edition)
// @description  Instagram Login, Meta Horizon, Full Name Typing Simulation, Accept Official Username (Auto-Next), Allow & Continue, and 2FA Redirect
// @match        https://www.instagram.com/*
// @run-at       document-end
// @grant        none
// ==/UserScript==

// ============================================================
// PART 1: LOGIN + META HORIZON AUTO SELECT
// ============================================================
(function () {
    'use strict';

    // Prevent the 2Fa login automation from being injected/running more than once
    // in the same WebView document. Multiple instances were causing repeated Login clicks.
    if (window.__KAUWA_2FA_LOGIN_FLOW_V18_ACTIVE) return;
    window.__KAUWA_2FA_LOGIN_FLOW_V18_ACTIVE = true;

    var clicked = false;
    var metaClicked = false;
    var lastCheck = 0;
    var horizonGuardTimer = null;

    // নতুন Login recovery state
    var loginSequenceRunning = false;
    var loginSequenceStartedAt = 0;
    var firstLoginDone = false;
    var spinnerStarted = false;
    var recoveryClicked = false;
    var secondLoginDone = false;

    if (window.top !== window.self) return;
    if (!window.location.hostname.includes('instagram.com')) return;
    if (!window.location.pathname.includes('/accounts/login')) return;


    // ============================================================
    // GET INPUTS
    // ============================================================
    function getInputs() {

        var inputs = document.querySelectorAll(
            'input:not([type="hidden"]):not([disabled])'
        );

        var visible = [];

        for (var i = 0; i < inputs.length; i++) {

            var el = inputs[i];
            var rect = el.getBoundingClientRect();

            if (
                rect.width > 0 &&
                rect.height > 0 &&
                getComputedStyle(el).visibility !== 'hidden' &&
                getComputedStyle(el).display !== 'none'
            ) {
                visible.push(el);
            }
        }

        return visible;
    }


    // ============================================================
    // FIND USERNAME
    // ============================================================
    function findUsernameField() {

        var inputs = getInputs();

        for (var i = 0; i < inputs.length; i++) {

            var el = inputs[i];

            var type = (el.type || '').toLowerCase();
            var name = (el.name || '').toLowerCase();
            var placeholder = (el.placeholder || '').toLowerCase();
            var aria = (
                el.getAttribute('aria-label') || ''
            ).toLowerCase();
            var autocomplete = (
                el.autocomplete || ''
            ).toLowerCase();

            if (
                type === 'email' ||
                autocomplete === 'username' ||
                name.includes('username') ||
                name.includes('email') ||
                placeholder.includes('email') ||
                placeholder.includes('phone') ||
                placeholder.includes('username') ||
                aria.includes('email') ||
                aria.includes('phone') ||
                aria.includes('username')
            ) {
                return el;
            }
        }

        for (var j = 0; j < inputs.length; j++) {

            if (
                (inputs[j].type || '').toLowerCase() !== 'password'
            ) {
                return inputs[j];
            }
        }

        return null;
    }


    // ============================================================
    // FIND PASSWORD
    // ============================================================
    function findPasswordField() {

        var inputs = getInputs();

        for (var i = 0; i < inputs.length; i++) {

            var el = inputs[i];

            var type = (el.type || '').toLowerCase();
            var name = (el.name || '').toLowerCase();
            var autocomplete = (
                el.autocomplete || ''
            ).toLowerCase();

            if (
                type === 'password' ||
                name.includes('password') ||
                autocomplete === 'current-password'
            ) {
                return el;
            }
        }

        return null;
    }


    // ============================================================
    // HAS VALUE
    // ============================================================
    function hasValue(el) {

        if (!el) return false;

        try {
            return String(el.value || '').trim().length > 0;
        } catch (e) {
            return false;
        }
    }


    // ============================================================
    // FIND LOGIN BUTTON
    // ============================================================
    function findLoginButton() {

        var elements = document.querySelectorAll(
            'button, [role="button"]'
        );

        var candidates = [];

        for (var i = 0; i < elements.length; i++) {

            var el = elements[i];
            var rect = el.getBoundingClientRect();

            if (
                rect.width <= 0 ||
                rect.height <= 0 ||
                getComputedStyle(el).display === 'none' ||
                getComputedStyle(el).visibility === 'hidden'
            ) {
                continue;
            }

            var text = (
                el.innerText ||
                el.textContent ||
                el.getAttribute('aria-label') ||
                ''
            ).trim().toLowerCase();

            if (
                text === 'log in' ||
                text === 'login' ||
                text === 'log in ' ||
                text.includes('log in')
            ) {
                candidates.push(el);
            }
        }

        return candidates.length ? candidates[0] : null;
    }


    // ============================================================
    // ADVANCED CLICK
    // ============================================================
    function advancedClick(el) {

        if (!el) return;

        try {
            el.scrollIntoView({
                behavior: 'instant',
                block: 'center',
                inline: 'center'
            });
        } catch (e) {}

        try {
            el.focus();
        } catch (e) {}

        var events = [
            'pointerdown',
            'mousedown',
            'pointerup',
            'mouseup'
        ];

        for (var i = 0; i < events.length; i++) {

            try {
                el.dispatchEvent(
                    new MouseEvent(events[i], {
                        bubbles: true,
                        cancelable: true,
                        view: window
                    })
                );
            } catch (e) {}
        }

        try {
            el.click();
        } catch (e) {}
    }


    // ============================================================
    // CHECK LOGIN SPINNER
    // ============================================================
    function isLoginSpinnerActive(btn) {

        if (!btn) return false;

        try {

            if (btn.disabled) return true;

            if (
                btn.getAttribute('aria-busy') === 'true'
            ) {
                return true;
            }

            if (
                btn.querySelector('[role="progressbar"]')
            ) {
                return true;
            }

            var text = (
                btn.innerText ||
                btn.textContent ||
                ''
            ).trim().toLowerCase();

            /*
             * Instagram spinner অবস্থায়
             * Login লেখাটা অদৃশ্য হয়ে যায়।
             */
            if (!text) {
                return true;
            }

            var children = btn.querySelectorAll('*');

            for (var i = 0; i < children.length; i++) {

                var style = getComputedStyle(children[i]);

                if (
                    style.animationName &&
                    style.animationName !== 'none' &&
                    style.animationDuration !== '0s'
                ) {
                    return true;
                }

                if (
                    style.webkitAnimationName &&
                    style.webkitAnimationName !== 'none' &&
                    style.webkitAnimationDuration !== '0s'
                ) {
                    return true;
                }
            }

        } catch (e) {}

        return false;
    }


    // ============================================================
    // WAIT UNTIL SPINNER STARTS
    // ============================================================
    function waitForSpinnerStart(callback) {

        var startedAt = Date.now();

        function check() {

            if (!loginSequenceRunning) return;

            var btn = findLoginButton();

            if (btn && isLoginSpinnerActive(btn)) {

                spinnerStarted = true;

                /*
                 * Spinner সত্যিই শুরু হয়েছে।
                 */
                setTimeout(function () {
                    waitForSpinnerStop(callback);
                }, 50);

                return;
            }

            /*
             * কিছু device/browser-এ spinner detection
             * একটু দেরিতে হতে পারে।
             */
            if (Date.now() - startedAt < 10000) {
                setTimeout(check, 50);
            } else {

                /*
                 * Timeout হলেও এখনই দ্বিতীয় Login নয়।
                 * কিছুক্ষণ অপেক্ষা করে recovery flow।
                 */
                setTimeout(function () {
                    callback();
                }, 1000);
            }
        }

        check();
    }


    // ============================================================
    // WAIT UNTIL SPINNER STOPS
    // ============================================================
    function waitForSpinnerStop(callback) {

        var startedAt = Date.now();

        function check() {

            if (!loginSequenceRunning) return;

            var btn = findLoginButton();

            /*
             * Spinner এখনও চলছে।
             */
            if (
                btn &&
                isLoginSpinnerActive(btn)
            ) {

                if (Date.now() - startedAt < 30000) {
                    setTimeout(check, 50);
                }

                return;
            }

            /*
             * Spinner শেষ হয়েছে।
             *
             * এখান থেকেই recovery শুরু হবে।
             */
            callback();
        }

        check();
    }


    // ============================================================
    // FIND "ENGLISH (US)"
    // ============================================================
    function findEnglishUS() {

        var elements = document.querySelectorAll(
            'button, [role="button"], a, div, span'
        );

        var best = null;

        for (var i = 0; i < elements.length; i++) {

            var el = elements[i];

            var rect = el.getBoundingClientRect();

            if (
                rect.width <= 0 ||
                rect.height <= 0 ||
                getComputedStyle(el).display === 'none' ||
                getComputedStyle(el).visibility === 'hidden'
            ) {
                continue;
            }

            var text = (
                el.innerText ||
                el.textContent ||
                ''
            ).trim().replace(/\s+/g, ' ');

            if (text === 'English (US)') {

                if (!best) {
                    best = el;
                } else {

                    var oldRect =
                        best.getBoundingClientRect();

                    if (
                        rect.width * rect.height <
                        oldRect.width * oldRect.height
                    ) {
                        best = el;
                    }
                }
            }
        }

        return best;
    }


    // ============================================================
    // FIND INSTAGRAM LOGO (ENGLISH US এর মতো হুবহু লজিক)
    // ============================================================
    function findInstagramLogo() {

        var elements = document.querySelectorAll(
            'i, svg, [role="img"], img, div, span'
        );

        var best = null;

        for (var i = 0; i < elements.length; i++) {

            var el = elements[i];

            var rect = el.getBoundingClientRect();

            if (
                rect.width <= 0 ||
                rect.height <= 0 ||
                getComputedStyle(el).display === 'none' ||
                getComputedStyle(el).visibility === 'hidden'
            ) {
                continue;
            }

            var aria = (
                el.getAttribute('aria-label') || ''
            ).toLowerCase();

            var alt = (
                el.getAttribute('alt') || ''
            ).toLowerCase();

            if (
                aria.includes('instagram') ||
                alt.includes('instagram')
            ) {
                return el;
            }

            if (
                rect.width >= 25 && rect.width <= 120 &&
                rect.height >= 25 && rect.height <= 120 &&
                rect.top > 0 && rect.top < window.innerHeight * 0.6
            ) {

                var ratio = rect.width / rect.height;

                if (ratio >= 0.75 && ratio <= 1.35) {

                    if (!best) {
                        best = el;
                    } else {

                        var oldRect =
                            best.getBoundingClientRect();

                        if (
                            rect.width * rect.height <
                            oldRect.width * oldRect.height
                        ) {
                            best = el;
                        }
                    }
                }
            }
        }

        return best;
    }


    // ============================================================
    // DISPATCH REALISTIC TAP AT SCREEN POSITION
    // ============================================================
    function tapAtPoint(x, y) {

        var target =
            document.elementFromPoint(x, y);

        if (!target) return false;

        var eventOptions = {
            bubbles: true,
            cancelable: true,
            view: window,
            clientX: x,
            clientY: y
        };

        try {
            if (window.PointerEvent) {
                target.dispatchEvent(
                    new PointerEvent(
                        'pointerdown',
                        Object.assign(
                            { pointerType: 'touch' },
                            eventOptions
                        )
                    )
                );
            }
        } catch (e) {}

        try {
            target.dispatchEvent(
                new MouseEvent(
                    'mousedown',
                    eventOptions
                )
            );
        } catch (e) {}

        try {
            if (window.PointerEvent) {
                target.dispatchEvent(
                    new PointerEvent(
                        'pointerup',
                        Object.assign(
                            { pointerType: 'touch' },
                            eventOptions
                        )
                    )
                );
            }
        } catch (e) {}

        try {
            target.dispatchEvent(
                new MouseEvent(
                    'mouseup',
                    eventOptions
                )
            );
        } catch (e) {}

        try {
            target.click();
        } catch (e) {}

        return true;
    }


    // ============================================================
    // CHECK WHETHER POINT IS ACTUALLY ON TARGET
    // ============================================================
    function isPointOnEnglishUS(x, y, english) {

        if (!english) return false;

        var target =
            document.elementFromPoint(x, y);

        if (!target) return false;

        return (
            target === english ||
            english.contains(target)
        );
    }


    // ============================================================
    // RECOVERY CLICK (SAFE MODE: NO LOGO CLICK)
    // ============================================================
    function performRecoveryClick(callback) {

        if (recoveryClicked) return;

        var english = findEnglishUS();
        var userField = findUsernameField();

        /*
         * লোগো ট্যাপ বাতিল! শুধু English US বা Username Field খুঁজবে
         */
        if (!english && !userField) {
            setTimeout(function () {
                performRecoveryClick(callback);
            }, 50);
            return;
        }

        // ১. English (US) এ ট্যাপ (স্ক্রিনে থাকলে)
        if (english) {
            var rect = english.getBoundingClientRect();
            if (rect.top >= 0 && rect.top < window.innerHeight) {
                var x = Math.floor(rect.left + rect.width / 2);
                var y = Math.floor(rect.top + rect.height / 2);
                tapAtPoint(x, y);
            }
        }

        // ২. Username Field এর সোজাসুজি ট্যাপ (পপআপের কালো পর্দায়)
        if (userField) {
            var uRect = userField.getBoundingClientRect();
            var ux = Math.floor(uRect.left + uRect.width / 2);
            var uy = Math.floor(uRect.top + uRect.height / 2);
            tapAtPoint(ux, uy);
        }

        recoveryClicked = true;


        // ========================================================
        // WAIT UNTIL BLACK OVERLAY DISAPPEARS
        // ========================================================
        var startedAt = Date.now();

        function waitForOverlayToDisappear() {

            var freshEnglish = findEnglishUS();
            var freshUserField = findUsernameField();

            if (!freshEnglish && !freshUserField) {
                setTimeout(waitForOverlayToDisappear, 50);
                return;
            }

            // চেক ১: English (US) ফ্রি হয়েছে কি না
            if (freshEnglish) {
                var freshRect = freshEnglish.getBoundingClientRect();
                var freshX = Math.floor(freshRect.left + freshRect.width / 2);
                var freshY = Math.floor(freshRect.top + freshRect.height / 2);

                if (isPointOnEnglishUS(freshX, freshY, freshEnglish)) {
                    setTimeout(function () { callback(); }, 100);
                    return;
                }
            }

            // চেক ২: Username Field সরাসরি ক্লিকেবল হয়েছে কি না
            if (freshUserField) {
                var freshURect = freshUserField.getBoundingClientRect();
                var freshUX = Math.floor(freshURect.left + freshURect.width / 2);
                var freshUY = Math.floor(freshURect.top + freshURect.height / 2);

                if (isPointOnEnglishUS(freshUX, freshUY, freshUserField)) {
                    setTimeout(function () { callback(); }, 100);
                    return;
                }
            }

            // পর্দা এখনও থাকলে অপেক্ষা করবে
            if (Date.now() - startedAt < 15000) {
                setTimeout(waitForOverlayToDisappear, 50);
            }
        }

        waitForOverlayToDisappear();
    }


    // ============================================================
    // WAIT FOR LOGIN SCREEN AFTER RECOVERY
    // ============================================================
    function waitForLoginScreen(callback) {

        var startedAt = Date.now();

        function check() {

            if (!loginSequenceRunning) return;

            var user =
                findUsernameField();

            var pass =
                findPasswordField();

            var btn =
                findLoginButton();

            if (
                user &&
                pass &&
                btn &&
                hasValue(user) &&
                hasValue(pass)
            ) {

                /*
                 * Screen পুরোপুরি ফিরে আসার পর
                 * সামান্য stable time।
                 */
                setTimeout(function () {
                    callback();
                }, 150);

                return;
            }

            if (
                Date.now() - startedAt <
                15000
            ) {
                setTimeout(check, 50);
            }
        }

        check();
    }


    // ============================================================
    // HORIZON POPUP GUARD
    // The moment the Meta Horizon account popup appears, stop every
    // pending Login retry/recovery path. Horizon must get priority.
    // ============================================================
    function isMetaHorizonPopupVisible() {
        try {
            var target = findMetaHorizon();
            if (target) return true;
        } catch (e) {}

        try {
            var text = ((document.body && (document.body.innerText || document.body.textContent)) || '')
                .replace(/\s+/g, ' ')
                .toLowerCase();
            return text.indexOf('meta horizon') !== -1;
        } catch (e) {
            return false;
        }
    }

    function stopLoginForHorizonPopup() {
        if (!isMetaHorizonPopupVisible()) return false;

        // Hard-stop all Login/recovery state immediately.
        loginSequenceRunning = false;
        clicked = true;
        firstLoginDone = true;
        secondLoginDone = true;
        spinnerStarted = false;
        recoveryClicked = true;

        if (horizonGuardTimer) {
            try { clearInterval(horizonGuardTimer); } catch (e) {}
            horizonGuardTimer = null;
        }

        // Give the existing Horizon click logic the next turn.
        setTimeout(function () {
            try { checkMetaHorizon(); } catch (e) {}
        }, 0);

        return true;
    }

    function startHorizonGuard() {
        if (horizonGuardTimer) return;
        horizonGuardTimer = setInterval(function () {
            if (stopLoginForHorizonPopup()) return;
            if (!loginSequenceRunning) {
                try { clearInterval(horizonGuardTimer); } catch (e) {}
                horizonGuardTimer = null;
            }
        }, 25);
    }

    // ============================================================
    // START COMPLETE LOGIN FLOW
    // ============================================================
    function startLoginSequence(btn) {

        if (loginSequenceRunning) return;

        loginSequenceRunning = true;
        loginSequenceStartedAt = Date.now();

        firstLoginDone = false;
        spinnerStarted = false;
        recoveryClicked = false;
        secondLoginDone = false;

        // From this point onward, watch the page continuously.
        // If Horizon appears, Login retries stop before another click can fire.
        startHorizonGuard();

        // ========================================================
        // STEP 1
        // FIRST LOGIN CLICK
        // ========================================================
        if (stopLoginForHorizonPopup()) return;
        setTimeout(function () {
            if (!loginSequenceRunning || stopLoginForHorizonPopup()) return;
            advancedClick(btn);

            clicked = true;
            firstLoginDone = true;

            waitForSpinnerStart(function () {
                performRecoveryClick(function () {
                    waitForLoginScreen(function () {
                        var secondBtn = findLoginButton();
                        if (!secondBtn) {
                            loginSequenceRunning = false;
                            return;
                        }

                        clicked = false;
                        if (stopLoginForHorizonPopup()) return;
                        setTimeout(function () {
                            if (!loginSequenceRunning || stopLoginForHorizonPopup()) return;
                            advancedClick(secondBtn);
                            clicked = true;
                            secondLoginDone = true;
                            loginSequenceRunning = false;
                            loginSequenceStartedAt = 0;
                            setTimeout(function () { checkMetaHorizon(); }, 220);
                        }, 220);
                    });
                });
            });
        }, 220);
        return;
    }


    // ============================================================
    // LOGIN READY
    // ============================================================
    function checkLoginReady() {

        var now = Date.now();

        if (now - lastCheck < 100) return;

        lastCheck = now;

        if (clicked) return;

        if (loginSequenceRunning) return;

        var usernameField =
            findUsernameField();

        var passwordField =
            findPasswordField();

        if (
            !usernameField ||
            !passwordField
        ) {
            return;
        }

        if (!hasValue(usernameField)) return;
        if (!hasValue(passwordField)) return;

        var loginButton =
            findLoginButton();

        if (!loginButton) return;


        setTimeout(function () {

            if (clicked) return;

            if (loginSequenceRunning) return;

            var user =
                findUsernameField();

            var pass =
                findPasswordField();

            var btn =
                findLoginButton();

            if (
                user &&
                pass &&
                hasValue(user) &&
                hasValue(pass) &&
                btn
            ) {

                startLoginSequence(btn);
            }

        }, 80);
    }


    // ============================================================
    // ORIGINAL META HORIZON LOGIC
    // ============================================================
    function getElementText(el) {

        if (!el) return '';

        var text = '';

        try {
            text += ' ' + (el.innerText || '');
        } catch (e) {}

        try {
            text += ' ' + (el.textContent || '');
        } catch (e) {}

        try {
            text += ' ' + (
                el.getAttribute('aria-label') || ''
            );
        } catch (e) {}

        try {
            text += ' ' + (
                el.getAttribute('title') || ''
            );
        } catch (e) {}

        return text
            .replace(/\s+/g, ' ')
            .trim()
            .toLowerCase();
    }


    function isMetaVisible(el) {

        if (!el) return false;

        try {

            var rect =
                el.getBoundingClientRect();

            var style =
                window.getComputedStyle(el);

            return (
                rect.width > 0 &&
                rect.height > 0 &&
                style.display !== 'none' &&
                style.visibility !== 'hidden' &&
                style.opacity !== '0'
            );

        } catch (e) {
            return false;
        }
    }


    function findMetaHorizon() {

        var elements =
            document.querySelectorAll(
                'button, [role="button"], a, li, div'
            );

        var candidates = [];

        for (
            var i = 0;
            i < elements.length;
            i++
        ) {

            var el = elements[i];

            if (!isMetaVisible(el)) continue;

            var text =
                getElementText(el);

            if (!text) continue;

            if (
                text.includes('meta horizon')
            ) {
                candidates.push(el);
            }
        }

        if (!candidates.length) {
            return null;
        }

        var best =
            candidates[0];

        for (
            var j = 1;
            j < candidates.length;
            j++
        ) {

            try {

                var a =
                    best.getBoundingClientRect();

                var b =
                    candidates[j]
                        .getBoundingClientRect();

                var areaA =
                    a.width * a.height;

                var areaB =
                    b.width * b.height;

                if (
                    areaB > 0 &&
                    areaB < areaA
                ) {
                    best =
                        candidates[j];
                }

            } catch (e) {}
        }

        return best;
    }


    function getMetaClickable(el) {

        if (!el) return null;

        var current = el;

        for (
            var i = 0;
            i < 8 && current;
            i++
        ) {

            if (
                current.tagName === 'BUTTON' ||
                current.tagName === 'A' ||
                current.getAttribute('role') === 'button'
            ) {
                return current;
            }

            try {

                if (
                    window.getComputedStyle(
                        current
                    ).cursor === 'pointer'
                ) {
                    return current;
                }

            } catch (e) {}

            current =
                current.parentElement;
        }

        return el;
    }


    function clickMetaHorizon(el) {

        if (
            !el ||
            metaClicked
        ) {
            return;
        }

        el =
            getMetaClickable(el);

        if (
            !el ||
            !isMetaVisible(el)
        ) {
            return;
        }

        try {
            el.scrollIntoView({
                behavior: 'instant',
                block: 'center',
                inline: 'center'
            });
        } catch (e) {}

        try {
            el.focus({
                preventScroll: true
            });
        } catch (e) {}

        try {
            el.dispatchEvent(
                new MouseEvent(
                    'mousedown',
                    {
                        bubbles: true,
                        cancelable: true,
                        view: window
                    }
                )
            );
        } catch (e) {}

        try {
            el.dispatchEvent(
                new MouseEvent(
                    'mouseup',
                    {
                        bubbles: true,
                        cancelable: true,
                        view: window
                    }
                )
            );
        } catch (e) {}

        try {
            el.click();

            metaClicked = true;

        } catch (e) {}
    }


    function checkMetaHorizon() {

        if (!clicked || metaClicked) return;

        var target =
            findMetaHorizon();

        if (!target) return;

        setTimeout(function () {

            if (metaClicked) return;

            var freshTarget =
                findMetaHorizon();

            if (freshTarget) {
                clickMetaHorizon(
                    freshTarget
                );
            }

        }, 220);
    }


    // ============================================================
    // INPUT / CHANGE
    // ============================================================
    document.addEventListener(
        'input',
        function () {
            checkLoginReady();
        },
        true
    );

    document.addEventListener(
        'change',
        function () {
            checkLoginReady();
        },
        true
    );


    // ============================================================
    // MUTATION OBSERVER
    // ============================================================
    var observer =
        new MutationObserver(
            function () {

                // Horizon popup has absolute priority over any Login/recovery action.
                if (stopLoginForHorizonPopup()) return;

                if (
                    !clicked &&
                    !loginSequenceRunning
                ) {
                    checkLoginReady();
                }

                else if (
                    clicked &&
                    secondLoginDone &&
                    !metaClicked
                ) {
                    checkMetaHorizon();
                }

            }
        );


    try {

        observer.observe(
            document.documentElement,
            {
                childList: true,
                subtree: true,
                attributes: true,
                attributeFilter: [
                    'disabled',
                    'aria-label',
                    'type'
                ]
            }
        );

    } catch (e) {}


    // ============================================================
    // INITIAL CHECK
    // ============================================================
    checkLoginReady();

    // Self-healing login watchdog: if the sequence loses a callback and the
    // login screen is still present for a long time, release the stale lock
    // and let the normal detector start the sequence again.
    var loginRecoveryTimer = setInterval(function () {
        try {
            if (!loginSequenceRunning || !loginSequenceStartedAt) return;
            if (Date.now() - loginSequenceStartedAt < 30000) return;
            if (stopLoginForHorizonPopup()) return;
            if (!isLoginPageActive()) return;
            console.warn('[2FA AUTO] Login sequence watchdog reset after 30s.');
            loginSequenceRunning = false;
            loginSequenceStartedAt = 0;
            clicked = false;
            firstLoginDone = false;
            spinnerStarted = false;
            recoveryClicked = false;
            secondLoginDone = false;
            checkLoginReady();
        } catch (e) {}
    }, 1000);

    // 👉 যতক্ষণ ক্লিক না পড়বে ডাকবে, ক্লিক পড়ামাত্রই ডাকা চিরতরে স্টপ:
    var loginCheckTimer = setInterval(function () {
        // ১. যেই মুহূর্তে ক্লিক পড়বে বা কাজ শুরু হবে -> সাথে সাথে ডাকা স্টপ!
        if (clicked || loginSequenceRunning) {
            clearInterval(loginCheckTimer); 
            return;
        }

        // ২. আর যতক্ষণ ক্লিক না পড়বে -> সে প্রতি ১৫০ms পর পর ডাকতেই থাকবে
        checkLoginReady();
    }, 150);

})();

// ============================================================
// PART 2: FULL NAME (TYPING SIMULATION) & OFFICIAL USERNAME AUTO-NEXT
// ============================================================
(function () {
    'use strict';
    
    var clicked = false;
    var lastCheck = 0;
    
    if (window.top !== window.self) return;
    if (!window.location.hostname.includes('instagram.com')) return;
    
    function isLoginPageActive() {
        var passwords = document.querySelectorAll('input[type="password"]');
        for (var i = 0; i < passwords.length; i++) {
            var rect = passwords[i].getBoundingClientRect();
            if (rect.width > 0 && rect.height > 0 && getComputedStyle(passwords[i]).display !== 'none' && getComputedStyle(passwords[i]).visibility !== 'hidden') {
                return true;
            }
        }
        return false;
    }

    // ============================================================
    // USERNAME-STYLE NAME GENERATOR (NOW APPLIED TO FULL NAME)
    // Formula: Bangladeshi + Foreign + Random Numbers (No Space)
    // ============================================================
    var bdNames = [
        'shohidul', 'rafiqul', 'tariqul', 'aminul', 'kamrul',
        'saiful', 'asraful', 'nazrul', 'jahirul', 'mizanur',
        'tanvir', 'mehedi', 'ariful', 'hasibul', 'rakibul',
        'sohel', 'sumon', 'shariful', 'delowar', 'monirul'
    ];

    var foreignNames = [
        'alexander', 'robertson', 'harrison', 'williams', 'thompson',
        'mitchell', 'anderson', 'morrison', 'sebastian', 'benjamin',
        'christopher', 'valentino', 'maximilian', 'montgomery', 'fernandez'
    ];

    function getRandomName() {
        var bd = bdNames[Math.floor(Math.random() * bdNames.length)];
        var foreign = foreignNames[Math.floor(Math.random() * foreignNames.length)];
        var digits = Math.floor(1000 + Math.random() * 9000);

        return bd + '_' + foreign + '_' + digits;
    }

    function sleep(ms) {
        return new Promise(function (resolve) {
            setTimeout(resolve, ms);
        });
    }

    function setInputValue(el, value) {
        if (!el) return false;

        try {
            el.focus();
            var prototype = Object.getPrototypeOf(el);
            var descriptor = Object.getOwnPropertyDescriptor(prototype, 'value');

            if (descriptor && descriptor.set) {
                descriptor.set.call(el, value);
            } else {
                el.value = value;
            }

            el.dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));
            el.dispatchEvent(new Event('change', { bubbles: true, cancelable: true }));
            return true;
        } catch (e) {
            return false;
        }
    }

    function getInputs() {
        var inputs = document.querySelectorAll('input:not([type="hidden"]):not([disabled])');
        var visible = [];    
        for (var i = 0; i < inputs.length; i++) {    
            var el = inputs[i];    
            var rect = el.getBoundingClientRect();    
            if (rect.width > 0 && rect.height > 0 && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none') {    
                visible.push(el);    
            }    
        }    
        return visible;
    }
    
    function findFullNameField() {
        var inputs = getInputs();
        for (var i = 0; i < inputs.length; i++) {    
            var el = inputs[i];    
            var type = (el.type || '').toLowerCase();    
            var name = (el.name || '').toLowerCase();    
            var placeholder = (el.placeholder || '').toLowerCase();    
            var aria = (el.getAttribute('aria-label') || '').toLowerCase();    
            var autocomplete = (el.autocomplete || '').toLowerCase();    

            if (type === 'password' || type === 'email') continue;
            if (name.includes('username') || placeholder.includes('username') || aria.includes('username') || autocomplete === 'username') continue;
            if (name.includes('email') || placeholder.includes('email') || aria.includes('email')) continue;
            if (name.includes('phone') || placeholder.includes('phone') || aria.includes('phone')) continue;

            if (
                autocomplete === 'name' ||
                name === 'fullname' ||
                name === 'full_name' ||
                name === 'name' ||
                placeholder.includes('full name') ||
                placeholder === 'name' ||
                aria.includes('full name')
            ) {    
                return el;    
            }    
        }    
        return null;
    }

    function findClearButton(nameInput) {
        if (!nameInput) return null;
        var container = nameInput.closest('label') || nameInput.parentElement;
        for (var i = 0; i < 4 && container; i++) {
            var buttons = container.querySelectorAll('button, [role="button"], span[role="button"]');
            for (var j = 0; j < buttons.length; j++) {
                var btn = buttons[j];
                if (btn === nameInput) continue;
                var text = (btn.innerText || btn.textContent || '').trim().toLowerCase();
                var aria = (btn.getAttribute('aria-label') || '').toLowerCase();
                
                if (text.includes('next') || aria.includes('next') || text.includes('log in')) continue;
                return btn;
            }
            container = container.parentElement;
        }
        return null;
    }
    
    function isVisibleNextElement(el) {
        if (!el || !el.isConnected) return false;
        var rect = el.getBoundingClientRect();
        var style = getComputedStyle(el);
        return rect.width > 0 && rect.height > 0 &&
            style.display !== 'none' &&
            style.visibility !== 'hidden' &&
            Number(style.opacity) !== 0;
    }

    // Strong Next finder: locate the visible "Next" text first, then walk up
    // to the real clickable button/container instead of clicking a fragile span.
    function findNextButton() {
        // Prefer the real native button first. This avoids clicking a nested
        // span/div that only contains the word "Next" on some Instagram builds.
        var buttons = document.querySelectorAll('button, [role="button"]');
        for (var j = 0; j < buttons.length; j++) {
            var b = buttons[j];
            if (!isVisibleNextElement(b)) continue;
            var bt = (b.innerText || b.textContent || b.getAttribute('aria-label') || '').replace(/\s+/g, ' ').trim().toLowerCase();
            if ((bt === 'next' || bt.startsWith('next ')) && nextButtonIsBasicUsable(b)) return b;
        }

        var textNodes = document.querySelectorAll('span, div, a');
        for (var i = 0; i < textNodes.length; i++) {
            var el = textNodes[i];
            if (!isVisibleNextElement(el)) continue;
            var text = (el.innerText || el.textContent || el.getAttribute('aria-label') || '').replace(/\s+/g, ' ').trim().toLowerCase();
            if (text !== 'next' && !text.startsWith('next ')) continue;

            var current = el;
            for (var level = 0; level < 12 && current; level++) {
                if (!isVisibleNextElement(current)) { current = current.parentElement; continue; }
                var role = (current.getAttribute('role') || '').toLowerCase();
                var tag = (current.tagName || '').toLowerCase();
                var aria = (current.getAttribute('aria-label') || '').toLowerCase();
                if (tag === 'button' || role === 'button' || aria === 'next') return current;
                current = current.parentElement;
            }
        }
        return null;
    }

    function nextButtonIsBasicUsable(btn) {
        if (!btn || !isVisibleNextElement(btn)) return false;
        if (btn.disabled || btn.hasAttribute('disabled')) return false;
        if ((btn.getAttribute('aria-disabled') || '').toLowerCase() === 'true') return false;
        try { if (getComputedStyle(btn).pointerEvents === 'none') return false; } catch (e) {}
        return true;
    }

    function nextButtonIsUsable(btn) {
        if (!btn || !isVisibleNextElement(btn)) return false;
        if (btn.disabled || btn.hasAttribute('disabled')) return false;
        if ((btn.getAttribute('aria-disabled') || '').toLowerCase() === 'true') return false;
        try {
            if (getComputedStyle(btn).pointerEvents === 'none') return false;
        } catch (e) {}
        return true;
    }
    
    // Strong human-style click used by both Full Name and Username flows.
    async function performClick(el) {
        if (!el) return false;

        for (var attempt = 0; attempt < 5; attempt++) {
            var target = findNextButton() || el;
            if (!nextButtonIsUsable(target)) {
                await sleep(120);
                continue;
            }

            try { target.scrollIntoView({ behavior: 'instant', block: 'center', inline: 'center' }); } catch (e) {}
            await sleep(70);

            var rect = target.getBoundingClientRect();
            var x = Math.floor(rect.left + rect.width / 2);
            var y = Math.floor(rect.top + rect.height / 2);
            var opts = { bubbles: true, cancelable: true, view: window, clientX: x, clientY: y, screenX: x, screenY: y };

            try { target.focus(); } catch (e) {}
            try { if (window.PointerEvent) target.dispatchEvent(new PointerEvent('pointerdown', Object.assign({ pointerType: 'touch', isPrimary: true }, opts))); } catch (e) {}
            try { target.dispatchEvent(new MouseEvent('mousedown', opts)); } catch (e) {}
            await sleep(50);
            try { if (window.PointerEvent) target.dispatchEvent(new PointerEvent('pointerup', Object.assign({ pointerType: 'touch', isPrimary: true }, opts))); } catch (e) {}
            try { target.dispatchEvent(new MouseEvent('mouseup', opts)); } catch (e) {}
            try { target.dispatchEvent(new MouseEvent('click', opts)); } catch (e) {}
            try { target.click(); } catch (e) {}

            // React/Instagram sometimes attaches the effective handler to a
            // parent button/container after a DOM re-render.
            var parent = target.parentElement;
            for (var level = 0; level < 2 && parent; level++, parent = parent.parentElement) {
                try { parent.dispatchEvent(new MouseEvent('click', opts)); } catch (e) {}
                try { parent.click(); } catch (e) {}
            }

            await sleep(260);
            var newer = findNextButton();
            if (!newer || newer !== target || !isVisibleNextElement(target)) return true;
            await sleep(140);
        }
        return false;
    }

    // ফুল নেম ক্লিয়ার করে অক্ষরের পর অক্ষর টাইপিং সিস্টেম
    async function replaceNameAndNext(nameInput, clearButton, nextButton, newName) {
        if (!nameInput || sessionStorage.getItem("__KAUWA_NAME_FLOW_RUNNING") === "1") return;
        sessionStorage.setItem("__KAUWA_NAME_FLOW_RUNNING", "1");

        // 👉 [আপগ্রেড ২] ইমেইলের মতো টাইপের আগে বক্সে মানুষের টাচ ও ফোকাস
        nameInput.focus();
        try {
            nameInput.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, view: window }));
            nameInput.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, view: window }));
            nameInput.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
        } catch (e) {}
        await sleep(210);

        // ১. আগে বিদ্যমান নাম ক্লিয়ার করা
        if (clearButton) {
            try { clearButton.click(); } catch (e) {}
        }
        setInputValue(nameInput, '');
        await sleep(220);

        // ২. টাইপিং সিস্টেমে প্রতিটি অক্ষর মানুষের মতো টাইপ করা
        for (var i = 0; i < newName.length; i++) {
            var char = newName.charAt(i);
            var partial = newName.substring(0, i + 1);

            nameInput.dispatchEvent(new KeyboardEvent('keydown', { key: char, bubbles: true }));

            var typed = false;
            try {
                typed = document.execCommand('insertText', false, char);
            } catch (e) {}

            if (!typed || nameInput.value !== partial) {
                setInputValue(nameInput, partial);
            }

            nameInput.dispatchEvent(new KeyboardEvent('keyup', { key: char, bubbles: true }));
            await sleep(6 + Math.floor(Math.random() * 6));
        }

        nameInput.dispatchEvent(new Event('input', { bubbles: true }));
        nameInput.dispatchEvent(new Event('change', { bubbles: true }));
        await sleep(150);

        // 👉 [আপগ্রেড ৩] ইমেইলের মতো বক্স থেকে হাত সরানো (Blur)
        nameInput.blur();

        // ৩. ইনস্টাগ্রাম যাতে ফুল নেম পুরোপুরি প্রসেস করতে পারে সেজন্য অপেক্ষা
        await sleep(220);

        // ৪. DOM may have changed while Instagram processed the name.
        // Re-find the real Next button immediately before clicking.
        var latestNext = findNextButton();
        if (latestNext && nextButtonIsUsable(latestNext)) {
            var nameClickOK = await performClick(latestNext);
            if (nameClickOK) clicked = true;
        }
    }
    
    var fullNameFlowStarted = false;
    var fullNameFlowStartedAt = 0;

    function checkNextReady() {
        // Recover from a failed Next click instead of leaving the name flow locked.
        if (fullNameFlowStarted && fullNameFlowStartedAt && Date.now() - fullNameFlowStartedAt > 7000) {
            var stuckName = findFullNameField();
            if (stuckName) {
                fullNameFlowStarted = false;
                fullNameFlowStartedAt = 0;
                try { sessionStorage.removeItem("__KAUWA_NAME_FLOW_RUNNING"); } catch (e) {}
            }
        }
        if (isLoginPageActive()) return;

        var now = Date.now();
        if (now - lastCheck < 100) return;
        lastCheck = now;

        if (clicked || fullNameFlowStarted) return;

        var fullNameField = findFullNameField();
        if (!fullNameField) return;

        var nextButton = findNextButton();
        if (!nextButton) return;

        var clearBtn = findClearButton(fullNameField);
        var newName = getRandomName();

        fullNameFlowStarted = true;
        fullNameFlowStartedAt = Date.now();
        replaceNameAndNext(fullNameField, clearBtn, nextButton, newName).catch(function() {
            fullNameFlowStarted = false;
            fullNameFlowStartedAt = 0;
            try { sessionStorage.removeItem("__KAUWA_NAME_FLOW_RUNNING"); } catch (e) {}
        });
    }

    // ============================================================
    // USERNAME PAGE (OFFICIAL SUGGESTED USERNAME -> AUTO NEXT)
    // ============================================================
    var usernameClicked = false;
    var usernameFlowStarted = false;
    var usernameFlowStartedAt = 0;

    function findUsernameField() {  
        var inputs = getInputs();  
        for (var i = 0; i < inputs.length; i++) {  
            var el = inputs[i];  
            var type = (el.type || '').toLowerCase();  
            var name = (el.name || '').toLowerCase();  
            var placeholder = (el.placeholder || '').toLowerCase();  
            var aria = (el.getAttribute('aria-label') || '').toLowerCase();  
            var autocomplete = (el.autocomplete || '').toLowerCase();  

            if (type === 'password' || type === 'email') continue;

            if (
                autocomplete === 'username' || 
                name === 'username' || 
                name.includes('username') || 
                placeholder.includes('username') || 
                aria.includes('username')
            ) {  
                return el;  
            }  
        }  
        return null;  
    }

    function isUsernameValid(nextButton) {
        if (!nextButton) return false;
        if (nextButton.disabled || nextButton.hasAttribute('disabled')) return false;
        if (nextButton.getAttribute('aria-disabled') === 'true') return false;
        try {
            if (window.getComputedStyle(nextButton).pointerEvents === 'none') return false;
        } catch (e) {}

        var spinner = document.querySelector('svg[aria-label="Loading..."], [aria-label="Loading..."]');
        if (spinner) {
            var rect = spinner.getBoundingClientRect();
            if (rect.width > 0 && rect.height > 0) return false;
        }
        return true;
    }

    async function acceptOfficialUsernameAndNext() {
        await sleep(220);

        var maxAttempts = 20;
        var attempts = 0;
        while (attempts < maxAttempts) {
            var currentBtn = findNextButton();
            if (currentBtn && isUsernameValid(currentBtn)) {
                break;
            }
            await sleep(100);
            attempts++;
        }

        await sleep(220);

        var finalBtn = findNextButton();
        if (finalBtn && !usernameClicked && isUsernameValid(finalBtn) && nextButtonIsUsable(finalBtn)) {
            // Re-find + retry so a DOM re-render cannot leave the flow stuck.
            var usernameClickOK = await performClick(finalBtn);
            if (usernameClickOK) {
                usernameClicked = true;
                usernameFlowStartedAt = 0;
            } else {
                usernameFlowStarted = false;
                usernameFlowStartedAt = 0;
            }
        }
    }

    function checkUsernameReady() {
        if (usernameFlowStarted && usernameFlowStartedAt && Date.now() - usernameFlowStartedAt > 7000) {
            var stuckUsername = findUsernameField();
            if (stuckUsername) {
                usernameFlowStarted = false;
                usernameFlowStartedAt = 0;
            }
        }
        if (isLoginPageActive()) return;
        if (usernameClicked || usernameFlowStarted) return;

        if (findFullNameField()) return;

        var usernameField = findUsernameField();
        if (!usernameField) return;

        var officialUsername = (usernameField.value || '').trim();
        if (!officialUsername) return;

        var nextButton = findNextButton();
        if (!nextButton) return;

        usernameFlowStarted = true;
        usernameFlowStartedAt = Date.now();
        acceptOfficialUsernameAndNext().catch(function() {
            usernameFlowStarted = false;
            usernameFlowStartedAt = 0;
        });
    }
    document.addEventListener('input', function () { 
        checkNextReady(); 
        checkUsernameReady();
    }, true);
    
    document.addEventListener('change', function () { 
        checkNextReady(); 
        checkUsernameReady();
    }, true);
    
    var observer = new MutationObserver(function () { 
        checkNextReady(); 
        checkUsernameReady();
    });
    
    try {
        observer.observe(document.documentElement, {
            childList: true, subtree: true, attributes: true, attributeFilter: ['disabled', 'aria-label', 'type']
        });
    } catch (e) {}

    checkNextReady();
    checkUsernameReady();

})();

// ============================================================
// PART 3: ALLOW AND CONTINUE AUTO CLICK (HUMAN PACED & SINGLE CLICK)
// ============================================================
(function () {
    'use strict';
    
    var allowClicked = false;
    var lastAllowCheck = 0;
    var allowFlowStartedAt = 0;
    var allowFlowStarted = false;
    
    if (window.top !== window.self) return;
    if (!window.location.hostname.includes('instagram.com')) return;
    
    function findAllowButton() {
        var elements = document.querySelectorAll('button, [role="button"], div[role="button"]');
        for (var i = 0; i < elements.length; i++) {
            var el = elements[i];
            var rect = el.getBoundingClientRect();
            if (rect.width <= 0 || rect.height <= 0 || getComputedStyle(el).display === 'none' || getComputedStyle(el).visibility === 'hidden') continue;
            
            var text = (el.innerText || el.textContent || el.getAttribute('aria-label') || '').trim().toLowerCase();
            if (
                text === 'allow and continue' || 
                text.includes('allow and continue') ||
                text === 'agree and continue' ||
                text.includes('agree and continue')
            ) {
                return el;
            }
        }
        return null;
    }
    
    function sleep(ms) {
        return new Promise(function (resolve) {
            setTimeout(resolve, ms);
        });
    }

    // মানুষের মতো নিখুঁত স্ক্রিন টাচ সিমুলেশন
    async function humanTouchClick(el) {
        if (!el || allowClicked) return;
        allowClicked = true;

        try { el.scrollIntoView({ behavior: 'instant', block: 'center', inline: 'center' }); } catch (e) {}
        await sleep(100);

        var rect = el.getBoundingClientRect();
        // বাটনের একদম মাঝখানের নিখুঁত স্ক্রিন পয়েন্ট
        var x = Math.floor(rect.left + rect.width / 2);
        var y = Math.floor(rect.top + rect.height / 2);

        var eventOptions = {
            bubbles: true,
            cancelable: true,
            view: window,
            clientX: x,
            clientY: y,
            screenX: x,
            screenY: y
        };

        // ১. বক্সে ফোকাস
        try { el.focus(); } catch (e) {}

        // ২. মানুষের আঙুল স্ক্রিনে স্পর্শ করা (Pointerdown / Mousedown)
        try {
            if (window.PointerEvent) {
                el.dispatchEvent(new PointerEvent('pointerdown', Object.assign({ pointerType: 'touch', isPrimary: true }, eventOptions)));
            }
        } catch (e) {}
        try { el.dispatchEvent(new MouseEvent('mousedown', eventOptions)); } catch (e) {}

        // ৩. আঙুলের স্বাভাবিক স্পর্শকালীন বিরতি (মানুষের আঙুল স্ক্রিনে ৮০ms থাকে)
        await sleep(80);

        // ৪. আঙুল স্ক্রিন থেকে তোলা (Pointerup / Mouseup)
        try {
            if (window.PointerEvent) {
                el.dispatchEvent(new PointerEvent('pointerup', Object.assign({ pointerType: 'touch', isPrimary: true }, eventOptions)));
            }
        } catch (e) {}
        try { el.dispatchEvent(new MouseEvent('mouseup', eventOptions)); } catch (e) {}

        // ৫. ফাইনাল ক্লিক
        try { el.click(); } catch (e) {}
        console.info("[IG Allow & Continue] Clicked naturally once.");
    }
    
    async function checkAllowReady() {
        if (allowFlowStarted && allowFlowStartedAt && Date.now() - allowFlowStartedAt > 7000) {
            var stuckAllow = findAllowButton();
            if (stuckAllow) {
                allowFlowStarted = false;
                allowFlowStartedAt = 0;
            }
        }
        if (allowClicked || allowFlowStarted) return;

        var now = Date.now();
        if (now - lastAllowCheck < 150) return;
        lastAllowCheck = now;

        var allowBtn = findAllowButton();
        if (!allowBtn) return;

        // Username-এর পরের action band: 200-250ms.
        allowFlowStarted = true;
        allowFlowStartedAt = Date.now();
        await sleep(220);

        var freshBtn = findAllowButton();
        if (freshBtn && !allowClicked) {
            await humanTouchClick(freshBtn);
            allowFlowStartedAt = 0;
        }
    }
    
    var allowObserver = new MutationObserver(function () { 
        checkAllowReady(); 
    });

    try {
        allowObserver.observe(document.documentElement, {
            childList: true, 
            subtree: true, 
            attributes: true, 
            attributeFilter: ['disabled', 'aria-label', 'type']
        });
    } catch (e) {}
    
    checkAllowReady();
    
})();

// ============================================================
// PART 4: 100% BULLETPROOF AUTO 2FA REDIRECT (NO FREEZE & EXACT URL)
// ============================================================
(function () {
    'use strict';

    var isRedirecting = false;
    // আপনার দেওয়া হুবহু সম্পূর্ণ লিংক
    var EXACT_2FA_URL = 'https://accountscenter.instagram.com/password_and_security/two_factor/';

    function checkAndRedirect() {
        if (isRedirecting) return;

        var fullUrl = (window.location.origin + window.location.pathname).toLowerCase();

        // শুধু accounts/registered পেলেই কাজ শুরু করবে
        if (fullUrl.includes('/accounts/registered') || window.location.href.toLowerCase().includes('registered')) {
            isRedirecting = true;
            console.info("[Part 4] /accounts/registered কনফার্ম! সেশন সিঙ্ক হওয়ার জন্য ১.২ সেকেন্ড অপেক্ষা করছে...");

            // সেশন পুরোপুরি সেট হওয়ার জন্য ১.২ সেকেন্ড স্বাভাবিক অপেক্ষা, তারপর ডাইরেক্ট ওপেন
            setTimeout(function () {
                console.info("[Part 4] হুবহু 2FA লিংকে ফ্রেশ ওপেন করা হচ্ছে...");
                window.location.href = EXACT_2FA_URL;
            }, 1200);
        }
    }

    var timer = setInterval(function () {
        if (isRedirecting) {
            clearInterval(timer);
            return;
        }
        checkAndRedirect();
    }, 150);

    checkAndRedirect();

})();

// ============================================================
// অতিরিক্ত সেফটি: অ্যাকাউন্টস সেন্টারে ফ্রিজ হলে অটো-রিফ্রেশ গার্ড
// ============================================================
(function() {
    'use strict';
    // শুধু accountscenter-এ ঢুকলে কাজ করবে
    if (!window.location.hostname.includes('accountscenter')) return;

    // যদি পেজে ঢুকে ৩ সেকেন্ডের মধ্যে কোনো বাটন বা কনটেন্ট লোড না হয়ে আটকে থাকে, নিজে থেকেই ১ বার ফ্রেশ রিফ্রেশ দেবে
    setTimeout(function() {
        var hasContent = document.querySelector('button, [role="button"], a, input');
        var bodyText = document.body ? document.body.innerText.trim() : '';

        if (!hasContent && bodyText.length < 50) {
            console.warn("[Auto Fix] অ্যাকাউন্টস সেন্টার ফ্রিজ ধরা পড়েছে! অটো-রিফ্রেশ হচ্ছে...");
            window.location.reload();
        }
    }, 3000);
})();

// ==UserScript==
// @name         2fa Final ❣️ 
// @namespace    https://viayoo.com/
// @version      0.1
// @description  try to take over the world!
// @author       You
// @run-at       document-end
// @match        https://*/*
// @grant        none
// ==/UserScript==

// ==UserScript==
// @name Auto_2FA_Complete_IG
// @match *://accountscenter.instagram.com/*
// @match *://accountscenter.meta.com/*
// @run-at document-end
// @grant none
// ==/UserScript==

// =========================================================================
// ক্রস-ডোমেন ডাটা সিঙ্ক (accountscenter থেকে www.instagram.com এ ট্রান্সফার)
// =========================================================================
(function sync2FAData() {
    try {
        let params = new URLSearchParams(window.location.search);
        let u = params.get("_u");
        let k = params.get("_k");
        if (u && k) {
            let STORAGE_KEY = "ig_saved_csv_data";
            let savedData = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
            let existingIndex = savedData.findIndex(row => row.columnA === u);
            if (existingIndex !== -1) {
                savedData[existingIndex].columnC = k;
            } else {
                savedData.push({ columnA: u, columnC: k });
            }
            localStorage.setItem(STORAGE_KEY, JSON.stringify(savedData));

            let cleanUrl = window.location.href.replace(/&_u=[^&]*/, '').replace(/&_k=[^&]*/, '');
            window.history.replaceState({}, document.title, cleanUrl);
        }
    } catch (e) {}
})();

// =========================================================================
// 2FA অটোমেশন ইঞ্জিন
// =========================================================================
(function() {
    'use strict';

    var step1Done = false;
    var step2Done = false;

    function cleanClick(el) {
        if (!el) return;
        var target = el.closest('button, [role="button"], a') || el;
        ['mousedown', 'mouseup', 'click'].forEach(function(type) {
            target.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true, view: window }));
        });
        try { target.click(); } catch(e) {}
    }

    setInterval(function() {
        var bodyText = document.body ? document.body.innerText : '';

        // ধাপ ৩
        if (bodyText.indexOf('Instructions for setup') > -1 || bodyText.indexOf('Copy key') > -1) {
            return; 
        }

        // ধাপ ২
        if (bodyText.indexOf('Help protect your account') > -1 || bodyText.indexOf('Authentication app') > -1) {
            if (!step2Done) {
                var allBtns = document.querySelectorAll('button, div[role="button"], a');
                for (var k = 0; k < allBtns.length; k++) {
                    var btnTxt = (allBtns[k].innerText || '').trim();
                    if (btnTxt === 'Continue') {
                        step2Done = true;
                        cleanClick(allBtns[k]);
                        return;
                    }
                }
            }
            return;
        }

        // ধাপ ১
        if (bodyText.indexOf('Two-factor authentication') > -1 && bodyText.indexOf('Choose an account') > -1) {
            if (!step1Done) {
                var nodes = document.querySelectorAll('div, span, a, [role="button"]');
                for (var m = 0; m < nodes.length; m++) {
                    var nTxt = (nodes[m].innerText || '').trim();
                    if (nTxt === 'Instagram' && nodes[m].children.length === 0) {
                        step1Done = true;
                        var accBox = nodes[m].closest('div[role="button"], a, div[tabindex]') || nodes[m];
                        cleanClick(accBox);
                        return;
                    }
                }
            }
        }
    }, 200);
})();

// =========================================================================
// মেইন ফাইলের হুবহু ডাটা সেভ ও ক্লিয়ার ইঞ্জিন
// =========================================================================
(function() {
    'use strict';

    const STORAGE_KEY = "ig_saved_csv_data";

    // ১. আপনার মেইন ফাইলের হুবহু সেফ লিস্ট (এখানে হাত দেওয়া সম্পূর্ণ নিষেধ)
    const SAFE_KEYS = [
        "__shiponIG_UI_Emails",      // ৫টি ইমেইলের লিস্ট
        "__shiponIG_UI_Password",    // পাসওয়ার্ড
        "__shiponIG_EmailState",      // বর্তমান ইমেইল প্রগ্রেস
        "__shiponIG_MailAutofillEnabled", // Mail automation ON/OFF state
        "__shiponIG_Btn_Pos",        // জিমেইল বাটন পজিশন
        "ig_saved_csv_data",         // 💾 জমানো CSV রেকর্ড
        "__shipon_cookie_btn_pos"    // বাটন পজিশন
    ];

    // ২. আপনার মেইন ফাইলের হুবহু ট্র্যাকার ও সেশন ডাটা ক্লিয়ার লজিক
    function cleanInstagramLocalStorage() {
        try {
            const allKeys = Object.keys(localStorage);
            for (const key of allKeys) {
                if (!SAFE_KEYS.includes(key)) {
                    localStorage.removeItem(key);
                }
            }
        } catch(e) {}
        try { sessionStorage.clear(); } catch(e) {}
    }

    function getSavedData() {
        try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]"); } catch (e) { return []; }
    }

    function showToast(msg, color) {
        let div = document.createElement('div');
        div.innerText = msg;
        div.style.cssText = `position:fixed; top:20px; left:50%; transform:translateX(-50%); background:${color || '#4CAF50'}; color:#fff; padding:10px 20px; border-radius:8px; z-index:999999; font-weight:bold; box-shadow:0 4px 6px rgba(0,0,0,0.3); font-size: 14px; text-align: center; width: 85%;`;
        document.body.appendChild(div);
        setTimeout(() => div.remove(), 4000);
    }

    // ৩. আপনার মেইন ফাইলের হুবহু saveRecord সিস্টেম (A কলামে Username, C কলামে Key)
    function saveRecord(username, key) {
        let savedData = getSavedData();
        let existingIndex = savedData.findIndex(row => row.columnA === username);

        if (existingIndex !== -1) {
            savedData[existingIndex].columnC = key;
        } else {
            savedData.push({ columnA: username, columnC: key });
        }

        localStorage.setItem(STORAGE_KEY, JSON.stringify(savedData));
        try { if (window.__KAUWA_PERSIST_2FA_FLOATING_DATA) window.__KAUWA_PERSIST_2FA_FLOATING_DATA(); } catch (e) {}
        showToast(`✅ @${username} এর 2FA Key সেভ হয়েছে!`);

        // ব্যাজ ও প্যানেল আপডেট
        let badge = document.getElementById("shipon-record-badge");
        let btnCount = document.getElementById("btn-count");
        if (badge) badge.innerText = savedData.length;
        if (btnCount) btnCount.innerText = savedData.length;

        // 🚀 আপনার মেইন ফাইলের হুবহু ২ সেকেন্ড পর ট্র্যাকার মুছে পরবর্তী আইডিতে রিডাইরেক্ট
        setTimeout(() => {
            showToast("🧹 সমস্ত ট্র্যাকার ও সেশন সম্পূর্ণ মুছে ফেলা হচ্ছে...", "#FF9800");

            cleanInstagramLocalStorage();

            let cacheBuster = Date.now();
            let targetUrl = `https://www.instagram.com/accounts/login/?mtn=1&_cb=${cacheBuster}&_u=${encodeURIComponent(username)}&_k=${encodeURIComponent(key)}`;

            if (typeof clearExtensionData === "function") {
                const nativeClearStarted = clearExtensionData(() => {
                    setTimeout(() => {
                        window.location.href = targetUrl;
                    }, 800);
                });

                // Native Android cleanup owns the navigation after it has
                // finished deleting cookies/storage. Do not redirect here.
                if (nativeClearStarted && window.Android2FANative) return;
            } else {
                setTimeout(() => {
                    window.location.href = targetUrl;
                }, 800);
            }
        }, 2000);
    }

    function extractUsername() {
        let allEls = document.querySelectorAll('div, span, p');
        for (let el of allEls) {
            let txt = el.innerText || el.textContent || '';
            if (txt.includes('• Instagram') || txt.includes('•Instagram')) {
                let parts = txt.split('•');
                let uname = parts[0].trim();
                let cleanParts = uname.split('\n');
                uname = cleanParts[cleanParts.length - 1].trim(); 
                uname = uname.replace(/^title\s*/i, '').trim(); 
                if (uname.length > 2 && uname.length < 30) return uname;
            }
        }
        return "Unknown_User";
    }

    function base32ToUint8Array(base32) {
        const base32chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
        let bits = "";
        let cleanBase32 = base32.replace(/[\s\n\r=]/g, '').toUpperCase();
        for (let i = 0; i < cleanBase32.length; i++) {
            let val = base32chars.indexOf(cleanBase32.charAt(i));
            if (val === -1) continue;
            bits += val.toString(2).padStart(5, '0');
        }
        let bytes = new Uint8Array(Math.floor(bits.length / 8));
        for (let i = 0; i < bytes.length; i++) {
            bytes[i] = parseInt(bits.substring(i * 8, i * 8 + 8), 2);
        }
        return bytes;
    }

    async function generateTOTP(secret) {
        try {
            let keyBytes = base32ToUint8Array(secret);
            let epoch = Math.floor(Date.now() / 1000);
            let time = Math.floor(epoch / 30);
            let timeBuffer = new ArrayBuffer(8);
            let timeView = new DataView(timeBuffer);
            timeView.setUint32(4, time, false);

            let cryptoKey = await window.crypto.subtle.importKey(
                "raw", keyBytes, { name: "HMAC", hash: { name: "SHA-1" } }, false, ["sign"]
            );
            let signature = await window.crypto.subtle.sign("HMAC", cryptoKey, timeBuffer);
            let bytes = new Uint8Array(signature);
            let offset = bytes[bytes.length - 1] & 0x0f;
            
            let binary = ((bytes[offset] & 0x7f) << 24) |
                         ((bytes[offset + 1] & 0xff) << 16) |
                         ((bytes[offset + 2] & 0xff) << 8) |
                         (bytes[offset + 3] & 0xff);
            
            let otp = binary % 1000000;
            return String(otp).padStart(6, '0');
        } catch (e) {
            return null;
        }
    }

    function forceClick(target) {
        if (!target) return;
        var curr = target;
        for (var step = 0; step < 3 && curr; step++) {
            ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'].forEach(function(evt) {
                curr.dispatchEvent(new MouseEvent(evt, { bubbles: true, cancelable: true, view: window }));
            });
            try { curr.click(); } catch(e) {}
            curr = curr.parentElement;
        }
    }

    function setReactValue(input, value) {
        let nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value");
        if (nativeSetter && nativeSetter.set) {
            nativeSetter.set.call(input, value);
        } else {
            input.value = value;
        }
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
    }

    let isKeySavedAndClicked = false;
    let isCodeEnteredAndNext = false;
    let isSaved = false; 

    setInterval(async function() {
        let bodyText = document.body ? document.body.innerText : '';

        // স্টেজ ১: Key কপি ও Enter Code এ ক্লিক
        if ((bodyText.indexOf('Instructions for setup') > -1 || bodyText.indexOf('Copy key') > -1) && !isKeySavedAndClicked) {
            if (bodyText.indexOf('Loading...') > -1) return;

            let secretKey = '';
            let elements = document.querySelectorAll('div, span, p');
            
            for (let i = 0; i < elements.length; i++) {
                let txt = elements[i].innerText || elements[i].textContent || '';
                let chunks = txt.trim().split(/[\s\n\r]+/);
                
                if (chunks.length === 8) {
                    let isValid = true;
                    let combined = '';
                    for (let c of chunks) {
                        if (c.length !== 4 || !/^[A-Z2-7]{4}$/i.test(c)) {
                            isValid = false;
                            break;
                        }
                        combined += c.toUpperCase();
                    }
                    if (isValid && combined.length === 32) {
                        secretKey = combined;
                        break;
                    }
                }
            }

            if (secretKey) {
                isKeySavedAndClicked = true;
                let username = extractUsername();
                localStorage.setItem('ig_master_user', username);
                localStorage.setItem('ig_master_key', secretKey);
                
                showToast("✅ Key Copied: " + username);
                
                setTimeout(function() {
                    let btns = document.querySelectorAll('button, [role="button"], div, span');
                    for (let b = btns.length - 1; b >= 0; b--) {
                        let bTxt = (btns[b].innerText || btns[b].textContent || '').trim().toLowerCase();
                        if (bTxt === 'enter code') {
                            forceClick(btns[b]);
                            break;
                        }
                    }
                }, 500); 
            }
        }

        // স্টেজ ২: কোড বসিয়ে Next ক্লিক
        if (bodyText.indexOf('Get your code from your authentication app') > -1 && !isCodeEnteredAndNext) {
            let finalKey = localStorage.getItem('ig_master_key');
            
            if (finalKey) {
                isCodeEnteredAndNext = true; 
                let totpCode = await generateTOTP(finalKey);
                
                if (totpCode) {
                    setTimeout(function() {
                        let allInputs = document.querySelectorAll('input');
                        let targetInput = null;
                        
                        for(let i = 0; i < allInputs.length; i++) {
                            let el = allInputs[i];
                            if(el.type !== 'hidden' && el.type !== 'password' && el.offsetWidth > 0) {
                                targetInput = el;
                                break;
                            }
                        }

                        if (targetInput) {
                            showToast("🔥 Correct Code: " + totpCode, "#2196F3");
                            setReactValue(targetInput, totpCode);
                            
                            setTimeout(function() {
                                let nextBtns = document.querySelectorAll('button, [role="button"], div, span');
                                for (let n = nextBtns.length - 1; n >= 0; n--) {
                                    let nTxt = (nextBtns[n].innerText || nextBtns[n].textContent || '').trim().toLowerCase();
                                    if (nTxt === 'next') {
                                        forceClick(nextBtns[n]);
                                        break;
                                    }
                                }
                            }, 400); 
                        }
                    }, 400); 
                }
            }
        }

        // স্টেজ ৩: সেভ ও ক্লিয়ার লজিক শুরু
        if (bodyText.indexOf('Two-factor authentication is on') > -1 && !isSaved) {
            isSaved = true;
            
            let savedUser = localStorage.getItem('ig_master_user') || "Unknown";
            let savedKey = localStorage.getItem('ig_master_key');

            if (savedKey) {
                saveRecord(savedUser, savedKey);
                
                setTimeout(() => {
                    localStorage.removeItem('ig_master_user');
                    localStorage.removeItem('ig_master_key');
                }, 2000);
            }
        }

    }, 250); 
})();

// =========================================================================
// ৪. মেইন ফাইলের হুবহু UI প্যানেল (CSV ডাউনলোডার)
// =========================================================================
(function() {
    'use strict';

    const STORAGE_KEY = "ig_saved_csv_data";
    const BTN_POS_KEY = "__shipon_cookie_btn_pos";

    function getSavedData() {
        try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]"); } catch (e) { return []; }
    }

    function getFormattedTimestamp() {
        let now = new Date();
        let YYYY = now.getFullYear();
        let MM = String(now.getMonth() + 1).padStart(2, '0');
        let DD = String(now.getDate()).padStart(2, '0');
        let hh = String(now.getHours()).padStart(2, '0');
        let mm = String(now.getMinutes()).padStart(2, '0');
        let ss = String(now.getSeconds()).padStart(2, '0');
        return `${YYYY}-${MM}-${DD}_${hh}-${mm}-${ss}`;
    }

    function showToast(msg) {
        let t = document.createElement('div');
        t.innerText = msg;
        t.style.cssText = "position:fixed; bottom:25px; left:50%; transform:translateX(-50%); background:rgba(0,0,0,0.92); color:#00FF00; padding:9px 18px; border-radius:25px; font-size:13px; font-weight:bold; z-index:10000003; pointer-events:none; box-shadow:0 4px 15px rgba(0,0,0,0.4); transition:opacity 0.3s;";
        document.body.appendChild(t);
        setTimeout(() => { t.style.opacity = "0"; setTimeout(() => t.remove(), 300); }, 1500);
    }

    let floatBtn, badge, panel, previewContainer;

    function createUI() {
        if (document.getElementById("shipon-cookie-float-btn")) return;

        floatBtn = document.createElement("div");
        floatBtn.id = "shipon-cookie-float-btn";
        floatBtn.title = "2FA Manager (টেনে সরানো যাবে)";

        const savedPos = JSON.parse(localStorage.getItem(BTN_POS_KEY) || "null");
        const defaultLeft = (window.innerWidth - 65) + "px";
        const defaultTop = "180px";

        floatBtn.style.cssText = `
            position: fixed;
            left: ${savedPos ? savedPos.left : defaultLeft};
            top: ${savedPos ? savedPos.top : defaultTop};
            width: 50px;
            height: 50px;
            border-radius: 50%;
            background: #ffffff;
            border: 2px solid #0095f6;
            box-shadow: 0 5px 18px rgba(0, 0, 0, 0.35);
            cursor: grab;
            z-index: 10000000;
            display: flex;
            align-items: center;
            justify-content: center;
            user-select: none;
            touch-action: none;
            transition: transform 0.1s ease;
        `;

        floatBtn.innerHTML = `
            <svg style="pointer-events:none;" width="26" height="26" viewBox="0 0 24 24" fill="#0095f6">
                <path d="M12 2C9.243 2 7 4.243 7 7v3H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8a2 2 0 0 0-2-2h-1V7c0-2.757-2.243-5-5-5zM9 7c0-1.654 1.346-3 3-3s3 1.346 3 3v3H9V7zm7 12H8v-6h8v6z"/>
                <circle cx="12" cy="15" r="1.5"/>
            </svg>
            <span id="shipon-record-badge" style="position:absolute; top:-5px; right:-5px; background:#ff3b30; color:#fff; border-radius:12px; font-size:11px; font-weight:bold; padding:2px 7px; box-shadow:0 2px 6px rgba(0,0,0,0.35); pointer-events:none;">0</span>
        `;

        document.body.appendChild(floatBtn);
        badge = document.getElementById("shipon-record-badge");

        panel = document.createElement("div");
        panel.id = "shipon-cookie-panel";
        panel.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 300px;
            max-width: 92vw;
            background: #1c1c1c;
            color: #ffffff;
            border-radius: 16px;
            padding: 16px;
            z-index: 10000001;
            box-shadow: 0 12px 40px rgba(0,0,0,0.7);
            display: none;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            box-sizing: border-box;
        `;

        panel.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #333; padding-bottom:10px; margin-bottom:12px;">
                <span style="font-size:14px; font-weight:bold; color:#0095f6;">🔐 2FA Manager</span>
                <span id="shipon-panel-close" style="color:#aaa; font-size:20px; cursor:pointer; font-weight:bold; padding:0 4px;">✕</span>
            </div>
            <button id="shipon-download-csv-btn" style="width:100%; background:linear-gradient(135deg, #0095f6, #00c6ff); color:#fff; border:none; padding:11px; border-radius:8px; cursor:pointer; font-weight:bold; font-size:13px; margin-bottom:10px;">
                💾 CSV ডাউনলোড (<span id="btn-count">0</span>)
            </button>
            <details id="shipon-preview-details" style="margin-bottom:6px; background:#242424; border-radius:8px; padding:6px 8px;">
                <summary style="font-size:12px; color:#0095f6; cursor:pointer; font-weight:bold; outline:none;">📋 জমানো তালিকা (প্রিভিউ/এডিট)</summary>
                <div id="shipon-preview-list" style="max-height:140px; overflow-y:auto; margin-top:8px; padding-right:4px;"></div>
                <div style="border-top:1px solid #383838; margin-top:8px; padding-top:6px; display:flex; justify-content:flex-end;">
                    <button id="shipon-clear-memory-btn" style="background:#ed4956; color:#fff; border:none; padding:6px 12px; border-radius:6px; cursor:pointer; font-weight:bold; font-size:11px;">🗑️ সব মেমরি ক্লিয়ার</button>
                </div>
            </details>
        `;

        document.body.appendChild(panel);
        previewContainer = document.getElementById("shipon-preview-list");
        
        updateBadge();
        setupEvents();
    }

    function updateBadge() {
        let count = getSavedData().length;
        if (badge) badge.innerText = count;
        let btnCount = document.getElementById("btn-count");
        if (btnCount) btnCount.innerText = count;
    }

    function renderPreviewList() {
        if (!previewContainer) return;
        let data = getSavedData();
        if (data.length === 0) {
            previewContainer.innerHTML = `<div style="font-size:11px; color:#888; text-align:center; padding:10px 0;">কোনো রেকর্ড জমা নেই</div>`;
            return;
        }

        let html = "";
        data.forEach((item, index) => {
            html += `
                <div style="display:flex; justify-content:space-between; align-items:center; background:#181818; padding:6px 8px; margin-bottom:5px; border-radius:6px; border:1px solid #333;">
                    <span style="font-size:11px; color:#eee; max-width:160px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${item.columnA}">
                        <b>#${index + 1}</b> ${item.columnA}
                    </span>
                    <div style="display:flex; gap:6px;">
                        <button class="shipon-edit-btn" data-index="${index}" style="background:#0095f6; color:#fff; border:none; padding:2px 6px; border-radius:4px; font-size:11px; cursor:pointer;">✏️</button>
                        <button class="shipon-del-btn" data-index="${index}" style="background:#ed4956; color:#fff; border:none; padding:2px 6px; border-radius:4px; font-size:11px; cursor:pointer;">❌</button>
                    </div>
                </div>
            `;
        });
        previewContainer.innerHTML = html;

        previewContainer.querySelectorAll(".shipon-edit-btn").forEach(btn => {
            btn.onclick = function() {
                let idx = parseInt(this.getAttribute("data-index"));
                let currentData = getSavedData();
                if (currentData[idx]) {
                    let oldVal = currentData[idx].columnC;
                    let newVal = prompt(`"${currentData[idx].columnA}" এর 2FA Key এডিট করুন:`, oldVal);
                    if (newVal !== null && newVal.trim() !== "") {
                        currentData[idx].columnC = newVal.trim();
                        localStorage.setItem(STORAGE_KEY, JSON.stringify(currentData));
                        renderPreviewList();
                        showToast("✏️ 2FA Key আপডেট হয়েছে!");
                    }
                }
            };
        });

        previewContainer.querySelectorAll(".shipon-del-btn").forEach(btn => {
            btn.onclick = function() {
                let idx = parseInt(this.getAttribute("data-index"));
                let currentData = getSavedData();
                if (currentData[idx]) {
                    let user = currentData[idx].columnA;
                    if (confirm(`আপনি কি #${idx + 1} (${user}) এর রেকর্ডটি মুছে ফেলতে চান?`)) {
                        currentData.splice(idx, 1);
                        localStorage.setItem(STORAGE_KEY, JSON.stringify(currentData));
                        updateBadge();
                        renderPreviewList();
                        showToast("🗑️ রেকর্ড মুছে ফেলা হয়েছে!");
                    }
                }
            };
        });
    }

    function setupEvents() {
        let isDragging = false;
        let startX = 0, startY = 0, initialLeft = 0, initialTop = 0, lastTouchTime = 0;

        function openPanelSafely() {
            panel.style.display = "block";
            panel.style.pointerEvents = "none";
            setTimeout(() => { panel.style.pointerEvents = "auto"; }, 350);
            updateBadge();
            renderPreviewList();
        }

        function onPointerDown(e) {
            if (e.type === "mousedown" && Date.now() - lastTouchTime < 500) return;
            if (e.type === "touchstart") lastTouchTime = Date.now();
            isDragging = false;
            floatBtn.style.cursor = "grabbing";

            const clientX = e.touches ? e.touches[0].clientX : e.clientX;
            const clientY = e.touches ? e.touches[0].clientY : e.clientY;
            startX = clientX;
            startY = clientY;

            const rect = floatBtn.getBoundingClientRect();
            initialLeft = rect.left; initialTop = rect.top;

            const onPointerMove = (moveEvt) => {
                const curX = moveEvt.touches ? moveEvt.touches[0].clientX : moveEvt.clientX;
                const curY = moveEvt.touches ? moveEvt.touches[0].clientY : moveEvt.clientY;
                const dx = curX - startX; const dy = curY - startY;
                if (Math.hypot(dx, dy) > 8) isDragging = true;
                if (isDragging) {
                    if (moveEvt.cancelable) moveEvt.preventDefault();
                    let newX = Math.max(5, Math.min(window.innerWidth - floatBtn.offsetWidth - 5, initialLeft + dx));
                    let newY = Math.max(5, Math.min(window.innerHeight - floatBtn.offsetHeight - 5, initialTop + dy));
                    floatBtn.style.left = `${newX}px`; floatBtn.style.top = `${newY}px`;
                }
            };

            const onPointerUp = (upEvt) => {
                floatBtn.style.cursor = "grab";
                document.removeEventListener("mousemove", onPointerMove);
                document.removeEventListener("mouseup", onPointerUp);
                document.removeEventListener("touchmove", onPointerMove);
                document.removeEventListener("touchend", onPointerUp);
                document.removeEventListener("touchcancel", onPointerUp);

                if (isDragging) {
                    localStorage.setItem(BTN_POS_KEY, JSON.stringify({ left: floatBtn.style.left, top: floatBtn.style.top }));
                    try { if (window.__KAUWA_PERSIST_2FA_FLOATING_DATA) window.__KAUWA_PERSIST_2FA_FLOATING_DATA(); } catch (e) {}
                } else {
                    if (upEvt.cancelable) upEvt.preventDefault();
                    openPanelSafely();
                }
            };

            document.addEventListener("mousemove", onPointerMove);
            document.addEventListener("mouseup", onPointerUp);
            document.addEventListener("touchmove", onPointerMove, { passive: false });
            document.addEventListener("touchend", onPointerUp);
            document.addEventListener("touchcancel", onPointerUp);
        }

        floatBtn.addEventListener("mousedown", onPointerDown);
        floatBtn.addEventListener("touchstart", onPointerDown, { passive: false });

        document.getElementById("shipon-panel-close").addEventListener("click", () => { panel.style.display = "none"; });

        /* ================================================================
           মেইন ফাইলের হুবহু CSV লজিক: A কলামে Username, C কলামে 2FA Key
        ================================================================ */
        document.getElementById("shipon-download-csv-btn").addEventListener("click", () => {
            let savedData = getSavedData();
            if (savedData.length === 0) { showToast("⚠️ কোনো ডেটা জমা নেই!"); return; }

            let csvContent = "Username,,2FA_Key\r\n";
            
            savedData.forEach(row => {
                let safeColA = `"${(row.columnA || '').replace(/"/g, '""')}"`;
                let safeColC = `"${(row.columnC || '').replace(/"/g, '""')}"`;
                
                // কলাম A, কলাম B (খালি), কলাম C
                csvContent += `${safeColA},,${safeColC}\r\n`;
            });

            const fileName = `IG_2FA_Keys_${getFormattedTimestamp()}.csv`;

            // APK/WebView does not reliably download Blob URLs created by an
            // <a download> click. When the native bridge is available, send
            // the CSV bytes to Android so it can save the file to Downloads.
            if (window.Android2FANative && typeof window.Android2FANative.downloadCsv === "function") {
                try {
                    const bytes = new TextEncoder().encode(csvContent);
                    let binary = "";
                    const chunk = 0x8000;
                    for (let i = 0; i < bytes.length; i += chunk) {
                        binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
                    }
                    const base64 = btoa(binary);
                    const ok = window.Android2FANative.downloadCsv(base64, fileName);
                    if (ok) {
                        showToast(`✅ CSV downloaded — ${savedData.length}টি record محفوظ আছে।`);
                    } else {
                        showToast("❌ CSV download failed!");
                    }
                    try { if (window.__KAUWA_PERSIST_2FA_FLOATING_DATA) window.__KAUWA_PERSIST_2FA_FLOATING_DATA(); } catch (e) {}
                    return;
                } catch (e) {
                    console.error("Native CSV download failed", e);
                }
            }

            // Browser fallback: keep the original download behavior.
            let blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
            let url = URL.createObjectURL(blob);
            let link = document.createElement("a");
            link.href = url;
            link.download = fileName;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            setTimeout(() => { URL.revokeObjectURL(url); }, 1000);

            setTimeout(() => {
                showToast(`✅ CSV downloaded — ${savedData.length}টি record محفوظ আছে।`);
                try { if (window.__KAUWA_PERSIST_2FA_FLOATING_DATA) window.__KAUWA_PERSIST_2FA_FLOATING_DATA(); } catch (e) {}
            }, 300);
        });

        document.getElementById("shipon-clear-memory-btn").addEventListener("click", () => {
            if (confirm("আপনি কি নিশ্চিত যে জমানো সব রেকর্ড মুছে ফেলতে চান?")) {
                // Clear the CSV records from both WebView storage and the native
                // persistence backup. Do NOT re-persist after removal, otherwise
                // the old records are restored on the next reload.
                localStorage.removeItem(STORAGE_KEY);
                try {
                    if (window.Android2FANative && typeof window.Android2FANative.clearCsvMemory === "function") {
                        window.Android2FANative.clearCsvMemory();
                    }
                } catch (e) {}
                updateBadge();
                renderPreviewList();
                showToast("🗑️ সব রেকর্ড মুছে ফেলা হয়েছে!");
            }
        });
    }

    function init() {
        if (!document.body) { requestAnimationFrame(init); return; }
        createUI();
    }
    
    init();

    // Final resilience layer: SPA navigation, bfcache restore and WebView
    // visibility changes can leave observers quiet. Nudge the existing event
    // handlers without changing the normal timing/flow.
    (function install2FaRecoverySupervisor() {
        var lastHref = location.href;
        var lastReadyState = document.readyState;
        function nudge() {
            try {
                document.dispatchEvent(new Event('input', { bubbles: true }));
                document.dispatchEvent(new Event('change', { bubbles: true }));
            } catch (e) {}
        }
        window.addEventListener('pageshow', function() { setTimeout(nudge, 120); });
        window.addEventListener('focus', function() { setTimeout(nudge, 120); });
        document.addEventListener('visibilitychange', function() {
            if (!document.hidden) setTimeout(nudge, 120);
        });
        setInterval(function() {
            try {
                if (location.href !== lastHref) {
                    lastHref = location.href;
                    setTimeout(nudge, 150);
                } else if (document.readyState !== lastReadyState) {
                    lastReadyState = document.readyState;
                    setTimeout(nudge, 150);
                }
            } catch (e) {}
        }, 1000);
    })();

})();

})();
