// ============================================================
// Rad Fantasy internal tool — app.js
// ============================================================

const TEAM_NAMES = {
  ARI: "Arizona Cardinals", ARZ: "Arizona Cardinals",
  ATL: "Atlanta Falcons", BAL: "Baltimore Ravens", BUF: "Buffalo Bills",
  CAR: "Carolina Panthers", CHI: "Chicago Bears", CIN: "Cincinnati Bengals",
  CLE: "Cleveland Browns", DAL: "Dallas Cowboys", DEN: "Denver Broncos",
  DET: "Detroit Lions", GB: "Green Bay Packers", HOU: "Houston Texans",
  IND: "Indianapolis Colts", JAC: "Jacksonville Jaguars", JAX: "Jacksonville Jaguars",
  KC: "Kansas City Chiefs", LV: "Las Vegas Raiders", OAK: "Las Vegas Raiders",
  LAC: "Los Angeles Chargers", SD: "Los Angeles Chargers",
  LA: "Los Angeles Rams", LAR: "Los Angeles Rams", STL: "Los Angeles Rams",
  MIA: "Miami Dolphins", MIN: "Minnesota Vikings", NE: "New England Patriots",
  NO: "New Orleans Saints", NYG: "New York Giants", NYJ: "New York Jets",
  PHI: "Philadelphia Eagles", PIT: "Pittsburgh Steelers", SEA: "Seattle Seahawks",
  SF: "San Francisco 49ers", TB: "Tampa Bay Buccaneers", TEN: "Tennessee Titans",
  WAS: "Washington Commanders",
};
function teamName(code) { return TEAM_NAMES[code] || code; }

// Real team brand colors (factual data, not copyrighted) -- used for badge
// styling. Logos themselves are copyrighted trademarks and are NOT
// included; if you add your own logo image files to the repo (e.g.
// assets/logos/DEN.png), the badge renderer below can be extended to show
// them instead.
const TEAM_COLORS = {
  ARI: "#97233F", ATL: "#A71930", BAL: "#241773", BUF: "#00338D", CAR: "#0085CA",
  CHI: "#0B162A", CIN: "#FB4F14", CLE: "#FF3C00", DAL: "#041E42", DEN: "#FB4F14",
  DET: "#0076B6", GB: "#203731", HOU: "#03202F", IND: "#002C5F",
  JAC: "#101820", JAX: "#101820", KC: "#E31837", LV: "#000000", OAK: "#000000",
  LAC: "#0080C6", SD: "#0080C6", LA: "#003594", LAR: "#003594", STL: "#003594",
  MIA: "#008E97", MIN: "#4F2683", NE: "#002244", NO: "#D3BC8D", NYG: "#0B2265",
  NYJ: "#125740", PHI: "#004C54", PIT: "#FFB612", SEA: "#002244", SF: "#AA0000",
  TB: "#D50A0A", TEN: "#0C2340", WAS: "#5A1414",
};
function teamColor(code) { return TEAM_COLORS[code] || "#5A6068"; }
function contrastText(hex) {
  const [r, g, b] = hexToRgb(hex);
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.55 ? "#1C2B36" : "#F7F7F6";
}

// Position accent colors -- distinct hues, deliberately NOT overlapping the
// red/green gradient scale (so a colored position badge is never confused
// with a "good/bad" signal). Used for both the leaderboard's position badge
// and the ADP-vs-points scatter chart, so the two views agree visually.
const POSITION_COLORS = {
  QB: "#3D6C94", RB: "#6B4E9C", WR: "#80BEE4", TE: "#C97B3D", K: "#5A6068",
};
function teamBadge(code) {
  return `<span class="cell-badge" style="background:${teamColor(code)};color:${contrastText(teamColor(code))}">${code}</span>`;
}
function positionBadge(pos) {
  const color = POSITION_COLORS[pos] || "#5A6068";
  return `<span class="cell-badge" style="background:${color};color:${contrastText(color)}">${pos}</span>`;
}

