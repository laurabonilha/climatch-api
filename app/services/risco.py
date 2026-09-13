def classificar_risco(dados: dict) -> str:
    chance_chuva = dados["chance_chuva"]
    vento_max = dados["vento_max"]

    if chance_chuva > 60 or vento_max > 40:
        return "arriscado"
    elif chance_chuva > 30:
        return "moderado"
    else:
        return "favoravel"