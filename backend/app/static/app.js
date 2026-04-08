const formatPercent = (value) => `${(value * 100).toFixed(1)}%`;

const formatDateTime = (value) =>
  new Date(value).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });

const formatDate = (value) =>
  new Date(value).toLocaleDateString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });

const state = {
  market: null,
  sectors: [],
  availableModes: [],
  selectedMode: null,
  signals: [],
  currentSymbol: null,
  currentDetail: null,
  currentEventTab: "official",
  currentEventTone: "all",
  tradeProfiles: [],
  tradeDiagnostics: null,
};

const SENTIMENT_THEME = {
  ice: {
    accent: "#6ea8ff",
    soft: "rgba(110, 168, 255, 0.18)",
    border: "rgba(110, 168, 255, 0.3)",
    chip: "rgba(110, 168, 255, 0.12)",
  },
  fade: {
    accent: "#8fc5ff",
    soft: "rgba(143, 197, 255, 0.18)",
    border: "rgba(143, 197, 255, 0.28)",
    chip: "rgba(143, 197, 255, 0.12)",
  },
  repair: {
    accent: "#f2c66b",
    soft: "rgba(242, 198, 107, 0.18)",
    border: "rgba(242, 198, 107, 0.28)",
    chip: "rgba(242, 198, 107, 0.12)",
  },
  rotation: {
    accent: "#ffb53a",
    soft: "rgba(255, 181, 58, 0.18)",
    border: "rgba(255, 181, 58, 0.28)",
    chip: "rgba(255, 181, 58, 0.12)",
  },
  trend: {
    accent: "#45d483",
    soft: "rgba(69, 212, 131, 0.18)",
    border: "rgba(69, 212, 131, 0.28)",
    chip: "rgba(69, 212, 131, 0.12)",
  },
};

async function fetchJson(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) {
    let message = `请求失败: ${path} (${response.status})`;
    try {
      const payload = await response.json();
      if (payload?.detail) {
        message = String(payload.detail);
      }
    } catch (error) {
      console.warn("Failed to parse error response", error);
    }
    throw new Error(message);
  }
  return response.json();
}

function setText(id, value) {
  const element = document.getElementById(id);
  if (element) {
    element.textContent = value;
  }
}

function buildAiAnalysisMarkup(aiRiskAnalysis) {
  if (!aiRiskAnalysis) {
    return `
      <section class="ai-modal-window">
        <h3 class="ai-modal-title">AI 交易执行分析</h3>
        <p class="ai-modal-summary">模型接入后，这里会显示更细的执行结论、触发条件和失效条件。</p>
        <div class="tag-row">
          <span>模型预留</span>
          <span>弹窗输出</span>
        </div>
      </section>
    `;
  }

  const meta = [
    aiRiskAnalysis.generated_at ? `生成 ${formatDateTime(aiRiskAnalysis.generated_at)}` : null,
    aiRiskAnalysis.model || "待接入模型",
    `置信度 ${Math.round(Number(aiRiskAnalysis.confidence || 0.68) * 100)} / 100`,
  ].filter(Boolean);

  return `
    <section class="ai-modal-window">
      <div class="ai-window-head">
        <h3 class="ai-modal-title">AI 交易执行分析</h3>
        <div class="ai-window-meta">
          ${meta.map((item) => `<span class="ai-meta-chip">${item}</span>`).join("")}
        </div>
      </div>
      <div class="tag-row">
        ${aiRiskAnalysis.stance ? `<span>${aiRiskAnalysis.stance}</span>` : ""}
        ${aiRiskAnalysis.setup_quality ? `<span>结构 ${aiRiskAnalysis.setup_quality}</span>` : ""}
        ${aiRiskAnalysis.source ? `<span>${aiRiskAnalysis.source}</span>` : ""}
      </div>
      <p class="ai-modal-summary">${aiRiskAnalysis.summary}</p>
      <div class="ai-insight-grid">
        <article class="ai-insight-card full-span">
          <strong>关键观察</strong>
          <p class="ai-key-line">${aiRiskAnalysis.key_signal || aiRiskAnalysis.next_step || "--"}</p>
        </article>
        <article class="ai-insight-card">
          <strong>触发条件</strong>
          <ul class="ai-list">
            ${(aiRiskAnalysis.trigger_points || []).map((item) => `<li>${item}</li>`).join("") || "<li>--</li>"}
          </ul>
        </article>
        <article class="ai-insight-card">
          <strong>失效条件</strong>
          <ul class="ai-list">
            ${(aiRiskAnalysis.invalidation_points || []).map((item) => `<li>${item}</li>`).join("") || "<li>--</li>"}
          </ul>
        </article>
        <article class="ai-insight-card full-span">
          <strong>执行步骤</strong>
          <ul class="ai-list">
            ${(aiRiskAnalysis.execution_plan || []).map((item) => `<li>${item}</li>`).join("") || "<li>--</li>"}
          </ul>
        </article>
        <article class="ai-insight-card">
          <strong>补充判断</strong>
          <ul class="ai-list">
            ${(aiRiskAnalysis.highlights || []).map((item) => `<li>${item}</li>`).join("") || "<li>--</li>"}
          </ul>
        </article>
        <article class="ai-insight-card">
          <strong>下一步</strong>
          <p class="ai-next-step">${aiRiskAnalysis.next_step || "--"}</p>
        </article>
      </div>
    </section>
  `;
}

