def classificar_risco(dados: dict, chance_chuva_limite: int = 60, vento_limite: float = 40.0) -> str:
    chance_chuva = dados["chance_chuva"]
    vento_max = dados["vento_max"]

    if chance_chuva > chance_chuva_limite or vento_max > vento_limite:
        return "arriscado"
    elif chance_chuva > chance_chuva_limite * 0.5:
        return "moderado"
    else:
        return "favoravel"


LIMITES_POR_TIPO = {
    "casamento": {"chance_chuva_limite": 30, "vento_limite": 25.0},
    "corrida": {"chance_chuva_limite": 70, "vento_limite": 45.0},
    "piquenique": {"chance_chuva_limite": 25, "vento_limite": 20.0},
    "praia": {"chance_chuva_limite": 35, "vento_limite": 30.0},
    "churrasco": {"chance_chuva_limite": 35, "vento_limite": 30.0},
    "futebol": {"chance_chuva_limite": 65, "vento_limite": 40.0},
    "show_ao_ar_livre": {"chance_chuva_limite": 45, "vento_limite": 25.0},
    "festa_infantil": {"chance_chuva_limite": 30, "vento_limite": 25.0},
    "trilha": {"chance_chuva_limite": 40, "vento_limite": 35.0},
    "acampamento": {"chance_chuva_limite": 30, "vento_limite": 35.0},
    "feira_ao_ar_livre": {"chance_chuva_limite": 55, "vento_limite": 35.0},
    "formatura_externa": {"chance_chuva_limite": 30, "vento_limite": 25.0},
}

LIMITE_GENERICO = {"chance_chuva_limite": 60, "vento_limite": 40.0}


def obter_limites_por_tipo(tipo_evento: str | None) -> dict:
    if not tipo_evento:
        return LIMITE_GENERICO
    return LIMITES_POR_TIPO.get(tipo_evento.strip().lower(), LIMITE_GENERICO)


def tipo_evento_reconhecido(tipo_evento: str | None) -> bool:
    if not tipo_evento:
        return False
    return tipo_evento.strip().lower() in LIMITES_POR_TIPO


def gerar_recomendacao(tipo_evento: str, classificacao: str, tipo_reconhecido: bool = True) -> str:
    if classificacao == "arriscado":
        texto = f"Condições arriscadas para um evento do tipo '{tipo_evento}'. Considere um plano B ou remarcar."
    elif classificacao == "moderado":
        texto = f"Condições medianas para '{tipo_evento}'. Vale ter um plano de contingência."
    else:
        texto = f"Condições favoráveis para '{tipo_evento}'."

    if not tipo_reconhecido:
        texto = f"Tipo de evento '{tipo_evento}' não mapeado — usando critérios genéricos de risco. {texto}"

    return texto


CLASSIFICACAO_RANK = {"favoravel": 0, "moderado": 1, "arriscado": 2}


def escolher_melhor(candidatos: list[dict]) -> dict | None:
    validos = [c for c in candidatos if c["classificacao"] in CLASSIFICACAO_RANK]
    if not validos:
        return None
    return min(validos, key=lambda c: (CLASSIFICACAO_RANK[c["classificacao"]], c["chance_chuva"]))


def obter_condicoes_no_horario(
    horarios: list[str],
    temperaturas: list[float],
    chances_chuva: list[int],
    ventos: list[float],
    hora: str,
) -> dict | None:
    hora_procurada = hora[:2] + ":00"
    for i, horario_completo in enumerate(horarios):
        if horario_completo.endswith(hora_procurada):
            return {
                "hora": hora,
                "temperatura": temperaturas[i],
                "chance_chuva": chances_chuva[i],
                "vento": ventos[i],
            }
    return None


HORA_MIN_RECOMENDADA = 7
HORA_MAX_RECOMENDADA = 22


def calcular_melhor_horario(horarios: list[str], chances_chuva: list[int]) -> tuple[str, str]:
    indices_candidatos = [
        i for i in range(len(horarios))
        if HORA_MIN_RECOMENDADA <= i <= HORA_MAX_RECOMENDADA
    ]
    indice_melhor = min(indices_candidatos, key=lambda i: chances_chuva[i])
    horario_completo = horarios[indice_melhor]
    horario_formatado = horario_completo.split("T")[1]

    if indice_melhor < 12:
        motivo = "menor chance de chuva no período da manhã"
    else:
        motivo = "menor chance de chuva no período da tarde ou noite"

    return horario_formatado, motivo