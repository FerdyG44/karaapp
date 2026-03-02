// script.js for ProfitApp
//
// This script drives the dynamic behaviour of the ProfitApp dashboard.  It
// fetches summary statistics and recent records from the server, updates the
// DOM accordingly, and periodically refreshes the data to reflect live
// changes.  The form for adding a new record posts JSON to the backend
// and clears itself on success.

async function fetchJSON(url) {
    const response = await fetch(url);
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
    }
    return await response.json();
}

// Global state for date range and grouping selections.  When either start or end
// is non‑null, the dashboard will fetch aggregated summaries and records for
// the specified range.  The group property controls daily, monthly or
// yearly grouping when displaying aggregated results.
const rangeSelection = {
    start: null,
    end: null,
    group: 'daily'
};

async function loadSummary() {
    try {
        // Always load today's summary so the top cards reflect current day
        const todayData = await fetchJSON('/api/summary');
        document.querySelector('.today-date').textContent = todayData.today_date;
        document.getElementById('today-sales').textContent = `${todayData.today_sales.toFixed(2)} SEK`;
        document.getElementById('today-expenses').textContent = `${todayData.today_expenses.toFixed(2)} SEK`;
        document.getElementById('today-profit').textContent = `${todayData.today_profit.toFixed(2)} SEK`;
        // New today metrics: orders, items and discount
        if (document.getElementById('today-orders'))
            document.getElementById('today-orders').textContent = `${todayData.today_orders || 0}`;
        if (document.getElementById('today-items'))
            document.getElementById('today-items').textContent = `${todayData.today_items || 0}`;
        if (document.getElementById('today-discount'))
            document.getElementById('today-discount').textContent = `${todayData.today_discount.toFixed(2)} SEK`;
        // Determine whether to show overall totals from entire dataset or a date range
        if (rangeSelection.start || rangeSelection.end) {
            const params = new URLSearchParams();
            if (rangeSelection.start) params.set('start', rangeSelection.start);
            if (rangeSelection.end) params.set('end', rangeSelection.end);
            params.set('group', rangeSelection.group);
            const rangeData = await fetchJSON(`/api/summary_range?${params.toString()}`);
            const totals = rangeData.totals || { sales: 0, expenses: 0, profit: 0, orders: 0, items: 0, discount: 0 };
            document.getElementById('total-sales').textContent = `${(totals.sales || 0).toFixed(2)} SEK`;
            document.getElementById('total-expenses').textContent = `${(totals.expenses || 0).toFixed(2)} SEK`;
            document.getElementById('total-profit').textContent = `${(totals.profit || 0).toFixed(2)} SEK`;
            if (document.getElementById('total-orders'))
                document.getElementById('total-orders').textContent = `${totals.orders || 0}`;
            if (document.getElementById('total-items'))
                document.getElementById('total-items').textContent = `${totals.items || 0}`;
            if (document.getElementById('total-discount'))
                document.getElementById('total-discount').textContent = `${(totals.discount || 0).toFixed(2)} SEK`;
        } else {
            // No range specified; use overall totals from todayData
            document.getElementById('total-sales').textContent = `${todayData.total_sales.toFixed(2)} SEK`;
            document.getElementById('total-expenses').textContent = `${todayData.total_expenses.toFixed(2)} SEK`;
            document.getElementById('total-profit').textContent = `${todayData.total_profit.toFixed(2)} SEK`;
            if (document.getElementById('total-orders'))
                document.getElementById('total-orders').textContent = `${todayData.total_orders || 0}`;
            if (document.getElementById('total-items'))
                document.getElementById('total-items').textContent = `${todayData.total_items || 0}`;
            if (document.getElementById('total-discount'))
                document.getElementById('total-discount').textContent = `${todayData.total_discount.toFixed(2)} SEK`;
        }
    } catch (err) {
        console.error('Failed to load summary:', err);
    }
}