function buildTradeDiagnosticsAiMarkup(aiAnalysis) {
  if (!aiAnalysis) {
    return `
      <section class="ai-modal-window">
        <h3 class="ai-modal-title">AI 交易复盘</h3>
        <p class="ai-modal-summary">导入交割单后，这里会显示针对你的交易风格、漏洞和下一周期计划的复盘结果。</p>
        <div class="tag-row">
          <span>交易诊断</span>
          <span>Gemini 预留</span>
        </div>
      </section>
    `;
  }

  const meta = [
    aiAnalysis.generated_at ? `生成 ${formatDateTime(aiAnalysis.generated_at)}` : null,
    aiAnalysis.model || "待接入模型",
    `置信度 ${Math.round(Number(aiAnalysis.confidence || 0.68) * 100)} / 100`,
  ].filter(Boolean);

  return `
    <section class="ai-modal-window">
      <div class="ai-window-head">
        <h3 class="ai-modal-title">AI 交易复盘</h3>
        <div class="ai-window-meta">
          ${meta.map((item) => `<span class="ai-meta-chip">${item}</span>`).join("")}
        </div>
      </div>
      <div class="tag-row">
        ${(aiAnalysis.behavior_tags || []).map((item) => `<span>${item}</span>`).join("")}
      </div>
      <p class="ai-modal-summary">${aiAnalysis.summary}</p>
      <div class="ai-insight-grid">
        <article class="ai-insight-card full-span">
          <strong>交易者画像</strong>
          <p class="ai-key-line">${aiAnalysis.trader_profile || "--"}</p>
        </article>
        <article class="ai-insight-card">
          <strong>有效优势</strong>
          <ul class="ai-list">
            ${(aiAnalysis.strengths || []).map((item) => `<li>${item}</li>`).join("") || "<li>--</li>"}
          </ul>
        </article>
        <article class="ai-insight-card">
          <strong>主要漏洞</strong>
          <ul class="ai-list">
            ${(aiAnalysis.weaknesses || []).map((item) => `<li>${item}</li>`).join("") || "<li>--</li>"}
          </ul>
        </article>
        <article class="ai-insight-card full-span">
          <strong>优化动作</strong>
          <ul class="ai-list">
            ${(aiAnalysis.adjustments || []).map((item) => `<li>${item}</li>`).join("") || "<li>--</li>"}
          </ul>
        </article>
        <article class="ai-insight-card full-span">
          <strong>下一周期计划</strong>
          <ul class="ai-list">
            ${(aiAnalysis.next_cycle_plan || []).map((item) => `<li>${item}</li>`).join("") || "<li>--</li>"}
          </ul>
        </article>
      </div>
    </section>
  `;
}

function openAiAnalysisModalWithMarkup(markup) {
  const modal = document.getElementById("ai-analysis-modal");
  const body = document.getElementById("ai-analysis-modal-body");
  if (!modal || !body) {
    return;
  }
  body.innerHTML = markup;
  modal.classList.remove("is-hidden");
  modal.setAttribute("aria-hidden", "false");
}

function openAiAnalysisModal(aiRiskAnalysis) {
  openAiAnalysisModalWithMarkup(buildAiAnalysisMarkup(aiRiskAnalysis));
}

function closeAiAnalysisModal() {
  const modal = document.getElementById("ai-analysis-modal");
  if (!modal) {
    return;
  }
  modal.classList.add("is-hidden");
  modal.setAttribute("aria-hidden", "true");
}

function applySentimentTheme(toneKey) {
  const theme = SENTIMENT_THEME[toneKey] || SENTIMENT_THEME.rotation;
  const root = document.documentElement;
  root.style.setProperty("--sentiment-accent", theme.accent);
  root.style.setProperty("--sentiment-accent-soft", theme.soft);
  root.style.setProperty("--sentiment-accent-border", theme.border);
  root.style.setProperty("--sentiment-chip-bg", theme.chip);
}

