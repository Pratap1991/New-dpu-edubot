/**
 * DPU EduBot — main.js
 * Session-based auth, chat, admin, faculty logic.
 * Zero emojis — uses Material Icons throughout.
 */

// ──────────────────────────────────────────────────────────
// AUTH STATE
// ──────────────────────────────────────────────────────────
let authRole = null; // null | 'admin' | 'faculty'
let loginRoleSelected = 'admin'; // role highlighted in dialog

function openLoginDialog() {
  const overlay = document.getElementById('login-overlay');
  overlay.classList.remove('hidden');
  overlay.classList.add('flex');
  document.getElementById('login-password').value = '';
  document.getElementById('login-error').classList.add('hidden');
  selectLoginRole('admin');
  setTimeout(() => document.getElementById('login-password').focus(), 120);
}

function closeLoginDialog() {
  const overlay = document.getElementById('login-overlay');
  overlay.classList.add('hidden');
  overlay.classList.remove('flex');
}

function selectLoginRole(role) {
  loginRoleSelected = role;
  document.getElementById('role-tab-admin').classList.toggle('active', role === 'admin');
  document.getElementById('role-tab-faculty').classList.toggle('active', role === 'faculty');
}

function submitLogin() {
  const pw = document.getElementById('login-password').value.trim();
  const errEl = document.getElementById('login-error');

  const PASSWORDS = {
    admin: 'admin@dpu2026',
    faculty: 'faculty@dpu2026',
  };

  if (pw === PASSWORDS[loginRoleSelected]) {
    authRole = loginRoleSelected;
    sessionStorage.setItem('dpu_role', authRole);
    errEl.classList.add('hidden');
    closeLoginDialog();
    applyAuthState();
  } else {
    errEl.classList.remove('hidden');
    document.getElementById('login-password').value = '';
    document.getElementById('login-password').focus();
  }
}

function logout() {
  authRole = null;
  sessionStorage.removeItem('dpu_role');
  applyAuthState();
  switchRole('student');
}

const MOCK_STUDENT_METADATA = {
  ERP001: { name: 'Pratap Nayadkar', role: 'Student — MBA Online' },
  ERP002: { name: 'Riya Sharma', role: 'Student — MBA Online' },
  ERP003: { name: 'Arjun Mehta', role: 'Student — MBA Online' },
  ERP006: { name: 'Sneha Iyer', role: 'Student — BBA Online' },
  ERP009: { name: 'Vikram Joshi', role: 'Student — MBA Online' }
};

function applyAuthState() {
  const isAdmin   = authRole === 'admin';
  const isFaculty = authRole === 'faculty';
  const isLoggedIn = isAdmin || isFaculty;

  // Show/hide nav buttons
  document.getElementById('nav-admin').classList.toggle('hidden', !isAdmin);
  document.getElementById('nav-faculty').classList.toggle('hidden', !isFaculty);

  // Footer
  document.getElementById('btn-login-footer').classList.toggle('hidden', isLoggedIn);
  document.getElementById('btn-logout-section').classList.toggle('hidden', !isLoggedIn);

  // Profile card update
  const profileName = document.getElementById('profile-name');
  const profileRole = document.getElementById('profile-role');

  if (isAdmin) {
    profileName.textContent = 'ADMIN';
    profileRole.textContent = 'Administration Portal';
  } else if (isFaculty) {
    profileName.textContent = 'FACULTY';
    profileRole.textContent = 'Academic Portal';
  } else {
    const selectedErp = document.getElementById('student-erp-id')?.value;
    if (selectedErp && MOCK_STUDENT_METADATA[selectedErp]) {
      profileName.textContent = MOCK_STUDENT_METADATA[selectedErp].name.toUpperCase();
      profileRole.textContent = MOCK_STUDENT_METADATA[selectedErp].role;
    } else {
      profileName.textContent = 'STUDENT';
      profileRole.textContent = 'Online Learning Portal';
    }
  }

  if (isLoggedIn) {
    const label = isAdmin ? 'Admin — Signed In' : 'Faculty — Signed In';
    document.getElementById('logged-in-label').textContent = label;
  }
}

// ──────────────────────────────────────────────────────────
// ROUTING / VIEWS
// ──────────────────────────────────────────────────────────
let currentRole = 'student';
let currentAdminTab = 'dashboard';

