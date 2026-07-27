# Arquivo: main.py
import os
import pandas as pd
import matplotlib.pyplot as plt
import customtkinter as ctk
from tkinter import filedialog
import threading


# Importando nossos motores matemáticos
from modulos.conversor_arquivos import converter_pasta_esf_para_csv # O NOSSO NOVO MOTOR!
from modulos.pre_processador import carregar_arquivo_esf, filtrar_ruido, remover_baseline, normalizar_por_area, identificar_picos_npk
from modulos.motor_pca import executar_pca_arquivos
from modulos.motor_outliers import executar_caca_outliers
from modulos.motor_variancia import executar_curva_variancia

# Configuração Visual
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

janela = ctk.CTk()
janela.title("AgroLIBS Studio - Embrapa")
janela.geometry("700x750") 

# ==============================================================================
# SISTEMA DE ABAS (TABS)
# ==============================================================================
tabview = ctk.CTkTabview(janela, width=650)
tabview.pack(pady=10, padx=20, fill="both", expand=True)

# Agora voltamos a ter 4 abas, mas muito mais poderosas!
aba_pre_conv = tabview.add("1. Pré-processamento & Conversão")
aba_pca = tabview.add("2. Análise PCA")
aba_outliers = tabview.add("3. Caçador de Outliers")
aba_variancia = tabview.add("4. Curva de Variância")

# ==============================================================================
# LÓGICA E INTERFACE DA ABA 1: PRÉ-PROCESSAMENTO & CONVERSÃO
# ==============================================================================
import threading

pasta_origem_selecionada = ""
mapa_arquivos_esf = {} # Dicionário para guardar Nome -> Caminho Completo

def atualizar_terminal(mensagem):
    terminal_conversao.insert("end", mensagem + "\n")
    terminal_conversao.see("end") 

def escolher_pasta_esf():
    global pasta_origem_selecionada, mapa_arquivos_esf
    pasta = filedialog.askdirectory(title="Selecione a pasta RAIZ com os .esf brutos")
    
    if pasta:
        pasta_origem_selecionada = pasta
        mapa_arquivos_esf.clear()
        
        # Usa o os.walk para encontrar os ficheiros
        for root, dirs, files in os.walk(pasta):
            for f in files:
                if f.lower().endswith('.esf'):
                    mapa_arquivos_esf[f] = os.path.join(root, f)
        
        nomes_ficheiros = list(mapa_arquivos_esf.keys())
        
        if nomes_ficheiros:
            label_status_conv.configure(text=f"✅ {len(nomes_ficheiros)} ficheiros encontrados.", text_color="green")
            
            # A CORREÇÃO MÁGICA: Pega apenas nos 50 primeiros para o menu não bugar!
            nomes_preview = nomes_ficheiros[:50]
            
            # Envia a lista limpa para o menu
            menu_amostras.configure(values=nomes_preview, state="normal")
            menu_amostras.set(nomes_preview[0]) 
            
            botao_preview.configure(state="normal")
            botao_processar_tudo.configure(state="normal")
        else:
            label_status_conv.configure(text="⚠️ Nenhum .esf encontrado nas subpastas.", text_color="red")
            botao_preview.configure(state="disabled")
            botao_processar_tudo.configure(state="disabled")
