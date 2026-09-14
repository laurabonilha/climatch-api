import httpx

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


class CidadeNaoEncontrada(Exception):
    pass


class PrevisaoIndisponivel(Exception):
    pass


def buscar_coordenadas(cidade: str) -> tuple[float, float]:
    resposta = httpx.get(GEOCODING_URL, params={
        "name": cidade,
        "count": 1,
        "language": "pt",
        "format": "json",
    })
    resposta.raise_for_status()
    dados = resposta.json()

    if "results" not in dados or len(dados["results"]) == 0:
        raise CidadeNaoEncontrada(f"Cidade '{cidade}' não encontrada")

    resultado = dados["results"][0]
    return resultado["latitude"], resultado["longitude"]


def buscar_previsao(lat: float, lon: float, data: str) -> dict:
    resposta = httpx.get(FORECAST_URL, params={
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,wind_speed_10m_max",
        "timezone": "auto",
        "start_date": data,
        "end_date": data,
    })
    
    if resposta.status_code == 400:
        raise PrevisaoIndisponivel(f"Data '{data}' fora do intervalo suportado pela previsão")

    resposta.raise_for_status()
    dados = resposta.json()

    if not dados["daily"]["time"]:
        raise PrevisaoIndisponivel(f"Sem previsão disponível para a data {data}")

    return {
        "temp_min": dados["daily"]["temperature_2m_min"][0],
        "temp_max": dados["daily"]["temperature_2m_max"][0],
        "chance_chuva": dados["daily"]["precipitation_probability_max"][0],
        "vento_max": dados["daily"]["wind_speed_10m_max"][0],
    }
    
def buscar_previsao_horaria(lat: float, lon: float, data: str) -> dict:
    resposta = httpx.get(FORECAST_URL, params={
        "latitude": lat,
        "longitude": lon,
        "hourly": "precipitation_probability",
        "timezone": "auto",
        "start_date": data,
        "end_date": data,
    })

    if resposta.status_code == 400:
        raise PrevisaoIndisponivel(f"Data '{data}' fora do intervalo suportado")

    resposta.raise_for_status()
    dados = resposta.json()

    if not dados["hourly"]["time"]:
        raise PrevisaoIndisponivel(f"Sem previsão horária disponível para a data {data}")

    return {
        "horarios": dados["hourly"]["time"],
        "chance_chuva_horaria": dados["hourly"]["precipitation_probability"],
    }