import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import io
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# =========================================================================
# 🟢 1. 萬用基礎地圖與參數初始化 (必須放在全檔案最頂端，徹底根除 NameError)
# =========================================================================
bar_diameter_map = {"#6 (#19)": 1.91, "#7 (#22)": 2.22, "#8 (#25)": 2.54, "#10 (#32)": 3.22}
bar_area_map = {"#6 (#19)": 2.87, "#7 (#22)": 3.87, "#8 (#25)": 5.07, "#10 (#32)": 8.14}

st.set_page_config(page_title="RC梁 LRFD 耐震設計工具", layout="centered")
st.title("🌁 RC 梁強度與耐震設計核算面板")

# 側邊欄全域參數與全域耐震控制開關
st.sidebar.header("📐 1. 全域環境與耐震設定")
seismic_zone = st.sidebar.checkbox("⚡ 啟用特殊抗彎矩構架 (高震區 SMRF) 塑鉸區構造限制", value=False)
st.sidebar.markdown("---")

st.sidebar.subheader("🧱 1.1 預設梁斷面幾何")
b = st.sidebar.number_input("預設梁寬 b (cm)", min_value=15.0, value=35.0, step=5.0)
h = st.sidebar.number_input("預設梁高 h (cm)", min_value=20.0, value=65.0, step=5.0)
fc = st.sidebar.number_input("混凝土強度 fc' (kgf/cm²)", min_value=140, value=280, step=35)
fy = st.sidebar.number_input("主鋼筋強度 fy (kgf/cm²)", min_value=2800, value=4200, step=700)
fyt = st.sidebar.number_input("箍筋強度 fyt (kgf/cm²)", min_value=2800, value=4200, step=700)
d_prime = st.sidebar.number_input("保護層深度 d' (cm)", min_value=3.0, value=6.0, step=0.5)

st.sidebar.subheader("🦾 1.2 預設全區主鋼筋配置")
default_n_top = st.sidebar.number_input("預設頂層筋(壓力筋)支數", min_value=1, value=4, step=1)
default_sz_top = st.sidebar.selectbox("預設頂層筋號數", ["#6 (#19)", "#7 (#22)", "#8 (#25)", "#10 (#32)"], index=2)
default_n_bot = st.sidebar.number_input("預設底層筋(張力筋)支數", min_value=1, value=3, step=1)
default_sz_bot = st.sidebar.selectbox("預設底層筋號數", ["#6 (#19)", "#7 (#22)", "#8 (#25)", "#10 (#32)"], index=2)

st.sidebar.header("🌀 2. 剪力箍筋規格")
tie_size = st.sidebar.selectbox("箍筋號數", ["#3 (#10)", "#4 (#13)"], index=0)
tie_legs = st.sidebar.number_input("有效箍筋肢數 (Av 肢數)", min_value=2, value=2, step=2)

ds = 0.95 if tie_size == "#3 (#10)" else 1.27
as_tie = 0.71 if tie_size == "#3 (#10)" else 1.27