function renderMarketSentiment(sentiment) {
  applySentimentTheme(sentiment?.tone_key);
  setText("sentiment-value", sentiment?.sentiment_label || "--");
  setText("sentiment-summary", sentiment?.summary || "--");
  setText("sentiment-headline", sentiment?.sentiment_label || "--");
  setText("sentiment-hero-summary", sentiment?.summary || "--");
  setText("sentiment-temperature-label", sentiment?.temperature_label || "温度待更新");
  setText(
    "sentiment-temperature-value",
    typeof sentiment?.temperature_value === "number"
      ? `${sentiment.temperature_value.toFixed(0)} / 100`
      : "--",
  );
  setText("sentiment-action-bias", sentiment?.action_bias || "--");
  setText(
    "sentiment-action-note",
    sentiment?.action_bias
      ? `${sentiment.action_bias}；优先 ${sentiment.preferred_setup || "强势主线前排"}；回避 ${sentiment.avoid_action || "无承接追价"}`
      : "--",
  );

  const temperatureFill = document.getElementById("sentiment-temperature-fill");
  if (temperatureFill) {
    const width = Math.max(6, Math.min(Number(sentiment?.temperature_value || 0), 100));
    temperatureFill.style.width = `${width}%`;
  }

  const tagRow = document.getElementById("sentiment-tag-row");
  if (tagRow) {
    const tags = sentiment?.tags?.length ? sentiment.tags : ["--"];
    tagRow.innerHTML = tags.map((item) => `<span>${item}</span>`).join("");
  }

  const playbook = document.getElementById("sentiment-playbook");
  if (playbook) {
    const items = sentiment?.playbook?.length ? sentiment.playbook : ["--"];
    playbook.innerHTML = items.map((item) => `<li>${item}</li>`).join("");
  }

  const watchouts = document.getElementById("sentiment-watchouts");
  if (watchouts) {
    const items = sentiment?.watchouts?.length ? sentiment.watchouts : ["--"];
    watchouts.innerHTML = items.map((item) => `<li>${item}</li>`).join("");
  }
}

function getModeFromUrl() {
  const params = new URLSearchParams(window.location.search);
  return params.get("mode");
}

function updateModeInUrl(mode) {
  const url = new URL(window.location.href);
  url.searchParams.set("mode", mode);
  window.history.replaceState({}, "", url.toString());
}

function renderSectors(items) {
  const container = document.getElementById("sector-list");
  const summary = document.getElementById("sector-summary-bar");
  if (!container) {
    return;
  }

  if (!items.length) {
    container.innerHTML = '<p class="empty-state">--</p>';
    if (summary) {
      summary.innerHTML = '<p class="empty-state">--</p>';
    }
    return;
  }

  if (summary) {
    const averageStrength =
      items.reduce((total, item) => total + Number(item.strength_score || 0), 0) / items.length;
    const chips = [
      `监控主线 ${items.length} 条`,
      `Top1 ${items[0].sector_name}`,
      `平均强度 ${averageStrength.toFixed(1)}`,
      `热度最高 ${items
        .slice()
        .sort((left, right) => Number(right.heat_score || 0) - Number(left.heat_score || 0))[0]
        .sector_name}`,
    ];
    summary.innerHTML = chips.map((item) => `<span class="sector-summary-chip">${item}</span>`).join("");
  }

  container.innerHTML = items
    .map(
      (sector, index) => `
        <article class="sector-card">
          <div class="sector-main-row">
            <span class="sector-rank-badge">#${index + 1}</span>
            <div class="sector-title-group">
              <strong>${sector.sector_name}</strong>
              <p>${sector.sector_code || "AKShare"} · 共识强度领先</p>
            </div>
            <div class="sector-score-group">
              <span class="sector-score-value">${sector.strength_score.toFixed(1)}</span>
              <small>主线分</small>
            </div>
          </div>
          <div class="sector-metrics">
            <span>强度 ${sector.strength_score.toFixed(0)}</span>
            <span>动量 ${sector.momentum_score.toFixed(0)}</span>
            <span>热度 ${sector.heat_score.toFixed(0)}</span>
          </div>
          <p class="sector-note">关注主线。</p>
        </article>
      `,
    )
    .join("");
}

function renderModeToolbar(items, selectedMode, onSelect) {
  const container = document.getElementById("mode-toolbar");
  if (!container) {
    return;
  }

  if (!items.length) {
    container.innerHTML = '<p class="empty-state">--</p>';
    return;
  }

  container.innerHTML = "";
  items.forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `mode-chip${item.mode_id === selectedMode ? " active" : ""}`;
    button.innerHTML = `
      <strong>${item.display_name}</strong>
      <small>${item.description}</small>
    `;
    button.addEventListener("click", () => onSelect(item.mode_id));
    container.appendChild(button);
  });
}

