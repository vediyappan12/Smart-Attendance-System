"use strict";

const API = `${window.location.origin}/api/public`;
let cameraStream = null;
let faceReady = false;
const byId = (id) => document.getElementById(id);

async function request(path, payload) {
  const response = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error(`Request failed (${response.status})`);
  }
  if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
  return data;
}

function setMessage(element, message, isError = false) {
  element.textContent = message;
  element.classList.toggle("error", isError);
}

async function startCamera() {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error("Camera needs a modern browser and localhost or HTTPS.");
  }
  cameraStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" }, audio: false });
  byId("camera").srcObject = cameraStream;
  byId("cameraFrame").classList.add("camera-on");
  byId("cameraButton").textContent = "Turn camera off";
  byId("registrationCameraButton").textContent = "Turn camera off";
}

function stopCamera() {
  cameraStream?.getTracks().forEach((track) => track.stop());
  cameraStream = null;
  byId("camera").srcObject = null;
  byId("cameraFrame").classList.remove("camera-on");
  byId("cameraButton").textContent = "Enable camera";
  byId("registrationCameraButton").textContent = "Enable camera";
}

async function captureFace() {
  const video = byId("camera");
  if (!cameraStream || !video.videoWidth) {
    throw new Error("Enable the camera and wait for the preview before continuing.");
  }
  const canvas = byId("captureCanvas");
  const scale = Math.min(1, 1280 / video.videoWidth);
  canvas.width = Math.round(video.videoWidth * scale);
  canvas.height = Math.round(video.videoHeight * scale);
  canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/jpeg", 0.82);
}

function toggleCamera() {
  if (cameraStream) stopCamera();
  else startCamera().catch((error) => setMessage(byId("attendanceMessage"), error.message, true));
}

byId("cameraButton").addEventListener("click", toggleCamera);
byId("registrationCameraButton").addEventListener("click", toggleCamera);

fetch(`${window.location.origin}/api/health`)
  .then((response) => {
    if (!response.ok) throw new Error(`Health request failed (${response.status})`);
    return response.json();
  })
  .then((health) => {
    faceReady = health.face_recognition_ready === true;
    if (!faceReady) {
      byId("faceReadiness").hidden = false;
      byId("faceReadiness").textContent = "Face matching is not installed on this server. Install the optional face-recognition package and Windows C++ build tools, then restart the server to enable enrollment and attendance.";
      byId("registerButton").disabled = true;
      byId("checkInButton").disabled = true;
      byId("checkOutButton").disabled = true;
    }
  })
  .catch((error) => setMessage(byId("attendanceMessage"), error.message, true));

byId("registrationForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = byId("registrationMessage");
  setMessage(message, "Processing face template and creating your account…");
  byId("registerButton").disabled = true;
  try {
    if (!faceReady) throw new Error("Face matching is not enabled. Contact the administrator.");
    if (!byId("consent").checked) throw new Error("Explicit face-processing consent is required.");
    const image_base64 = await captureFace();
    const result = await request("/register", {
      full_name: byId("fullName").value.trim(),
      email: byId("email").value.trim(),
      department: byId("department").value.trim(),
      biometric_consent: true,
      image_base64,
    });
    byId("employeeCode").value = result.employee_code;
    byId("registrationForm").reset();
    setMessage(message, `Registration complete. Your employee code is ${result.employee_code}. Save it privately; you need it for attendance.`);
  } catch (error) {
    setMessage(message, error.message, true);
  } finally {
    byId("registerButton").disabled = !faceReady;
  }
});

async function recordAttendance(action) {
  const message = byId("attendanceMessage");
  try {
    if (!faceReady) throw new Error("Face matching is not enabled. Contact the administrator.");
    const employee_code = byId("employeeCode").value.trim();
    if (!employee_code) throw new Error("Enter your employee code.");
    setMessage(message, "Verifying your face…");
    const image_base64 = await captureFace();
    const result = await request(`/attendance/${action}`, { employee_code, image_base64 });
    const outcome = action === "check-in"
      ? `Attendance ${result.employee} added successfully · ${result.status.toLowerCase()}.`
      : `Check-out for ${result.employee} added successfully.`;
    const anomaly = result.anomaly_flag ? ` · Flagged: ${result.anomaly_reason.replaceAll("_", " ").toLowerCase()}` : "";
    setMessage(message, `${outcome}${anomaly}`);
  } catch (error) {
    setMessage(message, error.message, true);
  }
}

byId("checkInButton").addEventListener("click", () => recordAttendance("check-in"));
byId("checkOutButton").addEventListener("click", () => recordAttendance("check-out"));

window.addEventListener("pagehide", stopCamera);
