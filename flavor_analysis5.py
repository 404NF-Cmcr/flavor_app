import streamlit as st
import pandas as pd
import networkx as nx
import matplotlib
matplotlib.use('Agg') # 后台绘图模式
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import os

# --- 0. 配置常量与文件路径 ---
DB_FILE = 'flavor_database.csv'  # 本地存档文件名
FONT_FILE = 'SimHei.ttf'  # <--- 新增这一行

# --- 1. 字体配置 (核心修复: 优先使用本地字体文件) ---
def configure_font():
    # 方案 A: 如果当前目录下有 SimHei.ttf (云端部署环境)，直接加载它
    if os.path.exists(FONT_FILE):
        # 将字体注册到 matplotlib 的字体管理器中
        fm.fontManager.addfont(FONT_FILE)
        # 设置全局默认字体为 SimHei
        plt.rcParams['font.sans-serif'] = ['SimHei']
    else:
        # 方案 B: 本地电脑环境 (没有放 ttf 文件时)，尝试查找系统字体
        font_names = ['SimHei', 'Microsoft YaHei', 'PingFang SC', 'Heiti TC', 'STHeiti', 'Arial Unicode MS']
        system_fonts = fm.findSystemFonts()
        found_font = None
        for font_path in system_fonts:
            try:
                font_prop = fm.FontProperties(fname=font_path)
                if any(name in font_prop.get_name() for name in font_names):
                    found_font = font_prop
                    break
            except:
                continue
        if found_font:
            plt.rcParams['font.sans-serif'] = [found_font.get_name()]
        else:
            plt.rcParams['font.sans-serif'] = ['sans-serif'] # 最后的保底
            
    plt.rcParams['axes.unicode_minus'] = False # 解决负号显示问题

configure_font()

# --- 页面设置 ---
st.set_page_config(page_title="风味数据库 Pro Max (自动存档版)", layout="wide")
st.title("🧪 风味数据库分析系统 Pro Max")
st.caption(f"💾 数据将自动保存至本地文件: {DB_FILE}")

# --- 2. 数据库管理 (核心新功能) ---

def save_db():
    """将当前 session_state 的数据保存到本地 CSV"""
    if 'data' in st.session_state and not st.session_state.data.empty:
        try:
            # 使用 utf-8-sig 编码，防止 Excel 打开乱码
            st.session_state.data.to_csv(DB_FILE, index=False, encoding='utf-8-sig')
        except Exception as e:
            st.error(f"保存失败: {e}")

def load_db():
    """初始化：尝试从本地加载数据"""
    if 'data' not in st.session_state:
        if os.path.exists(DB_FILE):
            try:
                df = pd.read_csv(DB_FILE)
                # 确保列都是字符串格式
                df = df.astype(str).replace('nan', '')
                st.session_state.data = df
                #以此方式通知用户
                # st.toast("✅ 已自动加载本地历史数据") 
            except Exception as e:
                st.error(f"加载本地存档失败，已重置为空库: {e}")
                st.session_state.data = pd.DataFrame(columns=['食材', '风味物质及英文名', '风味描述'])
        else:
            st.session_state.data = pd.DataFrame(columns=['食材', '风味物质及英文名', '风味描述'])

# 程序启动时立即尝试加载
load_db()

# --- 3. 业务逻辑函数 ---

def load_data_from_excel(file):
    try:
        df = pd.read_excel(file)
        if df.shape[1] >= 3:
            df = df.iloc[:, :3]
            df.columns = ['食材', '风味物质及英文名', '风味描述']
            df = df.astype(str).replace('nan', '')
            df = df[df['食材'] != '']
            
            # 合并并去重
            st.session_state.data = pd.concat([st.session_state.data, df]).drop_duplicates().reset_index(drop=True)
            save_db() # 立即保存
            st.success(f"✅ 成功导入 {len(df)} 条数据并已存档！")
        else:
            st.error("表格格式错误")
    except Exception as e:
        st.error(f"导入失败: {e}")

