<?php

/**
 * Plugin Name: Mixia Bot — Recomendador de Produtos
 * Description: Assistente de vendas inteligente powered by Claude AI. Recomenda produtos do portfólio Polibrinq para lojistas.
 * Version: 1.0.0
 * Author: Polibrinq
 * Text Domain: mixia-bot
 */

defined('ABSPATH') || exit;

define('MIXIA_BOT_VERSION', '1.6.0');
define('MIXIA_BOT_PATH', plugin_dir_path(__FILE__));
define('MIXIA_BOT_URL', plugin_dir_url(__FILE__));

require_once MIXIA_BOT_PATH . 'includes/admin-settings.php';
require_once MIXIA_BOT_PATH . 'includes/widget.php';
