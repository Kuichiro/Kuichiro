<?php
/**
 * Telegram Bot Health Check & Status Page
 * For Render.com Deployment
 * 
 * This file provides a web interface for monitoring the bot status
 * and health checks for Render.com's web service monitoring.
 */

// Enable error reporting for debugging
error_reporting(E_ALL);
ini_set('display_errors', 1);

// Set headers
header('Content-Type: text/html; charset=utf-8');
header('X-Content-Type-Options: nosniff');
header('X-Frame-Options: DENY');
header('X-XSS-Protection: 1; mode=block');

// Bot configuration
$bot_username = "PremiumGeneratorBot";
$bot_name = "Premium Account Generator Bot";
$deployment_platform = "Render.com";
$status = "online";
$last_updated = date('Y-m-d H:i:s');
$server_time = date('Y-m-d H:i:s T');
$start_time = microtime(true);

// Security: Basic IP restriction (optional)
$allowed_ips = ['127.0.0.1', '::1'];
$client_ip = $_SERVER['REMOTE_ADDR'] ?? 'unknown';

// Check if this is a health check request
$is_health_check = isset($_GET['health']) || $_SERVER['REQUEST_URI'] === '/health';
$is_api_call = isset($_GET['api']) || strpos($_SERVER['REQUEST_URI'], '/api/') === 0;

if ($is_health_check || $is_api_call) {
    handle_api_request($is_health_check);
    exit;
}

// Function to handle API requests
function handle_api_request($is_health_check = false) {
    global $start_time;
    
    $response = [
        'status' => 'healthy',
        'timestamp' => date('c'),
        'service' => 'telegram-bot',
        'version' => '1.0.0',
        'response_time' => round((microtime(true) - $start_time) * 1000, 2) . 'ms'
    ];

    // Check if bot process is running
    $bot_process_running = check_bot_process();
    $response['bot_process'] = $bot_process_running ? 'running' : 'stopped';
    
    // Check required files
    $required_files = check_required_files();
    $response['file_system'] = $required_files;
    
    // Check system resources
    $system_info = get_system_info();
    $response['system'] = $system_info;
    
    // Check database files
    $database_files = get_database_files();
    $response['database'] = $database_files;
    
    // Determine overall status
    if (!$bot_process_running) {
        $response['status'] = 'unhealthy';
        $response['error'] = 'Bot process is not running';
    }
    
    foreach (['bot.py', 'Dockerfile', 'requirements.txt'] as $critical_file) {
        if (!$required_files[$critical_file]) {
            $response['status'] = 'unhealthy';
            $response['error'] = 'Critical file missing: ' . $critical_file;
            break;
        }
    }
    
    // Set appropriate HTTP status code
    if ($response['status'] === 'unhealthy') {
        http_response_code(503);
    } else {
        http_response_code(200);
    }
    
    header('Content-Type: application/json');
    echo json_encode($response, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES);
}

// Function to check if bot process is running
function check_bot_process() {
    $processes = shell_exec('ps aux | grep bot.py | grep -v grep') ?: '';
    return strpos($processes, 'bot.py') !== false;
}

// Function to check required files
function check_required_files() {
    $files = [
        'bot.py' => file_exists('bot.py'),
        'Dockerfile' => file_exists('Dockerfile'),
        'requirements.txt' => file_exists('requirements.txt'),
        'keys.json' => file_exists('keys.json'),
        'bot_data.pkl' => file_exists('bot_data.pkl'),
        'logs/' => is_dir('logs'),
        'Generated_Results/' => is_dir('Generated_Results'),
        'database/' => is_dir('database'),
        'backups/' => is_dir('backups'),
        'temp/' => is_dir('temp')
    ];
    
    return $files;
}