function switchRole(role) {
  currentRole = role;

  // Sections
  ['student', 'admin', 'faculty'].forEach(r => {
    const sec = document.getElementById(`view-${r}`);
    if (sec) sec.classList.toggle('hidden', r !== role);
  });

  // Toolbar
  document.getElementById('student-toolbar').classList.toggle('hidden', role !== 'student');
  document.getElementById('admin-toolbar').classList.toggle('hidden', role !== 'admin');

  // Nav active state
  ['student', 'admin', 'faculty'].forEach(r => {
    const btn = document.getElementById(`nav-${r}`);
    if (btn) btn.classList.toggle('active', r === role);
  });

  // Page title / subtitle
  const titles = {
    student: ['Student Chat', 'Ask anything about your program, exams, fees, LMS, or support tickets.'],
    admin: ['Admin Panel', 'Monitor queries, manage escalations, SLA, FAQs and knowledge base.'],
    faculty: ['Faculty Portal', 'View batch info, query stats, and upload study materials.'],
  };
  document.getElementById('page-title').textContent = titles[role][0];
  document.getElementById('page-subtitle').textContent = titles[role][1];

  if (role === 'admin') {
    switchAdminTab(currentAdminTab);
  }
  if (role === 'faculty') {
    renderFacultyBatchInfo();
  }
}

function switchAdminTab(tab) {
  currentAdminTab = tab;
  document.querySelectorAll('.admin-tab-content').forEach(el => el.classList.add('hidden'));
  document.getElementById(`admin-tab-${tab}`)?.classList.remove('hidden');

  document.querySelectorAll('.tab-btn').forEach((btn, i) => {
    const tabs = ['dashboard', 'escalations', 'sla', 'faqs', 'kb'];
    btn.classList.toggle('active', tabs[i] === tab);
  });

  if (tab === 'escalations') renderEscalationQueue();
  if (tab === 'dashboard')   renderDashboardEscalations();
  if (tab === 'sla')         renderSLACountdowns();
  if (tab === 'faqs')        renderFAQList();
  if (tab === 'kb')          loadKBStats();
}

// ──────────────────────────────────────────────────────────
// CHAT
// ──────────────────────────────────────────────────────────
let batchId = 'mba_jan_26_sem1';

function updateBatch() {
  batchId = document.getElementById('student-batch').value;
}

function updateErpId() {
  applyAuthState();
}

function suggestQuery(text) {
  document.getElementById('chat-input').value = text;
  sendChatMessage();
}

async function sendChatMessage() {
  const input = document.getElementById('chat-input');
  const query = input.value.trim();
  if (!query) return;
  input.value = '';

  appendMessage('user', query);
  const typingId = appendTypingIndicator();

  try {
    const lang = document.getElementById('student-lang').value;
    const erpIdVal = document.getElementById('student-erp-id')?.value || null;
    const resp = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, batch_id: batchId, language: lang, erp_id: erpIdVal }),
    });

    const data = await resp.json();
    removeTypingIndicator(typingId);

    if (data.error) {
      appendMessage('assistant', data.error, [], null);
    } else {
      const erpAction = data.erp_action || (data.erp_link ? { url: data.erp_link, label: data.erp_label } : null);
      appendMessage('assistant', data.answer, data.sources || [], erpAction, data.escalate || false);
    }
  } catch (err) {
    removeTypingIndicator(typingId);
    appendMessage('assistant', 'Connection error. Please check the server and retry.');
  }
}

function appendMessage(role, text, sources = [], erpAction = null, showEscalate = false) {
  const container = document.getElementById('chat-messages');
  const wrap = document.createElement('div');
  wrap.className = `msg-wrapper ${role}`;

  const icon = role === 'user' ? 'person' : 'smart_toy';
  const avatarEl = `<div class="msg-avatar"><span class="material-icons-round">${icon}</span></div>`;

  let srcHtml = '';
  if (sources && sources.length > 0) {
    const chips = sources.slice(0, 4).map(s =>
      `<span class="src-chip"><span class="material-icons-round text-xs">link</span>${s}</span>`
    ).join(' ');
    srcHtml = `<div class="mt-2 flex flex-wrap gap-1">${chips}</div>`;
  }

  let erpHtml = '';
  if (erpAction) {
    erpHtml = `<button onclick='handleERP(${JSON.stringify(erpAction)})'
      class="erp-btn">
      <span class="material-icons-round text-sm">open_in_new</span>
      ${erpAction.label || 'View in ERP Portal'}
    </button>`;
  }

  let escalateHtml = '';
  if (showEscalate) {
    escalateHtml = `<button onclick='openRaiseTicketDialog()'
      class="erp-btn !bg-slate-500 hover:!bg-slate-600 ml-2 shadow-none">
      <span class="material-icons-round text-sm">add_circle</span>
      Raise Grievance Ticket
    </button>`;
  }

  const textHtml = text.replace(/\n/g, '<br/>');
  wrap.innerHTML = `
    ${role === 'user' ? '' : avatarEl}
    <div class="flex flex-col">
      <div class="msg-bubble">${textHtml}${srcHtml}${erpHtml}${escalateHtml}</div>
    </div>
    ${role === 'user' ? avatarEl : ''}
  `;

  container.appendChild(wrap);
  container.scrollTop = container.scrollHeight;
  return wrap;
}

