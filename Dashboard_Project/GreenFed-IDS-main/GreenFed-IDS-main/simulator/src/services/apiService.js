
const sendTelemetry = async (apiUrl, token, telemetry) => {
    const response = await fetch(`${apiUrl}/api/telemetry`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify(telemetry)
    });

    const text = await response.text();
    let result = null;
    try {
        result = text ? JSON.parse(text) : null;
    } catch {
        result = { message: text };
    }

    if (!response.ok) {
        const error = new Error(
            result?.message || result?.error || `API error ${response.status}`
        );
        error.status = response.status;
        throw error;
    }

    return result;
};

module.exports = sendTelemetry;