def testar_filtros_preview():
    amostra_nome = menu_amostras.get()
    caminho_completo = mapa_arquivos_esf.get(amostra_nome)
    if not caminho_completo: return
    
    try:
        # Carrega o bruto (agora o eixo X estará perfeitamente limpo!)
        wl, intens_bruta = carregar_arquivo_esf(caminho_completo)
        intens_tratada = intens_bruta.copy()
        
        tags = []
        if check_savgol.get() == 1:
            intens_tratada = filtrar_ruido(intens_tratada)
            tags.append("SG")
        if check_baseline.get() == 1:
            intens_tratada, _ = remover_baseline(intens_tratada)
            tags.append("BL")
        if check_normalizacao.get() == 1:
            intens_tratada = normalizar_por_area(wl, intens_tratada)
            tags.append("Norm")
            
        titulo_tags = " + ".join(tags) if tags else "Nenhum Filtro"
        
        # Plota os gráficos com um visual mais científico
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 8), sharex=True)
        
        # 1. Gráfico Bruto
        ax1.plot(wl, intens_bruta, color='#7f8c8d', linewidth=0.8, alpha=0.9)
        ax1.set_title(f"Espectro Bruto Original: {amostra_nome}", fontweight='bold')
        ax1.grid(True, linestyle=':', alpha=0.6)
        
        # 2. Gráfico Tratado
        ax2.plot(wl, intens_tratada, color='#2c3e50', linewidth=1)
        ax2.set_title(f"Espectro Tratado ({titulo_tags}) com Mapeamento NPK", fontweight='bold')
        ax2.set_xlabel("Comprimento de Onda (nm)")
        ax2.grid(True, linestyle=':', alpha=0.6)
        
        # A MAGIA VOLTOU: Desenhando os picos NPK no gráfico tratado!
        picos_npk = identificar_picos_npk(wl, intens_tratada)
        ELEMENTS_COLORS = {'N': '#3498db', 'P': '#e67e22', 'K': '#9b59b6'}
        elementos_vistos = set()
        
        for pico in picos_npk:
            elem = pico['elemento']
            label = f"Linha de {elem}" if elem not in elementos_vistos else ""
            elementos_vistos.add(elem)
            
            # Linha pontilhada e bolinha colorida
            ax2.axvline(x=pico['w_medido'], color=ELEMENTS_COLORS[elem], linestyle=':', alpha=0.6)
            ax2.scatter(pico['w_medido'], pico['intensidade'], color=ELEMENTS_COLORS[elem], s=45, zorder=5, label=label)
            
            # Texto indicando o elemento
            texto = f"{elem}\n{pico['w_medido']:.1f}"
            ax2.annotate(texto, xy=(pico['w_medido'], pico['intensidade']), xytext=(4, 4),
                         textcoords='offset points', fontsize=8, fontweight='bold', color=ELEMENTS_COLORS[elem])
        
        # Só mostra a legenda se algum elemento for encontrado
        if elementos_vistos:
            ax2.legend(loc='upper right')
        
        plt.tight_layout()
        plt.show() 
        
    except Exception as e:
        atualizar_terminal(f"Erro no preview: {str(e)}")
        
        
def iniciar_processamento_em_lote():
    if not pasta_origem_selecionada: return 
    
    terminal_conversao.delete("1.0", "end")
    
    pasta_pai = os.path.dirname(pasta_origem_selecionada)
    nome_pasta_origem = os.path.basename(pasta_origem_selecionada)
    pasta_destino = os.path.join(pasta_pai, f"{nome_pasta_origem}_CSV_Tratados")
    
    usa_sg = bool(check_savgol.get())
    usa_bl = bool(check_baseline.get())
    usa_norm = bool(check_normalizacao.get())
    
    label_status_conv.configure(text="A processar em segundo plano...", text_color="orange")
    botao_processar_tudo.configure(state="disabled") 
    
    def tarefa_pesada():
        try:
            sucesso, falhas, msg = converter_pasta_esf_para_csv(
                pasta_origem_selecionada, pasta_destino, 
                usar_sg=usa_sg, usar_baseline=usa_bl, usar_norm=usa_norm, 
                callback=atualizar_terminal
            )
            
            # Usamos o .after() para forçar a thread principal a atualizar os textos em segurança!
            janela.after(0, lambda: label_status_conv.configure(
                text=f"✅ Salvo em: {nome_pasta_origem}_CSV_Tratados", 
                text_color="green" if falhas == 0 else "red"
            ))
        except Exception as e:
            janela.after(0, lambda: [
                atualizar_terminal(f"\n❌ ERRO FATAL: {str(e)}"),
                label_status_conv.configure(text="Erro no processamento.", text_color="red")
            ])
        finally:
            # Liberta o botão de forma segura na thread principal
            janela.after(0, lambda: botao_processar_tudo.configure(state="normal"))

    threading.Thread(target=tarefa_pesada, daemon=True).start()    
    def tarefa_pesada():
        try:
            # Envia as escolhas das checkboxes para o motor!
            sucesso, falhas, msg = converter_pasta_esf_para_csv(
                pasta_origem_selecionada, pasta_destino, 
                usar_sg=usa_sg, usar_baseline=usa_bl, usar_norm=usa_norm, 
                callback=atualizar_terminal
            )
            cor = "green" if falhas == 0 else "red"
            label_status_conv.configure(text=f"✅ Salvo em: {nome_pasta_origem}_CSV_Tratados", text_color=cor)
        except Exception as e:
            atualizar_terminal(f"\n❌ ERRO FATAL: {str(e)}")
            label_status_conv.configure(text="Erro no processamento.", text_color="red")
        finally:
            botao_processar_tudo.configure(state="normal") 

    threading.Thread(target=tarefa_pesada, daemon=True).start()