function appendTypingIndicator() {
  const container = document.getElementById('chat-messages');
  const id = `typing-${Date.now()}`;
  const div = document.createElement('div');
  div.id = id;
  div.className = 'msg-wrapper assistant';
  div.innerHTML = `
    <div class="msg-avatar"><span class="material-icons-round">smart_toy</span></div>
    <div class="msg-bubble flex items-center gap-1.5 text-white/30 text-sm">
      <span class="material-icons-round text-base animate-pulse">more_horiz</span>
      Thinking...
    </div>
  `;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
  return id;
}

function removeTypingIndicator(id) {
  document.getElementById(id)?.remove();
}

function handleERP(action) {
  if (action.url) window.open(action.url, '_blank');
}

// ──────────────────────────────────────────────────────────
// INDEX STATUS
// ──────────────────────────────────────────────────────────
async function checkIndexStatus() {
  try {
    const r = await fetch('/api/kb_status');
    const d = await r.json();
    const dot  = document.getElementById('index-dot');
    const text = document.getElementById('index-text');
    const stat  = document.getElementById('stat-index-status');
    const sub   = document.getElementById('stat-index-sub');
    const kbChunks = document.getElementById('kb-chunks-count');

    const chunks = d.chunks_count || d.chunks || 0;
    if (d.ready) {
      dot.className  = 'w-2 h-2 rounded-full bg-green-400';
      text.textContent = `Index: ${chunks} chunks`;
      if (stat) { stat.textContent = 'Ready'; stat.className = 'stat-value text-green-400'; }
      if (sub)  sub.textContent = `${chunks} chunks indexed`;
    } else {
      dot.className  = 'w-2 h-2 rounded-full bg-red-400';
      text.textContent = 'Index: Not Built';
      if (stat) { stat.textContent = 'Not Ready'; stat.className = 'stat-value text-red-400'; }
      if (sub)  sub.textContent = 'Rebuild required';
    }
    if (kbChunks) kbChunks.textContent = chunks ? `${chunks} vectors` : 'Not built';
  } catch {
    document.getElementById('index-dot').className = 'w-2 h-2 rounded-full bg-gray-500';
    document.getElementById('index-text').textContent = 'Index: Offline';
  }
}

// ──────────────────────────────────────────────────────────
// ESCALATION DATA (mock until live API)
// ──────────────────────────────────────────────────────────
const mockTickets = [
  {
    id: 'ESC-001', student: 'Rahul Patil', roll: 'MBA-JAN26-101',
    category: 'accounts', priority: 'high', status: 'Open',
    question: 'My semester fee payment of Rs.45,000 shows as failed but amount is deducted.',
    time: '2h ago', batch: 'MBA Jan 2026 Sem 1',
    context: 'Payment attempted via HDFC Net Banking. Transaction ID: HDFC2026070901.',
    ai_reply: `Dear Rahul Patil,

Thank you for reaching out regarding your fee payment.

As per the DPU COL refund policy, any amounts deducted for failed transactions are refunded within 7-10 working days through the original payment method.

Please raise a formal ticket at https://dpuol.dpuakurdi.edu.in by navigating to Help Desk > Fee Grievance and attaching:
1. Bank transaction receipt / screenshot
2. Your enrollment ID

For urgent escalation, contact the Accounts department at +91-20-3087-2000.

Reference Policy: DPU COL Fee Refund Policy v2.3 | SLA: 24 hours from ticket submission

Best regards,
DPU COL Student Support`,
  },
  {
    id: 'ESC-002', student: 'Priya Shah', roll: 'MBA-JAN26-203',
    category: 'exam', priority: 'high', status: 'Open',
    question: 'Hall ticket not generated 3 days before the examination.',
    time: '5h ago', batch: 'MBA Jan 2026 Sem 1',
    context: 'Examinations begin in 3 days. Student is fully fee-cleared.',
    ai_reply: `Dear Priya Shah,

Regarding your hall ticket — as your fee clearance is confirmed, this appears to be a technical issue on the Examination portal.

Immediate steps:
1. Login to https://dpuol.dpuakurdi.edu.in > Examination > Hall Ticket Download
2. Clear browser cache and try again (Ctrl+Shift+Delete)
3. If still unavailable, email examination@dpuakurdi.edu.in with your enrollment ID and a screenshot

The Examinations department SLA for this category is 24 hours and they prioritize pre-exam requests.

Your exam schedule remains valid; our records confirm your eligibility.

Best regards,
DPU COL Student Support`,
  },
  {
    id: 'ESC-003', student: 'Arjun Mehta', roll: 'BBA-JAN26-075',
    category: 'academic', priority: 'medium', status: 'In Progress',
    question: 'LMS login credentials not working despite multiple reset attempts.',
    time: '1d ago', batch: 'BBA Jan 2026 Sem 1',
    context: 'Student applied on Day 1 of semester. All enrolment docs verified.',
    ai_reply: `Dear Arjun Mehta,

For LMS access issues, the IT helpdesk team is the single point of contact.

Please use this link to reset credentials: https://lms.dpuakurdi.edu.in/password-reset

If that does not resolve it within 2 hours:
- Email: itsupport@dpuakurdi.edu.in
- Phone: +91-20-3087-2001 (Mon-Sat, 9 AM - 6 PM)
- Include: Enrollment ID, registered mobile number, error screenshot

Your academic coordinator has been informed and will follow up within 1 business day.

Best regards,
DPU COL Student Support`,
  },
  {
    id: 'ESC-004', student: 'Sneha Kulkarni', roll: 'MBA-JAN26-312',
    category: 'dispatch', priority: 'low', status: 'Resolved',
    question: 'Study material books not received after 4 weeks of enrollment.',
    time: '3d ago', batch: 'MBA Jan 2026 Sem 1',
    context: 'Dispatch initiated 3 weeks ago per ERP. Tracking ID: DTDC20260612.',
    ai_reply: `Dear Sneha Kulkarni,

The tracking details for your shipment: DTDC Courier, AWB: DTDC20260612.

Books are dispatched within 2-3 weeks of enrollment. Please track at: https://dtdc.in/tracking

If the parcel is not delivered within 5 working days of this response, please raise a fresh ticket with the tracking ID and address confirmation.

Books Dispatch SLA: 72 hours for status update.

Best regards,
DPU COL Student Support`,
  },
];

