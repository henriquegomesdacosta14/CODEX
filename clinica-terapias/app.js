const storageKey = "clinica-florescer-v1";

const today = new Date();
const isoToday = today.toISOString().slice(0, 10);
const currentMonth = isoToday.slice(0, 7);

const seedData = {
  patients: [
    { id: crypto.randomUUID(), name: "Miguel A.", guardian: "Ana Paula", phone: "(11) 98888-2211", diagnosis: "TEA nível 1", plan: "TO 2x/semana, Fono 1x/semana, Psicologia 1x/semana" },
    { id: crypto.randomUUID(), name: "Laura M.", guardian: "Carlos Mendes", phone: "(11) 97777-1199", diagnosis: "TDAH", plan: "Psicopedagogia e terapia comportamental semanal" },
    { id: crypto.randomUUID(), name: "Theo R.", guardian: "Mariana Rocha", phone: "(11) 96666-4433", diagnosis: "Atraso de fala", plan: "Fonoaudiologia 2x/semana" }
  ],
  professionals: [
    { id: crypto.randomUUID(), name: "Dra. Camila Nunes", specialty: "Psicologia infantil", commission: 55, phone: "(11) 95555-0101", availability: "Segunda, quarta e sexta - 08h às 17h" },
    { id: crypto.randomUUID(), name: "Marina Torres", specialty: "Fonoaudiologia", commission: 50, phone: "(11) 94444-0202", availability: "Terça a sexta - 09h às 18h" },
    { id: crypto.randomUUID(), name: "Rafaela Lima", specialty: "Terapia ocupacional", commission: 52, phone: "(11) 93333-0303", availability: "Segunda a quinta - 08h às 16h" }
  ],
  appointments: [],
  sessions: [],
  transactions: []
};

seedData.appointments = [
  { id: crypto.randomUUID(), patientId: seedData.patients[0].id, professionalId: seedData.professionals[2].id, therapy: "Terapia ocupacional", date: isoToday, time: "09:00", status: "Confirmado", notes: "Sala sensorial" },
  { id: crypto.randomUUID(), patientId: seedData.patients[1].id, professionalId: seedData.professionals[0].id, therapy: "Psicologia infantil", date: isoToday, time: "10:30", status: "Agendado", notes: "Orientar responsável após sessão" },
  { id: crypto.randomUUID(), patientId: seedData.patients[2].id, professionalId: seedData.professionals[1].id, therapy: "Fonoaudiologia", date: addDays(isoToday, 1), time: "14:00", status: "Confirmado", notes: "Levar material de linguagem" },
  { id: crypto.randomUUID(), patientId: seedData.patients[0].id, professionalId: seedData.professionals[0].id, therapy: "Psicologia infantil", date: addDays(isoToday, 2), time: "08:30", status: "Agendado", notes: "" }
];

seedData.sessions = [
  { id: crypto.randomUUID(), patientId: seedData.patients[0].id, professionalId: seedData.professionals[2].id, therapy: "Terapia ocupacional", date: `${currentMonth}-01`, amount: 170, status: "Realizada", paymentStatus: "Pago", notes: "Sessão concluída" },
  { id: crypto.randomUUID(), patientId: seedData.patients[2].id, professionalId: seedData.professionals[1].id, therapy: "Fonoaudiologia", date: `${currentMonth}-02`, amount: 155, status: "Realizada", paymentStatus: "Pendente", notes: "Controle de sessões" },
  { id: crypto.randomUUID(), patientId: seedData.patients[1].id, professionalId: seedData.professionals[0].id, therapy: "Psicologia infantil", date: `${currentMonth}-02`, amount: 180, status: "Realizada", paymentStatus: "Pago", notes: "Sessão concluída" }
];

seedData.transactions = [
  { id: crypto.randomUUID(), type: "entrada", category: "Mensalidade", description: "Mensalidade Miguel A.", amount: 680, date: `${currentMonth}-01`, status: "Pago" },
  { id: crypto.randomUUID(), type: "entrada", category: "Sessão avulsa", description: "Sessão Laura M.", amount: 180, date: `${currentMonth}-02`, status: "Pago" },
  { id: crypto.randomUUID(), type: "saida", category: "Aluguel", description: "Aluguel da clínica", amount: 2200, date: `${currentMonth}-03`, status: "Pago" },
  { id: crypto.randomUUID(), type: "saida", category: "Materiais terapêuticos", description: "Materiais sensoriais", amount: 390, date: `${currentMonth}-04`, status: "Pago" }
];