function renderSignalList(items, selectedSymbol, onSelect) {
  const container = document.getElementById("signal-list");
  if (!container) {
    return;
  }

  const visibleItems = items.slice(0, 5);

  if (!visibleItems.length) {
    container.style.removeProperty("--candidate-count");
    container.innerHTML = '<p class="empty-state">--</p>';
    return;
  }

  container.style.setProperty("--candidate-count", String(Math.max(visibleItems.length, 1)));
  container.innerHTML = "";
  visibleItems.forEach((item) => {
    const tags = (item.event_tags || []).slice(0, 3);
    const button = document.createElement("button");
    button.type = "button";
    button.className = `signal-item${item.symbol === selectedSymbol ? " active" : ""}`;
    button.innerHTML = `
      <div class="signal-main-row">
        <span class="signal-rank-badge">#${item.rank}</span>
        <div class="signal-title-group">
          <strong>${item.name}</strong>
          <small>${item.symbol}</small>
        </div>
        <div class="signal-score-group">
          <span class="signal-score-value">${item.risk_adjusted_score.toFixed(1)}</span>
          <small>模式分</small>
        </div>
      </div>
      <div class="signal-meta-row">
        <span class="signal-meta-chip primary">${item.holding_window}</span>
        <span class="signal-meta-chip">基础分 ${item.base_score.toFixed(1)}</span>
        <span class="signal-meta-chip">事件分 ${item.event_score.toFixed(1)}</span>
      </div>
      <div class="signal-tag-row">
        ${
          tags.length
            ? tags.map((tag) => `<span class="signal-tag-pill">${tag}</span>`).join("")
            : '<span class="signal-tag-pill">无新增事件标签</span>'
        }
      </div>
    `;
    button.addEventListener("click", () => onSelect(item.symbol));
    container.appendChild(button);
  });
}

function renderFeatures(items) {
  const container = document.getElementById("feature-grid");
  if (!container) {
    return;
  }

  if (!items.length) {
    container.innerHTML = '<p class="empty-state">--</p>';
    return;
  }

  const getFeatureTier = (value) => {
    if (value >= 78) {
      return { className: "feature-strong", label: "强势" };
    }
    if (value >= 62) {
      return { className: "feature-medium", label: "均衡" };
    }
    return { className: "feature-watch", label: "观察" };
  };

  container.innerHTML = items
    .map((feature) => {
      const tier = getFeatureTier(feature.value);
      return `
        <article class="feature-card ${tier.className}">
          <div>
            <div class="feature-card-head">
              <strong>${feature.name}</strong>
              <span class="feature-chip">${tier.label}</span>
            </div>
            <div class="feature-score-row">
              <span>${feature.value.toFixed(1)}</span>
              <small class="feature-score-label">score</small>
            </div>
            <div class="feature-meter">
              <div class="feature-meter-fill" style="width: ${Math.max(
                8,
                Math.min(feature.value, 100),
              )}%"></div>
            </div>
          </div>
          <p>${feature.description}</p>
        </article>
      `;
    })
    .join("");
}

function splitEvents(items) {
  return {
    official: items.filter((event) => event.source_category === "官方公告"),
    market: items.filter((event) => event.source_category !== "官方公告"),
  };
}

function filterEventsByTone(items) {
  if (state.currentEventTone === "all") {
    return items;
  }
  return items.filter((event) => event.sentiment === state.currentEventTone);
}

function renderEventTabs(groups) {
  const container = document.getElementById("event-tab-toolbar");
  if (!container) {
    return;
  }

  const tabs = [
    {
      id: "official",
      label: `官方公告 ${groups.official.length ? `(${groups.official.length})` : ""}`,
      disabled: groups.official.length === 0,
    },
    {
      id: "market",
      label: `资讯/研报 ${groups.market.length ? `(${groups.market.length})` : ""}`,
      disabled: groups.market.length === 0,
    },
  ];

  container.innerHTML = "";
  tabs.forEach((tab) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `event-tab-chip${tab.id === state.currentEventTab ? " active" : ""}`;
    button.textContent = tab.label;
    button.disabled = tab.disabled;
    if (!tab.disabled) {
      button.addEventListener("click", () => {
        if (state.currentEventTab === tab.id) {
          return;
        }
        state.currentEventTab = tab.id;
        renderEvents(state.currentDetail?.recent_events || []);
      });
    }
    container.appendChild(button);
  });
}

