// API Base URL
const API_BASE = '/api';

// Helper to format time in Kuala Lumpur timezone
function formatKLTime(isoString) {
    if (!isoString) return 'N/A';
    try {
        const withTZ = isoString.endsWith('Z') || isoString.includes('+')
            ? isoString
            : isoString + 'Z';
        const d = new Date(withTZ);
        return d.toLocaleString('en-MY', { timeZone: 'Asia/Kuala_Lumpur' });
    } catch (e) {
        console.error('Error formatting time:', e);
        return isoString;
    }
}

// Load all data on page load
document.addEventListener('DOMContentLoaded', () => {
    loadChargerStatus();
    loadSessions();
    loadFaults();
    populateChargerSelects();
    
    // Auto-refresh every 2 seconds for more real-time updates
    setInterval(() => {
        loadChargerStatus();
        loadSessions();
        loadFaults();
    }, 2000);
});

// Populate charger selects
async function populateChargerSelects() {
    try {
        const response = await fetch(`${API_BASE}/chargers`);
        const chargers = await response.json();
        
        const selects = ['chargerFilter', 'meteringCharger', 'deviceCharger'];
        selects.forEach(selectId => {
            const select = document.getElementById(selectId);
            if (!select) return;
            select.innerHTML = selectId === 'chargerFilter' 
                ? '<option value="">All Chargers</option>'
                : '<option value="">Select Charger</option>';
            
            chargers.forEach(charger => {
                const option = document.createElement('option');
                option.value = charger.charge_point_id;
                option.textContent = charger.charge_point_id;
                select.appendChild(option);
            });
        });
    } catch (error) {
        console.error('Error populating charger selects:', error);
    }
}

// Load Charger Status
async function loadChargerStatus() {
    try {
        const response = await fetch(`${API_BASE}/chargers`);
        const chargers = await response.json();
        
        console.log('Loaded chargers from API:', chargers);
        
        const container = document.getElementById('chargerStatusList');
        if (!container) {
            console.error('chargerStatusList container not found!');
            return;
        }
        
        if (chargers.length === 0) {
            container.innerHTML = '<div class="no-data">No chargers registered</div>';
            console.log('No chargers found in database');
            return;
        }
        
        console.log(`Rendering ${chargers.length} charger(s)`);
        
        container.innerHTML = chargers.map(charger => {
            // Heartbeat timeout check
            const now = new Date();
            let lastHeartbeatDate = null;
            let heartbeatMs = null;
            
            if (charger.last_heartbeat) {
                try {
                    let heartbeatStr = charger.last_heartbeat.toString();
                    
                    if (!heartbeatStr.endsWith('Z') && !heartbeatStr.includes('+') && !heartbeatStr.includes('-', 10)) {
                        const match = heartbeatStr.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?/);
                        if (match) {
                            const [, year, month, day, hour, minute, second, millis] = match;
                            const utcTimestamp = Date.UTC(
                                parseInt(year), 
                                parseInt(month) - 1,
                                parseInt(day), 
                                parseInt(hour), 
                                parseInt(minute), 
                                parseInt(second),
                                millis ? parseInt(millis.padEnd(3, '0')) : 0
                            );
                            lastHeartbeatDate = new Date(utcTimestamp);
                        } else {
                            lastHeartbeatDate = new Date(heartbeatStr + 'Z');
                        }
                    } else {
                        lastHeartbeatDate = new Date(heartbeatStr);
                    }
                    
                    heartbeatMs = Date.now() - lastHeartbeatDate.getTime();
                    if (heartbeatMs < 0 || isNaN(heartbeatMs)) {
                        heartbeatMs = null;
                    }
                } catch (e) {
                    console.error('Error parsing heartbeat:', e, charger.last_heartbeat);
                    heartbeatMs = null;
                }
            }

            // Check for active charging session
            const hasActiveSession = charger.active_transaction_id !== null && 
                                     charger.active_transaction_id !== undefined && 
                                     charger.active_transaction_id > 0;
            
            // Database status
            let status = charger.status || 'offline';
            let availability = charger.availability || 'unknown';
            
            if (hasActiveSession) {
                availability = 'charging';
            }

            if (status === 'offline' && !hasActiveSession) {
                if (availability !== 'faulted' && availability !== 'charging') {
                    availability = 'unavailable';
                }
            }

            // Debug logging
            const heartbeatAgeSec = heartbeatMs ? Math.round(heartbeatMs/1000) : 'N/A';
            console.log(`Charger ${charger.charge_point_id}: status=${status}, availability=${availability}, heartbeat=${heartbeatAgeSec}s`);
            
            // Badge classes for new theme
            const statusBadgeClass = status === 'online' ? 'badge-online' : 'badge-offline';
            const availBadgeClass = `badge-${availability}`;
            const itemClass = status === 'offline' ? 'offline' : 
                            availability === 'charging' ? 'charging' :
                            availability === 'faulted' ? 'faulted' : '';
            
            const lastHeartbeat = charger.last_heartbeat 
                ? formatKLTime(charger.last_heartbeat)
                : 'Never';
            
            // Button visibility
            const canStart = status === 'online' && 
                           (availability === 'available' || availability === 'preparing') &&
                           !hasActiveSession;
            const canStop = availability === 'charging' || hasActiveSession;
            
            const statusDisplay = hasActiveSession && status === 'offline' 
                ? 'CHARGING (OFFLINE)' 
                : status.toUpperCase();
            
            return `
                <div class="charger-item ${itemClass}">
                    <div class="charger-header">
                        <span class="charger-id">${charger.charge_point_id}</span>
                        <div class="charger-badges">
                            <span class="badge ${statusBadgeClass}">${statusDisplay}</span>
                            <span class="badge ${availBadgeClass}">${availability.toUpperCase()}</span>
                        </div>
                    </div>
                    <div class="charger-info">
                        <div class="info-item">
                            <span class="info-label">Last Heartbeat</span>
                            <span class="info-value">${lastHeartbeat}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Vendor</span>
                            <span class="info-value">${charger.vendor || 'N/A'}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Model</span>
                            <span class="info-value">${charger.model || 'N/A'}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Firmware</span>
                            <span class="info-value">${charger.firmware_version || 'N/A'}</span>
                        </div>
                    </div>
                    <div class="charger-actions">
                        ${canStart ? `
                            <button class="btn btn-success" onclick="startCharging('${charger.charge_point_id}')">
                                ▶ Start Charging
                            </button>
                        ` : ''}
                        ${canStop ? `
                            <button class="btn btn-danger" onclick="stopCharging('${charger.charge_point_id}', ${charger.active_transaction_id || 'null'})">
                                ⏹ Stop Charging
                            </button>
                        ` : ''}
                    </div>
                </div>
            `;
        }).join('');
    } catch (error) {
        console.error('Error loading charger status:', error);
        document.getElementById('chargerStatusList').innerHTML = 
            '<div class="no-data">Error loading charger status</div>';
    }
}

