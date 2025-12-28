import streamlit as st
import pandas as pd
import networkx as nx
import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import os
import plotly.graph_objects as go
import plotly.express as px
import streamlit.components.v1 as components
from pyvis.network import Network
import numpy as np

# --- 0. 配置常量 ---
DB_FILE = 'flavor_database.csv'
FONT_FILE = 'simhei.ttf'

# --- 1. 字体配置 (保留用于Matplotlib备用) ---
def configure_font():
    if os.path.exists(FONT_FILE):
        fm.fontManager.addfont(FONT_FILE)
        plt.rcParams['font.sans-serif'] = ['SimHei']
    else:
        # Linux/Cloud 环境下备用
        plt.rcParams['font.sans-serif'] = ['sans-serif']
    plt.rcParams['axes.unicode_minus'] = False

configure_font()

# --- 页面设置 ---
st.set_page_config(page_title="风味数据库 测试2", layout="wide")
st.title("🧪 风味数据库分析系统 测试2")
st.caption(f"💾 数据自动存档: {DB_FILE}")

# --- 2. 数据库管理 ---
def save_db():
    if 'data' in st.session_state and not st.session_state.data.empty:
        try:
            st.session_state.data.to_csv(DB_FILE, index=False, encoding='utf-8-sig')
        except: pass

def load_db():
    if 'data' not in st.session_state:
        if os.path.exists(DB_FILE):
            try:
                df = pd.read_csv(DB_FILE)
                st.session_state.data = df.astype(str).replace('nan', '')
            except:
                st.session_state.data = pd.DataFrame(columns=['食材', '风味物质及英文名', '风味描述'])
        else:
            st.session_state.data = pd.DataFrame(columns=['食材', '风味物质及英文名', '风味描述'])

load_db()

# --- 3. 业务逻辑 ---
def load_data_from_excel(file):
    try:
        df = pd.read_excel(file)
        if df.shape[1] >= 3:
            df = df.iloc[:, :3]
            df.columns = ['食材', '风味物质及英文名', '风味描述']
            df = df.astype(str).replace('nan', '')
            df = df[df['食材'] != '']
            st.session_state.data = pd.concat([st.session_state.data, df]).drop_duplicates().reset_index(drop=True)
            save_db()
            st.success(f"✅ 导入成功！")
        else: st.error("格式错误")
    except Exception as e: st.error(f"导入失败: {e}")

def smart_add(ing, comp, desc):
    df = st.session_state.data
    new_rows = []
    if ing and comp and desc:
        new_rows.append({'食材': ing, '风味物质及英文名': comp, '风味描述': desc})
    elif ing and desc and not comp:
        matched = df[df['风味描述'] == desc]['风味物质及英文名'].unique()
        if len(matched) == 0:
            st.warning("无法推断物质")
            return
        for m in matched:
            rels = df[df['风味物质及英文名'] == m]['风味描述'].unique()
            for r in rels: new_rows.append({'食材': ing, '风味物质及英文名': m, '风味描述': r})
    else: return

    if new_rows:
        st.session_state.data = pd.concat([df, pd.DataFrame(new_rows)]).drop_duplicates().reset_index(drop=True)
        save_db()
        st.success("已添加")

def clear_db():
    st.session_state.data = pd.DataFrame(columns=['食材', '风味物质及英文名', '风味描述'])
    if os.path.exists(DB_FILE): os.remove(DB_FILE)
    st.rerun()

# --- 4. 核心：四种可视化引擎 ---

def get_graph_data(selected_ings, selected_comps, secondary_ings):
    """辅助函数：统一生成 NetworkX 图对象和分类信息"""
    G = nx.Graph()
    df = st.session_state.data
    subset = df[df['风味物质及英文名'].isin(selected_comps)]
    
    # 识别强关联
    strong_sec = []
    normal_sec = []
    for ing in secondary_ings:
        if len(subset[subset['食材'] == ing]['风味物质及英文名'].unique()) >= 2:
            strong_sec.append(ing)
        else:
            normal_sec.append(ing)
            
    # 颜色映射
    color_map = {
        'input': '#ff6b6b',    # 红
        'comp': '#51cf66',     # 绿
        'gold': '#FFD700',     # 金
        'normal': '#d0a9f5'    # 紫
    }
    
    # 添加节点
    for i in selected_ings: G.add_node(i, group='input', color=color_map['input'], size=25, title=f"输入: {i}")
    for c in selected_comps: G.add_node(c, group='comp', color=color_map['comp'], size=15, title=f"物质: {c}")
    for i in strong_sec: 
        if i not in selected_ings: G.add_node(i, group='gold', color=color_map['gold'], size=20, title=f"高匹配: {i}")
    for i in normal_sec:
        if i not in selected_ings: G.add_node(i, group='normal', color=color_map['normal'], size=10, title=f"关联: {i}")

    # 添加边
    for _, row in subset.iterrows():
        ing = row['食材']
        comp = row['风味物质及英文名']
        if (ing in selected_ings) or (ing in secondary_ings):
            weight = 3 if ing in strong_sec else 1
            G.add_edge(ing, comp, weight=weight)
            
    return G, color_map