function renderEventToneFilters(items) {
  const container = document.getElementById("event-tone-toolbar");
  if (!container) {
    return;
  }

  const toneCounts = {
    positive: items.filter((event) => event.sentiment === "positive").length,
    neutral: items.filter((event) => event.sentiment === "neutral").length,
    negative: items.filter((event) => event.sentiment === "negative").length,
  };

  if (state.currentEventTone !== "all" && toneCounts[state.currentEventTone] === 0) {
    state.currentEventTone = "all";
  }

  const tones = [
    { id: "all", label: `全部 (${items.length})`, disabled: items.length === 0 },
    { id: "positive", label: `利好 (${toneCounts.positive})`, disabled: toneCounts.positive === 0 },
    { id: "neutral", label: `中性 (${toneCounts.neutral})`, disabled: toneCounts.neutral === 0 },
    { id: "negative", label: `风险 (${toneCounts.negative})`, disabled: toneCounts.negative === 0 },
  ];

  container.innerHTML = "";
  tones.forEach((tone) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `event-tone-chip${tone.id === state.currentEventTone ? " active" : ""}`;
    button.textContent = tone.label;
    button.disabled = tone.disabled;
    if (!tone.disabled) {
      button.addEventListener("click", () => {
        if (state.currentEventTone === tone.id) {
          return;
        }
        state.currentEventTone = tone.id;
        renderEvents(state.currentDetail?.recent_events || []);
      });
    }
    container.appendChild(button);
  });
}

function renderEvents(items) {
  const container = document.getElementById("event-list");
  const toneToolbar = document.getElementById("event-tone-toolbar");
  if (!container) {
    return;
  }

  const groups = splitEvents(items);
  if (groups.official.length === 0 && groups.market.length === 0) {
    renderEventTabs(groups);
    if (toneToolbar) {
      toneToolbar.innerHTML = "";
    }
    container.innerHTML = '<p class="empty-state">--</p>';
    return;
  }

  if (state.currentEventTab === "official" && groups.official.length === 0) {
    state.currentEventTab = "market";
  } else if (state.currentEventTab === "market" && groups.market.length === 0) {
    state.currentEventTab = "official";
  }

  renderEventTabs(groups);
  const tabItems = state.currentEventTab === "official" ? groups.official : groups.market;
  renderEventToneFilters(tabItems);
  const currentItems = filterEventsByTone(tabItems);

  container.innerHTML = currentItems.length
    ? currentItems
        .map(
          (event) => `
        <article class="event-card sentiment-${event.sentiment || "neutral"}">
          <div class="event-head">
            <span>${event.source_category ? `${event.source_category} · ` : ""}${event.source}</span>
            <span>${formatDateTime(event.publish_time)}</span>
          </div>
          <strong>
            ${
              event.link
                ? `<a href="${event.link}" target="_blank" rel="noreferrer">${event.title}</a>`
                : event.title
            }
          </strong>
          <p>${event.summary}</p>
        </article>
      `,
        )
        .join("")
    : `<p class="empty-state">${
        state.currentEventTab === "official"
      ? "--"
      : "--"
      }</p>`;
}

function renderDetailQuickGrid(signal, detail) {
  const container = document.getElementById("detail-quick-grid");
  if (!container) {
    return;
  }

  if (!detail) {
    container.innerHTML = '<p class="empty-state">--</p>';
    return;
  }

  const cards = [
    { label: "证券代码", value: detail.symbol, note: detail.name },
    { label: "所属行业", value: detail.industry, note: "跟随行业主线判断" },
    {
      label: "模式分",
      value: signal ? signal.risk_adjusted_score.toFixed(1) : "--",
      note: signal ? `排名 #${signal.rank}` : "--",
    },
    {
      label: "持有窗",
      value: signal?.holding_window || "--",
      note: "窗口",
    },
    {
      label: "近期事件",
      value: `${detail.recent_events?.length || 0} 条`,
      note: "公告 / 资讯 / 研报聚合",
    },
    {
      label: "执行偏向",
      value: detail.risk_plan?.action_bias || "--",
      note: detail.risk_plan ? detail.risk_plan.price_basis : "--",
    },
  ];

  container.innerHTML = cards
    .map(
      (card) => `
        <article class="quick-stat-card">
          <span>${card.label}</span>
          <strong>${card.value}</strong>
          <small>${card.note}</small>
        </article>
      `,
    )
    .join("");
}

function renderSelectionReasons(signal, detail) {
  const tagContainer = document.getElementById("detail-reason-tags");
  const listContainer = document.getElementById("detail-reason-list");
  const marketContext = document.getElementById("detail-market-context");
  if (!tagContainer || !listContainer || !marketContext) {
    return;
  }

  if (!signal || !detail) {
    tagContainer.innerHTML = "<span>--</span>";
    listContainer.innerHTML = '<p class="empty-state">--</p>';
    marketContext.textContent = "";
    return;
  }

  const tags = (signal.event_tags || []).slice(0, 4);
  tagContainer.innerHTML = tags.length
    ? tags.map((tag) => `<span>${tag}</span>`).join("")
    : "<span>--</span>";

  listContainer.innerHTML = (signal.reasons || []).length
    ? signal.reasons
        .map(
          (reason) => `
            <article class="selection-reason-card">
              <strong>${reason.label}</strong>
              <p>${reason.detail}</p>
            </article>
          `,
        )
        .join("")
    : '<p class="empty-state">--</p>';
  marketContext.textContent = detail.market_context || "";
}