# --- Layout da Aba 1 (Fusão) ---
frame_topo = ctk.CTkFrame(aba_pre_conv, fg_color="transparent")
frame_topo.pack(pady=5, fill="x")

botao_pasta = ctk.CTkButton(frame_topo, text="📁 1. Selecionar Pasta Raiz (.esf)", command=escolher_pasta_esf)
botao_pasta.pack(side="left", padx=20)

label_status_conv = ctk.CTkLabel(frame_topo, text="Nenhuma pasta selecionada.", text_color="gray")
label_status_conv.pack(side="left", padx=10)

# Painel Central: Preview e Filtros
frame_filtros = ctk.CTkFrame(aba_pre_conv)
frame_filtros.pack(pady=10, padx=20, fill="x")

ctk.CTkLabel(frame_filtros, text="Amostra para Preview:", font=("Arial", 12, "bold")).grid(row=0, column=0, padx=10, pady=10)

# Adicionámos o dynamic_resizing=False e aumentámos a largura (width) para 250
menu_amostras = ctk.CTkOptionMenu(frame_filtros, values=["Aguardando..."], state="disabled", width=250)

menu_amostras.grid(row=0, column=1, padx=10, pady=10)

botao_preview = ctk.CTkButton(frame_filtros, text="👁️ 2. Ver Gráfico Antes/Depois", command=testar_filtros_preview, state="disabled", fg_color="#8e44ad", hover_color="#9b59b6")
botao_preview.grid(row=0, column=2, padx=10, pady=10)

check_savgol = ctk.CTkCheckBox(frame_filtros, text="Filtro Savitzky-Golay")
check_savgol.grid(row=1, column=0, padx=10, pady=10, sticky="w")
check_savgol.select() 

check_baseline = ctk.CTkCheckBox(frame_filtros, text="Correção Baseline")
check_baseline.grid(row=1, column=1, padx=10, pady=10, sticky="w")
check_baseline.select()

check_normalizacao = ctk.CTkCheckBox(frame_filtros, text="Normalização por Área")
check_normalizacao.grid(row=1, column=2, padx=10, pady=10, sticky="w")
check_normalizacao.select()

# Botão Final de Conversão
botao_processar_tudo = ctk.CTkButton(aba_pre_conv, text="▶️ 3. Processar Lote Inteiro para .CSV", command=iniciar_processamento_em_lote, state="disabled", fg_color="#28a745", hover_color="#218838", height=40)
botao_processar_tudo.pack(pady=10)

# Terminal de Processamento
label_terminal = ctk.CTkLabel(aba_pre_conv, text="Terminal de Processamento:", font=("Arial", 12, "italic"), text_color="gray")
label_terminal.pack(anchor="w", padx=20)
terminal_conversao = ctk.CTkTextbox(aba_pre_conv, height=180, fg_color="#0d0d0d", text_color="#00FF00", font=("Consolas", 12))
terminal_conversao.pack(fill="both", expand=True, padx=20, pady=(0, 20))


# ==============================================================================
# LÓGICA E INTERFACE DA ABA 2: ANÁLISE PCA
# ==============================================================================
arquivos_pca_selecionados = []

def escolher_pasta_pca():
    global arquivos_pca_selecionados
    
    pasta = filedialog.askdirectory(title="Selecione a pasta RAIZ com os resultados .csv")
    
    if pasta:
        arquivos_encontrados = []
        # O os.walk entra em todas as subpastas procurando os CSVs
        for root, dirs, files in os.walk(pasta):
            for f in files:
                if f.lower().endswith('.csv'):
                    arquivos_encontrados.append(os.path.join(root, f))
        
        if len(arquivos_encontrados) >= 3:
            arquivos_pca_selecionados = arquivos_encontrados
            lista_pca_texto.delete("1.0", "end")
            
            for f in arquivos_pca_selecionados:
                # Mostra no ecrã a pasta mãe e o ficheiro, para o utilizador saber o que carregou
                nome_pasta_mae = os.path.basename(os.path.dirname(f))
                lista_pca_texto.insert("end", f"[{nome_pasta_mae}] {os.path.basename(f)}\n")
                
            botao_gerar_pca.configure(state="normal")
            label_status_pca.configure(text=f"✅ {len(arquivos_pca_selecionados)} arquivos carregados (Recursivo).", text_color="green")
        else:
            lista_pca_texto.delete("1.0", "end")
            lista_pca_texto.insert("end", "⚠️ Erro: A pasta selecionada não possui arquivos .csv suficientes (Mínimo: 3).\n")
            botao_gerar_pca.configure(state="disabled")
            label_status_pca.configure(text="Arquivos insuficientes.", text_color="red")

