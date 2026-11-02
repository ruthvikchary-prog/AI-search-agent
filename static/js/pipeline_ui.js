/**
 * Pipeline Dashboard UI & Report Reader Controller
 * - 5 stage nodes, elevated pipes with traveling dots
 * - Top Tab switching (Pipeline <-> Report Reader)
 * - Single Agent execution (independent, does NOT reset other nodes, validates dependencies)
 * - Full Pipeline execution (resets all 5 nodes, starts M1 immediately)
 * - Live real data synchronization from outputs/*.json
 * - Report Reader auto-load with 8-dimension scorecard & IEEE sections
 */

class PipelineApp {
    constructor() {
        this.statusInterval = null;
        this.selectedAgentId = null;
        this.isFetchingStatus = false;
        this.currentLogsCount = 0;
        this.currentView = "pipeline";
        this.currentReportRunId = "";

        this.initElements();
        this.bindEvents();
        this.startPolling();
        this.loadLatestReport();
    }

    initElements() {
        // Top Navigation Tabs
        this.tabNavPipeline = document.getElementById("tab-nav-pipeline");
        this.tabNavReader = document.getElementById("tab-nav-reader");
        this.viewPipeline = document.getElementById("view-pipeline");
        this.viewReader = document.getElementById("view-reader");
        this.btnGotoPipeline = document.getElementById("btn-goto-pipeline") || document.getElementById("btn-goto-pipeline-from-reader");
        this.sidebarNavItems = document.querySelectorAll(".sidebar-nav-item[data-view]");
        this.viewPanels = document.querySelectorAll(".view-panel");
        this.pageHeaderTitle = document.getElementById("page-header-title");
        this.pageHeaderBreadcrumb = document.getElementById("page-header-breadcrumb");
        this.commandMenuTrigger = document.getElementById("command-menu-trigger");
        this.commandModal = document.getElementById("cmd-modal-backdrop");
        this.commandInput = document.getElementById("cmd-search-input");
        this.commandResults = document.getElementById("cmd-results-list");

        // Controls
        this.topicInput = document.getElementById("pipeline-topic-input");
        this.pipelineTopicError = document.getElementById("pipeline-topic-error");
        this.runPipelineBtn = document.getElementById("btn-run-full-pipeline");
        this.downloadPdfBtn = document.getElementById("btn-download-pdf");
        this.liveStatusPill = document.getElementById("pipeline-live-status-pill");

        // Nodes
        this.nodeElements = {
            m1: document.getElementById("node-m1"),
            m2: document.getElementById("node-m2"),
            m3: document.getElementById("node-m3"),
            evaluation: document.getElementById("node-evaluation"),
            final: document.getElementById("node-final")
        };

        // Pipes
        this.pipeElements = {
            m1_to_m2: document.getElementById("pipe-m1-to-m2"),
            m2_to_m3: document.getElementById("pipe-m2-to-m3"),
            m3_to_eval: document.getElementById("pipe-m3-to-eval"),
            eval_to_final: document.getElementById("pipe-eval-to-final")
        };

        // Terminal Log Console
        this.terminalLogs = document.getElementById("terminal-logs-body");
        this.clearLogsBtn = document.getElementById("terminal-clear-btn");
        this.copyLogsBtn = document.getElementById("terminal-copy-btn");
        this.toast = document.getElementById("toast-banner");

        // Side Panel Inspector Drawer
        this.drawer = document.getElementById("node-inspector-drawer");
        this.drawerOverlay = document.getElementById("drawer-backdrop");
        this.drawerCloseBtn = document.getElementById("drawer-close-btn");
        this.drawerTitle = document.getElementById("drawer-agent-title");
        this.drawerOwner = document.getElementById("drawer-agent-owner");
        this.drawerRunAgentBtn = document.getElementById("drawer-run-agent-btn");
        this.drawerInputJson = document.getElementById("drawer-input-json");
        this.drawerOutputJson = document.getElementById("drawer-output-json");
        this.drawerMetrics = document.getElementById("drawer-metrics-content");
        this.copyOutputBtn = document.getElementById("drawer-copy-output-btn");

        // Report Reader Elements
        this.readerScoreNum = document.getElementById("reader-overall-score");
        this.readerStatusBadge = document.getElementById("reader-status-badge");
        this.readerDimensionsList = document.getElementById("reader-dimensions-list");
        this.readerCritBox = document.getElementById("reader-critical-errors-box");
        this.readerWarnBox = document.getElementById("reader-warnings-box");
        this.readerCritList = document.getElementById("reader-critical-errors-list");
        this.readerWarnList = document.getElementById("reader-warnings-list");
        this.readerDownloadPdfBtn = document.getElementById("reader-download-pdf-btn");
        this.readerEmptyState = document.getElementById("reader-empty-state");
        this.readerPaperSheet = document.getElementById("reader-paper-sheet");
    }

