/**
 * Collective Campus - Responsive Custom Datepicker
 * Mengubah elemen <input type="date"> menjadi pemilih tanggal kustom responsif
 * yang 100% berada di dalam batas kartu/layar mobile tanpa memicu popup kalender OS bawaan.
 */
(function () {
    'use strict';

    const MONTH_NAMES = [
        'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
        'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'
    ];
    const DAY_NAMES = ['Min', 'Sen', 'Sel', 'Rab', 'Kam', 'Jum', 'Sab'];

    function pad2(n) {
        return String(n).padStart(2, '0');
    }

    function formatDateIndo(dateStr) {
        if (!dateStr) return '';
        const parts = dateStr.split('-');
        if (parts.length !== 3) return dateStr;
        const y = parts[0];
        const m = parseInt(parts[1], 10) - 1;
        const d = parseInt(parts[2], 10);
        return d + ' ' + (MONTH_NAMES[m] || '') + ' ' + y;
    }

    function getTodayStr() {
        const now = new Date();
        return now.getFullYear() + '-' + pad2(now.getMonth() + 1) + '-' + pad2(now.getDate());
    }

    function initCustomDatePicker(input) {
        if (!input || input.dataset.customDateInitialized === 'true') return;
        if (input.dataset.noCustom !== undefined) return;

        input.dataset.customDateInitialized = 'true';

        // Sembunyikan input asli namun tetap di DOM untuk form submit & validasi
        input.style.position = 'absolute';
        input.style.opacity = '0';
        input.style.pointerEvents = 'none';
        input.style.width = '1px';
        input.style.height = '1px';
        input.style.zIndex = '-1';
        input.tabIndex = -1;

        // Wadah wrapper
        const wrapper = document.createElement('div');
        wrapper.className = 'custom-date-wrapper relative w-full min-w-0';

        // Tombol Trigger
        const trigger = document.createElement('button');
        trigger.type = 'button';
        trigger.className = 'custom-date-trigger w-full bg-paper border border-line rounded-xl px-3 sm:px-3.5 py-2 sm:py-2.5 text-left text-xs sm:text-sm text-ink flex items-center justify-between transition-colors focus:outline-none focus:ring-2 focus:ring-brand hover:border-brand/40 min-h-[42px] sm:min-h-[44px] shadow-sm select-none';
        trigger.setAttribute('aria-haspopup', 'dialog');
        trigger.setAttribute('aria-expanded', 'false');

        const labelContainer = document.createElement('span');
        labelContainer.className = 'flex items-center gap-2 truncate';
        labelContainer.innerHTML = `
            <svg class="w-4 h-4 text-brand shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <rect x="3" y="4" width="18" height="18" rx="2" ry="2" stroke-width="2"></rect>
                <line x1="16" y1="2" x2="16" y2="6" stroke-width="2"></line>
                <line x1="8" y1="2" x2="8" y2="6" stroke-width="2"></line>
                <line x1="3" y1="10" x2="21" y2="10" stroke-width="2"></line>
            </svg>
            <span class="custom-date-label font-medium truncate"></span>
        `;

        const chevronIcon = document.createElement('span');
        chevronIcon.className = 'text-ink-muted shrink-0 transition-transform duration-200 ml-1';
        chevronIcon.innerHTML = `
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
            </svg>
        `;

        trigger.appendChild(labelContainer);
        trigger.appendChild(chevronIcon);

        const labelText = labelContainer.querySelector('.custom-date-label');

        function updateLabel() {
            if (input.value) {
                labelText.textContent = formatDateIndo(input.value);
                labelText.classList.remove('text-ink-muted');
                labelText.classList.add('text-ink');
            } else {
                labelText.textContent = input.getAttribute('placeholder') || 'Pilih tanggal';
                labelText.classList.add('text-ink-muted');
                labelText.classList.remove('text-ink');
            }
        }

        // Kalender Popup
        const popup = document.createElement('div');
        popup.className = 'custom-date-popup hidden absolute top-full left-0 right-0 sm:left-auto sm:right-0 mt-1.5 w-full sm:w-72 bg-card border border-line rounded-2xl shadow-2xl p-3 sm:p-4 z-50 text-ink';
        popup.style.maxWidth = 'calc(100vw - 2rem)';

        // State internal kalender
        let currentViewDate = input.value ? new Date(input.value + 'T00:00:00') : new Date();
        if (isNaN(currentViewDate.getTime())) currentViewDate = new Date();
        let viewYear = currentViewDate.getFullYear();
        let viewMonth = currentViewDate.getMonth();

        function renderCalendar() {
            popup.innerHTML = '';

            // Header navigasi bulan & tahun
            const nav = document.createElement('div');
            nav.className = 'flex items-center justify-between pb-2.5 border-b border-line';

            const prevBtn = document.createElement('button');
            prevBtn.type = 'button';
            prevBtn.className = 'w-7 h-7 sm:w-8 sm:h-8 rounded-lg border border-line bg-paper hover:bg-paper-deep text-ink flex items-center justify-center transition-colors font-bold text-xs select-none';
            prevBtn.innerHTML = '&larr;';
            prevBtn.title = 'Bulan sebelumnya';
            prevBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                if (viewMonth === 0) {
                    viewMonth = 11;
                    viewYear--;
                } else {
                    viewMonth--;
                }
                renderCalendar();
            });

            const monthTitle = document.createElement('span');
            monthTitle.className = 'text-xs sm:text-sm font-bold text-ink';
            monthTitle.textContent = MONTH_NAMES[viewMonth] + ' ' + viewYear;

            const nextBtn = document.createElement('button');
            nextBtn.type = 'button';
            nextBtn.className = 'w-7 h-7 sm:w-8 sm:h-8 rounded-lg border border-line bg-paper hover:bg-paper-deep text-ink flex items-center justify-center transition-colors font-bold text-xs select-none';
            nextBtn.innerHTML = '&rarr;';
            nextBtn.title = 'Bulan berikutnya';
            nextBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                if (viewMonth === 11) {
                    viewMonth = 0;
                    viewYear++;
                } else {
                    viewMonth++;
                }
                renderCalendar();
            });

            nav.appendChild(prevBtn);
            nav.appendChild(monthTitle);
            nav.appendChild(nextBtn);
            popup.appendChild(nav);

            // Baris Nama Hari
            const dayNamesRow = document.createElement('div');
            dayNamesRow.style.display = 'grid';
            dayNamesRow.style.gridTemplateColumns = 'repeat(7, minmax(0, 1fr))';
            dayNamesRow.style.gap = '2px';
            dayNamesRow.className = 'text-center py-2 text-[10px] sm:text-xs font-semibold text-ink-muted border-b border-line/60';
            DAY_NAMES.forEach(name => {
                const daySpan = document.createElement('span');
                daySpan.textContent = name;
                dayNamesRow.appendChild(daySpan);
            });
            popup.appendChild(dayNamesRow);

            // Grid Tanggal
            const grid = document.createElement('div');
            grid.style.display = 'grid';
            grid.style.gridTemplateColumns = 'repeat(7, minmax(0, 1fr))';
            grid.style.gap = '2px';
            grid.className = 'pt-2';

            const firstDayIndex = new Date(viewYear, viewMonth, 1).getDay();
            const totalDaysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();
            const todayStr = getTodayStr();
            const selectedStr = input.value;
            const minStr = input.getAttribute('min') || '';
            const maxStr = input.getAttribute('max') || '';

            // Slot kosong sebelum tanggal 1
            for (let i = 0; i < firstDayIndex; i++) {
                const emptyCell = document.createElement('div');
                emptyCell.className = 'aspect-square';
                grid.appendChild(emptyCell);
            }

            // Tombol Tanggal
            for (let d = 1; d <= totalDaysInMonth; d++) {
                const dStr = viewYear + '-' + pad2(viewMonth + 1) + '-' + pad2(d);
                const cell = document.createElement('div');
                cell.className = 'aspect-square flex items-center justify-center';

                const dayBtn = document.createElement('button');
                dayBtn.type = 'button';
                dayBtn.textContent = d;
                dayBtn.className = 'w-7 h-7 sm:w-8 sm:h-8 rounded-xl text-xs flex items-center justify-center transition-colors select-none';

                let isDisabled = false;
                if (minStr && dStr < minStr) isDisabled = true;
                if (maxStr && dStr > maxStr) isDisabled = true;

                if (isDisabled) {
                    dayBtn.disabled = true;
                    dayBtn.className += ' opacity-25 cursor-not-allowed text-ink-muted';
                } else if (dStr === selectedStr) {
                    dayBtn.className += ' bg-brand text-white font-bold shadow-sm';
                } else if (dStr === todayStr) {
                    dayBtn.className += ' ring-1 ring-brand text-brand font-bold hover:bg-brand-tint';
                } else {
                    dayBtn.className += ' text-ink hover:bg-paper-deep font-medium';
                }

                if (!isDisabled) {
                    dayBtn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        input.value = dStr;
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                        input.dispatchEvent(new Event('change', { bubbles: true }));
                        updateLabel();
                        closePopup();
                    });
                }

                cell.appendChild(dayBtn);
                grid.appendChild(cell);
            }

            popup.appendChild(grid);

            // Footer Kalender: Tombol Aksi Cepat
            const footer = document.createElement('div');
            footer.className = 'flex items-center justify-between pt-2.5 mt-2 border-t border-line text-xs';

            const clearBtn = document.createElement('button');
            clearBtn.type = 'button';
            clearBtn.textContent = 'Hapus';
            clearBtn.className = 'text-brick hover:underline text-[11px] font-medium py-1 px-1';
            clearBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                input.value = '';
                input.dispatchEvent(new Event('input', { bubbles: true }));
                input.dispatchEvent(new Event('change', { bubbles: true }));
                updateLabel();
                closePopup();
            });

            const rightActions = document.createElement('div');
            rightActions.className = 'flex items-center gap-1.5';

            const todayBtn = document.createElement('button');
            todayBtn.type = 'button';
            todayBtn.textContent = 'Hari ini';
            todayBtn.className = 'px-2 py-1 text-brand hover:underline text-[11px] font-semibold';
            todayBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                const t = getTodayStr();
                let canSetToday = true;
                if (minStr && t < minStr) canSetToday = false;
                if (maxStr && t > maxStr) canSetToday = false;
                if (canSetToday) {
                    input.value = t;
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                    input.dispatchEvent(new Event('change', { bubbles: true }));
                    updateLabel();
                    closePopup();
                } else {
                    viewYear = new Date().getFullYear();
                    viewMonth = new Date().getMonth();
                    renderCalendar();
                }
            });

            const closeBtn = document.createElement('button');
            closeBtn.type = 'button';
            closeBtn.textContent = 'Tutup';
            closeBtn.className = 'px-2.5 py-1 bg-paper hover:bg-paper-deep text-ink rounded-lg border border-line text-xs font-semibold transition-colors';
            closeBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                closePopup();
            });

            rightActions.appendChild(todayBtn);
            rightActions.appendChild(closeBtn);

            footer.appendChild(clearBtn);
            footer.appendChild(rightActions);
            popup.appendChild(footer);
        }

        function openPopup() {
            // Tutup popup lain yang terbuka
            document.querySelectorAll('.custom-date-popup:not(.hidden)').forEach(p => {
                if (p !== popup) {
                    p.classList.add('hidden');
                    const t = p.parentElement ? p.parentElement.querySelector('.custom-date-trigger') : null;
                    if (t) {
                        t.setAttribute('aria-expanded', 'false');
                        const icon = t.querySelector('.transition-transform');
                        if (icon) icon.classList.remove('rotate-180');
                    }
                }
            });

            // Set bulan & tahun ke tanggal terpilih atau hari ini
            if (input.value) {
                const parsed = new Date(input.value + 'T00:00:00');
                if (!isNaN(parsed.getTime())) {
                    viewYear = parsed.getFullYear();
                    viewMonth = parsed.getMonth();
                }
            } else {
                const now = new Date();
                viewYear = now.getFullYear();
                viewMonth = now.getMonth();
            }

            renderCalendar();
            popup.classList.remove('hidden');
            trigger.setAttribute('aria-expanded', 'true');
            chevronIcon.classList.add('rotate-180');

            // Penyesuaian batas viewport mobile agar popup tidak pernah terpotong ke kanan
            requestAnimationFrame(() => {
                const rect = popup.getBoundingClientRect();
                const winWidth = window.innerWidth;
                if (rect.right > winWidth - 10) {
                    popup.style.right = '0';
                    popup.style.left = 'auto';
                }
            });
        }

        function closePopup() {
            popup.classList.add('hidden');
            trigger.setAttribute('aria-expanded', 'false');
            chevronIcon.classList.remove('rotate-180');
        }

        trigger.addEventListener('click', (e) => {
            e.stopPropagation();
            if (popup.classList.contains('hidden')) {
                openPopup();
            } else {
                closePopup();
            }
        });

        input.addEventListener('change', () => {
            updateLabel();
        });

        // Sisipkan wrapper
        input.parentNode.insertBefore(wrapper, input);
        wrapper.appendChild(input);
        wrapper.appendChild(trigger);
        wrapper.appendChild(popup);

        updateLabel();
    }

    function initAllCustomDatePickers() {
        document.querySelectorAll('input[type="date"]:not([data-no-custom])').forEach(initCustomDatePicker);
    }

    // Klik luar menutup popup kalender
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.custom-date-wrapper')) {
            document.querySelectorAll('.custom-date-popup:not(.hidden)').forEach(p => {
                p.classList.add('hidden');
                const t = p.parentElement ? p.parentElement.querySelector('.custom-date-trigger') : null;
                if (t) {
                    t.setAttribute('aria-expanded', 'false');
                    const icon = t.querySelector('.transition-transform');
                    if (icon) icon.classList.remove('rotate-180');
                }
            });
        }
    });

    // Escape menutup kalender
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            document.querySelectorAll('.custom-date-popup:not(.hidden)').forEach(p => {
                p.classList.add('hidden');
                const t = p.parentElement ? p.parentElement.querySelector('.custom-date-trigger') : null;
                if (t) {
                    t.setAttribute('aria-expanded', 'false');
                    const icon = t.querySelector('.transition-transform');
                    if (icon) icon.classList.remove('rotate-180');
                }
            });
        }
    });

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAllCustomDatePickers);
    } else {
        initAllCustomDatePickers();
    }

    document.addEventListener('htmx:load', initAllCustomDatePickers);
    document.addEventListener('htmx:afterSwap', initAllCustomDatePickers);

    window.initCustomDatePicker = initCustomDatePicker;
    window.initAllCustomDatePickers = initAllCustomDatePickers;
})();