def smart_add(ing, comp, desc):
    df = st.session_state.data
    new_rows = []
    ing, comp, desc = ing.strip(), comp.strip(), desc.strip()
    
    if ing and comp and desc:
        new_rows.append({'食材': ing, '风味物质及英文名': comp, '风味描述': desc})
        msg = f"已添加: {ing} - {comp}"
    elif ing and desc and not comp:
        matched_comps = df[df['风味描述'] == desc]['风味物质及英文名'].unique()
        if len(matched_comps) == 0:
            st.warning(f"⚠️ 无法根据描述“{desc}”推断物质，请手动输入。")
            return
        count = 0
        for m in matched_comps:
            related_descs = df[df['风味物质及英文名'] == m]['风味描述'].unique()
            for r in related_descs:
                new_rows.append({'食材': ing, '风味物质及英文名': m, '风味描述': r})
            count += 1
        msg = f"⚡ 智能推断：已关联 {count} 个物质"
    else:
        st.warning("请至少填写 (食材 + 描述)")
        return

    if new_rows:
        new_df = pd.DataFrame(new_rows)
        st.session_state.data = pd.concat([df, new_df]).drop_duplicates().reset_index(drop=True)
        save_db() # 立即保存
        st.success(msg)

def clear_db():
    """清空数据库"""
    st.session_state.data = pd.DataFrame(columns=['食材', '风味物质及英文名', '风味描述'])
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
    st.rerun()

def draw_enhanced_network(selected_ings, selected_comps, secondary_ings):
    """
    绘制增强版网络图 (保留金色节点功能)
    """
    fig, ax = plt.subplots(figsize=(16, 12))
    G = nx.Graph()
    
    df = st.session_state.data
    subset = df[df['风味物质及英文名'].isin(selected_comps)]
    
    # 1. 识别强关联食材 (连接 >=2 个选中物质)
    strong_secondary = []
    normal_secondary = []
    
    for ing in secondary_ings:
        connected_comps = subset[subset['食材'] == ing]['风味物质及英文名'].unique()
        if len(connected_comps) >= 2:
            strong_secondary.append(ing)
        else:
            normal_secondary.append(ing)
            
    # 2. 添加节点
    for i in selected_ings:
        G.add_node(i, color='#ff6b6b', size=3000, label=i) # 红
    for c in selected_comps:
        G.add_node(c, color='#51cf66', size=1800, label=c) # 绿
    for i in strong_secondary:
        if i not in selected_ings:
            G.add_node(i, color='#FFD700', size=2400, label=i) # 金 (Gold)
    for i in normal_secondary:
        if i not in selected_ings:
            G.add_node(i, color='#d0a9f5', size=900, label=i) # 紫

    # 3. 添加连线
    for _, row in subset.iterrows():
        ing = row['食材']
        comp = row['风味物质及英文名']
        if (ing in selected_ings) or (ing in secondary_ings):
            weight = 2.5 if ing in strong_secondary else 1
            G.add_edge(ing, comp, weight=weight)

    # 4. 绘图
    pos = nx.spring_layout(G, k=0.6, seed=42)
    colors = [G.nodes[n].get('color', 'gray') for n in G.nodes]
    sizes = [G.nodes[n].get('size', 100) for n in G.nodes]
    weights = [G[u][v].get('weight', 1) for u,v in G.edges]
    
    nx.draw_networkx_edges(G, pos, edge_color='#cccccc', width=weights, alpha=0.6, ax=ax)
    nx.draw_networkx_nodes(G, pos, node_color=colors, node_size=sizes, alpha=0.95, ax=ax)
    nx.draw_networkx_labels(G, pos, font_family='sans-serif', font_size=10, ax=ax)
    
    ax.set_title(f"风味图谱: 红(输入) | 绿(物质) | 金(高匹配:{len(strong_secondary)}) | 紫(普通关联:{len(normal_secondary)})", fontsize=15)
    ax.axis('off')
    
    st.pyplot(fig)
    plt.close(fig)

