/**
 * Neural Network Workflow Visualization (SVG Engine)
 * Renders connected AI Agent nodes and dynamically animates active processing stages.
 *
 * Agents:
 * 1. Research Agent
 * 2. Source Verification Agent
 * 3. Academic Writer Agent
 * 4. Evaluation Module
 * 5. Final Report Generator
 */

class NeuralWorkflowGraph {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        if (!this.container) return;

        this.nodes = [
            { id: "research", label: "Research Agent", role: "Evidence Collection", x: 100, y: 110, icon: "search" },
            { id: "verification", label: "Source Verifier", role: "Grounding & Credibility", x: 280, y: 55, icon: "shield" },
            { id: "writer", label: "Academic Writer", role: "Synthesis & Citations", x: 460, y: 110, icon: "pen" },
            { id: "evaluation", label: "Evaluation Module", role: "8-Dim Quality Gate", x: 640, y: 55, icon: "check" },
            { id: "generator", label: "Final Report Generator", role: "PDF & Export", x: 820, y: 110, icon: "file" }
        ];

        this.edges = [
            { from: "research", to: "verification", id: "e1" },
            { from: "verification", to: "writer", id: "e2" },
            { from: "writer", to: "evaluation", id: "e3" },
            { from: "evaluation", to: "generator", id: "e4" },
            // Bounded correction loop feedback edge from evaluation back to writer
            { from: "evaluation", to: "writer", id: "e_loop", isLoop: true }
        ];

        this.activeNodeId = null;
        this.completedNodes = new Set();
        this.failedNodeId = null;

        this.init();
    }

    init() {
        this.render();
        window.addEventListener("resize", () => this.render());
    }

    render() {
        if (!this.container) return;
        const width = this.container.clientWidth || 920;
        const height = this.container.clientHeight || 220;

        // Scale nodes horizontally to fit container width smoothly
        const scaleX = (width - 160) / 720;
        const scaledNodes = this.nodes.map(n => ({
            ...n,
            renderX: 80 + (n.x - 100) * scaleX,
            renderY: n.y
        }));

        const nodeMap = {};
        scaledNodes.forEach(n => { nodeMap[n.id] = n; });

        let svgHtml = `
        <svg class="neural-graph-svg" viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg">
            <defs>
                <linearGradient id="edgeGradActive" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stop-color="#3B82F6" />
                    <stop offset="100%" stop-color="#22D3EE" />
                </linearGradient>
                <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
                    <feGaussianBlur stdDeviation="4" result="blur" />
                    <feComposite in="SourceGraphic" in2="blur" operator="over" />
                </filter>
            </defs>
            <g class="edges-group">
        `;

        // Render Edges
        this.edges.forEach(edge => {
            const src = nodeMap[edge.from];
            const dst = nodeMap[edge.to];
            if (!src || !dst) return;

            let pathD = "";
            let edgeClass = "neural-edge";

            if (edge.isLoop) {
                // Curved arc beneath for correction loop
                const midX = (src.renderX + dst.renderX) / 2;
                const midY = 185;
                pathD = `M ${src.renderX} ${src.renderY + 22} Q ${midX} ${midY} ${dst.renderX} ${dst.renderY + 22}`;
            } else {
                pathD = `M ${src.renderX} ${src.renderY} L ${dst.renderX} ${dst.renderY}`;
            }

            // Determine edge state
            if (this.completedNodes.has(edge.from) && (this.activeNodeId === edge.to || this.completedNodes.has(edge.to))) {
                if (this.activeNodeId === edge.to) {
                    edgeClass += " active";
                } else if (this.completedNodes.has(edge.to)) {
                    edgeClass += " completed";
                }
            }

            svgHtml += `<path id="${edge.id}" class="${edgeClass}" d="${pathD}" />`;
        });

        svgHtml += `</g><g class="nodes-group">`;

        // Render Nodes
        scaledNodes.forEach(n => {
            let stateClass = "";
            let statusText = "Waiting";

            if (this.activeNodeId === n.id) {
                stateClass = "active";
                statusText = "Active Processing";
            } else if (this.completedNodes.has(n.id)) {
                stateClass = "completed";
                statusText = "Verified & Complete";
            } else if (this.failedNodeId === n.id) {
                stateClass = "failed";
                statusText = "Error in Stage";
            }

            svgHtml += `
            <g class="node-group ${stateClass}" id="node-${n.id}" data-id="${n.id}">
                <!-- Outer Ring -->
                <circle cx="${n.renderX}" cy="${n.renderY}" r="22" class="node-circle-bg" />
                <!-- Center Core Glyph -->
                <circle cx="${n.renderX}" cy="${n.renderY}" r="9" fill="${stateClass === 'active' ? '#22D3EE' : (stateClass === 'completed' ? '#34D399' : 'rgba(255, 255, 255, 0.18)')}" />
                <!-- Label -->
                <text x="${n.renderX}" y="${n.renderY + 36}" class="node-label">${n.label}</text>
                <text x="${n.renderX}" y="${n.renderY + 48}" class="node-sublabel" style="font-size: 8px; fill: #8E8E96; text-anchor: middle;">${n.role}</text>
            </g>
            `;
        });

        svgHtml += `</g></svg>`;
        this.container.innerHTML = svgHtml;
    }

    /**
     * Map backend workflow stage directly to active and completed neural node states.
     * Only highlights nodes that have genuinely started or finished.
     */
    updateWorkflowStage(backendStage, isCompleted = false, isFailed = false) {
        this.completedNodes.clear();
        this.activeNodeId = null;
        this.failedNodeId = null;

        const stageMap = {
            "idle": null,
            "input_validation": "research",
            "pdf_extraction": "research",
            "research_collection": "research",
            "source_verification": "verification",
            "academic_writing": "writer",
            "citation_validation": "evaluation",
            "quality_evaluation": "evaluation",
            "correction_loop": "writer",
            "formatting_export": "generator",
            "completed": null
        };

        const targetNode = stageMap[backendStage];

        if (isFailed) {
            this.failedNodeId = targetNode || "generator";
        } else if (isCompleted) {
            // All completed
            this.nodes.forEach(n => this.completedNodes.add(n.id));
            this.activeNodeId = null;
        } else if (targetNode) {
            this.activeNodeId = targetNode;
            // Mark preceding nodes as completed
            const order = ["research", "verification", "writer", "evaluation", "generator"];
            const currentIdx = order.indexOf(targetNode);
            for (let i = 0; i < currentIdx; i++) {
                this.completedNodes.add(order[i]);
            }
        }

        this.render();
    }

    reset() {
        this.completedNodes.clear();
        this.activeNodeId = null;
        this.failedNodeId = null;
        this.render();
    }
}

window.NeuralWorkflowGraph = NeuralWorkflowGraph;