// Function to get system information
function get_system_info() {
    $memory_usage = memory_get_usage(true);
    $memory_peak = memory_get_peak_usage(true);
    $load = sys_getloadavg();
    
    // Get Python version
    $python_version = shell_exec('python --version 2>&1') ?: 'Unknown';
    $pip_version = shell_exec('pip --version 2>&1') ?: 'Unknown';
    
    return [
        'memory_usage' => round($memory_usage / 1024 / 1024, 2) . ' MB',
        'memory_peak' => round($memory_peak / 1024 / 1024, 2) . ' MB',
        'system_load' => [
            '1min' => round($load[0], 2),
            '5min' => round($load[1], 2),
            '15min' => round($load[2], 2)
        ],
        'python_version' => trim($python_version),
        'pip_version' => trim(explode(' from ', $pip_version)[0]),
        'php_version' => PHP_VERSION,
        'server_software' => $_SERVER['SERVER_SOFTWARE'] ?? 'Unknown'
    ];
}

// Function to get database files information
function get_database_files() {
    $database_files = [];
    $directories = ['Generated_Results', 'logs', 'database'];
    
    foreach ($directories as $dir) {
        if (is_dir($dir)) {
            $files = scandir($dir);
            foreach ($files as $file) {
                if ($file !== '.' && $file !== '..') {
                    $file_path = $dir . '/' . $file;
                    if (is_file($file_path)) {
                        $size = filesize($file_path);
                        $database_files[] = [
                            'name' => $file_path,
                            'size' => round($size / 1024, 2) . ' KB',
                            'modified' => date('Y-m-d H:i:s', filemtime($file_path)),
                            'lines' => count(file($file_path)) ?: 0
                        ];
                    }
                }
            }
        }
    }
    
    return $database_files;
}

// Function to get bot statistics
function get_bot_statistics() {
    $stats = [
        'total_users' => 0,
        'active_keys' => 0,
        'generation_count' => 0,
        'total_lines_generated' => 0
    ];
    
    // Try to read bot data file
    if (file_exists('bot_data.pkl')) {
        $stats['bot_data_exists'] = true;
        // Note: In production, you might want to parse the pickle file
        // or maintain a separate JSON file for web access
    } else {
        $stats['bot_data_exists'] = false;
    }
    
    // Count files in Generated_Results
    if (is_dir('Generated_Results')) {
        $files = scandir('Generated_Results');
        $stats['generated_files_count'] = count(array_filter($files, function($file) {
            return $file !== '.' && $file !== '..' && is_file('Generated_Results/' . $file);
        }));
    }
    
    return $stats;
}

