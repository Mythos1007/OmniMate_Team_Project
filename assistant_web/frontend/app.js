const $ = (id) => document.getElementById(id);

const state = {
  page: "face",
  theme: localStorage.getItem("assistant.web.theme") || "light",
  guiData: null,
  schedules: {},
  alarms: [],
  medications: { last_run_date: "", meds: [] },
  currentMonth: new Date(),
  selectedDate: new Date().toISOString().slice(0, 10),
  currentPose: { x: null, y: null, source: "" },
  lastStatus: "",
  lastState: null,
  mapImage: null,
  poseHistory: [],
  recognition: null,
  cameraStream: null,
  mapMeta: null,
  routeTargetWorld: null,
  recognitionActive: false,
};

const DAY_NAMES = ["일", "월", "화", "수", "목", "금", "토"];
const ALARM_DAY_ORDER = ["월", "화", "수", "목", "금", "토", "일"];
const DEFAULT_MENU_ITEMS = [
  { label: "📅 일정", page: "schedule" },
  { label: "⏰ 알람", page: "alarm" },
  { label: "💊 복약 확인", page: "medication" },
  { label: "✉️ 우편 전달", page: "mail" },
  { label: "⚙️ 설정", page: "settings" },
  { label: "🎤 음성 테스트", page: "voice" },
];

function setTheme(theme) {
  state.theme = theme === "dark" ? "dark" : "light";
  document.body.dataset.theme = state.theme;
  localStorage.setItem("assistant.web.theme", state.theme);
  const select = $("themeSelect");
  if (select) {
    select.value = state.theme;
  }
}

function setLog(text, isError = false) {
  const targets = [$("voiceLog"), $("mailResult")];
  targets.forEach((node) => {
    if (!node) {
      return;
    }
    node.textContent = text;
    node.style.color = isError ? "#b91c1c" : "";
  });
}

async function fetchJson(url, opts = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  if (res.status === 204) {
    return null;
  }
  return res.json();
}

function showPage(pageName) {
  state.page = pageName;
  document.querySelectorAll(".page").forEach((page) => {
    page.classList.toggle("active", page.id === `page-${pageName}`);
  });
  $("topbar").style.display = pageName === "face" ? "none" : "flex";
}

function formatPoseText(snapshot) {
  if (!Number.isFinite(snapshot.pose_x_m) || !Number.isFinite(snapshot.pose_y_m)) {
    return "지도 좌표 수신 대기 중";
  }
  const source = snapshot.pose_source || "n/a";
  return `x=${snapshot.pose_x_m.toFixed(2)}, y=${snapshot.pose_y_m.toFixed(2)} (${source})`;
}

function inferFaceAsset(snapshot) {
  const status = String(snapshot.status_text || "").toLowerCase();
  const assistantState = String(snapshot.assistant_state || "").toLowerCase();

  if (snapshot.charging) {
    return "charging_base.svg";
  }
  if (typeof snapshot.battery_percent === "number" && snapshot.battery_percent <= 20) {
    return "low_battery_base.svg";
  }
  if (status.includes("error") || assistantState.includes("error")) {
    return "error_base.svg";
  }
  if (status.includes("안내") || status.includes("navigate") || assistantState.includes("navigate")) {
    return "navigating_base.svg";
  }
  if (status.includes("생각") || status.includes("thinking")) {
    return "thinking_base.svg";
  }
  if (status.includes("듣") || status.includes("listening")) {
    return "listening_base.svg";
  }
  return "neutral_base.svg";
}

function updateFace(snapshot) {
  const asset = inferFaceAsset(snapshot);
  $("faceImg").src = `/gui-assets/faces/${asset}`;
  $("faceName").textContent = asset.replace(".svg", "");
  $("facePreviewImg").src = `/gui-assets/faces/${asset}`;
}

function updateState(snapshot) {
  state.lastState = snapshot;
  state.lastStatus = snapshot.status_text || "";
  $("voiceState").textContent = snapshot.ros_available ? "호출어 대기 중..." : "ROS 연결 대기 중";
  $("networkText").textContent = snapshot.ros_available ? "네트워크 연결됨" : "네트워크 확인 중";
  $("micText").textContent = state.recognition ? "마이크 준비됨" : "마이크 확인 중";
  $("batteryText").textContent = typeof snapshot.battery_percent === "number"
    ? `${snapshot.charging ? "충전" : "배터리"} ${snapshot.battery_percent}%`
    : "배터리 --";

  $("statusMain").textContent = snapshot.status_text || "대기 중...";
  $("statusSub").textContent = snapshot.assistant_state || "명령을 기다리고 있습니다.";
  $("statusEta").textContent = snapshot.charging ? "현재 충전 중입니다." : "";
  $("poseStatus").textContent = formatPoseText(snapshot);
  $("weatherRos").textContent = snapshot.ros_available ? "connected" : "unavailable";
  $("weatherState").textContent = snapshot.assistant_state || "-";
  $("weatherStatus").textContent = snapshot.status_text || "-";

  if (Number.isFinite(snapshot.pose_x_m) && Number.isFinite(snapshot.pose_y_m)) {
    state.currentPose = {
      x: Number(snapshot.pose_x_m),
      y: Number(snapshot.pose_y_m),
      source: snapshot.pose_source || "",
    };
    state.poseHistory.push({ x: state.currentPose.x, y: state.currentPose.y });
    if (state.poseHistory.length > 80) {
      state.poseHistory.shift();
    }
  }

  updateFace(snapshot);
  drawPoseMap();
}

