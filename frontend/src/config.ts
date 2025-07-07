// Détection automatique du protocole et du port
const protocol = window.location.protocol;
const hostname = window.location.hostname;
const port = window.location.port;

// URL de base de l'API en fonction de l'environnement
let apiBaseUrl: string;

if (process.env.NODE_ENV === 'development') {
  // En développement, utiliser le serveur React dev
  apiBaseUrl = 'https://localhost:443/api';
} else {
  // En production, utiliser la même origine que l'interface
  if (port && port !== '80' && port !== '443') {
    apiBaseUrl = `${protocol}//${hostname}:${port}/api`;
  } else {
    apiBaseUrl = `${protocol}//${hostname}/api`;
  }
}

export const API_BASE_URL = process.env.REACT_APP_API_URL || apiBaseUrl;

console.log('API Configuration:', {
  NODE_ENV: process.env.NODE_ENV,
  window_location: window.location.href,
  API_BASE_URL: API_BASE_URL
}); 