    bindEvents() {
        // Tab Navigation
        if (this.tabNavPipeline) {
            this.tabNavPipeline.addEventListener("click", () => this.switchView("pipeline"));
        }
        if (this.tabNavReader) {
            this.tabNavReader.addEventListener("click", () => {
                this.switchView("reader");
                this.loadLatestReport();
            });
        }
        if (this.btnGotoPipeline) {
            this.btnGotoPipeline.addEventListener("click", () => this.switchView("pipeline"));
        }

        // Visible sidebar navigation used by the current dashboard layout.
        this.sidebarNavItems.forEach((item) => {
            item.addEventListener("click", () => {
                const viewName = item.dataset.view;
                this.switchView(viewName);
                if (viewName === "reader") this.loadLatestReport();
            });
        });

        // The command control is a quick route back to a searchable research topic.
        if (this.commandMenuTrigger) {
            this.commandMenuTrigger.addEventListener("click", () => {
                this.openCommandMenu();
            });
        }
        if (this.commandModal) {
            this.commandModal.addEventListener("click", (event) => {
                if (event.target === this.commandModal) this.closeCommandMenu();
            });
        }
        if (this.commandInput) {
            this.commandInput.addEventListener("input", () => this.renderCommandResults(this.commandInput.value));
        }
        document.addEventListener("keydown", (event) => {
            if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
                event.preventDefault();
                this.openCommandMenu();
            } else if (event.key === "Escape") {
                this.closeCommandMenu();
            }
        });

        // Topic input
        if (this.topicInput) {
            this.topicInput.addEventListener("input", () => {
                if (this.pipelineTopicError) {
                    this.pipelineTopicError.style.display = "none";
                    this.pipelineTopicError.textContent = "";
                }
            });
        }

        // Run full pipeline
        if (this.runPipelineBtn) {
            this.runPipelineBtn.addEventListener("click", () => this.triggerFullPipeline());
        }

        // Download PDF
        if (this.downloadPdfBtn) {
            this.downloadPdfBtn.addEventListener("click", (e) => {
                if (this.downloadPdfBtn.classList.contains("disabled")) {
                    e.preventDefault();
                    this.showToast("outputs/final_report.pdf has not been generated yet. Run the pipeline first.", "warning");
                } else {
                    window.location.href = this.pdfUrl("/api/pipeline/download-pdf");
                }
            });
        }

        // Reader Download PDF
        if (this.readerDownloadPdfBtn) {
            this.readerDownloadPdfBtn.addEventListener("click", () => {
                window.location.href = this.pdfUrl("/api/pipeline/download-pdf");
            });
        }

        // Node card clicks & Run agent buttons
        Object.entries(this.nodeElements).forEach(([agentId, nodeEl]) => {
            if (!nodeEl) return;

            // Direct button inside card
            const runBtn = nodeEl.querySelector(".btn-node-run");
            if (runBtn) {
                runBtn.addEventListener("click", (e) => {
                    e.stopPropagation();
                    this.triggerSingleAgent(agentId);
                });
            }

            // Card click opens drawer
            nodeEl.addEventListener("click", () => {
                this.openDrawer(agentId);
            });
        });

        // Drawer Close
        if (this.drawerCloseBtn) {
            this.drawerCloseBtn.addEventListener("click", () => this.closeDrawer());
        }
        if (this.drawerOverlay) {
            this.drawerOverlay.addEventListener("click", () => this.closeDrawer());
        }

        // Drawer Run Agent
        if (this.drawerRunAgentBtn) {
            this.drawerRunAgentBtn.addEventListener("click", () => {
                if (this.selectedAgentId) {
                    this.triggerSingleAgent(this.selectedAgentId);
                }
            });
        }

