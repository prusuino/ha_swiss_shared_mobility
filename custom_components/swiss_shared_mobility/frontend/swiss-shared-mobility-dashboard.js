/* Swiss Shared Mobility — dashboard strategy for Home Assistant.
 *
 * The integration serves this file; register it once as a Lovelace resource
 * (Settings → Dashboards → Resources, type "JavaScript module"):
 *
 *     /swiss_shared_mobility_files/swiss-shared-mobility-dashboard.js
 *
 * Then create a dashboard whose raw configuration is
 *
 *     strategy:
 *       type: custom:swiss-shared-mobility
 *     views: []
 *
 * Everything below is kept inside one IIFE so its names never collide with
 * another integration shipping the same core in the global scope.
 */
(() => {
/* =====================================================================
 * Dashboard strategy core — shared building blocks
 * =====================================================================
 * A Lovelace dashboard strategy generates a dashboard in the browser at
 * render time. Nothing is written to .storage: the dashboard belongs to
 * the user, the integration only supplies the recipe.
 *
 * ⚠️ This block is duplicated into every integration that ships a
 * strategy. Each integration is its own HACS repository and must not
 * depend on another one being installed, so a shared file is not an
 * option. Keep the copies in sync and bump CORE_VERSION when the shared
 * part changes — it identifies which revision a copy was taken from.
 * ===================================================================== */

const CORE_VERSION = "1.1.1";

/* 1.1.1 - review follow-ups on the `strategy:` options
 *   (a) `map: false` only dropped the view with path "map". Where the map is
 *       a section inside another view (or a card in a panel view) it stayed
 *       visible. The option now also strips map cards out of every view: a
 *       section left with nothing but headings is dropped, and a view that
 *       ends up without any sections or cards is dropped as well.
 *   (b) The view flavour hardcoded max_columns: 2 and discarded the user's
 *       `max_columns`. It now uses the option when valid, else the value of
 *       the first sections view, else 2.
 *   (c) The view flavour copied only sections and cards, losing a view's
 *       `header` and `badges`. Both are carried over from the first view
 *       that has them. */

/* --- Registry access -------------------------------------------------
 * The registries are the only reliable way to find an integration's
 * entities: entity_id patterns are user-editable, unique_id is not.
 * Both calls are cheap and cached by the frontend for the render pass.
 */
async function loadRegistry(hass) {
  const [entities, devices] = await Promise.all([
    hass.callWS({ type: "config/entity_registry/list" }),
    hass.callWS({ type: "config/device_registry/list" }),
  ]);
  return { entities, devices };
}

/** All registry entries belonging to one integration (platform == domain). */
function entriesOfDomain(entities, domain) {
  return entities.filter((e) => e.platform === domain && !e.disabled_by);
}

/** Registry entries of one config entry, keyed by unique_id suffix.
 *  Mirrors the `f"{entry_id}_{suffix}"` convention the integrations use. */
function bySuffix(entities, configEntryId) {
  const out = {};
  const prefix = `${configEntryId}_`;
  for (const e of entities) {
    if (e.config_entry_id !== configEntryId) continue;
    if (typeof e.unique_id === "string" && e.unique_id.startsWith(prefix)) {
      out[e.unique_id.slice(prefix.length)] = e.entity_id;
    }
  }
  return out;
}

/** Group an integration's entities by the device they belong to.
 *  Returns [{device, entities:[registryEntry,...]}] sorted by device name. */
function groupByDevice(domainEntries, devices) {
  const byId = new Map(devices.map((d) => [d.id, d]));
  const groups = new Map();
  for (const e of domainEntries) {
    if (!e.device_id) continue;
    if (!groups.has(e.device_id)) groups.set(e.device_id, []);
    groups.get(e.device_id).push(e);
  }
  return [...groups.entries()]
    .map(([id, list]) => ({ device: byId.get(id), entities: list }))
    .filter((g) => g.device)
    .sort((a, b) => deviceName(a.device).localeCompare(deviceName(b.device)));
}

function deviceName(device) {
  return device.name_by_user || device.name || "";
}

/* --- Card helpers ---------------------------------------------------- */

const heading = (text, icon, badges) => {
  const card = { type: "heading", heading: text };
  if (icon) card.icon = icon;
  if (badges && badges.length) card.badges = badges;
  return card;
};

const grid = (cards, columnSpan) => {
  const section = { type: "grid", cards: cards.filter(Boolean) };
  if (columnSpan) section.column_span = columnSpan;
  return section;
};

const tile = (entity, extra = {}) => ({ type: "tile", entity, ...extra });

/** Map card fed from the integration's geo_location source.
 *  Deliberately uses geo_location_sources instead of an entity list: the
 *  markers are hidden entities, and the source keeps working when the
 *  set of markers changes between renders.
 *  labelAttribute writes the marker label into the source object, which is
 *  where the map card reads a geo-location source's label config from — the
 *  card-level label_mode only applies to `entities`. */
const mapCard = (domain, opts = {}) => ({
  type: "map",
  geo_location_sources: [
    opts.labelAttribute
      ? { source: domain, label_mode: "attribute", attribute: opts.labelAttribute }
      : domain,
  ],
  entities: opts.entities || ["zone.home"],
  default_zoom: opts.zoom ?? 8,
  theme_mode: "auto",
  grid_options: { columns: 12, rows: opts.rows ?? 6 },
});

/** Shown instead of an empty dashboard — an empty dashboard looks broken
 *  and gives the user nothing to act on. */
const emptyNotice = (text) => ({
  type: "markdown",
  content: text,
});

/* --- Localisation ----------------------------------------------------
 * Strategies run in the frontend, so hass.language is authoritative.
 * Falls back to English for any language the integration does not ship.
 */
function translator(strings, hass) {
  const lang = (hass.language || "en").split("-")[0];
  const table = strings[lang] || strings.en;
  return (key) => (table && table[key]) || (strings.en && strings.en[key]) || key;
}

/* --- Strategy base ---------------------------------------------------
 * Wraps the parts every strategy repeats: load registries, bail out
 * gracefully when the integration is not set up, and hand the concrete
 * strategy a prepared context.
 */

/* Options a user may put under `strategy:` in the raw configuration editor.
 * They are handled here in the core, so every integration supports the same
 * set without shipping its own option code:
 *
 *   map: false        drop the map: the full-screen map view as well as the
 *                     map cards inside section and panel views
 *   title: "..."      override the title
 *   max_columns: 3    column count of the generated section views (the view
 *                     flavour honours it too)
 *
 * Unknown keys are ignored on purpose - a strategy config is free-form, and a
 * typo should not take the dashboard down. */
const validColumns = (value) => {
  const cols = Number(value);
  return Number.isFinite(cols) && cols > 0 ? cols : undefined;
};

const isMapCard = (card) => Boolean(card) && card.type === "map";
const isHeadingCard = (card) => Boolean(card) && card.type === "heading";

/* Remove the map cards of one view. A section is dropped once only headings
 * remain - a heading merely labels the map that was just removed. Returns
 * null when nothing is left to show; views without a map card come back
 * untouched. */
const withoutMapCards = (view) => {
  let touched = false;
  const out = { ...view };
  if (Array.isArray(view.sections)) {
    out.sections = [];
    for (const section of view.sections) {
      const cards = Array.isArray(section.cards) ? section.cards : [];
      if (!cards.some(isMapCard)) {
        out.sections.push(section);
        continue;
      }
      touched = true;
      const rest = cards.filter((c) => !isMapCard(c));
      if (rest.some((c) => !isHeadingCard(c))) out.sections.push({ ...section, cards: rest });
    }
  }
  if (Array.isArray(view.cards) && view.cards.some(isMapCard)) {
    touched = true;
    out.cards = view.cards.filter((c) => !isMapCard(c));
  }
  if (!touched) return view;
  const empty = !(out.sections && out.sections.length) && !(out.cards && out.cards.length);
  return empty ? null : out;
};

const applyViewOptions = (views, config) => {
  const cfg = config || {};
  let out = views;
  if (cfg.map === false) {
    out = out
      .filter((v) => v.path !== "map")
      .map(withoutMapCards)
      .filter(Boolean);
  }
  const cols = validColumns(cfg.max_columns);
  if (cols) {
    out = out.map((v) => (v.type === "sections" ? { ...v, max_columns: cols } : v));
  }
  return out;
};

/* A view strategy must return exactly ONE view, while build() yields a list.
 * Section views are merged by concatenating their sections. A panel view (the
 * map) has no sections, so its cards become one full-width section instead -
 * that keeps the map visible rather than silently dropping it. */
const flattenToView = (views, title, icon, config) => {
  const sections = [];
  for (const v of views) {
    if (Array.isArray(v.sections) && v.sections.length) {
      sections.push(...v.sections);
    } else if (Array.isArray(v.cards) && v.cards.length) {
      sections.push(
        grid(
          v.cards.map((c) => ({
            ...c,
            grid_options: { columns: "full", rows: (c.grid_options || {}).rows ?? 8 },
          }))
        )
      );
    }
  }
  const sized = views.find((v) => v.type === "sections" && validColumns(v.max_columns));
  const view = {
    title,
    icon,
    type: "sections",
    max_columns: validColumns((config || {}).max_columns) ?? (sized ? validColumns(sized.max_columns) : 2),
    sections,
  };
  // header and badges live outside the sections and would be lost by the
  // merge above - keep the first ones the build produced.
  const withHeader = views.find((v) => v.header);
  if (withHeader) view.header = withHeader.header;
  const withBadges = views.find((v) => Array.isArray(v.badges) && v.badges.length);
  if (withBadges) view.badges = withBadges.badges;
  return view;
};

function defineDashboardStrategy(name, { domain, title, icon, build, strings, description }) {
  /* Shared by both strategy flavours: everything up to the finished view list. */
  const buildViews = async (config, hass) => {
    const t = translator(strings || {}, hass);
    let registry;
    try {
      registry = await loadRegistry(hass);
    } catch (err) {
      // Registry unreachable: render a readable message rather than
      // letting the dashboard fail with a blank screen.
      return [{ title: title, cards: [emptyNotice(`\u26a0\ufe0f ${err}`)] }];
    }
    const domainEntries = entriesOfDomain(registry.entities, domain);
    if (!domainEntries.length) {
      return [{ title: title, icon, cards: [emptyNotice(t("not_configured"))] }];
    }
    const views = await build({
      hass,
      config,
      t,
      domain,
      entities: domainEntries,
      devices: registry.devices,
      allEntities: registry.entities,
      helpers: { heading, grid, tile, mapCard, emptyNotice, bySuffix, groupByDevice, deviceName },
    });
    return applyViewOptions(views, config);
  };

  class Strategy extends HTMLElement {
    static async generate(config, hass) {
      const views = await buildViews(config, hass);
      return { title: (config && config.title) || title, views };
    }
  }

  /* The view flavour: fills a single view of a dashboard the user built
   * themselves, so adjusting the layout no longer requires "take control". */
  class ViewStrategy extends HTMLElement {
    static async generate(config, hass) {
      const views = await buildViews(config, hass);
      return flattenToView(views, (config && config.title) || title, icon, config);
    }
  }

  // getCreateSuggestions lets Home Assistant offer sensible defaults when the
  // strategy is picked from the "new dashboard" dialog.
  Strategy.getCreateSuggestions = () => ({ title, icon });

  customElements.define(`ll-strategy-dashboard-${name}`, Strategy);
  customElements.define(`ll-strategy-view-${name}`, ViewStrategy);

  // Announce the strategy to the frontend so it appears in the dashboard
  // creation dialog instead of having to be typed into the raw editor.
  window.customStrategies = window.customStrategies || [];
  if (!window.customStrategies.some((s) => s.type === name)) {
    window.customStrategies.push({
      type: name,
      strategyType: "dashboard",
      name: title,
      description: description || "",
    });
  }
  return Strategy;
}
/* =====================================================================
 * Dashboard strategy: Swiss Shared Mobility
 * =====================================================================
 * Generates the dashboard in the browser at render time: a map of the
 * vehicles currently reported around the configured areas, one section per
 * area (total, nearest vehicle, one tile per vehicle type) and one section
 * per favourite station. Nothing is written into the user's configuration;
 * adding or removing an entry changes the dashboard on the next load.
 *
 * Usage — create an empty dashboard, open the raw configuration editor and
 * replace its content with:
 *
 *     strategy:
 *       type: custom:swiss-shared-mobility
 *     views: []
 * ===================================================================== */

const SSM_STRINGS = {
  en: {
    map: "Map",
    areas: "Areas",
    stations: "Stations",
    attribution: "Data: sharedmobility.ch (Swiss Federal Office of Energy)",
    nothing_to_show:
      "### Nothing to show yet\n\nSwiss Shared Mobility is set up, but none of its areas or stations has a visible sensor. Check the integration's devices under **Settings → Devices & services**.",
    not_configured:
      "### Swiss Shared Mobility is not set up yet\n\nAdd the integration under **Settings → Devices & services** first. This dashboard then fills itself — there is nothing to configure here.",
  },
  de: {
    map: "Karte",
    areas: "Umkreise",
    stations: "Stationen",
    attribution: "Daten: sharedmobility.ch (Bundesamt für Energie)",
    nothing_to_show:
      "### Noch nichts anzuzeigen\n\nSwiss Shared Mobility ist eingerichtet, aber kein Umkreis und keine Station hat einen sichtbaren Sensor. Prüfe die Geräte der Integration unter **Einstellungen → Geräte & Dienste**.",
    not_configured:
      "### Swiss Shared Mobility ist noch nicht eingerichtet\n\nFüge die Integration zuerst unter **Einstellungen → Geräte & Dienste** hinzu. Dieses Dashboard füllt sich danach von selbst — hier ist nichts einzustellen.",
  },
  fr: {
    map: "Carte",
    areas: "Zones",
    stations: "Stations",
    attribution: "Données : sharedmobility.ch (Office fédéral de l'énergie)",
    nothing_to_show:
      "### Rien à afficher pour l'instant\n\nSwiss Shared Mobility est configuré, mais aucune zone ni aucune station n'a de capteur visible. Vérifiez les appareils de l'intégration sous **Paramètres → Appareils et services**.",
    not_configured:
      "### Swiss Shared Mobility n'est pas encore configuré\n\nAjoutez d'abord l'intégration sous **Paramètres → Appareils et services**. Ce tableau de bord se remplit ensuite tout seul.",
  },
  it: {
    map: "Mappa",
    areas: "Aree",
    stations: "Stazioni",
    attribution: "Dati: sharedmobility.ch (Ufficio federale dell'energia)",
    nothing_to_show:
      "### Ancora niente da mostrare\n\nSwiss Shared Mobility è configurato, ma nessuna area e nessuna stazione ha un sensore visibile. Controlla i dispositivi dell'integrazione in **Impostazioni → Dispositivi e servizi**.",
    not_configured:
      "### Swiss Shared Mobility non è ancora configurato\n\nAggiungi prima l'integrazione in **Impostazioni → Dispositivi e servizi**. Questa dashboard si riempie poi da sola.",
  },
};

/* Vehicle types in the integration's own order; a type added by a later
 * version sorts after them instead of disappearing. */
const SSM_CATEGORIES = ["bike", "e_bike", "cargo_bike", "e_scooter", "moped", "car", "other"];
const SSM_categoryRank = (key) => {
  const i = SSM_CATEGORIES.indexOf(key);
  return i < 0 ? SSM_CATEGORIES.length : i;
};

defineDashboardStrategy("swiss-shared-mobility", {
  domain: "swiss_shared_mobility",
  title: "Swiss Shared Mobility",
  icon: "mdi:bike",
  description:
    "Map of the vehicles around your areas, one section per area with total, nearest vehicle and a tile per vehicle type, and one section per favourite station.",
  strings: SSM_STRINGS,

  async build({ hass, t, domain, entities, devices, helpers }) {
    const { heading, grid, tile, mapCard, emptyNotice, groupByDevice, deviceName, bySuffix } = helpers;
    const views = [];

    // --- Map ----------------------------------------------------------
    // The markers are transient (vehicles move, so they have no registry
    // entry) and only exist while an area has "show on map" enabled and
    // vehicles are reported. Look at the live states rather than the
    // registry, and leave the view out when there is nothing to draw — an
    // empty map would just look broken.
    const states = hass && hass.states ? Object.values(hass.states) : [];
    const hasMarkers = states.some(
      (s) =>
        typeof s.entity_id === "string" &&
        s.entity_id.startsWith("geo_location.") &&
        s.attributes &&
        s.attributes.source === domain
    );
    if (hasMarkers) {
      views.push({
        title: t("map"),
        path: "map",
        icon: "mdi:map",
        type: "panel",
        // Areas are a few hundred metres across; zoom in accordingly and let
        // the card fit all markers (and the home zone) into view.
        cards: [{ ...mapCard(domain, { zoom: 14, rows: 12 }), auto_fit: true }],
      });
    }

    // --- One section per device ---------------------------------------
    // An area and a favourite station are each a device carrying the sensors
    // of one config entry. Only an area has the "nearest" sensor, which is
    // how the two kinds are told apart. Suffix lookup mirrors the
    // integration's `<entry_id>_<suffix>` unique ids, so renamed entity ids
    // keep working.
    const areaSections = [];
    const stationSections = [];
    for (const group of groupByDevice(entities, devices)) {
      const entryId = group.entities.find((e) => e.config_entry_id)?.config_entry_id;
      if (!entryId) continue;
      const ids = bySuffix(entities, entryId);
      const hidden = new Set(group.entities.filter((e) => e.hidden_by).map((e) => e.entity_id));
      const visible = (entityId) => (entityId && !hidden.has(entityId) ? entityId : null);
      const isArea = Boolean(ids.nearest);

      const cards = [];
      const totalId = visible(ids.available);
      const nearestId = visible(ids.nearest);
      if (totalId) cards.push(tile(totalId, { grid_options: { columns: isArea && nearestId ? 6 : "full" } }));
      if (nearestId) cards.push(tile(nearestId, { grid_options: { columns: 6 } }));
      // One tile per vehicle type: the `<type>_available` sensors.
      const typeKeys = Object.keys(ids)
        .filter((k) => k !== "available" && k.endsWith("_available"))
        .map((k) => k.slice(0, -"_available".length))
        .sort((a, b) => SSM_categoryRank(a) - SSM_categoryRank(b) || a.localeCompare(b));
      for (const key of typeKeys) {
        const id = visible(ids[`${key}_available`]);
        if (id) cards.push(tile(id, { grid_options: { columns: 6 } }));
      }
      if (!cards.length) continue;
      const section = grid([
        heading(deviceName(group.device), isArea ? "mdi:map-marker-radius" : "mdi:map-marker-check"),
        ...cards,
      ]);
      (isArea ? areaSections : stationSections).push(section);
    }

    if (areaSections.length) {
      views.push({
        title: t("areas"),
        path: "areas",
        icon: "mdi:map-marker-radius",
        type: "sections",
        max_columns: 2,
        sections: areaSections,
      });
    }
    if (stationSections.length) {
      views.push({
        title: t("stations"),
        path: "stations",
        icon: "mdi:map-marker-check",
        type: "sections",
        max_columns: 2,
        sections: stationSections,
      });
    }

    if (!views.length) {
      return [{ title: t("areas"), cards: [emptyNotice(t("nothing_to_show"))] }];
    }
    // sharedmobility.ch's terms require the source to be cited wherever its
    // data is shown; put it once at the bottom of the last section view.
    const last = views[views.length - 1];
    if (last.sections) {
      last.sections.push(grid([{ type: "markdown", text_only: true, content: t("attribution") }], 2));
    }
    return views;
  },
});
})();