# 1. 动态网络图 (PyVis)
def viz_interactive_network(G):
    try:
        net = Network(height="600px", width="100%", bgcolor="#ffffff", font_color="black")
        net.from_nx(G)
        # 物理引擎设置：排斥力，避免重叠
        net.repulsion(node_distance=150, spring_length=200)
        
        # 临时保存为 HTML 并读取
        path = 'temp_network.html'
        net.save_graph(path)
        with open(path, 'r', encoding='utf-8') as f:
            source_code = f.read()
        components.html(source_code, height=600)
        if os.path.exists(path): os.remove(path)
    except Exception as e:
        st.error(f"生成动态图失败: {e}")

# 2. 桑基图 (Plotly Sankey)
def viz_sankey(G, color_map):
    # Sankey 需要 mapping：名字 -> 索引 ID
    nodes = list(G.nodes())
    node_map = {name: i for i, name in enumerate(nodes)}
    
    sources = []
    targets = []
    values = []
    node_colors = []
    
    # 生成节点颜色列表
    for node in nodes:
        group = G.nodes[node]['group']
        node_colors.append(color_map[group])
        
    # 生成连线数据
    # 逻辑流向：输入食材(左) -> 物质(中) -> 关联食材(右)
    # 但由于 G 是无向图，我们需要手动定向
    for u, v in G.edges():
        # 判断 u 和 v 谁是物质
        is_u_comp = G.nodes[u]['group'] == 'comp'
        is_v_comp = G.nodes[v]['group'] == 'comp'
        
        if is_u_comp and not is_v_comp: # u是物质，v是食材
            comp, ing = u, v
        elif not is_u_comp and is_v_comp: # v是物质，u是食材
            comp, ing = v, u
        else:
            continue
            
        # 区分：是输入食材还是关联食材？
        if G.nodes[ing]['group'] == 'input':
            # 输入 -> 物质
            sources.append(node_map[ing])
            targets.append(node_map[comp])
        else:
            # 物质 -> 关联
            sources.append(node_map[comp])
            targets.append(node_map[ing])
        values.append(1) # 权重

    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15, thickness=20, line=dict(color="black", width=0.5),
            label=nodes, color=node_colors
        ),
        link=dict(source=sources, target=targets, value=values, color='#E0E0E0')
    )])
    fig.update_layout(title_text="风味流向图 (桑基图)", font_size=12, height=600)
    st.plotly_chart(fig, use_container_width=True)

# 3. 热力矩阵图 (Plotly Heatmap)
def viz_heatmap(G):
    # 提取轴数据
    comps = [n for n in G.nodes() if G.nodes[n]['group'] == 'comp']
    ings = [n for n in G.nodes() if G.nodes[n]['group'] != 'comp']
    
    # 排序：让输入食材排在最上面
    ings.sort(key=lambda x: 0 if G.nodes[x]['group'] == 'input' else (1 if G.nodes[x]['group'] == 'gold' else 2))
    
    # 构建矩阵
    z = []
    for ing in ings:
        row = []
        for comp in comps:
            row.append(1 if G.has_edge(ing, comp) else 0)
        z.append(row)
        
    fig = px.imshow(z, x=comps, y=ings, color_continuous_scale='Greens', aspect="auto")
    fig.update_layout(title="风味分布矩阵 (深色表示含有)", height=max(500, len(ings)*15))
    st.plotly_chart(fig, use_container_width=True)