async function loadRecords(daysFilter = null) {
    try {
        const table = document.getElementById('records-table');
        const tbody = table.querySelector('tbody');
        // If a date range is selected, ignore the days filter and use range APIs
        if (rangeSelection.start || rangeSelection.end) {
            // When grouping is not daily, fetch aggregated groups
            if (rangeSelection.group && rangeSelection.group !== 'daily') {
                const params = new URLSearchParams();
                if (rangeSelection.start) params.set('start', rangeSelection.start);
                if (rangeSelection.end) params.set('end', rangeSelection.end);
                params.set('group', rangeSelection.group);
                const data = await fetchJSON(`/api/summary_range?${params.toString()}`);
                // Update title suffix with range and group information
                const startStr = rangeSelection.start || 'beginning';
                const endStr = rangeSelection.end || 'today';
                document.getElementById('records-title-suffix').textContent = ` (${startStr} – ${endStr}, ${rangeSelection.group})`;
                // Adjust table header for aggregated data
                const thead = table.querySelector('thead');
                thead.innerHTML = '<tr><th>Period</th><th>Sales</th><th>Expenses</th><th>Profit</th></tr>';
                tbody.innerHTML = '';
                for (const g of data.groups || []) {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `<td>${g.period}</td><td>${g.sales.toFixed(2)} SEK</td><td>${g.expenses.toFixed(2)} SEK</td><td>${g.profit.toFixed(2)} SEK</td>`;
                    tbody.appendChild(tr);
                }
            } else {
                // Daily group or no group specified: fetch raw records for range
                const params = new URLSearchParams();
                if (rangeSelection.start) params.set('start', rangeSelection.start);
                if (rangeSelection.end) params.set('end', rangeSelection.end);
                const data = await fetchJSON(`/api/records_range?${params.toString()}`);
                const startStr = rangeSelection.start || 'beginning';
                const endStr = rangeSelection.end || 'today';
                document.getElementById('records-title-suffix').textContent = ` (${startStr} – ${endStr})`;
                // Reset table header for raw records
                const thead = table.querySelector('thead');
                thead.innerHTML = '<tr><th>Date</th><th>Type</th><th>Amount</th></tr>';
                tbody.innerHTML = '';
                for (const rec of data.records || []) {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `<td>${rec.record_date}</td><td>${rec.type}</td><td>${rec.amount.toFixed(2)} SEK</td>`;
                    tbody.appendChild(tr);
                }
            }
        } else {
            // No range: use days filter if provided
            const params = new URLSearchParams();
            params.set('limit', 50);
            let suffix;
            if (daysFilter) {
                params.set('days', daysFilter);
                suffix = ` (last ${daysFilter} days)`;
            } else {
                suffix = ' (last 50)';
            }
            const data = await fetchJSON(`/api/records?${params.toString()}`);
            document.getElementById('records-title-suffix').textContent = suffix;
            // Reset table header for raw records
            const thead = table.querySelector('thead');
            thead.innerHTML = '<tr><th>Date</th><th>Type</th><th>Amount</th></tr>';
            tbody.innerHTML = '';
            for (const rec of data.records || []) {
                const tr = document.createElement('tr');
                tr.innerHTML = `<td>${rec.record_date}</td><td>${rec.type}</td><td>${rec.amount.toFixed(2)} SEK</td>`;
                tbody.appendChild(tr);
            }
        }
    } catch (err) {
        console.error('Failed to load records:', err);
    }
}

