import { initDeckTree } from './tree.js';
import { initDeckModals } from './modals.js';
import { initStats } from './stats.js';

(() => {
    // Cleanup orphaned modal backdrops on page load
    const cleanupOrphanedBackdrops = () => {
        const backdrops = document.querySelectorAll(".modal-backdrop");
        const activeModals = document.querySelectorAll(".modal.show");

        if (activeModals.length === 0 && backdrops.length > 0) {
            backdrops.forEach((backdrop) => {
                backdrop.remove();
            });
            document.body.classList.remove("modal-open");
            document.body.style.overflow = "";
        }
    };

    // Cleanup on page load
    cleanupOrphanedBackdrops();

    // Also cleanup after a short delay to catch delayed backdrops
    setTimeout(cleanupOrphanedBackdrops, 500);

    const rowMap = new Map();
    const toggleMap = new Map();

    // Initialize UI Tree
    initDeckTree(rowMap, toggleMap);

    // Initialize Modals
    initDeckModals(rowMap);

    // Initialize Heatmap Stats
    initStats();
})();
