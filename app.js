// Dimple - Golf Intelligence App
// Fast, modern, retard-proof

const CLUBS = [
  'Driver', '3W', '5W', 'Hybrid',
  '3i', '4i', '5i', '6i', '7i', '8i', '9i',
  'PW', 'GW', 'SW', 'LW', 'Putter'
];

// State
let currentRound = null;
let currentHole = null;
let currentShotNum = null;
let selectedClub = null;
let manualDistance = null;
let modalCallback = null;
let isOnline = true;
let pendingSync = []; // Offline queue

// Initialize
function init() {
  renderClubGrid();
  bindEvents();
  checkConnectivity();
  loadRounds();
}

// Check if backend is reachable
async function checkConnectivity() {
  try {
    const health = await DimpleAPI.checkHealth();
    isOnline = health.status === 'healthy';
    console.log('Backend status:', health.status);
  } catch (err) {
    isOnline = false;
    console.log('Backend unreachable, using localStorage fallback');
  }
}

// Bind events
function bindEvents() {
  document.getElementById('btn-new-round')?.addEventListener('click', startRound);
  document.getElementById('btn-history')?.addEventListener('click', () => showScreen('screen-history'));
  document.getElementById('btn-settings')?.addEventListener('click', () => showScreen('screen-settings'));
}

// Navigation
function showScreen(id) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  
  if (id === 'screen-history') {
    loadRounds();
  }
}

// Club grid
function renderClubGrid() {
  const grid = document.getElementById('club-grid');
  grid.innerHTML = CLUBS.map(club => 
    `<button class="btn-press bg-slate-700 hover:bg-slate-600 py-3 rounded-xl text-sm font-medium transition-colors club-btn" data-club="${club}" onclick="selectClub('${club}')">${club}</button>`
  ).join('');
}

function selectClub(club) {
  selectedClub = club;
  document.querySelectorAll('.club-btn').forEach(btn => {
    btn.classList.toggle('club-selected', btn.dataset.club === club);
    btn.classList.toggle('bg-emerald-500/20', btn.dataset.club === club);
    btn.classList.toggle('text-emerald-300', btn.dataset.club === club);
    btn.classList.toggle('bg-slate-700', btn.dataset.club !== club);
  });
}

// Start round
async function startRound() {
  try {
    if (isOnline) {
      // Create round on backend
      const round = await DimpleAPI.RoundAPI.create();
      currentRound = {
        ...round,
        holes: [],
      };
    } else {
      // Offline fallback
      currentRound = {
        round_id: generateId(),
        round_date: new Date().toISOString().split('T')[0],
        start_time: new Date().toISOString(),
        course: { name: 'Unknown Course', tee_box: 'Unknown' },
        player: { handicap_index: null },
        holes: [],
        _offline: true,
      };
    }
    
    startHole(1);
    showScreen('screen-shot-entry');
  } catch (err) {
    console.error('Failed to start round:', err);
    alert('Failed to start round. Check your connection.');
  }
}

// Start hole
function startHole(holeNum) {
  currentHole = {
    hole_number: holeNum,
    par: 4,
    length_yards: 350,
    handicap_stroke: holeNum,
    shots: []
  };
  currentShotNum = 1;
  manualDistance = null;
  selectedClub = null;
  
  updateDisplay();
  clearClubSelection();
}

function clearClubSelection() {
  document.querySelectorAll('.club-btn').forEach(btn => {
    btn.classList.remove('club-selected', 'bg-emerald-500/20', 'text-emerald-300');
    btn.classList.add('bg-slate-700');
  });
}

// Update display
function updateDisplay() {
  document.getElementById('current-hole').textContent = currentHole.hole_number;
  document.getElementById('current-par').textContent = currentHole.par;
  document.getElementById('current-length').textContent = currentHole.length_yards;
  document.getElementById('current-shot').textContent = currentShotNum;
  document.getElementById('distance-display').textContent = manualDistance || '—';
  
  // Show/hide undo
  const undoBtn = document.getElementById('undo-btn');
  const hasShots = currentHole.shots.length > 0;
  undoBtn.style.opacity = hasShots ? '1' : '0.3';
  undoBtn.style.pointerEvents = hasShots ? 'auto' : 'none';
}