let selectedTicketId = null;

function renderEscalationQueue() {
  const filter = document.getElementById('escalation-filter')?.value || 'All';
  const container = document.getElementById('tickets-queue-container');
  if (!container) return;
  container.innerHTML = '';

  const visible = filter === 'All' ? mockTickets : mockTickets.filter(t => t.status === filter);

  visible.forEach(tkt => {
    const el = document.createElement('div');
    el.id = `tkt-${tkt.id}`;
    el.className = `tkt-row${selectedTicketId === tkt.id ? ' selected' : ''}`;
    el.onclick = () => openTicket(tkt.id);

    const catMap = { accounts: 'accounts', exam: 'exam', academic: 'academic', dispatch: 'dispatch' };
    const catClass = `cat-${catMap[tkt.category] || 'academic'}`;
    const priClass  = `pri-${tkt.priority}`;

    el.innerHTML = `
      <div class="flex-1 min-w-0">
        <div class="flex items-center gap-2 mb-1 flex-wrap">
          <span class="tkt-id">${tkt.id}</span>
          <span class="cat-chip ${catClass}">${tkt.category}</span>
          <span class="pri-badge ${priClass}">${tkt.priority.toUpperCase()}</span>
          <span class="ml-auto text-xs text-white/25">${tkt.time}</span>
        </div>
        <div class="tkt-q truncate">${tkt.question}</div>
        <div class="tkt-meta">${tkt.student} &middot; ${tkt.roll} &middot; ${tkt.batch}</div>
      </div>
    `;
    container.appendChild(el);
  });
}

function openTicket(id) {
  selectedTicketId = id;
  renderEscalationQueue();

  const tkt = mockTickets.find(t => t.id === id);
  if (!tkt) return;

  document.getElementById('composer-ticket-preview').classList.add('hidden');
  document.getElementById('composer-reply-box').classList.remove('hidden');
  document.getElementById('ai-reply-text').value = tkt.ai_reply;
}

function copyReplyText() {
  const txt = document.getElementById('ai-reply-text').value;
  navigator.clipboard.writeText(txt).then(() => {
    showToast('Reply copied to clipboard');
  });
}

function markTicketResolved() {
  if (!selectedTicketId) return;
  const tkt = mockTickets.find(t => t.id === selectedTicketId);
  if (tkt) tkt.status = 'Resolved';
  showToast(`Ticket ${selectedTicketId} marked as resolved`);
  selectedTicketId = null;
  document.getElementById('composer-ticket-preview').classList.remove('hidden');
  document.getElementById('composer-reply-box').classList.add('hidden');
  renderEscalationQueue();
}

function renderDashboardEscalations() {
  const cont = document.getElementById('dashboard-recent-escalations');
  if (!cont) return;
  cont.innerHTML = '';
  mockTickets.slice(0, 3).forEach(tkt => {
    const priClass = `pri-${tkt.priority}`;
    const catMap = { accounts: 'accounts', exam: 'exam', academic: 'academic', dispatch: 'dispatch' };
    const catClass = `cat-${catMap[tkt.category] || 'academic'}`;
    const div = document.createElement('div');
    div.className = 'flex items-start gap-2 py-2 border-b border-border last:border-0';
    div.innerHTML = `
      <span class="cat-chip ${catClass} mt-0.5">${tkt.category}</span>
      <div class="flex-1 min-w-0">
        <p class="text-xs text-white/80 font-medium truncate">${tkt.question}</p>
        <p class="text-xs text-white/30 mt-0.5">${tkt.student} &middot; ${tkt.time}</p>
      </div>
      <span class="pri-badge ${priClass}">${tkt.priority.toUpperCase()}</span>
    `;
    cont.appendChild(div);
  });
}

