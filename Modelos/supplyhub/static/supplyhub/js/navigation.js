(() => {
    const menus = Array.from(document.querySelectorAll("[data-q-menu]"));

    const closeMenu = (menu) => {
        const trigger = menu.querySelector("[data-q-menu-trigger]");
        const panel = menu.querySelector("[data-q-menu-panel]");
        if (!trigger || !panel) return;
        trigger.setAttribute("aria-expanded", "false");
        panel.hidden = true;
    };

    const closeAll = (except = null) => {
        menus.forEach((menu) => {
            if (menu !== except) closeMenu(menu);
        });
    };

    menus.forEach((menu) => {
        const trigger = menu.querySelector("[data-q-menu-trigger]");
        const panel = menu.querySelector("[data-q-menu-panel]");
        if (!trigger || !panel) return;

        trigger.addEventListener("click", (event) => {
            event.stopPropagation();
            const opening = trigger.getAttribute("aria-expanded") !== "true";
            closeAll(menu);
            trigger.setAttribute("aria-expanded", opening ? "true" : "false");
            panel.hidden = !opening;
        });

        panel.addEventListener("click", (event) => event.stopPropagation());
    });

    document.addEventListener("click", () => closeAll());
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") closeAll();
    });
})();