// Distance editing
function editDistance() {
  const current = manualDistance || '';
  const input = prompt('Distance to hole (yards):', current);
  if (input !== null && input.trim() !== '') {
    const yards = parseInt(input);
    if (!isNaN(yards) && yards > 0 && yards <= 700) {
      manualDistance = yards;
      updateDisplay();
    }
  }
}

// Record shot
async function recordResult(result) {
  if (!selectedClub) {
    shakeElement(document.getElementById('club-grid'));
    return;
  }
  
  const shot = {
    shot_number: currentShotNum,
    shot_id: generateId(),
    club: selectedClub,
    distance_to_hole_before: manualDistance,
    distance_to_hole_after: null,
    shot_result: { category: result, lie_quality: null, miss_direction: null },
    gps: { lat: null, lng: null },
    timestamp: new Date().toISOString()
  };
  
  // Capture GPS async (don't block)
  captureGps(shot);
  
  // Save shot
  await saveShot(shot, result);
}

function captureGps(shot) {
  if ('geolocation' in navigator) {
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        shot.gps.lat = pos.coords.latitude;
        shot.gps.lng = pos.coords.longitude;
      },
      () => {},
      { enableHighAccuracy: true, timeout: 3000 }
    );
  }
}

async function saveShot(shot, resultCategory) {
  currentHole.shots.push(shot);
  
  // Update previous shot's after distance
  if (currentShotNum > 1) {
    const prev = currentHole.shots[currentShotNum - 2];
    if (prev) prev.distance_to_hole_after = manualDistance;
  }
  
  // Sync to backend if online
  if (isOnline && currentRound.round_id && !currentRound._offline) {
    try {
      // Ensure hole exists on backend
      const existingHole = currentRound.holes?.find(h => h.hole_number === currentHole.hole_number);
      if (!existingHole) {
        await DimpleAPI.RoundAPI.addHole(currentRound.round_id, {
          hole_number: currentHole.hole_number,
          par: currentHole.par,
          length_yards: currentHole.length_yards,
        });
      }
      
      // Add shot to backend
      await DimpleAPI.RoundAPI.addShot(currentRound.round_id, currentHole.hole_number, {
        shot_number: shot.shot_number,
        club: shot.club,
        distance_to_hole_before: shot.distance_to_hole_before,
        distance_to_hole_after: shot.distance_to_hole_after,
        shot_result: shot.shot_result,
        gps: shot.gps,
      });
    } catch (err) {
      console.error('Failed to sync shot:', err);
      // Queue for later sync
      pendingSync.push({ type: 'shot', roundId: currentRound.round_id, data: shot });
    }
  }
  
  if (resultCategory === 'hole') {
    finishHole();
  } else {
    nextShot();
  }
}

function nextShot() {
  currentShotNum++;
  manualDistance = null;
  selectedClub = null;
  updateDisplay();
  clearClubSelection();
}

async function finishHole() {
  currentRound.holes.push(currentHole);
  
  if (currentHole.hole_number < 18) {
    startHole(currentHole.hole_number + 1);
  } else {
    await finishRound();
  }
}

async function finishRound() {
  currentRound.end_time = new Date().toISOString();
  
  if (isOnline && currentRound.round_id && !currentRound._offline) {
    try {
      await DimpleAPI.RoundAPI.finish(currentRound.round_id);
    } catch (err) {
      console.error('Failed to finish round on backend:', err);
    }
  } else {
    // Save locally
    saveRoundLocal(currentRound);
  }
  
  showModal('Round Complete!', 'Great round! Save it?', () => {
    closeModal();
    showScreen('screen-home');
    loadRounds();
  });
}

// Undo
function undoLastShot() {
  if (currentHole.shots.length === 0) return;
  
  currentHole.shots.pop();
  currentShotNum = Math.max(1, currentShotNum - 1);
  
  // Restore distance from previous shot if available
  const lastShot = currentHole.shots[currentHole.shots.length - 1];
  manualDistance = lastShot ? lastShot.distance_to_hole_after : null;
  
  selectedClub = null;
  updateDisplay();
  clearClubSelection();
}

// End round with confirmation
function confirmEndRound() {
  showModal('End Round?', 'Your progress will be saved.', async () => {
    currentRound.end_time = new Date().toISOString();
    
    if (currentHole.shots.length > 0) {
      currentRound.holes.push(currentHole);
    }
    
    if (isOnline && currentRound.round_id && !currentRound._offline) {
      try {
        await DimpleAPI.RoundAPI.finish(currentRound.round_id);
      } catch (err) {
        console.error('Failed to finish round:', err);
        saveRoundLocal(currentRound);
      }
    } else {
      saveRoundLocal(currentRound);
    }
    
    closeModal();
    showScreen('screen-home');
    loadRounds();
  });
}