// ──────────────────────────────────────────────────────────
// SLA COUNTDOWNS
// ──────────────────────────────────────────────────────────
const slaData = [
  { id: 'ESC-001', student: 'Rahul Patil', category: 'Accounts & Fees', slaHours: 24, elapsedHours: 2,  priority: 'high' },
  { id: 'ESC-002', student: 'Priya Shah',  category: 'Examinations',    slaHours: 24, elapsedHours: 5,  priority: 'high' },
  { id: 'ESC-003', student: 'Arjun Mehta', category: 'Academic & LMS',  slaHours: 48, elapsedHours: 24, priority: 'medium' },
];

function renderSLACountdowns() {
  const cont = document.getElementById('sla-countdown-container');
  if (!cont) return;
  cont.innerHTML = '';

  slaData.forEach(s => {
    const pct = Math.min(100, Math.round((s.elapsedHours / s.slaHours) * 100));
    const rem = s.slaHours - s.elapsedHours;
    const barColor = pct >= 80 ? 'sla-red' : pct >= 50 ? 'sla-amber' : 'sla-green';
    const textColor = pct >= 80 ? 'text-red-400' : pct >= 50 ? 'text-amber-400' : 'text-green-400';

    const div = document.createElement('div');
    div.className = 'flex flex-col gap-1.5';
    div.innerHTML = `
      <div class="flex items-center justify-between">
        <div>
          <span class="font-mono text-xs font-bold text-blue-400">${s.id}</span>
          <span class="text-xs text-white/60 ml-2">${s.student}</span>
          <span class="cat-chip cat-${s.priority === 'high' ? 'exam' : 'academic'} ml-1">${s.category}</span>
        </div>
        <span class="${textColor} text-xs font-bold">${rem}h remaining</span>
      </div>
      <div class="sla-bar-bg">
        <div class="sla-bar-fill ${barColor}" style="width:${pct}%"></div>
      </div>
      <div class="flex justify-between text-xs text-white/25">
        <span>${s.elapsedHours}h elapsed</span>
        <span>SLA: ${s.slaHours}h total (${pct}% used)</span>
      </div>
    `;
    cont.appendChild(div);
  });
}

// ──────────────────────────────────────────────────────────
// FAQ MANAGER
// ──────────────────────────────────────────────────────────
const mockFAQs = [
  {
    id: 'F001', category: 'accounts',
    question: 'How do I pay my semester fee online?',
    answer: 'Visit dpuol.dpuakurdi.edu.in > My Account > Fee Payment. Accepted: NEFT, UPI, debit card. Generate challan first.',
    tags: ['fee', 'payment', 'upi', 'neft'],
  },
  {
    id: 'F002', category: 'accounts',
    question: 'When will a failed payment be refunded?',
    answer: 'Refunds for failed transactions are processed within 7-10 working days via original payment method.',
    tags: ['refund', 'failed payment', 'transaction'],
  },
  {
    id: 'F003', category: 'academic',
    question: 'How do I access my session recordings?',
    answer: 'Login to LMS > My Courses > select course > Session Recordings tab. Available within 24h of the live session.',
    tags: ['lms', 'recording', 'session'],
  },
  {
    id: 'F004', category: 'academic',
    question: 'How do I submit an assignment?',
    answer: 'LMS > My Courses > Assignments > Upload file (PDF/DOCX, max 20 MB) > Submit. Submission closes at 11:59 PM IST on due date.',
    tags: ['assignment', 'submit', 'upload'],
  },
  {
    id: 'F005', category: 'examination',
    question: 'How do I download my hall ticket?',
    answer: 'LMS > Examination > Hall Ticket. Available 7 days before the exam. Requires fee clearance.',
    tags: ['hall ticket', 'exam', 'download'],
  },
  {
    id: 'F006', category: 'dispatch',
    question: 'When will I receive my study material books?',
    answer: 'Books are dispatched within 2-3 weeks of enrollment confirmation via courier (DTDC / SpeedPost). Track on courier website using AWB from ERP.',
    tags: ['books', 'dispatch', 'courier', 'awb'],
  },
];

function toggleAddFAQModal() {
  document.getElementById('add-faq-form').classList.toggle('hidden');
}

function saveFAQ() {
  const q = document.getElementById('new-faq-q').value.trim();
  const a = document.getElementById('new-faq-a').value.trim();
  const cat = document.getElementById('new-faq-cat').value;
  const tags = document.getElementById('new-faq-tags').value.split(',').map(t => t.trim()).filter(Boolean);

  if (!q || !a) { showToast('Question and answer are required', 'error'); return; }

  mockFAQs.push({
    id: `F${String(mockFAQs.length + 1).padStart(3, '0')}`,
    category: cat, question: q, answer: a, tags,
  });

  document.getElementById('new-faq-q').value = '';
  document.getElementById('new-faq-a').value = '';
  document.getElementById('new-faq-tags').value = '';
  toggleAddFAQModal();
  renderFAQList();
  showToast('FAQ saved to knowledge base');
}