function getMapDimensions() {
  return {
    displayWidth: Number(state.mapMeta?.display_width) || state.mapImage?.naturalWidth || 1,
    displayHeight: Number(state.mapMeta?.display_height) || state.mapImage?.naturalHeight || 1,
    referenceWidth: Number(state.mapMeta?.reference_width) || Number(state.mapMeta?.display_width) || state.mapImage?.naturalWidth || 1,
    referenceHeight: Number(state.mapMeta?.reference_height) || Number(state.mapMeta?.display_height) || state.mapImage?.naturalHeight || 1,
  };
}

function getMapRenderGeometry() {
  const canvas = $("poseMap");
  const dims = getMapDimensions();
  const scale = Math.max(canvas.width / dims.displayWidth, canvas.height / dims.displayHeight);
  const drawWidth = dims.displayWidth * scale;
  const drawHeight = dims.displayHeight * scale;
  const offsetX = (canvas.width - drawWidth) / 2;
  const offsetY = (canvas.height - drawHeight) / 2;
  return { ...dims, scale, drawWidth, drawHeight, offsetX, offsetY };
}

function rotatePoint(x, y, angleDeg, cx, cy) {
  const rad = (angleDeg * Math.PI) / 180;
  const dx = x - cx;
  const dy = y - cy;
  const cos = Math.cos(rad);
  const sin = Math.sin(rad);
  return {
    x: cx + (dx * cos) - (dy * sin),
    y: cy + (dx * sin) + (dy * cos),
  };
}

function worldToCanvasPoint(worldX, worldY) {
  if (!state.mapMeta) {
    return null;
  }
  const geometry = getMapRenderGeometry();
  const resolution = Number(state.mapMeta.resolution) || 0.05;
  const originX = Number(state.mapMeta.origin_x) || 0;
  const originY = Number(state.mapMeta.origin_y) || 0;
  const rotationDeg = Number(state.mapMeta.rotation_deg) || 0;

  let pxRef = (worldX - originX) / resolution;
  let pyRef = geometry.referenceHeight - ((worldY - originY) / resolution);
  pxRef = Math.max(0, Math.min(geometry.referenceWidth - 1, pxRef));
  pyRef = Math.max(0, Math.min(geometry.referenceHeight - 1, pyRef));

  const px = pxRef * (geometry.displayWidth / geometry.referenceWidth);
  const py = pyRef * (geometry.displayHeight / geometry.referenceHeight);
  const rotated = rotatePoint(px, py, rotationDeg, geometry.displayWidth / 2, geometry.displayHeight / 2);

  return {
    x: geometry.offsetX + rotated.x * geometry.scale,
    y: geometry.offsetY + rotated.y * geometry.scale,
  };
}

function canvasToWorldPoint(canvasX, canvasY) {
  if (!state.mapMeta) {
    return null;
  }
  const geometry = getMapRenderGeometry();
  const resolution = Number(state.mapMeta.resolution) || 0.05;
  const originX = Number(state.mapMeta.origin_x) || 0;
  const originY = Number(state.mapMeta.origin_y) || 0;
  const rotationDeg = Number(state.mapMeta.rotation_deg) || 0;

  let rotPx = (canvasX - geometry.offsetX) / geometry.scale;
  let rotPy = (canvasY - geometry.offsetY) / geometry.scale;
  rotPx = Math.max(0, Math.min(geometry.displayWidth - 1, rotPx));
  rotPy = Math.max(0, Math.min(geometry.displayHeight - 1, rotPy));

  const unrotated = rotatePoint(rotPx, rotPy, -rotationDeg, geometry.displayWidth / 2, geometry.displayHeight / 2);
  const pxRef = unrotated.x * (geometry.referenceWidth / geometry.displayWidth);
  const pyRef = unrotated.y * (geometry.referenceHeight / geometry.displayHeight);

  return {
    x: originX + (pxRef * resolution),
    y: originY + ((geometry.referenceHeight - pyRef) * resolution),
  };
}

