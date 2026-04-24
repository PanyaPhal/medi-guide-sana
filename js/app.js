const API_URL = "http://127.0.0.1:5000/api";

/* ============================================================
   MEDIGUIDE 2026 — Application Logic
   ============================================================ */
'use strict';

/* ── App State ─────────────────────────────────────────────── */
const MediGuide = {
  currentScreen: 'home',
  emergencyActive: false,
  currentStep: 0,
  emergencyType: null,
  user: {
    name: 'John Doeun', initials: 'JD', bloodType: 'B+',
    allergies: ['Penicillin', 'Latex'],
    conditions: ['Hypertension'],
    medications: ['Amlodipine 5mg'],
    contacts: [
      { name: 'Sokha Doeun',    relation: 'Spouse',       phone: '+855 12 345 678' },
      { name: 'Dr. Vichet Chan', relation: 'Cardiologist', phone: '+855 23 456 789' }
    ]
  }
};

/* ── Hospitals Data ────────────────────────────────────────── */
const hospitals = [
  {
    id: 'calmette',
    name: 'Calmette Hospital',
    distance: '1.2 km · ~4 min',
    address: 'Monivong Blvd, Phnom Penh',
    status: 'best', statusLabel: 'Best Match',
    tags: ['🟢 ER Open', '🫀 Cardiac', '🩸 Blood Bank'],
    phone: '023 426 948',
    mapsUrl:   'https://maps.google.com/?q=Calmette+Hospital,+Phnom+Penh,+Cambodia',
    mapsQuery: 'Calmette+Hospital,+Phnom+Penh,+Cambodia',
    lat: 11.5638, lng: 104.9238
  },
  {
    id: 'royal',
    name: 'Royal Phnom Penh Hospital',
    distance: '2.1 km · ~7 min',
    address: 'Russian Blvd, Phnom Penh',
    status: 'available', statusLabel: 'Available',
    tags: ['🟢 ER Open', '🏥 General', '💉 ICU'],
    phone: '023 991 000',
    mapsUrl:   'https://maps.google.com/?q=Royal+Phnom+Penh+Hospital,+Cambodia',
    mapsQuery: 'Royal+Phnom+Penh+Hospital,+Cambodia',
    lat: 11.5726, lng: 104.9160
  },
  {
    id: 'sunrise',
    name: 'Sunrise Japan Hospital',
    distance: '3.8 km · ~12 min',
    address: 'Mao Tse Tung Blvd, Phnom Penh',
    status: 'busy', statusLabel: 'Busy',
    tags: ['🔴 High Load', '💉 ICU'],
    phone: '023 999 111',
    mapsUrl:   'https://maps.google.com/?q=Sunrise+Japan+Hospital,+Phnom+Penh,+Cambodia',
    mapsQuery: 'Sunrise+Japan+Hospital,+Phnom+Penh,+Cambodia',
    lat: 11.5549, lng: 104.9282
  },
  {
    id: 'khmer-soviet',
    name: 'Khmer Soviet Friendship Hospital',
    distance: '4.5 km · ~15 min',
    address: 'Confederation de la Russie Blvd, Phnom Penh',
    status: 'available', statusLabel: 'Available',
    tags: ['🟢 ER Open', '🏥 General'],
    phone: '023 883 712',
    mapsUrl:   'https://maps.google.com/?q=Khmer+Soviet+Friendship+Hospital,+Phnom+Penh,+Cambodia',
    mapsQuery: 'Khmer+Soviet+Friendship+Hospital,+Phnom+Penh,+Cambodia',
    lat: 11.5800, lng: 104.9100
  }
];

