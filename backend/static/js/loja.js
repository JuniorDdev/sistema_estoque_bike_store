const API_URL = window.location.origin;

const searchInput = document.getElementById("searchInput");
const saleQuantity = document.getElementById("saleQuantity");
const selectedProductLabel = document.getElementById("selectedProductLabel");
const searchResults = document.getElementById("searchResults");
const addItemBtn = document.getElementById("addItemBtn");
const saleItemsBody = document.getElementById("saleItemsBody");
const saleTotal = document.getElementById("saleTotal");
const finishSaleBtn = document.getElementById("finishSaleBtn");
const logoutBtn = document.getElementById("logoutBtn");

let selectedProduct = null;
let saleItems = [];

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

async function searchProducts(query) {
    const response = await fetch(`${API_URL}/api/store/products/search?q=${encodeURIComponent(query)}`, {
        credentials: "include"
    });
    return response.json();
}

function renderSearchResults(products) {
    searchResults.innerHTML = "";

    if (!products.length) {
        searchResults.innerHTML = "<p>Nenhum produto encontrado em estoque.</p>";
        return;
    }

    products.forEach((product) => {
        const item = document.createElement("button");
        item.type = "button";
        item.className = "search-item";
        item.textContent = `${product.code} - ${product.name} (Estoque: ${product.quantity})`;
        item.addEventListener("click", () => {
            selectedProduct = product;
            selectedProductLabel.value = `${product.code} - ${product.name}`;
            searchResults.innerHTML = "";
            searchInput.value = `${product.code} - ${product.name}`;
        });
        searchResults.appendChild(item);
    });
}

function renderSaleItems() {
    saleItemsBody.innerHTML = "";

    if (!saleItems.length) {
        saleItemsBody.innerHTML = "<tr><td colspan='6'>Nenhum item adicionado.</td></tr>";
        saleTotal.textContent = "Total: R$ 0,00";
        return;
    }

    let total = 0;

    saleItems.forEach((item, index) => {
        const lineTotal = item.quantity * Number(item.price);
        total += lineTotal;

        const row = document.createElement("tr");
        row.innerHTML = `
            <td>${item.code}</td>
            <td>${item.name}</td>
            <td>${formatBRL(item.price)}</td>
            <td>${item.quantity}</td>
            <td>${formatBRL(lineTotal)}</td>
            <td><button class="btn-delete" onclick="removeItem(${index})">Remover</button></td>
        `;
        saleItemsBody.appendChild(row);
    });

    saleTotal.textContent = `Total: ${formatBRL(total)}`;
}

window.removeItem = (index) => {
    saleItems.splice(index, 1);
    renderSaleItems();
};

searchInput.addEventListener("input", async () => {
    const q = searchInput.value.trim();
    if (q.length < 2) {
        searchResults.innerHTML = "";
        return;
    }
    const products = await searchProducts(q);
    renderSearchResults(products);
});

addItemBtn.addEventListener("click", () => {
    if (!selectedProduct) {
        alert("Selecione um produto na busca.");
        return;
    }

    const quantity = Number(saleQuantity.value);
    if (!Number.isInteger(quantity) || quantity <= 0) {
        alert("Informe uma quantidade valida.");
        return;
    }

    if (quantity > selectedProduct.quantity) {
        alert("Quantidade maior que o estoque disponivel.");
        return;
    }

    const found = saleItems.find((item) => item.product_id === selectedProduct.id);
    if (found) {
        if (found.quantity + quantity > selectedProduct.quantity) {
            alert("Soma da quantidade excede o estoque disponivel.");
            return;
        }
        found.quantity += quantity;
    } else {
        saleItems.push({
            product_id: selectedProduct.id,
            code: selectedProduct.code,
            name: selectedProduct.name,
            price: selectedProduct.price,
            quantity,
        });
    }

    selectedProduct = null;
    searchInput.value = "";
    selectedProductLabel.value = "";
    saleQuantity.value = "1";
    searchResults.innerHTML = "";
    renderSaleItems();
});

finishSaleBtn.addEventListener("click", async () => {
    if (!saleItems.length) {
        alert("Adicione itens antes de finalizar a venda.");
        return;
    }

    const payload = {
        items: saleItems.map((item) => ({
            product_id: item.product_id,
            quantity: item.quantity,
        })),
    };

    const response = await fetch(`${API_URL}/api/store/sales`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(payload),
    });

    const data = await response.json();
    if (!response.ok) {
        alert(data.error || "Erro ao registrar venda.");
        return;
    }

    alert(`Venda #${data.sale.id} registrada com sucesso.`);
    saleItems = [];
    renderSaleItems();
});

logoutBtn.addEventListener("click", async () => {
    await fetch(`${API_URL}/api/logout`, { method: "POST", credentials: "include" });
    window.location.href = "/";
});

document.addEventListener("DOMContentLoaded", async () => {
    await checkAuth();
    renderSaleItems();
});