function drawPoseMap() {
  const canvas = $("poseMap");
  if (!canvas) {
    return;
  }
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    return;
  }

  const width = canvas.width;
  const height = canvas.height;
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#f8fafc";
  ctx.fillRect(0, 0, width, height);

  if (state.mapImage && state.mapImage.complete) {
    const geometry = getMapRenderGeometry();
    ctx.save();
    ctx.globalAlpha = 0.96;
    ctx.drawImage(state.mapImage, geometry.offsetX, geometry.offsetY, geometry.drawWidth, geometry.drawHeight);
    ctx.restore();
  }

  if (!Number.isFinite(state.currentPose.x) || !Number.isFinite(state.currentPose.y)) {
    ctx.fillStyle = "#334155";
    ctx.font = '16px "Manrope", sans-serif';
    ctx.fillText("pose waiting...", 18, 28);
    return;
  }

  const robotPoint = worldToCanvasPoint(state.currentPose.x, state.currentPose.y);
  const targetPoint = state.routeTargetWorld
    ? worldToCanvasPoint(state.routeTargetWorld.x, state.routeTargetWorld.y)
    : null;

  if (robotPoint && targetPoint) {
    ctx.save();
    ctx.strokeStyle = "#b8c0cc";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(robotPoint.x, robotPoint.y);
    ctx.lineTo(targetPoint.x, targetPoint.y);
    ctx.stroke();

    ctx.strokeStyle = "#ff3b30";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(robotPoint.x, robotPoint.y);
    ctx.lineTo(targetPoint.x, targetPoint.y);
    ctx.stroke();
    ctx.restore();
  }

  if (targetPoint) {
    ctx.save();
    ctx.strokeStyle = "#ff6b35";
    ctx.lineWidth = 2;
    ctx.fillStyle = "#ffe5d9";
    ctx.beginPath();
    ctx.arc(targetPoint.x, targetPoint.y, 10, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(targetPoint.x - 6, targetPoint.y - 6);
    ctx.lineTo(targetPoint.x + 6, targetPoint.y + 6);
    ctx.moveTo(targetPoint.x - 6, targetPoint.y + 6);
    ctx.lineTo(targetPoint.x + 6, targetPoint.y - 6);
    ctx.stroke();
    ctx.restore();
  }

  const robotX = robotPoint ? robotPoint.x : width / 2;
  const robotY = robotPoint ? robotPoint.y : height / 2;
  ctx.fillStyle = "#ef4444";
  ctx.beginPath();
  ctx.arc(robotX, robotY, 9, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = "#ffffff";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(robotX - 7, robotY);
  ctx.lineTo(robotX + 7, robotY);
  ctx.moveTo(robotX, robotY - 7);
  ctx.lineTo(robotX, robotY + 7);
  ctx.stroke();

  ctx.fillStyle = "#0f172a";
  ctx.font = '14px "Manrope", sans-serif';
  ctx.fillText(`x=${state.currentPose.x.toFixed(2)}m y=${state.currentPose.y.toFixed(2)}m`, 16, height - 16);
}

async function loadMapMeta() {
  try {
    const meta = await fetchJson("/api/map");
    state.mapMeta = meta;
    state.mapImage = new Image();
    state.mapImage.onload = () => drawPoseMap();
    state.mapImage.src = `${meta.image_url}?t=${Date.now()}`;
  } catch (error) {
    setLog("map image load failed", true);
  }
}

async function sendCommand(text) {
  const result = await fetchJson("/api/command", {
    method: "POST",
    body: JSON.stringify({ text, source: "web" }),
  });
  setLog(result.detail, !result.accepted);
}

async function sendWake() {
  const result = await fetchJson("/api/manual-wake", { method: "POST" });
  setLog(result.detail, !result.accepted);
}

async function sendNavigateClick(xM, yM) {
  const result = await fetchJson("/api/navigate/click", {
    method: "POST",
    body: JSON.stringify({ x_m: xM, y_m: yM }),
  });
  setLog(result.detail, !result.accepted);
}

function setupMapClick() {
  const canvas = $("poseMap");
  if (!canvas) {
    return;
  }

  canvas.addEventListener("click", async (event) => {
    const rect = canvas.getBoundingClientRect();
    const canvasX = (event.clientX - rect.left) * (canvas.width / rect.width);
    const canvasY = (event.clientY - rect.top) * (canvas.height / rect.height);
    const worldPoint = canvasToWorldPoint(canvasX, canvasY);
    if (!worldPoint) {
      return;
    }
    try {
      state.routeTargetWorld = { x: worldPoint.x, y: worldPoint.y };
      drawPoseMap();
      await sendNavigateClick(worldPoint.x, worldPoint.y);
      $("routeSummary").textContent = `선택 좌표: x=${worldPoint.x.toFixed(2)}, y=${worldPoint.y.toFixed(2)}`;
    } catch (error) {
      setLog(`navigate failed: ${error}`, true);
    }
  });
}

function startVoiceCommandFlow() {
  showPage("voice");
  if (!state.recognition) {
    setLog("브라우저 음성 인식이 준비되지 않았습니다.", true);
    return;
  }
  if (state.recognitionActive) {
    setLog("이미 음성명령을 듣고 있습니다.");
    return;
  }
  try {
    state.recognition.start();
    setLog("음성명령 대기 중...");
  } catch (error) {
    setLog(`mic start failed: ${error}`, true);
  }
}

function menuButton(label, page) {
  const button = document.createElement("button");
  button.className = "menu-btn";
  button.textContent = label;
  button.addEventListener("click", () => showPage(page));
  return button;
}

function renderMenu() {
  const root = $("menuGrid");
  root.innerHTML = "";
  const items = Array.isArray(state.guiData?.menu) && state.guiData.menu.length
    ? state.guiData.menu
    : DEFAULT_MENU_ITEMS;
  items.forEach((item) => {
    root.appendChild(menuButton(item.label, item.page));
  });
}

function renderQuickDestinations() {
  const root = $("quickDestinations");
  root.innerHTML = "";
  (state.guiData?.quick_destinations || []).forEach((name) => {
    const button = document.createElement("button");
    button.className = "dest-btn";
    button.textContent = name;
    button.addEventListener("click", async () => {
      try {
        await sendCommand(`${name}으로 안내해줘`);
      } catch (error) {
        setLog(`destination failed: ${error}`, true);
      }
    });
    root.appendChild(button);
  });

  const stopButton = document.createElement("button");
  stopButton.className = "dest-btn stop-btn";
  stopButton.textContent = "안내 중지";
  stopButton.addEventListener("click", async () => {
    try {
      await sendCommand("멈춰");
    } catch (error) {
      setLog(`stop failed: ${error}`, true);
    }
  });
  root.appendChild(stopButton);
}

function parseAirLabel(description) {
  if (String(description).includes("rain")) {
    return ["😷", "미세먼지<br>나쁨"];
  }
  if (String(description).includes("clear")) {
    return ["😊", "미세먼지<br>좋음"];
  }
  return ["🙂", "미세먼지<br>보통"];
}

function weatherIconFromCode(icon) {
  const map = {
    sun: "☀️",
    cloud: "☁️",
    rain: "🌧️",
    snow: "❄️",
    fog: "🌫️",
    storm: "⛈️",
  };
  return map[icon] || "☁️";
}

async function loadWeather() {
  try {
    const weather = await fetchJson("/api/weather");
    const icon = weatherIconFromCode(weather.icon);
    $("weatherIcon").textContent = icon;
    $("weatherDesc").textContent = weather.description || "확인중";
    $("weatherTemp").textContent = weather.temperature_c == null ? "--°" : `${Math.round(weather.temperature_c)}°`;
    $("weatherDetailIcon").textContent = icon;
    $("weatherDetailDesc").textContent = weather.description || "날씨 정보 대기 중";
    $("weatherDetailTemp").textContent = weather.temperature_c == null ? "--°" : `${Math.round(weather.temperature_c)}°`;
    const [airFace, airText] = parseAirLabel(String(weather.description || ""));
    $("airFace").textContent = airFace;
    $("airText").innerHTML = airText;
  } catch (error) {
    setLog("weather unavailable", true);
  }
}

function toDateString(date) {
  return date.toISOString().slice(0, 10);
}

function renderCalendar() {
  const grid = $("calendarGrid");
  grid.innerHTML = "";

  DAY_NAMES.forEach((day) => {
    const node = document.createElement("div");
    node.className = "calendar-weekday";
    node.textContent = day;
    grid.appendChild(node);
  });

  const monthDate = new Date(state.currentMonth.getFullYear(), state.currentMonth.getMonth(), 1);
  $("calendarTitle").textContent = `${monthDate.getFullYear()}년 ${monthDate.getMonth() + 1}월`;

  const startDay = new Date(monthDate);
  startDay.setDate(1 - monthDate.getDay());

  for (let i = 0; i < 42; i += 1) {
    const cellDate = new Date(startDay);
    cellDate.setDate(startDay.getDate() + i);
    const dateKey = toDateString(cellDate);
    const hasItems = Array.isArray(state.schedules[dateKey]) && state.schedules[dateKey].length > 0;

    const button = document.createElement("button");
    button.type = "button";
    button.className = "calendar-cell";
    if (cellDate.getMonth() !== monthDate.getMonth()) {
      button.classList.add("outside");
    }
    if (dateKey === state.selectedDate) {
      button.classList.add("selected");
    }
    button.innerHTML = `<strong>${cellDate.getDate()}</strong>${hasItems ? '<span class="calendar-marker"></span>' : ''}`;
    button.addEventListener("click", () => {
      state.selectedDate = dateKey;
      renderCalendar();
      renderScheduleList();
    });
    grid.appendChild(button);
  }
}

function renderScheduleList() {
  const root = $("scheduleList");
  root.innerHTML = "";
  $("scheduleDateTitle").textContent = `선택 날짜: ${state.selectedDate}`;

  const items = state.schedules[state.selectedDate] || [];
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "list-item";
    empty.innerHTML = '<div class="item-main"><strong>일정이 없습니다.</strong></div>';
    root.appendChild(empty);
    return;
  }

  items.forEach((item, index) => {
    const row = document.createElement("article");
    row.className = "list-item";
    row.innerHTML = `
      <div class="item-main">
        <strong>${item.time} - ${item.todo}</strong>
        <p>${item.place || "장소 미지정"}</p>
      </div>
      <div class="item-actions">
        <button class="subtle-btn">수정</button>
        <button class="ghost-btn">삭제</button>
      </div>
    `;
    row.querySelector(".subtle-btn").addEventListener("click", () => openScheduleModal("edit", state.selectedDate, index, item));
    row.querySelector(".ghost-btn").addEventListener("click", async () => {
      await fetch(`/api/schedules/${encodeURIComponent(state.selectedDate)}/${index}`, { method: "DELETE" });
      await refreshSchedules();
    });
    root.appendChild(row);
  });
}