# --- 主界面布局 ---
with st.sidebar:
    st.subheader("1. 数据库管理")
    # 显示当前数据量
    row_count = len(st.session_state.data)
    if row_count > 0:
        st.success(f"📚 当前库中已有 {row_count} 条数据")
    else:
        st.warning("📚 当前为空库")
        
    uploaded = st.file_uploader("导入新Excel (追加模式)", type='xlsx')
    if uploaded and st.button("确认导入"): 
        load_data_from_excel(uploaded)
    
    # 清空按钮
    with st.expander("🗑️ 危险操作区"):
        if st.button("清空所有数据"):
            clear_db()
    # --- 新增：云端备份功能 (开始) ---
    st.write("---") #用于视觉分隔
    st.markdown("### ☁️ 云端数据备份")
    st.caption("⚠️ 注意：云端程序休眠后数据会重置，离开前请务必下载备份！")
    
    # 将当前数据转换为CSV格式
    csv_data = st.session_state.data.to_csv(index=False, encoding='utf-8-sig')
    
    st.download_button(
        label="📥 点击下载当前数据库 (.csv)",
        data=csv_data,
        file_name="flavor_database_backup.csv",
        mime="text/csv",
        type="primary"  # 让按钮显示为显眼的颜色
    )
    # --- 新增：云端备份功能 (结束) ---
    st.divider()
    st.subheader("2. 智能录入")
    st.caption("填 食材+描述 自动关联")
    m_ing = st.text_input("食材")
    m_comp = st.text_input("物质")
    m_desc = st.text_input("描述")
    if st.button("添加并保存"): smart_add(m_ing, m_comp, m_desc)

# 仅当空库时显示演示数据按钮
if st.session_state.data.empty:
    st.info(f"👋 欢迎！检测到这是新库。请导入数据，或点击下方按钮生成演示数据。")
    if st.button("生成演示数据"):
        demo = {
            '食材': ['豌豆']*3 + ['辣椒']*3 + ['测试A']*2 + ['测试B']*2,
            '风味物质及英文名': ['Comp1', 'Comp2', 'Comp3', 'Comp2', 'Comp3', 'Comp4', 'Comp2', 'Comp3', 'Comp1', 'Comp4'],
            '风味描述': ['desc']*10
        }
        st.session_state.data = pd.DataFrame(demo)
        save_db() # 保存演示数据
        st.rerun()

# 主功能区
if not st.session_state.data.empty:
    df = st.session_state.data
    tab1, tab2, tab3 = st.tabs(["🔍 搜索", "🕸️ 图谱(Pro Max)", "📋 数据表"])
    
    with tab1:
        term = st.text_input("搜索关键词：")
        if term:
            mask = df.apply(lambda x: x.astype(str).str.contains(term, case=False)).any(axis=1)
            st.dataframe(df[mask], use_container_width=True)
            
    with tab2:
        c1, c2 = st.columns([1, 2.5])
        with c1:
            sel_ings = st.multiselect("第一步：选食材", sorted(df['食材'].unique()))
            final_comps = []
            if sel_ings:
                st.divider()
                ing_sets = [set(df[df['食材']==i]['风味物质及英文名']) for i in sel_ings]
                if len(ing_sets) > 1:
                    shared = set.intersection(*ing_sets)
                else:
                    shared = set()
                
                all_rel = set(df[df['食材'].isin(sel_ings)]['风味物质及英文名'])
                unique = all_rel - shared
                
                if shared:
                    st.success(f"🔥 共用物质 ({len(shared)})")
                    s1 = st.multiselect("勾选共用", sorted(list(shared)), default=sorted(list(shared)))
                else:
                    s1 = []
                
                st.info(f"🧊 其他物质 ({len(unique)})")
                s2 = st.multiselect("勾选特有", sorted(list(unique)))
                final_comps = s1 + s2
                
        with c2:
            if sel_ings and final_comps:
                # 二级关联逻辑
                l2 = df[df['风味物质及英文名'].isin(final_comps)]
                sec_ings = [x for x in l2['食材'].unique() if x not in sel_ings]
                
                if sec_ings:
                    # 统计强关联数量
                    sub = df[df['风味物质及英文名'].isin(final_comps)]
                    strong_count = 0
                    for si in sec_ings:
                        if len(sub[sub['食材']==si]['风味物质及英文名'].unique()) >= 2:
                            strong_count += 1
                    
                    st.markdown(f"**分析结果**：共 {len(sec_ings)} 个关联食材，其中 **{strong_count} 个为高匹配度（金色）**")
                
                draw_enhanced_network(sel_ings, final_comps, sec_ings)
            else:
                st.info("👈 请在左侧选择数据")
                
    with tab3:
        st.dataframe(df, use_container_width=True)