/* ── Emergency Protocols ───────────────────────────────────── */
const protocols = {
  cpr: {
    title: 'CPR', icon: '🫀',
    steps: [
      { text: 'Check responsiveness — tap their shoulder firmly and shout "Are you okay?"', duration: 5 },
      { text: 'Call 119 immediately or ask a bystander to call. Lay the person flat on their back on a firm surface.', duration: 6 },
      { text: 'Tilt the head back, lift the chin to open the airway. Check for breathing — no more than 10 seconds.', duration: 6 },
      { text: 'Place the heel of your hand in the center of the chest. Push hard and fast — 100–120 compressions/min, 5–6 cm deep.', duration: 8 },
      { text: 'Every 30 compressions: give 2 rescue breaths. Pinch nose shut, seal mouth, breathe until chest rises.', duration: 7 },
      { text: 'Continue the 30:2 cycle without stopping until emergency services arrive or an AED becomes available.', duration: 8 }
    ]
  },
  choking: {
    title: 'Choking', icon: '🍬',
    steps: [
      { text: '"Are you choking?" — if they cannot speak, cough, or breathe, act immediately.', duration: 4 },
      { text: 'Stand behind the person. Make a fist just above the belly button, below the ribcage.', duration: 5 },
      { text: 'Grab your fist with the other hand and give up to 5 quick, sharp upward thrusts.', duration: 6 },
      { text: 'Alternate: 5 firm back blows between the shoulder blades, then 5 abdominal thrusts.', duration: 6 },
      { text: 'Repeat until the object is expelled. If the person loses consciousness, begin CPR immediately.', duration: 6 }
    ]
  },
  bleeding: {
    title: 'Bleeding', icon: '🩸',
    steps: [
      { text: 'Put on gloves if available. Apply direct, firm pressure to the wound with a clean cloth or bandage.', duration: 5 },
      { text: 'Do not lift the cloth to check. If blood soaks through, add more material directly on top.', duration: 6 },
      { text: 'For severe limb bleeding, apply a tourniquet 5–8 cm above the wound and note the time.', duration: 6 },
      { text: 'Elevate the injured area above heart level to help reduce blood flow.', duration: 5 },
      { text: 'Keep the person warm and calm. Watch for shock signs: pale skin, rapid breathing, confusion. Call 119.', duration: 6 }
    ]
  },
  stroke: {
    title: 'Stroke (FAST)', icon: '🧠',
    steps: [
      { text: 'F — Face: Ask them to smile. Is one side drooping?', duration: 5 },
      { text: 'A — Arms: Ask them to raise both arms. Does one drift down?', duration: 5 },
      { text: 'S — Speech: Ask them to repeat a simple phrase. Is it slurred or unclear?', duration: 5 },
      { text: 'T — Time: If you see ANY sign, call 119 immediately. Note the exact time symptoms began.', duration: 6 },
      { text: 'Do not give food, drink, or medication. Keep them calm, on their side. Do not leave them alone.', duration: 6 }
    ]
  }
};

/* ── Google Maps ───────────────────────────────────────────── */
function openMaps(hospitalId) {
  const h = hospitals.find(x => x.id === hospitalId);
  if (!h) return;

  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        const url = `https://www.google.com/maps/dir/${coords.latitude},${coords.longitude}/${h.mapsQuery}`;
        window.open(url, '_blank');
      },
      () => window.open(h.mapsUrl, '_blank'),
      { timeout: 4000 }
    );
  } else {
    window.open(h.mapsUrl, '_blank');
  }
}

/* ── Render Hospitals ──────────────────────────────────────── */
/* -- Render Hospitals (calls Python hospital_map.py API) -- */
async function renderHospitals() {
  const container = document.getElementById('hospital-list');
  if (!container) return;

  container.innerHTML = '<p style="color:var(--text-2);padding:16px;">Loading hospitals...</p>';

  let lat = 11.5564, lng = 104.9282;
  if (navigator.geolocation) {
    try {
      const pos = await new Promise((res, rej) =>
        navigator.geolocation.getCurrentPosition(res, rej, { timeout: 4000 })
      );
      lat = pos.coords.latitude;
      lng = pos.coords.longitude;
    } catch (e) { /* use default Phnom Penh coords */ }
  }

  let hospData = hospitals;  // fallback to local data
  try {
    const res = await fetch(
      'http://localhost:5002/api/hospitals/nearest?lat=' + lat + '&lng=' + lng + '&k=5'
    );
    hospData = await res.json();
  } catch (err) {
    console.warn('[MediGuide] Map API unavailable, using local data');
  }

  const badgeClass = { best:'badge-teal', available:'badge-sky', busy:'badge-coral' };
  container.innerHTML = hospData.map(h => `
    <div class="hosp-card ${h.status === 'best' ? 'best' : ''}">
      <div class="flex-between mb-12">
        <div style="flex:1;min-width:0;">
          <div class="hosp-name">${h.name}</div>
          <div class="hosp-dist">
            ${h.distance_km ? h.distance_km + ' km · ~' + h.eta_min + ' min' : h.distance}
          </div>
          <div class="hosp-addr">${h.address}</div>
          ${h.score ? '<div style="font-size:11px;color:var(--teal);margin-top:2px;">ML Score: ' + (h.score * 100).toFixed(0) + '%</div>' : ''}
        </div>
        <span class="badge ${badgeClass[h.status] || 'badge-sky'}">${h.statusLabel || h.status}</span>
      </div>
      <div class="hosp-tags">
        ${(h.tags||[]).map(tag => '<span class="badge badge-ghost text-xs">' + tag + '</span>').join('')}
      </div>
      <div class="hosp-actions">
        <button class="btn-maps" onclick="openMaps('${h.id}')">Open in Google Maps</button>
        <button class="btn-call" onclick="showCalling('${h.phone}','${h.name}')">${h.phone}</button>
      </div>
    </div>
  `).join('');
}

