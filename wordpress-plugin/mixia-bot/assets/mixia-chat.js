(function () {
  'use strict';

  const cfg     = window.MixiaBotConfig || {};
  const BACKEND = cfg.backendUrl || '';
  const TITLE   = cfg.widgetTitle || 'Assistente de Vendas';
  const SESSION = cfg.sessionId  || ('s_' + Math.random().toString(36).slice(2));

  // ── Build DOM ──────────────────────────────────────────────────────────────
  const root = document.getElementById('mixia-bot-root');
  if (!root) return;

  root.innerHTML = `
    <div id="mb-chat">
      <div id="mb-header">
        <span id="mb-header-icon">🤖</span>
        <div>
          <div id="mb-header-title">${TITLE}</div>
          <div id="mb-header-sub">Polibrinq</div>
        </div>
      </div>
      <div id="mb-messages"></div>
      <div id="mb-input-area">
        <textarea id="mb-input" rows="1" placeholder="Digite sua mensagem..." disabled></textarea>
        <button id="mb-send" aria-label="Enviar" disabled>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <line x1="22" y1="2" x2="11" y2="13"/>
            <polygon points="22 2 15 22 11 13 2 9 22 2"/>
          </svg>
          <span>Enviar</span>
        </button>
      </div>
    </div>
  `;

  const msgs    = document.getElementById('mb-messages');
  const input   = document.getElementById('mb-input');
  const sendBtn = document.getElementById('mb-send');

  let isBusy        = false;
  let step          = 'segment';
  let chosenSegment = '';
  let chosenSize    = '';
  let chosenGender  = '';
  let chosenLocal   = '';
  let chosenQty     = '';

  function enableInput() {
    input.disabled = false;
    input.placeholder = 'Digite sua mensagem...';
    sendBtn.disabled = false;
    input.focus();
  }

  function lockInput() {
    input.disabled = true;
    sendBtn.disabled = true;
  }

  // ── Barra de Fechar Pedido removida — login obrigatório no WooCommerce ──

  // ── Fluxo guiado ───────────────────────────────────────────────────────────
  const FALLBACK_SEGMENTS = [
    'BRINQUEDOS', 'BRINQUEDOS EDUCATIVOS', 'CONVENIÊNCIA',
    'FARMÁCIA', 'PAPELARIA', 'SUPERMERCADOS'
  ];

  const SEGMENTOS_ONLINE = ['E-COMMERCE', 'ECOMMERCE', 'LOJA ONLINE', 'LOJA VIRTUAL', 'MARKETPLACE'];

  function isSegmentoOnline(seg) {
    return SEGMENTOS_ONLINE.some(s => seg.toUpperCase().includes(s));
  }

  let segmentsList = [];

  function buildSegmentListHtml(segs) {
    const items = segs.map((s, i) => `${i + 1}. ${escHtml(s)}`).join('\n');
    return '<div class="mb-segment-list">' + items + '</div>';
  }

  function handleSegmentChoice(seg) {
    chosenSegment = seg;
    appendMsg(escHtml(seg), 'user');
    if (isSegmentoOnline(seg)) {
      chosenSize = 'Média (50 a 150 m²)';
      step = 'gender';
      showGenderQuestion();
    } else {
      step = 'size';
      showSizeQuestion();
    }
  }

  function showGreetingAndSegments() {
    appendMsg(
      'Olá! 👋 Sou a Assistente de Vendas da <strong>Polibrinq</strong> e vou te ajudar a encontrar os melhores produtos para a sua loja!',
      'bot'
    );
    const loadingEl = appendMsg('<em>Carregando segmentos...</em>', 'bot');
    fetch(BACKEND + 'segments', { headers: { 'ngrok-skip-browser-warning': 'true' } })
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then(data => {
        loadingEl.remove();
        segmentsList = Array.isArray(data.segments) && data.segments.length > 0
          ? data.segments
          : FALLBACK_SEGMENTS;
        appendMsg(
          'Qual é o <strong>segmento</strong> da sua loja? Digite o número:' +
          buildSegmentListHtml(segmentsList),
          'bot'
        );
        enableInput();
        input.placeholder = 'Digite o número do segmento...';
        stepCallback = function(text) {
          const num = parseInt(text.trim(), 10);
          if (num >= 1 && num <= segmentsList.length) {
            handleSegmentChoice(segmentsList[num - 1]);
          } else {
            appendMsg('Por favor, digite um número de <strong>1</strong> a <strong>' + segmentsList.length + '</strong>.', 'bot');
            enableInput();
            input.placeholder = 'Digite o número do segmento...';
            stepCallback = arguments.callee;
          }
        };
      })
      .catch(() => {
        loadingEl.remove();
        segmentsList = FALLBACK_SEGMENTS;
        appendMsg(
          'Qual é o <strong>segmento</strong> da sua loja? Digite o número:' +
          buildSegmentListHtml(segmentsList),
          'bot'
        );
        enableInput();
        input.placeholder = 'Digite o número do segmento...';
        stepCallback = function(text) {
          const num = parseInt(text.trim(), 10);
          if (num >= 1 && num <= segmentsList.length) {
            handleSegmentChoice(segmentsList[num - 1]);
          } else {
            appendMsg('Por favor, digite um número de <strong>1</strong> a <strong>' + segmentsList.length + '</strong>.', 'bot');
            enableInput();
            input.placeholder = 'Digite o número do segmento...';
            stepCallback = arguments.callee;
          }
        };
      });
  }

  function showSizeQuestion() {
    showTypingBrief(function() {
      appendMsg('Perfeito! 🏪 E qual é o tamanho aproximado da sua loja?', 'bot');
      showChips(
        ['Pequena (até 50 m²)', 'Média (50 a 150 m²)', 'Grande (acima de 150 m²)'],
        size => {
          chosenSize = size;
          appendMsg(escHtml(size), 'user');
          step = 'gender';
          showGenderQuestion();
        }
      );
    });
  }

  function showGenderQuestion() {
    showTypingBrief(function() {
      appendMsg('👥 Para qual público a sua loja vende?', 'bot');
      showChips(
        ['Masculino', 'Feminino', 'Ambos'],
        gender => {
          chosenGender = gender;
          appendMsg(escHtml(gender), 'user');
          step = 'local';
          showLocalQuestion();
        }
      );
    });
  }

  const QTY_POR_TAMANHO = {
    'Pequena (até 50 m²)':      8,
    'Média (50 a 150 m²)':      12,
    'Grande (acima de 150 m²)': 20,
  };

  function showLocalQuestion() {
    showTypingBrief(function() {
    appendMsg('📍 Onde sua loja está localizada? <em>(ex: Curitiba/PR)</em>', 'bot');
    enableInput();
    input.placeholder = 'Digite sua cidade/estado...';
    stepCallback = function(text) {
      chosenLocal = text.trim();
      // Normaliza separadores: "Curitiba / PR" → cidade=Curitiba, uf=PR
      var partes = chosenLocal.split(/\s*[\/\-,]\s*/);
      var cidade = partes[0] || chosenLocal;
      var uf = partes[1] || '';
      chosenQty   = QTY_POR_TAMANHO[chosenSize] || 10;
      step = 'chat';
      enableInput();
      input.placeholder = 'Digite sua mensagem...';
      sendToBackend(
        'Perfil da loja:' +
        ' Segmento: ' + chosenSegment +
        '. Tamanho: ' + chosenSize +
        '. Público: ' + chosenGender +
        '. Cidade: ' + cidade +
        '. Estado: ' + uf +
        '. Quantidade de produtos: ' + chosenQty + '.' +
        ' Recomende agora os produtos sem fazer perguntas.'
      );
    };
    });
  }

  // Callback para passos que usam o input de texto
  let stepCallback = null;

  function showNumberedList(options, onClick) {
    const el = document.createElement('div');
    el.className = 'mb-numbered-list';
    options.forEach((opt, i) => {
      const btn = document.createElement('button');
      btn.className = 'mb-list-item';
      btn.innerHTML = '<span class="mb-list-num">' + (i + 1) + '</span>' + escHtml(opt);
      btn.addEventListener('click', () => { el.remove(); onClick(opt); });
      el.appendChild(btn);
    });
    msgs.appendChild(el);
    msgs.scrollTop = el.offsetTop - msgs.offsetTop;
  }

  function showChips(options, onClick) {
    const el = document.createElement('div');
    el.className = 'mb-chips';
    options.forEach(opt => {
      const btn = document.createElement('button');
      btn.className = 'mb-chip';
      btn.textContent = opt;
      btn.addEventListener('click', () => { el.remove(); onClick(opt); });
      el.appendChild(btn);
    });
    msgs.appendChild(el);
    msgs.scrollTop = el.offsetTop - msgs.offsetTop;
  }

  // ── Markdown renderer (lightweight) ───────────────────────────────────────
  function renderMarkdown(text) {
    let cardsHtml = '';

    // Extrai o bloco JSON ANTES de processar markdown para não corromper o HTML
    text = text.replace(/```json\s*([\s\S]*?)```/g, (_, json) => {
      try {
        const data = JSON.parse(json.trim());
        if (Array.isArray(data) && data.length > 0) {
          const valid = data.filter(p => p.em_estoque !== false && p.add_to_cart_url);
          if (valid.length > 0) {
            cardsHtml = '<div class="mb-cards-list">' + valid.map(renderProductCard).join('') + '</div>';
            return CARDS_MARKER;
          }
        }
      } catch (_) {}
      return '';
    });

    // Processa markdown no texto restante — split no marker para não tocar no HTML dos cards
    const partes = text.split(CARDS_MARKER);
    const mdProcess = t => t
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      .replace(/\[([^\]]+)\]\((https?:\/\/[^\)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
      .replace(/^#{1,3}\s+(.+)$/gm, '<strong>$1</strong>')
      .replace(/^---$/gm, '<hr>')
      .replace(/^[-*]\s+(.+)$/gm, '<li>$1</li>')
      .replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>')
      .replace(/\n{2,}/g, '<br><br>')
      .replace(/\n/g, '<br>');

    if (partes.length === 1) return mdProcess(partes[0]);

    // Reconstrói: texto antes + MARKER + cards + texto depois
    return mdProcess(partes[0]) + CARDS_MARKER + cardsHtml + CARDS_MARKER + mdProcess(partes.slice(1).join(''));
  }

  function renderProductCard(p) {
    const badgeClass = p.formato === 'Caixa Master' ? 'mb-badge-master' : 'mb-badge-display';
    const imgHtml    = p.imagem
      ? `<img class="mb-product-img" src="${p.imagem}" alt="${escHtml(p.nome)}" loading="lazy">`
      : '<div class="mb-product-img-placeholder">📦</div>';
    const precoUnit  = p.preco ? parseFloat(p.preco) : 0;
    const qty        = p.quantidade || 1;
    const subtotal   = precoUnit * qty;
    const fmtBRL     = v => v.toLocaleString('pt-BR', { minimumFractionDigits: 2 });

    return `
      <div class="mb-product-card">
        <div class="mb-product-img-wrap">${imgHtml}</div>
        <div class="mb-product-body">
          <div class="mb-product-name">${escHtml(p.nome)}</div>
          <span class="mb-product-badge ${badgeClass}">${escHtml(p.formato)}</span>
          <div class="mb-product-details">
            <div class="mb-detail-row"><span>Quantidade:</span> <span>${qty}</span></div>
            <div class="mb-detail-row"><span>Preço unitário:</span> <span>R$ ${fmtBRL(precoUnit)}</span></div>
            <div class="mb-detail-row mb-detail-total"><span>Total:</span> <strong>R$ ${fmtBRL(subtotal)}</strong></div>
          </div>
          ${p.add_to_cart_url
            ? `<a class="mb-btn-view" href="${p.add_to_cart_url}" target="_blank" rel="noopener">Ver Produto →</a>`
            : ''}
        </div>
      </div>`;
  }

  function escHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // ── Mensagens ──────────────────────────────────────────────────────────────
  function appendMsg(html, role) {
    const el = document.createElement('div');
    el.className = 'mb-msg ' + role;
    if (role === 'bot') {
      const icon = document.createElement('span');
      icon.className = 'mb-bot-icon';
      icon.textContent = '🤖';
      const content = document.createElement('div');
      content.className = 'mb-msg-content';
      content.innerHTML = html;
      el.appendChild(icon);
      el.appendChild(content);
    } else {
      el.innerHTML = html;
    }
    msgs.appendChild(el);
    msgs.scrollTop = el.offsetTop - msgs.offsetTop;
    return el;
  }

  // Renderiza resposta do bot — split em CARDS_MARKER para separar texto de cards
  const CARDS_MARKER = '|||CARDS|||';

  function appendBotResponse(html) {
    if (!html.includes(CARDS_MARKER)) {
      appendMsg(html, 'bot');
      return;
    }

    const parts = html.split(CARDS_MARKER);
    const beforeHtml = parts[0] || '';
    const cardsHtml  = parts[1] || '';
    const afterHtml  = parts[2] || '';

    if (beforeHtml.trim()) appendMsg(beforeHtml.trim(), 'bot');

    if (cardsHtml.trim()) {
      const cardsEl = document.createElement('div');
      cardsEl.className = 'mb-cards-wrapper';
      cardsEl.innerHTML = cardsHtml;
      msgs.appendChild(cardsEl);
    }

    if (afterHtml.trim()) appendMsg(afterHtml.trim(), 'bot');
  }

  const TYPING_MESSAGES = [
    '⏳ Essa análise pode levar até um minuto, aguarde...',
    'Analisando os campeões de venda da sua região...',
    'Consultando preços e disponibilidade em tempo real...',
    'Selecionando os produtos perfeitos para sua loja...',
    'Quase lá, montando sua curadoria personalizada...',
  ];
  let typingMsgInterval = null;

  function showTypingBrief(callback, delay) {
    delay = delay || 800;
    const el = document.createElement('div');
    el.className = 'mb-msg bot mb-typing';
    const icon = document.createElement('span');
    icon.className = 'mb-bot-icon';
    icon.textContent = '🤖';
    const dots = document.createElement('div');
    dots.className = 'mb-typing-dots';
    dots.style.padding = '10px 16px';
    dots.style.background = 'var(--mb-bubble-bot)';
    dots.style.borderRadius = '16px';
    dots.innerHTML = '<span></span><span></span><span></span>';
    el.appendChild(icon);
    el.appendChild(dots);
    msgs.appendChild(el);
    msgs.scrollTop = el.offsetTop - msgs.offsetTop;
    setTimeout(function() { el.remove(); callback(); }, delay);
  }

  function showTyping() {
    const el = document.createElement('div');
    el.className = 'mb-msg bot mb-typing';
    el.id = 'mb-typing-indicator';
    const icon = document.createElement('span');
    icon.className = 'mb-bot-icon';
    icon.textContent = '🤖';
    const wrap = document.createElement('div');
    wrap.className = 'mb-typing-wrap';
    const label = document.createElement('div');
    label.className = 'mb-typing-label';
    label.id = 'mb-typing-label';
    label.textContent = TYPING_MESSAGES[0];
    const dots = document.createElement('div');
    dots.className = 'mb-typing-dots';
    dots.innerHTML = '<span></span><span></span><span></span>';
    wrap.appendChild(label);
    wrap.appendChild(dots);
    el.appendChild(icon);
    el.appendChild(wrap);
    msgs.appendChild(el);
    msgs.scrollTop = el.offsetTop - msgs.offsetTop;

    // Alterna mensagens a cada 3,5s
    let idx = 0;
    typingMsgInterval = setInterval(() => {
      idx = (idx + 1) % TYPING_MESSAGES.length;
      const lbl = document.getElementById('mb-typing-label');
      if (lbl) {
        lbl.style.opacity = '0';
        setTimeout(() => {
          lbl.textContent = TYPING_MESSAGES[idx];
          lbl.style.opacity = '1';
        }, 200);
      }
    }, 3500);
  }

  function hideTyping() {
    if (typingMsgInterval) {
      clearInterval(typingMsgInterval);
      typingMsgInterval = null;
    }
    const el = document.getElementById('mb-typing-indicator');
    if (el) el.remove();
  }

  // ── Envio ──────────────────────────────────────────────────────────────────
  async function sendToBackend(text) {
    if (isBusy) return;
    isBusy = true;
    lockInput();

    showTyping();

    try {
      const res = await fetch(BACKEND + 'chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'ngrok-skip-browser-warning': 'true',
        },
        body: JSON.stringify({
          session_id: SESSION,
          mensagem: text,
          segmento: chosenSegment || null,
          regiao: chosenLocal || null,
          uf: null,
          porte: chosenSize || null,
        }),
      });

      hideTyping();

      if (!res.ok) throw new Error('Erro ' + res.status);
      const data = await res.json();

      // Renderiza texto (sem o bloco JSON, já vem limpo do backend)
      let msgEl = null;
      if (data.resposta) msgEl = appendMsg(renderMarkdown(data.resposta), 'bot');

      // Renderiza cards de produto diretamente do campo produtos
      if (data.produtos && data.produtos.length > 0) {
        const valid = data.produtos.filter(p => p.add_to_cart_url);
        if (valid.length > 0) {
          const cardsEl = document.createElement('div');
          cardsEl.className = 'mb-cards-wrapper';
          cardsEl.innerHTML = '<div class="mb-cards-list">' + valid.map(renderProductCard).join('') + '</div>';
          msgs.appendChild(cardsEl);

          // Botão "Salvar na Lista de Desejos"
          var productIds = valid.map(p => p.product_id).filter(Boolean);
          if (productIds.length > 0) {
            var wishBtn = document.createElement('button');
            wishBtn.className = 'mb-btn-wishlist';
            wishBtn.innerHTML = '💾 Salvar todos na Lista de Desejos';
            wishBtn.addEventListener('click', function() {
              addAllToWishlist(productIds, wishBtn);
            });
            msgs.appendChild(wishBtn);
          }

          var scrollTarget = msgEl || cardsEl;
          msgs.scrollTop = scrollTarget.offsetTop - msgs.offsetTop;
        }
      }
    } catch (err) {
      console.error('[MIXIA] Error:', err);
      hideTyping();
      appendMsg('Desculpe, houve um erro ao conectar. Tente novamente em instantes.', 'bot');
    } finally {
      isBusy = false;
      if (step === 'chat') enableInput();
    }
  }

  function handleSend() {
    const text = input.value.trim();
    if (!text || isBusy) return;
    input.value = '';
    input.style.height = 'auto';
    appendMsg(escHtml(text), 'user');

    // Se estamos em um passo guiado com callback
    if (stepCallback) {
      const cb = stepCallback;
      stepCallback = null;
      lockInput();
      cb(text);
      return;
    }

    if (step !== 'chat') return;
    sendToBackend(text);
  }

  sendBtn.addEventListener('click', handleSend);
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
  });

  input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 120) + 'px';
  });

  // ── Wishlist (Woodmart) ─────────────────────────────────────────────────────
  function addAllToWishlist(productIds, btn) {
    btn.disabled = true;
    btn.innerHTML = '⏳ Salvando...';
    var done = 0;
    var errors = 0;
    var total = productIds.length;

    // Woodmart usa admin-ajax.php com action woodmart_add_to_wishlist
    var ajaxUrl = (window.woodmart_settings && woodmart_settings.ajaxurl)
      || (window.ajaxurl)
      || '/wp-admin/admin-ajax.php';

    function next(i) {
      if (i >= total) {
        if (errors === 0) {
          btn.innerHTML = '✅ Salvo na Lista de Desejos!';
          btn.className = 'mb-btn-wishlist mb-btn-wishlist-done';
        } else {
          btn.innerHTML = '⚠️ ' + done + ' de ' + total + ' salvos';
        }
        return;
      }

      var formData = new FormData();
      formData.append('action', 'woodmart_add_to_wishlist');
      formData.append('product_id', productIds[i]);

      fetch(ajaxUrl, { method: 'POST', body: formData, credentials: 'same-origin' })
        .then(function(r) { return r.json(); })
        .then(function() { done++; btn.innerHTML = '⏳ Salvando ' + (i + 1) + '/' + total + '...'; next(i + 1); })
        .catch(function() { errors++; next(i + 1); });
    }

    next(0);
  }

  // ── Inicia fluxo ───────────────────────────────────────────────────────────
  showGreetingAndSegments();
})();;