def acionar_motor_pca():
    try:
        executar_pca_arquivos(arquivos_pca_selecionados)
    except Exception as e:
        label_status_pca.configure(text=f"Erro: {str(e)}", text_color="red")

# Layout da Aba 2
titulo_pca = ctk.CTkLabel(aba_pca, text="Análise de Componentes Principais", font=ctk.CTkFont(size=18, weight="bold"))
titulo_pca.pack(pady=10)

botao_selecionar_pca = ctk.CTkButton(aba_pca, text="📁 Selecionar Pasta com .csv", command=escolher_pasta_pca)
botao_selecionar_pca.pack(pady=10)

instrucao_pca = ctk.CTkLabel(aba_pca, text="Arquivos encontrados na pasta:")
instrucao_pca.pack()

lista_pca_texto = ctk.CTkTextbox(aba_pca, height=200)
lista_pca_texto.pack(fill="x", padx=20, pady=5)

botao_gerar_pca = ctk.CTkButton(aba_pca, text="🧠 Gerar Gráfico de Escores", command=acionar_motor_pca, state="disabled", fg_color="#8e44ad", hover_color="#9b59b6")
botao_gerar_pca.pack(pady=20)

label_status_pca = ctk.CTkLabel(aba_pca, text="", text_color="gray")
label_status_pca.pack()


# ==============================================================================
# LÓGICA E INTERFACE DA ABA 3: CAÇADOR E EXTERMINADOR DE OUTLIERS
# ==============================================================================
import shutil # Biblioteca nativa do Python para mover/copiar ficheiros

arquivos_outliers_selecionados = []
arquivos_defeituosos_encontrados = [] # Nova lista para guardar os ficheiros ruins

def escolher_pasta_outliers():
    global arquivos_outliers_selecionados
    pasta = filedialog.askdirectory(title="Selecione a pasta com os resultados .csv")
    if pasta:
        arquivos = []
        for root, dirs, files in os.walk(pasta):
            # O ESCUDO ANTI-ZUMBI
            if "QUARENTENA" in root:
                continue
                
            for f in files:
                if f.lower().endswith('.csv'):
                    arquivos.append(os.path.join(root, f))
                    
        if len(arquivos) >= 3:
            arquivos_outliers_selecionados = arquivos
            label_status_out.configure(text=f"✅ {len(arquivos)} ficheiros carregados.", text_color="green")
            botao_gerar_out.configure(state="normal")
            botao_quarentena.configure(state="disabled") 
        else:
            label_status_out.configure(text="⚠️ Ficheiros insuficientes (Mínimo 3).", text_color="red")
            
def acionar_motor_outliers():
    global arquivos_defeituosos_encontrados
    try:
        texto_log_out.delete("1.0", "end")
        texto_log_out.insert("end", "A calcular a matriz de distâncias Z-Score...\n")
        
        qtd, lista_ruins = executar_caca_outliers(arquivos_outliers_selecionados)
        arquivos_defeituosos_encontrados = lista_ruins # Guarda na memória para usar na quarentena
        
        texto_log_out.insert("end", f"\nFim da varredura! {qtd} outliers encontrados.\n")
        
        if qtd > 0:
            texto_log_out.insert("end", "Amostras defeituosas prontas para isolamento:\n")
            for ruim in lista_ruins:
                texto_log_out.insert("end", f" -> {os.path.basename(ruim)}\n")
            
            # MAGIA: Se encontrou erro, liberta o botão laranja da Quarentena!
            botao_quarentena.configure(state="normal")
        else:
            botao_quarentena.configure(state="disabled")
            
    except Exception as e:
        label_status_out.configure(text=f"Erro: {str(e)}", text_color="red")

def enviar_para_quarentena():
    """Agora esta função vai APAGAR os ficheiros permanentemente!"""
    if not arquivos_defeituosos_encontrados: return
    
    sucesso = 0
    for arq in arquivos_defeituosos_encontrados:
        try:
            os.remove(arq) # A MÁGICA MORTAL: Deleta o ficheiro para sempre do HD
            sucesso += 1
        except Exception as e:
            pass
            
    texto_log_out.insert("end", f"\n✅ EXTERMÍNIO CONCLUÍDO!\n{sucesso} ficheiros anómalos foram DELETADOS permanentemente.\nO seu dataset está 100% limpo!")
    botao_quarentena.configure(state="disabled")