// Load Charging Sessions
async function loadSessions() {
    try {
        const chargerFilter = document.getElementById('chargerFilter');
        const filterValue = chargerFilter ? chargerFilter.value : '';
        const url = filterValue 
            ? `${API_BASE}/sessions?charge_point_id=${filterValue}`
            : `${API_BASE}/sessions`;
        
        const response = await fetch(url);
        const sessions = await response.json();
        
        const container = document.getElementById('sessionList');
        if (!container) return;
        
        if (sessions.length === 0) {
            container.innerHTML = '<div class="no-data">No charging sessions found</div>';
            return;
        }
        
        container.innerHTML = sessions.map(session => {
            const startTime = formatKLTime(session.start_time);
            const stopTime = session.stop_time 
                ? formatKLTime(session.stop_time)
                : 'Ongoing';
            
            return `
                <div class="session-item">
                    <div class="session-header">
                        <span class="transaction-id">Transaction #${session.transaction_id}</span>
                        <span class="session-status ${session.status}">${session.status.toUpperCase()}</span>
                    </div>
                    <div class="session-details">
                        <div>
                            <strong>Charger:</strong> ${session.charge_point_id}
                        </div>
                        <div>
                            <strong>Start Time:</strong> ${startTime}
                        </div>
                        <div>
                            <strong>Stop Time:</strong> ${stopTime}
                        </div>
                        <div>
                            <strong>Energy Consumed:</strong> ${session.energy_consumed.toFixed(2)} kWh
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    } catch (error) {
        console.error('Error loading sessions:', error);
        const container = document.getElementById('sessionList');
        if (container) {
            container.innerHTML = '<div class="no-data">Error loading sessions</div>';
        }
    }
}

// Load Metering Data
async function loadMetering() {
    const chargePointId = document.getElementById('meteringCharger').value;
    
    if (!chargePointId) {
        document.getElementById('meteringData').innerHTML = 
            '<div class="no-data">Select a charger to view metering data</div>';
        return;
    }

    const container = document.getElementById('meteringData');
    
    try {
        const response = await fetch(`${API_BASE}/metering/${chargePointId}/latest`);

        if (!response.ok) {
            container.innerHTML = '<div class="no-data">No metering data available for this charger</div>';
            return;
        }

        const metering = await response.json();
        const timestamp = metering.timestamp ? formatKLTime(metering.timestamp) : 'N/A';
        
        container.innerHTML = `
            <div class="metering-grid">
                <div class="metering-item">
                    <div class="metering-label">Voltage</div>
                    <div class="metering-value">
                        ${metering.voltage !== null ? metering.voltage.toFixed(1) : 'N/A'}
                        <span class="metering-unit">${metering.voltage !== null ? 'V' : ''}</span>
                    </div>
                </div>
                <div class="metering-item">
                    <div class="metering-label">Current</div>
                    <div class="metering-value">
                        ${metering.current !== null ? metering.current.toFixed(2) : 'N/A'}
                        <span class="metering-unit">${metering.current !== null ? 'A' : ''}</span>
                    </div>
                </div>
                <div class="metering-item">
                    <div class="metering-label">Power</div>
                    <div class="metering-value">
                        ${metering.power !== null ? (metering.power / 1000).toFixed(2) : 'N/A'}
                        <span class="metering-unit">${metering.power !== null ? 'kW' : ''}</span>
                    </div>
                </div>
                <div class="metering-item">
                    <div class="metering-label">Total Energy</div>
                    <div class="metering-value">
                        ${metering.total_kwh !== null ? metering.total_kwh.toFixed(2) : 'N/A'}
                        <span class="metering-unit">${metering.total_kwh !== null ? 'kWh' : ''}</span>
                    </div>
                </div>
            </div>
            <div class="metering-timestamp">Last Update: ${timestamp}</div>
        `;
    } catch (error) {
        console.error('Error loading metering:', error);
        container.innerHTML = '<div class="no-data">No metering data available for this charger</div>';
    }
}

// Load Faults
async function loadFaults() {
    try {
        const showClearedEl = document.getElementById('showCleared');
        const showCleared = showClearedEl ? showClearedEl.checked : false;
        const url = showCleared 
            ? `${API_BASE}/faults`
            : `${API_BASE}/faults?cleared=false`;
        
        const response = await fetch(url);
        const faults = await response.json();
        
        const container = document.getElementById('faultList');
        if (!container) return;
        
        if (faults.length === 0) {
            container.innerHTML = '<div class="no-data">No faults found</div>';
            return;
        }
        
        container.innerHTML = faults.map(fault => {
            const timestamp = formatKLTime(fault.timestamp);
            const faultTypeMap = {
                'overcurrent': 'Overcurrent',
                'ground_fault': 'Ground Fault',
                'emergency_stop': 'Emergency Stop',
                'cp_error': 'CP Error'
            };
            
            const faultTypeName = faultTypeMap[fault.fault_type] || fault.fault_type;
            const clearedClass = fault.cleared ? 'cleared' : '';
            
            return `
                <div class="fault-item ${clearedClass}">
                    <div class="fault-header">
                        <span class="fault-type">${faultTypeName}</span>
                        ${fault.cleared ? '<span class="fault-cleared-badge">CLEARED</span>' : ''}
                    </div>
                    <div class="fault-message">
                        <strong>Charger:</strong> ${fault.charge_point_id}
                    </div>
                    ${fault.message ? `<div class="fault-message">${fault.message}</div>` : ''}
                    <div class="fault-timestamp">${timestamp}</div>
                </div>
            `;
        }).join('');
    } catch (error) {
        console.error('Error loading faults:', error);
        const container = document.getElementById('faultList');
        if (container) {
            container.innerHTML = '<div class="no-data">Error loading faults</div>';
        }
    }
}

// Load Device Info
async function loadDeviceInfo() {
    const chargePointId = document.getElementById('deviceCharger').value;
    
    if (!chargePointId) {
        document.getElementById('deviceInfo').innerHTML = 
            '<div class="no-data">Select a charger to view device information</div>';
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/device/${chargePointId}`);
        const device = await response.json();
        
        const container = document.getElementById('deviceInfo');
        
        container.innerHTML = `
            <div class="device-info-item">
                <span class="device-info-label">Charge Point ID</span>
                <span class="device-info-value">${device.charge_point_id}</span>
            </div>
            <div class="device-info-item">
                <span class="device-info-label">Vendor</span>
                <span class="device-info-value">${device.vendor || 'N/A'}</span>
            </div>
            <div class="device-info-item">
                <span class="device-info-label">Model</span>
                <span class="device-info-value">${device.model || 'N/A'}</span>
            </div>
            <div class="device-info-item">
                <span class="device-info-label">Firmware Version</span>
                <span class="device-info-value">${device.firmware_version || 'N/A'}</span>
            </div>
        `;
    } catch (error) {
        console.error('Error loading device info:', error);
        document.getElementById('deviceInfo').innerHTML = 
            '<div class="no-data">Error loading device information</div>';
    }
}

// Load OCPP Configuration (GetConfiguration)
async function loadConfiguration() {
    const chargePointId = document.getElementById('deviceCharger').value;
    
    if (!chargePointId) {
        document.getElementById('deviceConfig').innerHTML = 
            '<div class="no-data">Select a charger and click "Get Config"</div>';
        return;
    }

    try {
        document.getElementById('deviceConfig').innerHTML =
            '<div class="loading">Requesting configuration from charger...</div>';

        const url = `${API_BASE}/chargers/${encodeURIComponent(chargePointId)}/configuration`;
        const response = await fetch(url);
        if (!response.ok) {
            const text = await response.text();
            console.error('GetConfiguration API error:', response.status, text);
            document.getElementById('deviceConfig').innerHTML =
                `<div class="no-data">Error: ${text || 'Failed to get configuration'}</div>`;
            return;
        }

        const result = await response.json();
        console.log('GetConfiguration result:', result);

        if (!result.success) {
            document.getElementById('deviceConfig').innerHTML =
                `<div class="no-data">${result.message || 'Charger did not return configuration.'}</div>`;
            return;
        }

        if (!result.configuration || result.configuration.length === 0) {
            document.getElementById('deviceConfig').innerHTML =
                '<div class="no-data">No configuration keys returned by charger.</div>';
            return;
        }

        const rows = result.configuration.map(item => {
            const key = item.key || '(unknown)';
            const value = (item.value !== null && item.value !== undefined) ? item.value : '(none)';
            const ro = item.readonly === true ? 'Yes' : (item.readonly === false ? 'No' : 'Unknown');
            return `
                <tr>
                    <td class="config-key">${key}</td>
                    <td>${value}</td>
                    <td>${ro}</td>
                </tr>
            `;
        }).join('');

        document.getElementById('deviceConfig').innerHTML = `
            <div style="margin-bottom: 12px; color: #888;">${result.message || ''}</div>
            <div class="config-table-wrapper">
                <table class="config-table">
                    <thead>
                        <tr>
                            <th>Key</th>
                            <th>Value</th>
                            <th>Read-only</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${rows}
                    </tbody>
                </table>
            </div>
        `;
    } catch (error) {
        console.error('Error getting configuration:', error);
        document.getElementById('deviceConfig').innerHTML =
            `<div class="no-data">Error: ${error.message || 'Failed to get configuration'}</div>`;
    }
}

// Quick helper: set HeartbeatInterval to 10 seconds
async function setFastHeartbeat() {
    const chargePointId = document.getElementById('deviceCharger').value;
    
    if (!chargePointId) {
        alert('Please select a charger first.');
        return;
    }

    if (!confirm(`Set HeartbeatInterval to 10 seconds for charger ${chargePointId}?`)) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/chargers/${encodeURIComponent(chargePointId)}/configuration/change`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                key: 'HeartbeatInterval',
                value: '10',
            }),
        });

        const result = await response.json();
        console.log('ChangeConfiguration HeartbeatInterval result:', result);

        if (result.success) {
            alert(`✅ HeartbeatInterval set to 10 seconds.\n${result.message}`);
            loadConfiguration();
        } else {
            alert(`❌ Failed to change HeartbeatInterval:\n${result.message || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error changing HeartbeatInterval:', error);
        alert(`❌ Error: ${error.message || 'Failed to change HeartbeatInterval'}`);
    }
}

// Generic helper to change a single OCPP configuration key
async function changeChargerConfigKey(chargePointId, key, value) {
    const response = await fetch(`${API_BASE}/chargers/${encodeURIComponent(chargePointId)}/configuration/change`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            key,
            value: String(value),
        }),
    });

    const result = await response.json();
    console.log(`ChangeConfiguration result for ${key}:`, result);
    if (!result.success) {
        throw new Error(result.message || `ChangeConfiguration for ${key} failed`);
    }
    return result;
}