let state = loadState();
let expandedProfessionalId = null;
let selectedAppointmentId = null;

const views = {
  dashboard: "Visão geral",
  agenda: "Agenda",
  sessions: "Sessões",
  finance: "Fluxo de caixa",
  patients: "Pacientes",
  team: "Profissionais",
  reports: "Relatórios"
};

const formatter = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const dateFormatter = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" });
const monthFormatter = new Intl.DateTimeFormat("pt-BR", { month: "long", year: "numeric" });

document.addEventListener("DOMContentLoaded", () => {
  bindNavigation();
  bindModals();
  bindForms();
  bindFilters();
  fillSelects();
  setDefaultDates();
  render();
});

function loadState() {
  const saved = localStorage.getItem(storageKey);
  if (!saved) return structuredClone(seedData);
  try {
    return JSON.parse(saved);
  } catch {
    return structuredClone(seedData);
  }
}

function saveState() {
  localStorage.setItem(storageKey, JSON.stringify(state));
}

function render() {
  saveState();
  fillSelects();
  renderDashboard();
  renderAgenda();
  renderSessions();
  renderFinance();
  renderPatients();
  renderTeam();
  renderReports();
}

function bindNavigation() {
  document.querySelectorAll("[data-view]").forEach((button) => {
    button.addEventListener("click", () => switchView(button.dataset.view));
  });
  document.querySelectorAll("[data-view-jump]").forEach((button) => {
    button.addEventListener("click", () => switchView(button.dataset.viewJump));
  });
  document.getElementById("quickSessionBtn").addEventListener("click", () => openModal("sessionModal"));
}

function switchView(view) {
  document.querySelectorAll(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.view === view));
  document.querySelectorAll(".view").forEach((section) => section.classList.toggle("active", section.id === view));
  document.getElementById("viewTitle").textContent = views[view];
}

function bindModals() {
  document.querySelectorAll("[data-open-modal]").forEach((button) => {
    button.addEventListener("click", () => openModal(button.dataset.openModal));
  });
  document.querySelectorAll("[data-close-modal]").forEach((button) => {
    button.addEventListener("click", () => button.closest("dialog").close());
  });
}

function openModal(id) {
  const dialog = document.getElementById(id);
  if (dialog) dialog.showModal();
}

function openAppointmentModalWithSlot(professionalId, date, time) {
  const form = document.getElementById("appointmentForm");
  form.reset();
  form.elements.professionalId.value = professionalId;
  form.elements.date.value = date;
  form.elements.time.value = time;
  form.elements.status.value = "Confirmado";
  openModal("appointmentModal");
}

function bindForms() {
  document.getElementById("appointmentForm").addEventListener("submit", (event) => {
    event.preventDefault();
    state.appointments.push({ id: crypto.randomUUID(), ...formData(event.target) });
    event.target.reset();
    event.target.closest("dialog").close();
    render();
  });

  document.getElementById("sessionForm").addEventListener("submit", (event) => {
    event.preventDefault();
    const data = formData(event.target);
    const amount = Number(data.amount);
    state.sessions.push({ id: crypto.randomUUID(), ...data, amount });
    if (data.paymentStatus === "Pago" || data.paymentStatus === "Convênio") {
      state.transactions.push({
        id: crypto.randomUUID(),
        type: "entrada",
        category: data.paymentStatus === "Convênio" ? "Convênio" : "Sessão avulsa",
        description: `${getPatient(data.patientId).name} - ${data.therapy}`,
        amount,
        date: data.date,
        status: data.paymentStatus === "Convênio" ? "Pendente" : "Pago"
      });
    }
    event.target.reset();
    event.target.closest("dialog").close();
    render();
  });

  document.getElementById("patientForm").addEventListener("submit", (event) => {
    event.preventDefault();
    state.patients.push({ id: crypto.randomUUID(), ...formData(event.target) });
    event.target.reset();
    event.target.closest("dialog").close();
    render();
  });

  document.getElementById("professionalForm").addEventListener("submit", (event) => {
    event.preventDefault();
    const data = formData(event.target);
    state.professionals.push({ id: crypto.randomUUID(), ...data, commission: Number(data.commission) });
    event.target.reset();
    event.target.closest("dialog").close();
    render();
  });

  document.getElementById("transactionForm").addEventListener("submit", (event) => {
    event.preventDefault();
    const data = formData(event.target);
    state.transactions.push({ id: crypto.randomUUID(), ...data, amount: Number(data.amount) });
    event.target.reset();
    setDefaultDates();
    render();
  });

  document.getElementById("backupBtn").addEventListener("click", exportBackup);
  document.getElementById("restoreInput").addEventListener("change", importBackup);
  document.getElementById("exportFinanceBtn").addEventListener("click", exportFinanceCsv);
  document.getElementById("generatePayoutsBtn").addEventListener("click", generatePayoutTransactions);
  document.getElementById("cancelAppointmentBtn").addEventListener("click", cancelSelectedAppointment);
  document.getElementById("rescheduleAppointmentBtn").addEventListener("click", rescheduleSelectedAppointment);
  document.getElementById("completeAppointmentBtn").addEventListener("click", completeSelectedAppointment);
  document.addEventListener("click", handleInlineActions);
}