function renderEmptyDetail() {
  state.currentDetail = null;
  state.currentEventTab = "official";
  state.currentEventTone = "all";
  setText("detail-subtitle", "--");
  setText("detail-thesis", "--");
  renderDetailQuickGrid(null, null);
  renderSelectionReasons(null, null);
  renderFeatures([]);
  renderEvents([]);
}

async function loadDetail(symbol) {
  const detail = await fetchJson(
    `/api/stocks/${symbol}?mode=${encodeURIComponent(state.selectedMode || "balanced")}`,
  );
  state.currentDetail = detail;
  const currentSignal = state.signals.find((item) => item.symbol === symbol) || null;
  const eventGroups = splitEvents(detail.recent_events || []);
  state.currentEventTab = eventGroups.official.length > 0 ? "official" : "market";
  state.currentEventTone = "all";

  setText(
    "detail-subtitle",
    currentSignal
      ? `${detail.name} · ${detail.symbol} · ${detail.industry} · 排名 #${currentSignal.rank}`
      : `${detail.name} · ${detail.symbol} · ${detail.industry}`,
  );
  setText("detail-thesis", detail.thesis);
  renderDetailQuickGrid(currentSignal, detail);
  renderSelectionReasons(currentSignal, detail);
  renderFeatures(detail.feature_scores);
  renderEvents(detail.recent_events);
}

function setupAiRefreshButton() {
  const button = document.getElementById("refresh-ai-risk-button");
  if (!button) {
    return;
  }

  button.addEventListener("click", async () => {
    if (!state.currentSymbol) {
      openAiAnalysisModal(null);
      return;
    }
    openAiAnalysisModal(state.currentDetail?.ai_risk_analysis || null);
  });
}

function setupTradeAiAnalysisButton() {
  const button = document.getElementById("trade-ai-analysis-button");
  if (!button) {
    return;
  }

  button.addEventListener("click", async () => {
    const batchId = state.tradeDiagnostics?.latest_batch?.batch_id;
    if (!batchId) {
      openAiAnalysisModalWithMarkup(buildTradeDiagnosticsAiMarkup(state.tradeDiagnostics?.ai_analysis || null));
      return;
    }

    const idleLabel = "AI 交易复盘";
    button.disabled = true;
    button.textContent = "分析中";
    try {
      const query = new URLSearchParams({ batch_id: batchId });
      const payload = await fetchJson(`/api/trade-diagnostics/ai-analysis?${query.toString()}`, {
        method: "POST",
      });
      state.tradeDiagnostics = {
        ...(state.tradeDiagnostics || {}),
        ai_analysis: payload,
      };
      openAiAnalysisModalWithMarkup(buildTradeDiagnosticsAiMarkup(payload));
    } catch (error) {
      console.error(error);
      openAiAnalysisModalWithMarkup(
        buildTradeDiagnosticsAiMarkup(state.tradeDiagnostics?.ai_analysis || null),
      );
    } finally {
      button.disabled = false;
      button.textContent = idleLabel;
    }
  });
}

function setupAiModal() {
  const closeButton = document.getElementById("ai-analysis-close");
  const backdrop = document.getElementById("ai-analysis-backdrop");
  const modal = document.getElementById("ai-analysis-modal");
  if (closeButton) {
    closeButton.addEventListener("click", closeAiAnalysisModal);
  }
  if (backdrop) {
    backdrop.addEventListener("click", closeAiAnalysisModal);
  }
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && modal && !modal.classList.contains("is-hidden")) {
      closeAiAnalysisModal();
    }
  });
}

function renderTradeProfileGuide(profileId) {
  const container = document.getElementById("trade-profile-guide");
  if (!container) {
    return;
  }
  const profile = state.tradeProfiles.find((item) => item.profile_id === profileId);
  if (!profile) {
    container.innerHTML = '<p class="empty-state">--</p>';
    return;
  }
  container.innerHTML = `
    <article class="guide-card">
      <strong>${profile.display_name}</strong>
      <p>${profile.description}</p>
      <div class="tag-row">
        <span>${profile.broker}</span>
        <span>${profile.recommended_format}</span>
        <span>${profile.supported_extensions.join(" / ")}</span>
      </div>
      <ol class="guide-list">
        ${profile.export_steps.map((item) => `<li>${item}</li>`).join("")}
      </ol>
    </article>
  `;
}

