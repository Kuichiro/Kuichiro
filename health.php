<?php
// Simple health check that returns 200 OK if basic files exist
header('Content-Type: application/json');

$healthy = file_exists('bot.py') && file_exists('requirements.txt');

if ($healthy) {
    http_response_code(200);
    echo json_encode(['status' => 'healthy', 'timestamp' => date('c')]);
} else {
    http_response_code(503);
    echo json_encode(['status' => 'unhealthy', 'timestamp' => date('c')]);
}