// ---- gradient utility (red/green heatmap, reusing the existing brand's
// win-green #4A8A5A and loss-red #C04A4A rather than introducing new hues) ----
function hexToRgb(hex) {
  const n = parseInt(hex.replace("#", ""), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}
function rgbToHex(rgb) {
  return "#" + rgb.map(x => Math.max(0, Math.min(255, Math.round(x))).toString(16).padStart(2, "0")).join("");
}
function lerp(a, b, t) { return a + (b - a) * t; }

const GRADIENT_BAD = hexToRgb("#C04A4A");
const GRADIENT_MID = [239, 239, 238];
const GRADIENT_GOOD = hexToRgb("#4A8A5A");

function gradientColor(value, min, max, invert = false) {
  if (min === max || value === null || value === undefined || Number.isNaN(value)) return "transparent";
  let t = (value - min) / (max - min);
  t = Math.max(0, Math.min(1, t));
  if (invert) t = 1 - t;
  const rgb = t < 0.5
    ? GRADIENT_BAD.map((c, i) => lerp(c, GRADIENT_MID[i], t / 0.5))
    : GRADIENT_MID.map((c, i) => lerp(c, GRADIENT_GOOD[i], (t - 0.5) / 0.5));
  return rgbToHex(rgb);
}

// ---- data cache + fetch helper ----
const cache = {};
async function fetchJSON(path) {
  if (cache[path]) return cache[path];
  const res = await fetch(path);
  if (!res.ok) throw new Error(`Failed to fetch ${path}: ${res.status}`);
  const data = await res.json();
  cache[path] = data;
  return data;
}

// ---- generic helpers ----
function fmt(n, decimals = 1) {
  if (n === null || n === undefined || Number.isNaN(n)) return "-";
  return Number(n).toFixed(decimals);
}
function normalizeName(name) {
  return name
    .replace(/\s+(Jr\.?|Sr\.?|II|III|IV|V)\.?\s*$/i, "")
    .replace(/[.']/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

// ============================================================
// TAB SWITCHING
// ============================================================
const initedViews = new Set();

document.getElementById("groupTabs").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-group]");
  if (!btn) return;
  document.querySelectorAll("#groupTabs button").forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  document.querySelectorAll(".tab-group").forEach(g => g.style.display = "none");
  const groupEl = document.getElementById(`group-${btn.dataset.group}`);
  groupEl.style.display = "block";
  // The default-active sub-tab within this group was never "clicked", so its
  // view was never lazy-initialized -- do that now if this is the first visit.
  const activeSubBtn = groupEl.querySelector(".sub-tabs button.active");
  if (activeSubBtn) initView(activeSubBtn.dataset.view);
});

function wireSubTabs(containerId, onShow) {
  document.getElementById(containerId).addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-view]");
    if (!btn) return;
    const container = document.getElementById(containerId);
    container.querySelectorAll("button").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    const group = container.parentElement;
    group.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
    const viewEl = document.getElementById(`view-${btn.dataset.view}`);
    viewEl.classList.add("active");
    onShow(btn.dataset.view);
  });
}
wireSubTabs("rankingsSubTabs", (view) => initView(view));
wireSubTabs("trendsSubTabs", (view) => initView(view));

function initView(view) {
  if (initedViews.has(view)) return;
  initedViews.add(view);
  ({ sos: initSOS, ol: initOL, dst: initDST, leaderboard: initLeaderboard, scatter: initScatter })[view]();
}

// ============================================================
// RANKING CARD RENDERER (shared by SOS / OL / DST)
// ============================================================
function renderRankCard(container, { title, subtitle, bestRows, hardRows, footnote }) {
  const rowHtml = (r, variant) => `
    <div class="rank-row">
      <div class="rank-num ${variant}">${r.rank}</div>
      <div class="rank-badge" style="background:${teamColor(r.team)};color:${contrastText(teamColor(r.team))}">${r.team}</div>
      <div class="rank-name">${teamName(r.team)}</div>
      <div class="rank-metric">${r.metric}</div>
    </div>`;
  container.innerHTML = `
    <div class="card-title">${title}</div>
    <div class="card-sub">${subtitle}</div>
    <div class="section-label best">Best</div>
    ${bestRows.map(r => rowHtml(r, "best")).join("")}
    <div class="section-label hard">Worst</div>
    ${hardRows.map(r => rowHtml(r, "hard")).join("")}
    <div class="footnote">${footnote}</div>
  `;
}

