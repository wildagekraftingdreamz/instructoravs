/* Instructoravs studio front end.
   One shell, one API: every panel reads or writes the same document payload the
   server returns, so the preview, the version list and the downloads can never
   drift apart. */

(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const API = "/api";
  const CATEGORY_KEY = "instructoravs.playbookCategory";
  const TOOLBAR_KEY = "instructoravs.toolbar";

  const state = {
    docs: [],
    doc: null,
    version: 0,
    payload: null,
    versions: [],
    view: "preview",
    kind: "auto",
    formMode: "guide",
    spec: null,
    playbooks: [],
    playbookIndex: 0,
  };

  const NOTES = {
    auto: "One sentence is enough. A built-in playbook supplies prerequisites, steps, checks and troubleshooting — then detail, tone and audience reshape it.",
    guide: "Describe the task. Matching playbooks cover login, passwords, MFA, VPN, Wi-Fi, printers, email, shared mailboxes, phone enrolment, asset handovers, software, backup, onboarding, remote desktop, Teams, site access, phishing and updates.",
    cv: "Give the target role, or paste the real details in Spec JSON. Without a spec the CV is a scaffold of placeholders, not invented facts.",
    form: "Fill the fields below; the form builds the same spec the JSON tab edits. Empty optional fields are skipped.",
    spec: "Full JSON control over sections, tables and CV fields. Load an example, edit it, then Generate.",
  };

  const CV_EXAMPLE = {
    kind: "cv",
    name: "Alex Morgan",
    headline: "Senior IT Support Engineer",
    contact: {
      email: "alex.morgan@example.com",
      phone: "+44 7700 900 123",
      location: "Manchester, UK",
      linkedin: "linkedin.com/in/alexmorgan",
    },
    summary:
      "Senior support engineer with eight years across managed Windows estates, Microsoft 365 and endpoint security. Known for turning recurring tickets into documented self-service guides.",
    skills: {
      Platforms: ["Windows 10/11", "macOS", "Microsoft 365", "Intune"],
      Tooling: ["PowerShell", "Entra ID", "ServiceNow", "JAMF"],
      Practice: ["ITIL 4", "Knowledge management", "Root-cause analysis"],
    },
    experience: [
      {
        role: "Senior IT Support Engineer",
        company: "Northwind Logistics",
        dates: "Jan 2021 – Present",
        location: "Manchester",
        bullets: [
          "Own second-line support for 1,200 users across 14 sites, closing 94% of tickets within SLA.",
          "Rebuilt the onboarding runbook, cutting first-day setup from 90 to 35 minutes.",
          "Introduced Intune compliance policies that removed 70% of manual patching checks.",
        ],
      },
      {
        role: "IT Support Technician",
        company: "Cedar Health",
        dates: "2017 – 2020",
        location: "Leeds",
        bullets: [
          "Supported clinical staff across three hospitals on a 24/7 rota.",
          "Wrote 40 knowledge-base articles adopted by the wider service desk.",
        ],
      },
    ],
    education: [
      {
        qualification: "BSc (Hons) Computing",
        institution: "Leeds Beckett University",
        dates: "2013 – 2016",
        grade: "First class",
      },
    ],
    certifications: ["Microsoft Certified: Endpoint Administrator (2023)", "ITIL 4 Foundation (2021)"],
    projects: [
      {
        name: "Self-service password reset",
        summary: "Rolled out SSPR with MFA for 1,200 users.",
        bullets: ["Password tickets fell by 62% in the first quarter after launch."],
      },
    ],
    languages: ["English (native)", "German (B1)"],
    availability: "One month's notice",
  };

  const GUIDE_EXAMPLE = {
    kind: "guide",
    title: "Issuing a loan laptop",
    purpose: "Hand a configured loan laptop to a colleague and record the handover.",
    meta: { "Applies to": "Loan pool, cabinet 2", Audience: "Service desk", "Time needed": "15 minutes" },
    prerequisites: ["The request has an approved ticket.", "A charged laptop from the loan pool."],
    sections: [
      {
        heading: "Step-by-step",
        steps: [
          { title: "Pick the next laptop", detail: "Take the oldest return in the pool so the stock rotates." },
          { title: "Record the asset tag", detail: "Add the tag and the colleague's name to the handover sheet." },
          { title: "Sign the handover", detail: "Ask the colleague to confirm receipt on the ticket." },
        ],
      },
      {
        heading: "Troubleshooting",
        table: {
          header: ["Symptom", "What to do"],
          rows: [
            ["Laptop will not power on", "Swap it for the next unit and flag this one for repair."],
            ["No loan unit available", "Escalate to the hardware team with the ticket number."],
          ],
        },
      },
    ],
  };

  const GUIDE_FORM_META = "Title, purpose, steps and troubleshooting — enough for a complete guide.";
  const CV_FORM_META = "Contact, summary, skills, roles and education; optional sections are skipped when empty.";

  const lines = (value) => String(value || "").split("\n").map((line) => line.trim()).filter(Boolean);
  const splitList = (value) => String(value || "").split(",").map((item) => item.trim()).filter(Boolean);

  function addStepRow(values = {}, focus = false) {
    const row = document.createElement("div");
    row.className = "repeat-row step-row";
    row.innerHTML = `
      <input class="step-title" placeholder="Step title" value="${esc(values.title || "")}">
      <textarea class="step-detail" rows="2" placeholder="What to do">${esc(values.detail || "")}</textarea>
      <button type="button" class="icon-btn row-del" title="Remove step" aria-label="Remove step">✕</button>`;
    row.querySelector(".row-del").addEventListener("click", () => { row.remove(); updateFormSummary(); });
    $("gSteps").appendChild(row);
    if (focus) row.querySelector(".step-title").focus();
    updateFormSummary();
    return row;
  }

  function addIssueRow(symptom = "", fix = "") {
    const row = document.createElement("div");
    row.className = "repeat-row issue-row";
    row.innerHTML = `
      <input class="issue-symptom" placeholder="Symptom" value="${esc(symptom)}">
      <textarea class="issue-fix" rows="2" placeholder="What to do">${esc(fix)}</textarea>
      <button type="button" class="icon-btn row-del" title="Remove row" aria-label="Remove row">✕</button>`;
    row.querySelector(".row-del").addEventListener("click", () => { row.remove(); updateFormSummary(); });
    $("gIssues").appendChild(row);
    updateFormSummary();
    return row;
  }

  function addRoleRow(values = {}) {
    const row = document.createElement("div");
    row.className = "repeat-row role-row";
    row.innerHTML = `
      <input class="role-title" placeholder="Role" value="${esc(values.role || "")}">
      <input class="role-company" placeholder="Company" value="${esc(values.company || "")}">
      <button type="button" class="icon-btn row-del" title="Remove role" aria-label="Remove role">✕</button>
      <input class="role-dates" placeholder="Dates, e.g. Jan 2021 – Present" value="${esc(values.dates || "")}">
      <input class="role-location" placeholder="Location" value="${esc(values.location || "")}">
      <textarea class="role-bullets" rows="2" placeholder="Achievements — one per line">${esc((values.bullets || []).join("\n"))}</textarea>`;
    row.querySelector(".row-del").addEventListener("click", () => { row.remove(); updateFormSummary(); });
    $("cvRoles").appendChild(row);
    updateFormSummary();
    return row;
  }

  function addEducationRow(values = {}) {
    const row = document.createElement("div");
    row.className = "repeat-row edu-row";
    row.innerHTML = `
      <input class="edu-qualification" placeholder="Qualification" value="${esc(values.qualification || "")}">
      <input class="edu-institution" placeholder="Institution" value="${esc(values.institution || "")}">
      <button type="button" class="icon-btn row-del" title="Remove education" aria-label="Remove education">✕</button>
      <input class="edu-dates" placeholder="Dates" value="${esc(values.dates || "")}">
      <input class="edu-grade" placeholder="Grade (optional)" value="${esc(values.grade || "")}">`;
    row.querySelector(".row-del").addEventListener("click", () => { row.remove(); updateFormSummary(); });
    $("cvEducation").appendChild(row);
    updateFormSummary();
    return row;
  }

  function addProjectRow(values = {}) {
    const row = document.createElement("div");
    row.className = "repeat-row project-row";
    row.innerHTML = `
      <input class="project-name" placeholder="Project name" value="${esc(values.name || "")}">
      <input class="project-summary" placeholder="One-line summary" value="${esc(values.summary || "")}">
      <button type="button" class="icon-btn row-del" title="Remove project" aria-label="Remove project">✕</button>
      <textarea class="project-bullets" rows="2" placeholder="Highlights — one per line">${esc((values.bullets || []).join("\n"))}</textarea>`;
    row.querySelector(".row-del").addEventListener("click", () => { row.remove(); updateFormSummary(); });
    $("cvProjects").appendChild(row);
    updateFormSummary();
    return row;
  }

  function updateFormSummary() {
    if (!$("formSummary")) return;
    if (state.formMode === "cv") {
      const roles = document.querySelectorAll("#cvRoles .role-row").length;
      const certifications = lines($("cvCerts").value).length;
      $("formSummary").textContent =
        `${roles} role${roles === 1 ? "" : "s"} · ${certifications} certification${certifications === 1 ? "" : "s"}`;
      return;
    }
    const steps = document.querySelectorAll("#gSteps .step-row").length;
    const issues = document.querySelectorAll("#gIssues .issue-row").length;
    $("formSummary").textContent =
      `${steps} step${steps === 1 ? "" : "s"} · ${issues} troubleshooting row${issues === 1 ? "" : "s"}`;
  }

  function setFormMode(mode, { silent = false } = {}) {
    state.formMode = mode === "cv" ? "cv" : "guide";
    document.querySelectorAll("#formModeTabs button").forEach((button) => {
      const active = button.dataset.form === state.formMode;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", String(active));
    });
    $("guideForm").hidden = state.formMode !== "guide";
    $("cvForm").hidden = state.formMode !== "cv";
    $("formModeMeta").textContent = state.formMode === "cv" ? CV_FORM_META : GUIDE_FORM_META;
    updateFormSummary();
    if (!silent) hint("");
  }

  function buildGuideSpec() {
    const title = $("gTitle").value.trim();
    if (!title) throw new Error("Give the guide a title first.");
    const spec = { kind: "guide", title };
    const purpose = $("gPurpose").value.trim();
    if (purpose) spec.purpose = purpose;

    const meta = {};
    [
      ["Applies to", $("gApplies").value.trim()],
      ["Audience", $("gAudience").value.trim()],
      ["Time needed", $("gTime").value.trim()],
      ["Owner", $("gOwner").value.trim()],
    ].forEach(([key, value]) => { if (value) meta[key] = value; });
    if (Object.keys(meta).length) spec.meta = meta;

    const prerequisites = lines($("gPrereqs").value);
    if (prerequisites.length) spec.prerequisites = prerequisites;

    const sections = [];
    const steps = [...document.querySelectorAll("#gSteps .step-row")]
      .map((row) => ({
        title: row.querySelector(".step-title").value.trim(),
        detail: row.querySelector(".step-detail").value.trim(),
      }))
      .filter((step) => step.title || step.detail);
    if (steps.length) sections.push({ heading: "Step-by-step", steps });

    const checklist = lines($("gVerify").value);
    if (checklist.length) sections.push({ heading: "Verify it worked", checklist });

    const rows = [...document.querySelectorAll("#gIssues .issue-row")]
      .map((row) => [
        row.querySelector(".issue-symptom").value.trim(),
        row.querySelector(".issue-fix").value.trim(),
      ])
      .filter(([symptom, fix]) => symptom || fix);
    if (rows.length) {
      sections.push({ heading: "Troubleshooting", table: { header: ["Symptom", "What to do"], rows } });
    }

    if (sections.length) spec.sections = sections;
    const footer = $("gFooter").value.trim();
    if (footer) spec.footer = footer;
    return spec;
  }

  function buildCvSpec() {
    const name = $("cvName").value.trim();
    if (!name) throw new Error("A CV needs a name first.");
    const spec = { kind: "cv", name };
    const headline = $("cvHeadline").value.trim();
    const summary = $("cvSummary").value.trim();
    if (headline) spec.headline = headline;
    if (summary) spec.summary = summary;

    const contact = {};
    [
      ["email", $("cvEmail")],
      ["phone", $("cvPhone")],
      ["location", $("cvLocation")],
      ["linkedin", $("cvLinkedin")],
    ].forEach(([key, input]) => { const value = input.value.trim(); if (value) contact[key] = value; });
    if (Object.keys(contact).length) spec.contact = contact;

    const groups = {};
    lines($("cvSkills").value).forEach((line) => {
      const at = line.indexOf(":");
      if (at > 0) {
        const group = line.slice(0, at).trim();
        groups[group] = [...(groups[group] || []), ...splitList(line.slice(at + 1))];
      } else {
        groups.Skills = [...(groups.Skills || []), ...splitList(line)];
      }
    });
    if (Object.keys(groups).length) spec.skills = groups;

    const certifications = lines($("cvCerts").value);
    if (certifications.length) spec.certifications = certifications;

    const experience = [...document.querySelectorAll("#cvRoles .role-row")]
      .map((row) => ({
        role: row.querySelector(".role-title").value.trim(),
        company: row.querySelector(".role-company").value.trim(),
        dates: row.querySelector(".role-dates").value.trim(),
        location: row.querySelector(".role-location").value.trim(),
        bullets: lines(row.querySelector(".role-bullets").value),
      }))
      .filter((entry) => entry.role || entry.company);
    if (experience.length) spec.experience = experience;

    const education = [...document.querySelectorAll("#cvEducation .edu-row")]
      .map((row) => ({
        qualification: row.querySelector(".edu-qualification").value.trim(),
        institution: row.querySelector(".edu-institution").value.trim(),
        dates: row.querySelector(".edu-dates").value.trim(),
        grade: row.querySelector(".edu-grade").value.trim(),
      }))
      .filter((entry) => entry.qualification || entry.institution);
    if (education.length) spec.education = education;

    const projects = [...document.querySelectorAll("#cvProjects .project-row")]
      .map((row) => ({
        name: row.querySelector(".project-name").value.trim(),
        summary: row.querySelector(".project-summary").value.trim(),
        bullets: lines(row.querySelector(".project-bullets").value),
      }))
      .filter((entry) => entry.name || entry.summary);
    if (projects.length) spec.projects = projects;

    const languages = lines($("cvLanguages").value);
    if (languages.length) spec.languages = languages;
    const availability = $("cvAvailability").value.trim();
    if (availability) spec.availability = availability;
    const references = $("cvReferences").value.trim();
    if (references) spec.references = references;
    return spec;
  }

  function buildFormSpec() {
    return state.formMode === "cv" ? buildCvSpec() : buildGuideSpec();
  }

  function sectionOf(example, key) {
    return (example.sections || []).find((section) => section && section[key]);
  }

  function fillGuideForm(example) {
    $("gTitle").value = example.title || "";
    $("gPurpose").value = example.purpose || "";
    const meta = example.meta || {};
    $("gApplies").value = meta["Applies to"] || "";
    $("gAudience").value = meta.Audience || "";
    $("gTime").value = meta["Time needed"] || "";
    $("gOwner").value = meta.Owner || "";
    $("gPrereqs").value = (example.prerequisites || []).join("\n");
    $("gSteps").innerHTML = "";
    (sectionOf(example, "steps")?.steps || []).forEach((step) => addStepRow(step));
    if (!$("gSteps").children.length) addStepRow();
    $("gIssues").innerHTML = "";
    const table = sectionOf(example, "table")?.table;
    (table?.rows || []).forEach((row) => addIssueRow(row[0] || "", row[1] || ""));
    if (!$("gIssues").children.length) addIssueRow();
    $("gVerify").value = (sectionOf(example, "checklist")?.checklist || []).join("\n");
    $("gFooter").value = example.footer || "";
    updateFormSummary();
  }

  function fillCvForm(example) {
    $("cvName").value = example.name || "";
    $("cvHeadline").value = example.headline || "";
    const contact = example.contact || {};
    $("cvEmail").value = contact.email || "";
    $("cvPhone").value = contact.phone || "";
    $("cvLocation").value = contact.location || "";
    $("cvLinkedin").value = contact.linkedin || contact.website || "";
    $("cvSummary").value = example.summary || "";
    const skills = example.skills || {};
    $("cvSkills").value = Array.isArray(skills)
      ? skills.join(", ")
      : Object.entries(skills).map(([group, items]) => `${group}: ${[].concat(items).join(", ")}`).join("\n");
    $("cvCerts").value = (example.certifications || []).join("\n");
    $("cvRoles").innerHTML = "";
    (example.experience || []).forEach((role) => addRoleRow(role));
    if (!$("cvRoles").children.length) addRoleRow();
    $("cvEducation").innerHTML = "";
    (example.education || []).forEach((entry) => addEducationRow(entry));
    if (!$("cvEducation").children.length) addEducationRow();
    $("cvProjects").innerHTML = "";
    (example.projects || []).forEach((project) => addProjectRow(project));
    $("cvLanguages").value = (example.languages || []).join("\n");
    $("cvAvailability").value = example.availability || "";
    $("cvReferences").value = example.references || "";
    updateFormSummary();
  }

  function viewFormJson() {
    try {
      const spec = buildFormSpec();
      state.spec = spec;
      $("specText").value = JSON.stringify(spec, null, 2);
      $("specDialog").showModal();
      $("specText").focus();
    } catch (error) {
      hint(error.message, "error");
      toast(error.message, true);
    }
  }

  function seedForm() {
    if (!$("gSteps").children.length) addStepRow();
    if (!$("gIssues").children.length) addIssueRow();
    if (!$("cvRoles").children.length) addRoleRow();
    if (!$("cvEducation").children.length) addEducationRow();
    setFormMode("guide", { silent: true });
  }

  const esc = (value) =>
    String(value ?? "").replace(/[&<>"']/g, (char) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[char]);

  const when = (iso) => (iso ? iso.slice(0, 16).replace("T", " ") : "");

  async function api(path, options = {}) {
    const response = await fetch(API + path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    if (!response.ok) {
      let detail = `${response.status} ${response.statusText}`;
      try {
        const body = await response.json();
        if (body && body.detail) {
          detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
        }
      } catch (_) { /* non-JSON error body */ }
      throw new Error(detail);
    }
    return response.json();
  }

  function toast(text, isError = false) {
    const node = $("toast");
    node.textContent = text;
    node.classList.toggle("error", isError);
    node.hidden = false;
    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => { node.hidden = true; }, 3200);
  }

  function hint(text, kind = "") {
    const node = $("hint");
    node.textContent = text;
    node.className = `hint${kind ? " " + kind : ""}`;
  }

  function formats() {
    return [...document.querySelectorAll("#formatPills input:checked")].map((box) => box.value);
  }

  function preferenceDiffs() {
    const label = (id) => $(id).selectedOptions[0]?.textContent.trim() || $(id).value;
    const diffs = [];
    if ($("detailSelect").value !== "standard") diffs.push(`Detail: ${label("detailSelect")}`);
    if ($("toneSelect").value !== "professional") diffs.push(`Tone: ${label("toneSelect")}`);
    if ($("audienceSelect").value !== "general") diffs.push(`Audience: ${label("audienceSelect")}`);
    const selected = formats();
    const defaults = ["md", "txt", "pdf", "docx"];
    if (selected.length !== defaults.length || !defaults.every((value) => selected.includes(value))) {
      const names = selected.length ? selected.map((value) => `.${value}`).join(" ") : "none";
      diffs.push(`Formats: ${names}`);
    }
    return diffs;
  }

  function announcePreferences(diffs) {
    const live = $("prefLive");
    if (!live) return;
    const message = diffs.length
      ? `Toolbar customized: ${diffs.join("; ")}.`
      : "Toolbar is at default settings.";
    if (live.textContent !== message) live.textContent = message;
  }

  function updatePrefState() {
    const badge = $("prefState");
    const diffs = preferenceDiffs();
    badge.hidden = diffs.length === 0;
    if (diffs.length) {
      badge.title = `Differs from defaults — ${diffs.join(" · ")}`;
    } else {
      badge.removeAttribute("title");
    }
    announcePreferences(diffs);
  }

  function saveToolbar() {
    try {
      localStorage.setItem(
        TOOLBAR_KEY,
        JSON.stringify({
          detail: $("detailSelect").value,
          tone: $("toneSelect").value,
          audience: $("audienceSelect").value,
          formats: formats(),
        })
      );
    } catch (error) {
      // Storage can be blocked; the toolbar still works for this session.
    }
    updatePrefState();
  }

  function restoreToolbar() {
    let saved = {};
    try {
      saved = JSON.parse(localStorage.getItem(TOOLBAR_KEY) || "{}");
    } catch (error) {
      saved = {};
    }
    const applySelect = (id, value) => {
      const select = $(id);
      if (typeof value === "string" && [...select.options].some((option) => option.value === value)) {
        select.value = value;
      }
    };
    applySelect("detailSelect", saved.detail);
    applySelect("toneSelect", saved.tone);
    applySelect("audienceSelect", saved.audience);
    if (Array.isArray(saved.formats)) {
      const wanted = new Set(saved.formats.filter((value) => typeof value === "string"));
      const boxes = [...document.querySelectorAll("#formatPills input")];
      if (wanted.size && boxes.some((box) => wanted.has(box.value))) {
        boxes.forEach((box) => {
          box.checked = wanted.has(box.value);
        });
      }
    }
    updatePrefState();
  }

  function fileUrl(fmt, inline = false) {
    if (!state.doc) return "#";
    const version = state.version ? `&version=${state.version}` : "";
    return `${API}/documents/${encodeURIComponent(state.doc.id)}/file?format=${fmt}${version}${inline ? "&inline=1" : ""}`;
  }

  function resetPreferences() {
    $("detailSelect").value = "standard";
    $("toneSelect").value = "professional";
    $("audienceSelect").value = "general";
    document.querySelectorAll("#formatPills input").forEach((box) => {
      box.checked = ["md", "txt", "pdf", "docx"].includes(box.value);
    });
    const select = $("playbookCategory");
    if (select.options.length > 1) select.value = "all";
    try {
      localStorage.removeItem(TOOLBAR_KEY);
      localStorage.removeItem(CATEGORY_KEY);
    } catch (error) {
      // Storage can be blocked; the defaults still apply to this session.
    }
    updatePrefState();
    toast("Preferences reset to defaults");
  }

  // ── rendering ────────────────────────────────────────────────────────────
  function renderDocs(docs) {
    state.docs = docs;
    $("libMeta").textContent = `${docs.length} document${docs.length === 1 ? "" : "s"}`;
    const list = $("docList");
    if (!docs.length) {
      list.innerHTML = '<li class="empty">Every generated document is listed here.</li>';
      return;
    }
    list.innerHTML = docs.map((doc) => `
      <li data-doc="${esc(doc.id)}" class="${state.doc && state.doc.id === doc.id ? "active" : ""}">
        <span class="vnum">${doc.kind === "cv" ? "CV" : "GD"}</span>
        <span class="vbody">
          <b>${esc(doc.title)}</b>
          <small>v${doc.version} · ${doc.words} words · ${esc(doc.detail || "standard")}</small>
        </span>
        <span class="when">${esc(when(doc.updated))}</span>
      </li>`).join("");
    list.querySelectorAll("li[data-doc]").forEach((row) => {
      row.addEventListener("click", () => loadDoc(row.dataset.doc));
    });
  }

  function renderVersions() {
    const list = $("versionList");
    const versions = state.versions;
    $("versionMeta").textContent = state.doc
      ? `${versions.length} version${versions.length === 1 ? "" : "s"} · latest v${state.doc.version}`
      : "no document";
    if (!versions.length) {
      list.innerHTML = '<li class="empty">Versions appear after the first generate.</li>';
      return;
    }
    list.innerHTML = versions.map((version) => `
      <li data-version="${version.number}" class="${version.number === state.version ? "active" : ""}">
        <span class="vnum">v${version.number}</span>
        <span class="vbody">
          <b>${esc(version.message)}</b>
          <small>${version.words} words${version.annotations.length ? ` · ${version.annotations.length} note${version.annotations.length === 1 ? "" : "s"}` : ""}${version.parent ? ` · from v${version.parent}` : ""}</small>
        </span>
        <span class="when">${esc(when(version.created))}</span>
      </li>`).join("");
    list.querySelectorAll("li[data-version]").forEach((row) => {
      row.addEventListener("click", () => loadDoc(state.doc.id, Number(row.dataset.version)));
    });
  }

  function statsMarkup(payload) {
    return `
      <div class="doc-stat"><span class="k">version</span><span class="v">v${payload.number}</span></div>
      <div class="doc-stat"><span class="k">words</span><span class="v">${payload.words}</span></div>
      <div class="doc-stat"><span class="k">formats</span><span class="v">${esc(payload.formats.join(" "))}</span></div>
      <div class="doc-stat"><span class="k">notes</span><span class="v">${payload.annotations.length}</span></div>`;
  }

  function setView(view) {
    state.view = view;
    document.querySelectorAll("#viewTabs button").forEach((button) => {
      const active = button.dataset.view === view;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", String(active));
    });
    const panes = {
      preview: $("previewPane"),
      markdown: $("mdPane"),
      text: $("txtPane"),
      pdf: $("pdfPaneWrap"),
    };
    Object.entries(panes).forEach(([name, node]) => { node.hidden = name !== view; });
    if (view === "pdf" && state.doc) {
      $("pdfPane").src = `${fileUrl("pdf", true)}&_=${Date.now()}`;
    }
  }

  function renderDoc() {
    const payload = state.payload;
    if (!payload) return;
    $("emptyDoc").hidden = true;
    $("docTitle").textContent = payload.title;
    $("versionChip").hidden = false;
    $("versionChip").textContent = `v${payload.number} · ${payload.prefs.detail || "standard"}`;
    $("docStats").innerHTML = statsMarkup(payload);
    $("previewPane").innerHTML = payload.html;
    $("mdPane").textContent = payload.markdown;
    $("txtPane").textContent = payload.text;

    ["mdBtn", "pdfBtn", "docxBtn", "editBtn", "diffBtn", "annotateBtn", "restoreBtn", "csvBtn"].forEach((id) => {
      $(id).disabled = false;
    });
    $("editWrap").hidden = true;
    $("editBtn").textContent = "✎ Edit";
    setView(state.view);
  }

  // ── data flow ────────────────────────────────────────────────────────────
  async function refreshDocs() {
    const [docs, health] = await Promise.all([api("/documents"), api("/health")]);
    renderDocs(docs);
    $("storeBadge").textContent = `${health.documents} documents · ${health.versions} versions`;
    $("storeBadge").title = health.root;
  }

  async function loadDoc(id, version) {
    const query = version ? `?version=${version}` : "";
    try {
      const payload = await api(`/documents/${encodeURIComponent(id)}${query}`);
      state.doc = payload.document;
      state.version = payload.number;
      state.payload = payload;
      state.versions = payload.versions || [];
      renderDoc();
      renderVersions();
      renderDocs(state.docs);
      $("hint").textContent = "";
      $("hint").className = "hint";
    } catch (error) {
      toast(error.message, true);
      hint(error.message, "error");
    }
  }

  function prefsBody() {
    return {
      detail: $("detailSelect").value,
      tone: $("toneSelect").value,
      audience: $("audienceSelect").value,
    };
  }

  async function generate() {
    let instruction = $("instruction").value.trim();
    let spec = state.kind === "spec" ? state.spec : null;
    if (state.kind === "form") {
      try {
        spec = buildFormSpec();
        instruction = "";
      } catch (error) {
        hint(error.message, "error");
        toast(error.message, true);
        return;
      }
    }
    if (state.kind === "spec" && !spec) {
      openSpec();
      hint("Load or paste a spec, then press Generate again.", "error");
      return;
    }
    if (!instruction && !spec) {
      hint("Write one sentence first — for example “Create a guide for user login”.", "error");
      $("instruction").focus();
      return;
    }
    const button = $("generateBtn");
    const formButton = $("formGenerate");
    button.disabled = true;
    button.textContent = "Generating…";
    if (formButton) formButton.disabled = true;
    hint("Writing the document and rendering the formats…");
    try {
      const body = {
        instruction,
        kind: state.kind === "form" ? spec.kind : state.kind === "spec" ? "auto" : state.kind,
        detail: $("detailSelect").value,
        prefs: { tone: $("toneSelect").value, audience: $("audienceSelect").value },
        spec,
        formats: formats(),
        message: "Initial version",
      };
      const payload = await api("/documents", { method: "POST", body: JSON.stringify(body) });
      await loadDoc(payload.document.id);
      await refreshDocs();
      hint(`Saved ${payload.title} as v${payload.number}.`, "ok");
      toast(`v${payload.number} · ${payload.formats.join(" ")}`);
    } catch (error) {
      hint(error.message, "error");
      toast(error.message, true);
    } finally {
      button.disabled = false;
      button.textContent = "Generate ↵";
      if (formButton) formButton.disabled = false;
    }
  }

  // ── version actions ──────────────────────────────────────────────────────
  function openAnnotate() {
    if (!state.doc) return;
    $("annotateSub").textContent = `v${state.version} · ${state.doc.title}`;
    $("annotateText").value = "";
    $("annotateDialog").showModal();
    $("annotateText").focus();
  }

  async function saveAnnotation() {
    const text = $("annotateText").value.trim();
    if (!text) { $("annotateText").focus(); return; }
    try {
      await api(`/documents/${encodeURIComponent(state.doc.id)}/versions/${state.version}/annotate`, {
        method: "POST",
        body: JSON.stringify({ text }),
      });
      $("annotateDialog").close();
      await loadDoc(state.doc.id, state.version);
      toast("Note saved to this version");
    } catch (error) {
      toast(error.message, true);
    }
  }

  function openDiff() {
    if (!state.versions.length) return;
    const options = [...state.versions]
      .sort((a, b) => a.number - b.number)
      .map((version) => `<option value="${version.number}">v${version.number} — ${esc(version.message)}</option>`)
      .join("");
    $("diffA").innerHTML = options;
    $("diffB").innerHTML = options;
    const numbers = state.versions.map((version) => version.number).sort((a, b) => a - b);
    $("diffB").value = String(state.version || numbers[numbers.length - 1]);
    const previous = numbers.filter((number) => number < Number($("diffB").value)).pop();
    $("diffA").value = String(previous || numbers[0]);
    $("diffBody").textContent = "Choose two versions.";
    $("diffDialog").showModal();
    runDiff();
  }

  async function runDiff() {
    if (!state.doc) return;
    try {
      const data = await api(
        `/documents/${encodeURIComponent(state.doc.id)}/diff?a=${$("diffA").value}&b=${$("diffB").value}`
      );
      $("diffBody").textContent = data.diff || `No line changes between v${data.a} and v${data.b}.`;
    } catch (error) {
      $("diffBody").textContent = error.message;
    }
  }

  async function restore() {
    if (!state.doc) return;
    try {
      const payload = await api(
        `/documents/${encodeURIComponent(state.doc.id)}/versions/${state.version}/restore`,
        { method: "POST" }
      );
      await loadDoc(payload.document.id);
      await refreshDocs();
      toast(`Restored v${state.version} as v${payload.number}`);
    } catch (error) {
      toast(error.message, true);
    }
  }

  function openEdit() {
    if (!state.payload) return;
    $("editArea").value = state.payload.markdown;
    $("editMessage").value = "";
    $("editWrap").hidden = false;
    $("editBtn").textContent = "✎ Editing";
    $("editArea").focus();
    $("editWrap").scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  async function saveEdit() {
    const markdown = $("editArea").value;
    if (!markdown.trim()) { hint("The document cannot be empty.", "error"); return; }
    const message = $("editMessage").value.trim() || "Edited by hand";
    $("editSave").disabled = true;
    try {
      const payload = await api(`/documents/${encodeURIComponent(state.doc.id)}/versions`, {
        method: "POST",
        body: JSON.stringify({ markdown, message }),
      });
      await loadDoc(payload.document.id);
      await refreshDocs();
      toast(`Saved v${payload.number}`);
    } catch (error) {
      toast(error.message, true);
      hint(error.message, "error");
    } finally {
      $("editSave").disabled = false;
    }
  }

  // ── spec dialog ──────────────────────────────────────────────────────────
  function openSpec() {
    if (!state.spec) {
      state.spec = state.kind === "cv" ? CV_EXAMPLE : GUIDE_EXAMPLE;
    }
    $("specText").value = JSON.stringify(state.spec, null, 2);
    $("specDialog").showModal();
    $("specText").focus();
  }

  function useSpec() {
    const raw = $("specText").value.trim();
    if (!raw) {
      $("specDialog").close();
      return;
    }
    try {
      const parsed = JSON.parse(raw);
      if (typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("spec must be a JSON object");
      state.spec = parsed;
      setKind("spec", { silent: true });
      $("specDialog").close();
      hint("Spec loaded. Press Generate to build the document.", "ok");
    } catch (error) {
      hint(`Invalid JSON: ${error.message}`, "error");
    }
  }

  // ── playbook picker ──────────────────────────────────────────────────────
  function rememberedCategory() {
    try {
      return localStorage.getItem(CATEGORY_KEY) || "all";
    } catch (error) {
      return "all";
    }
  }

  function rememberCategory(category) {
    try {
      localStorage.setItem(CATEGORY_KEY, category);
    } catch (error) {
      // Storage can be blocked; the picker still works for this session.
    }
  }

  let pickerAnnouncement = 0;
  let pickerSearchTimer = 0;

  function announcePicker(message) {
    const live = $("pickerLive");
    if (!live) return;
    if (live.textContent !== message) {
      live.textContent = message;
      return;
    }
    // Clear the identical text briefly so it is announced again. A timer is
    // used because animation frames pause while the tab is in the background.
    const ticket = ++pickerAnnouncement;
    live.textContent = "";
    setTimeout(() => {
      if (ticket === pickerAnnouncement) live.textContent = message;
    }, 50);
  }

  function pickerCategoryLabel() {
    return $("playbookCategory").selectedOptions[0]?.textContent.trim() || "All topic areas";
  }

  function announcePickerCategory(prefix = "Topic area") {
    const count = document.querySelectorAll("#playbookList .playbook-item").length;
    const noun = count === 1 ? "playbook" : "playbooks";
    announcePicker(`${prefix}: ${pickerCategoryLabel()}. ${count} ${noun}.`);
  }

  function announcePickerResults() {
    const query = $("playbookSearch").value.trim();
    const count = document.querySelectorAll("#playbookList .playbook-item").length;
    const noun = count === 1 ? "playbook" : "playbooks";
    if (!query) {
      announcePicker(`${count} ${noun} in ${pickerCategoryLabel()}.`);
      return;
    }
    const scope = $("playbookCategory").value === "all" ? "" : ` in ${pickerCategoryLabel()}`;
    if (!count) {
      announcePicker(`No playbooks match “${query}”${scope}.`);
      return;
    }
    const verb = count === 1 ? "matches" : "match";
    announcePicker(`${count} ${noun} ${verb} “${query}”${scope}.`);
  }

  function queuePickerResults() {
    clearTimeout(pickerSearchTimer);
    pickerSearchTimer = setTimeout(announcePickerResults, 250);
  }

  async function openPlaybooks(category = null) {
    $("playbookSearch").value = "";
    $("playbookDialog").showModal();
    $("playbookSearch").focus();
    if (!state.playbooks.length) {
      $("playbookList").innerHTML = '<p class="playbook-loading">Loading built-in topics…</p>';
      $("playbookEmpty").hidden = true;
      try {
        state.playbooks = await api("/playbooks");
      } catch (error) {
        $("playbookList").innerHTML =
          `<p class="playbook-loading">Could not load playbooks: ${esc(error.message)}</p>`;
        return;
      }
    }
    ensureCategoryOptions();
    const select = $("playbookCategory");
    const wanted = category || rememberedCategory();
    const known = [...select.options].some((option) => option.value === wanted);
    select.value = known ? wanted : "all";
    rememberCategory(select.value);
    renderPlaybooks();
    announcePickerCategory("Playbook picker opened. Topic area");
  }

  function ensureCategoryOptions() {
    const select = $("playbookCategory");
    if (select.options.length > 1 || !state.playbooks.length) return;
    const categories = [...new Set(state.playbooks.map((playbook) => playbook.category))];
    select.innerHTML =
      '<option value="all">All topic areas</option>' +
      categories
        .map((category) => `<option value="${esc(category)}">${esc(category)}</option>`)
        .join("");
  }

  function highlight(text, query) {
    const value = String(text);
    if (!query) return esc(value);
    const lower = value.toLowerCase();
    let out = "";
    let start = 0;
    let at = lower.indexOf(query);
    while (at !== -1) {
      out += esc(value.slice(start, at));
      out += `<mark>${esc(value.slice(at, at + query.length))}</mark>`;
      start = at + query.length;
      at = lower.indexOf(query, start);
    }
    return out + esc(value.slice(start));
  }

  function playbookCard(playbook, query = "") {
    return `
      <button type="button" class="playbook-item" data-playbook="${esc(playbook.key)}">
        <b>${highlight(playbook.title, query)}</b>
        <small>${highlight(playbook.applies_to, query)}</small>
        <span class="playbook-meta">${playbook.steps} step${playbook.steps === 1 ? "" : "s"} · ${esc(playbook.time)}</span>
        <span class="playbook-prereq">Starts with: ${highlight(playbook.first_prerequisite, query)}</span>
      </button>`;
  }

  function rankPlaybook(playbook, query) {
    const title = playbook.title.toLowerCase();
    if (title.startsWith(query)) return 0;
    if (title.includes(query)) return 1;
    if (playbook.key.toLowerCase().includes(query)) return 2;
    if (playbook.category.toLowerCase().includes(query)) return 3;
    if (playbook.applies_to.toLowerCase().includes(query)) return 4;
    return 5;
  }

  function setActivePlaybook(index, { announce = false } = {}) {
    const cards = [...document.querySelectorAll("#playbookList .playbook-item")];
    if (!cards.length) {
      state.playbookIndex = -1;
      if (announce) announcePicker("No playbooks match the current filter.");
      return;
    }
    state.playbookIndex = Math.max(0, Math.min(index, cards.length - 1));
    cards.forEach((card, position) => {
      const active = position === state.playbookIndex;
      card.classList.toggle("active", active);
      if (active) {
        card.setAttribute("aria-current", "true");
      } else {
        card.removeAttribute("aria-current");
      }
    });
    const activeCard = cards[state.playbookIndex];
    activeCard.scrollIntoView({ block: "nearest" });
    if (!announce) return;
    const playbook = state.playbooks.find((item) => item.key === activeCard.dataset.playbook);
    if (!playbook) {
      announcePicker(`${state.playbookIndex + 1} of ${cards.length}.`);
      return;
    }
    const steps = `${playbook.steps} step${playbook.steps === 1 ? "" : "s"}`;
    announcePicker(
      `${state.playbookIndex + 1} of ${cards.length}: ${playbook.title}. ` +
      `${playbook.category}, ${steps}, ${playbook.time}.`
    );
  }

  function renderPlaybooks() {
    clearTimeout(pickerSearchTimer);
    ensureCategoryOptions();
    const query = $("playbookSearch").value.trim().toLowerCase();
    const category = $("playbookCategory").value || "all";
    state.playbookIndex = 0;
    let items = state.playbooks.filter((playbook) => {
      if (category !== "all" && playbook.category !== category) return false;
      if (!query) return true;
      return `${playbook.title} ${playbook.applies_to} ${playbook.time} ${playbook.key} ${playbook.category}`
        .toLowerCase()
        .includes(query);
    });
    $("playbookTotal").textContent = String(state.playbooks.length);
    $("playbookEmpty").hidden = items.length > 0;

    if (query) {
      items = [...items].sort((a, b) => rankPlaybook(a, query) - rankPlaybook(b, query));
      $("playbookList").innerHTML = `
        <section class="playbook-group">
          <h3>Best matches <span>${items.length}</span></h3>
          <div class="playbook-grid">${items.map((playbook) => playbookCard(playbook, query)).join("")}</div>
        </section>`;
    } else {
      const groups = new Map();
      items.forEach((playbook) => {
        if (!groups.has(playbook.category)) groups.set(playbook.category, []);
        groups.get(playbook.category).push(playbook);
      });
      $("playbookList").innerHTML = [...groups.entries()]
        .map(([name, groupItems]) => `
        <section class="playbook-group">
          <h3>${esc(name)} <span>${groupItems.length}</span></h3>
          <div class="playbook-grid">${groupItems.map((playbook) => playbookCard(playbook, query)).join("")}</div>
        </section>`)
        .join("");
    }

    $("playbookList").querySelectorAll("button[data-playbook]").forEach((button) => {
      button.addEventListener("click", () => usePlaybook(button.dataset.playbook));
    });
    setActivePlaybook(0);
  }

  function usePlaybook(key) {
    const playbook = state.playbooks.find((item) => item.key === key);
    clearTimeout(pickerSearchTimer);
    if (!playbook) return;
    $("instruction").value = playbook.brief;
    if (state.kind !== "guide") setKind("guide", { silent: true });
    $("playbookDialog").close();
    hint(`${playbook.title} selected — edit the brief or press Generate.`, "ok");
    $("instruction").focus();
  }

  // ── shell wiring ─────────────────────────────────────────────────────────
  function setKind(kind, { silent = false } = {}) {
    state.kind = kind;
    document.querySelectorAll("#kindTabs button").forEach((button) => {
      const active = button.dataset.kind === kind;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", String(active));
    });
    $("briefNote").textContent = NOTES[kind] || NOTES.auto;
    $("specBtn").hidden = kind !== "spec";
    const isForm = kind === "form";
    $("formPanel").hidden = !isForm;
    $("composer").hidden = isForm;
    $("chips").hidden = isForm;
    $("playbookBar").hidden = !(kind === "auto" || kind === "guide");
    if (isForm) updateFormSummary();
    if (!silent && kind === "spec" && !state.spec) {
      $("instruction").placeholder = "Optional brief to accompany the spec, for example “Create a CV for a senior support engineer”";
    } else {
      $("instruction").placeholder = "Create a step-by-step guide for user login";
    }
  }

  async function loadCategories() {
    try {
      state.playbooks = await api("/playbooks");
    } catch (error) {
      return;
    }
    renderCategoryChips();
  }

  function renderCategoryChips() {
    const counts = new Map();
    state.playbooks.forEach((playbook) => {
      counts.set(playbook.category, (counts.get(playbook.category) || 0) + 1);
    });
    $("chips").innerHTML = [...counts.entries()]
      .map(
        ([category, count]) => `<button type="button" data-category="${esc(category)}"
          title="Browse ${esc(category)} playbooks">${esc(category)}
          <span class="chip-count">${count}</span></button>`
      )
      .join("");
    $("chips").querySelectorAll("button[data-category]").forEach((button) => {
      button.addEventListener("click", () => openPlaybooks(button.dataset.category));
    });
  }

  function wire() {
    $("generateBtn").addEventListener("click", generate);
    $("formGenerate").addEventListener("click", generate);
    document.querySelectorAll("#formModeTabs button").forEach((button) => {
      button.addEventListener("click", () => setFormMode(button.dataset.form));
    });
    $("formExample").addEventListener("click", () => {
      if (state.formMode === "cv") {
        fillCvForm(CV_EXAMPLE);
      } else {
        fillGuideForm(GUIDE_EXAMPLE);
      }
      toast("Example loaded — edit anything before generating");
    });
    $("formJson").addEventListener("click", viewFormJson);
    $("gAddStep").addEventListener("click", () => addStepRow({}, true));
    $("gAddIssue").addEventListener("click", () => addIssueRow());
    $("cvAddRole").addEventListener("click", () => addRoleRow());
    $("cvAddEducation").addEventListener("click", () => addEducationRow());
    $("cvAddProject").addEventListener("click", () => addProjectRow());
    $("formPanel").addEventListener("input", updateFormSummary);
    document
      .querySelectorAll("#detailSelect, #toneSelect, #audienceSelect, #formatPills input")
      .forEach((control) => control.addEventListener("change", saveToolbar));
    $("resetPrefs").addEventListener("click", resetPreferences);
    $("playbookBtn").addEventListener("click", () => openPlaybooks());
    $("playbookSearch").addEventListener("input", () => {
      renderPlaybooks();
      queuePickerResults();
    });
    $("playbookCategory").addEventListener("change", () => {
      rememberCategory($("playbookCategory").value);
      renderPlaybooks();
      announcePickerCategory();
    });
    $("playbookSearch").addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      const cards = [...document.querySelectorAll("#playbookList .playbook-item")];
      const target = cards[state.playbookIndex] || cards[0];
      if (target) usePlaybook(target.dataset.playbook);
    });
    $("playbookDialog").addEventListener("keydown", (event) => {
      if (event.ctrlKey || event.metaKey || event.altKey) return;
      if (event.target instanceof HTMLSelectElement) return;
      const cards = [...document.querySelectorAll("#playbookList .playbook-item")];
      if (!cards.length) return;
      const arrows = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 };
      let target = null;
      if (event.key in arrows) {
        target = (state.playbookIndex < 0 ? 0 : state.playbookIndex) + arrows[event.key];
      } else if (event.key === "Home") {
        target = 0;
      } else if (event.key === "End") {
        target = cards.length - 1;
      }
      if (target === null) return;
      event.preventDefault();
      clearTimeout(pickerSearchTimer);
      setActivePlaybook(target, { announce: true });
      if (document.activeElement?.closest(".playbook-item")) {
        cards[state.playbookIndex]?.focus();
      }
    });
    $("instruction").addEventListener("keydown", (event) => {
      if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
        event.preventDefault();
        generate();
      }
    });
    document.querySelectorAll("#kindTabs button").forEach((button) => {
      button.addEventListener("click", () => setKind(button.dataset.kind));
    });
    document.querySelectorAll("#viewTabs button").forEach((button) => {
      button.addEventListener("click", () => setView(button.dataset.view));
    });
    $("mdBtn").addEventListener("click", () => { window.location.href = fileUrl("md"); });
    $("pdfBtn").addEventListener("click", () => { window.location.href = fileUrl("pdf"); });
    $("docxBtn").addEventListener("click", () => { window.location.href = fileUrl("docx"); });
    $("csvBtn").addEventListener("click", () => {
      if (!state.doc) return;
      window.location.href = `${API}/documents/${encodeURIComponent(state.doc.id)}/export?format=csv&version=${state.version}`;
    });
    $("editBtn").addEventListener("click", openEdit);
    $("editCancel").addEventListener("click", () => {
      $("editWrap").hidden = true;
      $("editBtn").textContent = "✎ Edit";
    });
    $("editSave").addEventListener("click", saveEdit);
    $("annotateBtn").addEventListener("click", openAnnotate);
    $("annotateSave").addEventListener("click", saveAnnotation);
    $("diffBtn").addEventListener("click", openDiff);
    $("diffRun").addEventListener("click", runDiff);
    $("restoreBtn").addEventListener("click", restore);
    $("specBtn").addEventListener("click", openSpec);
    $("specSave").addEventListener("click", useSpec);
    $("specExample").addEventListener("click", () => {
      const example = state.kind === "cv" ? CV_EXAMPLE : GUIDE_EXAMPLE;
      $("specText").value = JSON.stringify(example, null, 2);
    });
    $("specClear").addEventListener("click", () => { $("specText").value = ""; });
    document.querySelectorAll("[data-close]").forEach((button) => {
      button.addEventListener("click", () => button.closest("dialog").close());
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && (event.ctrlKey || event.metaKey) && event.target.id === "editArea") {
        event.preventDefault();
        saveEdit();
      }
    });
    document.addEventListener("keydown", (event) => {
      if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== "k") return;
      event.preventDefault();
      if ($("playbookDialog").open) {
        $("playbookSearch").focus();
        $("playbookSearch").select();
        return;
      }
      if (document.querySelector("dialog[open]")) return;
      openPlaybooks();
    });
  }

  async function boot() {
    wire();
    restoreToolbar();
    await loadCategories();
    seedForm();
    setKind("auto", { silent: true });
    try {
      await refreshDocs();
      if (state.docs.length) await loadDoc(state.docs[0].id);
    } catch (error) {
      $("storeBadge").textContent = "store unavailable";
      hint(`Cannot reach the engine: ${error.message}`, "error");
    }
  }

  boot();
})();