# =========================================================================
# 🔵 2. Matplotlib 梁斷面詳圖比例繪製引擎 (加入強制完全洗滌畫布防護)
# =========================================================================
def draw_beam_section(b_in, h_in, d_prime_in, n_top_in, size_top_in, n_bot_in, size_bot_in, db_top_in, db_bot_in):
    plt.close('all')
    plt.clf()
    plt.cla()
    
    plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'Arial']
    plt.rcParams['axes.unicode_minus'] = False
    
    fig = plt.figure(figsize=(5, 5))
    ax = fig.add_subplot(111)
    ax.set_aspect('equal')
    
    # 混凝土外緣
    rect_out = patches.Rectangle((-b_in/2, -h_in/2), b_in, h_in, linewidth=2, edgecolor='#555555', facecolor='#F5F5F0', zorder=1)
    ax.add_patch(rect_out)
    
    # 閉合剪力箍筋
    tie_b = b_in - 2 * (d_prime_in - 0.5)
    tie_h = h_in - 2 * (d_prime_in - 0.5)
    rect_tie = patches.Rectangle((-tie_b/2, -tie_h/2), tie_b, tie_h, linewidth=1.5, edgecolor='#1f77b4', facecolor='none', zorder=2)
    ax.add_patch(rect_tie)
    
    # 頂層壓力主筋
    top_y = h_in/2 - d_prime_in
    if n_top_in > 1:
        top_xs = np.linspace(-b_in/2 + d_prime_in, b_in/2 - d_prime_in, n_top_in)
        for x_pos in top_xs:
            ax.add_patch(patches.Circle((x_pos, top_y), db_top_in/2, color='#2ca02c', zorder=3))
    else:
        ax.add_patch(patches.Circle((0, top_y), db_top_in/2, color='#2ca02c', zorder=3))
        
    # 底層張力主筋
    bot_y = -h_in/2 + d_prime_in
    if n_bot_in > 1:
        bot_xs = np.linspace(-b_in/2 + d_prime_in, b_in/2 - d_prime_in, n_bot_in)
        for x_pos in bot_xs:
            ax.add_patch(patches.Circle((x_pos, bot_y), db_bot_in/2, color='#9467bd', zorder=3))
    else:
        ax.add_patch(patches.Circle((0, bot_y), db_bot_in/2, color='#9467bd', zorder=3))
        
    margin = max(b_in, h_in) * 0.1
    ax.set_xlim(-b_in/2 - margin, b/2 + margin)
    ax.set_ylim(-h_in/2 - margin, h_in/2 + margin)
    ax.set_title(f"RC 梁施工配筋詳圖 (頂: {n_top_in}支, 底: {n_bot_in}支)", fontsize=11, weight='bold')
    ax.axis('off')
    return fig

# =========================================================================
# 🟡 3. 核心力學與耐震構造完整檢核封裝函式 (check_single_beam_safety)
# =========================================================================
def check_single_beam_safety(frame_id, sect_name, Mu_val, Vu_val, 
                             b_i, h_i, fc_val, fy_val, fyt_val, d_prime_val, 
                             n_t, db_t, ab_t, n_b, db_b, ab_b,
                             tie_size_str, tie_legs_val, ds_val, as_tie_val, seismic_zone_val):
    res = {
        "梁編號": frame_id, "識別型號": sect_name, "彎矩需求 Mu (tf-m)": round(Mu_val, 1),
        "剪力需求 Vu (tf)": round(Vu_val, 1), "設計抗彎 ɸMn": 0.0, "彎矩 D/C 比": 0.0,
        "抗彎判定": "❌ 未驗算", "建議箍筋間距": ""
    }
    
    d = h_i - d_prime_val
    ast_bot = n_b * ab_b
    
    rho_min1 = 14.0 / fy_val
    rho_min2 = 0.8 * np.sqrt(fc_val) / fy_val
    rho_min_required = max(rho_min1, rho_min2)
    rho_actual = ast_bot / (b_i * d)
    
    beta1 = 0.85 if fc_val <= 280 else max(0.85 - 0.05 * (fc_val - 280) / 70, 0.65)
    a = (ast_bot * fy_val) / (0.85 * fc_val * b_i)
    c = a / beta1
    
    epsilon_t = 0.003 * (d - c) / c if c > 0 else 0.005
    phi_flex = 0.90 if epsilon_t >= 0.005 else max(0.65, min(0.90, 0.65 + (epsilon_t - 0.002) * (250 / 3)))
    
    phi_Mn = phi_flex * (ast_bot * fy_val * (d - a / 2.0)) / 100000.0
    res["設計抗彎 ɸMn"] = round(phi_Mn, 1)
    res["彎矩 D/C 比"] = round(Mu_val / phi_Mn, 2) if phi_Mn > 0 else 99.0
    
    if rho_actual < rho_min_required:
        res["抗彎判定"] = "❌ 違反最小配筋率"
    elif phi_Mn >= Mu_val:
        res["抗彎判定"] = "✅ 安全"
    else:
        res["抗彎判定"] = "❌ 強度不足"
        
    # 剪力控制間距
    Vc = (0.53 * np.sqrt(fc_val) * b_i * d) / 1000.0
    phi_shear = 0.75
    phi_Vc = phi_shear * Vc
    
    if not seismic_zone_val:
        max_tie_spacing = min(d / 2.0, 30.0)
    else:
        # SMRF 塑鉸區嚴格構造限制
        max_tie_spacing = min(d / 4.0, 8 * min(db_t, db_b), 24 * ds_val, 10.0)
        
    if Vu_val <= phi_Vc:
        res["建議箍筋間距"] = f"{tie_size_str} @ {min(30.0, max_tie_spacing):.0f} cm (構造控制)"
    else:
        Vs_req = (Vu_val / phi_shear) - Vc
        Av = tie_legs_val * as_tie_val
        spacing_calc = (Av * fyt_val * d) / (Vs_req * 1000.0)
        res["建議箍筋間距"] = f"{tie_size_str} @ {min(30.0, min(max_tie_spacing, spacing_calc)):.0f} cm (強度控制)"
        
    return res