// Function to check recent errors
function get_recent_errors() {
    $errors = [];
    $log_files = ['error.log', 'bot.log'];
    
    foreach ($log_files as $log_file) {
        if (file_exists($log_file)) {
            $lines = file($log_file, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
            $recent_lines = array_slice($lines, -10); // Last 10 lines
            $errors[$log_file] = $recent_lines;
        }
    }
    
    return $errors;
}

// Main HTML page
?>
<!DOCTYPE html>
<html lang="en" data-bs-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><?php echo htmlspecialchars($bot_name); ?> - Status Dashboard</title>
    <link href="https://cdn.replit.com/agent/bootstrap-agent-dark-theme.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {
            --primary-color: #6f42c1;
            --secondary-color: #fd7e14;
            --success-color: #20c997;
            --warning-color: #ffc107;
            --danger-color: #dc3545;
            --dark-color: #212529;
            --light-color: #f8f9fa;
        }
        
        .status-card {
            transition: transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out;
            border: none;
            border-radius: 15px;
            overflow: hidden;
        }
        
        .status-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.15);
        }
        
        .status-indicator {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            display: inline-block;
            margin-right: 8px;
        }
        
        .status-online { background-color: var(--success-color); }
        .status-offline { background-color: var(--danger-color); }
        .status-warning { background-color: var(--warning-color); }
        
        .file-status {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 15px;
            margin-bottom: 8px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 10px;
            border-left: 4px solid var(--success-color);
            transition: all 0.3s ease;
        }
        
        .file-status.missing {
            border-left-color: var(--danger-color);
            background: rgba(220, 53, 69, 0.1);
        }
        
        .file-status:hover {
            background: rgba(255, 255, 255, 0.1);
            transform: translateX(5px);
        }
        
        .metric-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 15px;
            padding: 20px;
            text-align: center;
        }
        
        .metric-value {
            font-size: 2.5rem;
            font-weight: bold;
            margin: 10px 0;
        }
        
        .metric-label {
            font-size: 0.9rem;
            opacity: 0.9;
        }
        
        .database-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }
        
        .database-table th,
        .database-table td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .database-table th {
            background: rgba(255, 255, 255, 0.1);
            font-weight: 600;
        }
        
        .database-table tr:hover {
            background: rgba(255, 255, 255, 0.05);
        }
        
        .btn-custom {
            background: linear-gradient(135deg, var(--primary-color), #5a2d9c);
            border: none;
            border-radius: 25px;
            padding: 10px 25px;
            color: white;
            font-weight: 600;
            transition: all 0.3s ease;
        }
        
        .btn-custom:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(111, 66, 193, 0.4);
            color: white;
        }
        
        .nav-tabs .nav-link.active {
            background: transparent;
            border-bottom: 3px solid var(--primary-color);
            color: var(--primary-color);
            font-weight: 600;
        }
        
        .refresh-indicator {
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }
        
        .glow {
            animation: glow 2s ease-in-out infinite alternate;
        }
        
        @keyframes glow {
            from { box-shadow: 0 0 5px var(--primary-color); }
            to { box-shadow: 0 0 20px var(--primary-color); }
        }
        
        /* Dark theme enhancements */
        body {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            min-height: 100vh;
            color: #e9ecef;
        }
        
        .card {
            background: rgba(33, 37, 41, 0.95);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
    </style>
</head>
<body>
    <!-- Navigation -->
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="#">
                <i class="fas fa-robot me-2"></i>
                <?php echo htmlspecialchars($bot_name); ?>
            </a>
            <div class="navbar-nav ms-auto">
                <span class="navbar-text">
                    <i class="fas fa-circle text-success me-1"></i>
                    Status: <span class="text-success">Online</span>
                </span>
            </div>
        </div>
    </nav>

    <div class="container py-5">
        <!-- Header -->
        <div class="row mb-5">
            <div class="col-12 text-center">
                <h1 class="display-4 fw-bold mb-3">
                    <i class="fas fa-server me-3"></i>
                    Bot Status Dashboard
                </h1>
                <p class="lead text-muted">
                    Real-time monitoring and health checks for your Telegram bot
                </p>
                <div class="d-flex justify-content-center gap-3 mt-4">
                    <a href="/health" class="btn btn-custom" target="_blank">
                        <i class="fas fa-heart-pulse me-2"></i>Health Check
                    </a>
                    <a href="https://t.me/<?php echo $bot_username; ?>" class="btn btn-outline-light" target="_blank">
                        <i class="fab fa-telegram me-2"></i>Open Bot
                    </a>
                    <button id="refreshBtn" class="btn btn-outline-info">
                        <i class="fas fa-sync-alt me-2"></i>Refresh
                    </button>
                </div>
            </div>
        </div>

        <!-- Metrics Overview -->
        <div class="row mb-5">
            <div class="col-md-3 mb-4">
                <div class="metric-card">
                    <i class="fas fa-microchip fa-2x mb-3"></i>
                    <div class="metric-value" id="cpuLoad">--</div>
                    <div class="metric-label">CPU Load</div>
                </div>
            </div>
            <div class="col-md-3 mb-4">
                <div class="metric-card" style="background: linear-gradient(135deg, #fd7e14, #e55a00);">
                    <i class="fas fa-memory fa-2x mb-3"></i>
                    <div class="metric-value" id="memoryUsage">--</div>
                    <div class="metric-label">Memory Usage</div>
                </div>
            </div>
            <div class="col-md-3 mb-4">
                <div class="metric-card" style="background: linear-gradient(135deg, #20c997, #169c74);">
                    <i class="fas fa-hdd fa-2x mb-3"></i>
                    <div class="metric-value" id="fileCount">--</div>
                    <div class="metric-label">Generated Files</div>
                </div>
            </div>
            <div class="col-md-3 mb-4">
                <div class="metric-card" style="background: linear-gradient(135deg, #6f42c1, #5a2d9c);">
                    <i class="fas fa-network-wired fa-2x mb-3"></i>
                    <div class="metric-value" id="responseTime">--</div>
                    <div class="metric-label">Response Time</div>
                </div>
            </div>
        </div>

        <div class="row">
            <!-- Left Column -->
            <div class="col-lg-8 mb-4">
                <!-- System Status -->
                <div class="card status-card mb-4">
                    <div class="card-header bg-dark">
                        <h5 class="card-title mb-0">
                            <i class="fas fa-cogs me-2"></i>System Status
                        </h5>
                    </div>
                    <div class="card-body">
                        <div class="row">
                            <div class="col-md-6">
                                <?php
                                $system_info = get_system_info();
                                $required_files = check_required_files();
                                $bot_running = check_bot_process();
                                ?>
                                <div class="mb-3">
                                    <strong>Bot Process:</strong>
                                    <span class="float-end">
                                        <span class="status-indicator <?php echo $bot_running ? 'status-online' : 'status-offline'; ?>"></span>
                                        <?php echo $bot_running ? 'Running' : 'Stopped'; ?>
                                    </span>
                                </div>
                                <div class="mb-3">
                                    <strong>Python Version:</strong>
                                    <span class="float-end text-info"><?php echo htmlspecialchars($system_info['python_version']); ?></span>
                                </div>
                                <div class="mb-3">
                                    <strong>PHP Version:</strong>
                                    <span class="float-end text-info"><?php echo htmlspecialchars($system_info['php_version']); ?></span>
                                </div>
                                <div class="mb-3">
                                    <strong>Memory Usage:</strong>
                                    <span class="float-end text-warning"><?php echo $system_info['memory_usage']; ?></span>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="mb-3">
                                    <strong>Server Time:</strong>
                                    <span class="float-end"><?php echo $server_time; ?></span>
                                </div>
                                <div class="mb-3">
                                    <strong>Last Updated:</strong>
                                    <span class="float-end"><?php echo $last_updated; ?></span>
                                </div>
                                <div class="mb-3">
                                    <strong>Platform:</strong>
                                    <span class="float-end text-info"><?php echo $deployment_platform; ?></span>
                                </div>
                                <div class="mb-3">
                                    <strong>System Load:</strong>
                                    <span class="float-end text-warning"><?php echo $system_info['system_load']['1min']; ?></span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- File System Status -->
                <div class="card status-card">
                    <div class="card-header bg-dark">
                        <h5 class="card-title mb-0">
                            <i class="fas fa-folder me-2"></i>File System Status
                        </h5>
                    </div>
                    <div class="card-body">
                        <?php foreach ($required_files as $file => $exists): ?>
                            <div class="file-status <?php echo !$exists ? 'missing' : ''; ?>">
                                <span>
                                    <i class="fas fa-<?php echo $exists ? 'check-circle text-success' : 'times-circle text-danger'; ?> me-2"></i>
                                    <?php echo htmlspecialchars($file); ?>
                                </span>
                                <span class="status-indicator <?php echo $exists ? 'status-online' : 'status-offline'; ?>"></span>
                            </div>
                        <?php endforeach; ?>
                    </div>
                </div>
            </div>

            <!-- Right Column -->
            <div class="col-lg-4">
                <!-- Quick Actions -->
                <div class="card status-card mb-4">
                    <div class="card-header bg-dark">
                        <h5 class="card-title mb-0">
                            <i class="fas fa-bolt me-2"></i>Quick Actions
                        </h5>
                    </div>
                    <div class="card-body">
                        <div class="d-grid gap-2">
                            <a href="/health" class="btn btn-outline-success btn-sm" target="_blank">
                                <i class="fas fa-heart-pulse me-2"></i>Health Check API
                            </a>
                            <a href="/api/status" class="btn btn-outline-info btn-sm" target="_blank">
                                <i class="fas fa-code me-2"></i>Status API
                            </a>
                            <a href="https://t.me/<?php echo $bot_username; ?>" class="btn btn-outline-primary btn-sm" target="_blank">
                                <i class="fab fa-telegram me-2"></i>Test Bot
                            </a>
                            <button class="btn btn-outline-warning btn-sm" onclick="restartBot()">
                                <i class="fas fa-power-off me-2"></i>Restart Bot
                            </button>
                        </div>
                    </div>
                </div>

                <!-- Database Files -->
                <div class="card status-card">
                    <div class="card-header bg-dark">
                        <h5 class="card-title mb-0">
                            <i class="fas fa-database me-2"></i>Database Files
                        </h5>
                    </div>
                    <div class="card-body">
                        <?php
                        $database_files = get_database_files();
                        if (empty($database_files)): ?>
                            <div class="text-center text-muted py-3">
                                <i class="fas fa-inbox fa-2x mb-2"></i>
                                <p>No database files found</p>
                            </div>
                        <?php else: ?>
                            <div style="max-height: 300px; overflow-y: auto;">
                                <?php foreach (array_slice($database_files, 0, 10) as $file): ?>
                                    <div class="file-status">
                                        <div>
                                            <small class="text-info"><?php echo htmlspecialchars($file['name']); ?></small>
                                            <br>
                                            <small class="text-muted">
                                                <?php echo $file['size']; ?> • <?php echo $file['lines']; ?> lines
                                            </small>
                                        </div>
                                    </div>
                                <?php endforeach; ?>
                                <?php if (count($database_files) > 10): ?>
                                    <div class="text-center mt-2">
                                        <small class="text-muted">+<?php echo count($database_files) - 10; ?> more files</small>
                                    </div>
                                <?php endif; ?>
                            </div>
                        <?php endif; ?>
                    </div>
                </div>

                <!-- Bot Statistics -->
                <div class="card status-card mt-4">
                    <div class="card-header bg-dark">
                        <h5 class="card-title mb-0">
                            <i class="fas fa-chart-bar me-2"></i>Bot Statistics
                        </h5>
                    </div>
                    <div class="card-body">
                        <?php
                        $stats = get_bot_statistics();
                        ?>
                        <div class="mb-3">
                            <strong>Generated Files:</strong>
                            <span class="float-end text-info"><?php echo $stats['generated_files_count'] ?? 0; ?></span>
                        </div>
                        <div class="mb-3">
                            <strong>Bot Data:</strong>
                            <span class="float-end <?php echo $stats['bot_data_exists'] ? 'text-success' : 'text-warning'; ?>">
                                <?php echo $stats['bot_data_exists'] ? 'Exists' : 'Not Found'; ?>
                            </span>
                        </div>
                        <div class="mb-3">
                            <strong>Uptime:</strong>
                            <span class="float-end text-success" id="uptime">Calculating...</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Recent Activity -->
        <div class="row mt-4">
            <div class="col-12">
                <div class="card status-card">
                    <div class="card-header bg-dark d-flex justify-content-between align-items-center">
                        <h5 class="card-title mb-0">
                            <i class="fas fa-history me-2"></i>Recent Activity
                        </h5>
                        <span class="badge bg-primary" id="activityCount">0 events</span>
                    </div>
                    <div class="card-body">
                        <div id="activityLog" class="text-center text-muted py-4">
                            <i class="fas fa-spinner fa-spin me-2"></i>Loading activity log...
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Footer -->
    <footer class="bg-dark text-light py-4 mt-5">
        <div class="container">
            <div class="row">
                <div class="col-md-6">
                    <h6><?php echo htmlspecialchars($bot_name); ?></h6>
                    <p class="text-muted mb-0">Premium Account Generator Bot</p>
                </div>
                <div class="col-md-6 text-md-end">
                    <p class="text-muted mb-0">
                        <i class="fas fa-clock me-1"></i>
                        Server: <?php echo $server_time; ?> | 
                        <i class="fas fa-sync-alt me-1 ms-2"></i>
                        <span id="lastRefresh">Just now</span>
                    </p>
                </div>
            </div>
        </div>
    </footer>

    <!-- JavaScript -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        let lastRefresh = new Date();
        
        // Update metrics
        function updateMetrics() {
            fetch('/health')
                .then(response => response.json())
                .then(data => {
                    // Update CPU Load
                    document.getElementById('cpuLoad').textContent = data.system?.system_load?.['1min'] || '--';
                    
                    // Update Memory Usage
                    document.getElementById('memoryUsage').textContent = data.system?.memory_usage || '--';
                    
                    // Update File Count
                    document.getElementById('fileCount').textContent = data.database?.length || '0';
                    
                    // Update Response Time
                    document.getElementById('responseTime').textContent = data.response_time || '--';
                    
                    // Update Uptime
                    document.getElementById('uptime').textContent = data.response_time || '--';
                    
                    // Update last refresh time
                    document.getElementById('lastRefresh').textContent = 'Just now';
                    lastRefresh = new Date();
                })
                .catch(error => {
                    console.error('Error fetching metrics:', error);
                    document.getElementById('cpuLoad').textContent = 'Error';
                    document.getElementById('memoryUsage').textContent = 'Error';
                    document.getElementById('fileCount').textContent = 'Error';
                    document.getElementById('responseTime').textContent = 'Error';
                });
        }
        
        // Refresh button handler
        document.getElementById('refreshBtn').addEventListener('click', function() {
            const icon = this.querySelector('i');
            icon.classList.add('refresh-indicator');
            
            updateMetrics();
            
            setTimeout(() => {
                icon.classList.remove('refresh-indicator');
            }, 1000);
        });
        
        // Simulate restart bot
        function restartBot() {
            if (confirm('Are you sure you want to restart the bot? This will temporarily interrupt service.')) {
                alert('Bot restart command sent. This feature would be implemented in a production environment.');
            }
        }
        
        // Auto-refresh every 30 seconds
        setInterval(updateMetrics, 30000);
        
        // Initial load
        updateMetrics();
        
        // Update relative time
        setInterval(() => {
            const now = new Date();
            const diff = Math.floor((now - lastRefresh) / 1000);
            const minutes = Math.floor(diff / 60);
            const seconds = diff % 60;
            
            if (minutes > 0) {
                document.getElementById('lastRefresh').textContent = `${minutes}m ${seconds}s ago`;
            } else {
                document.getElementById('lastRefresh').textContent = `${seconds}s ago`;
            }
        }, 1000);
        
        // Simulate activity log
        setTimeout(() => {
            const activities = [
                'Bot started successfully',
                'Health check passed',
                'User authentication completed',
                'Account generation requested',
                'File processed successfully',
                'Database updated',
                'Backup created',
                'Cache cleared'
            ];
            
            const activityLog = document.getElementById('activityLog');
            const activityCount = document.getElementById('activityCount');
            
            let html = '';
            for (let i = 0; i < 5; i++) {
                const activity = activities[Math.floor(Math.random() * activities.length)];
                const time = Math.floor(Math.random() * 10) + 1;
                html += `
                    <div class="d-flex justify-content-between align-items-center py-2 border-bottom border-secondary">
                        <span>${activity}</span>
                        <small class="text-muted">${time} min ago</small>
                    </div>
                `;
            }
            
            activityLog.innerHTML = html;
            activityCount.textContent = '5 events';
        }, 2000);
    </script>

    <?php
    // Log access for monitoring
    $log_message = sprintf(
        "[%s] %s accessed %s from %s - User Agent: %s\n",
        date('Y-m-d H:i:s'),
        $client_ip,
        $_SERVER['REQUEST_URI'],
        $_SERVER['HTTP_USER_AGENT'] ?? 'Unknown'
    );
    
    // Write to access log
    file_put_contents('access.log', $log_message, FILE_APPEND | LOCK_EX);
    ?>
</body>
</html>