        // Drawer Tabs
        document.querySelectorAll(".drawer-tab-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                document.querySelectorAll(".drawer-tab-btn").forEach(b => b.classList.remove("active"));
                document.querySelectorAll(".drawer-tab-pane").forEach(p => p.classList.remove("active"));
                btn.classList.add("active");
                const target = document.getElementById(btn.getAttribute("data-target"));
                if (target) target.classList.add("active");
            });
        });

        // Copy Output JSON
        if (this.copyOutputBtn) {
            this.copyOutputBtn.addEventListener("click", () => {
                if (this.drawerOutputJson) {
                    navigator.clipboard.writeText(this.drawerOutputJson.textContent);
                    const orig = this.copyOutputBtn.textContent;
                    this.copyOutputBtn.textContent = "Copied!";
                    setTimeout(() => { this.copyOutputBtn.textContent = orig; }, 1500);
                }
            });
        }

        // Terminal Log Buttons
        if (this.clearLogsBtn) {
            this.clearLogsBtn.addEventListener("click", () => {
                if (this.terminalLogs) this.terminalLogs.innerHTML = "";
            });
        }
        if (this.copyLogsBtn) {
            this.copyLogsBtn.addEventListener("click", () => {
                if (this.terminalLogs) {
                    navigator.clipboard.writeText(this.terminalLogs.innerText);
                    const orig = this.copyLogsBtn.textContent;
                    this.copyLogsBtn.textContent = "Copied!";
                    setTimeout(() => { this.copyLogsBtn.textContent = orig; }, 1500);
                }
            });
        }

        document.querySelectorAll("[data-action-view]").forEach((button) => {
            button.addEventListener("click", () => this.switchView(button.dataset.actionView));
        });
        const newReportForm = document.getElementById("new-report-form");
        if (newReportForm) newReportForm.addEventListener("submit", (event) => this.submitNewReport(event));
        const resetNewForm = document.getElementById("btn-reset-new-form");
        if (resetNewForm) resetNewForm.addEventListener("click", () => newReportForm?.reset());
        const improveForm = document.getElementById("improve-report-form");
        if (improveForm) improveForm.addEventListener("submit", (event) => this.submitImprovement(event));
        const settingsForm = document.getElementById("settings-defaults-form");
        if (settingsForm) settingsForm.addEventListener("submit", (event) => this.saveSettings(event));
        const reportsButton = document.getElementById("btn-new-from-reports");
        if (reportsButton) reportsButton.addEventListener("click", () => this.switchView("new"));
        const emptyReportsButton = document.getElementById("btn-empty-goto-new");
        if (emptyReportsButton) emptyReportsButton.addEventListener("click", () => this.switchView("new"));
        const readerPipelineButton = document.getElementById("btn-goto-pipeline-from-reader");
        if (readerPipelineButton) readerPipelineButton.addEventListener("click", () => this.switchView("pipeline"));
        const reportSearch = document.getElementById("my-reports-search-input");
        if (reportSearch) reportSearch.addEventListener("input", () => this.filterReports(reportSearch.value));
        if (this.currentView === "reports") this.loadReports();
    }

    switchView(viewName) {
        this.currentView = viewName;
        this.viewPanels.forEach((panel) => {
            panel.classList.toggle("active", panel.id === `view-${viewName}`);
        });
        this.sidebarNavItems.forEach((item) => {
            item.classList.toggle("active", item.dataset.view === viewName);
        });

        // Preserve compatibility with the former top-tab layout if it is used.
        if (this.tabNavPipeline) this.tabNavPipeline.classList.toggle("active", viewName === "pipeline");
        if (this.tabNavReader) this.tabNavReader.classList.toggle("active", viewName === "reader");

        const headings = {
            pipeline: ["Academic Research Assistant", "Evidence-Grounded Multi-Agent Synthesis & Verification"],
            new: ["New Report", "Configure and launch a research workflow"],
            reports: ["My Reports", "Browse completed research workflows"],
            reader: ["Document Reader", "Review the latest generated academic report"],
            improve: ["Improve Report", "Refine an existing report with grounded evidence"],
            settings: ["Settings", "Configure research and generation defaults"]
        };
        const [title, subtitle] = headings[viewName] || headings.pipeline;
        if (this.pageHeaderTitle) this.pageHeaderTitle.textContent = title;
        if (this.pageHeaderBreadcrumb) this.pageHeaderBreadcrumb.textContent = subtitle;
        if (viewName === "reports") this.loadReports();
        if (viewName === "improve") this.loadReportsForImprove();
        if (viewName === "settings") this.loadSettings();
    }

    openCommandMenu() {
        if (!this.commandModal) return;
        this.commandModal.classList.add("open");
        this.renderCommandResults("");
        this.commandInput?.focus();
    }

    closeCommandMenu() {
        this.commandModal?.classList.remove("open");
    }

    renderCommandResults(query) {
        if (!this.commandResults) return;
        const options = [
            ["Neural Hub", "pipeline"],
            ["New Report", "new"],
            ["Improve Report", "improve"],
            ["My Reports", "reports"],
            ["Document Reader", "reader"],
            ["Settings", "settings"]
        ].filter(([label]) => label.toLowerCase().includes(query.trim().toLowerCase()));
        this.commandResults.innerHTML = options.map(([label, view]) =>
            `<button type="button" class="command-result" data-command-view="${view}">${this.escapeHtml(label)}</button>`
        ).join("");
        this.commandResults.querySelectorAll("[data-command-view]").forEach((button) => {
            button.addEventListener("click", () => {
                this.closeCommandMenu();
                this.switchView(button.dataset.commandView);
            });
        });
    }

    async requestJson(url, options = {}) {
        const response = await fetch(url, options);
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.error || `Request failed (HTTP ${response.status})`);
        return data;
    }

    showToast(message, type = "success") {
        if (!this.toast) return;
        this.toast.textContent = message;
        this.toast.className = `toast-banner ${type}`;
        this.toast.style.display = "block";
        window.clearTimeout(this.toastTimer);
        this.toastTimer = window.setTimeout(() => { this.toast.style.display = "none"; }, 5000);
    }

    async submitNewReport(event) {
        event.preventDefault();
        const form = event.currentTarget;
        const button = document.getElementById("btn-submit-new-report");
        const topic = document.getElementById("new-report-topic")?.value.trim();
        const sourceCount = Number(document.getElementById("new-report-sources")?.value || 8);
        if (!topic) {
            this.showToast("Research topic is required.", "error");
            return;
        }
        const originalText = button ? button.innerHTML : "";
        if (button) {
            button.disabled = true;
            button.innerHTML = "⏳ Starting Pipeline...";
        }
        try {
            await this.requestJson("/api/pipeline/run", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    topic,
                    citation_style: document.getElementById("new-report-style")?.value || "IEEE",
                    source_count: sourceCount
                })
            });
            if (this.topicInput) this.topicInput.value = topic;
            this.showToast("Pipeline started successfully.");
            this.switchView("pipeline");
        } catch (error) {
            this.showToast(error.message, "error");
        } finally {
            if (button) {
                button.disabled = false;
                button.innerHTML = originalText;
            }
        }
    }

    async submitImprovement(event) {
        event.preventDefault();
        const button = document.getElementById("btn-submit-improve");
        const feedback = document.getElementById("improve-feedback-input")?.value.trim();
        if (!feedback) {
            this.showToast("Revision feedback is required.", "error");
            return;
        }
        const originalText = button ? button.innerHTML : "";
        if (button) {
            button.disabled = true;
            button.innerHTML = "⏳ Refining Report (M3 -> Evaluation -> Final)...";
        }
        try {
            const data = await this.requestJson("/api/pipeline/improve", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    run_id: document.getElementById("improve-run-select")?.value || "latest",
                    feedback
                })
            });
            document.getElementById("improve-results-box").style.display = "block";
            document.getElementById("improve-before-score").textContent = Number(data.before_score).toFixed(1);
            document.getElementById("improve-before-grade").textContent = `Grade ${data.before_grade}`;
            document.getElementById("improve-after-score").textContent = Number(data.after_score).toFixed(1);
            document.getElementById("improve-after-grade").textContent = `Grade ${data.after_grade}`;
            document.getElementById("btn-open-improved-reader").onclick = () => {
                this.currentReportRunId = data.new_run_id;
                this.switchView("reader");
                this.loadLatestReport(data.new_run_id);
            };
            this.showToast("Report improved and saved.");
        } catch (error) {
            this.showToast(error.message, "error");
        } finally {
            if (button) {
                button.disabled = false;
                button.innerHTML = originalText;
            }
        }
    }

    async loadReports() {
        try {
            const data = await this.requestJson("/api/pipeline/reports");
            this.reports = data.reports || [];
            this.renderReports(this.reports);
        } catch (error) {
            this.showToast(error.message, "error");
        }
    }

    renderReports(reports) {
        const body = document.getElementById("my-reports-tbody");
        const empty = document.getElementById("reports-empty-state");
        if (!body || !empty) return;
        body.innerHTML = reports.map((report) => `
            <tr>
                <td>${this.escapeHtml(report.topic || report.run_id)}</td>
                <td>${this.escapeHtml(report.version || "Latest")}<br><small>${this.escapeHtml(report.created_at || "")}</small></td>
                <td>${report.score == null ? "--" : `${Number(report.score).toFixed(1)}/100`}</td>
                <td>${this.escapeHtml(report.status || "AVAILABLE")}</td>
                <td class="report-actions">
                    <button class="btn-flat" data-open-report="${this.escapeHtml(report.run_id)}">Open</button>
                    <button class="btn-flat" data-delete-report="${this.escapeHtml(report.run_id)}">Delete</button>
                </td>
            </tr>
        `).join("");
        empty.style.display = reports.length ? "none" : "block";
        body.parentElement.style.display = reports.length ? "table" : "none";
        body.querySelectorAll("[data-open-report]").forEach((button) => button.addEventListener("click", () => {
            this.currentReportRunId = button.dataset.openReport;
            this.switchView("reader");
            this.loadLatestReport(this.currentReportRunId);
        }));
        body.querySelectorAll("[data-delete-report]").forEach((button) => button.addEventListener("click", async () => {
            if (!window.confirm("Delete this saved report?")) return;
            try {
                await this.requestJson(`/api/pipeline/reports/${encodeURIComponent(button.dataset.deleteReport)}`, { method: "DELETE" });
                this.loadReports();
            } catch (error) {
                this.showToast(error.message, "error");
            }
        }));
    }

    filterReports(query) {
        const needle = query.trim().toLowerCase();
        this.renderReports((this.reports || []).filter((report) => JSON.stringify(report).toLowerCase().includes(needle)));
    }

    async loadReportsForImprove() {
        try {
            const data = await this.requestJson("/api/pipeline/reports");
            const select = document.getElementById("improve-run-select");
            if (!select) return;
            select.innerHTML = `<option value="latest">Latest Report (outputs/)</option>` +
                (data.reports || []).map((report) => `<option value="${this.escapeHtml(report.run_id)}">${this.escapeHtml(report.topic || report.run_id)} (${this.escapeHtml(report.version || "saved")})</option>`).join("");
        } catch (error) {
            this.showToast(error.message, "error");
        }
    }

    async loadSettings() {
        try {
            const data = await this.requestJson("/api/pipeline/settings");
            const defaults = data.defaults || {};
            document.getElementById("settings-model-name").value = defaults.model_name || "";
            document.getElementById("settings-citation-style").value = defaults.citation_style || "IEEE";
            document.getElementById("settings-sources-count").value = defaults.default_sources || 8;
            const keys = document.getElementById("settings-keys-tbody");
            if (keys) keys.innerHTML = (data.keys || []).map((key) => `<tr><td>${this.escapeHtml(key.key)}</td><td>${this.escapeHtml(key.description)}</td><td>${this.escapeHtml(key.status)}</td></tr>`).join("");
            const team = document.getElementById("settings-team-list");
            if (team) team.innerHTML = (data.team || []).map((member) => `
                <article class="team-card">
                    <strong>${this.escapeHtml(member.module)} · ${this.escapeHtml(member.name)}</strong>
                    <div>${this.escapeHtml(member.member)} · ${this.escapeHtml(member.student_id)}</div>
                    <p>${this.escapeHtml(member.description)}</p>
                </article>
            `).join("");
        } catch (error) {
            this.showToast(error.message, "error");
        }
    }

    async saveSettings(event) {
        event.preventDefault();
        try {
            await this.requestJson("/api/pipeline/settings", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    model_name: document.getElementById("settings-model-name").value.trim(),
                    citation_style: document.getElementById("settings-citation-style").value,
                    default_sources: Number(document.getElementById("settings-sources-count").value)
                })
            });
            this.showToast("Preferences saved.");
        } catch (error) {
            this.showToast(error.message, "error");
        }
    }

    startPolling() {
        this.poll();
    }

    async poll() {
        if (this.isPolling) return;
        this.isPolling = true;
        try {
            await this.fetchStatus();
            await this.fetchLogs();
        } catch (e) {
            console.warn("Poll loop error:", e);
        } finally {
            this.isPolling = false;
            const delay = document.hidden ? 8000 : (this.isRunning ? 1000 : 3500);
            window.clearTimeout(this.statusTimer);
            this.statusTimer = window.setTimeout(() => this.poll(), delay);
        }
    }

    async fetchStatus() {
        if (this.isFetchingStatus) return;
        this.isFetchingStatus = true;

        try {
            const res = await fetch("/api/pipeline/status");
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            this.isRunning = Boolean(data.is_running);
            this.updateUI(data);
        } catch (err) {
            console.warn("Status poll error:", err);
        } finally {
            this.isFetchingStatus = false;
        }
    }

    async fetchLogs() {
        try {
            const res = await fetch("/api/pipeline/logs");
            if (!res.ok) return;
            const data = await res.json();
            const logs = data.logs || [];

            if (this.terminalLogs && logs.length !== this.currentLogsCount) {
                this.currentLogsCount = logs.length;
                this.terminalLogs.innerHTML = logs.map(line => {
                    let cls = "log-line";
                    if (line.includes("DONE") || line.includes("PASSED") || line.includes("SUCCESS") || line.includes("🎉")) {
                        cls += " log-success";
                    } else if (line.includes("START") || line.includes("🚀")) {
                        cls += " log-start";
                    } else if (line.includes("FAILED") || line.includes("Error") || line.includes("[!]")) {
                        cls += " log-error";
                    }
                    return `<div class="${cls}">${this.escapeHtml(line)}</div>`;
                }).join("");
                this.terminalLogs.scrollTop = this.terminalLogs.scrollHeight;
            }
        } catch (err) {
            console.warn("Log fetch error:", err);
        }
    }

    updateUI(data) {
        // Sync topic if user is not actively typing
        if (this.topicInput && document.activeElement !== this.topicInput && data.topic && data.is_running) {
            this.topicInput.value = data.topic;
        }

        // Live status pill
        if (this.liveStatusPill) {
            if (data.is_running) {
                this.liveStatusPill.className = "status-chip state-running";
                this.liveStatusPill.textContent = `Running: ${data.active_agent ? data.active_agent.toUpperCase() : "Pipeline"}...`;
            } else if (data.failed_agent) {
                this.liveStatusPill.className = "status-chip state-failed";
                this.liveStatusPill.textContent = `Failed at ${data.failed_agent.toUpperCase()}`;
            } else {
                this.liveStatusPill.className = "status-chip state-done";
                this.liveStatusPill.textContent = "Pipeline Ready (Done)";
            }
        }

        // Download PDF Button
        if (this.downloadPdfBtn) {
            if (data.pdf_ready) {
                this.downloadPdfBtn.classList.remove("disabled");
                this.downloadPdfBtn.removeAttribute("disabled");
                this.downloadPdfBtn.title = "Download outputs/final_report.pdf";
            } else {
                this.downloadPdfBtn.classList.add("disabled");
                this.downloadPdfBtn.setAttribute("disabled", "true");
                this.downloadPdfBtn.title = "final_report.pdf not generated yet";
            }
        }

        // Run full pipeline button state
        if (this.runPipelineBtn) {
            if (data.is_running) {
                this.runPipelineBtn.disabled = true;
                this.runPipelineBtn.textContent = "Running Pipeline...";
            } else {
                this.runPipelineBtn.disabled = false;
                this.runPipelineBtn.textContent = "Run full pipeline";
            }
        }

        // Update 5 Nodes with REAL numbers
        if (data.nodes) {
            Object.entries(data.nodes).forEach(([id, nodeData]) => {
                this.updateNodeCard(id, nodeData);
            });
        }

        // Update 4 Pipes
        if (data.pipes) {
            Object.entries(data.pipes).forEach(([pipeId, pipeData]) => {
                this.updatePipe(pipeId, pipeData);
            });
        }

        // Auto-refresh Report Reader after a pipeline run finishes
        if (this.wasRunning && !data.is_running) {
            this.loadLatestReport();
        }
        this.wasRunning = data.is_running;

        // If drawer open, refresh data
        if (this.selectedAgentId && this.drawer.classList.contains("open")) {
            this.loadDrawerData(this.selectedAgentId, false);
        }
    }

    updateNodeCard(agentId, info) {
        const card = this.nodeElements[agentId];
        if (!card) return;

        // Apply state classes
        const displayState = info.state === "success" ? "done" : info.state;
        card.classList.remove("state-idle", "state-running", "state-done", "state-success", "state-failed");
        card.classList.add(`state-${displayState}`);

        // Status badge
        const badge = card.querySelector(".node-status-badge");
        if (badge) {
            badge.className = `node-status-badge badge-${displayState}`;
            badge.textContent = displayState.charAt(0).toUpperCase() + displayState.slice(1);
        }

        // Timing chip (only show if done and time available)
        const timingEl = card.querySelector(".node-timing");
        if (timingEl) {
            if ((info.state === "done" || info.state === "success") && info.time_taken !== null && info.time_taken !== undefined) {
                timingEl.textContent = `${Number(info.time_taken).toFixed(2)}s`;
                timingEl.style.display = "inline-flex";
            } else {
                timingEl.style.display = "none";
            }
        }

        // Real metrics line
        const metricsEl = card.querySelector(".node-metrics-line");
        if (metricsEl) {
            if (info.state === "idle") {
                metricsEl.textContent = info.role;
            } else if (info.state === "running") {
                metricsEl.textContent = "Executing agent...";
            } else if (info.state === "failed") {
                metricsEl.textContent = info.error || "Execution failed";
            } else {
                // Done: show real numbers
                if (agentId === "m1") {
                    metricsEl.textContent = `${info.metrics.sources_count || 0} sources · ${info.metrics.subtopics_count || 0} subtopics`;
                } else if (agentId === "m2") {
                    metricsEl.textContent = `${info.metrics.verified_sources || 0} verified · ${info.metrics.rejected_sources || 0} rejected`;
                } else if (agentId === "m3") {
                    metricsEl.textContent = `${(info.metrics.word_count || 0).toLocaleString()} words · ${info.metrics.sections_count || 0} sections`;
                } else if (agentId === "evaluation") {
                    const score = info.metrics.overall_score !== null ? `${info.metrics.overall_score}/100` : "N/A";
                    const grade = info.metrics.grade ? ` (${info.metrics.grade})` : "";
                    metricsEl.textContent = `Score: ${score}${grade}`;
                } else if (agentId === "final") {
                    const pgs = info.metrics.pdf_pages || 7;
                    metricsEl.textContent = `IEEE Access PDF (${pgs} pages)`;
                }
            }
        }

        // Run agent button
        const runBtn = card.querySelector(".btn-node-run");
        if (runBtn) {
            if (info.state === "running") {
                runBtn.disabled = true;
                runBtn.textContent = "Running...";
            } else {
                runBtn.disabled = false;
                runBtn.textContent = "Run agent";
            }
        }
    }

    updatePipe(pipeId, pipeData) {
        const pipeEl = this.pipeElements[pipeId];
        if (!pipeEl) return;

        pipeEl.classList.remove("pipe-active", "pipe-filled");
        if (pipeData.active) {
            pipeEl.classList.add("pipe-active");
        } else if (pipeData.filled) {
            pipeEl.classList.add("pipe-filled");
        }
    }

    async openDrawer(agentId) {
        this.selectedAgentId = agentId;
        this.drawer.classList.add("open");
        this.drawerOverlay.classList.add("open");
        await this.loadDrawerData(agentId, true);
    }

    closeDrawer() {
        this.selectedAgentId = null;
        this.drawer.classList.remove("open");
        this.drawerOverlay.classList.remove("open");
    }

    async loadDrawerData(agentId, showLoading = true) {
        if (showLoading) {
            this.drawerInputJson.textContent = "Loading input data...";
            this.drawerOutputJson.textContent = "Loading output artifact...";
            this.drawerMetrics.innerHTML = "<p>Loading diagnostic metrics...</p>";
        }

        try {
            const res = await fetch(`/api/pipeline/output/${agentId}`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();

            this.drawerTitle.textContent = data.metadata.title;
            this.drawerOwner.textContent = `Owner: ${data.metadata.owner}`;

            this.drawerInputJson.textContent = JSON.stringify(data.input, null, 2);

            if (data.output) {
                this.drawerOutputJson.textContent = JSON.stringify(data.output, null, 2);
            } else {
                this.drawerOutputJson.textContent = "// Output file not generated yet. Click 'Run This Agent' above.";
            }

            let metricsHtml = `
                <div class="metrics-grid">
                    <div class="metric-item">
                        <label>Target Output File</label>
                        <code>${data.metadata.output_file}</code>
                    </div>
                    <div class="metric-item">
                        <label>Output Status</label>
                        <span>${data.has_output ? "Generated on Disk [OK]" : "Missing / Not Executed"}</span>
                    </div>
            `;
            if (data.output && data.output.time_taken_seconds !== undefined) {
                metricsHtml += `
                    <div class="metric-item">
                        <label>Execution Latency</label>
                        <span>${data.output.time_taken_seconds}s</span>
                    </div>
                `;
            }
            if (agentId === "evaluation" && data.output) {
                metricsHtml += `
                    <div class="metric-item">
                        <label>Composite Score</label>
                        <span>${data.output.overall_score}/100.0 (Grade: ${data.output.grade})</span>
                    </div>
                    <div class="metric-item">
                        <label>Hard Quality Gate</label>
                        <span>${data.output.passed ? "PASSED" : "FAILED"}</span>
                    </div>
                `;
            }
            metricsHtml += `</div>`;
            this.drawerMetrics.innerHTML = metricsHtml;

        } catch (err) {
            console.error("Error loading drawer:", err);
            this.drawerOutputJson.textContent = `// Error loading data: ${err.message}`;
        }
    }

    // ── TRIGGER FULL PIPELINE (Resets all 5 nodes, starts M1 immediately) ──
    async triggerFullPipeline() {
        if (this.isRunning) {
            this.showToast("A pipeline run is already in progress.", "warning");
            return;
        }

        const topic = this.topicInput ? this.topicInput.value.trim() : "";
        if (!topic) {
            if (this.pipelineTopicError) {
                this.pipelineTopicError.textContent = "Please enter a research topic.";
                this.pipelineTopicError.style.display = "block";
            }
            this.showToast("Please enter a research topic.", "error");
            this.topicInput?.focus();
            return;
        }

        if (this.pipelineTopicError) {
            this.pipelineTopicError.style.display = "none";
            this.pipelineTopicError.textContent = "";
        }

        // 1. Immediately reset all 5 nodes to idle & clear screen log
        Object.keys(this.nodeElements).forEach(id => {
            const card = this.nodeElements[id];
            if (card) {
                card.className = "pipeline-node-card state-idle";
                const b = card.querySelector(".node-status-badge");
                if (b) { b.className = "node-status-badge badge-idle"; b.textContent = "Idle"; }
                const t = card.querySelector(".node-timing");
                if (t) t.style.display = "none";
                const m = card.querySelector(".node-metrics-line");
                if (m) m.textContent = "Waiting to run...";
            }
        });

        // 2. Clear pipes
        Object.values(this.pipeElements).forEach(p => {
            if (p) p.className = "pipeline-pipe";
        });

        // 3. Immediately set M1 to running on screen
        const m1Card = this.nodeElements["m1"];
        if (m1Card) {
            m1Card.className = "pipeline-node-card state-running";
            const b = m1Card.querySelector(".node-status-badge");
            if (b) { b.className = "node-status-badge badge-running"; b.textContent = "Running"; }
            const m = m1Card.querySelector(".node-metrics-line");
            if (m) m.textContent = "Searching scientific literature...";
        }

        // 4. Clear logs
        if (this.terminalLogs) {
            this.terminalLogs.innerHTML = `<div class="log-line log-start">🚀 Starting Multi-Agent Pipeline for '${this.escapeHtml(topic)}'...</div>`;
            this.currentLogsCount = 1;
        }

        if (this.runPipelineBtn) {
            this.runPipelineBtn.disabled = true;
            this.runPipelineBtn.textContent = "Running Pipeline...";
        }

        try {
            const res = await fetch("/api/pipeline/run", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ topic })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || "Failed to start pipeline.");
            this.isRunning = true;
            this.poll();
        } catch (err) {
            this.showToast(`Pipeline Error: ${err.message}`, "error");
            this.poll();
        }
    }

    // ── TRIGGER SINGLE AGENT (Updates ONLY its own node, checks dependencies) ──
    async triggerSingleAgent(agentId) {
        if (this.isRunning) {
            this.showToast("An execution is currently in progress. Please wait for it to finish.", "warning");
            return;
        }

        const card = this.nodeElements[agentId];
        const prevMetrics = card ? card.querySelector(".node-metrics-line").textContent : "";

        // Optimistically set ONLY this node to running
        if (card) {
            card.className = "pipeline-node-card state-running";
            const b = card.querySelector(".node-status-badge");
            if (b) { b.className = "node-status-badge badge-running"; b.textContent = "Running"; }
            const m = card.querySelector(".node-metrics-line");
            if (m) m.textContent = "Executing...";
        }

        try {
            const res = await fetch(`/api/pipeline/run-agent/${agentId}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" }
            });
            const data = await res.json();
            if (!res.ok) {
                // Dependency error e.g. "Run M1 first (m1_research.json is missing)"
                if (card) {
                    card.className = "pipeline-node-card state-failed";
                    const b = card.querySelector(".node-status-badge");
                    if (b) { b.className = "node-status-badge badge-failed"; b.textContent = "Failed"; }
                    const m = card.querySelector(".node-metrics-line");
                    if (m) m.textContent = data.error || "Dependency missing";
                }
                this.showToast(data.error || "Dependency missing", "error");
                this.poll();
                return;
            }
            this.isRunning = true;
            this.poll();
        } catch (err) {
            if (card) {
                card.className = "pipeline-node-card state-failed";
                const b = card.querySelector(".node-status-badge");
                if (b) { b.className = "node-status-badge badge-failed"; b.textContent = "Failed"; }
                const m = card.querySelector(".node-metrics-line");
                if (m) m.textContent = err.message;
            }
            this.showToast(`Agent Execution Error: ${err.message}`, "error");
        }
    }

    // ── LOAD LATEST REPORT INTO REPORT READER ──
    pdfUrl(path) {
        return this.currentReportRunId ? `${path}?run_id=${encodeURIComponent(this.currentReportRunId)}` : path;
    }

    async loadLatestReport(runId = "") {
        try {
            this.currentReportRunId = runId;
            const query = runId ? `?run_id=${encodeURIComponent(runId)}` : "";
            const res = await fetch(`/api/pipeline/latest-report${query}`);
            if (!res.ok) return;
            const data = await res.json();

            if (!data.has_report) {
                if (this.readerEmptyState) this.readerEmptyState.style.display = "block";
                if (this.readerPaperSheet) this.readerPaperSheet.style.display = "none";
                if (this.readerScoreNum) this.readerScoreNum.textContent = "--";
                if (this.readerStatusBadge) {
                    this.readerStatusBadge.innerHTML = `<span class="badge badge-idle">Pending</span>`;
                }
                if (this.readerDimensionsList) this.readerDimensionsList.innerHTML = "<p style='font-size:0.75rem; color:var(--pipe-text-muted);'>No evaluation scorecard yet.</p>";
                if (this.readerCritBox) this.readerCritBox.style.display = "none";
                if (this.readerWarnBox) this.readerWarnBox.style.display = "none";
                return;
            }

            // Has report: hide empty state, show document sheet
            if (this.readerEmptyState) this.readerEmptyState.style.display = "none";
            if (this.readerPaperSheet) this.readerPaperSheet.style.display = "block";

            const rep = data.report;
            const ev = data.evaluation;
            const viewPdfLink = document.getElementById("reader-view-pdf-btn");
            if (viewPdfLink) viewPdfLink.href = this.pdfUrl("/api/pipeline/view-pdf");

            // Render Scorecard
            if (ev) {
                if (this.readerScoreNum) this.readerScoreNum.textContent = Number(ev.overall_score).toFixed(1);
                if (this.readerStatusBadge) {
                    const passed = ev.passed;
                    this.readerStatusBadge.innerHTML = passed
                        ? `<span class="node-status-badge badge-done">Passed (${ev.grade || "A"})</span>`
                        : `<span class="node-status-badge badge-failed">Failed</span>`;
                }
                if (this.readerDimensionsList && ev.dimensions) {
                    this.readerDimensionsList.innerHTML = ev.dimensions.map(d => `
                        <div class="reader-dim-item">
                            <div class="reader-dim-header">
                                <span class="reader-dim-name">${d.name}</span>
                                <span class="reader-dim-score">${Number(d.score).toFixed(0)}/100</span>
                            </div>
                            <div class="reader-dim-track">
                                <div class="reader-dim-fill" style="width: ${d.score}%; background: ${d.score >= 70 ? 'var(--pipe-done)' : 'var(--pipe-running)'};"></div>
                            </div>
                        </div>
                    `).join("");
                }

                // Render Critical Issues & Quality Warnings
                if (this.readerCritBox && this.readerCritList) {
                    const crits = ev.critical_errors || [];
                    if (crits.length > 0) {
                        this.readerCritList.innerHTML = crits.map(err => `<li>${this.escapeHtml(err)}</li>`).join("");
                        this.readerCritBox.style.display = "block";
                    } else {
                        this.readerCritBox.style.display = "none";
                    }
                }
                if (this.readerWarnBox && this.readerWarnList) {
                    const warns = ev.warnings || [];
                    if (warns.length > 0) {
                        this.readerWarnList.innerHTML = warns.map(w => `<li>${this.escapeHtml(w)}</li>`).join("");
                        this.readerWarnBox.style.display = "block";
                    } else {
                        this.readerWarnBox.style.display = "none";
                    }
                }
            } else {
                if (this.readerScoreNum) this.readerScoreNum.textContent = "--";
                if (this.readerStatusBadge) {
                    this.readerStatusBadge.innerHTML = `<span class="node-status-badge badge-failed">Failed</span>`;
                }
                if (this.readerCritBox) this.readerCritBox.style.display = "none";
                if (this.readerWarnBox) this.readerWarnBox.style.display = "none";
            }

            // Render Academic Document Sheet
            if (this.readerPaperSheet && rep) {
                let html = `
                    <div class="paper-title">${this.escapeHtml(rep.title || "Academic Report")}</div>
                    <div class="paper-meta-row">
                        <span><strong>Citation Style:</strong> ${this.escapeHtml(rep.citation_style || "IEEE")}</span>
                        <span><strong>Sections:</strong> ${(rep.sections || []).length}</span>
                        <span><strong>Target Scope:</strong> ~${rep.target_page_count || 8} pages</span>
                    </div>

                    <!-- Abstract Box -->
                    <div class="paper-abstract-box">
                        <div class="paper-abstract-title">■ ABSTRACT</div>
                        <div class="paper-abstract-content">${this.escapeHtml(rep.abstract || "No abstract available.")}</div>
                        ${rep.keywords && rep.keywords.length > 0 ? `<div class="paper-keywords"><strong>■ INDEX TERMS:</strong> ${this.escapeHtml(rep.keywords.join(", "))}.</div>` : ""}
                    </div>
                `;

                // Render All Sections
                if (rep.sections && rep.sections.length > 0) {
                    rep.sections.forEach(s => {
                        const paragraphs = (s.content || "").split("\n\n").filter(p => p.trim());
                        html += `
                            <div class="paper-section">
                                <h3 class="paper-section-heading">${this.escapeHtml(s.heading)}</h3>
                                ${paragraphs.map(p => `<p class="paper-section-content">${this.escapeHtml(p)}</p>`).join("")}
                            </div>
                        `;
                    });
                }

                // Render Conclusion
                if (rep.conclusion) {
                    html += `
                        <div class="paper-section">
                            <h3 class="paper-section-heading">CONCLUSION</h3>
                            <p class="paper-section-content">${this.escapeHtml(rep.conclusion)}</p>
                        </div>
                    `;
                }

                // Render References
                if (rep.references && rep.references.length > 0) {
                    html += `
                        <div class="paper-section">
                            <h3 class="paper-section-heading">REFERENCES</h3>
                            <ol class="paper-references-list">
                                ${rep.references.map((r, idx) => {
                                    const num = r.citation_number || (idx + 1);
                                    let cleanTxt = r.formatted_text || "";
                                    cleanTxt = cleanTxt.replace(/^\[\d+\]\s*/, "");
                                    return `<li>[${num}] ${this.escapeHtml(cleanTxt)}</li>`;
                                }).join("")}
                            </ol>
                        </div>
                    `;
                }

                // Render Author Biographies
                if (rep.biographies && rep.biographies.length > 0) {
                    html += `
                        <div class="paper-bios-block">
                            <h4 style="font-size:0.85rem; font-weight:700; text-transform:uppercase; margin-bottom:14px;">Author Biographies</h4>
                            ${rep.biographies.map(b => `
                                <div class="bio-entry">
                                    <strong>${this.escapeHtml(b.name || "")}</strong> ${this.escapeHtml(b.grade || "")} ${this.escapeHtml(b.bio || "")}
                                </div>
                            `).join("")}
                        </div>
                    `;
                }

                this.readerPaperSheet.innerHTML = html;
            }

        } catch (err) {
            console.warn("Error loading latest report:", err);
        }
    }

    escapeHtml(str) {
        if (!str) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
}

// Instantiate on DOM ready
document.addEventListener("DOMContentLoaded", () => {
    window.pipelineApp = new PipelineApp();
});
