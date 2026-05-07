<?php
defined('ABSPATH') || exit;

add_action('admin_menu', 'mixia_bot_admin_menu');
add_action('admin_init', 'mixia_bot_register_settings');
add_action('admin_post_mixia_bot_save_settings', 'mixia_bot_save_settings');

function mixia_bot_admin_menu()
{
    add_menu_page(
        'Mixia Bot',
        'Mixia Bot',
        'manage_options',
        'mixia-bot',
        'mixia_bot_settings_page',
        'dashicons-format-chat',
        58
    );
}

function mixia_bot_register_settings()
{
    register_setting('mixia_bot_options', 'mixia_bot_backend_url');
    register_setting('mixia_bot_options', 'mixia_bot_admin_token');
    register_setting('mixia_bot_options', 'mixia_bot_widget_title');
    register_setting('mixia_bot_options', 'mixia_bot_widget_enabled');
}

function mixia_bot_save_settings()
{
    if (!current_user_can('manage_options')) {
        wp_die('Sem permissão.');
    }
    check_admin_referer('mixia_bot_save');

    $backend_url   = sanitize_url($_POST['mixia_bot_backend_url'] ?? '');
    $admin_token   = sanitize_text_field($_POST['mixia_bot_admin_token'] ?? '');
    $widget_title  = sanitize_text_field($_POST['mixia_bot_widget_title'] ?? 'Assistente de Vendas');
    $widget_enabled = isset($_POST['mixia_bot_widget_enabled']) ? '1' : '0';

    update_option('mixia_bot_backend_url', $backend_url);
    update_option('mixia_bot_admin_token', $admin_token);
    update_option('mixia_bot_widget_title', $widget_title);
    update_option('mixia_bot_widget_enabled', $widget_enabled);

    $anthropic_key  = sanitize_text_field($_POST['mixia_bot_anthropic_key'] ?? '');
    $wc_key         = sanitize_text_field($_POST['mixia_bot_wc_key'] ?? '');
    $wc_secret      = sanitize_text_field($_POST['mixia_bot_wc_secret'] ?? '');

    if ($anthropic_key) update_option('mixia_bot_anthropic_key_set', '1');
    if ($wc_key)        update_option('mixia_bot_wc_key_set', '1');
    if ($wc_secret)     update_option('mixia_bot_wc_secret_set', '1');

    $has_keys = $anthropic_key || $wc_key || $wc_secret;

    if ($has_keys && $backend_url && $admin_token) {
        $payload = array_filter([
            'anthropic_api_key'    => $anthropic_key ?: null,
            'woocommerce_key'      => $wc_key ?: null,
            'woocommerce_secret'   => $wc_secret ?: null,
        ]);

        $response = wp_remote_post(
            trailingslashit($backend_url) . 'admin/update-config',
            [
                'headers' => [
                    'Content-Type'              => 'application/json',
                    'Authorization'             => 'Bearer ' . $admin_token,
                    'ngrok-skip-browser-warning' => 'true',
                ],
                'body'    => wp_json_encode($payload),
                'timeout' => 10,
            ]
        );

        if (is_wp_error($response)) {
            $notice = 'error';
            $msg = 'Erro ao conectar com o backend: ' . $response->get_error_message();
        } else {
            $code = wp_remote_retrieve_response_code($response);
            $notice = $code === 200 ? 'success' : 'error';
            $msg = $code === 200
                ? 'Configurações salvas e chaves atualizadas no backend!'
                : 'Configurações locais salvas, mas o backend retornou erro ' . $code . '.';
        }
    } else {
        $notice = 'success';
        $msg = 'Configurações salvas!';
    }

    wp_redirect(admin_url('admin.php?page=mixia-bot&notice=' . $notice . '&msg=' . urlencode($msg)));
    exit;
}