function bindFilters() {
  ["scheduleDateFilter", "scheduleProfessionalFilter", "scheduleStatusFilter"].forEach((id) => {
    document.getElementById(id).addEventListener("input", renderAgenda);
  });
  document.getElementById("sessionSearch").addEventListener("input", renderSessions);
  document.getElementById("sessionMonthFilter").addEventListener("change", renderSessions);
  document.getElementById("patientSearch").addEventListener("input", renderPatients);
  document.getElementById("teamSearch").addEventListener("input", renderTeam);
}

function formData(form) {
  return Object.fromEntries(new FormData(form).entries());
}

function setDefaultDates() {
  document.querySelectorAll('input[type="date"]').forEach((input) => {
    if (!input.value) input.value = isoToday;
  });
}

function fillSelects() {
  const patientOptions = state.patients.map((patient) => `<option value="${patient.id}">${patient.name}</option>`).join("");
  const professionalOptions = state.professionals.map((professional) => `<option value="${professional.id}">${professional.name} - ${professional.specialty}</option>`).join("");

  document.querySelectorAll('select[name="patientId"]').forEach((select) => select.innerHTML = patientOptions);
  document.querySelectorAll('select[name="professionalId"]').forEach((select) => select.innerHTML = professionalOptions);

  const professionalFilter = document.getElementById("scheduleProfessionalFilter");
  professionalFilter.innerHTML = `<option value="all">Todos os profissionais</option>${professionalOptions}`;

  const months = [...new Set([...state.sessions, ...state.transactions].map((item) => item.date.slice(0, 7)))].sort().reverse();
  document.getElementById("sessionMonthFilter").innerHTML = `<option value="all">Todos os meses</option>${months.map((month) => `<option value="${month}">${formatMonth(month)}</option>`).join("")}`;
}

function renderDashboard() {
  const monthTransactions = state.transactions.filter((item) => item.date.startsWith(currentMonth));
  const income = sum(monthTransactions.filter((item) => item.type === "entrada" && item.status !== "Atrasado"), "amount");
  const expenses = sum(monthTransactions.filter((item) => item.type === "saida"), "amount");
  const monthSessions = state.sessions.filter((item) => item.date.startsWith(currentMonth));
  const doneSessions = monthSessions.filter((item) => item.status === "Realizada");
  const payouts = calculatePayouts(doneSessions);

  text("incomeMetric", money(income));
  text("expenseMetric", money(expenses));
  text("doneSessionsMetric", doneSessions.length);
  text("pendingSessionsMetric", `${state.appointments.filter((item) => item.status !== "Realizado" && item.status !== "Cancelado").length} pendentes`);
  text("payoutMetric", money(payouts));
  text("sidebarBalance", money(income - expenses));
  text("sidebarMonth", formatMonth(currentMonth));
  text("incomeTrend", `${monthTransactions.filter((item) => item.type === "entrada").length} recebimentos no mês`);

  renderTodayTimeline();
  renderFinanceBars(monthTransactions);
  renderProfessionalSummary(doneSessions);
}

function renderTodayTimeline() {
  const items = state.appointments
    .filter((item) => item.date === isoToday)
    .sort((a, b) => a.time.localeCompare(b.time));
  const container = document.getElementById("todayTimeline");
  container.innerHTML = items.length ? items.map((item) => `
    <div class="timeline-item">
      <strong>${item.time}</strong>
      <div>
        <h3>${getPatient(item.patientId).name}</h3>
        <small>${item.therapy} com ${getProfessional(item.professionalId).name}</small>
      </div>
      ${statusPill(item.status)}
    </div>
  `).join("") : empty("Nenhum atendimento agendado para hoje.");
}

