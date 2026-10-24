"use strict";

const defaultApiUrl = `${window.location.origin}/api`;
let apiUrl = sessionStorage.getItem("attendanceApiUrl") || defaultApiUrl;
let accessToken = sessionStorage.getItem("attendanceAdminToken") || "";
let employees = [];
let cameraStream = null;

const byId = (id) => document.getElementById(id);

function showToast(message, isError = false) {
  const toast = byId("toast");
  toast.textContent = message;
  toast.classList.toggle("error", isError);
  toast.classList.add("visible");
  window.clearTimeout(showToast.timeout);
  showToast.timeout = window.setTimeout(() => toast.classList.remove("visible"), 3500);
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("Authorization", `Bearer ${accessToken}`);
  if (options.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const response = await fetch(`${apiUrl}${path}`, { ...options, headers });
  if (!response.ok) {
    if (response.status === 401) {
      accessToken = "";
      sessionStorage.removeItem("attendanceAdminToken");
      setConnection(false, "Admin sign-in required");
      if (!byId("settingsDialog").open) byId("settingsDialog").showModal();
    }
    let detail = `Request failed (${response.status})`;
    try {
      const result = await response.json();
      detail = result.detail || detail;
    } catch {
      // Keep the HTTP status message when the response is not JSON.
    }
    throw new Error(detail);
  }
  return response.status === 204 ? null : response.json();
}

function setConnection(connected, message = connected ? "Connected" : "Not connected") {
  byId("connectionText").textContent = message;
  byId("connectionText").parentElement.classList.toggle("offline", !connected);
}

function createCell(row, text, className = "") {
  const cell = document.createElement("td");
  if (className) cell.className = className;
  cell.textContent = text;
  row.appendChild(cell);
  return cell;
}

function formatDate(value) {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "—" : parsed.toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}

function renderReports(records) {
  const tbody = byId("reportTableBody");
  tbody.replaceChildren();
  byId("recordCount").textContent = `${records.length} ${records.length === 1 ? "record" : "records"}`;
  if (!records.length) {
    const row = tbody.insertRow();
    const cell = row.insertCell();
    cell.colSpan = 7;
    cell.className = "table-empty";
    cell.textContent = "No records match these filters.";
    return;
  }

  records.forEach((record) => {
    const row = tbody.insertRow();
    const employeeCell = row.insertCell();
    employeeCell.className = "employee-cell";
    const name = document.createElement("strong");
    name.textContent = record.full_name;
    const code = document.createElement("small");
    code.textContent = record.employee_code;
    employeeCell.append(name, code);
    createCell(row, record.department);
    createCell(row, formatDate(record.check_in));
    createCell(row, formatDate(record.check_out));
    const statusCell = createCell(row, "");
    const badge = document.createElement("span");
    badge.className = `badge ${record.status === "LATE" ? "badge-late" : "badge-present"}`;
    badge.textContent = record.status;
    statusCell.appendChild(badge);
    const anomalyCell = createCell(row, "");
    if (record.anomaly_flag) {
      const anomaly = document.createElement("span");
      anomaly.className = "badge badge-anomaly";
      anomaly.textContent = record.anomaly_reason.replaceAll("_", " ");
      anomaly.title = record.anomaly_notes || "";
      anomalyCell.appendChild(anomaly);
    } else {
      anomalyCell.textContent = "—";
      anomalyCell.className = "muted-cell";
    }
    const actionCell = row.insertCell();
    actionCell.className = "admin-row-actions";
    const editButton = document.createElement("button");
    editButton.type = "button";
    editButton.className = "row-action";
    editButton.textContent = "Edit";
    editButton.addEventListener("click", () => openAttendanceEditor(record));
    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "row-action row-action-danger";
    deleteButton.textContent = "Delete";
    deleteButton.addEventListener("click", () => deleteAttendance(record));
    actionCell.append(editButton, deleteButton);
  });
}

function toLocalDateTime(value) {
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
}

function openAttendanceEditor(record) {
  byId("editRecordId").value = record.id;
  byId("editCheckIn").value = toLocalDateTime(record.check_in);
  byId("editCheckOut").value = record.check_out ? toLocalDateTime(record.check_out) : "";
  byId("editStatus").value = record.status;
  byId("editAnomalyFlag").checked = record.anomaly_flag;
  byId("editAnomalyReason").value = record.anomaly_reason;
  byId("editAnomalyNotes").value = record.anomaly_notes || "";
  byId("attendanceEditMessage").textContent = "";
  byId("attendanceEditDialog").showModal();
}

async function deleteAttendance(record) {
  if (!window.confirm(`Permanently delete the attendance record for ${record.full_name} on ${formatDate(record.check_in)}?`)) return;
  try {
    await api(`/attendance/${record.id}`, { method: "DELETE" });
    showToast("Attendance record deleted.");
    await refreshDashboard();
  } catch (error) {
    showToast(error.message, true);
  }
}

function renderActivity(records) {
  const list = byId("activityList");
  list.replaceChildren();
  const recent = records.slice(0, 6);
  if (!recent.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "No attendance activity recorded yet.";
    list.appendChild(empty);
    return;
  }
  recent.forEach((record) => {
    const item = document.createElement("div");
    item.className = "activity-item";
    const avatar = document.createElement("span");
    avatar.className = `activity-avatar${record.anomaly_flag ? " avatar-alert" : ""}`;
    avatar.textContent = record.full_name.split(/\s+/).map((part) => part[0]).join("").slice(0, 2).toUpperCase();
    const details = document.createElement("div");
    details.className = "activity-details";
    const name = document.createElement("strong");
    name.textContent = record.full_name;
    const description = document.createElement("span");
    description.textContent = record.anomaly_flag ? record.anomaly_reason.replaceAll("_", " ") : `${record.status.toLowerCase()} · ${record.department}`;
    details.append(name, description);
    const time = document.createElement("time");
    time.textContent = new Date(record.check_in).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    item.append(avatar, details, time);
    list.appendChild(item);
  });
}

function reportQuery() {
  const params = new URLSearchParams();
  if (byId("startDate").value) params.set("start_date", byId("startDate").value);
  if (byId("endDate").value) params.set("end_date", byId("endDate").value);
  if (byId("anomaliesOnly").checked) params.set("anomalies_only", "true");
  const query = params.toString();
  return query ? `?${query}` : "";
}

async function refreshDashboard() {
  if (!accessToken) {
    setConnection(false, "Admin sign-in required");
    return;
  }
  try {
    const [summary, records, employeeList] = await Promise.all([
      api("/reports/summary"),
      api(`/reports${reportQuery()}`),
      api("/employees"),
    ]);
    byId("statEmployees").textContent = summary.employees;
    byId("statPresent").textContent = summary.present_today;
    byId("statLate").textContent = summary.late_today;
    byId("statAnomalies").textContent = summary.anomalies_today;
    renderReports(records);
    renderActivity(records);
    employees = employeeList;
    renderEmployees();
    setConnection(true);
  } catch (error) {
    setConnection(false, "Connection issue");
    showToast(error.message, true);
  }
}

function renderEmployees() {
  const select = byId("attendanceEmployee");
  const previous = select.value;
  select.replaceChildren(new Option("Select an employee", ""));
  employees.filter((employee) => employee.is_active).forEach((employee) => {
    const option = new Option(`${employee.full_name} · ${employee.employee_code}`, employee.employee_code);
    option.dataset.biometric = String(employee.biometric_consent);
    select.add(option);
  });
  if ([...select.options].some((option) => option.value === previous)) select.value = previous;
  updateEnrollmentButton();
}

function updateEnrollmentButton() {
  const employee = employees.find((item) => item.employee_code === byId("attendanceEmployee").value);
  byId("enrollFaceButton").hidden = !(employee?.biometric_consent && !employee.has_biometric);
  byId("manualOverrideControl").hidden = !(employee?.biometric_consent && employee.has_biometric);
  byId("manualOverride").checked = false;
}

async function captureImage() {
  if (!cameraStream || !byId("webcam").videoWidth) throw new Error("Enable the camera and wait for the preview before scanning.");
  const video = byId("webcam");
  const canvas = byId("canvas");
  const scale = Math.min(1, 1280 / video.videoWidth);
  canvas.width = Math.round(video.videoWidth * scale);
  canvas.height = Math.round(video.videoHeight * scale);
  canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/jpeg", 0.82);
}

async function enableCamera() {
  if (!navigator.mediaDevices?.getUserMedia) throw new Error("Camera access requires localhost or HTTPS and a supported browser.");
  cameraStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" }, audio: false });
  byId("webcam").srcObject = cameraStream;
  byId("cameraBox").classList.add("camera-on");
  byId("cameraButton").textContent = "Turn camera off";
}

function stopCamera() {
  cameraStream?.getTracks().forEach((track) => track.stop());
  cameraStream = null;
  byId("webcam").srcObject = null;
  byId("cameraBox").classList.remove("camera-on");
  byId("cameraButton").textContent = "Enable camera";
}

async function markAttendance() {
  const code = byId("attendanceEmployee").value;
  if (!code) {
    showToast("Choose an employee first.", true);
    return;
  }
  const employee = employees.find((item) => item.employee_code === code);
  const payload = { employee_code: code };
  if (employee?.biometric_consent && employee.has_biometric && !byId("manualOverride").checked) {
    payload.image_base64 = await captureImage();
  } else if (employee?.biometric_consent && employee.has_biometric) {
    payload.manual_override = true;
  }
  const result = await api("/attendance/mark", { method: "POST", body: JSON.stringify(payload) });
  byId("attendanceMessage").textContent = `${result.employee} checked in · ${result.punctuality.toLowerCase()}${result.anomaly_flag ? ` · Flagged: ${result.anomaly_reason.replaceAll("_", " ")}` : ""}`;
  byId("attendanceMessage").className = `form-message${result.anomaly_flag ? " message-warning" : " message-success"}`;
  await refreshDashboard();
}

async function markCheckout() {
  const code = byId("attendanceEmployee").value;
  if (!code) {
    showToast("Choose an employee first.", true);
    return;
  }
  const result = await api("/attendance/checkout", { method: "POST", body: JSON.stringify({ employee_code: code }) });
  byId("attendanceMessage").textContent = `Check-out recorded at ${new Date(result.time).toLocaleTimeString()}.`;
  byId("attendanceMessage").className = "form-message message-success";
  await refreshDashboard();
}

async function addEmployee(event) {
  event.preventDefault();
  const message = byId("employeeMessage");
  message.textContent = "";
  const consent = byId("biometricConsent").checked;
  try {
    await api("/employees", {
      method: "POST",
      body: JSON.stringify({
        employee_code: byId("employeeCode").value.trim(),
        full_name: byId("employeeName").value.trim(),
        email: byId("employeeEmail").value.trim(),
        department: byId("employeeDepartment").value.trim(),
        biometric_consent: consent,
      }),
    });
    byId("employeeForm").reset();
    byId("employeeDialog").close();
    showToast(consent
      ? "Employee added with consent. Select them and use Enroll face when the camera is ready."
      : "Employee added without biometric data.");
    await refreshDashboard();
  } catch (error) {
    message.textContent = error.message;
    message.className = "dialog-message message-error";
  }
}

async function exportCsv() {
  try {
    const response = await fetch(`${apiUrl}/reports/export.csv${reportQuery()}`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    if (!response.ok) throw new Error(`Export failed (${response.status})`);
    const blob = await response.blob();
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `attendance-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(link.href);
  } catch (error) {
    showToast(error.message, true);
  }
}

byId("todayLabel").textContent = new Intl.DateTimeFormat([], { weekday: "long", month: "long", day: "numeric" }).format(new Date());
byId("settingsButton").addEventListener("click", () => {
  byId("apiUrlInput").value = apiUrl;
  byId("settingsDialog").showModal();
});
byId("addEmployeeButton").addEventListener("click", () => byId("employeeDialog").showModal());
byId("employeeForm").addEventListener("submit", addEmployee);
byId("checkinButton").addEventListener("click", () => markAttendance().catch((error) => showToast(error.message, true)));
byId("checkoutButton").addEventListener("click", () => markCheckout().catch((error) => showToast(error.message, true)));
byId("cameraButton").addEventListener("click", () => {
  if (cameraStream) stopCamera();
  else enableCamera().catch((error) => showToast(error.message, true));
});
byId("attendanceEmployee").addEventListener("change", updateEnrollmentButton);
byId("enrollFaceButton").addEventListener("click", async () => {
  try {
    const image_base64 = await captureImage();
    await api("/employees/biometrics/enroll", {
      method: "POST",
      body: JSON.stringify({ employee_code: byId("attendanceEmployee").value, image_base64 }),
    });
    showToast("Encrypted face template enrolled. The image was not retained.");
    await refreshDashboard();
  } catch (error) {
    showToast(error.message, true);
  }
});
byId("refreshButton").addEventListener("click", refreshDashboard);
byId("startDate").addEventListener("change", refreshDashboard);
byId("endDate").addEventListener("change", refreshDashboard);
byId("anomaliesOnly").addEventListener("change", refreshDashboard);
byId("exportButton").addEventListener("click", exportCsv);
byId("attendanceEditForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = byId("attendanceEditMessage");
  message.textContent = "";
  const checkIn = byId("editCheckIn").value;
  const checkOut = byId("editCheckOut").value;
  if (checkOut && new Date(checkOut) < new Date(checkIn)) {
    message.textContent = "Check-out must not be earlier than check-in.";
    message.className = "dialog-message message-error";
    return;
  }
  const anomalyFlag = byId("editAnomalyFlag").checked;
  try {
    await api(`/attendance/${byId("editRecordId").value}`, {
      method: "PATCH",
      body: JSON.stringify({
        check_in: checkIn,
        check_out: checkOut || null,
        status: byId("editStatus").value,
        anomaly_flag: anomalyFlag,
        anomaly_reason: anomalyFlag ? byId("editAnomalyReason").value : "NONE",
        anomaly_notes: byId("editAnomalyNotes").value.trim() || null,
      }),
    });
    byId("attendanceEditDialog").close();
    showToast("Attendance record updated.");
    await refreshDashboard();
  } catch (error) {
    message.textContent = error.message;
    message.className = "dialog-message message-error";
  }
});
byId("settingsForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const username = byId("adminUsername").value.trim();
  const password = byId("adminPassword").value;
  const nextUrl = byId("apiUrlInput").value.trim().replace(/\/+$/, "");
  if (!username || !password || !nextUrl) return;
  apiUrl = nextUrl;
  sessionStorage.setItem("attendanceApiUrl", apiUrl);
  try {
    const response = await fetch(`${apiUrl}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Admin sign-in failed");
    accessToken = data.access_token;
    sessionStorage.setItem("attendanceAdminToken", accessToken);
    byId("adminPassword").value = "";
    byId("settingsDialog").close();
    await refreshDashboard();
    showToast("Signed in to the admin panel.");
  } catch (error) {
    byId("settingsMessage").textContent = error.message;
    byId("settingsMessage").className = "dialog-message message-error";
  }
});
byId("disconnectButton").addEventListener("click", () => {
  accessToken = "";
  sessionStorage.removeItem("attendanceAdminToken");
  byId("settingsDialog").close();
  setConnection(false, "Admin sign-in required");
});
document.querySelectorAll("[data-close]").forEach((button) => button.addEventListener("click", () => byId(button.dataset.close).close()));

byId("apiUrlInput").value = apiUrl;
if (!accessToken) byId("settingsDialog").showModal();
else refreshDashboard();
