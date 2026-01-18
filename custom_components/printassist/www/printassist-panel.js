import {
  LitElement,
  html,
  css,
} from "https://unpkg.com/lit-element@2.4.0/lit-element.js?module";

class PrintAssistPanel extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      narrow: { type: Boolean },
      panel: { type: Object },
      _view: { type: String },
      _projects: { type: Array },
      _plates: { type: Array },
      _jobs: { type: Array },
      _selectedProject: { type: Object },
      _schedule: { type: Array },
      _uploading: { type: Boolean },
    };
  }

  static get styles() {
    return css`
      :host {
        display: block;
        padding: 16px;
        background: var(--primary-background-color);
        min-height: 100vh;
      }

      .header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 16px;
      }

      h1 {
        margin: 0;
        color: var(--primary-text-color);
        font-size: 24px;
      }

      .tabs {
        display: flex;
        gap: 8px;
        margin-bottom: 16px;
        border-bottom: 1px solid var(--divider-color);
        padding-bottom: 8px;
      }

      .tab {
        padding: 8px 16px;
        cursor: pointer;
        border-radius: 4px;
        color: var(--primary-text-color);
        background: transparent;
        border: none;
        font-size: 14px;
      }

      .tab:hover {
        background: var(--secondary-background-color);
      }

      .tab.active {
        background: var(--primary-color);
        color: var(--text-primary-color);
      }

      .card {
        background: var(--card-background-color);
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 16px;
        box-shadow: var(--ha-card-box-shadow, 0 2px 2px rgba(0,0,0,0.1));
      }

      .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;
      }

      .card-title {
        font-size: 18px;
        font-weight: 500;
        color: var(--primary-text-color);
      }

      .project-list {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
        gap: 16px;
      }

      .project-card {
        background: var(--card-background-color);
        border-radius: 8px;
        padding: 16px;
        cursor: pointer;
        border: 1px solid var(--divider-color);
        transition: border-color 0.2s;
      }

      .project-card:hover {
        border-color: var(--primary-color);
      }

      .project-name {
        font-size: 16px;
        font-weight: 500;
        margin-bottom: 8px;
      }

      .project-meta {
        color: var(--secondary-text-color);
        font-size: 12px;
      }

      .progress-bar {
        height: 4px;
        background: var(--divider-color);
        border-radius: 2px;
        margin-top: 8px;
        overflow: hidden;
      }

      .progress-fill {
        height: 100%;
        background: var(--primary-color);
        transition: width 0.3s;
      }

      .plate-list {
        display: flex;
        flex-direction: column;
        gap: 12px;
      }

      .plate-item {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 12px;
        background: var(--secondary-background-color);
        border-radius: 8px;
      }

      .plate-thumbnail {
        width: 60px;
        height: 60px;
        object-fit: cover;
        border-radius: 4px;
        background: var(--divider-color);
      }

      .plate-info {
        flex: 1;
      }

      .plate-name {
        font-weight: 500;
        margin-bottom: 4px;
      }

      .plate-meta {
        color: var(--secondary-text-color);
        font-size: 12px;
      }

      .plate-actions {
        display: flex;
        gap: 8px;
        align-items: center;
      }

      .quantity-control {
        display: flex;
        align-items: center;
        gap: 8px;
      }

      .quantity-btn {
        width: 28px;
        height: 28px;
        border-radius: 4px;
        border: 1px solid var(--divider-color);
        background: var(--card-background-color);
        cursor: pointer;
        font-size: 16px;
        color: var(--primary-text-color);
      }

      .quantity-value {
        min-width: 24px;
        text-align: center;
        font-weight: 500;
      }

      .btn {
        padding: 8px 16px;
        border-radius: 4px;
        border: none;
        cursor: pointer;
        font-size: 14px;
        transition: opacity 0.2s;
      }

      .btn:hover {
        opacity: 0.8;
      }

      .btn-primary {
        background: var(--primary-color);
        color: var(--text-primary-color);
      }

      .btn-secondary {
        background: var(--secondary-background-color);
        color: var(--primary-text-color);
      }

      .btn-danger {
        background: var(--error-color);
        color: white;
      }

      .btn-success {
        background: var(--success-color);
        color: white;
      }

      .btn-small {
        padding: 4px 8px;
        font-size: 12px;
      }

      .upload-zone {
        border: 2px dashed var(--divider-color);
        border-radius: 8px;
        padding: 32px;
        text-align: center;
        color: var(--secondary-text-color);
        cursor: pointer;
        transition: border-color 0.2s;
        margin-bottom: 16px;
      }

      .upload-zone:hover,
      .upload-zone.dragover {
        border-color: var(--primary-color);
      }

      .upload-zone input {
        display: none;
      }

      .schedule-item {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 12px;
        background: var(--secondary-background-color);
        border-radius: 8px;
        margin-bottom: 8px;
      }

      .schedule-number {
        width: 28px;
        height: 28px;
        background: var(--primary-color);
        color: var(--text-primary-color);
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 500;
        font-size: 14px;
      }

      .schedule-info {
        flex: 1;
      }

      .schedule-time {
        color: var(--secondary-text-color);
        font-size: 12px;
      }

      .back-btn {
        display: flex;
        align-items: center;
        gap: 8px;
        color: var(--primary-color);
        cursor: pointer;
        margin-bottom: 16px;
        font-size: 14px;
      }

      .empty-state {
        text-align: center;
        padding: 48px;
        color: var(--secondary-text-color);
      }

      .jobs-section {
        margin-top: 16px;
        padding-top: 16px;
        border-top: 1px solid var(--divider-color);
      }

      .job-item {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 8px 12px;
        background: var(--card-background-color);
        border-radius: 4px;
        margin-bottom: 8px;
        font-size: 13px;
      }

      .status-badge {
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 500;
        text-transform: uppercase;
      }

      .status-queued {
        background: var(--warning-color);
        color: white;
      }

      .status-printing {
        background: var(--primary-color);
        color: white;
      }

      .status-completed {
        background: var(--success-color);
        color: white;
      }

      .status-failed {
        background: var(--error-color);
        color: white;
      }

      .jobs-history {
        margin-left: 72px;
        margin-top: 8px;
        padding: 8px;
        background: var(--card-background-color);
        border-radius: 4px;
        font-size: 12px;
      }

      .job-history-item {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 4px 0;
        color: var(--secondary-text-color);
      }

      .failure-reason {
        color: var(--error-color);
        font-style: italic;
      }

      .next-job-banner {
        background: var(--primary-color);
        color: var(--text-primary-color);
        padding: 12px 16px;
        border-radius: 8px;
        margin-bottom: 16px;
        display: flex;
        align-items: center;
        justify-content: space-between;
      }

      .next-job-info {
        display: flex;
        flex-direction: column;
        gap: 4px;
      }

      .next-job-title {
        font-weight: 500;
      }

      .next-job-file {
        font-size: 12px;
        opacity: 0.9;
      }
    `;
  }

  constructor() {
    super();
    this._view = "projects";
    this._projects = [];
    this._plates = [];
    this._jobs = [];
    this._selectedProject = null;
    this._schedule = [];
    this._uploading = false;
  }

  connectedCallback() {
    super.connectedCallback();
    this._loadData();
  }

  async _loadData() {
    if (!this.hass) return;

    try {
      const result = await this.hass.connection.sendMessagePromise({
        type: "printassist/get_data",
      });
      this._projects = result.projects || [];
      this._plates = result.plates || [];
      this._jobs = result.jobs || [];
      this._schedule = result.schedule || [];
    } catch (err) {
      console.error("Failed to load PrintAssist data:", err);
      this._projects = [];
      this._plates = [];
      this._jobs = [];
      this._schedule = [];
    }
  }

  _formatDuration(seconds) {
    if (!seconds) return "Unknown";
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    if (hours > 0) {
      return `${hours}h ${minutes}m`;
    }
    return `${minutes}m`;
  }

  _handleTabClick(view) {
    this._view = view;
    this._selectedProject = null;
  }

  _selectProject(project) {
    this._selectedProject = project;
    this._view = "project-detail";
  }

  _goBack() {
    this._selectedProject = null;
    this._view = "projects";
  }

  async _createProject() {
    const name = prompt("Project name:");
    if (!name) return;

    try {
      await this.hass.callService("printassist", "create_project", { name });
      await this._loadData();
    } catch (err) {
      console.error("Failed to create project:", err);
      alert("Failed to create project: " + err.message);
    }
  }

  async _deleteProject(projectId, e) {
    e.stopPropagation();
    if (!confirm("Delete this project and all its plates?")) return;

    await this.hass.callService("printassist", "delete_project", {
      project_id: projectId,
    });
    this._goBack();
    setTimeout(() => this._loadData(), 500);
  }

  async _handleFileUpload(e) {
    const files = e.target.files || e.dataTransfer?.files;
    if (!files?.length || !this._selectedProject) return;

    this._uploading = true;

    for (const file of files) {
      const formData = new FormData();
      formData.append("project_id", this._selectedProject.id);
      formData.append("file", file);

      try {
        const response = await fetch("/api/printassist/upload", {
          method: "POST",
          body: formData,
          headers: {
            Authorization: `Bearer ${this.hass.auth.data.access_token}`,
          },
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.error || "Upload failed");
        }

        await this._loadData();
      } catch (err) {
        console.error("Upload failed:", err);
        alert("Upload failed: " + err.message);
      }
    }

    this._uploading = false;
  }

  async _setQuantity(plateId, quantity) {
    if (quantity < 0) return;
    await this.hass.callService("printassist", "set_quantity", {
      plate_id: plateId,
      quantity,
    });
    setTimeout(() => this._loadData(), 300);
  }

  async _deletePlate(plateId) {
    if (!confirm("Delete this plate?")) return;
    await this.hass.callService("printassist", "delete_plate", {
      plate_id: plateId,
    });
    setTimeout(() => this._loadData(), 500);
  }

  async _startJob(jobId) {
    await this.hass.callService("printassist", "start_job", { job_id: jobId });
    setTimeout(() => this._loadData(), 500);
  }

  async _completeJob(jobId) {
    await this.hass.callService("printassist", "complete_job", { job_id: jobId });
    setTimeout(() => this._loadData(), 500);
  }

  async _failJob(jobId) {
    const reason = prompt("Failure reason (optional):");
    await this.hass.callService("printassist", "fail_job", {
      job_id: jobId,
      failure_reason: reason || undefined,
    });
    setTimeout(() => this._loadData(), 500);
  }

  _handleDragOver(e) {
    e.preventDefault();
    e.currentTarget.classList.add("dragover");
  }

  _handleDragLeave(e) {
    e.currentTarget.classList.remove("dragover");
  }

  _handleDrop(e) {
    e.preventDefault();
    e.currentTarget.classList.remove("dragover");
    this._handleFileUpload(e);
  }

  _getProjectPlates(projectId) {
    return (this._plates || []).filter((p) => p.project_id === projectId);
  }

  _getPlateJobs(plateId) {
    return (this._jobs || []).filter((j) => j.plate_id === plateId);
  }

  _getCompletedCount(plateId) {
    return this._getPlateJobs(plateId).filter((j) => j.status === "completed").length;
  }

  _getActiveJob() {
    return (this._jobs || []).find((j) => j.status === "printing");
  }

  _renderProjects() {
    return html`
      <div class="card-header">
        <span class="card-title">Projects</span>
        <button class="btn btn-primary" @click=${this._createProject}>
          + New Project
        </button>
      </div>

      ${this._projects.length === 0
        ? html`
            <div class="empty-state">
              <p>No projects yet. Create one to start organizing your prints.</p>
            </div>
          `
        : html`
            <div class="project-list">
              ${this._projects.map(
                (project) => {
                  const progress = project.total > 0
                    ? (project.completed / project.total) * 100
                    : 0;
                  return html`
                    <div
                      class="project-card"
                      @click=${() => this._selectProject(project)}
                    >
                      <div class="project-name">${project.name}</div>
                      <div class="project-meta">
                        ${project.completed} / ${project.total} prints completed
                      </div>
                      <div class="progress-bar">
                        <div class="progress-fill" style="width: ${progress}%"></div>
                      </div>
                    </div>
                  `;
                }
              )}
            </div>
          `}
    `;
  }

  _getNextQueuedJob() {
    const sorted = [...this._schedule];
    return sorted[0] || null;
  }

  _renderProjectDetail() {
    const plates = this._getProjectPlates(this._selectedProject.id);
    const activeJob = this._getActiveJob();
    const nextJob = this._getNextQueuedJob();
    const nextPlate = nextJob ? this._plates.find(p => p.id === nextJob.plate_id) : null;

    return html`
      <div class="back-btn" @click=${this._goBack}>← Back to Projects</div>

      <div class="card-header">
        <span class="card-title">${this._selectedProject.name}</span>
        <button
          class="btn btn-danger btn-small"
          @click=${(e) => this._deleteProject(this._selectedProject.id, e)}
        >
          Delete Project
        </button>
      </div>

      ${activeJob ? "" : nextJob && nextPlate ? html`
        <div class="next-job-banner">
          <div class="next-job-info">
            <div class="next-job-title">Next: ${nextJob.plate_name}</div>
            <div class="next-job-file">${nextPlate.source_filename} → Plate ${nextPlate.plate_number}</div>
          </div>
          <button class="btn btn-success" @click=${() => this._startJob(nextJob.job_id)}>
            Start Print
          </button>
        </div>
      ` : ""}

      <div
        class="upload-zone"
        @click=${() => this.shadowRoot.querySelector("#file-input").click()}
        @dragover=${this._handleDragOver}
        @dragleave=${this._handleDragLeave}
        @drop=${this._handleDrop}
      >
        <input
          type="file"
          id="file-input"
          accept=".3mf,.gcode"
          multiple
          @change=${this._handleFileUpload}
        />
        ${this._uploading
          ? "Uploading..."
          : "Drop 3MF or gcode files here, or click to browse"}
      </div>

      <div class="plate-list">
        ${plates.length === 0
          ? html`<div class="empty-state">No plates yet. Upload some files above.</div>`
          : plates.map(
              (plate) => {
                const completed = this._getCompletedCount(plate.id);
                const jobs = this._getPlateJobs(plate.id);
                const printingJob = jobs.find((j) => j.status === "printing");
                const queuedJobs = jobs.filter((j) => j.status === "queued");

                const finishedJobs = jobs
                  .filter((j) => j.status === "completed" || j.status === "failed")
                  .sort((a, b) => new Date(b.ended_at) - new Date(a.ended_at));

                return html`
                  <div class="plate-item">
                    ${plate.thumbnail_path
                      ? html`<img
                          class="plate-thumbnail"
                          src="${plate.thumbnail_path}"
                          alt="${plate.name}"
                        />`
                      : html`<div class="plate-thumbnail"></div>`}
                    <div class="plate-info">
                      <div class="plate-name">${plate.name}</div>
                      <div class="plate-meta">
                        ${this._formatDuration(plate.estimated_duration_seconds)}
                        · ${completed}/${plate.quantity_needed} done
                        · ${queuedJobs.length} queued
                        ${printingJob ? html`<span class="status-badge status-printing">Printing</span>` : ""}
                      </div>
                      <div class="plate-meta">${plate.source_filename}</div>
                    </div>
                    <div class="plate-actions">
                      <div class="quantity-control">
                        <button
                          class="quantity-btn"
                          @click=${() => this._setQuantity(plate.id, plate.quantity_needed - 1)}
                        >-</button>
                        <span class="quantity-value">${plate.quantity_needed}</span>
                        <button
                          class="quantity-btn"
                          @click=${() => this._setQuantity(plate.id, plate.quantity_needed + 1)}
                        >+</button>
                      </div>
                      <button
                        class="btn btn-secondary btn-small"
                        @click=${() => this._deletePlate(plate.id)}
                      >
                        Delete
                      </button>
                    </div>
                  </div>

                  ${printingJob ? html`
                    <div class="jobs-section">
                      <div class="job-item">
                        <span class="status-badge status-printing">Printing</span>
                        <span style="flex:1">Started ${new Date(printingJob.started_at).toLocaleTimeString()}</span>
                        <button class="btn btn-success btn-small" @click=${() => this._completeJob(printingJob.id)}>Complete</button>
                        <button class="btn btn-danger btn-small" @click=${() => this._failJob(printingJob.id)}>Failed</button>
                      </div>
                    </div>
                  ` : ""}

                  ${finishedJobs.length > 0 ? html`
                    <div class="jobs-history">
                      ${finishedJobs.map((job) => html`
                        <div class="job-history-item">
                          <span class="status-badge status-${job.status}">${job.status}</span>
                          <span>${new Date(job.ended_at).toLocaleString()}</span>
                          ${job.failure_reason ? html`<span class="failure-reason">${job.failure_reason}</span>` : ""}
                        </div>
                      `)}
                    </div>
                  ` : ""}
                `;
              }
            )}
      </div>
    `;
  }

  _renderSchedule() {
    const nextPrint = this.hass?.states["sensor.printassist_next_print"];
    const queueCount = this.hass?.states["sensor.printassist_queue_count"];
    const activeJob = this.hass?.states["sensor.printassist_active_job"];

    return html`
      <div class="card">
        <div class="card-title">Current Status</div>
        <p>
          ${activeJob?.state && activeJob.state !== "unknown"
            ? `Printing: ${activeJob.state}`
            : "Printer idle"}
        </p>
        <p>Queue: ${queueCount?.state || 0} jobs pending</p>
        ${nextPrint?.state && nextPrint.state !== "unknown"
          ? html`<p><strong>Next recommended:</strong> ${nextPrint.state}</p>`
          : ""}
      </div>

      <div class="card">
        <div class="card-title">Print Queue</div>
        ${this._schedule.length === 0
          ? html`<div class="empty-state">No jobs in queue</div>`
          : this._schedule.map(
              (item, index) => html`
                <div class="schedule-item">
                  <div class="schedule-number">${index + 1}</div>
                  ${item.thumbnail_path
                    ? html`<img
                        class="plate-thumbnail"
                        src="${item.thumbnail_path}"
                        alt="${item.plate_name}"
                      />`
                    : ""}
                  <div class="schedule-info">
                    <div class="plate-name">${item.plate_name}</div>
                    <div class="schedule-time">
                      ${item.source_filename} → Plate ${item.plate_number}
                      · ${this._formatDuration(item.estimated_duration_seconds)}
                    </div>
                  </div>
                </div>
              `
            )}
      </div>
    `;
  }

  render() {
    return html`
      <div class="header">
        <h1>PrintAssist</h1>
      </div>

      <div class="tabs">
        <button
          class="tab ${this._view === "projects" ||
          this._view === "project-detail"
            ? "active"
            : ""}"
          @click=${() => this._handleTabClick("projects")}
        >
          Projects
        </button>
        <button
          class="tab ${this._view === "schedule" ? "active" : ""}"
          @click=${() => this._handleTabClick("schedule")}
        >
          Schedule
        </button>
      </div>

      <div class="card">
        ${this._view === "projects"
          ? this._renderProjects()
          : this._view === "project-detail"
          ? this._renderProjectDetail()
          : this._renderSchedule()}
      </div>
    `;
  }
}

customElements.define("printassist-panel", PrintAssistPanel);