function getDateRange(rangeType) {
    const now = new Date();
    const format = (date) => date.toISOString().slice(0, 10);
    let start = null;
    let end = null;
    switch (rangeType) {
        case 'today':
            start = format(now);
            end = format(now);
            break;
        case 'yesterday': {
            const y = new Date(now);
            y.setDate(now.getDate() - 1);
            const yd = format(y);
            start = yd;
            end = yd;
            break;
        }
        case 'this-week': {
            // Monday as start of week
            const day = now.getDay(); // 0 (Sun) to 6 (Sat)
            const diffToMonday = day === 0 ? -6 : 1 - day;
            const monday = new Date(now);
            monday.setDate(now.getDate() + diffToMonday);
            start = format(monday);
            end = format(now);
            break;
        }
        case 'last-week': {
            // Compute Monday of current week
            const day = now.getDay();
            const diffToMonday = day === 0 ? -6 : 1 - day;
            const currentMonday = new Date(now);
            currentMonday.setDate(now.getDate() + diffToMonday);
            // Monday of last week
            const lastMonday = new Date(currentMonday);
            lastMonday.setDate(currentMonday.getDate() - 7);
            const lastSunday = new Date(currentMonday);
            lastSunday.setDate(currentMonday.getDate() - 1);
            start = format(lastMonday);
            end = format(lastSunday);
            break;
        }
        case 'this-month': {
            const first = new Date(now.getFullYear(), now.getMonth(), 1);
            start = format(first);
            end = format(now);
            break;
        }
        case 'last-month': {
            const firstPrev = new Date(now.getFullYear(), now.getMonth() - 1, 1);
            const lastPrev = new Date(now.getFullYear(), now.getMonth(), 0);
            start = format(firstPrev);
            end = format(lastPrev);
            break;
        }
        case 'all':
        default:
            start = null;
            end = null;
    }
    return { start, end };
}

function attachFilterHandlers() {
    // Quick range filter buttons
    document.querySelectorAll('.filter-buttons button').forEach(btn => {
        btn.addEventListener('click', () => {
            const rangeType = btn.getAttribute('data-range');
            // Compute start/end based on rangeType
            const range = getDateRange(rangeType);
            rangeSelection.start = range.start;
            rangeSelection.end = range.end;
            rangeSelection.group = 'daily';
            // Update date inputs
            const rs = document.getElementById('range-start');
            const re = document.getElementById('range-end');
            if (rs) rs.value = range.start || '';
            if (re) re.value = range.end || '';
            // Toggle active state
            document.querySelectorAll('.filter-buttons button').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            // Refresh summary and records
            loadSummary();
            loadRecords();
        });
    });
}

function attachFormHandler() {
    const form = document.getElementById('record-form');
    form.addEventListener('submit', async (ev) => {
        ev.preventDefault();
        const date = document.getElementById('record-date').value;
        const type = document.getElementById('record-type').value;
        const amountStr = document.getElementById('record-amount').value;
        const amount = parseFloat(amountStr);
        if (!date || !amountStr || isNaN(amount)) {
            alert('Please provide a valid date and amount.');
            return;
        }
        try {
            const res = await fetch('/api/add_record', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ record_date: date, type: type, amount: amount })
            });
            const resData = await res.json();
            if (!res.ok || !resData.success) {
                throw new Error(resData.error || 'Unknown error');
            }
            // Clear amount field and refresh data
            document.getElementById('record-amount').value = '';
            await loadSummary();
            await loadRecords();
        } catch (err) {
            alert('Failed to add record: ' + err.message);
        }
    });
}

function startAutoRefresh() {
    setInterval(() => {
        loadSummary();
        // Keep the same filter active when auto refreshing; find active button
        const activeBtn = document.querySelector('.filter-buttons button.active');
        const days = activeBtn ? activeBtn.getAttribute('data-days') : null;
        loadRecords(days || null);
    }, 5000);
}

// Attach handler for the date range apply button.  This function reads the
// selected start/end dates and grouping option from the controls, updates the
// global rangeSelection and refreshes the summary and records accordingly.
function attachRangeHandler() {
    const applyBtn = document.getElementById('range-apply');
    if (!applyBtn) return;
    applyBtn.addEventListener('click', () => {
        const startInput = document.getElementById('range-start');
        const endInput = document.getElementById('range-end');
        const groupSelect = document.getElementById('range-group');
        const startVal = startInput && startInput.value ? startInput.value : null;
        const endVal = endInput && endInput.value ? endInput.value : null;
        const groupVal = groupSelect && groupSelect.value ? groupSelect.value : 'daily';
        // Update range state
        rangeSelection.start = startVal;
        rangeSelection.end = endVal;
        rangeSelection.group = groupVal;
        // Clear days filter active state
        document.querySelectorAll('.filter-buttons button').forEach(b => b.classList.remove('active'));
        // Refresh summary and records
        loadSummary();
        loadRecords();
    });
}