// Modal system
function showModal(title, message, onConfirm) {
  document.getElementById('confirm-title').textContent = title;
  document.getElementById('confirm-message').textContent = message;
  modalCallback = onConfirm;
  document.getElementById('confirm-modal').classList.remove('hidden');
}

function closeModal() {
  document.getElementById('confirm-modal').classList.add('hidden');
  modalCallback = null;
}

function modalConfirm() {
  if (modalCallback) modalCallback();
}

// Visual feedback
function shakeElement(el) {
  el.style.transform = 'translateX(-8px)';
  setTimeout(() => el.style.transform = 'translateX(8px)', 50);
  setTimeout(() => el.style.transform = 'translateX(-4px)', 100);
  setTimeout(() => el.style.transform = 'translateX(4px)', 150);
  setTimeout(() => el.style.transform = 'translateX(0)', 200);
}

// LocalStorage fallback (for offline mode)
function saveRoundLocal(round) {
  const rounds = getRoundsLocal();
  rounds.push(round);
  localStorage.setItem('dimple_rounds', JSON.stringify(rounds));
}

function getRoundsLocal() {
  try {
    return JSON.parse(localStorage.getItem('dimple_rounds') || '[]');
  } catch {
    return [];
  }
}

// Load rounds — prefer backend, fallback to localStorage
async function loadRounds() {
  const list = document.getElementById('rounds-list');
  
  if (isOnline) {
    try {
      const rounds = await DimpleAPI.RoundAPI.list();
      renderRoundsList(rounds);
      return;
    } catch (err) {
      console.error('Failed to load from backend:', err);
    }
  }
  
  // Fallback to localStorage
  const rounds = getRoundsLocal();
  renderRoundsListLocal(rounds);
}

function renderRoundsList(rounds) {
  const list = document.getElementById('rounds-list');
  
  if (!rounds || rounds.length === 0) {
    list.innerHTML = '<p class="text-slate-500 text-center mt-20">No rounds yet</p>';
    return;
  }
  
  list.innerHTML = rounds.map(r => `
    <div class="bg-slate-800/50 rounded-xl p-4 mb-3" data-round-id="${r.round_id}">
      <div class="flex justify-between items-start">
        <div>
          <div class="font-semibold">${r.course_name || 'Unknown Course'}</div>
          <div class="text-sm text-slate-400">${r.round_date}</div>
        </div>
        <div class="text-right">
          <div class="text-2xl font-bold text-emerald-400">${r.total_holes || 0}</div>
          <div class="text-xs text-slate-500">holes</div>
        </div>
      </div>
      <div class="text-sm text-slate-500 mt-2">${r.total_shots || 0} shots${r.total_score ? ` • Score: ${r.total_score}` : ''}</div>
    </div>
  `).join('');
}

function renderRoundsListLocal(rounds) {
  const list = document.getElementById('rounds-list');
  
  if (!rounds || rounds.length === 0) {
    list.innerHTML = '<p class="text-slate-500 text-center mt-20">No rounds yet</p>';
    return;
  }
  
  list.innerHTML = rounds.slice().reverse().map(r => {
    const totalShots = r.holes ? r.holes.reduce((sum, h) => sum + (h.shots ? h.shots.length : 0), 0) : 0;
    const totalHoles = r.holes ? r.holes.length : 0;
    return `
      <div class="bg-slate-800/50 rounded-xl p-4 mb-3">
        <div class="flex justify-between items-start">
          <div>
            <div class="font-semibold">${r.course?.name || 'Unknown Course'}</div>
            <div class="text-sm text-slate-400">${r.round_date}</div>
          </div>
          <div class="text-right">
            <div class="text-2xl font-bold text-emerald-400">${totalHoles}</div>
            <div class="text-xs text-slate-500">holes</div>
          </div>
        </div>
        <div class="text-sm text-slate-500 mt-2">${totalShots} shots</div>
      </div>
    `;
  }).join('');
}

// Utilities
function generateId() {
  return Date.now().toString(36) + Math.random().toString(36).substr(2, 5);
}

// Init
init();
