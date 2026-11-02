/**
 * Multi-Agent Academic Research Assistant — Main Frontend Application Logic
 * Manages view switching, API interactions, polling, and interactive scorecard rendering.
 */

document.addEventListener("DOMContentLoaded", () => {
    // Initialize Neural Workflow Graph
    const neuralGraph = new NeuralWorkflowGraph("neural-graph-stage");

    // State
    let currentJobId = null;
    let pollInterval = null;
    let currentReportId = null;

    // Elements
    const navItems = document.querySelectorAll(".nav-item");
    const viewPanels = document.querySelectorAll(".view-panel");
    const toast = document.getElementById("toast-banner");

    // Forms
    const newReportForm = document.getElementById("new-report-form");
    const improveReportForm = document.getElementById("improve-report-form");
    const settingsForm = document.getElementById("settings-form");

    // Dropzones
    setupDropzone("new-pdf-dropzone", "new-pdf-input", "new-file-pill");
    setupDropzone("improve-pdf-dropzone", "improve-pdf-input", "improve-file-pill");

    // View Navigation
    navItems.forEach(item => {
        item.addEventListener("click", (e) => {
            e.preventDefault();
            const targetView = item.getAttribute("data-view");
            switchView(targetView);
        });
    });

    // Quick Action Card Triggers
    document.querySelectorAll("[data-action-view]").forEach(btn => {
        btn.addEventListener("click", () => {
            const target = btn.getAttribute("data-action-view");
            switchView(target);
        });
    });

    function switchView(viewName) {
        navItems.forEach(n => {
            n.classList.toggle("active", n.getAttribute("data-view") === viewName);
        });
        viewPanels.forEach(p => {
            p.classList.toggle("active", p.id === `view-${viewName}`);
        });

        // Refresh reports list if navigating to dashboard or reports
        if (viewName === "dashboard" || viewName === "reports") {
            loadRecentReports();
        } else if (viewName === "settings") {
            loadSettings();
        }
    }

    // Dropzone Handler
    function setupDropzone(dropzoneId, inputId, pillId) {
        const dropzone = document.getElementById(dropzoneId);
        const input = document.getElementById(inputId);
        const pill = document.getElementById(pillId);
        if (!dropzone || !input) return;

        dropzone.addEventListener("click", () => input.click());

        dropzone.addEventListener("dragover", (e) => {
            e.preventDefault();
            dropzone.classList.add("dragover");
        });

        dropzone.addEventListener("dragleave", () => {
            dropzone.classList.remove("dragover");
        });

        dropzone.addEventListener("drop", (e) => {
            e.preventDefault();
            dropzone.classList.remove("dragover");
            if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                const file = e.dataTransfer.files[0];
                if (file.name.toLowerCase().endsWith(".pdf")) {
                    input.files = e.dataTransfer.files;
                    updateFilePill(pill, file.name);
                } else {
                    showToast("Please upload a valid .pdf document.", "error");
                }
            }
        });

        input.addEventListener("change", () => {
            if (input.files && input.files[0]) {
                updateFilePill(pill, input.files[0].name);
            }
        });
    }

    function updateFilePill(pill, filename) {
        if (!pill) return;
        pill.style.display = "inline-flex";
        pill.innerHTML = `
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
            ${filename}
        `;
    }

    // Submit: Create New Report
    if (newReportForm) {
        newReportForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const submitBtn = document.getElementById("new-submit-btn");
            submitBtn.disabled = true;
            submitBtn.innerHTML = "Submitting Workflow...";

            const formData = new FormData(newReportForm);

            try {
                const resp = await fetch("/api/reports/generate", {
                    method: "POST",
                    body: formData
                });
                const data = await resp.json();

                if (resp.ok && data.job_id) {
                    showToast("Workflow initiated successfully. Processing evidence...", "success");
                    currentJobId = data.job_id;
                    switchView("dashboard");
                    startJobPolling(data.job_id);
                } else {
                    showToast(data.error || "Failed to start report generation.", "error");
                }
            } catch (err) {
                showToast(`Request failed: ${err.message}`, "error");
            } finally {
                submitBtn.disabled = false;
                submitBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg> Generate Academic Report`;
            }
        });
    }

    // Submit: Improve Existing Report
    if (improveReportForm) {
        improveReportForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const submitBtn = document.getElementById("improve-submit-btn");
            submitBtn.disabled = true;
            submitBtn.innerHTML = "Submitting Revision...";

            const formData = new FormData(improveReportForm);

            try {
                const resp = await fetch("/api/reports/improve", {
                    method: "POST",
                    body: formData
                });
                const data = await resp.json();

                if (resp.ok && data.job_id) {
                    showToast("Revision workflow initiated. Checking citations and structure...", "success");
                    currentJobId = data.job_id;
                    switchView("dashboard");
                    startJobPolling(data.job_id);
                } else {
                    showToast(data.error || "Failed to start improvement workflow.", "error");
                }
            } catch (err) {
                showToast(`Request failed: ${err.message}`, "error");
            } finally {
                submitBtn.disabled = false;
                submitBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg> Validate & Improve Report`;
            }
        });
    }

    // Polling Engine
    function startJobPolling(jobId) {
        if (pollInterval) clearInterval(pollInterval);

        const fill = document.getElementById("progress-fill");
        const msg = document.getElementById("progress-msg");
        const percent = document.getElementById("progress-percent");
        const statusBadge = document.getElementById("workflow-status-badge");

        pollInterval = setInterval(async () => {
            try {
                const res = await fetch(`/api/jobs/${jobId}`);
                if (!res.ok) return;
                const job = await res.json();

                // Update UI Progress & Blueprint Gauge
                if (fill) fill.style.width = `${job.progress}%`;
                if (percent) percent.innerText = `${job.progress}%`;
                if (msg) msg.innerText = job.message;
                if (statusBadge) {
                    statusBadge.innerText = job.stage_label || job.status;
                }
                updateSpeedometerGauge(job.progress, job.stage_label || job.status, `${job.progress}% Complete`);

                // Update Neural Graph
                const isCompleted = job.status === "completed";
                const isFailed = job.status === "failed";
                neuralGraph.updateWorkflowStage(job.stage, isCompleted, isFailed);

                if (isCompleted) {
                    clearInterval(pollInterval);
                    updateSpeedometerGauge(100, "Synthesis Complete", "Grounding: 100%");
                    showToast("Academic Report generation complete!", "success");
                    if (job.report_id) {
                        currentReportId = job.report_id;
                        loadReportResults(job.report_id);
                        switchView("results");
                    }
                    loadRecentReports();
                } else if (isFailed) {
                    clearInterval(pollInterval);
                    updateSpeedometerGauge(0, "Synthesis Interrupted", "Check Telemetry");
                    showToast(`Workflow failed: ${job.error || job.message}`, "error");
                }
            } catch (e) {
                console.error("Job poll error:", e);
            }
        }, 1500);
    }

    // Load Report Results
    async function loadReportResults(reportId) {
        try {
            const resp = await fetch(`/api/reports/${reportId}`);
            if (!resp.ok) {
                showToast("Could not load report details.", "error");
                return;
            }
            const data = await resp.json();
            currentReportId = reportId;
            renderReportResults(data);
        } catch (e) {
            showToast(`Error loading report: ${e.message}`, "error");
        }
    }

    function renderReportResults(data) {
        const report = data.report;
        const evaluation = data.evaluation;
        const htmlPreview = data.html_preview;

        // Render Reader View
        const docContainer = document.getElementById("report-document-container");
        if (docContainer) {
            docContainer.innerHTML = htmlPreview;
        }

        // Setup PDF Download Link
        const downloadBtn = document.getElementById("download-pdf-btn");
        if (downloadBtn) {
            downloadBtn.onclick = () => {
                window.location.href = `/api/reports/${report.id}/download`;
            };
        }

        // Setup "Improve this report" action
        const improveActionBtn = document.getElementById("improve-this-report-btn");
        if (improveActionBtn) {
            improveActionBtn.onclick = () => {
                const reportTextArea = document.getElementById("improve-report-text");
                if (reportTextArea) {
                    reportTextArea.value = data.markdown || report.abstract;
                }
                switchView("improve");
            };
        }

        // Setup Re-Correct Button
        const heroReCorrectBtn = document.getElementById("hero-re-correct-btn");
        if (heroReCorrectBtn) {
            heroReCorrectBtn.onclick = () => triggerReCorrect();
        }

        // Render Scorecard
        renderScorecard(evaluation);
    }

    function renderScorecard(evalData) {
        const scoreNum = document.getElementById("card-overall-score");
        const statusBadge = document.getElementById("card-status-badge");
        const heroContainer = document.getElementById("hero-re-correct-container");
        const heroBtn = document.getElementById("hero-re-correct-btn");
        const dimensionsContainer = document.getElementById("dimensions-container");
        const criticalBox = document.getElementById("critical-errors-box");
        const warningsBox = document.getElementById("warnings-box");

        if (!evalData) {
            if (scoreNum) scoreNum.innerText = "--";
            if (statusBadge) statusBadge.innerHTML = `<span class="badge badge-warning">Unchecked</span>`;
            if (heroContainer) heroContainer.style.display = "none";
            return;
        }

        if (scoreNum) scoreNum.innerText = `${evalData.overall_score.toFixed(1)}`;
        if (statusBadge) {
            statusBadge.innerHTML = evalData.passed
                ? `<span class="badge badge-success">Passed Quality Gate</span>`
                : `<span class="badge badge-warning">Needs Correction</span>`;
        }

        // Configure Re-Correct Button
        if (heroContainer && heroBtn) {
            heroContainer.style.display = "block";
            heroBtn.disabled = false;
            if (!evalData.passed || (evalData.critical_errors && evalData.critical_errors.length > 0)) {
                heroBtn.className = "btn btn-recorrect glow-amber-pulse";
                heroBtn.innerHTML = `
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg>
                    <span>⚡ Auto Re-Correct Report</span>
                `;
            } else {
                heroBtn.className = "btn btn-recorrect";
                heroBtn.innerHTML = `
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg>
                    <span>⚡ Re-Run AI Polish</span>
                `;
            }
        }

        // Dimensions
        if (dimensionsContainer && evalData.dimensions) {
            dimensionsContainer.innerHTML = evalData.dimensions.map(d => `
                <div class="dimension-item">
                    <div class="dimension-header">
                        <span class="dim-name">${d.name}</span>
                        <span class="dim-score">${d.score.toFixed(0)}/100</span>
                    </div>
                    <div class="dim-track">
                        <div class="dim-fill" style="width: ${d.score}%; background: ${d.score >= 70 ? 'var(--cyan)' : 'var(--warning)'};"></div>
                    </div>
                </div>
            `).join("");
        }

        // Critical Errors
        if (criticalBox) {
            if (evalData.critical_errors && evalData.critical_errors.length > 0) {
                criticalBox.style.display = "block";
                criticalBox.innerHTML = `
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                        <span style="font-size: 0.8rem; font-weight: 700; color: var(--error);">Critical Errors (Gating):</span>
                        <button id="inline-critical-fix-btn" class="btn btn-warning" style="font-size: 0.72rem; padding: 2px 8px; border-radius: 4px; gap: 4px;">
                            ⚡ Fix Issues
                        </button>
                    </div>
                    <ul style="padding-left: 18px; font-size: 0.76rem; color: var(--text-secondary); display: flex; flex-direction: column; gap: 4px;">
                        ${evalData.critical_errors.map(err => `<li>${err}</li>`).join("")}
                    </ul>
                `;
                const inlineFixBtn = document.getElementById("inline-critical-fix-btn");
                if (inlineFixBtn) {
                    inlineFixBtn.onclick = () => triggerReCorrect();
                }
            } else {
                criticalBox.style.display = "none";
            }
        }

        // Warnings
        if (warningsBox) {
            if (evalData.warnings && evalData.warnings.length > 0) {
                warningsBox.style.display = "block";
                warningsBox.innerHTML = `
                    <div style="font-size: 0.8rem; font-weight: 700; color: var(--warning); margin-bottom: 6px;">Advisory Warnings:</div>
                    <ul style="padding-left: 18px; font-size: 0.76rem; color: var(--text-secondary); display: flex; flex-direction: column; gap: 4px;">
                        ${evalData.warnings.slice(0, 4).map(w => `<li>${w}</li>`).join("")}
                    </ul>
                `;
            } else {
                warningsBox.style.display = "none";
            }
        }
    }

    // Trigger Autonomous Re-Correction
    async function triggerReCorrect() {
        if (!currentReportId) {
            showToast("No report selected to re-correct.", "error");
            return;
        }

        const heroBtn = document.getElementById("hero-re-correct-btn");
        const banner = document.getElementById("reader-re-correct-banner");
        const bannerStatus = document.getElementById("reader-re-correct-status");
        const bannerFill = document.getElementById("reader-re-correct-fill");
        const bannerBadge = document.getElementById("reader-re-correct-badge");

        // Button loading indicators
        if (heroBtn) {
            heroBtn.disabled = true;
            heroBtn.innerHTML = `<span class="banner-spinner" style="width: 14px; height: 14px; border-width: 2px;"></span> <span>Re-Correcting...</span>`;
        }

        // Show live progress banner
        if (banner) {
            banner.style.display = "flex";
            if (bannerFill) bannerFill.style.width = "18%";
            if (bannerStatus) bannerStatus.innerText = "Analyzing 8-dimension evaluation critiques & resolving gating issues...";
            if (bannerBadge) {
                bannerBadge.innerText = "Starting";
                bannerBadge.className = "badge badge-warning";
            }
            banner.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }

        try {
            const resp = await fetch(`/api/reports/${currentReportId}/re-correct`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({})
            });

            const data = await resp.json();
            if (!resp.ok || !data.job_id) {
                throw new Error(data.error || "Failed to start re-correction workflow.");
            }

            showToast("Multi-Agent re-correction started. Refining report...", "info");

            const jobId = data.job_id;
            const reCorrectPoll = setInterval(async () => {
                try {
                    const jobResp = await fetch(`/api/jobs/${jobId}`);
                    if (!jobResp.ok) return;
                    const job = await jobResp.json();

                    // Update live banner
                    if (bannerFill) bannerFill.style.width = `${Math.max(18, job.progress)}%`;
                    if (bannerStatus) bannerStatus.innerText = job.message || "Polishing structure and citations...";
                    if (bannerBadge) {
                        bannerBadge.innerText = job.stage_label || job.status;
                    }

                    // Update global gauge and neural graph
                    updateSpeedometerGauge(job.progress, job.stage_label || job.status, `${job.progress}% Complete`);
                    neuralGraph.updateWorkflowStage(job.stage, job.status === "completed", job.status === "failed");

                    if (job.status === "completed") {
                        clearInterval(reCorrectPoll);
                        if (bannerFill) bannerFill.style.width = "100%";
                        if (bannerStatus) bannerStatus.innerText = "Report successfully re-corrected! Reloading...";
                        if (bannerBadge) {
                            bannerBadge.innerText = "Completed";
                            bannerBadge.className = "badge badge-success";
                        }

                        setTimeout(async () => {
                            if (banner) banner.style.display = "none";
                            await loadReportResults(currentReportId);
                            loadRecentReports();
                            showToast("Report successfully re-corrected! Quality gate passed.", "success");
                        }, 750);
                    } else if (job.status === "failed") {
                        clearInterval(reCorrectPoll);
                        if (banner) banner.style.display = "none";
                        showToast(`Re-correction failed: ${job.error || job.message}`, "error");
                        if (heroBtn) {
                            heroBtn.disabled = false;
                            heroBtn.innerHTML = `⚡ Retry Re-Correction`;
                        }
                    }
                } catch (pollErr) {
                    console.error("Re-correction poll error:", pollErr);
                }
            }, 1200);

        } catch (err) {
            if (banner) banner.style.display = "none";
            showToast(`Error: ${err.message}`, "error");
            if (heroBtn) {
                heroBtn.disabled = false;
                heroBtn.innerHTML = `⚡ Re-Correct Report`;
            }
        }
    }

    // Load Reports List
    async function loadRecentReports() {
        const tbodyDashboard = document.getElementById("recent-reports-tbody");
        const tbodyReportsView = document.getElementById("all-reports-tbody");

        try {
            const resp = await fetch("/api/reports");
            if (!resp.ok) return;
            const data = await resp.json();
            const reports = data.reports || [];

            const renderRows = (container) => {
                if (!container) return;
                if (reports.length === 0) {
                    container.innerHTML = `
                        <tr>
                            <td colspan="5">
                                <div class="empty-state">
                                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
                                    <h4>No reports generated yet</h4>
                                    <p>Start a new academic research workflow to produce evidence-grounded reports.</p>
                                </div>
                            </td>
                        </tr>
                    `;
                    return;
                }

                container.innerHTML = reports.map(r => `
                    <tr>
                        <td class="report-title-cell" title="${r.title}">
                            <a href="#" class="report-link" data-id="${r.id}" style="color: var(--cyan); text-decoration: none; font-weight: 500;">
                                ${r.title}
                            </a>
                        </td>
                        <td><span class="badge badge-info">${r.citation_style}</span></td>
                        <td>
                            ${r.score !== null ? `<span class="badge ${r.passed ? 'badge-success' : 'badge-warning'}">${r.score.toFixed(0)}/100</span>` : '<span class="badge">--</span>'}
                        </td>
                        <td style="color: var(--text-muted); font-size: 0.78rem;">${(r.created_at || '').substring(0, 10)}</td>
                        <td>
                            <div style="display: flex; gap: 8px;">
                                <button class="btn btn-secondary view-report-btn" data-id="${r.id}" style="padding: 4px 10px; font-size: 0.75rem;">View</button>
                                <a href="/api/reports/${r.id}/download" class="btn btn-secondary" style="padding: 4px 10px; font-size: 0.75rem;">PDF</a>
                                <button class="btn btn-danger delete-report-btn" data-id="${r.id}" style="padding: 4px 8px; font-size: 0.75rem;">×</button>
                            </div>
                        </td>
                    </tr>
                `).join("");

                // Attach click handlers
                container.querySelectorAll(".view-report-btn, .report-link").forEach(btn => {
                    btn.addEventListener("click", (e) => {
                        e.preventDefault();
                        const id = btn.getAttribute("data-id");
                        loadReportResults(id);
                        switchView("results");
                    });
                });

                container.querySelectorAll(".delete-report-btn").forEach(btn => {
                    btn.addEventListener("click", async () => {
                        const id = btn.getAttribute("data-id");
                        if (confirm("Are you sure you want to delete this report?")) {
                            await deleteReport(id);
                        }
                    });
                });
            };

            renderRows(tbodyDashboard);
            renderRows(tbodyReportsView);
        } catch (e) {
            console.error("Error loading reports:", e);
        }
    }

    async function deleteReport(reportId) {
        try {
            const resp = await fetch(`/api/reports/${reportId}`, { method: "DELETE" });
            if (resp.ok) {
                showToast("Report deleted", "success");
                loadRecentReports();
            } else {
                showToast("Failed to delete report", "error");
            }
        } catch (e) {
            showToast(e.message, "error");
        }
    }

    // Load Settings
    async function loadSettings() {
        try {
            const res = await fetch("/api/settings");
            if (!res.ok) return;
            const data = await res.json();
            const select = document.getElementById("setting-default-style");
            const scoreInp = document.getElementById("setting-passing-score");
            const modelBadge = document.getElementById("groq-model-status");
            const searchBadge = document.getElementById("search-provider-status");

            if (select) select.value = data.default_citation_style || "IEEE";
            if (scoreInp) scoreInp.value = data.passing_score || 75;
            if (modelBadge) {
                modelBadge.innerText = `${data.groq_model} (${data.groq_configured ? 'Active' : 'Unconfigured'})`;
            }
            if (searchBadge) {
                searchBadge.innerText = `${data.search_provider} (Ready)`;
            }
        } catch (e) {
            console.error("Settings load error:", e);
        }
    }

    // Save Settings
    if (settingsForm) {
        settingsForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const default_citation_style = document.getElementById("setting-default-style").value;
            const passing_score = document.getElementById("setting-passing-score").value;

            try {
                const res = await fetch("/api/settings", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ default_citation_style, passing_score })
                });
                if (res.ok) {
                    showToast("Settings updated successfully", "success");
                }
            } catch (err) {
                showToast("Failed to save settings", "error");
            }
        });
    }

    // Toast Utility
    function showToast(message, type = "info") {
        if (!toast) return;
        toast.className = `toast-banner toast-${type} show`;
        toast.innerHTML = `
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                ${type === 'success' 
                    ? '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline>'
                    : '<circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line>'}
            </svg>
            <span>${message}</span>
        `;
        setTimeout(() => {
            toast.classList.remove("show");
        }, 4500);
    }

    // Gauge Update Helper (Blueprint CAD Speedometer)
    function updateSpeedometerGauge(pct, statusText, subText) {
        const valEl = document.getElementById("gauge-display-val");
        const arcEl = document.getElementById("gauge-live-arc");
        const statusEl = document.getElementById("gauge-status-text");
        const subEl = document.getElementById("gauge-display-sub");
        if (valEl) valEl.innerText = `${pct}%`;
        if (statusEl && statusText) statusEl.innerText = statusText;
        if (subEl && subText) subEl.innerText = subText;
        if (arcEl) {
            const offset = Math.max(0, 172 - (172 * (pct / 100)));
            arcEl.style.strokeDashoffset = offset;
        }
    }

    // =========================================================================
    // COMMAND PALETTE (⌘K / Ctrl+K) & TEMPLATE INTERACTION ENGINE
    // =========================================================================
    const cmdPaletteModal = document.getElementById("command-palette-modal");
    const cmdPaletteInput = document.getElementById("command-palette-input");
    const topCmdTrigger = document.getElementById("top-cmd-trigger");
    const cardTriggerPalette = document.getElementById("card-trigger-palette");

    function openCommandPalette() {
        if (!cmdPaletteModal) return;
        cmdPaletteModal.style.display = "flex";
        if (cmdPaletteInput) {
            cmdPaletteInput.value = "";
            cmdPaletteInput.focus();
            filterPaletteItems("");
        }
    }

    function closeCommandPalette() {
        if (!cmdPaletteModal) return;
        cmdPaletteModal.style.display = "none";
    }

    if (topCmdTrigger) topCmdTrigger.addEventListener("click", openCommandPalette);
    if (cardTriggerPalette) cardTriggerPalette.addEventListener("click", openCommandPalette);

    // Global Keydown: ⌘K or Ctrl+K or Esc
    document.addEventListener("keydown", (e) => {
        if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
            e.preventDefault();
            if (cmdPaletteModal && cmdPaletteModal.style.display === "flex") {
                closeCommandPalette();
            } else {
                openCommandPalette();
            }
        } else if (e.key === "Escape") {
            closeCommandPalette();
        }
    });

    if (cmdPaletteModal) {
        cmdPaletteModal.addEventListener("click", (e) => {
            if (e.target === cmdPaletteModal) {
                closeCommandPalette();
            }
        });
    }

    // Filter Command Palette Items
    function filterPaletteItems(query) {
        const items = document.querySelectorAll(".command-palette-results .palette-item");
        const lower = query.toLowerCase().trim();
        items.forEach(item => {
            const text = item.innerText.toLowerCase();
            item.style.display = (!lower || text.includes(lower)) ? "flex" : "none";
        });
    }

    if (cmdPaletteInput) {
        cmdPaletteInput.addEventListener("input", (e) => {
            filterPaletteItems(e.target.value);
        });
    }

    // Handle Palette Navigation & Template clicks
    document.querySelectorAll("[data-cmd-nav]").forEach(btn => {
        btn.addEventListener("click", () => {
            const view = btn.getAttribute("data-cmd-nav");
            switchView(view);
            closeCommandPalette();
        });
    });

    function applyAcademicTemplate(topic, style) {
        const topicInput = document.getElementById("new-topic");
        const styleSelect = document.getElementById("new-citation-style");
        if (topicInput) topicInput.value = topic;
        if (styleSelect && style) {
            for (let opt of styleSelect.options) {
                if (opt.value.toLowerCase() === style.toLowerCase() || opt.text.toLowerCase().includes(style.toLowerCase())) {
                    styleSelect.value = opt.value;
                    break;
                }
            }
        }
        switchView("create");
        closeCommandPalette();
        showToast(`Template loaded: ${topic.slice(0, 45)}...`, "info");
        if (topicInput) topicInput.focus();
    }

    document.querySelectorAll("[data-cmd-template]").forEach(btn => {
        btn.addEventListener("click", () => {
            const topic = btn.getAttribute("data-cmd-template");
            const style = btn.getAttribute("data-style") || "IEEE";
            applyAcademicTemplate(topic, style);
        });
    });

    // Handle Templates Card (Interactive Filter Chips & List Preview)
    const tplPresets = {
        all: [
            { topic: "Agentic AI: Autonomous Intelligence for Complex Goals—A Comprehensive Survey", style: "IEEE" },
            { topic: "Quantum Error Correction & Fault-Tolerant Architectures", style: "Nature" },
            { topic: "Deep Residual Reinforcement Learning for Robotic Manipulation", style: "APA" },
            { topic: "Cognitive Architectures for Hallucination Reduction in LLMs", style: "IEEE" }
        ],
        design: [
            { topic: "Human-AI Co-Design Systems in Scientific Workflows", style: "ACM" },
            { topic: "Visual Analytics for High-Dimensional Genomic Embeddings", style: "IEEE" }
        ],
        uiux: [
            { topic: "Evaluation of Progressive Disclosure in Agentic Cockpits", style: "APA" },
            { topic: "Cognitive Load in Multi-Agent Autonomous Dashboards", style: "IEEE" }
        ],
        web: [
            { topic: "Distributed Real-Time Neural Graph Visualization Systems", style: "IEEE" },
            { topic: "Decentralized Verification Protocols for Scientific Assertions", style: "IEEE" }
        ],
        research: [
            { topic: "Deterministic Citation Resolution and Graph Grounding in LLM Pipelines", style: "IEEE" },
            { topic: "Comparative Meta-Analysis of LLM Reasoning Benchmarks (2024-2026)", style: "Nature" }
        ]
    };

    function renderTplList(category = "all") {
        const listContainer = document.getElementById("tpl-list-preview");
        if (!listContainer) return;
        const items = tplPresets[category] || tplPresets.all;
        listContainer.innerHTML = items.map(item => `
            <div class="tpl-preview-item" data-template-topic="${item.topic}" data-style="${item.style}">
                <span class="tpl-dot"></span>
                <span class="tpl-name">${item.topic.length > 36 ? item.topic.slice(0, 36) + '...' : item.topic} (${item.style})</span>
            </div>
        `).join("");

        listContainer.querySelectorAll(".tpl-preview-item").forEach(item => {
            item.addEventListener("click", () => {
                const topic = item.getAttribute("data-template-topic");
                const style = item.getAttribute("data-style") || "IEEE";
                applyAcademicTemplate(topic, style);
            });
        });
    }

    document.querySelectorAll(".tpl-chip").forEach(chip => {
        chip.addEventListener("click", () => {
            document.querySelectorAll(".tpl-chip").forEach(c => c.classList.remove("active"));
            chip.classList.add("active");
            const filter = chip.getAttribute("data-tpl-filter");
            renderTplList(filter);
        });
    });

    const tplQuickSearch = document.getElementById("tpl-quick-search");
    if (tplQuickSearch) {
        tplQuickSearch.addEventListener("input", (e) => {
            const query = e.target.value.toLowerCase();
            document.querySelectorAll("#tpl-list-preview .tpl-preview-item").forEach(item => {
                const txt = item.innerText.toLowerCase();
                item.style.display = (!query || txt.includes(query)) ? "flex" : "none";
            });
        });
    }

    // Initial render of templates preview
    renderTplList("all");

    // Initial load
    loadRecentReports();
});