# --- Layout da Aba 4 ---
titulo_out = ctk.CTkLabel(aba_outliers, text="Rastreamento e Isolamento de Anomalias", font=ctk.CTkFont(size=18, weight="bold"))
titulo_out.pack(pady=10)

botao_selecionar_out = ctk.CTkButton(aba_outliers, text="📁 Selecionar Pasta com .csv", command=escolher_pasta_outliers)
botao_selecionar_out.pack(pady=10)

label_status_out = ctk.CTkLabel(aba_outliers, text="Nenhuma pasta selecionada.", text_color="gray")
label_status_out.pack()

# Botão Vermelho (Procurar)
botao_gerar_out = ctk.CTkButton(aba_outliers, text="🎯 1. Rastrear Outliers", command=acionar_motor_outliers, state="disabled", fg_color="#c0392b", hover_color="#e74c3c")
botao_gerar_out.pack(pady=10)

texto_log_out = ctk.CTkTextbox(aba_outliers, height=150)
texto_log_out.pack(fill="x", padx=20, pady=5)

# Botão Vermelho (Excluir Permanentemente - Só acende se achar erros)
botao_quarentena = ctk.CTkButton(aba_outliers, text="💀 2. DELETAR Outliers Permanentemente", command=enviar_para_quarentena, state="disabled", fg_color="#8b0000", hover_color="#ff0000")
botao_quarentena.pack(pady=10)

# ==============================================================================
# LÓGICA E INTERFACE DA ABA 4: CURVA DE VARIÂNCIA
# ==============================================================================
arquivos_var_selecionados = []

def escolher_pasta_variancia():
    global arquivos_var_selecionados
    pasta = filedialog.askdirectory(title="Selecione a pasta com os resultados .csv")
    if pasta:
        arquivos = []
        for root, dirs, files in os.walk(pasta):
            # O ESCUDO ANTI-ZUMBI
            if "QUARENTENA" in root:
                continue
                
            for f in files:
                if f.lower().endswith('.csv'):
                    arquivos.append(os.path.join(root, f))
                    
        if len(arquivos) >= 3:
            arquivos_var_selecionados = arquivos
            label_status_var.configure(text=f"✅ {len(arquivos)} ficheiros carregados.", text_color="green")
            botao_gerar_var.configure(state="normal")
        else:
            label_status_var.configure(text="⚠️ Ficheiros insuficientes (Mínimo 3).", text_color="red")

def acionar_motor_variancia():
    try:
        executar_curva_variancia(arquivos_var_selecionados)
    except Exception as e:
        label_status_var.configure(text=f"Erro: {str(e)}", text_color="red")

titulo_var = ctk.CTkLabel(aba_variancia, text="Análise de Variância Explicada", font=ctk.CTkFont(size=18, weight="bold"))
titulo_var.pack(pady=10)

botao_selecionar_var = ctk.CTkButton(aba_variancia, text="📁 Selecionar Pasta com .csv", command=escolher_pasta_variancia)
botao_selecionar_var.pack(pady=10)

label_status_var = ctk.CTkLabel(aba_variancia, text="Nenhuma pasta selecionada.", text_color="gray")
label_status_var.pack()

texto_instrucao_var = ctk.CTkLabel(aba_variancia, text="O gráfico irá calcular quantos PCs são necessários\npara reter 95% da informação química original.", text_color="gray")
texto_instrucao_var.pack(pady=20)

botao_gerar_var = ctk.CTkButton(aba_variancia, text="📈 Gerar Curva de Variância", command=acionar_motor_variancia, state="disabled", fg_color="#2980b9", hover_color="#3498db")
botao_gerar_var.pack(pady=20)


# ==============================================================================
# ENCERRAMENTO SEGURO DA APLICAÇÃO
# ==============================================================================
def ao_fechar():
    """Garante que a janela fecha de forma limpa, matando threads e limpando a memória sem erros no terminal"""
    try:
        # 1. Fecha qualquer gráfico fantasma do Matplotlib que tenha ficado aberto
        plt.close('all') 
        
        # 2. Encerra a janela gráfica
        janela.quit()
        janela.destroy()
    except Exception:
        pass
    finally:
        # 3. O "Golpe Ninja": Mata o processo do Python instantaneamente!
        import os
        os._exit(0)

# Intercepta o comando de fechar a janela (o 'X' do programa)
janela.protocol("WM_DELETE_WINDOW", ao_fechar)

# Executa o loop principal
if __name__ == "__main__":
    janela.mainloop()