function renderSortableTable(container, { columns, rows, defaultSortKey, defaultSortDir = -1 }) {
  let sortKey = defaultSortKey;
  let sortDir = defaultSortDir;

  // Precompute min/max for every gradient-enabled column, over the current rows.
  function computeRanges() {
    const ranges = {};
    columns.forEach(c => {
      if (!c.gradient) return;
      const values = rows.map(r => r[c.key]).filter(v => typeof v === "number" && !Number.isNaN(v));
      if (values.length) ranges[c.key] = { min: Math.min(...values), max: Math.max(...values) };
    });
    return ranges;
  }

  function draw() {
    const ranges = computeRanges();
    const sortCol = columns.find(c => c.key === sortKey);
    const isNumeric = sortCol ? !!sortCol.numeric : (rows.length > 0 && typeof rows[0][sortKey] === "number");
    const sorted = isNumeric
      ? [...rows].sort((a, b) => {
          const av = a[sortKey], bv = b[sortKey];
          if (av === null || av === undefined) return 1;
          if (bv === null || bv === undefined) return -1;
          return (av - bv) * sortDir;
        })
      : [...rows].sort((a, b) => (String(a[sortKey]) > String(b[sortKey]) ? 1 : -1) * sortDir);

    let html = `<table><thead><tr>`;
    columns.forEach(c => {
      html += `<th data-key="${c.key}" class="${c.key === sortKey ? 'sorted' : ''}">${c.label}</th>`;
    });
    html += `</tr></thead><tbody>`;
    sorted.forEach(row => {
      html += "<tr>";
      columns.forEach(c => {
        const val = c.render ? c.render(row) : row[c.key];
        let style = "";
        if (c.gradient && ranges[c.key]) {
          const bg = gradientColor(row[c.key], ranges[c.key].min, ranges[c.key].max, c.invert);
          style = `style="background:${bg}"`;
        }
        html += `<td class="${c.numeric ? 'num' : ''}" ${style}>${val}</td>`;
      });
      html += "</tr>";
    });
    html += "</tbody></table>";
    container.innerHTML = html;

    container.querySelectorAll("th[data-key]").forEach(th => {
      th.addEventListener("click", () => {
        const key = th.dataset.key;
        sortDir = sortKey === key ? -sortDir : -1;
        sortKey = key;
        draw();
      });
    });
  }
  draw();
}

// ============================================================
// SOS VIEW
// ============================================================
const SOS_POSITIONS = [
  { key: "passing_sos", label: "Passing", unit: "pts/gm to QB" },
  { key: "rushing_sos", label: "Rushing", unit: "pts/gm to RB" },
  { key: "receiving_wr_sos", label: "Receiving (WR)", unit: "pts/gm to WR" },
  { key: "receiving_te_sos", label: "Receiving (TE)", unit: "pts/gm to TE" },
  { key: "kicking_sos", label: "Kicking", unit: "pts/gm to K" },
  { key: "dst_sos", label: "D/ST", unit: "composite" },
];
let sosData = null;
let sosCurrentPos = "rushing_sos";
let sosCurrentWindow = "full_season";

async function initSOS() {
  const toggle = document.getElementById("sosPositionToggle");
  toggle.innerHTML = SOS_POSITIONS.map((p) =>
    `<button data-pos="${p.key}" class="${p.key === sosCurrentPos ? 'active' : ''}">${p.label}</button>`
  ).join("");
  toggle.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-pos]");
    if (!btn) return;
    toggle.querySelectorAll("button").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    sosCurrentPos = btn.dataset.pos;
    renderSOS();
  });

  document.getElementById("sosWindowToggle").addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-window]");
    if (!btn) return;
    document.querySelectorAll("#sosWindowToggle button").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    sosCurrentWindow = btn.dataset.window;
    renderSOS();
  });

  document.getElementById("sosCard").innerHTML = `<div class="loading">Loading...</div>`;
  sosData = await fetchJSON("data/context/strength_of_schedule_2026.json");
  renderSOS();

  initScheduleView();
}

// ---- team schedule sub-section within SOS ----
let scheduleData = null;
let scheduleCurrentWindow = "full_season";

