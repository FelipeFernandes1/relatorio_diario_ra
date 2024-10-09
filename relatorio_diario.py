import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import openpyxl
import numpy as np
from fpdf import FPDF
from matplotlib.dates import DateFormatter

# Estilizar botões usando CSS
st.markdown("""
    <style>
    .stButton>button {
        background-color: #4CAF50; /* Cor de fundo */
        color: white; /* Cor do texto */
        padding: 10px 20px;
        border: none;
        border-radius: 5px; /* Bordas arredondadas */
        font-size: 16px; /* Tamanho da fonte */
        transition: background-color 0.3s; /* Transição suave */
    }
    .stButton>button:hover {
        background-color: #45a049; /* Cor de fundo ao passar o mouse */
    }
    </style>
""", unsafe_allow_html=True)


# Função para verificar o upload dos arquivos
def verificar_upload(base_nome):
    st.sidebar.markdown(f"<p style='font-size:18px; font-weight:bold;'>Faça o upload da base {base_nome}</p>", unsafe_allow_html=True)
    uploaded_file = st.sidebar.file_uploader("", type=["xlsx"], key=base_nome)
    if uploaded_file is not None:
        df = pd.read_excel(uploaded_file, header=3)
        colunas = ['Id HugMe', 'Data Reclamação', 'Status Hugme', 'Atribuido Para', 'Moderação status',
                   'Moderação motivo']
        if len(df) == 10000:
            st.warning("ATENÇÃO, o tamanho da base é 10000 (limite Hugme)!")
        if not all(col in df.columns for col in colunas):
            st.error("Faltam algumas colunas necessárias. Extraia um novo arquivo.")
            return None
        return df[colunas]
    return None


