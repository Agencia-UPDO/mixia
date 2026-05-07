<?php
defined('ABSPATH') || exit;

add_shortcode('mixia_chat', 'mixia_bot_shortcode');
add_action('wp_ajax_mixia_add_to_cart',        'mixia_bot_add_to_cart');
add_action('wp_ajax_nopriv_mixia_add_to_cart', 'mixia_bot_add_to_cart');

function mixia_bot_shortcode($atts)
{
    $atts = shortcode_atts(['height' => ''], $atts, 'mixia_chat');

    mixia_bot_enqueue_assets();

    $style = $atts['height'] ? ' style="--mb-chat-height:' . esc_attr($atts['height']) . '"' : '';
    return '<div id="mixia-bot-root"' . $style . '></div>';
}

function mixia_bot_enqueue_assets()
{
    static $enqueued = false;
    if ($enqueued) return;
    $enqueued = true;

    wp_enqueue_style(
        'mixia-bot-chat',
        MIXIA_BOT_URL . 'assets/mixia-chat.css',
        [],
        MIXIA_BOT_VERSION
    );

    wp_enqueue_script(
        'mixia-bot-chat',
        MIXIA_BOT_URL . 'assets/mixia-chat.js',
        [],
        MIXIA_BOT_VERSION,
        true
    );

    wp_localize_script('mixia-bot-chat', 'MixiaBotConfig', [
        'backendUrl'  => trailingslashit(get_option('mixia_bot_backend_url', '')),
        'widgetTitle' => get_option('mixia_bot_widget_title', 'Assistente de Vendas'),
        'sessionId'   => 'wc_' . md5(uniqid('', true)),
        'ajaxUrl'     => admin_url('admin-ajax.php'),
        'nonce'       => wp_create_nonce('mixia_add_to_cart'),
    ]);
}

function mixia_bot_add_to_cart()
{
    check_ajax_referer('mixia_add_to_cart', 'nonce');

    // Suporta formato novo (items com qty) e legado (ids)
    $items_raw = stripslashes($_POST['items'] ?? '');
    $ids_raw   = stripslashes($_POST['ids'] ?? '');

    $items = $items_raw ? json_decode($items_raw, true) : null;
    if (!is_array($items) || empty($items)) {
        // Fallback formato antigo
        $ids = json_decode($ids_raw, true);
        if (is_array($ids) && !empty($ids)) {
            $items = array_map(function ($id) {
                return ['id' => $id, 'qty' => 1];
            }, $ids);
        }
    }

    if (!is_array($items) || empty($items)) {
        wp_send_json_error(['message' => 'Nenhum produto informado.']);
    }

    if (!function_exists('WC') || !WC()->cart) {
        wp_send_json_error(['message' => 'WooCommerce não está ativo.']);
    }

    foreach ($items as $item) {
        $product_id = absint($item['id'] ?? 0);
        $qty        = max(1, intval($item['qty'] ?? 1));
        if ($product_id > 0) {
            WC()->cart->add_to_cart($product_id, $qty);
        }
    }

    wp_send_json_success(['cart_url' => wc_get_cart_url()]);
}