/* ── Screen Navigation ─────────────────────────────────────── */
function showScreen(id) {
  document.querySelectorAll('.screen').forEach(s => {
    s.classList.remove('active');
    s.style.display = 'none';
  });
  const target = document.getElementById(id);
  if (target) {
    target.style.display = 'flex';
    requestAnimationFrame(() => target.classList.add('active'));
    MediGuide.currentScreen = id;
  }
  document.querySelectorAll('[data-screen]').forEach(a => {
    a.classList.toggle('active', a.dataset.screen === id);
  });
  // close mobile drawer
  const drawer = document.getElementById('nav-drawer');
  if (drawer) drawer.classList.remove('open');
}

/* ── Emergency ─────────────────────────────────────────────── */
function activateEmergency(type = 'cpr') {
  MediGuide.emergencyActive = true;
  MediGuide.emergencyType   = type;
  MediGuide.currentStep     = 0;
  const protocol = protocols[type];
  if (!protocol) return;
  showScreen('emergency');
  const titleEl = document.getElementById('emg-title');
  const typeEl  = document.getElementById('emg-type');
  if (titleEl) titleEl.textContent = '🚨 EMERGENCY ACTIVE';
  if (typeEl)  typeEl.textContent  = protocol.icon + ' ' + protocol.title + ' — Voice Guided';
  renderSteps(protocol);
  notifyContacts();
}

function renderSteps(protocol) {
  const c = document.getElementById('step-list');
  if (!c) return;
  c.innerHTML = '';
  protocol.steps.forEach((step, i) => {
    const div = document.createElement('div');
    div.className = 'step-item' + (i === 0 ? ' active-step' : '');
    div.id = 'step-' + i;
    div.innerHTML = `
      <div class="step-num">${i + 1}</div>
      <div class="step-text">${step.text}
        ${i === 0 ? `<div class="progress-bar mt-12"><div class="progress-fill" style="animation-duration:${step.duration}s"></div></div>` : ''}
      </div>`;
    c.appendChild(div);
  });
}

function nextStep() {
  if (!MediGuide.emergencyType) return;
  const steps = protocols[MediGuide.emergencyType].steps;
  document.getElementById('step-' + MediGuide.currentStep)?.classList.remove('active-step');
  MediGuide.currentStep = Math.min(MediGuide.currentStep + 1, steps.length - 1);
  const curr = document.getElementById('step-' + MediGuide.currentStep);
  if (curr) {
    curr.classList.add('active-step');
    const stepData = steps[MediGuide.currentStep];
    const textEl = curr.querySelector('.step-text');
    if (textEl) textEl.innerHTML = stepData.text + `<div class="progress-bar mt-12"><div class="progress-fill" style="animation-duration:${stepData.duration}s"></div></div>`;
    curr.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}

function prevStep() {
  if (MediGuide.currentStep === 0) return;
  const steps = protocols[MediGuide.emergencyType].steps;
  const prev = document.getElementById('step-' + MediGuide.currentStep);
  if (prev) {
    prev.classList.remove('active-step');
    prev.querySelector('.step-text').textContent = steps[MediGuide.currentStep].text;
  }
  MediGuide.currentStep--;
  const curr = document.getElementById('step-' + MediGuide.currentStep);
  if (curr) {
    curr.classList.add('active-step');
    const stepData = steps[MediGuide.currentStep];
    curr.querySelector('.step-text').innerHTML = stepData.text + `<div class="progress-bar mt-12"><div class="progress-fill" style="animation-duration:${stepData.duration}s"></div></div>`;
  }
}

function endEmergency() {
  if (!confirm('End emergency session?')) return;
  MediGuide.emergencyActive = false;
  MediGuide.emergencyType   = null;
  MediGuide.currentStep     = 0;
  showScreen('home');
}

/* ── Calling Overlay ───────────────────────────────────────── */
function showCalling(number = '119', label = 'Cambodia Emergency Services') {
  const overlay = document.getElementById('calling-overlay');
  if (!overlay) return;
  document.getElementById('call-number').textContent = 'Calling ' + number;
  document.getElementById('call-label').textContent  = label;
  overlay.classList.add('show');
  setTimeout(hideCalling, 5000);
}
function hideCalling() {
  document.getElementById('calling-overlay')?.classList.remove('show');
}

/* ── Notify Contacts ───────────────────────────────────────── */
/* -- Notify Contacts (calls Python emergency_alerts.py API) -- */
async function notifyContacts() {
  const banner = document.getElementById('alert-banner');
  if (banner) banner.classList.remove('hidden');

  let location = 'Phnom Penh, Cambodia';
  if (navigator.geolocation) {
    try {
      const pos = await new Promise((res, rej) =>
        navigator.geolocation.getCurrentPosition(res, rej, { timeout: 4000 })
      );
      location = pos.coords.latitude + ', ' + pos.coords.longitude;
    } catch (e) { /* use default */ }
  }

  try {
    const res = await fetch('http://localhost:5001/api/alerts/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        situation: MediGuide.emergencyType || 'Medical Emergency',
        location:  location
      })
    });
    const data = await res.json();
    console.log('[MediGuide] Alerts sent:', data.alerts_sent);
    if (banner) {
      banner.querySelector('span:last-child').textContent =
        data.alerts_sent + ' contacts notified · GPS shared';
    }
  } catch (err) {
    console.warn('[MediGuide] Alert API unavailable, using offline mode');
  }

  if (banner) setTimeout(() => banner.classList.add('hidden'), 5000);
}