// Initialise the dashboard when the DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    attachFilterHandlers();
    // New record form no longer used; do not attach form handler
    attachExportHandlers();
    // Language is selected via settings; no language buttons here
    attachGoProHandler();
    attachRangeHandler();
    loadSummary();
    loadRecords();
    startAutoRefresh();
    // Initialise language for card headings based on current language from server
    const defaultLang = window.appLanguage || 'en';
    setLanguage(defaultLang);
});

// Attach click handlers for export buttons
function attachExportHandlers() {
    const csvBtn = document.getElementById('export-csv');
    const xlsxBtn = document.getElementById('export-excel');
    if (csvBtn) {
        csvBtn.addEventListener('click', () => {
            // Pass current filter days if any
            const activeBtn = document.querySelector('.filter-buttons button.active');
            const days = activeBtn ? activeBtn.getAttribute('data-days') : null;
            let url = '/api/export/csv';
            if (days) url += '?days=' + encodeURIComponent(days);
            window.location.href = url;
        });
    }
    if (xlsxBtn) {
        xlsxBtn.addEventListener('click', () => {
            const activeBtn = document.querySelector('.filter-buttons button.active');
            const days = activeBtn ? activeBtn.getAttribute('data-days') : null;
            let url = '/api/export/excel';
            if (days) url += '?days=' + encodeURIComponent(days);
            window.location.href = url;
        });
    }
}

// Simple language translation support
const translations = {
    en: {
        // Date range filters
        today_label: 'Today',
        yesterday_label: 'Yesterday',
        this_week_label: 'This Week',
        last_week_label: 'Last Week',
        this_month_label: 'This Month',
        last_month_label: 'Last Month',
        all_label: 'All',
        // Summary headings
        sales: 'Sales',
        expenses: 'Expenses',
        profit: 'Profit',
        orders: 'Orders',
        items: 'Items',
        discount: 'Discount',
        today_summary: 'Today',
        totals_summary: 'Totals',
        // Range controls
        start: 'Start:',
        end: 'End:',
        group: 'Group:',
        apply: 'Apply',
        daily: 'Daily',
        monthly: 'Monthly',
        yearly: 'Yearly',
        appTitle: 'ProfitApp',
        tagline: 'Enter daily sales and expenses and see profit instantly.',
        todaysales: "Today's sales",
        todayexpenses: "Today's expense",
        todayprofit: "Today's profit",
        totalsales: 'Total sales',
        totalexpenses: 'Total expense',
        totalprofit: 'Total profit',
        newrecord: 'New record',
        date: 'Date:',
        type: 'Type:',
        amount: 'Amount (SEK):',
        save: 'Save',
        records: 'Records',
        lastn: '(last 50)',
    },
    tr: {
        // Date range filters
        today_label: 'Bugün',
        yesterday_label: 'Dün',
        this_week_label: 'Bu Hafta',
        last_week_label: 'Geçen Hafta',
        this_month_label: 'Bu Ay',
        last_month_label: 'Geçen Ay',
        all_label: 'Tümü',
        // Summary headings
        sales: 'Satış',
        expenses: 'Gider',
        profit: 'Kâr',
        orders: 'Siparişler',
        items: 'Ürünler',
        discount: 'İndirim',
        today_summary: 'Bugün',
        totals_summary: 'Toplamlar',
        // Range controls
        start: 'Başlangıç:',
        end: 'Bitiş:',
        group: 'Gruplama:',
        apply: 'Uygula',
        daily: 'Günlük',
        monthly: 'Aylık',
        yearly: 'Yıllık',
        appTitle: 'Kâr Uygulaması',
        tagline: 'Günlük satışları ve giderleri girin, kârı anında görün.',
        todaysales: 'Bugünkü satışlar',
        todayexpenses: 'Bugünkü giderler',
        todayprofit: 'Bugünkü kâr',
        totalsales: 'Toplam satış',
        totalexpenses: 'Toplam gider',
        totalprofit: 'Toplam kâr',
        newrecord: 'Yeni kayıt',
        date: 'Tarih:',
        type: 'Tür:',
        amount: 'Tutar (SEK):',
        save: 'Kaydet',
        records: 'Kayıtlar',
        lastn: '(son 50)',
    },
    sv: {
        // Date range filters
        today_label: 'Idag',
        yesterday_label: 'Igår',
        this_week_label: 'Denna vecka',
        last_week_label: 'Förra veckan',
        this_month_label: 'Den här månaden',
        last_month_label: 'Förra månaden',
        all_label: 'Alla',
        // Summary headings
        sales: 'Försäljning',
        expenses: 'Utgifter',
        profit: 'Vinst',
        orders: 'Beställningar',
        items: 'Artiklar',
        discount: 'Rabatt',
        today_summary: 'Idag',
        totals_summary: 'Totaler',
        // Range controls
        start: 'Start:',
        end: 'Slut:',
        group: 'Grupp:',
        apply: 'Tillämpa',
        daily: 'Daglig',
        monthly: 'Månatlig',
        yearly: 'Årlig',
        appTitle: 'VinstApp',
        tagline: 'Ange dagliga försäljningar och kostnader och se vinsten direkt.',
        todaysales: 'Dagens försäljning',
        todayexpenses: 'Dagens kostnader',
        todayprofit: 'Dagens vinst',
        totalsales: 'Total försäljning',
        totalexpenses: 'Totala kostnader',
        totalprofit: 'Total vinst',
        newrecord: 'Ny post',
        date: 'Datum:',
        type: 'Typ:',
        amount: 'Belopp (SEK):',
        save: 'Spara',
        records: 'Poster',
        lastn: '(senaste 50)',
    },
};

