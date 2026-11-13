const registerClient = async (apiUrl, displayName) => {
    const response = await fetch(`${apiUrl}/api/clients`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            displayName,
            agentMode: "simulated_agent"
        })
    });

    const text = await response.text();
    let result = null;
    try {
        result = text ? JSON.parse(text) : null;
    } catch {
        result = { message: text };
    }

    if (!response.ok) {
        throw new Error(
            result?.message || result?.error || "Client registration failed"
        );
    }

    const client = result?.data ?? result;
    const clientId = client?.client_id ?? client?.clientId;
    const token = client?.clientToken ?? client?.agentToken;

    if (!clientId || !token) {
        throw new Error("Client ID or authentication token missing");
    }

    return {
        clientId,
        displayName: client.display_name ?? client.displayName ?? displayName,
        token
    };
};

module.exports = registerClient;