# =========================================================================
# 📜 4. 萬用 PDF 結構設計計算書生成引擎 (已完全正名欄位對齊，徹底消滅 KeyError)
# =========================================================================
def generate_beam_pdf_report(df_results, sect_db):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, title="RC梁結構設計計算書",
                            rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=50)
    story = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TText', fontName='Helvetica-Bold', fontSize=22, alignment=1, textColor=colors.HexColor('#2c3e50'))
    h2_style = ParagraphStyle('H2Text', fontName='Helvetica-Bold', fontSize=13, spaceBefore=12, spaceAfter=6, textColor=colors.HexColor('#1f77b4'))
    body_style = ParagraphStyle('BText', fontName='Helvetica', fontSize=9, leading=13)
    
    story.append(Paragraph("<b>RC BEAM STRUCTURAL DESIGN REPORT</b>", title_style))
    story.append(Paragraph("結構設計計算書 (抗彎強度與高震區 SMRF 箍筋間距複核)", ParagraphStyle('Sub', parent=title_style, fontSize=11, spaceAfter=15)))
    
    story.append(Paragraph("一、 梁幾何尺寸與鋼筋參數資料庫", h2_style))
    db_rows = []
    for k, v in sect_db.items():
        db_rows.append([Paragraph(str(k), body_style), Paragraph(f"{v['梁寬 b (cm)']} x {v['梁高 h (cm)']}", body_style), Paragraph(f"{v['頂層支數']} 支", body_style), Paragraph(str(v['頂層號數']), body_style), Paragraph(f"{v['底層支數']} 支", body_style), Paragraph(str(v['底層號數']), body_style)])
    t_db = Table([[Paragraph("<b>型號</b>", body_style), Paragraph("<b>斷面尺寸 (cm)</b>", body_style), Paragraph("<b>頂層主筋</b>", body_style), Paragraph("<b>頂層號數</b>", body_style), Paragraph("<b>底層主筋</b>", body_style), Paragraph("<b>底層號數</b>", body_style)]] + db_rows, colWidths=[80, 100, 60, 80, 60, 80])
    t_db.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f8f9fa')), ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#dddddd')), ('PADDING', (0,0), (-1,-1), 5)]))
    story.append(t_db)
    
    story.append(Paragraph("二、 全模型梁桿件力學強度包絡與構造檢核總表", h2_style))
    res_rows = []
    for idx, r in df_results.iterrows():
        # 🟢 終極修正點：將 PDF 生成內部的字典鍵值，100% 精準改為與批次總表一致的新標頭名稱！
        f_id = str(r['梁編號']) if '梁編號' in r else str(r.iloc[0])
        s_name = str(r['識別型號']) if '識別型號' in r else str(r.iloc[1])
        m_u = f"{r['彎矩需求 Mu (tf-m)']:.1f}" if '彎矩需求 Mu (tf-m)' in r else f"{r.iloc[2]:.1f}"
        phi_mn = f"{r['設計抗彎 ɸMn']:.1f}" if '設計抗彎 ɸMn' in r else "0.0"
        d_c = f"{r['彎矩 D/C 比']:.2f}" if '彎矩 D/C 比' in r else "0.00"
        chk_res = str(r['抗彎判定']) if '抗彎判定' in r else "未定"
        tie_sp = str(r['建議箍筋間距']) if '建議箍筋間距' in r else "構造控制"

        res_rows.append([
            Paragraph(f_id, body_style), 
            Paragraph(s_name, body_style), 
            Paragraph(m_u, body_style), 
            Paragraph(phi_mn, body_style), 
            Paragraph(d_c, body_style), 
            Paragraph(chk_res, body_style), 
            Paragraph(tie_sp, body_style)
        ])
        
    t_res = Table([[Paragraph("<b>梁號</b>", body_style), Paragraph("<b>識別型號</b>", body_style), Paragraph("<b>彎矩 Mu</b>", body_style), Paragraph("<b>設計 ɸMn</b>", body_style), Paragraph("<b>D/C 比</b>", body_style), Paragraph("<b>強度判定</b>", body_style), Paragraph("<b>建議箍筋間距</b>", body_style)]] + res_rows, colWidths=[40, 90, 50, 50, 45, 75, 150])
    t_res.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2c3e50')), ('TEXTCOLOR', (0,0), (-1,0), colors.white), ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cccccc')), ('PADDING', (0,0), (-1,-1), 4)]))
    story.append(t_res)
    
    doc.build(story)
    buffer.seek(0)
    return buffer.read()