function renderAlarmList() {
  const root = $("alarmList");
  root.innerHTML = "";
  if (!state.alarms.length) {
    root.innerHTML = '<article class="alarm-item"><div class="alarm-left"><strong>등록된 알람이 없습니다.</strong></div></article>';
    return;
  }

  state.alarms.forEach((alarm, index) => {
    const row = document.createElement("article");
    row.className = "alarm-item";
    const dayChips = ALARM_DAY_ORDER.map((day) => `<span class="day-chip ${alarm.days?.includes(day) ? "selected" : ""}">${day}</span>`).join("");
    row.innerHTML = `
      <div class="alarm-left">
        <strong class="alarm-time">${alarm.time || "00:00"}</strong>
        <div class="alarm-meta">📍 ${alarm.target || "미지정"} / 🏁 ${alarm.place || "미지정"}</div>
        <div class="chip-row">${dayChips}</div>
        <div class="alarm-meta">${alarm.memo || "메모 없음"}</div>
      </div>
      <div class="item-actions">
        <button class="toggle ${alarm.active ? "active" : ""}"></button>
        <button class="subtle-btn">수정</button>
        <button class="ghost-btn">삭제</button>
      </div>
    `;
    row.querySelector(".toggle").addEventListener("click", async () => {
      await fetchJson(`/api/alarms/${index}/toggle`, {
        method: "POST",
        body: JSON.stringify({ active: !alarm.active }),
      });
      await refreshAlarms();
    });
    row.querySelector(".subtle-btn").addEventListener("click", () => openAlarmModal("edit", index, alarm));
    row.querySelector(".ghost-btn").addEventListener("click", async () => {
      await fetch(`/api/alarms/${index}`, { method: "DELETE" });
      await refreshAlarms();
    });
    root.appendChild(row);
  });
}