function mixia_bot_settings_page()
{
    $backend_url    = get_option('mixia_bot_backend_url', '');
    $admin_token    = get_option('mixia_bot_admin_token', '');
    $widget_title   = get_option('mixia_bot_widget_title', 'Assistente de Vendas');
    $widget_enabled = get_option('mixia_bot_widget_enabled', '1');
    $anthropic_set  = get_option('mixia_bot_anthropic_key_set', '');
    $wc_key_set     = get_option('mixia_bot_wc_key_set', '');
    $wc_secret_set  = get_option('mixia_bot_wc_secret_set', '');
    $notice         = $_GET['notice'] ?? '';
    $msg            = $_GET['msg'] ?? '';
?>
    <div class="wrap">
        <h1>⚙️ Mixia Bot — Configurações</h1>

        <?php if ($notice === 'success'): ?>
            <div class="notice notice-success is-dismissible">
                <p><?= esc_html($msg ?: 'Configurações salvas!') ?></p>
            </div>
        <?php elseif ($notice === 'error'): ?>
            <div class="notice notice-error is-dismissible">
                <p><?= esc_html($msg) ?></p>
            </div>
        <?php endif; ?>

        <form method="POST" action="<?= admin_url('admin-post.php') ?>">
            <input type="hidden" name="action" value="mixia_bot_save_settings">
            <?php wp_nonce_field('mixia_bot_save'); ?>

            <h2>🔌 Backend</h2>
            <table class="form-table">
                <tr>
                    <th><label for="mixia_bot_backend_url">URL do Backend</label></th>
                    <td>
                        <input type="url" id="mixia_bot_backend_url" name="mixia_bot_backend_url"
                            value="<?= esc_attr($backend_url) ?>" class="regular-text"
                            placeholder="https://seu-backend.railway.app">
                        <p class="description">Endereço do servidor Python (FastAPI).</p>
                    </td>
                </tr>
                <tr>
                    <th><label for="mixia_bot_admin_token">Token Administrativo</label></th>
                    <td>
                        <input type="password" id="mixia_bot_admin_token" name="mixia_bot_admin_token"
                            value="<?= esc_attr($admin_token) ?>" class="regular-text"
                            placeholder="Token secreto definido no backend">
                        <p class="description">Token para autorizar atualizações de configuração no backend.</p>
                    </td>
                </tr>
            </table>

            <h2>🔑 Chaves de API <span style="font-size:13px;font-weight:normal;color:#666">(deixe em branco para não alterar)</span></h2>
            <table class="form-table">
                <tr>
                    <th><label for="mixia_bot_anthropic_key">Chave Claude (Anthropic)</label></th>
                    <td>
                        <input type="password" id="mixia_bot_anthropic_key" name="mixia_bot_anthropic_key"
                            value="" class="regular-text" placeholder="<?= $anthropic_set ? '••••••••  (já configurada)' : 'sk-ant-...' ?>">
                        <?php if ($anthropic_set): ?><span style="color:#46b450">✔ Configurada</span><?php endif; ?>
                    </td>
                </tr>
                <tr>
                    <th><label for="mixia_bot_wc_key">WooCommerce Consumer Key</label></th>
                    <td>
                        <input type="password" id="mixia_bot_wc_key" name="mixia_bot_wc_key"
                            value="" class="regular-text" placeholder="<?= $wc_key_set ? '••••••••  (já configurada)' : 'ck_...' ?>">
                        <?php if ($wc_key_set): ?><span style="color:#46b450">✔ Configurada</span><?php endif; ?>
                    </td>
                </tr>
                <tr>
                    <th><label for="mixia_bot_wc_secret">WooCommerce Consumer Secret</label></th>
                    <td>
                        <input type="password" id="mixia_bot_wc_secret" name="mixia_bot_wc_secret"
                            value="" class="regular-text" placeholder="<?= $wc_secret_set ? '••••••••  (já configurada)' : 'cs_...' ?>">
                        <?php if ($wc_secret_set): ?><span style="color:#46b450">✔ Configurada</span><?php endif; ?>
                    </td>
                </tr>
            </table>

            <h2>💬 Chat</h2>
            <table class="form-table">
                <tr>
                    <th><label for="mixia_bot_widget_title">Título do Chat</label></th>
                    <td>
                        <input type="text" id="mixia_bot_widget_title" name="mixia_bot_widget_title"
                            value="<?= esc_attr($widget_title) ?>" class="regular-text">
                        <p class="description">Use o shortcode <code>[mixia_chat]</code> em qualquer página para exibir o assistente.</p>
                    </td>
                </tr>
            </table>

            <?php submit_button('Salvar Configurações'); ?>
        </form>
    </div>
<?php
}