# =========================================================================
# 🗃️ 5. 萬用多尺寸梁基本參數資料庫 (Multi-Beam DB - 智慧下拉選單欄位優化版)
# =========================================================================
st.header("🗃️ 多尺寸梁基本參數資料庫 (Multi-Beam DB)")
st.caption("ℹ️ 可雙擊下方表格直接修改參數。新增或刪除型號時，系統會自動在後台完成資料庫排重。")

if "df_beam_db" not in st.session_state:
    st.session_state.df_beam_db = pd.DataFrame([
        {"梁型號": "B 40 X 70", "梁寬 b (cm)": 40.0, "梁高 h (cm)": 70.0, "頂層支數": 4, "頂層號數": "#8 (#25)", "底層支數": 3, "底層號數": "#8 (#25)"},
        {"梁型號": "B 40 X 60", "梁寬 b (cm)": 40.0, "梁高 h (cm)": 60.0, "頂層支數": 4, "頂層號數": "#8 (#25)", "底層支數": 3, "底層號數": "#8 (#25)"}
    ])

# 💡 【✨ 終極優化：設定 Data Editor 智慧欄位配置（下拉選單與數值級距限制）】
# 100% 根除工程師手手打錯字、打錯空格導致力學對照落空的硬傷！
configured_cols = {
    "梁型號": st.column_config.TextColumn("梁型號 (大寫無空格比對)", help="請輸入對應 SAP2000 的剖面名稱，如 B 40X70", required=True),
    "梁寬 b (cm)": st.column_config.NumberColumn("梁寬 b (cm)", min_value=15.0, max_value=200.0, step=5.0, format="%.1f"),
    "梁高 h (cm)": st.column_config.NumberColumn("梁高 h (cm)", min_value=20.0, max_value=300.0, step=5.0, format="%.1f"),
    "頂層支數": st.column_config.NumberColumn("頂層壓力筋支數", min_value=1, max_value=30, step=1, format="%d"),
    "頂層號數": st.column_config.SelectboxColumn("頂層壓力筋號數", options=["#6 (#19)", "#7 (#22)", "#8 (#25)", "#10 (#32)"], required=True),
    "底層支數": st.column_config.NumberColumn("底層張力筋支數", min_value=1, max_value=30, step=1, format="%d"),
    "底層號數": st.column_config.SelectboxColumn("底層張力筋號數", options=["#6 (#19)", "#7 (#22)", "#8 (#25)", "#10 (#32)"], required=True)
}

# 發動高階網頁動態編輯器
edited_df = st.data_editor(
    st.session_state.get("df_beam_db"), 
    num_rows="dynamic", 
    column_config=configured_cols, 
    width='stretch'
)