async function initScheduleView() {
  const teamSelect = document.getElementById("scheduleTeamSelect");
  const teams = Object.keys(TEAM_NAMES).filter(c => !["JAC","OAK","SD","STL","LAR"].includes(c)); // canonical codes only, avoid duplicate aliases
  teamSelect.innerHTML = teams.sort((a,b) => teamName(a).localeCompare(teamName(b)))
    .map(c => `<option value="${c}">${teamName(c)}</option>`).join("");
  teamSelect.addEventListener("change", renderSchedule);

  document.getElementById("scheduleWindowToggle").addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-window]");
    if (!btn) return;
    document.querySelectorAll("#scheduleWindowToggle button").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    scheduleCurrentWindow = btn.dataset.window;
    renderSchedule();
  });

  document.getElementById("scheduleDisplay").innerHTML = `<div class="loading">Loading schedule...</div>`;
  try {
    scheduleData = await fetchJSON("data/context/schedule_2026.json");
    renderSchedule();
  } catch (err) {
    document.getElementById("scheduleDisplay").innerHTML =
      `<div class="loading">2026 schedule data not available yet (data/context/schedule_2026.json). ` +
      `Run generate_schedule_2026.py and add the output to your repo to enable this view.</div>`;
  }
}

function renderSchedule() {
  if (!scheduleData) return;
  const team = document.getElementById("scheduleTeamSelect").value;
  const teamSchedule = scheduleData.find(t => t.team === team);
  if (!teamSchedule) {
    document.getElementById("scheduleDisplay").innerHTML = `<div class="loading">No schedule found for ${teamName(team)}.</div>`;
    return;
  }

  const weeks = scheduleCurrentWindow === "full_season"
    ? teamSchedule.weeks
    : teamSchedule.weeks.filter(w => w.week >= 15 && w.week <= 17);

  const rowHtml = (w) => {
    if (w.is_bye) {
      return `<div class="schedule-row bye">
        <div class="sched-week">Wk ${w.week}</div>
        <div class="sched-opp">Bye</div>
      </div>`;
    }
    return `<div class="schedule-row">
      <div class="sched-week">Wk ${w.week}</div>
      <div class="sched-badge" style="background:${teamColor(w.opponent)};color:${contrastText(teamColor(w.opponent))}">${w.opponent}</div>
      <div class="sched-opp">${teamName(w.opponent)}</div>
      <div class="sched-loc">${w.is_home ? "Home" : "Away"}</div>
    </div>`;
  };

  document.getElementById("scheduleDisplay").innerHTML = weeks.map(rowHtml).join("");
}

function renderSOS() {
  const posInfo = SOS_POSITIONS.find(p => p.key === sosCurrentPos);
  const isDst = sosCurrentPos === "dst_sos";

  const rows = sosData.map(r => {
    const entry = r[sosCurrentPos][sosCurrentWindow];
    if (isDst) {
      return {
        team: r.team, rank: entry.composite_rank,
        points: entry.avg_opponent_points_scored.value,
        give: entry.avg_opponent_giveaways_per_game.value,
        sacks: entry.avg_opponent_sacks_allowed_per_game.value,
      };
    }
    return { team: r.team, rank: entry.rank, value: entry.value };
  }).filter(r => r.rank !== null && r.rank !== undefined);

  rows.sort((a, b) => a.rank - b.rank);
  const best = rows.slice(0, 5);
  const worst = rows.slice(-5).reverse();

  const metricLabel = (r) => isDst ? `${fmt(r.points)} pts allowed` : `${fmt(r.value, 2)} ${posInfo.unit}`;

  renderRankCard(document.getElementById("sosCard"), {
    title: `${posInfo.label} SOS`,
    subtitle: `2026 Projected — ${sosCurrentWindow === "full_season" ? "Full season" : "Fantasy playoff weeks (15-17)"}`,
    bestRows: best.map(r => ({ rank: r.rank, team: r.team, metric: metricLabel(r) })),
    hardRows: worst.map(r => ({ rank: r.rank, team: r.team, metric: metricLabel(r) })),
    footnote: isDst
      ? "Composite of opponent points scored, giveaways/gm, and sacks-allowed/gm (each ranked, then averaged). Based on each 2026 opponent's actual 2025 offense."
      : `Average PPR fantasy points allowed to ${posInfo.label.split(' ')[0]} per game, based on each 2026 opponent's actual 2025 defense.`,
  });

  const columns = isDst
    ? [
        { key: "rank", label: "Rank", numeric: true, gradient: true, invert: true },
        { key: "team", label: "Team", render: r => teamName(r.team) },
        { key: "points", label: "Pts Allowed", numeric: true, gradient: true, invert: true, render: r => fmt(r.points) },
        { key: "give", label: "Giveaways/gm", numeric: true, gradient: true, render: r => fmt(r.give, 2) },
        { key: "sacks", label: "Sacks Allowed/gm", numeric: true, gradient: true, render: r => fmt(r.sacks, 2) },
      ]
    : [
        { key: "rank", label: "Rank", numeric: true, gradient: true, invert: true },
        { key: "team", label: "Team", render: r => teamName(r.team) },
        { key: "value", label: posInfo.unit, numeric: true, gradient: true, render: r => fmt(r.value, 2) },
      ];

  renderSortableTable(document.getElementById("sosTable"), { columns, rows, defaultSortKey: "rank", defaultSortDir: 1 });
}

