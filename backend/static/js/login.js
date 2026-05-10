const API_URL = window.location.origin;

const loginForm = document.getElementById("loginForm");
const errorMessage = document.getElementById("errorMessage");

loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    errorMessage.textContent = "";

    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value.trim();

    if (!username || !password) {
        errorMessage.textContent = "Preencha todos os campos.";
        return;
    }

    try {
        const response = await fetch(`${API_URL}/api/login`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            credentials: "include",
            body: JSON.stringify({
                username,
                password
            })
        });

        const data = await response.json();

        if (!response.ok) {
            errorMessage.textContent = data.error || "Erro no login";
            return;
        }

        alert("✅ Login realizado com sucesso!");
        window.location.href = "/dashboard";

    } catch (error) {
        console.error(error);
        errorMessage.textContent = "Erro ao conectar com o servidor Flask.";
    }
});

async function checkAuth() {
    try {
        const response = await fetch(`${API_URL}/api/check-auth`, {
            credentials: "include"
        });

        const data = await response.json();

        if (data.authenticated) {
            window.location.href = "/dashboard";
        }

    } catch (error) {
        console.error("Erro ao verificar login:", error);
    }
}

checkAuth();