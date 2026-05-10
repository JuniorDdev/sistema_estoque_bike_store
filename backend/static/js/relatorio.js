const API_URL = window.location.origin;

const periodSelect = document.getElementById("periodSelect");
const refreshReportBtn = document.getElementById("refreshReportBtn");
const reportTableBody = document.getElementById("reportTableBody");
const kpiSales = document.getElementById("kpiSales");
const kpiItems = document.getElementById("kpiItems");
const kpiRevenue = document.getElementById("kpiRevenue");
const kpiTicket = document.getElementById("kpiTicket");
const logoutBtn = document.getElementById("logoutBtn");

function formatBRL(value) {
    return `R$ ${Number(value).toFixed(2).replace(".", ",")}`;
}

async function checkAuth() {
    const response = await fetch(`${API_URL}/api/check-auth`, { credentials: "include" });
    const data = await response.json();
    if (!data.authenticated) {
        window.location.href = "/";
    }
}

async function loadReport() {
    const period = periodSelect.value;
    const response = await fetch(`${API_URL}/api/reports/sales?period=${period}`, {
        credentials: "include",
    });
    const data = await response.json();

    if (!response.ok) {
        alert(data.error || "Erro ao carregar relatorio.");
        return;
    }

    kpiSales.textContent = data.summary.total_sales;
    kpiItems.textContent = data.summary.total_items;
    kpiRevenue.textContent = formatBRL(data.summary.total_revenue);
    kpiTicket.textContent = formatBRL(data.summary.average_ticket);

    reportTableBody.innerHTML = "";
    let hasRows = false;

    data.sales.forEach((sale) => {
        sale.items.forEach((item) => {
            hasRows = true;
            const row = document.createElement("tr");
            row.innerHTML = `
                <td>#${sale.id}</td>
                <td>${new Date(sale.created_at).toLocaleString("pt-BR")}</td>
                <td>${item.product_code} - ${item.product_name}</td>
                <td>${item.quantity}</td>
                <td>${formatBRL(item.unit_price)}</td>
                <td>${formatBRL(item.line_total)}</td>
            `;
            reportTableBody.appendChild(row);
        });
    });

    if (!hasRows) {
        reportTableBody.innerHTML = "<tr><td colspan='6'>Nenhuma venda no periodo.</td></tr>";
    }
}

function exportReport(format) {
    const period = periodSelect.value;
    window.open(`${API_URL}/api/reports/sales/export?period=${period}&format=${format}`, "_blank");
}

refreshReportBtn.addEventListener("click", loadReport);

document.querySelectorAll(".export-btn").forEach((button) => {
    button.addEventListener("click", () => exportReport(button.dataset.format));
});

logoutBtn.addEventListener("click", async () => {
    await fetch(`${API_URL}/api/logout`, { method: "POST", credentials: "include" });
    window.location.href = "/";
});

document.addEventListener("DOMContentLoaded", async () => {
    await checkAuth();
    await loadReport();
});