// ============================================================
// OL VIEW
// ============================================================
let olData2026 = null, olData2025 = null;
let olCurrentYear = "2026";

async function initOL() {
  document.getElementById("olYearToggle").addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-year]");
    if (!btn) return;
    document.querySelectorAll("#olYearToggle button").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    olCurrentYear = btn.dataset.year;
    renderOL();
  });

  document.getElementById("olCard").innerHTML = `<div class="loading">Loading...</div>`;
  [olData2026, olData2025] = await Promise.all([
    fetchJSON("data/context/offensive_line_rankings_2026.json"),
    fetchJSON("data/context/offensive_line_rankings_2025.json"),
  ]);
  renderOL();
}

function renderOL() {
  const is2026 = olCurrentYear === "2026";
  const data = is2026 ? olData2026 : olData2025;

  const rows = is2026
    ? data.map(r => ({
        team: r.team, rank: r.consensus_rank,
        fp_rank: r.sources.fantasypros?.rank ?? null,
        sf_rank: r.sources.stackedfantasy?.rank ?? null,
        pff_rank: r.sources.pff_4for4?.overall?.rank ?? null,
        ftn_rank: r.sources.ftnfantasy?.rank ?? null,
      }))
    : data.map(r => ({ team: r.team, rank: r.ol_rank }));

  rows.sort((a, b) => a.rank - b.rank);
  const best = rows.slice(0, 5);
  const worst = rows.slice(-5).reverse();

  renderRankCard(document.getElementById("olCard"), {
    title: `Offensive Line — ${olCurrentYear}`,
    subtitle: is2026 ? "2026 Projected — preseason projection (4-source blend)" : "2025 Actual — end-of-season performance (PFF)",
    bestRows: best.map(r => ({ rank: fmt(r.rank, is2026 ? 1 : 0), team: r.team, metric: "" })),
    hardRows: worst.map(r => ({ rank: fmt(r.rank, is2026 ? 1 : 0), team: r.team, metric: "" })),
    footnote: is2026
      ? "Consensus of FantasyPros, StackedFantasy, 4for4/PFF grades, and FTN Fantasy rankings, averaged by rank. Projection for a season not yet played."
      : "PFF's actual end-of-season offensive line rankings. Reflects real 2025 performance.",
  });

  const columns = is2026
    ? [
        { key: "rank", label: "Consensus", numeric: true, gradient: true, invert: true, render: r => fmt(r.rank, 1) },
        { key: "team", label: "Team", render: r => teamName(r.team) },
        { key: "fp_rank", label: "FantasyPros", numeric: true, gradient: true, invert: true, render: r => r.fp_rank ?? "-" },
        { key: "sf_rank", label: "StackedFantasy", numeric: true, gradient: true, invert: true, render: r => r.sf_rank ?? "-" },
        { key: "pff_rank", label: "4for4/PFF", numeric: true, gradient: true, invert: true, render: r => r.pff_rank ?? "-" },
        { key: "ftn_rank", label: "FTN Fantasy", numeric: true, gradient: true, invert: true, render: r => r.ftn_rank ?? "-" },
      ]
    : [
        { key: "rank", label: "Rank", numeric: true, gradient: true, invert: true },
        { key: "team", label: "Team", render: r => teamName(r.team) },
      ];
  renderSortableTable(document.getElementById("olTable"), { columns, rows, defaultSortKey: "rank", defaultSortDir: 1 });
}