# Função para gerar gráficos e relatórios
def gerar_graficos_e_relatorio(df_Geral):
    # Limpeza e tratamento dos dados
    df_Geral['Data Reclamação'] = pd.to_datetime(df_Geral['Data Reclamação'], format='%d/%m/%Y')
    df_Geral['Atribuido Para'].fillna('Sem atribuição', inplace=True)
    df_Geral['Atribuido Para'] = df_Geral['Atribuido Para'].apply(lambda x: 'Atribuído' if x != 'Sem atribuição' else x)
    df_Geral.rename(columns={'Atribuido Para': 'Status'}, inplace=True)

    # Calcular o intervalo de datas
    data_minima = df_Geral['Data Reclamação'].min().strftime('%d/%m/%Y')
    data_maxima = df_Geral['Data Reclamação'].max().strftime('%d/%m/%Y')
    # Adicionar texto com o intervalo de datas
    st.markdown(f"<h3 style='font-size:16px;'>Casos criados entre {data_minima} e {data_maxima}</h3>",
                unsafe_allow_html=True)

    # Função para gerar gráfico de casos pendentes
    def plot_pending_cases(df, paginas):
        pending_data = {
            "Página": [],
            "Sem atribuição": [],
            "Atribuído": []
        }
        for pagina in paginas:
            df_pendentes = df[(df['Status Hugme'] == 'Novo') & (df['Página'] == pagina)]
            sem_atribuicao = df_pendentes[df_pendentes['Status'] == 'Sem atribuição'].shape[0]
            atribuido = df_pendentes[df_pendentes['Status'] == 'Atribuído'].shape[0]
            pending_data["Página"].append(pagina)
            pending_data["Sem atribuição"].append(sem_atribuicao)
            pending_data["Atribuído"].append(atribuido)
        df_pending = pd.DataFrame(pending_data)
        df_pending.set_index('Página', inplace=True)
        df_pending['Total'] = df_pending['Sem atribuição'] + df_pending['Atribuído']
        df_pending_sorted = df_pending.sort_values(by='Total', ascending=True)
        colors = ['#808080', '#ec7b20']
        fig, ax = plt.subplots(figsize=(9, 2))
        bars = df_pending_sorted[['Atribuído', 'Sem atribuição']].plot(kind='barh', stacked=True, ax=ax, width=0.9,                                                                       color=colors)
        ax.tick_params(axis='x', labelsize=10)
        ax.tick_params(axis='y', labelsize=10)
        ax.set_ylabel('')
        for i, (sem_atribuicao, atribuido) in enumerate(
                zip(df_pending_sorted['Sem atribuição'], df_pending_sorted['Atribuído'])):
            total = sem_atribuicao + atribuido
            if total >= 15:
                ax.annotate(f'{atribuido}', xy=(atribuido, i), xytext=(-10, 0), textcoords='offset points', ha='center',
                            va='center', fontsize=10, color='white')
                ax.annotate(f'{sem_atribuicao}', xy=(atribuido + sem_atribuicao, i), xytext=(-10, 0),
                            textcoords='offset points', ha='center', va='center', fontsize=10, color='black')
        plt.tight_layout()
        return fig  # Retorna a figura criada

    # Função para gerar gráfico de média móvel simples (período de 7 dias) com cores diferentes para cada página
    def plot_cumulative_daily_average(df, paginas):
        fig, ax = plt.subplots(figsize=(9, 4))
        max_y_value = 0

        # Definindo uma paleta de cores para as páginas
        colors = ['#5800d9', '#ff5733', '#33c1ff', '#85e033']  # Você pode adicionar mais cores aqui

        for i, pagina in enumerate(paginas):
            df_pagina = df[df['Página'] == pagina].set_index('Data Reclamação').resample('D').size()
            dates = df_pagina.index
            values = df_pagina.values

            if len(values) == 0:
                continue

            # Cálculo da média móvel simples com janela de 7 dias
            rolling_average = pd.Series(values).rolling(window=7, min_periods=1).mean()

            # Usando cores diferentes para cada linha de página
            ax.plot(dates[:len(rolling_average)], rolling_average, label=f'{pagina}', linewidth=2,
                    color=colors[i % len(colors)])

            # Adicionando etiquetas de texto apenas para médias acima de 5 a cada 7 dias
            for j in range(len(rolling_average)):
                if j % 7 == 0 and rolling_average[j] >= 5:  # Exibir apenas a cada 7 dias
                    ax.text(dates[j], rolling_average[j] + 1, f'{int(rolling_average[j])}', fontsize=8, ha='center',
                            va='bottom', color=colors[i % len(colors)])

            if rolling_average.max() > max_y_value:
                max_y_value = rolling_average.max()

        if max_y_value > 0:  # Configurar para não exibir linha abaixo de determinada média
            ylim_upper = max_y_value * 1.4
            ax.set_ylim(0, ylim_upper)

        ax.legend(loc='upper right', fontsize=8, framealpha=0.6)
        ax.xaxis.set_major_formatter(DateFormatter('%d/%m'))
        ax.tick_params(axis='both', which='major', labelsize=10)

        plt.tight_layout()
        return fig  # Retorna a figura criada

    # Função para mostrar a tabela das últimas datas dos casos pendentes
    def show_latest_pending_dates(df):
        last_dates_attributed = df[(df['Status Hugme'] == 'Novo') & (df['Status'] == 'Atribuído')]
        last_date_attributed = last_dates_attributed.groupby('Página')['Data Reclamação'].min().reset_index()
        last_date_attributed.rename(columns={'Data Reclamação': 'Última Data Atribuída'}, inplace=True)
        last_dates_unattributed = df[(df['Status Hugme'] == 'Novo') & (df['Status'] == 'Sem atribuição')]
        last_date_unattributed = last_dates_unattributed.groupby('Página')['Data Reclamação'].min().reset_index()
        last_date_unattributed.rename(columns={'Data Reclamação': 'Última Data Sem Atribuição'}, inplace=True)
        last_dates = pd.merge(last_date_attributed, last_date_unattributed, on='Página', how='outer')
        # Formatar as colunas de datas para o formato dia/mês/ano
        last_dates['Última Data Atribuída'] = last_dates['Última Data Atribuída'].dt.strftime('%d/%m/%Y')
        last_dates['Última Data Sem Atribuição'] = last_dates['Última Data Sem Atribuição'].dt.strftime('%d/%m/%Y')
        st.markdown("<h3 style='font-size:18px;'>Últimas datas</h3>", unsafe_allow_html=True)
        st.table(last_dates)

    # Gráficos
    st.subheader("Casos pendentes de resposta pública")
    paginas = ['Pay', 'Classificados', 'Zap', 'Viva']
    fig_pendentes = plot_pending_cases(df_Geral, paginas)
    st.pyplot(fig_pendentes)  # Passa a figura gerada

    # Exibir a tabela de últimas datas dos casos pendentes
    show_latest_pending_dates(df_Geral)

    # Linha horizontal para separar as seções
    st.markdown("<hr style='border: 2px solid #4d4d4d;'>", unsafe_allow_html=True)

    st.subheader("Incoming - média móvel janela de 7 dias")
    fig_acumulada = plot_cumulative_daily_average(df_Geral, paginas)
    st.pyplot(fig_acumulada)  # Passa a figura gerada

