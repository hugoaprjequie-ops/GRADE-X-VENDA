import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Acompanhamento de Estoque", layout="wide")

st.title("📦 Acompanhamento de Saída de Produtos do Estoque")
st.write("Lendo dados automaticamente do Google Drive...")

# --- COLOQUE OS IDs DOS SEUS ARQUIVOS AQUI ---
ID_VENDAS = "COLOQUE_AQUI_O_ID_DO_ARQUIVO_03_02_37"
ID_ESTOQUE = "COLOQUE_AQUI_O_ID_DO_ARQUIVO_02_03_04"

# Converte o link de visualização em um link de download direto
URL_VENDAS = f"https://drive.google.com/uc?export=download&id={ID_VENDAS}"
URL_ESTOQUE = f"https://drive.google.com/uc?export=download&id={ID_ESTOQUE}"

@st.cache_data(ttl=3600) # Atualiza o cache a cada 1 hora
def carregar_dados():
    # Lê direto dos links do Drive
    df_vendas = pd.read_csv(URL_VENDAS, sep=';', encoding='latin1', low_memory=False)
    df_estoque = pd.read_csv(URL_ESTOQUE, sep=';', encoding='latin1', low_memory=False)
    return df_vendas, df_estoque

def processar_dados(df_vendas, df_estoque):
    # Ajustar colunas de datas
    df_vendas['Dt. Operacao'] = pd.to_datetime(df_vendas['Dt. Operacao'], dayfirst=True, errors='coerce')
    
    data_min = df_vendas['Dt. Operacao'].min()
    data_max = df_vendas['Dt. Operacao'].max()
    dias_periodo = (data_max - data_min).days
    if dias_periodo <= 0: dias_periodo = 1 
        
    vendas_agg = df_vendas.groupby('Produto').agg(
        Ultima_Venda=('Dt. Operacao', 'max'),
        Total_Vendido=('Qtde', 'sum')
    ).reset_index()
    
    vendas_agg['Média Diária (cx/dz)'] = vendas_agg['Total_Vendido'] / dias_periodo
    vendas_agg['Produto'] = vendas_agg['Produto'].astype(str)
    df_estoque['Cod'] = df_estoque['Cod'].astype(str)
    
    df_resultado = pd.merge(df_estoque, vendas_agg, left_on='Cod', right_on='Produto', how='left')
    
    df_resultado['Média Diária (cx/dz)'] = df_resultado['Média Diária (cx/dz)'].fillna(0)
    df_resultado['Disp.'] = pd.to_numeric(df_resultado['Disp.'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
    
    df_resultado['Dias de Estoque'] = np.where(
        df_resultado['Média Diária (cx/dz)'] > 0, 
        df_resultado['Disp.'] / df_resultado['Média Diária (cx/dz)'], 
        9999 
    )
    
    df_resultado['Dias sem Venda'] = (data_max - df_resultado['Ultima_Venda']).dt.days
    
    def definir_alerta(dias):
        if pd.isna(dias) or dias > 14: return '🚨 Crítico'
        elif dias > 7: return '🟠 Alerta'
        elif dias > 3: return '🟡 Atenção'
        else: return '✅ OK'
            
    df_resultado['Status'] = df_resultado['Dias sem Venda'].apply(definir_alerta)
    
    colunas_finais = ['Cod', 'Descricao', 'UN', 'Disp.', 'Ultima_Venda', 'Média Diária (cx/dz)', 'Dias de Estoque', 'Dias sem Venda', 'Status']
    return df_resultado[colunas_finais].sort_values(by='Dias sem Venda', ascending=False)

try:
    with st.spinner("Baixando e processando arquivos do Drive..."):
        df_v, df_e = carregar_dados()
        df_final = processar_dados(df_v, df_e)
        
        df_display = df_final.copy()
        df_display['Ultima_Venda'] = df_display['Ultima_Venda'].dt.strftime('%d/%m/%Y').fillna('Sem venda')
        df_display['Média Diária (cx/dz)'] = df_display['Média Diária (cx/dz)'].round(2)
        df_display['Dias de Estoque'] = df_display['Dias de Estoque'].replace(9999, 'Infinito').apply(
            lambda x: round(x, 1) if isinstance(x, (int, float)) else x
        )
        
        st.dataframe(df_display, use_container_width=True)
        
        # Botão para limpar cache se você atualizar o arquivo no Drive e quiser forçar a leitura
        if st.button("🔄 Atualizar Dados do Drive"):
            st.cache_data.clear()
            st.rerun()
            
except Exception as e:
    st.error(f"Erro ao carregar do Drive. Verifique se os arquivos estão como 'Qualquer pessoa com o link' e se os IDs estão corretos. Erro: {e}")