// ============================================================
// D/ST VIEW
// ============================================================
let dstData = null;

async function initDST() {
  document.getElementById("dstCard").innerHTML = `<div class="loading">Loading...</div>`;
  dstData = await fetchJSON("data/stats/team_defense_season_stats.json");

  const seasons = [...new Set(dstData.map(r => r.season))].sort((a, b) => b - a);
  const select = document.getElementById("dstSeasonSelect");
  select.innerHTML = seasons.map(s => `<option value="${s}">${s}</option>`).join("");
  select.addEventListener("change", renderDST);
  renderDST();
}

function renderDST() {
  const season = Number(document.getElementById("dstSeasonSelect").value);
  const rows = dstData
    .filter(r => r.season === season)
    .map(r => ({
      team: r.team, fantasy_points: r.fantasy_points, sacks: r.raw_stats.sacks,
      interceptions: r.raw_stats.interceptions, fumbles_recovered: r.raw_stats.fumbles_recovered,
      def_tds: r.raw_stats.def_tds, points_allowed: r.raw_stats.points_allowed,
      yards_allowed: r.raw_stats.yards_allowed,
    }));

  const ranked = [...rows].sort((a, b) => b.fantasy_points - a.fantasy_points)
    .map((r, i) => ({ ...r, rank: i + 1 }));

  const best = ranked.slice(0, 5);
  const worst = ranked.slice(-5).reverse();

  renderRankCard(document.getElementById("dstCard"), {
    title: `D/ST — ${season}`,
    subtitle: "Ranked by fantasy points, your custom scoring rules",
    bestRows: best.map(r => ({ rank: r.rank, team: r.team, metric: `${fmt(r.fantasy_points)} pts` })),
    hardRows: worst.map(r => ({ rank: r.rank, team: r.team, metric: `${fmt(r.fantasy_points)} pts` })),
    footnote: "Sacks (1pt), INTs (2pt), fumble recoveries (2pt), def TDs (6pt), plus tiered points/yards-allowed bonuses. Actual real-season results, not a projection.",
  });

  const columns = [
    { key: "rank", label: "Rank", numeric: true, gradient: true, invert: true },
    { key: "team", label: "Team", render: r => teamName(r.team) },
    { key: "fantasy_points", label: "Fantasy Pts", numeric: true, gradient: true, render: r => fmt(r.fantasy_points) },
    { key: "sacks", label: "Sacks", numeric: true, gradient: true },
    { key: "interceptions", label: "INT", numeric: true, gradient: true },
    { key: "fumbles_recovered", label: "FR", numeric: true, gradient: true },
    { key: "def_tds", label: "Def TD", numeric: true, gradient: true },
    { key: "points_allowed", label: "Pts Allowed", numeric: true, gradient: true, invert: true },
    { key: "yards_allowed", label: "Yds Allowed", numeric: true, gradient: true, invert: true },
  ];
  renderSortableTable(document.getElementById("dstTable"), { columns, rows: ranked, defaultSortKey: "fantasy_points", defaultSortDir: -1 });
}

// ============================================================
// PLAYER LEADERBOARD VIEW
// ============================================================
let playerSeasonData = null;

