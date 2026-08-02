<?php
require_once __DIR__ . '/prompt.php';
$userMessage = 'example user input';
$messages = [['role' => 'system', 'content' => $systemPrompt], ['role' => 'user', 'content' => $userMessage]];
$openai->chat(messages: $messages, model: 'local-example');
$database->create(['messages' => 2]); // deliberately not an LLM call