function renderFinanceBars(transactions) {
  const byCategory = groupSum(transactions, "category");
  const total = Math.max(...Object.values(byCategory), 1);
  document.getElementById("financeBars").innerHTML = Object.entries(byCategory)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([category, value]) => `
      <div class="bar-row">
        <div class="bar-meta"><span>${category}</span><strong>${money(value)}</strong></div>
        <div class="bar-track"><div class="bar-fill" style="width:${Math.round((value / total) * 100)}%"></div></div>
      </div>
    `).join("") || empty("Sem movimentações neste mês.");
}

function renderProfessionalSummary(sessions) {
  document.getElementById("professionalSummary").innerHTML = state.professionals.map((professional) => {
    const ownSessions = sessions.filter((session) => session.professionalId === professional.id);
    const revenue = sum(ownSessions, "amount");
    return `
      <article class="professional-tile">
        <header>
          <div>
            <strong>${professional.name}</strong>
            <small>${professional.specialty}</small>
          </div>
          <span class="professional-number">${ownSessions.length}</span>
        </header>
        <div class="professional-money"><span>Receita</span><strong>${money(revenue)}</strong></div>
        <div class="professional-money"><span>Repasse</span><strong>${money(revenue * professional.commission / 100)}</strong></div>
      </article>
    `;
  }).join("");
}

function renderAgenda() {
  const date = document.getElementById("scheduleDateFilter").value || isoToday;
  const professional = document.getElementById("scheduleProfessionalFilter").value || "all";
  const status = document.getElementById("scheduleStatusFilter").value || "all";
  const days = Array.from({ length: 5 }, (_, index) => addDays(date, index));
  const filtered = state.appointments.filter((item) =>
    days.includes(item.date) &&
    (professional === "all" || item.professionalId === professional) &&
    (status === "all" || item.status === status)
  );

  document.getElementById("scheduleBoard").innerHTML = days.map((day) => {
    const items = filtered.filter((item) => item.date === day).sort((a, b) => a.time.localeCompare(b.time));
    return `
      <section class="schedule-day">
        <div class="schedule-day-head">
          <h3>${formatShortDate(day)}</h3>
          <span>${items.length} horário(s)</span>
        </div>
        ${items.map((item) => `
          <article class="schedule-item">
            <div class="schedule-time">${item.time}</div>
            <div class="schedule-main">
              <h3>${getPatient(item.patientId).name}</h3>
              <small>${item.therapy} com ${getProfessional(item.professionalId).name}</small>
            </div>
            <div class="schedule-status">${statusPill(item.status)}</div>
            ${item.status !== "Realizado" && item.status !== "Cancelado" ? `
              <div class="item-actions">
                <button class="mini-button" type="button" data-complete-appointment="${item.id}">Realizar</button>
                <button class="mini-button danger" type="button" data-cancel-appointment="${item.id}">Cancelar</button>
              </div>
            ` : ""}
          </article>
        `).join("") || empty("Sem horários.")}
      </section>
    `;
  }).join("");
}

function renderAgenda() {
  const date = document.getElementById("scheduleDateFilter").value || isoToday;
  const professional = document.getElementById("scheduleProfessionalFilter").value || "all";
  const status = document.getElementById("scheduleStatusFilter").value || "all";
  const visibleProfessionals = state.professionals.filter((item) => professional === "all" || item.id === professional);
  const slots = buildTimeSlots("07:00", "19:00", 30);
  if (expandedProfessionalId && !visibleProfessionals.some((item) => item.id === expandedProfessionalId)) {
    expandedProfessionalId = null;
  }
  const filtered = state.appointments.filter((item) =>
    item.date === date &&
    (professional === "all" || item.professionalId === professional) &&
    (status === "all" || item.status === status)
  );

  if (!visibleProfessionals.length) {
    document.getElementById("scheduleBoard").innerHTML = empty("Nenhuma profissional encontrada para este filtro.");
    return;
  }

  document.getElementById("scheduleBoard").innerHTML = `
    <section class="schedule-matrix-panel">
      <div class="schedule-matrix-head">
        <div>
          <p class="eyebrow">Mapa do dia</p>
          <h2>${formatDate(date)}</h2>
        </div>
        <div class="schedule-legend">
          <span><i class="legend-free"></i> Livre</span>
          <span><i class="legend-busy"></i> Confirmado/ocupado</span>
        </div>
      </div>
      <div class="matrix-scroll">
        <div class="schedule-matrix" style="grid-template-columns: 86px repeat(${visibleProfessionals.length}, minmax(150px, 1fr));">
          <div class="matrix-corner">Horário</div>
          ${visibleProfessionals.map((item) => `
            <button class="therapist-head ${expandedProfessionalId === item.id ? "active" : ""}" type="button" data-expand-professional="${item.id}">
              <strong>${item.name}</strong>
              <span>${item.specialty}</span>
            </button>
          `).join("")}
          ${slots.map((slot) => `
            <div class="time-head">${slot}</div>
            ${visibleProfessionals.map((therapist) => renderScheduleCell(slot, therapist, filtered)).join("")}
          `).join("")}
        </div>
      </div>
    </section>
    ${expandedProfessionalId ? renderExpandedProfessional(date, filtered) : ""}
  `;
}