function updateMedicationStatus() {
  const banner = $("medStatusBar");
  const meds = state.medications.meds || [];
  const currentTime = new Date().toTimeString().slice(0, 5);
  banner.className = "status-banner pending";
  if (!meds.length) {
    banner.textContent = "등록된 복약 일정이 없습니다.";
    return;
  }
  const currentAlarm = meds.find((item) => !item.active && item.time === currentTime);
  if (currentAlarm) {
    banner.className = "status-banner alarm";
    banner.textContent = `🚨 [알람] ${currentAlarm.name || "사용자"}님, ${currentAlarm.pill || "약"} 복용 시간입니다!`;
    return;
  }
  const allDone = meds.every((item) => item.active);
  if (allDone) {
    banner.className = "status-banner done";
    banner.textContent = "✅ 오늘의 모든 복약 일정을 완료했습니다!";
    return;
  }
  banner.textContent = "⏳ 복약 미완료 (일정이 남아있습니다)";
}

function renderMedicationList() {
  const root = $("medList");
  root.innerHTML = "";
  const meds = state.medications.meds || [];
  if (!meds.length) {
    root.innerHTML = '<article class="med-item"><div class="med-left"><strong>등록된 복약 일정이 없습니다.</strong></div></article>';
    updateMedicationStatus();
    return;
  }

  meds.forEach((med, index) => {
    const row = document.createElement("article");
    row.className = "med-item";
    row.innerHTML = `
      <div class="med-left">
        <strong class="med-time">${med.time || "00:00"}</strong>
        <div class="med-meta">👤 ${med.name || "사용자"} | 💊 ${med.pill || "약"}</div>
      </div>
      <div class="item-actions">
        <button class="subtle-btn">${med.active ? "복용 완료" : "미복용"}</button>
        <button class="ghost-btn">수정</button>
        <button class="ghost-btn med-delete">삭제</button>
      </div>
    `;
    row.querySelector(".subtle-btn").addEventListener("click", async () => {
      await fetchJson(`/api/medications/${index}/toggle`, {
        method: "POST",
        body: JSON.stringify({ active: !med.active }),
      });
      await refreshMedications();
    });
    row.querySelectorAll(".ghost-btn")[0].addEventListener("click", () => openMedicationModal("edit", index, med));
    row.querySelector(".med-delete").addEventListener("click", async () => {
      await fetch(`/api/medications/${index}`, { method: "DELETE" });
      await refreshMedications();
    });
    root.appendChild(row);
  });
  updateMedicationStatus();
}

