// Dimple API Client
// Handles all communication with the FastAPI backend

const API_BASE_URL = window.location.hostname === 'localhost' 
    ? 'http://localhost:8000'  // Development
    : 'https://your-production-api.com';  // Production

// Simple auth — stores user_id as token
// In production, replace with proper JWT from Supabase Auth
const AUTH_KEY = 'dimple_auth';

function getAuthToken() {
    return localStorage.getItem(AUTH_KEY);
}

function setAuthToken(userId) {
    localStorage.setItem(AUTH_KEY, userId);
}

function getUserId() {
    // For now, token IS the user_id
    // In production, decode JWT here
    return getAuthToken();
}

function ensureAuth() {
    let userId = getUserId();
    if (!userId) {
        // Generate a simple user ID for now
        userId = 'user_' + Date.now().toString(36) + Math.random().toString(36).substr(2, 5);
        setAuthToken(userId);
    }
    return userId;
}

// HTTP client
async function apiRequest(method, path, body = null) {
    const userId = ensureAuth();
    const url = `${API_BASE_URL}${path}`;
    
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${userId}`,
        },
    };
    
    if (body) {
        options.body = JSON.stringify(body);
    }
    
    try {
        const response = await fetch(url, options);
        
        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
            throw new Error(error.detail || `HTTP ${response.status}`);
        }
        
        // 204 No Content
        if (response.status === 204) {
            return null;
        }
        
        return await response.json();
    } catch (err) {
        console.error('API Error:', err);
        throw err;
    }
}

// Round API
const RoundAPI = {
    // Start a new round
    async create(course = null, player = null) {
        return apiRequest('POST', '/rounds', {
            course: course || { name: 'Unknown Course' },
            player: player || {},
        });
    },
    
    // Get all rounds (summaries)
    async list(limit = 50) {
        return apiRequest('GET', `/rounds?limit=${limit}`);
    },
    
    // Get full round details
    async get(roundId) {
        return apiRequest('GET', `/rounds/${roundId}`);
    },
    
    // Update round metadata
    async update(roundId, updates) {
        return apiRequest('PATCH', `/rounds/${roundId}`, updates);
    },
    
    // Delete round
    async delete(roundId) {
        return apiRequest('DELETE', `/rounds/${roundId}`);
    },
    
    // Add a hole to a round
    async addHole(roundId, holeData) {
        return apiRequest('POST', `/rounds/${roundId}/holes`, holeData);
    },
    
    // Add a shot to a hole
    async addShot(roundId, holeNumber, shotData) {
        return apiRequest('POST', `/rounds/${roundId}/holes/${holeNumber}/shots`, shotData);
    },
    
    // Finish round
    async finish(roundId) {
        return apiRequest('POST', `/rounds/${roundId}/finish`);
    },
};

// Health check
async function checkHealth() {
    try {
        const response = await fetch(`${API_BASE_URL}/health`);
        return await response.json();
    } catch (err) {
        return { status: 'unreachable', error: err.message };
    }
}

// Export for use in app.js
window.DimpleAPI = {
    RoundAPI,
    checkHealth,
    getUserId,
    ensureAuth,
};