function renderTradeProfiles(payload) {
  state.tradeProfiles = payload.profiles || [];
  const select = document.getElementById("trade-profile-select");
  if (!select) {
    return;
  }

  select.innerHTML = "";
  state.tradeProfiles.forEach((profile) => {
    const option = document.createElement("option");
    option.value = profile.profile_id;
    option.textContent = `${profile.display_name} · ${profile.recommended_format}`;
    select.appendChild(option);
  });
  select.addEventListener("change", () => renderTradeProfileGuide(select.value));

  if (state.tradeProfiles.length) {
    renderTradeProfileGuide(state.tradeProfiles[0].profile_id);
  }
}

function renderTradeMetrics(containerId, items) {
  const container = document.getElementById(containerId);
  if (!container) {
    return;
  }
  if (!items.length) {
    container.innerHTML = '<p class="empty-state">--</p>';
    return;
  }
  container.innerHTML = items
    .map(
      (item) => `
        <article class="metric-card">
          <strong>${item.label}</strong>
          <span>${item.value}</span>
          <p>${item.detail}</p>
        </article>
      `,
    )
    .join("");
}

function renderInsightList(containerId, items, type) {
  const container = document.getElementById(containerId);
  if (!container) {
    return;
  }
  if (!items.length) {
    container.innerHTML = '<p class="empty-state">--</p>';
    return;
  }
  container.innerHTML = items
    .map(
      (item) => `
        <article class="insight-card ${type}">
          <div class="event-head">
            <span>${type === "positive" ? "有效模式" : "错误模式"}</span>
            <span>${item.severity}</span>
          </div>
          <strong>${item.title}</strong>
          <p>${item.detail}</p>
        </article>
      `,
    )
    .join("");
}

function renderTradeBatches(items) {
  const container = document.getElementById("trade-batch-list");
  if (!container) {
    return;
  }
  if (!items.length) {
    container.innerHTML = '<p class="empty-state">--</p>';
    return;
  }
  container.innerHTML = items
    .map(
      (batch) => `
        <article class="batch-card">
          <div class="event-head">
            <span>${batch.broker}</span>
            <span>${formatDateTime(batch.imported_at)}</span>
          </div>
          <strong>${batch.filename}</strong>
          <p>${batch.imported_count} 条记录 · ${batch.symbol_count} 只股票 · ${batch.source_type.toUpperCase()}</p>
        </article>
      `,
    )
    .join("");
}

function renderTradeStyle(style) {
  const container = document.getElementById("trade-style-profile");
  if (!container) {
    return;
  }
  if (!style) {
    container.innerHTML = '<p class="empty-state">--</p>';
    return;
  }
  container.innerHTML = `
    <div class="style-title-row">
      <strong>${style.display_name}</strong>
      <span>${formatPercent(style.confidence)}</span>
    </div>
    <p>${style.summary}</p>
    <div class="tag-row">
      ${(style.traits || []).map((item) => `<span>${item}</span>`).join("")}
    </div>
  `;
}

function renderTradeRecommendations(items) {
  const container = document.getElementById("trade-recommendations");
  if (!container) {
    return;
  }
  if (!items.length) {
    container.innerHTML = "<li>--</li>";
    return;
  }
  container.innerHTML = items.map((item) => `<li>${item}</li>`).join("");
}

function renderTradeSidebarSummary(payload) {
  const container = document.getElementById("trade-sidebar-summary");
  if (!container) {
    return;
  }

  const chips = [];
  if (payload?.style_profile?.display_name) {
    chips.push({ text: payload.style_profile.display_name, primary: true });
  }
  if (payload?.summary_metrics?.[0]?.value) {
    chips.push({ text: `${payload.summary_metrics[0].label} ${payload.summary_metrics[0].value}` });
  }
  if (payload?.summary_metrics?.[1]?.value) {
    chips.push({ text: `${payload.summary_metrics[1].label} ${payload.summary_metrics[1].value}` });
  }
  if (payload?.latest_batch?.imported_count) {
    chips.push({ text: `最近导入 ${payload.latest_batch.imported_count} 条` });
  } else if (payload?.status === "demo") {
    chips.push({ text: "示例" });
  }

  container.innerHTML = chips.length
    ? chips
        .map(
          (item) =>
            `<span class="trade-summary-chip${item.primary ? " primary" : ""}">${item.text}</span>`,
        )
        .join("")
    : '<p class="empty-state">--</p>';
}

