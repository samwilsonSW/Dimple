// Dimple - Golf Intelligence App
// Local-first, PWA, offline-capable

const CLUBS = [
  'Driver', '3W', '5W', 'Hybrid',
  '2i', '3i', '4i', '5i', '6i', '7i', '8i', '9i',
  'PW', 'GW', 'SW', 'LW', 'Putter'
];

const RESULTS = {
  fairway: 'Fairway',
  rough: 'Rough',
  green: 'Green',
  sand: 'Bunker',
  hole: 'In Hole',
  penalty: 'Penalty'
};

// State
let currentRound = null;
let currentHole = null;
let currentShot = null;
let watchId = null;

// Initialize
function init() {
  renderClubGrid();
  loadRounds();
}

// Navigation
function showScreen(id) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.getElementById(id).classList.add('active');
}

// Club grid rendering
function renderClubGrid() {
  const grid = document.getElementById('club-grid');
  grid.innerHTML = CLUBS.map(club => 
    `<button class="btn" onclick="selectClub('${club}')">${club}</button>`
  ).join('');
}

// Start new round
function startRound() {
  const roundId = generateId();
  currentRound = {
    round_id: roundId,
    round_date: new Date().toISOString().split('T')[0],
    start_time: new Date().toISOString(),
    course: {
      name: 'Unknown Course',
      tee_box: 'Unknown'
    },
    player: {
      handicap_index: null
    },
    holes: []
  };
  
  startHole(1);
  showScreen('screen-shot-entry');
}

// Start a hole
function startHole(holeNum) {
  currentHole = {
    hole_number: holeNum,
    par: 4, // Default, should be configurable per course
    length_yards: 350, // Default
    handicap_stroke: holeNum, // Simplified
    shots: []
  };
  currentShot = 1;
  manualDistanceSet = false;
  
  updateHoleDisplay();
  startGpsWatch();
}

// Update hole display
function updateHoleDisplay() {
  document.getElementById('current-hole').textContent = currentHole.hole_number;
  document.getElementById('current-par').textContent = currentHole.par;
  document.getElementById('current-length').textContent = currentHole.length_yards;
  document.getElementById('current-shot').textContent = currentShot;
}

// GPS handling
function startGpsWatch() {
  if (watchId) navigator.geolocation.clearWatch(watchId);
  
  if ('geolocation' in navigator) {
    watchId = navigator.geolocation.watchPosition(
      (pos) => {
        const dist = estimateDistanceToHole(pos.coords);
        if (dist && !manualDistanceSet) {
          document.getElementById('distance-display').textContent = dist;
        }
      },
      (err) => {
        console.log('GPS not available (expected on desktop):', err.message);
        // Keep showing manual entry or '—'
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 30000 }
    );
  } else {
    console.log('Geolocation not supported');
  }
}

let manualDistanceSet = false;

function editDistance() {
  const current = document.getElementById('distance-display').textContent;
  const input = prompt('Distance to hole (yards):', current === '—' ? '' : current);
  if (input !== null && input.trim() !== '') {
    const yards = parseInt(input);
    if (!isNaN(yards) && yards > 0) {
      document.getElementById('distance-display').textContent = yards;
      manualDistanceSet = true;
    }
  }
}

// Rough distance estimate (would need course data for accuracy)
function estimateDistanceToHole(coords) {
  // Placeholder: would calculate against known hole locations
  // For now, return null to indicate manual entry needed
  return null;
}

// Club selection
function selectClub(club) {
  currentShotData = currentShotData || {};
  currentShotData.club = club;
}

// Record shot result
function recordResult(result) {
  if (!currentShotData || !currentShotData.club) {
    alert('Select a club first');
    return;
  }
  
  const shot = {
    shot_number: currentShot,
    shot_id: generateId(),
    club: currentShotData.club,
    distance_to_hole_before: parseDistance(document.getElementById('distance-display').textContent),
    distance_to_hole_after: null, // Will be updated on next shot or manual entry
    shot_result: {
      category: result,
      lie_quality: null,
      miss_direction: null
    },
    gps: {
      lat: null,
      lng: null
    },
    timestamp: new Date().toISOString()
  };
  
  // Try to capture GPS
  if ('geolocation' in navigator) {
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        shot.gps.lat = pos.coords.latitude;
        shot.gps.lng = pos.coords.longitude;
        saveShot(shot);
      },
      () => saveShot(shot),
      { enableHighAccuracy: true, timeout: 5000 }
    );
  } else {
    saveShot(shot);
  }
}

let currentShotData = null;

function saveShot(shot) {
  currentHole.shots.push(shot);
  
  // Update previous shot's "after" distance if available
  if (currentShot > 1 && shot.distance_to_hole_before) {
    const prevShot = currentHole.shots[currentShot - 2];
    if (prevShot) {
      prevShot.distance_to_hole_after = shot.distance_to_hole_before;
    }
  }
  
  // Check if holed
  if (shot.shot_result.category === 'hole') {
    finishHole();
  } else {
    currentShot++;
    currentShotData = null;
    updateHoleDisplay();
  }
}

function finishHole() {
  currentRound.holes.push(currentHole);
  
  // Auto-advance or finish
  if (currentHole.hole_number < 18) {
    startHole(currentHole.hole_number + 1);
  } else {
    finishRound();
  }
}

function finishRound() {
  currentRound.end_time = new Date().toISOString();
  saveRound(currentRound);
  
  if (watchId) navigator.geolocation.clearWatch(watchId);
  
  alert('Round complete!');
  showScreen('screen-home');
}

// Storage
function saveRound(round) {
  const rounds = getRounds();
  rounds.push(round);
  localStorage.setItem('dimple_rounds', JSON.stringify(rounds));
}

function getRounds() {
  try {
    return JSON.parse(localStorage.getItem('dimple_rounds') || '[]');
  } catch {
    return [];
  }
}

function loadRounds() {
  const rounds = getRounds();
  const list = document.getElementById('rounds-list');
  
  if (rounds.length === 0) {
    list.innerHTML = '<p style="text-align: center; opacity: 0.6; margin-top: 40px;">No rounds yet</p>';
    return;
  }
  
  list.innerHTML = rounds.map(r => `
    <div style="background: #1a5f2a; padding: 12px; border-radius: 8px; margin-bottom: 8px;">
      <div style="font-weight: 600;">${r.course.name}</div>
      <div style="font-size: 0.875rem; opacity: 0.8;">${r.round_date} • ${r.holes.length} holes</div>
    </div>
  `).join('');
}

// Utilities
function generateId() {
  return Date.now().toString(36) + Math.random().toString(36).substr(2);
}

function parseDistance(val) {
  const num = parseInt(val);
  return isNaN(num) ? null : num;
}

// Init on load
init();
