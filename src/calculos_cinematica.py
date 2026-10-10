"""
Calculos cinematica MRUV e geracao de graficos estaticos (Matplotlib).
Experimentos em Plano Inclinado: 5 deg e 10 deg.
"""

import math
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

# Dados de laboratorio
EXP_5DEG = {
    "angulo": 5.0,
    "a_exp": 0.658,
    "a_teor": 0.855,
    "posicoes": [0.20, 0.40, 0.60, 0.80],
    "tempos": [0.787, 1.098, 1.346, 1.553]
}

EXP_10DEG = {
    "angulo": 10.0,
    "a_exp": 1.432,
    "a_teor": 1.7035,
    "posicoes": [0.20, 0.40, 0.60, 0.80],
    "tempos": [0.533, 0.745, 0.913, 1.054]
}

def imprimir_tabela_cinematica():
    print("=" * 85)
    print("      CÁLCULOS PONTO A PONTO DAS EQUAÇÕES CINEMÁTICAS DO MRUV")
    print("=" * 85)

    for exp in [EXP_5DEG, EXP_10DEG]:
        a = exp["a_exp"]
        ang = exp["angulo"]
        print(f"\n>>> INCLINAÇÃO: {ang}° (Aceleração Experimental a = {a:.3f} m/s²)")
        print(f"{'Ponto':<6} | {'x (m)':<8} | {'t (s)':<8} | {'x(t) calc (m)':<14} | {'v(t) (m/s)':<12} | {'v(x) Torricelli (m/s)':<22}")
        print("-" * 85)

        for i in range(len(exp["posicoes"])):
            n = i + 1
            x_m = exp["posicoes"][i]
            t_m = exp["tempos"][i]

            x_calc = 0.5 * a * (t_m ** 2)
            v_t = a * t_m
            v_x = math.sqrt(2 * a * x_m)

            print(f"{n:<6} | {x_m:<8.2f} | {t_m:<8.3f} | {x_calc:<14.4f} | {v_t:<12.4f} | {v_x:<22.4f}")

def gerargrafico_posicao_tempo(output_path: Path):
    fig, ax = plt.subplots(figsize=(8, 5), dpi=150)
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')

    # Pontos experimentais
    ax.scatter(EXP_5DEG["tempos"], EXP_5DEG["posicoes"], color='#1f77b4', s=60, zorder=5, 
               label='Pontos Experimentais (5°)')
    ax.scatter(EXP_10DEG["tempos"], EXP_10DEG["posicoes"], color='#d62728', marker='s', s=60, zorder=5, 
               label='Pontos Experimentais (10°)')

    # Curva parabólica para 5° (0.5 * 0.658 = 0.329)
    t_smooth_5 = np.linspace(0, max(EXP_5DEG["tempos"]) * 1.05, 100)
    x_smooth_5 = 0.5 * EXP_5DEG["a_exp"] * (t_smooth_5 ** 2)
    ax.plot(t_smooth_5, x_smooth_5, color='#1f77b4', linestyle='--', linewidth=2,
            label=r'Ajuste Parabólico (5°): $x = 0.329 t^2$')

    # Curva parabólica para 10° (0.5 * 1.432 = 0.716)
    t_smooth_10 = np.linspace(0, max(EXP_10DEG["tempos"]) * 1.05, 100)
    x_smooth_10 = 0.5 * EXP_10DEG["a_exp"] * (t_smooth_10 ** 2)
    ax.plot(t_smooth_10, x_smooth_10, color='#d62728', linestyle='--', linewidth=2,
            label=r'Ajuste Parabólico (10°): $x = 0.716 t^2$')

    # Configuração dos eixos
    ax.set_title(r'Posição vs. Tempo no MRUV: $x(t) = \frac{1}{2}a t^2$', fontsize=13, fontweight='bold', pad=12)
    ax.set_xlabel(r'Tempo $t$ (s)', fontsize=11)
    ax.set_ylabel(r'Posição $x$ (m)', fontsize=11)

    ax.set_xlim(0, 1.8)
    ax.set_ylim(0, 0.9)
    ax.set_xticks(np.arange(0, 1.9, 0.3))
    ax.set_yticks(np.arange(0, 1.0, 0.15))

    ax.legend(fontsize=10, loc='upper left', frameon=True)
    ax.grid(True, linestyle=':', alpha=0.7)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_path, bbox_inches='tight')
    plt.close()
    print(f"Gráfico de posição vs tempo salvo em: {output_path}")

def gerargrafico_linearizacao(output_path: Path):
    fig, ax = plt.subplots(figsize=(8, 5), dpi=150)
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')

    z_5 = np.array(EXP_5DEG["tempos"])**2
    z_10 = np.array(EXP_10DEG["tempos"])**2

    ax.scatter(z_5, EXP_5DEG["posicoes"], color='#1f77b4', s=60, zorder=5, label='Dados Experimentais (5°)')
    ax.scatter(z_10, EXP_10DEG["posicoes"], color='#d62728', marker='s', s=60, zorder=5, label='Dados Experimentais (10°)')

    z_line_5 = np.linspace(0, max(z_5) * 1.05, 100)
    ax.plot(z_line_5, 0.329 * z_line_5, color='#1f77b4', linestyle='-', linewidth=2, label=r'Reta MMQ (5°): $x = 0.329 z$')

    z_line_10 = np.linspace(0, max(z_10) * 1.05, 100)
    ax.plot(z_line_10, 0.716 * z_line_10, color='#d62728', linestyle='-', linewidth=2, label=r'Reta MMQ (10°): $x = 0.716 z$')

    ax.set_title(r'Linearização: Posição vs. $t^2$ ($z = t^2$)', fontsize=13, fontweight='bold', pad=12)
    ax.set_xlabel(r'Tempo ao Quadrado $z = t^2$ (s²)', fontsize=11)
    ax.set_ylabel(r'Posição $x$ (m)', fontsize=11)

    ax.legend(fontsize=10, loc='upper left', frameon=True)
    ax.grid(True, linestyle=':', alpha=0.7)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_path, bbox_inches='tight')
    plt.close()
    print(f"Gráfico de linearização salvo em: {output_path}")

def main():
    diretorio_raiz = Path(__file__).resolve().parent.parent
    caminho_posicao = diretorio_raiz / "assets" / "grafico_posicao_tempo.png"
    caminho_linearizacao = diretorio_raiz / "assets" / "grafico_linearizacao.png"

    imprimir_tabela_cinematica()
    gerargrafico_posicao_tempo(caminho_posicao)
    gerargrafico_linearizacao(caminho_linearizacao)

if __name__ == "__main__":
    main()
