# exchange_api.py
import requests
import json
from datetime import datetime, timedelta

API_KEY = "ada65b1d20419450f7b34cb1"
BASE_URL = "https://v6.exchangerate-api.com/v6"

class ExchangeRateAPI:
    def __init__(self, api_key=API_KEY):
        self.api_key = api_key
        self.base_url = BASE_URL
        self.cache = {}
        self.cache_timeout = 3600  # 1 hora en segundos
        
    def get_exchange_rates(self, base_currency="USD"):
        """Obtiene tasas de cambio para una moneda base"""
        cache_key = f"rates_{base_currency}"
        
        # Verificar caché
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if (datetime.now() - timestamp).seconds < self.cache_timeout:
                return cached_data
        
        try:
            url = f"{self.base_url}/{self.api_key}/latest/{base_currency}"
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            if data.get('result') == 'success':
                self.cache[cache_key] = (data, datetime.now())
                return data
            else:
                print(f"Error en API: {data.get('error-type', 'Unknown error')}")
                return None
        except Exception as e:
            print(f"Error al obtener tasas de cambio: {e}")
            return None
    
    def convert_currency(self, amount, from_currency, to_currency):
        """Convierte una cantidad de una moneda a otra"""
        if from_currency == to_currency:
            return amount
        
        rates = self.get_exchange_rates(from_currency)
        if rates and 'conversion_rates' in rates:
            conversion_rate = rates['conversion_rates'].get(to_currency)
            if conversion_rate:
                return amount * conversion_rate
        return None
    
    def get_supported_currencies(self):
        """Obtiene lista de monedas soportadas"""
        try:
            url = f"{self.base_url}/{self.api_key}/codes"
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            if data.get('result') == 'success':
                return data.get('supported_codes', [])
            return []
        except Exception as e:
            print(f"Error al obtener monedas: {e}")
            return []
    
    def get_historical_rates(self, base_currency, target_currency, date):
        """Obtiene tasas históricas para una fecha específica"""
        try:
            rates = self.get_exchange_rates(base_currency)
            if rates and 'conversion_rates' in rates:
                return rates['conversion_rates'].get(target_currency)
            return None
        except Exception as e:
            print(f"Error al obtener tasa histórica: {e}")
            return None

# Instancia global para usar en toda la aplicación
exchange_api = ExchangeRateAPI()

# Monedas comunes para la aplicación
COMMON_CURRENCIES = [
    ('USD', 'Dólar Estadounidense'),
    ('EUR', 'Euro'),
    ('GBP', 'Libra Esterlina'),
    ('JPY', 'Yen Japonés'),
    ('MXN', 'Peso Mexicano'),
    ('CAD', 'Dólar Canadiense'),
    ('AUD', 'Dólar Australiano'),
    ('CHF', 'Franco Suizo'),
    ('CNY', 'Yuan Chino'),
    ('BRL', 'Real Brasileño'),
    ('ARS', 'Peso Argentino'),
    ('CLP', 'Peso Chileno'),
    ('COP', 'Peso Colombiano'),
    ('PEN', 'Sol Peruano')
]