const API_URL = window.location.origin;

const productForm = document.getElementById("productForm");
const productsTableBody = document.getElementById("productsTableBody");
const logoutBtn = document.getElementById("logoutBtn");


async function checkAuth() {
    try {
        const response = await fetch(`${API_URL}/api/check-auth`, {
            credentials: "include"
        });

        const data = await response.json();

        if (!data.authenticated) {
            window.location.href = "/";
        }

    } catch (error) {
        alert("Erro ao conectar com o servidor Flask.");
        window.location.href = "/";
    }
}


async function loadProducts() {
    try {
        const response = await fetch(`${API_URL}/api/products`, {
            credentials: "include"
        });

        const products = await response.json();

        productsTableBody.innerHTML = "";

        if (products.length === 0) {
            productsTableBody.innerHTML = `
                <tr>
                    <td colspan="7" style="text-align:center;">
                        Nenhum produto cadastrado.
                    </td>
                </tr>
            `;
            return;
        }

        products.forEach(product => {
            const row = document.createElement("tr");

            row.innerHTML = `
                <td>${product.id}</td>
                <td>${product.code}</td>
                <td>${product.name}</td>
                <td>${product.category || "-"}</td>
                <td>R$ ${Number(product.price).toFixed(2).replace(".", ",")}</td>
                <td>${product.quantity}</td>
                <td>
                    <button class="btn-delete" onclick="deleteProduct(${product.id})">
                        Excluir
                    </button>
                </td>
            `;

            productsTableBody.appendChild(row);
        });

    } catch (error) {
        productsTableBody.innerHTML = `
            <tr>
                <td colspan="7" style="text-align:center;color:red;">
                    Erro ao carregar produtos.
                </td>
            </tr>
        `;
    }
}


productForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const productData = {
        code: document.getElementById("productCode").value.trim().toUpperCase(),
        name: document.getElementById("productName").value.trim(),
        category: document.getElementById("productCategory").value.trim(),
        price: document.getElementById("productPrice").value,
        quantity: document.getElementById("productQuantity").value,
        description: document.getElementById("productDescription").value.trim()
    };

    try {
        const response = await fetch(`${API_URL}/api/products`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            credentials: "include",
            body: JSON.stringify(productData)
        });

        const data = await response.json();

        if (!response.ok) {
            alert(data.error || "Erro ao adicionar produto.");
            return;
        }

        alert("Produto adicionado com sucesso!");

        productForm.reset();

        loadProducts();

    } catch (error) {
        alert("Erro ao conectar com o servidor.");
    }
});


async function deleteProduct(id) {
    const confirmDelete = confirm("Tem certeza que deseja excluir este produto?");

    if (!confirmDelete) return;

    try {
        const response = await fetch(`${API_URL}/api/products/${id}`, {
            method: "DELETE",
            credentials: "include"
        });

        const data = await response.json();

        if (!response.ok) {
            alert(data.error || "Erro ao excluir produto.");
            return;
        }

        alert("Produto excluido com sucesso!");

        loadProducts();

    } catch (error) {
        alert("Erro ao conectar com o servidor.");
    }
}


logoutBtn.addEventListener("click", async () => {
    try {
        await fetch(`${API_URL}/api/logout`, {
            method: "POST",
            credentials: "include"
        });

        window.location.href = "/";

    } catch (error) {
        window.location.href = "/";
    }
});


document.addEventListener("DOMContentLoaded", async () => {
    await checkAuth();
    await loadProducts();
});