# 4. 弦图/圆形图 (Plotly Circular)
def viz_chord_circle(G, color_map):
    # 使用 NetworkX 的圆形布局计算坐标
    pos = nx.circular_layout(G)
    
    edge_x = []
    edge_y = []
    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=0.5, color='#888'),
        hoverinfo='none', mode='lines')

    node_x = []
    node_y = []
    node_text = []
    node_marker_colors = []
    node_sizes = []
    
    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        node_text.append(node)
        node_marker_colors.append(color_map[G.nodes[node]['group']])
        node_sizes.append(G.nodes[node]['size'] * 1.5) # 稍微放大一点

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        hoverinfo='text',
        text=node_text,
        textposition="top center",
        marker=dict(color=node_marker_colors, size=node_sizes, line_width=1))

    fig = go.Figure(data=[edge_trace, node_trace],
             layout=go.Layout(
                title='风味关联环 (仿弦图)',
                showlegend=False,
                hovermode='closest',
                margin=dict(b=20,l=5,r=5,t=40),
                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                height=700
             ))
    st.plotly_chart(fig, use_container_width=True)


# --- Sidebar ---
with st.sidebar:
    st.subheader("1. 数据库管理")
    if len(st.session_state.data) > 0: st.success(f"📚 数据量: {len(st.session_state.data)}")
    else: st.warning("📚 空库")
    up = st.file_uploader("导入Excel", type='xlsx')
    if up and st.button("确认导入"): load_data_from_excel(up)
    
    with st.expander("🗑️ 清空库"):
        if st.button("确认清空"): clear_db()
        
    st.write("---")
    st.markdown("### ☁️ 云端备份")
    csv_d = st.session_state.data.to_csv(index=False, encoding='utf-8-sig')
    st.download_button("📥 下载备份", csv_d, "backup.csv", "text/csv", type="primary")
    
    st.divider()
    st.subheader("2. 智能录入")
    m_i = st.text_input("食材")
    m_c = st.text_input("物质")
    m_d = st.text_input("描述")
    if st.button("添加"): smart_add(m_i, m_c, m_d)

if st.session_state.data.empty:
    st.info("👋 请导入数据")
    if st.button("生成演示数据"):
        demo = {
            '食材': ['豌豆']*3 + ['辣椒']*3 + ['测试A']*2 + ['测试B']*2 + ['测试C']*3,
            '风味物质及英文名': ['Comp1', 'Comp2', 'Comp3', 'Comp2', 'Comp3', 'Comp4', 'Comp2', 'Comp3', 'Comp1', 'Comp4', 'Comp2', 'Comp5', 'Comp6'],
            '风味描述': ['杏仁味', '果香', '油脂味', '生青味', '油脂味', '辛辣', '果香', '油脂味', '杏仁味', '辛辣', '生青味', '特殊味', '坚果味']
        }
        st.session_state.data = pd.DataFrame(demo)
        save_db()
        st.rerun()

