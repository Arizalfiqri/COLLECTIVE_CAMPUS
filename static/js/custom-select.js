/**
 * Collective Campus - Responsive Custom Select Dropdown
 * Mengubah elemen <select> bawaan HTML menjadi dropdown kustom responsif
 * yang 100% berada di dalam batas kartu/viewport tanpa memicu menu OS bawaan.
 */
(function () {
    'use strict';

    function initCustomSelect(select) {
        if (!select || select.dataset.customSelectInitialized === 'true') return;
        if (select.multiple || select.dataset.noCustom !== undefined) return;

        select.dataset.customSelectInitialized = 'true';

        // Sembunyikan select asli namun tetap ada di DOM agar form submit & validasi tetap bekerja
        select.style.position = 'absolute';
        select.style.opacity = '0';
        select.style.pointerEvents = 'none';
        select.style.width = '1px';
        select.style.height = '1px';
        select.style.zIndex = '-1';
        select.tabIndex = -1;

        // Wadah wrapper relatif
        const wrapper = document.createElement('div');
        wrapper.className = 'custom-select-wrapper relative w-full';

        // Tombol pemicu (Trigger Button)
        const trigger = document.createElement('button');
        trigger.type = 'button';
        trigger.className = 'custom-select-trigger w-full bg-card border border-line rounded-xl px-3.5 sm:px-4 py-2.5 text-left text-xs sm:text-sm text-ink flex items-center justify-between transition-colors focus:outline-none focus:ring-2 focus:ring-brand hover:border-brand/50 min-h-[44px] shadow-sm';
        trigger.setAttribute('aria-haspopup', 'listbox');
        trigger.setAttribute('aria-expanded', 'false');

        const labelSpan = document.createElement('span');
        labelSpan.className = 'truncate pr-2 font-medium';

        const iconSpan = document.createElement('span');
        iconSpan.className = 'text-ink-muted flex-shrink-0 transition-transform duration-200 ml-1';
        iconSpan.innerHTML = `
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
            </svg>
        `;

        trigger.appendChild(labelSpan);
        trigger.appendChild(iconSpan);

        // Panel Menu Dropdown Kustom
        const menu = document.createElement('div');
        menu.className = 'custom-select-menu hidden absolute left-0 right-0 top-full mt-1.5 w-full bg-card border border-line rounded-xl shadow-2xl z-50 max-h-56 overflow-y-auto divide-y divide-line/30 custom-scrollbar safe-bottom';
        menu.setAttribute('role', 'listbox');

        function updateOptions() {
            menu.innerHTML = '';
            const options = Array.from(select.options);
            const selectedOpt = select.options[select.selectedIndex];
            
            if (selectedOpt) {
                labelSpan.textContent = selectedOpt.text;
                if (!selectedOpt.value) {
                    labelSpan.classList.add('text-ink-muted');
                } else {
                    labelSpan.classList.remove('text-ink-muted');
                }
            } else {
                labelSpan.textContent = '-- Pilih --';
                labelSpan.classList.add('text-ink-muted');
            }

            options.forEach((opt) => {
                const optItem = document.createElement('div');
                optItem.className = 'custom-select-option px-4 py-3 min-h-[44px] text-xs sm:text-sm cursor-pointer flex items-center justify-between transition-colors ' +
                    (opt.selected ? 'bg-brand-tint text-brand font-semibold' : 'text-ink hover:bg-paper hover:text-brand');
                optItem.setAttribute('role', 'option');
                optItem.setAttribute('aria-selected', opt.selected ? 'true' : 'false');
                optItem.dataset.value = opt.value;

                const textSpan = document.createElement('span');
                textSpan.className = 'truncate pr-2' + (!opt.value ? ' text-ink-muted' : '');
                textSpan.textContent = opt.text;
                optItem.appendChild(textSpan);

                if (opt.selected && opt.value) {
                    const checkSpan = document.createElement('span');
                    checkSpan.className = 'text-brand flex-shrink-0';
                    checkSpan.innerHTML = `
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                        </svg>
                    `;
                    optItem.appendChild(checkSpan);
                }

                if (opt.disabled) {
                    optItem.classList.add('opacity-40', 'cursor-not-allowed');
                } else {
                    optItem.addEventListener('click', (e) => {
                        e.stopPropagation();
                        if (select.value !== opt.value) {
                            select.value = opt.value;
                            select.dispatchEvent(new Event('change', { bubbles: true }));
                            select.dispatchEvent(new Event('input', { bubbles: true }));
                        }
                        closeMenu();
                        updateOptions();
                    });
                }

                menu.appendChild(optItem);
            });
        }

        function openMenu() {
            // Tutup dropdown lain yang sedang terbuka
            document.querySelectorAll('.custom-select-menu:not(.hidden)').forEach(m => {
                if (m !== menu) {
                    m.classList.add('hidden');
                    if (m.parentElement) {
                        m.parentElement.classList.remove('z-40');
                    }
                    const t = m.parentElement ? m.parentElement.querySelector('.custom-select-trigger') : null;
                    if (t) {
                        t.setAttribute('aria-expanded', 'false');
                        const icon = t.querySelector('svg');
                        if (icon) icon.classList.remove('rotate-180');
                    }
                }
            });

            menu.classList.remove('hidden');
            wrapper.classList.add('z-40');
            trigger.setAttribute('aria-expanded', 'true');
            iconSpan.querySelector('svg').classList.add('rotate-180');

            // Scroll ke opsi yang sedang terpilih
            const selectedItem = menu.querySelector('[aria-selected="true"]');
            if (selectedItem) {
                selectedItem.scrollIntoView({ block: 'nearest' });
            }
        }

        function closeMenu() {
            menu.classList.add('hidden');
            wrapper.classList.remove('z-40');
            trigger.setAttribute('aria-expanded', 'false');
            const svg = iconSpan.querySelector('svg');
            if (svg) svg.classList.remove('rotate-180');
        }

        trigger.addEventListener('click', (e) => {
            e.stopPropagation();
            if (menu.classList.contains('hidden')) {
                openMenu();
            } else {
                closeMenu();
            }
        });

        // Event listener saat nilai select berubah dari luar (HTMX / script)
        select.addEventListener('change', () => {
            updateOptions();
        });

        // Sisipkan wrapper sebelum elemen select dan masukkan select ke dalamnya
        select.parentNode.insertBefore(wrapper, select);
        wrapper.appendChild(select);
        wrapper.appendChild(trigger);
        wrapper.appendChild(menu);

        updateOptions();
    }

    function initAllCustomSelects() {
        document.querySelectorAll('select:not([data-no-custom])').forEach(initCustomSelect);
    }

    // Klik di luar menutup seluruh menu
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.custom-select-wrapper')) {
            document.querySelectorAll('.custom-select-menu:not(.hidden)').forEach(m => {
                m.classList.add('hidden');
                if (m.parentElement) m.parentElement.classList.remove('z-40');
                const t = m.parentElement ? m.parentElement.querySelector('.custom-select-trigger') : null;
                if (t) {
                    t.setAttribute('aria-expanded', 'false');
                    const icon = t.querySelector('svg');
                    if (icon) icon.classList.remove('rotate-180');
                }
            });
        }
    });

    // Escape menutup menu
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            document.querySelectorAll('.custom-select-menu:not(.hidden)').forEach(m => {
                m.classList.add('hidden');
                if (m.parentElement) m.parentElement.classList.remove('z-40');
                const t = m.parentElement ? m.parentElement.querySelector('.custom-select-trigger') : null;
                if (t) {
                    t.setAttribute('aria-expanded', 'false');
                    const icon = t.querySelector('svg');
                    if (icon) icon.classList.remove('rotate-180');
                }
            });
        }
    });

    // Inisialisasi saat load dan swap HTMX
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAllCustomSelects);
    } else {
        initAllCustomSelects();
    }

    document.addEventListener('htmx:load', initAllCustomSelects);
    document.addEventListener('htmx:afterSwap', initAllCustomSelects);

    window.initCustomSelect = initCustomSelect;
    window.initAllCustomSelects = initAllCustomSelects;
})();