const LEADERBOARD_COLUMNS = {
  QB: [
    { key: "attempts", label: "Pass Att", numeric: true, gradient: true },
    { key: "passing_yards", label: "Pass Yds", numeric: true, gradient: true },
    { key: "passing_tds", label: "Pass TD", numeric: true, gradient: true },
    { key: "interceptions", label: "INT", numeric: true, gradient: true, invert: true },
    { key: "rushing_yards", label: "Rush Yds", numeric: true, gradient: true },
    { key: "rushing_tds", label: "Rush TD", numeric: true, gradient: true },
  ],
  RB: [
    { key: "carries", label: "Carries", numeric: true, gradient: true },
    { key: "rushing_yards", label: "Rush Yds", numeric: true, gradient: true },
    { key: "rushing_tds", label: "Rush TD", numeric: true, gradient: true },
    { key: "targets", label: "Tgt", numeric: true, gradient: true },
    { key: "receptions", label: "Rec", numeric: true, gradient: true },
    { key: "receiving_yards", label: "Rec Yds", numeric: true, gradient: true },
    { key: "receiving_tds", label: "Rec TD", numeric: true, gradient: true },
  ],
  WR: [
    { key: "targets", label: "Tgt", numeric: true, gradient: true },
    { key: "receptions", label: "Rec", numeric: true, gradient: true },
    { key: "receiving_yards", label: "Rec Yds", numeric: true, gradient: true },
    { key: "receiving_tds", label: "Rec TD", numeric: true, gradient: true },
  ],
  TE: [
    { key: "targets", label: "Tgt", numeric: true, gradient: true },
    { key: "receptions", label: "Rec", numeric: true, gradient: true },
    { key: "receiving_yards", label: "Rec Yds", numeric: true, gradient: true },
    { key: "receiving_tds", label: "Rec TD", numeric: true, gradient: true },
  ],
  K: [
    { key: "fg_made", label: "FG Made", numeric: true, gradient: true },
    { key: "fg_attempts", label: "FG Att", numeric: true, gradient: true },
    { key: "fg_pct", label: "FG %", numeric: true, gradient: true, render: r => r.fg_pct === null ? "-" : `${fmt(r.fg_pct, 0)}%` },
    { key: "pat_made", label: "PAT Made", numeric: true, gradient: true },
    { key: "pat_attempts", label: "PAT Att", numeric: true, gradient: true },
  ],
};

async function initLeaderboard() {
  document.getElementById("lbTable").innerHTML = `<div class="loading">Loading...</div>`;
  playerSeasonData = await fetchJSON("data/stats/player_season_stats.json");

  const seasons = [...new Set(playerSeasonData.map(r => r.season))].sort((a, b) => b - a);
  const select = document.getElementById("lbSeasonSelect");
  select.innerHTML = seasons.map(s => `<option value="${s}">${s}</option>`).join("");

  document.getElementById("lbSeasonSelect").addEventListener("change", renderLeaderboard);
  document.getElementById("lbPositionSelect").addEventListener("change", renderLeaderboard);
  document.getElementById("lbScoringSelect").addEventListener("change", renderLeaderboard);
  document.getElementById("lbSearch").addEventListener("input", renderLeaderboard);

  renderLeaderboard();
}

function extractRowForPosition(r, position, scoring) {
  const base = {
    player_name: r.player_name, team: r.team, position: r.position,
    games_played: r.games_played, fantasy_points: r.fantasy_points[scoring],
  };
  if (position === "K") {
    const k = r.raw_stats.kicking;
    return {
      ...base,
      fg_made: k ? k.fg_made : null, fg_attempts: k ? k.fg_attempts : null,
      fg_pct: (k && k.fg_attempts) ? (100 * k.fg_made / k.fg_attempts) : null,
      pat_made: k ? k.pat_made : null, pat_attempts: k ? k.pat_attempts : null,
    };
  }
  return {
    ...base,
    attempts: r.raw_stats.attempts, passing_yards: r.raw_stats.passing_yards,
    passing_tds: r.raw_stats.passing_tds, interceptions: r.raw_stats.interceptions,
    carries: r.raw_stats.carries, rushing_yards: r.raw_stats.rushing_yards,
    rushing_tds: r.raw_stats.rushing_tds, targets: r.raw_stats.targets,
    receptions: r.raw_stats.receptions, receiving_yards: r.raw_stats.receiving_yards,
    receiving_tds: r.raw_stats.receiving_tds,
  };
}