// Apply selected settings (UserPass, BackSelection, StatusLight, BackgroundLight, LogoLight)
async function applySelectedSettings() {
    const chargePointId = document.getElementById('deviceCharger').value;

    if (!chargePointId) {
        alert('Please select a charger first from "Device Information" section.');
        return;
    }

    const userPass = document.getElementById('settingUserPass').value.trim();
    const backSelection = document.getElementById('settingBackSelection').value;
    const statusLight = document.getElementById('settingStatusLight').value;
    const backgroundLight = document.getElementById('settingBackgroundLight').value;
    const logoLight = document.getElementById('settingLogoLight').value;

    const tasks = [];

    if (userPass) {
        tasks.push({ key: 'UserPass', value: userPass });
    }
    if (backSelection) {
        tasks.push({ key: 'BackSelection', value: backSelection });
    }
    if (statusLight) {
        tasks.push({ key: 'StatusLight', value: statusLight });
    }
    if (backgroundLight) {
        tasks.push({ key: 'BackgroundLight', value: backgroundLight });
    }
    if (logoLight) {
        tasks.push({ key: 'LogoLight', value: logoLight });
    }

    if (tasks.length === 0) {
        alert('Please set at least one setting before applying.');
        return;
    }

    const resultDiv = document.getElementById('settingsResult');
    resultDiv.innerHTML = '<span style="color: #ffc800;">Applying settings...</span>';

    let successCount = 0;
    let failCount = 0;
    const errors = [];

    for (const task of tasks) {
        try {
            await changeChargerConfigKey(chargePointId, task.key, task.value);
            successCount += 1;
        } catch (err) {
            failCount += 1;
            errors.push(`${task.key}: ${err.message}`);
        }
    }

    if (failCount === 0) {
        resultDiv.innerHTML = `<span style="color: #00ff88;">✅ All ${successCount} setting(s) applied successfully!</span>`;
    } else {
        resultDiv.innerHTML = `<span style="color: #ff4444;">⚠️ ${successCount} succeeded, ${failCount} failed</span>`;
    }

    // Refresh configuration view
    loadConfiguration();
}