function renderScheduleCell(slot, therapist, appointments) {
  const appointment = findAppointmentForSlot(slot, therapist.id, appointments);
  if (!appointment) {
    return `
      <button class="schedule-cell free" type="button" title="Clique para agendar" data-new-appointment-professional="${therapist.id}" data-new-appointment-time="${slot}">
        <span>Livre</span>
      </button>
    `;
  }
  const patient = getPatient(appointment.patientId);
  const range = `${appointment.time} às ${appointmentEndTime(appointment)}`;
  return `
    <button class="schedule-cell busy" type="button" title="${patient.name} - ${range}" data-view-appointment="${appointment.id}">
      <span>${patient.name}</span>
      <small>${appointment.time}</small>
      <div class="cell-tooltip">
        <strong>${patient.name}</strong>
        <span>${range}</span>
        <span>${appointment.therapy}</span>
      </div>
    </button>
  `;
}

function renderExpandedProfessional(date, appointments) {
  const professional = getProfessional(expandedProfessionalId);
  const items = appointments
    .filter((item) => item.professionalId === expandedProfessionalId)
    .sort((a, b) => a.time.localeCompare(b.time));
  return `
    <section class="professional-day-panel">
      <div class="section-title">
        <div>
          <p class="eyebrow">Dia da terapeuta</p>
          <h2>${professional.name}</h2>
        </div>
        <small>${formatDate(date)}</small>
      </div>
      <div class="professional-day-list">
        ${items.map((item) => `
          <article class="professional-day-item">
            <div class="schedule-time">${item.time} - ${appointmentEndTime(item)}</div>
            <div>
              <h3>${getPatient(item.patientId).name}</h3>
              <small>${item.therapy}</small>
            </div>
            ${statusPill(item.status)}
            ${item.status !== "Realizado" && item.status !== "Cancelado" ? `
              <div class="item-actions">
                <button class="mini-button" type="button" data-complete-appointment="${item.id}">Realizar</button>
                <button class="mini-button danger" type="button" data-cancel-appointment="${item.id}">Cancelar</button>
              </div>
            ` : ""}
          </article>
        `).join("") || empty("Nenhum paciente para esta profissional neste dia.")}
      </div>
    </section>
  `;
}

function handleInlineActions(event) {
  const target = event.target.closest("[data-complete-appointment], [data-cancel-appointment], [data-expand-professional], [data-new-appointment-professional], [data-view-appointment]");
  if (!target) return;
  const completeId = target.dataset.completeAppointment;
  const cancelId = target.dataset.cancelAppointment;
  const expandId = target.dataset.expandProfessional;
  const newAppointmentProfessional = target.dataset.newAppointmentProfessional;
  const viewAppointmentId = target.dataset.viewAppointment;
  if (completeId) completeAppointment(completeId);
  if (cancelId) cancelAppointment(cancelId);
  if (expandId) {
    expandedProfessionalId = expandedProfessionalId === expandId ? null : expandId;
    renderAgenda();
  }
  if (newAppointmentProfessional) {
    const date = document.getElementById("scheduleDateFilter").value || isoToday;
    openAppointmentModalWithSlot(newAppointmentProfessional, date, target.dataset.newAppointmentTime);
  }
  if (viewAppointmentId) openAppointmentDetails(viewAppointmentId);
}

