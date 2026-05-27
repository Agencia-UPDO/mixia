<?php
defined('ABSPATH') || exit;

add_shortcode('mixia_chat', 'mixia_bot_shortcode');
add_action('wp_ajax_mixia_add_to_cart',        'mixia_bot_add_to_cart');
add_action('wp_ajax_nopriv_mixia_add_to_cart', 'mixia_bot_add_to_cart');
add_action('wp_ajax_mixia_add_to_wishlist',        'mixia_bot_add_to_wishlist');
add_action('wp_ajax_nopriv_mixia_add_to_wishlist', 'mixia_bot_add_to_wishlist');

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
        'wishlistNonce' => wp_create_nonce('mixia_wishlist'),
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

function mixia_bot_add_to_wishlist()
{
    check_ajax_referer('mixia_wishlist', 'nonce');

    $product_ids_raw = stripslashes($_POST['product_ids'] ?? '');
    $product_ids = json_decode($product_ids_raw, true);

    if (!is_array($product_ids) || empty($product_ids)) {
        wp_send_json_error(['message' => 'Nenhum produto informado.']);
    }

    $added = 0;

    // Tenta usar a classe Wishlist do Woodmart
    if (class_exists('\XTS\Modules\Wishlist\Wishlist')) {
        $wishlist = \XTS\Modules\Wishlist\Wishlist::get_instance();
        foreach ($product_ids as $pid) {
            $pid = absint($pid);
            if ($pid > 0 && method_exists($wishlist, 'add')) {
                $wishlist->add($pid);
                $added++;
            }
        }
    }

    // Manipula direto no banco do Woodmart
    if ($added === 0 && is_user_logged_in()) {
        global $wpdb;
        $user_id = get_current_user_id();
        $wishlist_table = $wpdb->prefix . 'woodmart_wishlists';
        $products_table = $wpdb->prefix . 'woodmart_wishlist_products';

        // Verifica se a tabela existe
        if ($wpdb->get_var("SHOW TABLES LIKE '$products_table'") === $products_table) {
            // Pega o ID da wishlist padrao do usuario
            $wishlist_id = $wpdb->get_var($wpdb->prepare(
                "SELECT ID FROM $wishlist_table WHERE user_id = %d ORDER BY ID ASC LIMIT 1",
                $user_id
            ));

            // Se nao tem wishlist, cria uma
            if (!$wishlist_id) {
                $wpdb->insert($wishlist_table, [
                    'user_id'        => $user_id,
                    'wishlist_group' => '',
                    'date_created'   => current_time('mysql'),
                ]);
                $wishlist_id = $wpdb->insert_id;
            }

            foreach ($product_ids as $pid) {
                $pid = absint($pid);
                if ($pid <= 0) continue;

                // Verifica se ja existe
                $exists = $wpdb->get_var($wpdb->prepare(
                    "SELECT COUNT(*) FROM $products_table WHERE product_id = %d AND wishlist_id = %d",
                    $pid, $wishlist_id
                ));

                if (!$exists) {
                    $wpdb->insert($products_table, [
                        'product_id'  => $pid,
                        'wishlist_id' => $wishlist_id,
                        'date_added'  => current_time('mysql'),
                        'on_sale'     => 0,
                    ]);
                    $added++;
                }
            }
        }
    }

    // Debug info temporário
    global $wpdb;
    $debug = [
        'prefix' => $wpdb->prefix,
        'user_id' => get_current_user_id(),
        'logged_in' => is_user_logged_in(),
        'wishlist_table_exists' => $wpdb->get_var("SHOW TABLES LIKE '{$wpdb->prefix}woodmart_wishlist_products'") ? true : false,
        'wishlist_id_used' => isset($wishlist_id) ? $wishlist_id : null,
        'product_ids_received' => $product_ids,
    ];
    wp_send_json_success(['added' => $added, 'total' => count($product_ids), 'debug' => $debug]);
}
