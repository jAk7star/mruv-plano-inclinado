"""
Consome a especificacao MRUV JSON e gera uma pagina HTML interativa.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(frozen=True)
class SerieExperimental:
    angulo: float
    posicoes: np.ndarray
    tempos: np.ndarray
    aceleracao_teorica: float | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SerieExperimental":
        try:
            angulo = float(data["angulo"])
            posicoes = np.asarray(data["posicoes"], dtype=float)
            tempos = np.asarray(data["tempos"], dtype=float)
            aceleracao_teorica = data.get("aceleracao_teorica")
            if aceleracao_teorica is not None:
                aceleracao_teorica = float(aceleracao_teorica)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                "Cada serie precisa de angulo, posicoes e tempos numericos."
            ) from exc

        if not np.isfinite(angulo) or not 0 <= angulo <= 90:
            raise ValueError("O angulo deve estar entre 0 e 90 graus.")
        if posicoes.ndim != 1 or tempos.ndim != 1 or len(posicoes) != len(tempos):
            raise ValueError("Posicoes e tempos devem ser listas 1D de mesmo tamanho.")
        if len(posicoes) < 2:
            raise ValueError("Cada serie precisa ter ao menos dois pontos.")
        if not np.all(np.isfinite(posicoes)) or not np.all(np.isfinite(tempos)):
            raise ValueError("Posicoes e tempos devem conter apenas valores finitos.")
        if np.any(tempos <= 0) or np.unique(tempos).size < 2:
            raise ValueError("Os tempos devem ser positivos e nao podem ser todos iguais.")
        if aceleracao_teorica is not None and (
            not np.isfinite(aceleracao_teorica) or aceleracao_teorica < 0
        ):
            raise ValueError("A aceleracao teorica deve ser finita e nao negativa.")

        return cls(
            angulo=angulo,
            posicoes=posicoes,
            tempos=tempos,
            aceleracao_teorica=aceleracao_teorica,
        )

    @classmethod
    def from_dataset(cls, data: dict[str, Any]) -> "SerieExperimental":
        try:
            pontos = data["points"]
            return cls.from_dict(
                {
                    "angulo": data["inclination_deg"],
                    "posicoes": [ponto["position_m"] for ponto in pontos],
                    "tempos": [ponto["time_s"] for ponto in pontos],
                    "aceleracao_teorica": data.get("theoretical_acceleration_m_s2"),
                }
            )
        except (KeyError, TypeError) as exc:
            raise ValueError(
                "Cada input_dataset precisa de inclination_deg e points com position_m/time_s."
            ) from exc


@dataclass(frozen=True)
class ResultadoAjuste:
    z: np.ndarray
    media_x: float
    media_z: float
    desvio_absoluto_x: np.ndarray
    desvio_absoluto_z: np.ndarray
    coeficiente: float
    intercepto: float
    aceleracao_experimental: float
    aceleracao_teorica: float
    erro_relativo_percentual: float | None


def ajustar_mruv(serie: SerieExperimental, gravidade: float) -> ResultadoAjuste:
    z = serie.tempos**2
    media_x = float(np.mean(serie.posicoes))
    media_z = float(np.mean(z))
    delta_x = serie.posicoes - media_x
    delta_z = z - media_z
    denominador = float(np.sum(delta_z**2))
    if denominador == 0:
        raise ValueError("Nao e possivel ajustar uma reta: os valores de t^2 sao iguais.")

    coeficiente = float(np.sum(delta_z * delta_x) / denominador)
    intercepto = media_x - coeficiente * media_z
    aceleracao_teorica = serie.aceleracao_teorica
    if aceleracao_teorica is None:
        aceleracao_teorica = gravidade * float(np.sin(np.deg2rad(serie.angulo)))
    aceleracao_experimental = 2 * coeficiente
    erro_relativo_percentual = (
        abs(aceleracao_experimental - aceleracao_teorica) / aceleracao_teorica * 100
        if aceleracao_teorica > 0
        else None
    )

    return ResultadoAjuste(
        z=z,
        media_x=media_x,
        media_z=media_z,
        desvio_absoluto_x=np.abs(delta_x),
        desvio_absoluto_z=np.abs(delta_z),
        coeficiente=coeficiente,
        intercepto=intercepto,
        aceleracao_experimental=aceleracao_experimental,
        aceleracao_teorica=aceleracao_teorica,
        erro_relativo_percentual=erro_relativo_percentual,
    )


def criar_documento_vegalite(
    series: list[SerieExperimental],
    resultados: list[ResultadoAjuste],
    delta_x: float,
    gravidade: float,
) -> dict[str, Any]:
    registros: list[dict[str, Any]] = []
    relatorios: list[dict[str, Any]] = []

    for serie, resultado in zip(series, resultados, strict=True):
        angulo = serie.angulo
        x_minimo = float(np.min(serie.posicoes))
        x_maximo = float(np.max(serie.posicoes))
        x_margem = (x_maximo - x_minimo) / 12
        t_minimo = float(np.min(serie.tempos))
        t_maximo = float(np.max(serie.tempos))
        t_margem = (t_maximo - t_minimo) / 12
        z_minimo = float(np.min(resultado.z))
        z_maximo = float(np.max(resultado.z))
        z_margem = (z_maximo - z_minimo) / 12

        for ponto_id, tempo, z, posicao in zip(
            range(1, len(serie.tempos) + 1),
            serie.tempos,
            resultado.z,
            serie.posicoes,
            strict=True,
        ):
            registros.append(
                {
                    "angulo": angulo,
                    "tipo": "Dados medidos",
                    "id": ponto_id,
                    "tempo_s": float(tempo),
                    "tempo_quadrado_s2": float(z),
                    "posicao_m": float(posicao),
                }
            )

        tempos_suaves = np.linspace(t_minimo, t_maximo, 300)
        for tempo in tempos_suaves:
            z = float(tempo**2)
            posicao_ajustada = resultado.coeficiente * z + resultado.intercepto
            posicao_teorica = (
                0.5 * resultado.aceleracao_teorica * z + resultado.intercepto
            )
            for tipo, posicao in (
                ("Ajuste MMQ", posicao_ajustada),
                ("Curva teórica", posicao_teorica),
            ):
                if x_minimo - x_margem <= posicao <= x_maximo + x_margem:
                    registros.append(
                        {
                            "angulo": angulo,
                            "tipo": tipo,
                            "tempo_s": float(tempo),
                            "tempo_quadrado_s2": z,
                            "posicao_m": float(posicao),
                        }
                    )

        for tempo, z, posicao in (
            (t_minimo - t_margem, z_minimo - z_margem, x_minimo - x_margem),
            (t_maximo + t_margem, z_maximo + z_margem, x_maximo + x_margem),
        ):
            registros.append(
                {
                    "angulo": angulo,
                    "tipo": "Limites de escala",
                    "tempo_s": tempo,
                    "tempo_quadrado_s2": z,
                    "posicao_m": posicao,
                }
            )

        relatorios.append(
            {
                "angulo_deg": angulo,
                "media_posicao_m": resultado.media_x,
                "media_tempo_quadrado_s2": resultado.media_z,
                "desvios_absolutos_posicao_m": resultado.desvio_absoluto_x.tolist(),
                "desvios_absolutos_tempo_quadrado_s2": resultado.desvio_absoluto_z.tolist(),
                "coeficiente_C_m_s2": resultado.coeficiente,
                "intercepto_b_m": resultado.intercepto,
                "aceleracao_experimental_m_s2": resultado.aceleracao_experimental,
                "aceleracao_teorica_m_s2": resultado.aceleracao_teorica,
                "erro_relativo_percentual": resultado.erro_relativo_percentual,
            }
        )

    angulos = [serie.angulo for serie in series]
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "description": "Dados e ajustes interativos do experimento de MRUV.",
        "title": "MRUV no plano inclinado",
        "data": {"values": registros},
        "usermeta": {
            "experiment": {
                "sensor_gap_m": delta_x,
                "gravity_m_s2": gravidade,
            },
            "results_by_angle": relatorios,
        },
        "params": [
            {
                "name": "anguloSelecionado",
                "value": angulos[0],
                "bind": {
                    "input": "select",
                    "options": angulos,
                    "name": "Ângulo (graus): ",
                },
            }
        ],
        "hconcat": [
            {
                "width": 400,
                "height": 360,
                "title": "Posição x vs. tempo t (MRUV - parábola)",
                "layer": [
                    {
                        "transform": [
                            {
                                "filter": "datum.angulo == anguloSelecionado && datum.tipo == 'Limites de escala'"
                            }
                        ],
                        "mark": {"type": "point", "opacity": 0, "size": 1},
                        "encoding": {
                            "x": {
                                "field": "tempo_s",
                                "type": "quantitative",
                                "scale": {"nice": False, "zero": False},
                                "axis": {"title": "Tempo t (s)", "tickCount": 6},
                            },
                            "y": {
                                "field": "posicao_m",
                                "type": "quantitative",
                                "scale": {"nice": False, "zero": False},
                                "axis": {"title": "Posição x (m)", "tickCount": 6},
                            },
                        },
                    },
                    {
                        "transform": [
                            {
                                "filter": "datum.angulo == anguloSelecionado && datum.tipo == 'Dados medidos'"
                            }
                        ],
                        "mark": {"type": "point", "filled": True, "size": 90},
                        "encoding": {
                            "x": {"field": "tempo_s", "type": "quantitative"},
                            "y": {"field": "posicao_m", "type": "quantitative"},
                            "color": {
                                "field": "tipo",
                                "type": "nominal",
                                "scale": {
                                    "domain": ["Dados medidos", "Ajuste MMQ", "Curva teórica"],
                                    "range": ["#0072B2", "#D55E00", "#009E73"],
                                },
                                "legend": {"title": "Série"},
                            },
                            "tooltip": [
                                {"field": "angulo", "type": "quantitative", "title": "Ângulo (graus)"},
                                {"field": "id", "type": "ordinal", "title": "Ponto"},
                                {"field": "tempo_s", "type": "quantitative", "title": "Tempo (s)", "format": ".3f"},
                                {"field": "posicao_m", "type": "quantitative", "title": "Posição (m)", "format": ".3f"},
                            ],
                        },
                    },
                    {
                        "transform": [
                            {
                                "filter": "datum.angulo == anguloSelecionado && datum.tipo == 'Ajuste MMQ'"
                            }
                        ],
                        "mark": {"type": "line", "strokeWidth": 2.5, "clip": True},
                        "encoding": {
                            "x": {"field": "tempo_s", "type": "quantitative"},
                            "y": {"field": "posicao_m", "type": "quantitative"},
                            "color": {
                                "field": "tipo",
                                "type": "nominal",
                                "scale": {
                                    "domain": ["Dados medidos", "Ajuste MMQ", "Curva teórica"],
                                    "range": ["#0072B2", "#D55E00", "#009E73"],
                                },
                                "legend": {"title": "Série"},
                            },
                            "tooltip": [
                                {"field": "tipo", "type": "nominal", "title": "Curva"},
                                {"field": "tempo_s", "type": "quantitative", "title": "Tempo (s)", "format": ".3f"},
                                {"field": "posicao_m", "type": "quantitative", "title": "Posição ajustada (m)", "format": ".3f"},
                            ],
                        },
                    },
                    {
                        "transform": [
                            {
                                "filter": "datum.angulo == anguloSelecionado && datum.tipo == 'Curva teórica'"
                            }
                        ],
                        "mark": {"type": "line", "strokeWidth": 2.5, "clip": True},
                        "encoding": {
                            "x": {"field": "tempo_s", "type": "quantitative"},
                            "y": {"field": "posicao_m", "type": "quantitative"},
                            "color": {
                                "field": "tipo",
                                "type": "nominal",
                                "scale": {
                                    "domain": ["Dados medidos", "Ajuste MMQ", "Curva teórica"],
                                    "range": ["#0072B2", "#D55E00", "#009E73"],
                                },
                                "legend": {"title": "Série"},
                            },
                            "tooltip": [
                                {"field": "tipo", "type": "nominal", "title": "Curva"},
                                {"field": "tempo_s", "type": "quantitative", "title": "Tempo (s)", "format": ".3f"},
                                {"field": "posicao_m", "type": "quantitative", "title": "Posição teórica (m)", "format": ".3f"},
                            ],
                        },
                    },
                ],
            },
            {
                "width": 400,
                "height": 360,
                "title": "Linearização: posição x vs. t² (ajuste MMQ)",
                "layer": [
                    {
                        "transform": [
                            {
                                "filter": "datum.angulo == anguloSelecionado && datum.tipo == 'Limites de escala'"
                            }
                        ],
                        "mark": {"type": "point", "opacity": 0, "size": 1},
                        "encoding": {
                            "x": {
                                "field": "tempo_quadrado_s2",
                                "type": "quantitative",
                                "scale": {"nice": False, "zero": False},
                                "axis": {"title": "Tempo ao quadrado t² (s²)", "tickCount": 6},
                            },
                            "y": {
                                "field": "posicao_m",
                                "type": "quantitative",
                                "scale": {"nice": False, "zero": False},
                                "axis": {"title": "Posição x (m)", "tickCount": 6},
                            },
                        },
                    },
                    {
                        "transform": [
                            {
                                "filter": "datum.angulo == anguloSelecionado && datum.tipo == 'Dados medidos'"
                            }
                        ],
                        "mark": {"type": "point", "filled": True, "size": 90},
                        "encoding": {
                            "x": {"field": "tempo_quadrado_s2", "type": "quantitative"},
                            "y": {"field": "posicao_m", "type": "quantitative"},
                            "color": {
                                "field": "tipo",
                                "type": "nominal",
                                "scale": {
                                    "domain": ["Dados medidos", "Ajuste MMQ"],
                                    "range": ["#0072B2", "#D55E00"],
                                },
                                "legend": {"title": "Série"},
                            },
                            "tooltip": [
                                {"field": "angulo", "type": "quantitative", "title": "Ângulo (graus)"},
                                {"field": "id", "type": "ordinal", "title": "Ponto"},
                                {"field": "tempo_quadrado_s2", "type": "quantitative", "title": "Tempo ao quadrado (s²)", "format": ".3f"},
                                {"field": "posicao_m", "type": "quantitative", "title": "Posição (m)", "format": ".3f"},
                            ],
                        },
                    },
                    {
                        "transform": [
                            {
                                "filter": "datum.angulo == anguloSelecionado && datum.tipo == 'Ajuste MMQ'"
                            }
                        ],
                        "mark": {"type": "line", "strokeWidth": 2.5, "clip": True},
                        "encoding": {
                            "x": {"field": "tempo_quadrado_s2", "type": "quantitative"},
                            "y": {"field": "posicao_m", "type": "quantitative"},
                            "color": {
                                "field": "tipo",
                                "type": "nominal",
                                "scale": {
                                    "domain": ["Dados medidos", "Ajuste MMQ"],
                                    "range": ["#0072B2", "#D55E00"],
                                },
                                "legend": {"title": "Série"},
                            },
                            "tooltip": [
                                {"field": "tipo", "type": "nominal", "title": "Curva"},
                                {"field": "tempo_quadrado_s2", "type": "quantitative", "title": "Tempo ao quadrado (s²)", "format": ".3f"},
                                {"field": "posicao_m", "type": "quantitative", "title": "Posição ajustada (m)", "format": ".3f"},
                            ],
                        },
                    },
                ],
            },
        ],
        "resolve": {
            "scale": {
                "x": "independent",
                "y": "independent",
                "color": "independent",
            }
        },
        "config": {
            "view": {"stroke": None},
            "axis": {"grid": True, "tickCount": 6},
            "legend": {"orient": "bottom"},
        },
    }


def criar_html_interativo(documento: dict[str, Any]) -> str:
    spec_json = json.dumps(documento, ensure_ascii=False, separators=(",", ":"))
    spec_json = spec_json.replace("</", "<\\/")

    return f'''<!doctype html>
<html lang="pt-BR">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="color-scheme" content="light">
    <title>MRUV no plano inclinado</title>
    <script src="https://cdn.jsdelivr.net/npm/vega@5"></script>
    <script src="https://cdn.jsdelivr.net/npm/vega-lite@5"></script>
    <script src="https://cdn.jsdelivr.net/npm/vega-embed@6"></script>
    <style>
        :root {{
            font-family: "Segoe UI", sans-serif;
            color: #18232b;
            background: #f3f6f5;
            font-synthesis: none;
            text-rendering: optimizeLegibility;
        }}
        * {{ box-sizing: border-box; }}
        body {{ margin: 0; }}
        header {{
            padding: 28px clamp(20px, 5vw, 64px) 20px;
            background: #123b46;
            color: #f5fbfa;
            border-bottom: 4px solid #e4a83a;
        }}
        h1 {{ margin: 0; font-size: 25px; font-weight: 650; }}
        header p {{ margin: 7px 0 0; color: #c6d7d8; font-size: 14px; }}
        main {{ max-width: 1320px; margin: auto; padding: 22px clamp(16px, 4vw, 48px) 44px; }}
        .results {{
            width: 100%; border-collapse: collapse; background: #fff;
            border: 1px solid #d8e1e0; margin-bottom: 18px; font-size: 14px;
        }}
        .results th, .results td {{ padding: 10px 14px; text-align: right; border-bottom: 1px solid #e5ebea; }}
        .results th:first-child, .results td:first-child {{ text-align: left; }}
        .results th {{ color: #42545b; background: #eaf0ef; font-weight: 600; }}
        .chart {{ background: #fff; border: 1px solid #d8e1e0; padding: 14px 10px; }}
        #status {{ color: #566970; font-size: 13px; padding: 8px 2px; }}
        #error {{ color: #a12b24; white-space: pre-wrap; }}
        @media (max-width: 700px) {{
            main {{ padding-inline: 10px; }}
            .results {{ font-size: 12px; }}
            .results th, .results td {{ padding: 8px 6px; }}
            .chart {{ overflow-x: auto; }}
        }}
    </style>
</head>
<body>
    <header>
        <h1>MRUV no plano inclinado</h1>
        <p>Trilho de ar com fotossensores · ajuste por mínimos quadrados</p>
    </header>
    <main>
        <table class="results" aria-label="Resultados do ajuste por ângulo">
            <thead><tr><th>Ângulo</th><th>a exp (m/s²)</th><th>a teor (m/s²)</th><th>Erro relativo</th></tr></thead>
            <tbody id="results"></tbody>
        </table>
        <div id="status">Carregando visualização...</div>
        <div class="chart"><div id="vis"></div></div>
        <div id="error" role="alert"></div>
    </main>
    <script id="vega-spec" type="application/json">{spec_json}</script>
    <script>
        const spec = JSON.parse(document.getElementById("vega-spec").textContent);
        const results = spec.usermeta.results_by_angle;
        document.getElementById("results").innerHTML = results.map(result => {{
            const error = result.erro_relativo_percentual;
            return `<tr><td>${{result.angulo_deg}}°</td>` +
                `<td>${{result.aceleracao_experimental_m_s2.toFixed(6)}}</td>` +
                `<td>${{result.aceleracao_teorica_m_s2.toFixed(4)}}</td>` +
                `<td>${{error === null ? "indefinido" : error.toFixed(3) + "%"}}</td></tr>`;
        }}).join("");
        vegaEmbed("#vis", spec, {{ actions: false, renderer: "svg" }})
            .then(() => {{ document.getElementById("status").textContent = ""; }})
            .catch(error => {{
                document.getElementById("status").textContent = "";
                document.getElementById("error").textContent =
                    "Não foi possível carregar os gráficos. Verifique a conexão com a internet e tente abrir o HTML novamente.\\n" + error;
            }});
    </script>
</body>
</html>
'''


class AgenteMRUV:
    def __init__(self, caminho_json: Path, arquivo_saida: Path) -> None:
        self.caminho_json = caminho_json
        self.arquivo_saida = arquivo_saida

    def carregar(self) -> tuple[float, float, list[SerieExperimental]]:
        try:
            especificacao = json.loads(self.caminho_json.read_text(encoding="utf-8"))
            if not isinstance(especificacao, dict):
                raise ValueError("A raiz do documento JSON deve ser um objeto.")
            metadados = especificacao["experiment_metadata"]
            delta_x = float(metadados["sensor_gap_m"])
            gravidade = float(metadados["gravity_m_s2"])
            datasets = especificacao["input_datasets"]
            if not isinstance(datasets, list):
                raise ValueError("input_datasets deve ser uma lista.")
            series = [SerieExperimental.from_dataset(item) for item in datasets]
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Especificacao invalida em {self.caminho_json}: {exc}") from exc

        if not np.isfinite(delta_x) or delta_x <= 0:
            raise ValueError("sensor_gap_m deve ser um numero positivo e finito.")
        if not np.isfinite(gravidade) or gravidade <= 0:
            raise ValueError("gravity_m_s2 deve ser um numero positivo e finito.")
        if not series:
            raise ValueError("input_datasets precisa conter ao menos um conjunto de dados.")
        return delta_x, gravidade, series

    def processar(self) -> None:
        delta_x, gravidade, series = self.carregar()
        resultados = [ajustar_mruv(serie, gravidade) for serie in series]
        documento = criar_documento_vegalite(series, resultados, delta_x, gravidade)
        self.arquivo_saida.parent.mkdir(parents=True, exist_ok=True)
        self.arquivo_saida.write_text(
            criar_html_interativo(documento),
            encoding="utf-8",
        )

        print(f"Distancia entre sensores: {delta_x:g} m")
        for serie, resultado in zip(series, resultados, strict=True):
            erro = (
                f"{resultado.erro_relativo_percentual:.3f}%"
                if resultado.erro_relativo_percentual is not None
                else "indefinido (aceleracao teorica nula)"
            )
            print(
                f"Angulo {serie.angulo:g} graus: C={resultado.coeficiente:.6g} m/s^2, "
                f"b={resultado.intercepto:.6g} m, "
                f"a_exp={resultado.aceleracao_experimental:.6g} m/s^2, "
                f"a_teor={resultado.aceleracao_teorica:.6g} m/s^2, "
                f"erro relativo={erro}"
            )
        print(f"Pagina HTML interativa: {self.arquivo_saida}")


def main() -> None:
    diretorio_raiz = Path(__file__).resolve().parent.parent
    entrada_padrao = diretorio_raiz / "data" / "especificacao_mruv.json"
    saida_padrao = diretorio_raiz / "docs" / "relatorio_mruv.html"

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "entrada", nargs="?", type=Path, default=entrada_padrao,
        help=f"Documento JSON (padrao: {entrada_padrao.name})",
    )
    parser.add_argument(
        "-o", "--saida", type=Path, default=saida_padrao,
        help=f"Pagina HTML de saida (padrao: {saida_padrao.name})",
    )
    argumentos = parser.parse_args()

    try:
        AgenteMRUV(argumentos.entrada, argumentos.saida).processar()
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
