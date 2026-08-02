# fred_api.py
import requests
import json
from datetime import datetime, timedelta

API_KEY = "c7472f825bc72c3019d384789fd33672"
BASE_URL = "https://api.stlouisfed.org/fred"

class FredAPI:
    def __init__(self, api_key=API_KEY):
        self.api_key = api_key
        self.base_url = BASE_URL
        self.cache = {}
        self.cache_timeout = 3600  # 1 hora
    
    def _make_request(self, endpoint, params):
        """Realiza una petición a la API de FRED"""
        cache_key = f"{endpoint}_{json.dumps(params, sort_keys=True)}"
        
        # Verificar caché
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if (datetime.now() - timestamp).seconds < self.cache_timeout:
                return cached_data
        
        try:
            params['api_key'] = self.api_key
            params['file_type'] = 'json'
            
            url = f"{self.base_url}/{endpoint}"
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            self.cache[cache_key] = (data, datetime.now())
            return data
        except Exception as e:
            print(f"Error en API FRED: {e}")
            return None
    
    def get_series_observations(self, series_id, start_date=None, end_date=None, limit=100):
        """
        Obtiene observaciones de una serie de FRED
        series_id: ID de la serie (ej: 'GDP', 'CPI', 'FEDFUNDS')
        """
        params = {
            'series_id': series_id,
            'limit': limit,
            'sort_order': 'desc'
        }
        
        if start_date:
            params['observation_start'] = start_date
        if end_date:
            params['observation_end'] = end_date
        
        data = self._make_request('series/observations', params)
        
        if data and 'observations' in data:
            observations = []
            for obs in data['observations']:
                if obs['value'] != '.':
                    observations.append({
                        'date': obs['date'],
                        'value': float(obs['value'])
                    })
            return observations
        return []
    
    def get_series_info(self, series_id):
        """Obtiene información de una serie"""
        params = {'series_id': series_id}
        data = self._make_request('series', params)
        
        if data and 'seriess' in data and len(data['seriess']) > 0:
            series = data['seriess'][0]
            return {
                'id': series.get('id'),
                'title': series.get('title'),
                'frequency': series.get('frequency'),
                'units': series.get('units'),
                'seasonal_adjustment': series.get('seasonal_adjustment'),
                'observation_start': series.get('observation_start'),
                'observation_end': series.get('observation_end'),
                'popularity': series.get('popularity')
            }
        return None
    
    def search_series(self, search_text, limit=10):
        """Busca series por texto"""
        params = {
            'search_text': search_text,
            'limit': limit
        }
        data = self._make_request('series/search', params)
        
        if data and 'seriess' in data:
            results = []
            for series in data['seriess']:
                results.append({
                    'id': series.get('id'),
                    'title': series.get('title'),
                    'frequency': series.get('frequency'),
                    'units': series.get('units'),
                    'popularity': series.get('popularity')
                })
            return results
        return []
    
    def get_latest_value(self, series_id):
        """Obtiene el valor más reciente de una serie"""
        observations = self.get_series_observations(series_id, limit=1)
        if observations:
            return observations[0]['value']
        return None
    
    def get_historical_data(self, series_id, days=365):
        """Obtiene datos históricos de los últimos N días"""
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        return self.get_series_observations(series_id, start_date, end_date)

# Series comunes de FRED
FRED_SERIES = {
    'GDP': 'Producto Interno Bruto (PIB)',
    'GDPC1': 'PIB Real',
    'GDPPOT': 'PIB Potencial',
    'CPIAUCSL': 'Índice de Precios al Consumidor (IPC)',
    'CPI': 'Inflación (IPC)',
    'FEDFUNDS': 'Tasa de Fondos Federales',
    'DGS10': 'Rendimiento del Bono del Tesoro a 10 años',
    'UNRATE': 'Tasa de Desempleo',
    'PAYEMS': 'Empleo Total No Agrícola',
    'INDPRO': 'Producción Industrial',
    'RETAIL': 'Ventas Minoristas',
    'HOUST': 'Inicios de Construcción de Viviendas',
    'M1SL': 'Oferta Monetaria M1',
    'M2SL': 'Oferta Monetaria M2',
    'DEXUSEU': 'Tipo de Cambio USD/EUR',
    'DEXMXUS': 'Tipo de Cambio MXN/USD',
    'DEXCAUS': 'Tipo de Cambio CAD/USD',
    'DEXJPUS': 'Tipo de Cambio JPY/USD',
    'DEXCHUS': 'Tipo de Cambio CNY/USD',
    'DEXBZUS': 'Tipo de Cambio BRL/USD'
}

# Instancia global
fred_api = FredAPI()