function setLanguage(lang) {
    const t = translations[lang] || translations.en;
    // Header
    const titleEl = document.querySelector('.app-title');
    if (titleEl) titleEl.textContent = t.appTitle;
    const tagEl = document.querySelector('.tagline');
    if (tagEl) tagEl.textContent = t.tagline;
    // Card headings
    document.querySelectorAll('.card-sales h3').forEach(el => el.textContent = t.todaysales);
    document.querySelectorAll('.card-expense h3').forEach(el => el.textContent = t.todayexpenses);
    document.querySelectorAll('.card-profit h3').forEach(el => el.textContent = t.todayprofit);
    // Totals headings
    const total = document.querySelector('.total-summary');
    if (total) {
        const cards = total.querySelectorAll('.card');
        if (cards[0]) cards[0].querySelector('h3').textContent = t.totalsales;
        if (cards[1]) cards[1].querySelector('h3').textContent = t.totalexpenses;
        if (cards[2]) cards[2].querySelector('h3').textContent = t.totalprofit;
    }
    // New record form labels and heading
    const newRec = document.querySelector('.new-record');
    if (newRec) {
        newRec.querySelector('h2').textContent = t.newrecord;
        const labels = newRec.querySelectorAll('label');
        if (labels[0]) labels[0].textContent = t.date;
        if (labels[1]) labels[1].textContent = t.type;
        if (labels[2]) labels[2].textContent = t.amount;
        const btn = newRec.querySelector('button[type="submit"]');
        if (btn) btn.textContent = t.save;
    }
    // Records title
    const recSection = document.querySelector('.records-section h2');
    if (recSection) {
        recSection.childNodes[0].textContent = t.records + ' ';
        const suffix = document.getElementById('records-title-suffix');
        if (suffix) suffix.textContent = ' ' + t.lastn;
    }

    // Update summary headings (Today and Totals labels)
    const todayLabel = document.querySelector('.today-summary .summary-label');
    if (todayLabel) todayLabel.textContent = t.today_summary || 'Today';
    const totalLabel = document.querySelector('.total-summary .summary-label');
    if (totalLabel) totalLabel.textContent = t.totals_summary || 'Totals';
    // Update card headings in today and totals sections
    document.querySelectorAll('.today-summary .card h3').forEach((el, idx) => {
        switch (idx) {
            case 0: el.textContent = t.sales; break;
            case 1: el.textContent = t.expenses; break;
            case 2: el.textContent = t.profit; break;
            case 3: el.textContent = t.orders; break;
            case 4: el.textContent = t.items; break;
            case 5: el.textContent = t.discount; break;
        }
    });
    document.querySelectorAll('.total-summary .card h3').forEach((el, idx) => {
        switch (idx) {
            case 0: el.textContent = 'Total ' + t.sales.toLowerCase(); break;
            case 1: el.textContent = 'Total ' + t.expenses.toLowerCase(); break;
            case 2: el.textContent = 'Total ' + t.profit.toLowerCase(); break;
            case 3: el.textContent = 'Total ' + t.orders.toLowerCase(); break;
            case 4: el.textContent = 'Total ' + t.items.toLowerCase(); break;
            case 5: el.textContent = 'Total ' + t.discount.toLowerCase(); break;
        }
    });
    // Update quick filter button labels
    document.querySelectorAll('.filter-buttons button').forEach(btn => {
        const rt = btn.getAttribute('data-range');
        let labelKey;
        switch (rt) {
            case 'today': labelKey = 'today_label'; break;
            case 'yesterday': labelKey = 'yesterday_label'; break;
            case 'this-week': labelKey = 'this_week_label'; break;
            case 'last-week': labelKey = 'last_week_label'; break;
            case 'this-month': labelKey = 'this_month_label'; break;
            case 'last-month': labelKey = 'last_month_label'; break;
            case 'all': labelKey = 'all_label'; break;
            default: labelKey = null;
        }
        if (labelKey && t[labelKey]) btn.textContent = t[labelKey];
    });
    // Update range control labels and group options
    const startLbl = document.querySelector('label[for="range-start"]');
    const endLbl = document.querySelector('label[for="range-end"]');
    const groupLbl = document.querySelector('label[for="range-group"]');
    if (startLbl) startLbl.textContent = t.start;
    if (endLbl) endLbl.textContent = t.end;
    if (groupLbl) groupLbl.textContent = t.group;
    const applyBtn = document.getElementById('range-apply');
    if (applyBtn) applyBtn.textContent = t.apply;
    const groupSelect = document.getElementById('range-group');
    if (groupSelect) {
        groupSelect.querySelectorAll('option').forEach(opt => {
            const val = opt.value;
            if (val === 'daily') opt.textContent = t.daily;
            if (val === 'monthly') opt.textContent = t.monthly;
            if (val === 'yearly') opt.textContent = t.yearly;
        });
    }
}

function attachLanguageHandlers() {
    // Determine language code by button text (first two letters lowercased)
    document.querySelectorAll('.lang-buttons button').forEach(btn => {
        btn.addEventListener('click', async () => {
            const code = btn.textContent.trim().toLowerCase().slice(0, 2);
            // Update client side language immediately
            setLanguage(code);
            // Persist language on the server session
            try {
                await fetch('/set_lang?lang=' + encodeURIComponent(code));
            } catch (err) {
                console.warn('Failed to set language on server', err);
            }
        });
    });
}

// Attach Go Pro button handler
function attachGoProHandler() {
    const btn = document.getElementById('go-pro-btn');
    if (!btn) return;
    btn.addEventListener('click', async () => {
        const userId = btn.dataset.userId;
        if (!userId) return;
        if (!confirm('Upgrade to Pro plan?')) return;
        try {
            const res = await fetch('/api/change_plan', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId, plan: 'Pro' })
            });
            const data = await res.json();
            if (!res.ok || !data.success) {
                alert(data.error || 'Failed to upgrade plan');
                return;
            }
            alert('Plan upgraded to Pro.');
            location.reload();
        } catch (err) {
            alert('Error: ' + err);
        }
    });
}