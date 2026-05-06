// config.js
const API_BASE_URL = (() => {
    // Kontrollera om vi kör i Render-miljön
    if (window.location.hostname !== "localhost" && 
        window.location.hostname !== "127.0.0.1") {
        // Sätt din Render-backend URL här (din faktiska .onrender.com-adress)
        return "https://ai-chess-solution.onrender.com";
    }
    // Annars, använd lokal utvecklingsadress
    return "http://127.0.0.1:5000";
})();