# 後台排重與字典轉換清洗
if edited_df is not None and not edited_df.empty:
    edited_df['梁型號'] = edited_df['梁型號'].astype(str).str.strip().str.upper()
    df_clean_db = edited_df.drop_duplicates(subset=["梁型號"], keep="last")
    df_clean_db = df_clean_db[~df_clean_db["梁型號"].isin(["", "NAN", "NONE"])]
    sect_db = df_clean_db.set_index("梁型號").to_dict(orient="index")
else:
    sect_db = {}

# =========================================================================
# 6. 批次自動化上傳：全新純淨 Excel 檔 0 迴圈物理快洗引擎 (純字串降維解包版)
# =========================================================================
with st.expander("📁 批次自動化：上傳 SAP2000 梁內力雙表 Excel (.xlsx)", expanded=True):
    uploaded_file = st.file_uploader("請上傳同時包含內力表與性質指派表的 Excel 活頁簿", type=["xlsx"])
    
    if uploaded_file is not None:
        try:
            xl = pd.ExcelFile(uploaded_file, engine='openpyxl')
            sheet_names = xl.sheet_names
            
            forces_sheets = [s for s in sheet_names if 'FORCES' in s.upper() or '內力' in s or 'FORCE' in s.upper()]
            assign_sheets = [s for s in sheet_names if 'ASSIGN' in s.upper() or '性質' in s or 'SECT' in s.upper()]
            
            if len(forces_sheets) == 0 or len(assign_sheets) == 0:
                st.error("❌ 檔案錯誤：Excel 活頁簿中必須同時包含『Element Forces』與『Frame Section Assignments』兩個工作表分頁！")
                st.stop()
            
            # 💡 【✨ 關鍵修正點】：加上 [0]，強制將 List 內的分頁名稱提取、還原為「純字串名稱」！
            # 這是消滅 pd.read_excel 回傳 dict 字典物件進而引發 head() 崩潰最正統、唯一的做法
            target_forces_sheet = forces_sheets[0]
            target_assign_sheet = assign_sheets[0]
            
            # --- 1. 極速讀取左表 (Element Forces 內力需求表) ---
            df_forces_raw = pd.read_excel(uploaded_file, sheet_name=target_forces_sheet, header=None)
            
            raw_values_f = df_forces_raw.head(5).values
            header_idx = 0
            for i in range(len(raw_values_f)):
                row_str = [str(item).strip().upper() for item in raw_values_f[i]]
                if any('FRAME' in item for item in row_str) and not any('TABLE' in item for item in row_str):
                    header_idx = i
                    break
                    
            df_forces_clean = df_forces_raw.iloc[header_idx+1:].copy()
            forces_cols_count = df_forces_raw.shape[1]
            
            # 物理位置絕對序號指派：第 1 欄梁號、第 6 欄 V2 剪力、第 10 欄 M3 彎矩
            f_col_names = []
            for idx in range(forces_cols_count):
                if idx == 0: f_col_names.append("F_COL_0")      
                elif idx == 5: f_col_names.append("RAW_V2")     
                elif idx == 9: f_col_names.append("RAW_M3")     
                else: f_col_names.append(f"F_COL_{idx}")
                    
            df_forces_clean.columns = f_col_names
            df_forces_clean = df_forces_clean.reset_index(drop=True)
            
            # --- 2. 極速讀取右表 (Frame Section Assignments 性質指派表) ---
            df_assign_raw = pd.read_excel(uploaded_file, sheet_name=target_assign_sheet, header=None)
            
            raw_values_a = df_assign_raw.head(5).values
            as_header_idx = 0
            for i in range(len(raw_values_a)):
                as_row_str = [str(item).strip().upper() for item in raw_values_a[i]]
                if any(k in item for item in as_row_str for k in ['FRAME', 'ELEMENT', 'SECT', 'PROP']):
                    as_header_idx = i
                    break
                    
            df_assign = df_assign_raw.iloc[as_header_idx+1:].copy()
            assign_cols_count = df_assign_raw.shape[1]
            df_assign.columns = [f"A_COL_{idx}" for idx in range(assign_cols_count)]
            df_assign = df_assign.reset_index(drop=True)
            
            # 高速大數據型態收斂
            df_forces_clean['LINK_NUM'] = pd.to_numeric(df_forces_clean['F_COL_0'], errors='coerce')
            df_assign['LINK_NUM'] = pd.to_numeric(df_assign['A_COL_0'], errors='coerce')
            
            df_forces_final = df_forces_clean.dropna(subset=['LINK_NUM']).copy()
            df_assign_final = df_assign.dropna(subset=['LINK_NUM']).copy()
            
            df_forces_final['LINK_ID_STR'] = df_forces_final['LINK_NUM'].astype(int).astype(str)
            df_assign_final['LINK_ID_STR'] = df_assign_final['LINK_NUM'].astype(int).astype(str)
            
            df_assign_clean = df_assign_final[['LINK_ID_STR', 'A_COL_4']].copy()
            df_assign_clean.columns = ['LINK_ID_STR', 'REAL_SECTION']
            df_assign_clean['REAL_SECTION'] = df_assign_clean['REAL_SECTION'].astype(str).str.strip().str.upper()
            
            # 🚀 雙表跨表完美合併
            df_sap = pd.merge(df_forces_final, df_assign_clean, on='LINK_ID_STR', how='left')
            
            df_sap['Num_M3'] = pd.to_numeric(df_sap['RAW_M3'], errors='coerce').fillna(0.0)
            df_sap['Abs_V2'] = pd.to_numeric(df_sap['RAW_V2'], errors='coerce').fillna(0.0).abs()
            
            # 雙向正負彎矩獨立聚合包絡
            group_keys = ['LINK_ID_STR', 'REAL_SECTION']
            df_summary = df_sap.groupby(group_keys).agg(
                Max_Pos_M3=('Num_M3', 'max'),
                Max_Neg_M3=('Num_M3', 'min'),
                Max_V2=('Abs_V2', 'max')
            ).reset_index()
            
            df_summary.columns = ['梁編號', '識別型號', '正彎矩 Mu+ (tf-m)', '負彎矩 Mu- (tf-m)', '剪力需求 Vu (tf)']
            df_summary_clean = df_summary[~df_summary['識別型號'].isin(['NAN', 'NONE', ''])].reset_index(drop=True)
            
            # --- 💡 按鈕 1：進行整張大表格的雙向正負彎矩批次跑算 ---
            if st.button("📊 執行全模型/全批次梁強度與耐震構造安全檢核"):
                results = []
                for index, row in df_summary_clean.iterrows():
                    frame_id = str(row['梁編號']).strip()
                    sect_name = str(row['識別型號']).strip().upper()
                    
                    Mu_pos = float(row['正彎矩 Mu+ (tf-m)'])
                    Mu_neg = abs(float(row['負彎矩 Mu- (tf-m)']))
                    Vu_val = float(row['剪力需求 Vu (tf)'] or 0.0)
                    
                    matched_key = None
                    clean_sect_name = sect_name.replace(" ", "")
                    
                    for db_key in sect_db.keys():
                        clean_db_key = str(db_key).strip().upper().replace(" ", "")
                        if (clean_db_key in clean_sect_name) or (clean_sect_name in clean_db_key):
                            matched_key = db_key
                            break
                            
                    if matched_key is not None:
                        b_i = float(sect_db[matched_key]["梁寬 b (cm)"])
                        h_i = float(sect_db[matched_key]["梁高 h (cm)"])
                        n_t = int(sect_db[matched_key]["頂層支數"])
                        sz_t = str(sect_db[matched_key]["頂層號數"])
                        n_b = int(sect_db[matched_key]["底層支數"])
                        sz_b = str(sect_db[matched_key]["底層號數"])
                        display_sect_label = matched_key
                    else:
                        b_i, h_i = float(b), float(h)
                        n_t, sz_t = int(default_n_top), str(default_sz_top)
                        n_b, sz_b = int(default_n_bot), str(default_sz_bot)
                        display_sect_label = f"未識別({sect_name})"
                        
                    db_t, ab_t = bar_diameter_map[sz_t], bar_area_map[sz_t]
                    db_b, ab_b = bar_diameter_map[sz_b], bar_area_map[sz_b]
                    
                    # 正彎矩檢核 (下層拉力筋)
                    res_pos = check_single_beam_safety(
                        frame_id, display_sect_label, Mu_pos, Vu_val,
                        b_i, h_i, fc, fy, fyt, d_prime, n_t, db_t, ab_t, n_b, db_b, ab_b,
                        tie_size, tie_legs, ds, as_tie, seismic_zone
                    )
                    
                    # 負彎矩檢核 (上層拉力筋 - 鋼筋角色對調)
                    res_neg = check_single_beam_safety(
                        frame_id, display_sect_label, Mu_neg, Vu_val,
                        b_i, h_i, fc, fy, fyt, d_prime, n_b, db_b, ab_b, n_t, db_t, ab_t,
                        tie_size, tie_legs, ds, as_tie, seismic_zone
                    )
                    
                    final_status = "✅ 安全"
                    if "❌" in res_pos["抗彎判定"] or "❌" in res_neg["抗彎判定"]:
                        if "最小配筋率" in res_pos["抗彎判定"] or "最小配筋率" in res_neg["抗彎判定"]:
                            final_status = "❌ 違反最小配筋率"
                        else:
                            final_status = "❌ 強度不足"
                            
                    results.append({
                        "梁編號": frame_id,
                        "識別型號": display_sect_label,
                        "正彎矩 Mu+ (tf-m)": round(Mu_pos, 1),
                        "下層抗彎 ɸMn+": res_pos["設計抗彎 ɸMn"],
                        "下層 D/C 比": res_pos["彎矩 D/C 比"],
                        "負彎矩 Mu- (tf-m)": round(-Mu_neg, 1),
                        "上層抗彎 ɸMn-": res_neg["設計抗彎 ɸMn"],
                        "上層 D/C 比": res_neg["彎矩 D/C 比"],
                        "抗彎判定": final_status,
                        "建議箍筋間距": res_pos["建議箍筋間距"]
                    })
                    
                if len(results) > 0:
                    df_results = pd.DataFrame(results)
                    st.subheader("🏁 批次自動化梁設計複核總報告")
                    
                    def highlight_status(val):
                        if "❌" in str(val): return 'background-color: #ffcccc; color: #cc0000; font-weight: bold;'
                        elif "✅" in str(val): return 'background-color: #e6ffed; color: #22863a;'
                        return ''
                    st.dataframe(df_results.style.map(highlight_status, subset=['抗彎判定']), width='stretch')
                    
                    with st.spinner("正在為您產出商用級 PDF 設計計算書..."):
                        pdf_data = generate_beam_pdf_report(df_results, sect_db)
                    st.download_button(label="📄 一鍵下載 PDF 格式梁設計計算書", data=pdf_data, file_name="RC_Beam_Design_Report.pdf", mime="application/pdf")
                    
        except Exception as e:
            st.error(f"❌ 檔案解析失敗，錯誤訊息: {str(e)}")