function openAppointmentDetails(id) {
  const appointment = state.appointments.find((item) => item.id === id);
  if (!appointment) return;
  selectedAppointmentId = id;
  const patient = getPatient(appointment.patientId);
  const professional = getProfessional(appointment.professionalId);
  document.getElementById("appointmentDetailsContent").innerHTML = `
    <div class="detail-grid">
      <article class="detail-card">
        <small>Paciente</small>
        <strong>${patient.name}</strong>
        <span>Responsável: ${patient.guardian || "Não informado"}</span>
        <span>Telefone: ${patient.phone || "Não informado"}</span>
        <span>Diagnóstico: ${patient.diagnosis || "Não informado"}</span>
      </article>
      <article class="detail-card">
        <small>Atendimento</small>
        <strong>${appointment.therapy}</strong>
        <span>${formatDate(appointment.date)} - ${appointment.time} às ${appointmentEndTime(appointment)}</span>
        <span>Terapeuta: ${professional.name}</span>
        <span>Status: ${appointment.status}</span>
      </article>
      <article class="detail-card wide-detail">
        <small>Plano/observações</small>
        <span>${patient.plan || "Plano terapêutico não informado."}</span>
        <span>${appointment.notes || "Sem observações neste agendamento."}</span>
      </article>
    </div>
  `;
  openModal("appointmentDetailsModal");
}

function cancelSelectedAppointment() {
  if (!selectedAppointmentId) return;
  cancelAppointment(selectedAppointmentId);
  document.getElementById("appointmentDetailsModal").close();
}

function completeSelectedAppointment() {
  if (!selectedAppointmentId) return;
  completeAppointment(selectedAppointmentId);
  document.getElementById("appointmentDetailsModal").close();
}

function rescheduleSelectedAppointment() {
  const appointment = state.appointments.find((item) => item.id === selectedAppointmentId);
  if (!appointment) return;
  const newDate = prompt("Nova data", appointment.date);
  if (!newDate) return;
  const newTime = prompt("Novo horário", appointment.time);
  if (!newTime) return;
  appointment.date = newDate;
  appointment.time = newTime;
  appointment.status = "Confirmado";
  document.getElementById("appointmentDetailsModal").close();
  render();
}

function completeAppointment(id) {
  const appointment = state.appointments.find((item) => item.id === id);
  if (!appointment) return;
  const rawValue = prompt("Valor da sessão realizada", "180");
  if (rawValue === null) return;
  const amount = Number(String(rawValue).replace(",", "."));
  if (!Number.isFinite(amount) || amount < 0) {
    alert("Informe um valor válido.");
    return;
  }
  appointment.status = "Realizado";
  state.sessions.push({
    id: crypto.randomUUID(),
    patientId: appointment.patientId,
    professionalId: appointment.professionalId,
    therapy: appointment.therapy,
    date: appointment.date,
    amount,
    status: "Realizada",
    paymentStatus: "Pendente",
    notes: appointment.notes || "Gerado a partir da agenda"
  });
  render();
}

function cancelAppointment(id) {
  const appointment = state.appointments.find((item) => item.id === id);
  if (!appointment) return;
  appointment.status = "Cancelado";
  render();
}

function renderSessions() {
  const search = normalize(document.getElementById("sessionSearch").value);
  const month = document.getElementById("sessionMonthFilter").value || "all";
  const rows = state.sessions
    .filter((session) => month === "all" || session.date.startsWith(month))
    .filter((session) => {
      const haystack = normalize(`${getPatient(session.patientId).name} ${getProfessional(session.professionalId).name} ${session.therapy}`);
      return haystack.includes(search);
    })
    .sort((a, b) => b.date.localeCompare(a.date));

  document.getElementById("sessionsTable").innerHTML = rows.map((session) => `
    <tr>
      <td>${formatDate(session.date)}</td>
      <td><strong>${getPatient(session.patientId).name}</strong></td>
      <td>${getProfessional(session.professionalId).name}</td>
      <td>${session.therapy}</td>
      <td>${statusPill(session.status)}</td>
      <td>${money(session.amount)}</td>
      <td>${statusPill(session.paymentStatus)}</td>
    </tr>
  `).join("") || tableEmpty(7, "Nenhuma sessão encontrada.");
}

function renderFinance() {
  const rows = [...state.transactions].sort((a, b) => b.date.localeCompare(a.date));
  document.getElementById("transactionsTable").innerHTML = rows.map((item) => `
    <tr>
      <td>${formatDate(item.date)}</td>
      <td>${item.type === "entrada" ? "Entrada" : "Saída"}</td>
      <td>${item.category}</td>
      <td><strong>${item.description}</strong></td>
      <td>${statusPill(item.status)}</td>
      <td>${money(item.amount)}</td>
    </tr>
  `).join("") || tableEmpty(6, "Nenhum lançamento financeiro.");
}