# Interface principal
st.title("Relatório Diário RA")

df_Geral = pd.DataFrame(
    columns=['Id HugMe', 'Data Reclamação', 'Status Hugme', 'Atribuido Para', 'Moderação status', 'Moderação motivo',
             'Página'])

# Carregar as bases
df_Classificados = verificar_upload("Classificados")
if df_Classificados is not None:
    df_Classificados['Página'] = 'Classificados'
    df_Geral = pd.concat([df_Geral, df_Classificados], ignore_index=True)
    # excluindo as reclamações a serem moderadas p página correta
    df_Geral = df_Geral.loc[~((df_Geral['Moderação motivo'] == 'A reclamação de outra empresa') & (
    df_Geral['Moderação status'] == 'Pendente'))]
    df_Geral.reset_index(inplace=True, drop=True)

df_Pay = verificar_upload("Pay")
if df_Pay is not None:
    df_Pay['Página'] = 'Pay'
    df_Geral = pd.concat([df_Geral, df_Pay], ignore_index=True)
    # tratando os valores de data
    #df_Geral['Data Reclamação'] = df_Geral['Data Reclamação'].dt.date
    # excluindo as reclamações a serem moderadas p página correta
    df_Geral = df_Geral.loc[~((df_Geral['Moderação motivo'] == 'A reclamação de outra empresa') & (
    df_Geral['Moderação status'] == 'Pendente'))]
    df_Geral.reset_index(inplace=True, drop=True)

df_Zap = verificar_upload("Zap")
if df_Zap is not None:
    df_Zap['Página'] = 'Zap'
    df_Geral = pd.concat([df_Geral, df_Zap], ignore_index=True)
    # excluindo as reclamações a serem moderadas p página correta
    df_Geral = df_Geral.loc[~((df_Geral['Moderação motivo'] == 'A reclamação de outra empresa') & (
    df_Geral['Moderação status'] == 'Pendente'))]
    df_Geral.reset_index(inplace=True, drop=True)

df_Viva = verificar_upload("Viva")
if df_Viva is not None:
    df_Viva['Página'] = 'Viva'
    df_Geral = pd.concat([df_Geral, df_Viva], ignore_index=True)
    # excluindo as reclamações a serem moderadas p página correta
    df_Geral = df_Geral.loc[~((df_Geral['Moderação motivo'] == 'A reclamação de outra empresa') & (
    df_Geral['Moderação status'] == 'Pendente'))]
    df_Geral.reset_index(inplace=True, drop=True)

if not df_Geral.empty:
    gerar_graficos_e_relatorio(df_Geral)