// Start Charging
async function startCharging(chargePointId) {
    if (!confirm(`Start charging for charger ${chargePointId}?`)) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/charging/start`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                charger_id: chargePointId,
                connector_id: 1,
                id_tag: 'DASHBOARD_USER'
            })
        });
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error('API error:', response.status, errorText);
            let errorMsg = 'Unknown error';
            try {
                const errorJson = JSON.parse(errorText);
                errorMsg = errorJson.message || errorJson.detail || errorText;
            } catch {
                errorMsg = errorText || `HTTP ${response.status}`;
            }
            alert(`❌ Failed to start charging:\n${errorMsg}`);
            return;
        }
        
        const result = await response.json();
        
        if (result.success) {
            alert(`✅ Charging started successfully!\n${result.message}`);
            loadChargerStatus();
            loadSessions();
            setTimeout(() => {
                loadChargerStatus();
                loadSessions();
            }, 2000);
        } else {
            alert(`❌ Failed to start charging:\n${result.message || 'Unknown error'}`);
            loadChargerStatus();
        }
    } catch (error) {
        console.error('Error starting charging:', error);
        alert(`❌ Error: ${error.message || 'Failed to start charging. Please check console for details.'}`);
    }
}

// Stop Charging
async function stopCharging(chargePointId) {
    try {
        const sessionsResponse = await fetch(`${API_BASE}/sessions`);
        const sessions = await sessionsResponse.json();
        
        // Find active session for this charger
        const activeSession = sessions.find(session => 
            session.charge_point_id === chargePointId && 
            (session.status === 'active' || session.status === 'pending')
        );

        let transactionId = 0;
        if (activeSession && activeSession.transaction_id) {
            transactionId = activeSession.transaction_id;
        }

        if (!confirm(
            transactionId
                ? `Stop charging for charger ${chargePointId}?\nTransaction ID: ${transactionId}`
                : `No active session found in server.\nSend best-effort stop to charger ${chargePointId}?`
        )) {
            return;
        }
        
        const response = await fetch(`${API_BASE}/charging/stop`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                transaction_id: transactionId,
                charger_id: chargePointId
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert(`✅ Charging stop requested!\n${result.message}`);
            loadChargerStatus();
            loadSessions();
        } else {
            alert(`❌ Failed to stop charging:\n${result.message}`);
        }
    } catch (error) {
        console.error('Error stopping charging:', error);
        alert(`❌ Error: ${error.message}`);
    }
}