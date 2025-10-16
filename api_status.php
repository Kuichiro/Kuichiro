<?php
header('Content-Type: application/json');

$response = [
    'status' => 'online',
    'timestamp' => date('c'),
    'service' => 'telegram-bot',
    'version' => '1.0.0'
];

// Add bot-specific status information
$response['bot'] = [
    'username' => 'PremiumGeneratorBot',
    'name' => 'Premium Account Generator',
    'admin_id' => 6675722513
];

echo json_encode($response, JSON_PRETTY_PRINT);