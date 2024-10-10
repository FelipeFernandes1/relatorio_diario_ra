import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import openpyxl
import numpy as np
from fpdf import FPDF
from matplotlib.dates import DateFormatter
import matplotlib.dates as mdates


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
    df_Geral = df_Geral.loc[~((df_Geral['Moderação motivo'] == 'A reclamação de outra empresa') & (
    df_Geral['Moderação status'] == 'Pendente'))]
    df_Geral.reset_index(inplace=True, drop=True)

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
        bars = df_pending_sorted[['Atribuído', 'Sem atribuição']].plot(kind='barh', stacked=True, ax=ax, width=0.9,
                                                                       color=colors)
        ax.tick_params(axis='x', labelsize=10)
        ax.tick_params(axis='y', labelsize=10)
        ax.set_ylabel('')

        for i, (sem_atribuicao, atribuido) in enumerate(
                zip(df_pending_sorted['Sem atribuição'], df_pending_sorted['Atribuído'])):
            total = sem_atribuicao + atribuido
            if total >= 0:
                ax.annotate(f'{atribuido}', xy=(atribuido, i), xytext=(-10, 0), textcoords='offset points', ha='center',
                            va='center', fontsize=10, color='white')
                ax.annotate(f'{sem_atribuicao}', xy=(atribuido + sem_atribuicao, i), xytext=(10, 0),
                            textcoords='offset points', ha='center', va='center', fontsize=10, color='black')
        plt.tight_layout()
        return fig  # Retorna a figura criada

    paginas = ['Pay', 'Classificados', 'Zap', 'Viva']  # Adicione mais páginas conforme necessário

    # Gráficos para Pay e Classificados
    st.subheader("Casos pendentes de resposta pública - Pay e Classificados")
    paginas_pc = ['Pay', 'Classificados']
    fig_pendentes_pc = plot_pending_cases(df_Geral, paginas_pc)
    st.pyplot(fig_pendentes_pc)  # Passa a figura gerada

    # Gráficos para Zap e Viva
    st.subheader("Casos pendentes de resposta pública - Zap e Viva")
    paginas_zv = ['Zap', 'Viva']
    fig_pendentes_zv = plot_pending_cases(df_Geral, paginas_zv)
    st.pyplot(fig_pendentes_zv)  # Passa a figura gerada

    # Função para plotar o gráfico de contagem semanal para páginas específicas, com linhas roxa e laranja
    def plot_total_por_semana(dataframe, paginas, y_lim_factor=1.2):
        """
        Plota o total de reclamações por semana para as páginas selecionadas.

        Args:
            dataframe (pd.DataFrame): O DataFrame contendo os dados.
            paginas (list): Lista de páginas a serem plotadas.
            y_lim_factor (float): Fator para aumentar o limite do eixo Y (padrão 1.2 para 20% a mais).
        """
        # Converte a coluna "Data Reclamação" para o tipo datetime
        dataframe['Data Reclamação'] = pd.to_datetime(dataframe['Data Reclamação'])

        # Define o domingo como início da semana (freq='W-SUN')
        dataframe['Semana'] = dataframe['Data Reclamação'].dt.to_period('W-SUN').apply(lambda r: r.end_time)

        # Iniciando o gráfico
        fig, ax = plt.subplots(figsize=(9, 4))

        # Variável para armazenar o valor máximo das contagens
        max_valor = 0

        # Lista de cores fixas: roxa e laranja
        cores = ['#5800d9', '#ff5733']

        # Itera sobre cada página selecionada e plota uma linha separada para cada uma
        for idx, pagina in enumerate(paginas):
            df_filtrado = dataframe[dataframe['Página'] == pagina]

            # Conta o número de reclamações por semana para a página selecionada
            contagem_semanal = df_filtrado.groupby('Semana').size()

            # Atualiza o valor máximo para definir o limite do eixo Y
            max_valor = max(max_valor, contagem_semanal.max())

            # Plota a linha para a página atual
            plt.plot(contagem_semanal.index, contagem_semanal.values, marker='o', label=pagina, color=cores[idx])

            # Adiciona os valores totais em cada ponto da linha
            for i, valor in enumerate(contagem_semanal.values):
                plt.text(contagem_semanal.index[i], valor, str(valor), ha='center', va='bottom', fontsize=10)

        # Definindo o eixo X com os domingos no formato dia/mês
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
        plt.xticks(rotation=45)

        # Definindo o eixo X com os domingos
        plt.xticks(contagem_semanal.index, contagem_semanal.index.date, rotation=45)

        # Ajustando o limite do eixo Y com o fator fornecido
        plt.ylim(0, max_valor * y_lim_factor)

        # Adicionando legenda para identificar as páginas
        plt.legend()

        # Títulos e rótulos
        #plt.title(f'Total de Casos por Semana - Páginas: {", ".join(paginas)}')
        plt.xlabel('Contagem até o final do domingo')

        plt.tight_layout()
        return fig  # Retorna a figura criada

    # Função para mostrar a tabela das últimas datas dos casos pendentes
    def show_latest_pending_dates(df):
        last_dates_attributed = df[(df['Status Hugme'] == 'Novo') & (df['Status'] == 'Atribuído')]
        last_date_attributed = last_dates_attributed.groupby('Página')['Data Reclamação'].min().reset_index()
        last_date_attributed.rename(columns={'Data Reclamação': 'Atribuído'}, inplace=True)
        last_dates_unattributed = df[(df['Status Hugme'] == 'Novo') & (df['Status'] == 'Sem atribuição')]
        last_date_unattributed = last_dates_unattributed.groupby('Página')['Data Reclamação'].min().reset_index()
        last_date_unattributed.rename(columns={'Data Reclamação': 'Sem Atribuição'}, inplace=True)
        last_dates = pd.merge(last_date_attributed, last_date_unattributed, on='Página', how='outer')
        # Formatar as colunas de datas para o formato dia/mês/ano
        last_dates['Atribuído'] = last_dates['Atribuído'].dt.strftime('%d/%m/%Y')
        last_dates['Sem Atribuição'] = last_dates['Sem Atribuição'].dt.strftime('%d/%m/%Y')
        st.markdown("<h3 style='font-size:18px;'>Casos pendentes mais antigos</h3>", unsafe_allow_html=True)
        st.table(last_dates)

    # Exibir a tabela de últimas datas dos casos pendentes
    show_latest_pending_dates(df_Geral)

    # Linha horizontal para separar as seções
    st.markdown("<hr style='border: 2px solid #4d4d4d;'>", unsafe_allow_html=True)

    # Gráficos para Incoming - média móvel
    st.subheader("Incoming Semanal - Pay e Classificados")
    fig_acumulada_pc = plot_total_por_semana(df_Geral, ['Classificados', 'Pay'], y_lim_factor=1.2)
    st.pyplot(fig_acumulada_pc)  # Passa a figura gerada

    st.subheader("Incoming Semanal - Zap e Viva")
    fig_acumulada_zv = plot_total_por_semana(df_Geral, ['Zap', 'Viva'], y_lim_factor=1.2)
    st.pyplot(fig_acumulada_zv)  # Passa a figura gerada

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


df_Pay = verificar_upload("Pay")
if df_Pay is not None:
    df_Pay['Página'] = 'Pay'
    df_Geral = pd.concat([df_Geral, df_Pay], ignore_index=True)


df_Zap = verificar_upload("Zap")
if df_Zap is not None:
    df_Zap['Página'] = 'Zap'
    df_Geral = pd.concat([df_Geral, df_Zap], ignore_index=True)


df_Viva = verificar_upload("Viva")
if df_Viva is not None:
    df_Viva['Página'] = 'Viva'
    df_Geral = pd.concat([df_Geral, df_Viva], ignore_index=True)


if not df_Geral.empty:
    gerar_graficos_e_relatorio(df_Geral)