function renderFAQList() {
  const cont = document.getElementById('faq-list-container');
  if (!cont) return;
  const filter = document.getElementById('faq-cat-filter')?.value || 'All';
  const visible = filter === 'All' ? mockFAQs : mockFAQs.filter(f => f.category === filter);
  cont.innerHTML = '';

  const grouped = {};
  visible.forEach(f => {
    if (!grouped[f.category]) grouped[f.category] = [];
    grouped[f.category].push(f);
  });

  const catLabels = { accounts: 'Accounts & Fees', academic: 'Academic & LMS', examination: 'Examinations', dispatch: 'Books Dispatch' };

  Object.entries(grouped).forEach(([cat, faqs]) => {
    const section = document.createElement('div');
    section.className = 'mb-4';
    section.innerHTML = `<div class="faq-section-title">${catLabels[cat] || cat}</div>`;
    faqs.forEach(f => {
      const item = document.createElement('div');
      item.className = 'faq-item';
      item.innerHTML = `
        <div class="faq-q">${f.question}</div>
        <div class="faq-a">${f.answer}</div>
        <div class="mt-2 flex gap-1 flex-wrap">
          ${f.tags.map(t => `<span class="src-chip">${t}</span>`).join('')}
        </div>
      `;
      section.appendChild(item);
    });
    cont.appendChild(section);
  });
}

// ──────────────────────────────────────────────────────────
// KB / ADMIN REBUILD
// ──────────────────────────────────────────────────────────
async function loadKBStats() {
  const el = document.getElementById('kb-chunks-count');
  try {
    const r = await fetch('/api/kb_status');
    const d = await r.json();
    if (el) el.textContent = (d.chunks_count || d.chunks) ? `${d.chunks_count || d.chunks} vectors` : 'Not built';
  } catch {
    if (el) el.textContent = 'Unavailable';
  }
}

async function rebuildIndexAPI() {
  const btn = document.getElementById('btn-rebuild-index');
  const spin = document.getElementById('rebuild-spinner');
  btn.disabled = true;
  spin.classList.remove('hidden');

  try {
    const r = await fetch('/api/rebuild_index', { method: 'POST' });
    const d = await r.json();
    showToast(d.message || 'Index rebuilt successfully');
    checkIndexStatus();
    loadKBStats();
  } catch {
    showToast('Rebuild failed — check server logs', 'error');
  } finally {
    btn.disabled = false;
    spin.classList.add('hidden');
  }
}

async function uploadDocumentAPI(e) {
  e.preventDefault();
  const form   = document.getElementById('doc-upload-form');
  const status = document.getElementById('upload-status');
  const formData = new FormData(form);

  status.innerHTML = `<span class="text-blue-400 flex items-center gap-1.5"><span class="material-icons-round text-sm animate-pulse">hourglass_top</span> Uploading and parsing...</span>`;

  try {
    const r = await fetch('/api/upload_doc', { method: 'POST', body: formData });
    const d = await r.json();
    if (d.error) {
      status.innerHTML = `<span class="text-red-400">${d.error}</span>`;
    } else {
      status.innerHTML = `<span class="text-green-400 flex items-center gap-1.5"><span class="material-icons-round text-sm">check_circle</span> ${d.message}</span>`;
      form.reset();
    }
  } catch {
    status.innerHTML = `<span class="text-red-400">Upload failed — check server connection.</span>`;
  }
}

// ──────────────────────────────────────────────────────────
// FACULTY
// ──────────────────────────────────────────────────────────
const batchData = {
  mba_jan_26_sem1: {
    name: 'MBA Jan 2026 — Semester 1',
    programme: 'MBA',
    students: 247,
    examStart: '2026-08-10',
    assignmentDue: '2026-07-28',
    sessionDays: 'Monday, Wednesday, Friday',
    subjects: ['Management Concepts & OB', 'Managerial Economics', 'Business Statistics', 'Marketing Management', 'Financial Accounting'],
  },
  bba_jan_26_sem1: {
    name: 'BBA Jan 2026 — Semester 1',
    programme: 'BBA',
    students: 189,
    examStart: '2026-08-12',
    assignmentDue: '2026-07-25',
    sessionDays: 'Tuesday, Thursday, Saturday',
    subjects: ['Principles of Management', 'Business Communication', 'Financial Accounting', 'Economics', 'Business Mathematics'],
  },
};