function renderTradeDiagnostics(payload) {
  state.tradeDiagnostics = payload;
  setText("trade-coverage-text", payload.coverage_text);
  renderTradeSidebarSummary(payload);
  renderTradeStyle(payload.style_profile);
  renderTradeMetrics("trade-summary-metrics", payload.summary_metrics || []);
  renderInsightList("trade-error-patterns", payload.error_patterns || [], "negative");
  renderInsightList("trade-effective-patterns", payload.effective_patterns || [], "positive");
  renderTradeRecommendations(payload.recommendations || []);
  renderTradeBatches(payload.recent_batches || []);
}

function setupTradeImportForm() {
  const form = document.getElementById("trade-import-form");
  const button = document.getElementById("trade-import-button");
  const status = document.getElementById("trade-import-status");
  const select = document.getElementById("trade-profile-select");
  const fileInput = document.getElementById("trade-file-input");
  if (!form || !button || !status || !select || !fileInput) {
    return;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const file = fileInput.files?.[0];
    if (!file) {
      status.textContent = "请先选择一个 CSV 或 XLSX 文件。";
      return;
    }

    button.disabled = true;
    button.textContent = "导入中";
    status.textContent = "处理中";

    try {
      const formData = new FormData();
      formData.append("profile_id", select.value);
      formData.append("file", file);
      const response = await fetchJson("/api/trade-diagnostics/import", {
        method: "POST",
        body: formData,
      });
      status.textContent = response.message;
      fileInput.value = "";
      await loadTradeDiagnostics();
    } catch (error) {
      console.error(error);
      status.textContent = error instanceof Error ? error.message : "导入失败，请稍后重试。";
    } finally {
      button.disabled = false;
      button.textContent = "导入";
    }
  });
}

async function loadTradeDiagnostics() {
  const payload = await fetchJson("/api/trade-diagnostics/summary");
  renderTradeDiagnostics(payload);
}

async function loadTradeProfiles() {
  const payload = await fetchJson("/api/trade-diagnostics/profiles");
  renderTradeProfiles(payload);
}

async function loadSignals(mode) {
  const signals = await fetchJson(`/api/signals/daily?mode=${encodeURIComponent(mode)}`);
  state.availableModes = signals.available_modes;
  state.selectedMode = signals.selected_mode;
  state.signals = signals.items;
  state.currentSymbol = signals.items[0]?.symbol ?? null;
  updateModeInUrl(state.selectedMode);

  renderModeToolbar(state.availableModes, state.selectedMode, async (nextMode) => {
    if (nextMode === state.selectedMode) {
      return;
    }
    try {
      await loadSignals(nextMode);
    } catch (error) {
      console.error(error);
      setText("signal-subtitle", error instanceof Error ? error.message : "策略模式切换失败");
    }
  });

  setText(
    "signal-subtitle",
    `${signals.trade_date} · ${signals.selected_mode_name}`,
  );
  setText("signal-count-value", String(Math.min(signals.items.length, 5)));

  const handleSelect = async (symbol) => {
    state.currentSymbol = symbol;
    renderSignalList(state.signals, state.currentSymbol, handleSelect);
    await loadDetail(symbol);
  };

  renderSignalList(state.signals, state.currentSymbol, handleSelect);

  if (state.currentSymbol) {
    await loadDetail(state.currentSymbol);
  } else {
    renderEmptyDetail();
  }
}

async function bootstrap() {
  try {
    const [regime, sectors] = await Promise.all([
      fetchJson("/api/market/regime"),
      fetchJson("/api/sectors/top"),
    ]);

    state.market = regime;
    state.sectors = sectors.items;

    setText("updated-at", `刷新：${formatDateTime(regime.updated_at)}`);
    renderMarketSentiment(regime.ai_sentiment);
    setText("exposure-value", formatPercent(regime.suggested_exposure));
    setText("breadth-value", regime.breadth_score.toFixed(1));
    setText("sentiment-breadth-metric", regime.breadth_score.toFixed(1));
    setText("sentiment-momentum-metric", regime.momentum_score.toFixed(1));
    setText("sentiment-northbound-metric", regime.northbound_score.toFixed(1));

    renderSectors(state.sectors);
    setupAiModal();
    setupAiRefreshButton();
    setupTradeAiAnalysisButton();
    setupTradeImportForm();

    await Promise.all([
      loadSignals(getModeFromUrl() || "balanced"),
      loadTradeProfiles(),
      loadTradeDiagnostics(),
    ]);
  } catch (error) {
    console.error(error);
    setText("signal-subtitle", error instanceof Error ? error.message : "页面加载失败");
    setText("trade-coverage-text", error instanceof Error ? error.message : "历史交易诊断加载失败");
  }
}

window.addEventListener("DOMContentLoaded", () => {
  void bootstrap();
});
