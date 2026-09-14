def classificar_risco(dados: dict, chance_chuva_limite: int = 60, vento_limite: float = 40.0) -> str:
    chance_chuva = dados["chance_chuva"]
    vento_max = dados["vento_max"]

    if chance_chuva > chance_chuva_limite or vento_max > vento_limite:
        return "arriscado"
    elif chance_chuva > chance_chuva_limite * 0.5:
        return "moderado"
    else:
        return "favoravel"


def obter_limites_por_tipo(tipo_evento: str) -> dict:
    limites_por_tipo = {
        "casamento": {"chance_chuva_limite": 30, "vento_limite": 25.0},
        "corrida": {"chance_chuva_limite": 70, "vento_limite": 45.0},
    }
    return limites_por_tipo.get(tipo_evento, {"chance_chuva_limite": 60, "vento_limite": 40.0})


def gerar_recomendacao(tipo_evento: str, classificacao: str) -> str:
    if classificacao == "arriscado":
        return f"Condições arriscadas para um evento do tipo '{tipo_evento}'. Considere um plano B ou remarcar."
    elif classificacao == "moderado":
        return f"Condições medianas para '{tipo_evento}'. Vale ter um plano de contingência."
    else:
        return f"Condições favoráveis para '{tipo_evento}'."


def calcular_melhor_horario(horarios: list[str], chances_chuva: list[int]) -> tuple[str, str]:
    indice_melhor = chances_chuva.index(min(chances_chuva))
    horario_completo = horarios[indice_melhor]
    horario_formatado = horario_completo.split("T")[1]

    if indice_melhor < 12:
        motivo = "menor chance de chuva no período da manhã"
    else:
        motivo = "menor chance de chuva no período da tarde ou noite"

    return horario_formatado, motivo