function renderFacultyBatchInfo() {
  const batchId = document.getElementById('faculty-batch-select').value;
  const d = batchData[batchId];
  const cont = document.getElementById('faculty-batch-info');
  if (!cont || !d) return;

  cont.innerHTML = `
    <div class="grid grid-cols-2 gap-2">
      <div class="bg-slate-50 border border-slate-200 rounded-lg p-3"><div class="text-xs text-slate-500 mb-0.5">Enrolled Students</div><div class="text-lg font-bold text-slate-800">${d.students}</div></div>
      <div class="bg-slate-50 border border-slate-200 rounded-lg p-3"><div class="text-xs text-slate-500 mb-0.5">Exam Start</div><div class="text-sm font-bold text-amber-600">${d.examStart}</div></div>
      <div class="bg-slate-50 border border-slate-200 rounded-lg p-3 col-span-2"><div class="text-xs text-slate-500 mb-0.5">Assignment Due</div><div class="text-sm font-bold text-red-600">${d.assignmentDue}</div></div>
      <div class="bg-slate-50 border border-slate-200 rounded-lg p-3 col-span-2"><div class="text-xs text-slate-500 mb-1">Session Days</div><div class="text-sm text-slate-800">${d.sessionDays}</div></div>
    </div>
    <div class="mt-3">
      <div class="text-xs text-slate-500 font-semibold mb-2">Subjects (Sem 1)</div>
      <div class="flex flex-col gap-1">
        ${d.subjects.map((s, i) => `<div class="text-xs bg-slate-50 border border-slate-100 rounded px-2 py-1.5 flex items-center gap-2 text-slate-700"><span class="material-icons-round text-[#AE2E2D] text-sm">book</span>${s}</div>`).join('')}
      </div>
    </div>
  `;
}

async function uploadFacultyDoc(e) {
  e.preventDefault();
  const form   = document.getElementById('faculty-upload-form');
  const status = document.getElementById('faculty-upload-status');
  const formData = new FormData(form);

  status.innerHTML = `<span class="text-blue-400 flex items-center gap-1.5"><span class="material-icons-round text-sm animate-pulse">hourglass_top</span> Uploading...</span>`;

  try {
    const r = await fetch('/api/upload_doc', { method: 'POST', body: formData });
    const d = await r.json();
    if (d.error) {
      status.innerHTML = `<span class="text-red-400">${d.error}</span>`;
    } else {
      status.innerHTML = `<span class="text-green-400 flex items-center gap-1.5"><span class="material-icons-round text-sm">check_circle</span> ${d.message}</span>`;
      form.reset();
    }
  } catch {
    status.innerHTML = `<span class="text-red-400">Upload failed — check server connection.</span>`;
  }
}

// ──────────────────────────────────────────────────────────
// TOAST NOTIFICATIONS
// ──────────────────────────────────────────────────────────
function showToast(message, type = 'success') {
  const existing = document.getElementById('toast-container');
  if (!existing) {
    const cont = document.createElement('div');
    cont.id = 'toast-container';
    cont.className = 'fixed bottom-4 right-4 z-[9999] flex flex-col gap-2';
    document.body.appendChild(cont);
  }

  const icon = type === 'error' ? 'error' : 'check_circle';
  const color = type === 'error' ? 'bg-red-900/90 border-red-800' : 'bg-green-900/90 border-green-800';

  const toast = document.createElement('div');
  toast.className = `flex items-center gap-2.5 px-4 py-3 rounded-lg border text-sm font-medium text-white shadow-2xl ${color}`;
  toast.style.animation = 'msgIn 0.2s ease';
  toast.innerHTML = `<span class="material-icons-round text-base">${icon}</span> ${message}`;

  document.getElementById('toast-container').appendChild(toast);
  setTimeout(() => toast.remove(), 3500);
}

// ──────────────────────────────────────────────────────────
// INIT
// ──────────────────────────────────────────────────────────
function init() {
  // Restore session
  const saved = sessionStorage.getItem('dpu_role');
  if (saved === 'admin' || saved === 'faculty') {
    authRole = saved;
  }

  applyAuthState();
  checkIndexStatus();

  // Load initial welcome message
  appendMessage('assistant',
    'Hello! I am the DPU EduBot, your AI learning assistant for Dr. D.Y. Patil Centre for Online Learning.\n\n' +
    'I can help you with:\n' +
    '- Exam schedules and hall tickets\n' +
    '- Fee payment and refund queries\n' +
    '- LMS access, session recordings, assignments\n' +
    '- Book dispatch and support tickets\n\n' +
    'Please select your batch above and type your question.'
  );

  // Poll index status every 30s
  setInterval(checkIndexStatus, 30000);
}

document.addEventListener('DOMContentLoaded', init);

// Close login on overlay click outside the dialog
document.getElementById('login-overlay')?.addEventListener('click', function(e) {
  if (e.target === this) closeLoginDialog();
});

// ──────────────────────────────────────────────────────────
// RESPONSIVE SIDEBAR TOGGLE (MOBILE)
// ──────────────────────────────────────────────────────────
function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebar-overlay');
  const isOpen = sidebar.classList.contains('open');
  if (isOpen) {
    sidebar.classList.remove('open');
    overlay.classList.remove('active');
  } else {
    sidebar.classList.add('open');
    overlay.classList.add('active');
  }
}