function renderPatients() {
  const search = normalize(document.getElementById("patientSearch").value);
  const patients = state.patients.filter((patient) => normalize(`${patient.name} ${patient.guardian}`).includes(search));
  document.getElementById("patientsGrid").innerHTML = patients.map((patient) => {
    const sessions = state.sessions.filter((session) => session.patientId === patient.id);
    const pending = sessions.filter((session) => session.paymentStatus === "Pendente").length;
    return `
      <article class="person-card">
        <div>
          <h3>${patient.name}</h3>
          <small>Responsável: ${patient.guardian}</small>
        </div>
        <div class="person-meta">
          <span class="tag">${patient.diagnosis || "Sem diagnóstico"}</span>
          <span class="tag">${sessions.length} sessões</span>
          <span class="tag">${pending} pendentes</span>
        </div>
        <p>${patient.plan || "Plano terapêutico ainda não informado."}</p>
        <small>${patient.phone}</small>
      </article>
    `;
  }).join("") || empty("Nenhum paciente encontrado.");
}

function renderTeam() {
  const search = normalize(document.getElementById("teamSearch").value);
  const professionals = state.professionals.filter((professional) => normalize(`${professional.name} ${professional.specialty}`).includes(search));
  document.getElementById("teamGrid").innerHTML = professionals.map((professional) => {
    const sessions = state.sessions.filter((session) => session.professionalId === professional.id && session.status === "Realizada");
    const revenue = sum(sessions, "amount");
    return `
      <article class="person-card">
        <div>
          <h3>${professional.name}</h3>
          <small>${professional.specialty}</small>
        </div>
        <div class="person-meta">
          <span class="tag">${professional.commission}% repasse</span>
          <span class="tag">${sessions.length} sessões</span>
          <span class="tag">${money(revenue * professional.commission / 100)}</span>
        </div>
        <p>${professional.availability || "Agenda base não informada."}</p>
        <small>${professional.phone || "Telefone não informado"}</small>
      </article>
    `;
  }).join("") || empty("Nenhum profissional encontrado.");
}

function renderReports() {
  const therapyRevenue = groupSum(state.sessions.filter((item) => item.status === "Realizada"), "therapy");
  document.getElementById("therapyReport").innerHTML = Object.entries(therapyRevenue)
    .sort((a, b) => b[1] - a[1])
    .map(([therapy, value]) => `<div class="report-item"><strong>${therapy}</strong><br><small>${money(value)} em receita registrada</small></div>`)
    .join("") || empty("Sem sessões realizadas.");

  const pendingPatients = state.sessions.filter((session) => session.paymentStatus === "Pendente");
  document.getElementById("pendingReport").innerHTML = pendingPatients.map((session) => `
    <div class="report-item">
      <strong>${getPatient(session.patientId).name}</strong><br>
      <small>${session.therapy} em ${formatDate(session.date)} - ${money(session.amount)}</small>
    </div>
  `).join("") || empty("Nenhuma pendência financeira.");

  const totalRevenue = sum(state.transactions.filter((item) => item.type === "entrada"), "amount");
  const totalExpenses = sum(state.transactions.filter((item) => item.type === "saida"), "amount");
  const realized = state.sessions.filter((item) => item.status === "Realizada").length;
  const noShows = state.sessions.filter((item) => item.status === "Falta").length;
  document.getElementById("insightGrid").innerHTML = [
    ["Margem operacional", money(totalRevenue - totalExpenses)],
    ["Ticket médio", money(realized ? totalRevenue / realized : 0)],
    ["Taxa de faltas", `${realized + noShows ? Math.round((noShows / (realized + noShows)) * 100) : 0}%`],
    ["Pacientes ativos", state.patients.length]
  ].map(([label, value]) => `<div class="insight-card"><small>${label}</small><strong>${value}</strong></div>`).join("");
}

function calculatePayouts(sessions) {
  return sessions.reduce((total, session) => {
    const professional = getProfessional(session.professionalId);
    return total + session.amount * (professional.commission || 0) / 100;
  }, 0);
}

function getPatient(id) {
  return state.patients.find((patient) => patient.id === id) || { name: "Paciente removido" };
}

function getProfessional(id) {
  return state.professionals.find((professional) => professional.id === id) || { name: "Profissional removido", specialty: "", commission: 0 };
}

