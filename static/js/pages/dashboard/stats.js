export function initStats() {
    const statsRoot = document.getElementById("stats-board");
    const statsSummaryEl = document.getElementById("stats-summary");
    const statsYearLabelEl = document.getElementById("stats-year-label");
    const statsHeatmapEl = document.getElementById("stats-heatmap");
    const statsTooltipEl = document.getElementById("stats-tooltip");
    const statsPrevYearBtn = document.getElementById("stats-prev-year");
    const statsNextYearBtn = document.getElementById("stats-next-year");
    const statsDailyAverageEl = document.getElementById("stats-daily-average");
    const statsDaysLearnedEl = document.getElementById("stats-days-learned");
    const statsLongestStreakEl = document.getElementById("stats-longest-streak");
    const statsCurrentStreakEl = document.getElementById("stats-current-streak");

    function parseIsoDate(isoDate) {
        const parts = String(isoDate || "").split("-");
        if (parts.length !== 3) {
            return null;
        }
        const year = Number(parts[0]);
        const month = Number(parts[1]);
        const day = Number(parts[2]);
        if (!Number.isInteger(year) || !Number.isInteger(month) || !Number.isInteger(day)) {
            return null;
        }
        return new Date(Date.UTC(year, month - 1, day));
    }

    function weekdayIndexMonday(dateObj) {
        return (dateObj.getUTCDay() + 6) % 7;
    }

    function buildHeatmapWeeks(days) {
        const weeks = [];
        let week = new Array(7).fill(null);
        days.forEach((item, index) => {
            const parsedDate = parseIsoDate((item && (item.day || item.date)) || "");
            if (!parsedDate) {
                return;
            }
            const weekday = weekdayIndexMonday(parsedDate);
            week[weekday] = item;
            const isLast = index === days.length - 1;
            if (weekday === 6 || isLast) {
                weeks.push(week);
                week = new Array(7).fill(null);
            }
        });
        return weeks;
    }

    function toFixedNumber(rawValue, digits = 2) {
        const value = Number(rawValue || 0);
        if (!Number.isFinite(value)) {
            return (0).toFixed(digits);
        }
        return value.toFixed(digits);
    }

    function toInt(rawValue) {
        const value = Number(rawValue || 0);
        if (!Number.isFinite(value)) {
            return 0;
        }
        return Math.round(value);
    }

    function heatLevel(cards, maxCards) {
        if (!cards || cards <= 0) {
            return 0;
        }
        if (!maxCards || maxCards <= 0) {
            return 1;
        }
        return Math.min(5, Math.max(1, Math.ceil((cards / maxCards) * 5)));
    }

    function updateStatsTooltip(item) {
        if (!statsTooltipEl || !item) {
            return;
        }
        const day = String(item.day || item.date || "");
        const cards = toInt(item.cards);
        const source = String(item.source || "reviewed").toLowerCase();
        if (source === "due") {
            statsTooltipEl.textContent = `${day} · Due: ${cards}`;
            return;
        }
        const studyTime = toInt(item.study_time);
        const minutes = studyTime > 0 ? toFixedNumber(studyTime / 60000, 2) : toFixedNumber(item.minutes, 2);
        const secPerCard = cards > 0 ? toFixedNumber((studyTime / 1000) / cards, 2) : "0.00";
        statsTooltipEl.textContent = `${day} · Reviewed: ${cards} · ${minutes} minutes · ${secPerCard}s/card`;
    }

    function renderStats(payload) {
        if (!payload || typeof payload !== "object") {
            return;
        }

        const today = payload.today || {};
        const metrics = payload.metrics || {};
        const heatmap = Array.isArray(payload.heatmap) ? payload.heatmap : [];

        if (statsYearLabelEl) {
            statsYearLabelEl.textContent = String(payload.year || "");
        }
        if (statsSummaryEl) {
            const cards = toInt(today.cards);
            const minutes = toFixedNumber(today.minutes, 2);
            const secPerCard = toFixedNumber(today.sec_per_card, 2);
            statsSummaryEl.textContent = `Studied ${cards} cards in ${minutes} minutes today (${secPerCard}s/card)`;
        }
        if (statsDailyAverageEl) {
            statsDailyAverageEl.textContent = `${toInt(metrics.daily_average_cards)} cards`;
        }
        if (statsDaysLearnedEl) {
            statsDaysLearnedEl.textContent = `${toInt(metrics.days_learned_percent)}%`;
        }
        if (statsLongestStreakEl) {
            statsLongestStreakEl.textContent = `${toInt(metrics.longest_streak_days)} days`;
        }
        if (statsCurrentStreakEl) {
            statsCurrentStreakEl.textContent = `${toInt(metrics.current_streak_days)} days`;
        }

        if (!statsHeatmapEl) {
            return;
        }
        statsHeatmapEl.innerHTML = "";
        statsHeatmapEl.style.setProperty("--stats-week-count", "1");
        if (heatmap.length === 0) {
            if (statsTooltipEl) {
                statsTooltipEl.textContent = "No data yet.";
            }
            return;
        }

        const maxCards = heatmap.reduce((max, item) => Math.max(max, toInt(item && item.cards)), 0);
        const weeks = buildHeatmapWeeks(heatmap);
        statsHeatmapEl.style.setProperty("--stats-week-count", String(Math.max(1, weeks.length)));
        weeks.forEach((week) => {
            const weekEl = document.createElement("div");
            weekEl.className = "stats-week";
            week.forEach((item) => {
                if (!item) {
                    const spacer = document.createElement("span");
                    spacer.className = "stats-day stats-day--empty";
                    spacer.setAttribute("aria-hidden", "true");
                    weekEl.appendChild(spacer);
                    return;
                }

                const cards = toInt(item.cards);
                const level = heatLevel(cards, maxCards);
                const day = String(item.day || item.date || "");
                const sourceLabel = String(item.source || "reviewed").toLowerCase() === "due" ? "Due" : "Reviewed";
                const cell = document.createElement("button");
                cell.type = "button";
                cell.className = `stats-day stats-day--level-${level}${item.is_future ? " stats-day--future" : ""}`;
                cell.setAttribute("aria-label", `${day} ${sourceLabel.toLowerCase()} ${cards} cards`);
                cell.title = `${day} · ${sourceLabel}: ${cards} cards`;
                const showTooltip = () => updateStatsTooltip(item);
                cell.addEventListener("mouseenter", showTooltip);
                cell.addEventListener("focus", showTooltip);
                cell.addEventListener("click", showTooltip);
                weekEl.appendChild(cell);
            });
            statsHeatmapEl.appendChild(weekEl);
        });

        if (statsTooltipEl) {
            const firstDay = heatmap.find((item) => toInt(item.cards) > 0) || heatmap[0];
            updateStatsTooltip(firstDay);
        }
    }

    function setStatsLoading(isLoading) {
        if (statsPrevYearBtn) {
            statsPrevYearBtn.disabled = Boolean(isLoading);
        }
        if (statsNextYearBtn) {
            statsNextYearBtn.disabled = Boolean(isLoading);
        }
    }

    let statsYear = Number(statsRoot?.dataset.initialYear || 0);
    if (!Number.isFinite(statsYear) || statsYear <= 0) {
        statsYear = new Date().getFullYear();
    }
    let statsRequestId = 0;

    async function loadStats(year) {
        if (!statsRoot) {
            return;
        }
        statsYear = toInt(year);
        const requestId = ++statsRequestId;
        setStatsLoading(true);
        if (statsYearLabelEl) {
            statsYearLabelEl.textContent = String(statsYear);
        }
        try {
            const response = await fetch(`/api/stats/overview?year=${encodeURIComponent(statsYear)}`);
            const data = await response.json().catch(() => null);
            if (requestId !== statsRequestId) {
                return;
            }
            if (!response.ok || !data) {
                throw new Error(data?.message || "Unable to load statistics.");
            }
            statsYear = toInt(data.year || statsYear);
            renderStats(data);
        } catch (error) {
            if (requestId !== statsRequestId) {
                return;
            }
            if (statsTooltipEl) {
                statsTooltipEl.textContent = "Failed to load statistics.";
            }
            console.error(error);
        } finally {
            if (requestId === statsRequestId) {
                setStatsLoading(false);
            }
        }
    }

    if (statsPrevYearBtn) {
        statsPrevYearBtn.addEventListener("click", () => {
            loadStats(statsYear - 1);
        });
    }
    if (statsNextYearBtn) {
        statsNextYearBtn.addEventListener("click", () => {
            loadStats(statsYear + 1);
        });
    }

    if (statsRoot) {
        loadStats(statsYear);
    }
}