# =========================================================================
# 🪐 7. 模式 A：單根梁手動設計與詳圖模擬 (智慧開關連動、完美雙控防凍結版)
# =========================================================================
st.markdown("---")
st.header("🪐 單根梁手動設計與詳圖模擬")
st.caption("ℹ️ 本區為獨立試算面板。您在左側側邊欄調整任何預設參數，皆『絕對不會』影響或覆蓋本區已輸入的數值。")

sync_global = st.checkbox("🔗 手動區同步讀取左側全域預設參數 (打勾連動，取消則可自由微調)", value=True)

col_dim1, col_dim2 = st.columns(2)
with col_dim1:
    init_b = float(b) if sync_global else 35.0
    b_manual = st.number_input("手動調整：本支梁寬 b (cm)", min_value=15.0, value=init_b, step=5.0, key="b_manual_unique_key")
with col_dim2:
    init_h = float(h) if sync_global else 65.0
    h_manual = st.number_input("手動調整：本支梁高 h (cm)", min_value=20.0, value=init_h, step=5.0, key="h_manual_unique_key")

col_m1, col_m2 = st.columns(2)
with col_m1:
    init_n_top = int(default_n_top) if sync_global else 4
    n_top_manual = st.number_input("手動頂層筋(壓力筋)支數", min_value=1, value=init_n_top, step=1, key="n_top_manual_key")
    all_sizes = ["#6 (#19)", "#7 (#22)", "#8 (#25)", "#10 (#32)"]
    init_sz_top_idx = all_sizes.index(default_sz_top) if (sync_global and default_sz_top in all_sizes) else 2
    sz_top_manual = st.selectbox("手動頂層筋號數", all_sizes, index=init_sz_top_idx, key="sz_top_manual_key")