/* ── Mobile Nav ────────────────────────────────────────────── */
function toggleMobileNav() {
  document.getElementById('nav-drawer')?.classList.toggle('open');
}

/* ── Voice hint ────────────────────────────────────────────── */
function setupVoiceHint() {
  const hint = document.getElementById('voice-hint');
  if (!hint) return;
  // CSS handles animation; no JS needed — placeholder for future TTS
}

/* ── Survey Form ───────────────────────────────────────────── */
function setupSurveyForm() {
  const form = document.getElementById('survey-form');
  if (!form) return;
  form.addEventListener('submit', e => {
    e.preventDefault();
    const result = Object.fromEntries(new FormData(form).entries());
    const confirm = document.getElementById('form-confirm');
    if (confirm) {
      confirm.classList.remove('hidden');
      form.style.opacity = '0.35';
      form.style.pointerEvents = 'none';
      setTimeout(() => {
        confirm.classList.add('hidden');
        form.reset();
        form.style.opacity = '1';
        form.style.pointerEvents = '';
        document.querySelectorAll('.star').forEach(s => s.classList.remove('selected', 'hover'));
      }, 4500);
    }
    console.log('Survey:', result);
  });
}

/* ── Star Rating ───────────────────────────────────────────── */
function setupStarRating() {
  document.querySelectorAll('.star-group').forEach(group => {
    const stars = group.querySelectorAll('.star');
    stars.forEach((star, i) => {
      star.addEventListener('click', () => {
        stars.forEach((s, j) => s.classList.toggle('selected', j <= i));
        const inp = group.querySelector('input[type=hidden]');
        if (inp) inp.value = i + 1;
      });
      star.addEventListener('mouseenter', () => stars.forEach((s,j) => s.classList.toggle('hover', j <= i)));
      star.addEventListener('mouseleave', () => stars.forEach(s => s.classList.remove('hover')));
    });
  });
}

/* ── Init ──────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  renderHospitals();
  setupVoiceHint();
  setupSurveyForm();
  setupStarRating();

  // [data-screen] links
  document.querySelectorAll('[data-screen]').forEach(el => {
    el.addEventListener('click', e => { e.preventDefault(); showScreen(el.dataset.screen); });
  });

  showScreen('home');
});

async function openBookingPortal() {
  const response = await fetch(`${API_URL}/doctors`);
  const doctors = await response.json();
  
  let selection = prompt(
    "Available Doctors:\n" + 
    doctors.map(d => `${d.id}: ${d.name} (${d.specialty})`).join('\n') +
    "\n\nEnter Doctor ID to book:"
  );

  if (selection) {
    const bookRes = await fetch(`${API_URL}/book-appointment`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ doctorId: selection, time: "2026-04-10 10:00 AM" })
    });
    const data = await bookRes.json();
    alert(`Booking ${data.status}! Ref: ${data.booking_ref}`);
  }
}

async function getSmartNearestHospital() {
    const response = await fetch(`${API_URL}/find-nearest`);
    const data = await response.json();
    alert("Python Recommendation: " + data.name);
    openMaps(data.id);
}