function openModal(title, contentBuilder) {
  $("modalTitle").textContent = title;
  const form = $("modalForm");
  form.innerHTML = "";
  contentBuilder(form);
  $("modalBackdrop").classList.remove("hidden");
}

function closeModal() {
  $("modalBackdrop").classList.add("hidden");
  $("modalForm").innerHTML = "";
}

function appendField(form, labelText, input) {
  const label = document.createElement("label");
  label.className = "field-label";
  label.textContent = labelText;
  form.appendChild(label);
  form.appendChild(input);
}

function modalActions(form, onSubmit) {
  const actions = document.createElement("div");
  actions.className = "modal-form-actions";
  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "ghost-btn";
  cancel.textContent = "취소";
  cancel.addEventListener("click", closeModal);
  const submit = document.createElement("button");
  submit.type = "submit";
  submit.className = "primary-btn";
  submit.textContent = "저장";
  actions.append(cancel, submit);
  form.appendChild(actions);
  form.addEventListener("submit", onSubmit, { once: true });
}

function openScheduleModal(mode, dateStr = state.selectedDate, index = -1, item = null) {
  openModal(mode === "edit" ? "일정 수정" : "새 일정 등록", (form) => {
    const date = document.createElement("input");
    date.type = "date";
    date.value = dateStr;
    const time = document.createElement("input");
    time.type = "time";
    time.value = item?.time || "09:00";
    const todo = document.createElement("input");
    todo.value = item?.todo || "";
    const place = document.createElement("input");
    place.value = item?.place || "";
    appendField(form, "날짜", date);
    appendField(form, "시간", time);
    appendField(form, "내용", todo);
    appendField(form, "장소", place);
    modalActions(form, async (event) => {
      event.preventDefault();
      const payload = { date: date.value, time: time.value, todo: todo.value.trim(), place: place.value.trim() };
      if (!payload.todo) {
        return;
      }
      if (mode === "edit") {
        await fetchJson(`/api/schedules/${encodeURIComponent(dateStr)}/${index}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
      } else {
        await fetchJson("/api/schedules", {
          method: "POST",
          body: JSON.stringify(payload),
        });
      }
      closeModal();
      state.selectedDate = payload.date;
      await refreshSchedules();
    });
  });
}

function openAlarmModal(mode, index = -1, item = null) {
  openModal(mode === "edit" ? "알람 수정" : "새 알람 추가", (form) => {
    const time = document.createElement("input");
    time.type = "time";
    time.value = item?.time || "09:00";
    const target = document.createElement("input");
    target.value = item?.target || "";
    const place = document.createElement("input");
    place.value = item?.place || "";
    const memo = document.createElement("input");
    memo.value = item?.memo || "";
    const daysWrap = document.createElement("div");
    daysWrap.className = "checkbox-grid";
    const selectedDays = new Set(item?.days || ["월", "화", "수", "목", "금"]);
    const boxes = ALARM_DAY_ORDER.map((day) => {
      const label = document.createElement("label");
      label.className = "checkbox-chip";
      const box = document.createElement("input");
      box.type = "checkbox";
      box.checked = selectedDays.has(day);
      label.append(box, document.createTextNode(day));
      daysWrap.appendChild(label);
      return { day, box };
    });
    appendField(form, "시간", time);
    appendField(form, "대상", target);
    appendField(form, "장소", place);
    appendField(form, "요일 선택", daysWrap);
    appendField(form, "메모", memo);
    modalActions(form, async (event) => {
      event.preventDefault();
      const payload = {
        time: time.value,
        target: target.value.trim() || "미지정",
        place: place.value.trim() || "미지정",
        memo: memo.value.trim(),
        days: boxes.filter((entry) => entry.box.checked).map((entry) => entry.day),
        active: item?.active ?? true,
      };
      if (mode === "edit") {
        await fetchJson(`/api/alarms/${index}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
      } else {
        await fetchJson("/api/alarms", {
          method: "POST",
          body: JSON.stringify(payload),
        });
      }
      closeModal();
      await refreshAlarms();
    });
  });
}

function openMedicationModal(mode, index = -1, item = null) {
  openModal(mode === "edit" ? "복약 일정 수정" : "복약 일정 추가", (form) => {
    const time = document.createElement("input");
    time.type = "time";
    time.value = item?.time || "09:00";
    const name = document.createElement("input");
    name.value = item?.name || "";
    const pill = document.createElement("input");
    pill.value = item?.pill || "";
    appendField(form, "시간", time);
    appendField(form, "이름", name);
    appendField(form, "약", pill);
    modalActions(form, async (event) => {
      event.preventDefault();
      const payload = {
        time: time.value,
        name: name.value.trim() || "사용자",
        pill: pill.value.trim() || "약",
        active: item?.active ?? false,
      };
      if (mode === "edit") {
        await fetchJson(`/api/medications/${index}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
      } else {
        await fetchJson("/api/medications", {
          method: "POST",
          body: JSON.stringify(payload),
        });
      }
      closeModal();
      await refreshMedications();
    });
  });
}

async function refreshSchedules() {
  state.schedules = await fetchJson("/api/schedules");
  renderCalendar();
  renderScheduleList();
}

async function refreshAlarms() {
  state.alarms = await fetchJson("/api/alarms");
  renderAlarmList();
}

async function refreshMedications() {
  state.medications = await fetchJson("/api/medications");
  renderMedicationList();
}

function renderFaceOptions() {
  const select = $("faceSelect");
  select.innerHTML = "";
  (state.guiData?.face_assets || []).forEach((filename) => {
    const option = document.createElement("option");
    option.value = filename;
    option.textContent = filename.replace(".svg", "");
    select.appendChild(option);
  });
}

function setupSocket() {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${protocol}://${window.location.host}/ws/state`);
  ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.type === "state") {
      updateState(message.data);
    }
  };
  ws.onclose = () => {
    setLog("socket disconnected, retrying...", true);
    setTimeout(setupSocket, 1500);
  };
}

function setupMic() {
  const SpeechRecognitionApi = window.SpeechRecognition || window.webkitSpeechRecognition;
  const micBtn = $("micBtn");
  const permBtn = $("permBtn");
  const secure = window.isSecureContext || window.location.hostname === "localhost";
  if (!secure) {
    $("permState").textContent = "보안 연결 필요(HTTPS 권장)";
  }
  if (!SpeechRecognitionApi) {
    micBtn.disabled = true;
    permBtn.disabled = true;
    $("permState").textContent = "브라우저 미지원";
    return;
  }

  state.recognition = new SpeechRecognitionApi();
  state.recognition.lang = "ko-KR";
  state.recognition.interimResults = false;
  state.recognition.maxAlternatives = 1;
  state.recognition.onstart = () => {
    state.recognitionActive = true;
    $("micText").textContent = "마이크 듣는 중";
  };
  state.recognition.onend = () => {
    state.recognitionActive = false;
    $("micText").textContent = "마이크 준비됨";
  };
  state.recognition.onresult = async (event) => {
    const text = event.results?.[0]?.[0]?.transcript?.trim() || "";
    if (!text) {
      return;
    }
    $("commandText").value = text;
    await sendCommand(text);
  };
  state.recognition.onerror = (event) => {
    state.recognitionActive = false;
    setLog(`mic error: ${event.error}`, true);
  };

  permBtn.addEventListener("click", async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((track) => track.stop());
      $("permState").textContent = "허용됨";
      $("micText").textContent = "마이크 준비됨";
    } catch (error) {
      $("permState").textContent = "거부/실패";
      setLog(`permission failed: ${error}`, true);
    }
  });

  micBtn.addEventListener("click", async () => {
    if (state.recognitionActive) {
      setLog("이미 음성명령을 듣고 있습니다.");
      return;
    }
    try {
      state.recognition.start();
      setLog("listening...");
    } catch (error) {
      setLog(`mic start failed: ${error}`, true);
    }
  });
}

async function startMailCamera() {
  if (!navigator.mediaDevices?.getUserMedia) {
    setLog("camera API not supported", true);
    return;
  }
  if (state.cameraStream) {
    state.cameraStream.getTracks().forEach((track) => track.stop());
  }
  try {
    state.cameraStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
    $("mailVideo").srcObject = state.cameraStream;
    $("mailResult").textContent = "카메라가 준비되었습니다. OCR 연동은 다음 단계에서 연결합니다.";
  } catch (error) {
    setLog(`camera failed: ${error}`, true);
  }
}

function setupButtons() {
  $("hdrHomeBtn").addEventListener("click", () => showPage("home"));
  $("hdrSleepBtn").addEventListener("click", () => showPage("face"));
  $("hdrVoiceCmdBtn").addEventListener("click", startVoiceCommandFlow);
  $("faceWakeBtn").addEventListener("click", () => showPage("home"));
  $("weatherCard").addEventListener("click", () => showPage("weather"));
  $("calendarPrevBtn").addEventListener("click", () => {
    state.currentMonth = new Date(state.currentMonth.getFullYear(), state.currentMonth.getMonth() - 1, 1);
    renderCalendar();
  });
  $("calendarNextBtn").addEventListener("click", () => {
    state.currentMonth = new Date(state.currentMonth.getFullYear(), state.currentMonth.getMonth() + 1, 1);
    renderCalendar();
  });
  $("scheduleAddBtn").addEventListener("click", () => openScheduleModal("create"));
  $("alarmAddBtn").addEventListener("click", () => openAlarmModal("create"));
  $("medAddBtn").addEventListener("click", () => openMedicationModal("create"));
  $("modalCloseBtn").addEventListener("click", closeModal);
  $("modalBackdrop").addEventListener("click", (event) => {
    if (event.target === $("modalBackdrop")) {
      closeModal();
    }
  });
  $("themeSelect").addEventListener("change", (event) => setTheme(event.target.value));
  $("faceSelect").addEventListener("change", (event) => {
    $("facePreviewImg").src = `/gui-assets/faces/${event.target.value}`;
  });
  $("mailStartBtn").addEventListener("click", startMailCamera);
  $("mailCancelBtn").addEventListener("click", () => {
    if (state.cameraStream) {
      state.cameraStream.getTracks().forEach((track) => track.stop());
      state.cameraStream = null;
    }
    $("mailVideo").srcObject = null;
    $("mailResult").textContent = "수취인을 스캔해 주세요.";
  });
  $("mailConfirmBtn").addEventListener("click", () => setLog("확인 동작은 OCR 연동 단계에서 연결됩니다."));

  document.querySelectorAll("[data-go]").forEach((button) => {
    button.addEventListener("click", () => showPage(button.dataset.go));
  });

  $("sendBtn").addEventListener("click", async () => {
    const text = $("commandText").value.trim();
    if (!text) {
      setLog("명령 텍스트를 입력해 주세요.", true);
      return;
    }
    await sendCommand(text);
  });
  $("commandText").addEventListener("keydown", async (event) => {
    if (event.key !== "Enter") {
      return;
    }
    event.preventDefault();
    const text = $("commandText").value.trim();
    if (!text) {
      return;
    }
    await sendCommand(text);
  });
  $("wakeBtn").addEventListener("click", sendWake);
  $("stopBtn").addEventListener("click", async () => sendCommand("멈춰"));
  $("homeBtn").addEventListener("click", async () => sendCommand("집으로 가"));
  $("followBtn").addEventListener("click", async () => sendCommand("나를 따라와"));
  $("speakBtn").addEventListener("click", () => {
    if (!state.lastStatus || !("speechSynthesis" in window)) {
      return;
    }
    const utterance = new SpeechSynthesisUtterance(state.lastStatus);
    utterance.lang = "ko-KR";
    window.speechSynthesis.speak(utterance);
  });
}

async function bootstrap() {
  setTheme(state.theme);
  showPage("face");
  renderMenu();
  setupButtons();
  setupMic();
  setupMapClick();
  setupSocket();

  try {
    state.guiData = await fetchJson("/api/gui-data");
    renderMenu();
    renderQuickDestinations();
    state.schedules = state.guiData.schedules || {};
    state.alarms = state.guiData.alarms || [];
    state.medications = state.guiData.medications || { last_run_date: "", meds: [] };
    renderFaceOptions();
    renderCalendar();
    renderScheduleList();
    renderAlarmList();
    renderMedicationList();
  } catch (error) {
    setLog("gui data load failed", true);
  }

  try {
    const snapshot = await fetchJson("/api/state");
    updateState(snapshot);
  } catch (error) {
    setLog("backend not reachable", true);
  }

  await loadMapMeta();
  await loadWeather();
}

bootstrap();