function renderLeaderboard() {
  const season = Number(document.getElementById("lbSeasonSelect").value);
  const position = document.getElementById("lbPositionSelect").value;
  const scoring = document.getElementById("lbScoringSelect").value;
  const search = document.getElementById("lbSearch").value.trim().toLowerCase();

  let rows = playerSeasonData.filter(r => r.season === season && r.position === position);
  if (search) rows = rows.filter(r => r.player_name.toLowerCase().includes(search));

  rows = rows.map(r => extractRowForPosition(r, position, scoring));

  const columns = [
    { key: "player_name", label: "Player" },
    { key: "team", label: "Team", render: r => teamBadge(r.team) },
    { key: "position", label: "Pos", render: r => positionBadge(r.position) },
    { key: "games_played", label: "GP", numeric: true },
    ...LEADERBOARD_COLUMNS[position],
    { key: "fantasy_points", label: "Fantasy Pts", numeric: true, gradient: true, render: r => fmt(r.fantasy_points) },
  ];
  renderSortableTable(document.getElementById("lbTable"), { columns, rows, defaultSortKey: "fantasy_points", defaultSortDir: -1 });
}

// ============================================================
// ADP VS POINTS SCATTER VIEW
// ============================================================
let adpData = null, scatterChartInstance = null;

async function initScatter() {
  const results = await Promise.all([
    fetchJSON("data/adp/adp_fantasypros.json"),
    playerSeasonData ? Promise.resolve(playerSeasonData) : fetchJSON("data/stats/player_season_stats.json"),
  ]);
  adpData = results[0];
  playerSeasonData = results[1];

  const years = [...new Set(adpData.map(r => r.year))].sort((a, b) => b - a);
  const select = document.getElementById("scatterSeasonSelect");
  select.innerHTML = years.map(y => `<option value="${y}">${y}</option>`).join("");

  document.getElementById("scatterSeasonSelect").addEventListener("change", renderScatter);
  document.getElementById("scatterPositionSelect").addEventListener("change", renderScatter);

  renderScatter();
}

function renderScatter() {
  const year = Number(document.getElementById("scatterSeasonSelect").value);
  const position = document.getElementById("scatterPositionSelect").value;

  const adpRows = adpData.filter(r => r.year === year && r.position !== "DST" && r.position !== "K");
  const statsLookup = new Map();
  playerSeasonData.filter(r => r.season === year).forEach(r => {
    statsLookup.set(normalizeName(r.player_name), r);
  });

  const matched = [];
  adpRows.forEach(a => {
    const stat = statsLookup.get(normalizeName(a.player_name));
    if (stat) matched.push({ name: a.player_name, position: a.position, adp: a.adp, points: stat.fantasy_points.ppr });
  });

  const filtered = position === "ALL" ? matched : matched.filter(m => m.position === position);

  const positions = position === "ALL" ? ["QB", "RB", "WR", "TE"] : [position];
  const datasets = positions.map(pos => ({
    label: pos,
    data: filtered.filter(m => m.position === pos).map(m => ({ x: m.adp, y: m.points, name: m.name })),
    backgroundColor: POSITION_COLORS[pos],
  }));

  if (scatterChartInstance) scatterChartInstance.destroy();

  if (typeof Chart === "undefined") {
    document.getElementById("scatterFallbackMsg").style.display = "block";
    document.getElementById("scatterFallbackMsg").textContent =
      "Chart.js failed to load (no network access?). Data join itself is unaffected -- see match count below.";
  } else {
    document.getElementById("scatterFallbackMsg").style.display = "none";
    const ctx = document.getElementById("scatterChart").getContext("2d");
    scatterChartInstance = new Chart(ctx, {
      type: "scatter",
      data: { datasets },
      options: {
        responsive: true, maintainAspectRatio: false,
        scales: {
          x: { title: { display: true, text: "ADP (lower = drafted earlier)" } },
          y: { title: { display: true, text: "PPR Fantasy Points" } },
        },
        plugins: {
          tooltip: { callbacks: { label: (ctx) => `${ctx.raw.name}: ADP ${ctx.raw.x}, ${ctx.raw.y} pts` } },
        },
      },
    });
  }

  document.getElementById("scatterMatchNote").textContent =
    `Matched ${matched.length} of ${adpRows.length} drafted skill-position players to ${year} season stats ` +
    `(${Math.round(100 * matched.length / adpRows.length)}%). Unmatched names are typically nickname/legal-name ` +
    `differences between FantasyPros and nflverse (e.g. "Kenneth" vs "Kenny").`;
}

// Kick off default view
initSOS();
