import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Acompanhamento de Estoque", layout="wide")

st.title("📦 Acompanhamento de Saída de Produtos do Estoque")
st.write("Sincronizado automaticamente com a pasta no Google Drive.")

# IDs extraídos dos seus links de compartilhamento
ID_VENDAS = "1jHR_qxraTvxkbzEaeom0p5AseA5gA-of"   # 03.02.37.csv
ID_ESTOQUE = "1dAA2n-5fMX1wD8FuHbTiLp8ryMG41ZAL"  # 02.03.04.csv

# URLs de download direto do Google Drive
URL_VENDAS = f"https://drive.google.com/uc?export=download&id={ID_VENDAS}"
URL_ESTOQUE = f"https://drive.google.com/uc?export=download&id={ID_ESTOQUE}"

@st.cache_data(ttl=1800)  # Recarrega do Drive a cada 30 minutos
def carregar_dados():
    # Leitura com fallback de encoding para CSVs de sistemas legados
    df_vendas = pd.read_csv(URL_VENDAS, sep=';', encoding='latin1', low_memory=False)
    df_estoque = pd.read_csv(URL_ESTOQUE, sep=';', encoding='latin1', low_memory=False)
    return df_vendas, df_estoque

def processar_dados(df_vendas, df_estoque):
    # Tratar data de operação
    df_vendas['Dt. Operacao'] = pd.to_datetime(df_vendas['Dt. Operacao'], dayfirst=True, errors='coerce')
    
    # Tratar quantidades vendidas (ajuste de vírgula/ponto)
    df_vendas['Qtde'] = pd.to_numeric(
        df_vendas['Qtde'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False),
        errors='coerce'
    ).fillna(0)
    
    # Data mais recente do arquivo de vendas serve como referência de "hoje"
    data_max = df_vendas['Dt. Operacao'].max()
    data_min = df_vendas['Dt. Operacao'].min()
    dias_periodo = max((data_max - data_min).days + 1, 1)

    # Agrupamento de Vendas por Produto (SKU)
    vendas_agg = df_vendas.groupby('Produto').agg(
        Ultima_Venda=('Dt. Operacao', 'max'),
        Total_Vendido=('Qtde', 'sum')
    ).reset_index()

    # Média Diária em cx/dz
    vendas_agg['Média Diária (cx/dz)'] = vendas_agg['Total_Vendido'] / dias_periodo

    # Padronização da chave para junção (código do produto)
    vendas_agg['Produto'] = vendas_agg['Produto'].astype(str).str.strip()
    df_estoque['Cod'] = df_estoque['Cod'].astype(str).str.strip()

    # Cruzamento Estoque x Vendas (Muitos para um)
    df_resultado = pd.merge(df_estoque, vendas_agg, left_on='Cod', right_on='Produto', how='left')

    # Tratar Estoque Disponível
    df_resultado['Disp.'] = pd.to_numeric(
        df_resultado['Disp.'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False),
        errors='coerce'
    ).fillna(0)

    df_resultado['Média Diária (cx/dz)'] = df_resultado['Média Diária (cx/dz)'].fillna(0)

    # Dias de Estoque = Estoque Disponível / Média de Venda Diária
    df_resultado['Dias de Estoque'] = np.where(
        df_resultado['Média Diária (cx/dz)'] > 0,
        df_resultado['Disp.'] / df_resultado['Média Diária (cx/dz)'],
        9999
    )

    # Dias sem Saída/Venda
    df_resultado['Dias sem Venda'] = (data_max - df_resultado['Ultima_Venda']).dt.days

    # Regra de Alertas
    def classificar_alerta(dias):
        if pd.isna(dias) or dias > 14:
            return '🚨 Crítico'
        elif dias > 7:
            return '🟠 Alerta'
        elif dias > 3:
            return '🟡 Atenção'
        else:
            return '✅ OK'

    df_resultado['Status'] = df_resultado['Dias sem Venda'].apply(classificar_alerta)

    colunas_finais = [
        'Cod', 'Descricao', 'UN', 'Disp.',
        'Ultima_Venda', 'Média Diária (cx/dz)',
        'Dias de Estoque', 'Dias sem Venda', 'Status'
    ]

    return df_resultado[colunas_finais].sort_values(by='Dias sem Venda', ascending=False)

try:
    with st.spinner("Conectando ao Google Drive e atualizando indicadores..."):
        df_v, df_e = carregar_dados()
        df_final = processar_dados(df_v, df_e)

        # Filtro interativo na barra lateral
        st.sidebar.header("Filtros")
        status_selecionados = st.sidebar.multiselect(
            "Filtrar por Status:",
            options=['🚨 Crítico', '🟠 Alerta', '🟡 Atenção', '✅ OK'],
            default=['🚨 Crítico', '🟠 Alerta', '🟡 Atenção', '✅ OK']
        )
        
        df_filtrado = df_final[df_final['Status'].isin(status_selecionados)]

        # Exibição de Métricas no Topo
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Criticos (+14 dias sem venda)", len(df_final[df_final['Status'] == '🚨 Crítico']))
        col2.metric("Em Alerta (+7 dias)", len(df_final[df_final['Status'] == '🟠 Alerta']))
        col3.metric("Em Atenção (+3 dias)", len(df_final[df_final['Status'] == '🟡 Atenção']))
        col4.metric("OK", len(df_final[df_final['Status'] == '✅ OK']))

        # Formatação para exibição amigável
        df_display = df_filtrado.copy()
        df_display['Ultima_Venda'] = df_display['Ultima_Venda'].dt.strftime('%d/%m/%Y').fillna('Sem registro de venda')
        df_display['Média Diária (cx/dz)'] = df_display['Média Diária (cx/dz)'].round(2)
        df_display['Dias de Estoque'] = df_display['Dias de Estoque'].replace(9999, 'Sem Giro').apply(
            lambda x: round(x, 1) if isinstance(x, (int, float)) else x
        )

        st.dataframe(df_display, use_container_width=True)

        col_btn1, col_btn2 = st.columns([1, 4])
        with col_btn1:
            if st.button("🔄 Forçar Atualização do Drive"):
                st.cache_data.clear()
                st.rerun()

        with col_btn2:
            csv_data = df_filtrado.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button(
                label="📥 Baixar Tabela (CSV)",
                data=csv_data,
                file_name="acompanhamento_estoque.csv",
                mime="text/csv"
            )

except Exception as e:
    st.error(f"Erro ao processar dados do Drive: {e}")