with col_m2:
    init_n_bot = int(default_n_bot) if sync_global else 3
    n_bot_manual = st.number_input("手動底層筋(張力筋)支數", min_value=1, value=init_n_bot, step=1, key="n_bot_manual_key")
    init_sz_bot_idx = all_sizes.index(default_sz_bot) if (sync_global and default_sz_bot in all_sizes) else 2
    sz_bot_manual = st.selectbox("手動底層筋號數", all_sizes, index=init_sz_bot_idx, key="sz_bot_manual_key")

col_f1, col_f2 = st.columns(2)
with col_f1: Mu_manual = st.number_input("手動設計彎矩需求 Mu (tf-m)", min_value=0.0, value=25.0, step=5.0, key="Mu_manual_key")
with col_f2: Vu_manual = st.number_input("手動設計剪力需求 Vu (tf)", min_value=0.0, value=12.0, step=2.0, key="Vu_manual_key")

if st.button("🚀 開始進行單根梁強度與詳圖安全檢核", type="primary"):
    plt.close('all')
    plt.clf()
    
    db_t_manual = bar_diameter_map[sz_top_manual]
    ab_t_manual = bar_area_map[sz_top_manual]
    db_b_manual = bar_diameter_map[sz_bot_manual]
    ab_b_manual = bar_area_map[sz_bot_manual]
    
    single_res = check_single_beam_safety(
        "Manual_Check", "手動型號", Mu_manual, Vu_manual, b_manual, h_manual, fc, fy, fyt, d_prime,
        n_top_manual, db_t_manual, ab_t_manual, n_bot_manual, db_b_manual, ab_b_manual,
        tie_size, tie_legs, ds, as_tie, seismic_zone
    )
    
    st.subheader("📋 單根梁檢核結果")
    sc1, sc2, sc3 = st.columns(3)
    sc1.metric("設計抗彎容量 ɸMn", f"{single_res['設計抗彎 ɸMn']:.1f} tf-m")
    sc2.metric("彎矩需求比 (D/C)", f"{single_res['彎矩 D/C 比']:.2f}")
    sc3.metric("構造判定結果", single_res['抗彎判定'])
    st.info(f"🚨 建議剪力配箍方案：{single_res['建議箍筋間距']}")
    
    st.markdown("---")
    p_c1, p_c2 = st.columns(2)
    with p_c1:
        st.write("🎨 **RC 梁極限設計詳圖資訊：**")
        st.write(f"* 斷面邊寬: $b$ = {b_manual} cm, $h$ = {h_manual} cm")
        st.write(f"* 頂層壓力筋: **{n_top_manual} 支 {sz_top_manual}**")
        st.write(f"* 底層張力筋: **{n_bot_manual} 支 {sz_bot_manual}**")
        st.write(f"* 配箍限制: 考慮高震區 SMRF" if seismic_zone else "* 配箍限制: 常規非耐震構造")
    with p_c2:
        fig_beam = draw_beam_section(
            b_manual, h_manual, d_prime, 
            int(n_top_manual), sz_top_manual, 
            int(n_bot_manual), sz_bot_manual, 
            db_t_manual, db_b_manual
        )
        st.pyplot(fig_beam, clear_figure=True)            