# --- Main Logic ---
if not st.session_state.data.empty:
    df = st.session_state.data
    tab1, tab2, tab3 = st.tabs(["🔍 精准搜索", "🕸️ 高级分析 (Pro)", "📋 数据表"])
    
    with tab1:
        st.subheader("多维数据检索")
        c1, c2, c3 = st.columns(3)
        with c1: search_ing = st.text_input("按 [食材] 搜索", placeholder="如: 豌豆")
        with c2: search_comp = st.text_input("按 [风味物质] 搜索", placeholder="如: 2-庚烯醛")
        with c3: search_desc = st.text_input("按 [风味描述] 搜索", placeholder="如: 生青味")
        
        st.divider()
        
        # 1. 搜食材 (还原 V6 逻辑)
        if search_ing:
            st.markdown(f"#### 🥬 食材“{search_ing}”的关联分析：")
            res = df[df['食材'].str.contains(search_ing, case=False)]
            if not res.empty:
                # 聚合：按食材和物质分组，合并描述
                grouped = res.groupby(['食材', '风味物质及英文名'])['风味描述'].apply(lambda x: '、'.join(x.unique())).reset_index()
                for _, row in grouped.iterrows():
                    st.write(f"🔹 **{row['食材']}** — `{row['风味物质及英文名']}` — （{row['风味描述']}）")
            else:
                st.caption("未找到相关食材")
            st.write("---")

        # 2. 搜物质 (还原 V6 逻辑)
        if search_comp:
            st.markdown(f"#### 🧪 物质“{search_comp}”的分布情况：")
            res = df[df['风味物质及英文名'].str.contains(search_comp, case=False)]
            if not res.empty:
                # 以物质为核心聚合
                target_comps = res['风味物质及英文名'].unique()
                for comp in target_comps:
                    sub = df[df['风味物质及英文名'] == comp]
                    ings = '、'.join(sub['食材'].unique())
                    descs = '、'.join(sub['风味描述'].unique())
                    st.write(f"🔸 （包含食材：{ings}）— **`{comp}`** — （{descs}）")
            else:
                st.caption("未找到相关物质")
            st.write("---")

        # 3. 搜描述 (还原 V6 逻辑 - 包含高亮)
        if search_desc:
            st.markdown(f"#### 👃 描述“{search_desc}”的反向检索：")
            res = df[df['风味描述'].str.contains(search_desc, case=False)]
            if not res.empty:
                # 找到符合描述的物质
                target_comps = res['风味物质及英文名'].unique()
                for comp in target_comps:
                    # 获取该物质的完整信息
                    sub = df[df['风味物质及英文名'] == comp]
                    ings = '、'.join(sub['食材'].unique())
                    
                    # --- 核心修复：处理描述高亮 ---
                    all_descs_list = sub['风味描述'].unique()
                    highlighted_descs = []
                    for d in all_descs_list:
                        if search_desc in d:
                            # Markdown 高亮
                            highlighted_descs.append(f"**{d}**")
                        else:
                            highlighted_descs.append(d)
                    descs_str = '、'.join(highlighted_descs)
                    
                    st.write(f"✨ （包含食材：{ings}）— 含 **{search_desc}** 的物质 `{comp}` — （{descs_str}）")
            else:
                st.caption("未找到相关描述")

    with tab2:
        c_left, c_right = st.columns([1, 3])
        with c_left:
            st.markdown("### 1. 选食材")
            all_ings = sorted(df['食材'].unique())
            sel_ings = st.multiselect("食材 (1-5个)", options=all_ings)
            
            final_comps = []
            if sel_ings:
                subset = df[df['食材'].isin(sel_ings)]
                st.markdown("### 2. 选特征 (可选)")
                descs = sorted(subset['风味描述'].unique())
                f_descs = st.multiselect("特征筛选", options=descs)
                if f_descs:
                    v = subset[subset['风味描述'].isin(f_descs)]['风味物质及英文名'].unique()
                    subset = subset[subset['风味物质及英文名'].isin(v)]
                
                st.markdown("### 3. 选物质")
                # 逻辑分类
                owners = {}
                for _, row in subset.iterrows():
                    c, i = row['风味物质及英文名'], row['食材']
                    if c not in owners: owners[c] = set()
                    owners[c].add(i)
                
                shared_all, shared_some, unique_map = [], [], {i:[] for i in sel_ings}
                for c, oss in owners.items():
                    if len(oss) == len(sel_ings) and len(sel_ings)>1: shared_all.append(c)
                    elif len(oss) >= 2: shared_some.append(c)
                    elif len(oss) == 1: unique_map[list(oss)[0]].append(c)
                
                if shared_all: final_comps.extend(st.multiselect("🔥 全共用", sorted(shared_all), default=sorted(shared_all)))
                if shared_some: final_comps.extend(st.multiselect("🔗 部分共用", sorted(shared_some), default=sorted(shared_some)))
                st.caption("🧊 特有物质")
                for i, cs in unique_map.items():
                    if cs: final_comps.extend(st.multiselect(f"{i} 特有", sorted(cs)))
                    
        with c_right:
            if sel_ings and final_comps:
                # 寻找二级关联
                l2 = df[df['风味物质及英文名'].isin(final_comps)]
                sec_ings = [x for x in l2['食材'].unique() if x not in sel_ings]
                
                # 构造图数据
                G, color_map = get_graph_data(sel_ings, final_comps, sec_ings)
                
                # --- 新增：可视化类型选择 ---
                st.markdown("### 4. 分析视图 (NEW)")
                viz_type = st.radio(
                    "选择一种观察视角：",
                    ["🕸️ 交互式动态网络 (物理模拟)", "🌊 桑基流向图 (逻辑清晰)", "📊 热力矩阵图 (分布密度)", "⭕ 弦状环形图 (整体关联)"],
                    horizontal=True
                )
                
                st.divider()
                
                if "交互" in viz_type:
                    viz_interactive_network(G)
                elif "桑基" in viz_type:
                    viz_sankey(G, color_map)
                elif "热力" in viz_type:
                    viz_heatmap(G)
                elif "弦状" in viz_type:
                    viz_chord_circle(G, color_map)
                    
            elif not sel_ings:
                st.info("👈 请从左侧开始")

    with tab3:
        st.dataframe(df, use_container_width=True)