function statusPill(status) {
  const danger = ["Atrasado", "Falta", "Cancelado"].includes(status);
  const warn = ["Pendente", "Agendado", "Convênio"].includes(status);
  const rose = ["Confirmado", "Reposição"].includes(status);
  return `<span class="status ${danger ? "danger" : warn ? "warn" : rose ? "rose" : ""}">${status}</span>`;
}

function exportBackup() {
  download(`backup-clinica-florescer-${isoToday}.json`, JSON.stringify(state, null, 2), "application/json");
}

function importBackup(event) {
  const file = event.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    try {
      state = JSON.parse(reader.result);
      render();
    } catch {
      alert("Não foi possível importar este arquivo.");
    }
  };
  reader.readAsText(file);
}

function exportFinanceCsv() {
  const header = ["Data", "Tipo", "Categoria", "Descricao", "Status", "Valor"];
  const rows = state.transactions.map((item) => [item.date, item.type, item.category, item.description, item.status, item.amount]);
  const csv = [header, ...rows].map((row) => row.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(";")).join("\n");
  download(`fluxo-caixa-${isoToday}.csv`, csv, "text/csv;charset=utf-8");
}

function generatePayoutTransactions() {
  const monthSessions = state.sessions.filter((item) => item.date.startsWith(currentMonth) && item.status === "Realizada");
  let created = 0;
  state.professionals.forEach((professional) => {
    const ownSessions = monthSessions.filter((session) => session.professionalId === professional.id);
    const revenue = sum(ownSessions, "amount");
    const amount = revenue * professional.commission / 100;
    const description = `Repasse ${professional.name} - ${formatMonth(currentMonth)}`;
    const alreadyExists = state.transactions.some((item) => item.description === description);
    if (amount > 0 && !alreadyExists) {
      state.transactions.push({
        id: crypto.randomUUID(),
        type: "saida",
        category: "Repasse profissional",
        description,
        amount,
        date: isoToday,
        status: "Pendente"
      });
      created += 1;
    }
  });
  alert(created ? `${created} repasse(s) gerado(s).` : "Nenhum repasse novo para gerar.");
  render();
}

function download(filename, content, type) {
  const blob = new Blob([content], { type });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  link.click();
  URL.revokeObjectURL(link.href);
}

function money(value) { return formatter.format(value || 0); }
function sum(items, key) { return items.reduce((total, item) => total + Number(item[key] || 0), 0); }
function text(id, value) { document.getElementById(id).textContent = value; }
function normalize(value) { return String(value || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, ""); }
function empty(message) { return `<div class="empty">${message}</div>`; }
function tableEmpty(cols, message) { return `<tr><td colspan="${cols}">${empty(message)}</td></tr>`; }

function groupSum(items, key) {
  return items.reduce((acc, item) => {
    acc[item[key]] = (acc[item[key]] || 0) + Number(item.amount || 0);
    return acc;
  }, {});
}

function formatDate(date) {
  return dateFormatter.format(new Date(`${date}T12:00:00`));
}

function formatShortDate(date) {
  const parsed = new Date(`${date}T12:00:00`);
  return new Intl.DateTimeFormat("pt-BR", { weekday: "short", day: "2-digit", month: "2-digit" }).format(parsed);
}

function formatMonth(month) {
  return monthFormatter.format(new Date(`${month}-01T12:00:00`));
}

function addDays(date, amount) {
  const parsed = new Date(`${date}T12:00:00`);
  parsed.setDate(parsed.getDate() + amount);
  return parsed.toISOString().slice(0, 10);
}

function buildTimeSlots(start, end, interval) {
  const slots = [];
  for (let minutes = timeToMinutes(start); minutes <= timeToMinutes(end); minutes += interval) {
    slots.push(minutesToTime(minutes));
  }
  return slots;
}

function findAppointmentForSlot(slot, professionalId, appointments) {
  const slotMinutes = timeToMinutes(slot);
  return appointments.find((item) => {
    if (item.professionalId !== professionalId || item.status === "Cancelado") return false;
    const start = timeToMinutes(item.time);
    const end = start + Number(item.duration || 50);
    return slotMinutes >= start && slotMinutes < end;
  });
}

function appointmentEndTime(appointment) {
  return minutesToTime(timeToMinutes(appointment.time) + Number(appointment.duration || 50));
}

function timeToMinutes(time) {
  const [hours, minutes] = time.split(":").map(Number);
  return hours * 60 + minutes;
}

function minutesToTime(total) {
  const hours = Math.floor(total / 60);
  const minutes = total % 60;
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
}