function closeSidebar() {
  document.getElementById('sidebar').classList.remove('open');
  document.getElementById('sidebar-overlay').classList.remove('active');
}

// Auto-close sidebar on mobile when a nav item is clicked
document.querySelectorAll('.nav-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    if (window.innerWidth <= 768) closeSidebar();
  });
});

// ──────────────────────────────────────────────────────────
// SPEECH RECOGNITION (VOICE INPUT)
// ──────────────────────────────────────────────────────────
let recognition = null;
let isListening = false;

function initSpeechRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    console.warn("Speech recognition is not supported in this browser.");
    const micBtn = document.getElementById('mic-btn');
    if (micBtn) micBtn.style.display = 'none';
    return;
  }

  recognition = new SpeechRecognition();
  recognition.continuous = false;
  recognition.interimResults = false;

  recognition.onstart = () => {
    isListening = true;
    const micIcon = document.getElementById('mic-icon');
    if (micIcon) {
      micIcon.textContent = 'mic_off';
      micIcon.classList.add('text-red-600', 'animate-pulse');
    }
    const chatInput = document.getElementById('chat-input');
    if (chatInput) chatInput.placeholder = 'Listening... Speak now...';
  };

  recognition.onend = () => {
    isListening = false;
    const micIcon = document.getElementById('mic-icon');
    if (micIcon) {
      micIcon.textContent = 'mic';
      micIcon.classList.remove('text-red-600', 'animate-pulse');
    }
    const chatInput = document.getElementById('chat-input');
    if (chatInput) chatInput.placeholder = 'Type your question about DPU programs, exams, fees...';
  };

  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    const chatInput = document.getElementById('chat-input');
    if (chatInput) {
      chatInput.value = transcript;
    }
  };

  recognition.onerror = (event) => {
    console.error("Speech recognition error:", event.error);
    isListening = false;
    const micIcon = document.getElementById('mic-icon');
    if (micIcon) {
      micIcon.textContent = 'mic';
      micIcon.classList.remove('text-red-600', 'animate-pulse');
    }
  };
}

function toggleVoiceInput() {
  if (!recognition) {
    initSpeechRecognition();
  }

  if (!recognition) return;

  if (isListening) {
    recognition.stop();
  } else {
    // Select language code dynamically
    const selectedLang = document.getElementById('student-lang')?.value || 'English';
    if (selectedLang === 'Hindi') {
      recognition.lang = 'hi-IN';
    } else if (selectedLang === 'Marathi') {
      recognition.lang = 'mr-IN';
    } else {
      recognition.lang = 'en-IN';
    }
    recognition.start();
  }
}

// ──────────────────────────────────────────────────────────
// RAISE GRIVANCE TICKET DIALOG (STUDENT)
// ──────────────────────────────────────────────────────────
function openRaiseTicketDialog() {
  const overlay = document.getElementById('ticket-overlay');
  if (!overlay) return;
  overlay.classList.remove('hidden');
  overlay.classList.add('flex');

  // Pre-fill ERP ID if selected in toolbar
  const selectedErp = document.getElementById('student-erp-id')?.value;
  const erpInput = document.getElementById('ticket-erp-id');
  if (erpInput) {
    erpInput.value = selectedErp || '';
  }
  document.getElementById('ticket-subject').value = '';
  document.getElementById('ticket-desc').value = '';
}

function closeRaiseTicketDialog() {
  const overlay = document.getElementById('ticket-overlay');
  if (overlay) {
    overlay.classList.add('hidden');
    overlay.classList.remove('flex');
  }
}

function submitGrievanceTicket() {
  const erpId = document.getElementById('ticket-erp-id').value.trim();
  const cat = document.getElementById('ticket-category').value;
  const subject = document.getElementById('ticket-subject').value.trim();
  const desc = document.getElementById('ticket-desc').value.trim();

  if (!erpId || !subject || !desc) {
    showToast('Please fill in all fields to submit.', 'error');
    return;
  }

  const newTicket = {
    id: `ESC-${Math.floor(100 + Math.random() * 900)}`,
    student: MOCK_STUDENT_METADATA[erpId]?.name || erpId,
    roll: erpId,
    category: cat.toLowerCase(),
    priority: 'high',
    status: 'Open',
    question: subject,
    time: 'Just now',
    context: desc,
    ai_reply: 'Suggested AI reply: Please check the ticket description. Our team will get back to you shortly.'
  };

  mockTickets.unshift(newTicket); // Add to the top of mockTickets!
  closeRaiseTicketDialog();
  showToast(`Ticket ${newTicket.id} raised successfully!`);

  // Re-render escalation lists if open
  if (currentAdminTab === 'escalations') renderEscalationQueue();
  if (currentAdminTab === 'dashboard') renderDashboardEscalations();
}
