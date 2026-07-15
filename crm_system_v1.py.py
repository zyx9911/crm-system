import streamlit as st
import sqlite3
import pandas as pd
import datetime
import os
import random
import string
import io
import time
import hashlib
import re
from collections import defaultdict

try:
    import plotly.express as px
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    USE_PLOTLY = True
except ImportError:
    USE_PLOTLY = False

st.set_page_config(page_title='AI潜客线索CRM系统', layout='wide')

st.markdown('''
<style>
.block-container {padding:1rem 2rem;}
h1 {color:#003366; font-weight:bold;}
h2 {color:#225599; margin-top:16px;}
.stMetric {background:#f0f7ff; border-radius:8px; padding:12px; text-align:center;}
.auto-card {background:#f6ffed; border:1px solid #b7eb8f; border-radius:8px; padding:16px; margin-bottom:16px;}
.filter-bar {background:#fafafa; border:1px solid #e8e8e8; border-radius:8px; padding:16px; margin-bottom:16px;}
.call-timer-box {text-align:center; margin:20px 0;}
.call-timer {font-size:36px; font-weight:bold; color:#003366; letter-spacing:2px;}
.call-status {color:#52c41a; font-size:14px; margin-top:8px;}
.dashboard-card {
    background: #fff; border: 1px solid #e8e8e8; border-left: 4px solid #c41c23;
    border-radius: 4px; padding: 16px; color: #333; text-align: left;
    margin-bottom: 12px;
}
.dashboard-card .metric-value {font-size: 28px; font-weight: bold; color: #c41c23; margin: 4px 0;}
.dashboard-card .metric-label {font-size: 13px; color: #999;}
.dashboard-card .metric-change {font-size: 12px; margin-top: 4px; color: #666;}
.health-good {border-left-color: #52c41a !important;}
.health-good .metric-value {color: #52c41a !important;}
.health-warning {border-left-color: #faad14 !important;}
.health-warning .metric-value {color: #faad14 !important;}
.health-danger {border-left-color: #ff4d4f !important;}
.health-danger .metric-value {color: #ff4d4f !important;}
.health-info {border-left-color: #1890ff !important;}
.health-info .metric-value {color: #1890ff !important;}
.health-purple {border-left-color: #722ed1 !important;}
.health-purple .metric-value {color: #722ed1 !important;}
.health-cyan {border-left-color: #13c2c2 !important;}
.health-cyan .metric-value {color: #13c2c2 !important;}
.dashboard-section {
    background: #fff; border-radius: 4px; padding: 20px;
    margin-bottom: 16px; border: 1px solid #f0f0f0;
}
.dashboard-title {
    font-size: 16px; font-weight: bold; color: #333;
    margin-bottom: 16px; padding-left: 12px;
    border-left: 4px solid #c41c23;
}
</style>
''', unsafe_allow_html=True)

# ========================== 常量配置 ==========================
STATUS_MAP = {
    'untouch': '待跟进', 'contacted': '已建联', 'reserve_test': '预约试驾',
    'bargain': '议价中', 'deal': '已成交', 'lost': '已流失'
}
SORT_OPTIONS = ['按AI评分降序', '按留资时间降序', '按序号升序', '按线索等级排序']
FUNNEL_STAGES = ['untouch', 'contacted', 'reserve_test', 'bargain', 'deal', 'lost']
FUNNEL_NAMES = ['待跟进', '已建联', '预约试驾', '议价中', '已成交', '已流失']

NAME_POOL = ['王先生','李女士','张先生','陈女士','刘先生','杨女士','黄先生','周女士','吴先生','赵女士','郑先生','孙女士','马先生','朱女士','胡先生','林女士','郭先生','何女士','高先生','罗女士']
CITY_POOL = ['重庆','成都','万州','涪陵','宜宾','绵阳','德阳','泸州','南充','自贡']
PHONE_PREFIX = ['138','139','137','136','135','150','151','152','158','159','188','189']
CONSULT_TEMPLATES = ['想了解{model}有没有现车，近期想试驾','咨询{model}的配置和油耗，日常通勤用','{model}有置换补贴吗？打算近期订车','问下{model}的落地价，预算{budget}左右','对比了几款车，想了解{model}的售后保养政策','摩旅用，想问问{model}动力和续航怎么样','新手代步，预算{budget}，推荐一下车型','随便看看，先了解下{model}的价格','等新款好久了，{model}什么时候上市？','有现车的话周末就过来订，{model}有优惠吗','旧车想置换，问下{model}的置换政策','上下班代步，{model}油耗高不高？']
BUDGET_POOL = ['1万出头','1.5万左右','2万以内','2-3万','3万以上','预算不多']
MODEL_POOL = ['RT150S','AQS250','RX500']

AI_SPEECH_SCENES = {
    "开场白": [
        "您好，我是赛科龙智能购车助手，看到您关注了我们{model}车型，想跟您确认几个购车需求，方便为您推荐最合适的方案。",
        "您好，感谢您关注赛科龙{model}！我是您的专属AI购车顾问，现在通话方便吗？"
    ],
    "确认预算": [
        "请问您的购车预算大概在什么范围呢？这样我可以帮您看看有没有合适的金融方案。",
        "您之前填写的预算是{budget}，请问这个预算包含上牌和保险吗？"
    ],
    "确认车型": [
        "您关注的{model}目前门店有现车，本周预约试驾可以赠送骑行礼包，您看周六还是周日方便？",
        "除了{model}，您还在对比其他车型吗？我可以帮您做个详细对比。"
    ],
    "异议处理": [
        "您提到价格有点超预算，我们目前支持12期免息分期，首付只要30%，月供压力很小，需要我帮您算一下吗？",
        "您担心油耗问题？{model}实测百公里油耗2.8L，日常通勤一个月油费大概100块左右，非常省油。"
    ],
    "促成成交": [
        "如果您今天确定下单，我可以帮您申请置换补贴+赠送首保，这个优惠本周截止。",
        "门店现在刚好有一台{model}现车，颜色齐全，您看明天下午方便过来提车吗？"
    ],
    "结束语": [
        "好的，我已经把您的需求记录下来了，稍后会把详细方案和报价发到您微信，注意查收。",
        "感谢您的接听，祝您生活愉快，期待您到店试驾！"
    ]
}

# ========================== 数据库层 ==========================
def get_conn():
    return sqlite3.connect('crm_demo.db')

@st.cache_resource
def init_db_once():
    db_path = 'crm_demo.db'
    first_run = not os.path.exists(db_path)
    conn = get_conn()
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS shop (id INTEGER PRIMARY KEY AUTOINCREMENT, shop_name TEXT NOT NULL, province TEXT, city TEXT, contact TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS sys_user (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL, real_name TEXT, role TEXT, shop_id INTEGER)')
    c.execute('CREATE TABLE IF NOT EXISTS channel_dict (id INTEGER PRIMARY KEY AUTOINCREMENT, channel_name TEXT NOT NULL, weight INTEGER)')
    c.execute('CREATE TABLE IF NOT EXISTS motorcycle_model (id INTEGER PRIMARY KEY AUTOINCREMENT, model_name TEXT NOT NULL, price_min REAL)')
    c.execute('CREATE TABLE IF NOT EXISTS score_rule (id INTEGER PRIMARY KEY AUTOINCREMENT, full_info_score INTEGER, time_score INTEGER, high_intent_score INTEGER, mid_intent_score INTEGER, low_intent_score INTEGER, behavior_freq_score INTEGER, demand_clear_score INTEGER)')
    c.execute('CREATE TABLE IF NOT EXISTS level_config (id INTEGER PRIMARY KEY AUTOINCREMENT, a_min INTEGER, b_min INTEGER, c_min INTEGER, high_value_min INTEGER)')
    c.execute('CREATE TABLE IF NOT EXISTS intent_keyword (id INTEGER PRIMARY KEY AUTOINCREMENT, keyword TEXT, type TEXT, score_change INTEGER)')
    c.execute("CREATE TABLE IF NOT EXISTS customer_leads (id INTEGER PRIMARY KEY AUTOINCREMENT, phone TEXT UNIQUE, customer_name TEXT, city TEXT, budget TEXT, model_id INTEGER, channel_id INTEGER, consult_content TEXT, source_time TEXT, latest_source_time TEXT, repeat_label TEXT DEFAULT '', behavior_count INTEGER DEFAULT 1, total_score INTEGER, lead_level TEXT, is_high_value INTEGER DEFAULT 0, user_tags TEXT DEFAULT '', assign_shop_id INTEGER, assign_sale_id INTEGER, assign_time TEXT, first_contact_time TEXT, lead_status TEXT DEFAULT 'untouch', lost_reason TEXT)")
    c.execute('CREATE TABLE IF NOT EXISTS lead_follow_record (id INTEGER PRIMARY KEY AUTOINCREMENT, lead_id INTEGER, sale_id INTEGER, follow_type TEXT, follow_content TEXT, ai_summary TEXT, create_time TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS call_record (id INTEGER PRIMARY KEY AUTOINCREMENT, lead_id INTEGER, shop_id INTEGER, call_duration INTEGER, call_content TEXT, ai_analysis TEXT, score_after_call INTEGER, level_after_call TEXT, create_time TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS ai_speech_lib (id INTEGER PRIMARY KEY AUTOINCREMENT, scene TEXT, speech_content TEXT)')
    c.execute("CREATE TABLE IF NOT EXISTS daily_stats (date TEXT PRIMARY KEY, total_leads INTEGER DEFAULT 0, new_leads INTEGER DEFAULT 0, high_value_leads INTEGER DEFAULT 0, contacted_leads INTEGER DEFAULT 0, reserve_test_leads INTEGER DEFAULT 0, bargain_leads INTEGER DEFAULT 0, deal_leads INTEGER DEFAULT 0, lost_leads INTEGER DEFAULT 0, call_count INTEGER DEFAULT 0, total_call_duration INTEGER DEFAULT 0, avg_score REAL DEFAULT 0, a_level_count INTEGER DEFAULT 0, b_level_count INTEGER DEFAULT 0, c_level_count INTEGER DEFAULT 0, d_level_count INTEGER DEFAULT 0)")
    conn.commit()
    if first_run:
        def hash_pwd(p): return hashlib.sha256(p.encode()).hexdigest()[:16]
        c.execute("INSERT INTO shop(shop_name,province,city,contact) VALUES ('重庆A区旗舰店','重庆市','重庆','张经理'),('成都B区旗舰店','四川省','成都','李经理')")
        c.execute("INSERT INTO sys_user(username,password,real_name,role,shop_id) VALUES ('admin',?,'工厂管理员','admin',NULL),('shop_a',?,'重庆店销售','sale',1),('shop_b',?,'成都店销售','sale',2)", (hash_pwd('123456'),hash_pwd('123456'),hash_pwd('123456')))
        c.execute("INSERT INTO channel_dict(channel_name,weight) VALUES ('抖音',15),('小红书',12),('快手',14),('摩托范',13),('小程序',11),('赛科龙APP',16),('批量导入',10)")
        c.execute("INSERT INTO motorcycle_model(model_name,price_min) VALUES ('RT150S',12800),('AQS250',16800),('RX500',32800)")
        c.execute("INSERT INTO score_rule(full_info_score,time_score,high_intent_score,mid_intent_score,low_intent_score,behavior_freq_score,demand_clear_score) VALUES (20,10,25,10,-15,10,10)")
        c.execute("INSERT INTO level_config(a_min,b_min,c_min,high_value_min) VALUES (75,50,30,80)")
        kw_list = [('现车','high',18),('试驾','high',15),('置换补贴','high',12),('订车','high',20),('油耗','mid',6),('保养','mid',4),('配置','mid',5),('售后','mid',5),('随便看看','low',-12),('等新款','low',-10),('太贵','low',-8),('再考虑','low',-10)]
        c.executemany('INSERT INTO intent_keyword(keyword,type,score_change) VALUES (?,?,?)', kw_list)
        speech_list = [('客户嫌贵','本店支持12期0息金融+置换补贴，月供压力很低'),('对比竞品','同价位我们车架、售后网点更完善'),('邀约试驾','门店现车充足，预约试驾赠送骑行礼包')]
        c.executemany('INSERT INTO ai_speech_lib(scene,speech_content) VALUES (?,?)', speech_list)
        _generate_historical_data(c)
        conn.commit()
    conn.close()

def _generate_historical_data(c):
    base_date = datetime.datetime.now() - datetime.timedelta(days=60)
    for i in range(60):
        date = (base_date + datetime.timedelta(days=i)).strftime('%Y-%m-%d')
        growth_factor = 1 + i * 0.02
        total = int(random.randint(80, 120) * growth_factor)
        new = int(random.randint(10, 30) * growth_factor)
        high = int(random.randint(5, 15) * growth_factor)
        contacted = int(total * 0.3)
        reserve = int(total * 0.15)
        bargain = int(total * 0.1)
        deal = int(total * 0.05)
        lost = int(total * 0.08)
        calls = int(random.randint(20, 50) * growth_factor)
        duration = calls * random.randint(60, 180)
        avg_s = random.randint(55, 75)
        a_c = int(total * 0.2)
        b_c = int(total * 0.3)
        c_c = int(total * 0.3)
        d_c = max(0, total - a_c - b_c - c_c)
        c.execute('INSERT OR REPLACE INTO daily_stats (date,total_leads,new_leads,high_value_leads,contacted_leads,reserve_test_leads,bargain_leads,deal_leads,lost_leads,call_count,total_call_duration,avg_score,a_level_count,b_level_count,c_level_count,d_level_count) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (date,total,new,high,contacted,reserve,bargain,deal,lost,calls,duration,avg_s,a_c,b_c,c_c,d_c))

def db_query(sql, params=()):
    conn = None
    try:
        conn = get_conn()
        return pd.read_sql(sql, conn, params=params)
    except Exception as e:
        st.error(f'数据库查询异常: {e}')
        return pd.DataFrame()
    finally:
        if conn: conn.close()

def db_exec(sql, params=()):
    conn = None
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute(sql, params)
        conn.commit()
        return True
    except Exception as e:
        st.error(f'数据库操作异常: {e}')
        return False
    finally:
        if conn: conn.close()

# ========================== 通用工具函数 ==========================
def clean_score(score_val):
    if score_val is None: return 0
    try: return int(float(str(score_val).strip().split(',')[0]))
    except: return 0

def clean_score_column(df, col='total_score'):
    if col in df.columns:
        df[col] = df[col].apply(clean_score)
    return df

def status_to_cn(s): return STATUS_MAP.get(s, s)

def sort_leads(df, sort_type):
    if sort_type == '按AI评分降序': return df.sort_values('total_score', ascending=False)
    elif sort_type == '按留资时间降序': return df.sort_values('source_time', ascending=False)
    elif sort_type == '按序号升序': return df.sort_values('id', ascending=True)
    elif sort_type == '按线索等级排序':
        level_order = {'A':0,'B':1,'C':2,'D':3}
        df['level_order'] = df['lead_level'].map(level_order)
        return df.sort_values('level_order', ascending=True).drop(columns=['level_order'])
    return df

def get_province(city):
    if pd.isna(city): return '其他'
    city = str(city)
    if any(c in city for c in ['重庆','万州','涪陵']): return '重庆市'
    if any(c in city for c in ['成都','宜宾','绵阳','德阳','泸州','南充','自贡']): return '四川省'
    return '其他'

def _plot(fig, height=None):
    """统一 plotly 图表渲染配置"""
    if height:
        fig.update_layout(height=height)
    st.plotly_chart(fig, use_container_width=True, config={'scrollZoom':False,'displayModeBar':False})

def bar_chart(data, x, y, color=None, height=350):
    if USE_PLOTLY:
        fig = px.bar(data, x=x, y=y, color=color, color_discrete_sequence=px.colors.qualitative.Pastel)
        fig.update_layout(margin=dict(l=20,r=20,t=30,b=20), height=height)
        _plot(fig)
    else:
        st.bar_chart(data[[x,y]].set_index(x), use_container_width=True)

def line_chart(data, x, y, color=None, height=300):
    if USE_PLOTLY:
        fig = px.line(data, x=x, y=y, color_discrete_sequence=[color] if color else None)
        fig.update_layout(margin=dict(l=20,r=20,t=30,b=20), height=height)
        _plot(fig)
    else:
        st.line_chart(data[[x,y]].set_index(x), use_container_width=True)

def render_metric_card(label, value, change=None, change_type='up', css_class=''):
    change_html = ''
    if change is not None:
        arrow = '▲' if change_type == 'up' else '▼'
        color = '#52c41a' if change_type == 'up' else '#ff4d4f'
        change_html = f'<div class="metric-change" style="color:{color}">{arrow} {change}%</div>'
    st.markdown(f'<div class="dashboard-card {css_class}"><div class="metric-label">{label}</div><div class="metric-value">{value}</div>{change_html}</div>', unsafe_allow_html=True)

def get_date_range(preset):
    now = datetime.datetime.now()
    end = now.strftime('%Y-%m-%d %H:%M:%S')
    if preset == '24h':
        start = (now - datetime.timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
    elif preset == '7天':
        start = (now - datetime.timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
    elif preset == '30天':
        start = (now - datetime.timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
    elif preset == '本年':
        start = f"{now.year}-01-01 00:00:00"
    else:
        start = (now - datetime.timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
    return start, end

def render_time_filter(key_suffix=""):
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        preset = st.selectbox("⏱️ 时间范围", ["24h", "7天", "30天", "本年", "自定义"], key=f"time_preset_{key_suffix}")
    start_time, end_time = get_date_range(preset)
    if preset == "自定义":
        with col2:
            s_date = st.date_input("开始", datetime.date.today() - datetime.timedelta(days=7), key=f"time_s_{key_suffix}")
        with col3:
            e_date = st.date_input("结束", datetime.date.today(), key=f"time_e_{key_suffix}")
        start_time = f"{s_date.strftime('%Y-%m-%d')} 00:00:00"
        end_time = f"{e_date.strftime('%Y-%m-%d')} 23:59:59"
    return start_time, end_time

def render_lead_filters(key_prefix=""):
    """渲染线索筛选栏，返回 (level, channel, high_value, status, sort_type, search_key)"""
    st.markdown('<div class="filter-bar">', unsafe_allow_html=True)
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: level = st.selectbox('线索等级', ['全部','A','B','C','D'], key=f'{key_prefix}_level')
    channels = ['全部'] + list(db_query('SELECT channel_name FROM channel_dict')['channel_name'])
    with c2: channel = st.selectbox('来源渠道', channels, key=f'{key_prefix}_channel')
    with c3: high_val = st.selectbox('价值筛选', ['全部','仅高价值'], key=f'{key_prefix}_hv')
    with c4: status = st.selectbox('线索状态', ['全部']+list(STATUS_MAP.values()), key=f'{key_prefix}_status')
    with c5: sort_type = st.selectbox('排序方式', SORT_OPTIONS, key=f'{key_prefix}_sort')
    c1, c2 = st.columns([3, 1])
    with c1: search = st.text_input('🔍 关键词模糊搜索', placeholder='输入手机号、姓名、城市、咨询内容进行搜索', key=f'{key_prefix}_search')
    with c2:
        st.write(''); st.write('')
        if st.button('🔄 刷新列表', use_container_width=True, key=f'{key_prefix}_refresh'):
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    return level, channel, high_val, status, sort_type, search

def apply_lead_filters(leads_df, level, channel, high_val, status, sort_type, search):
    """应用筛选条件到线索DataFrame"""
    filtered = leads_df.copy()
    if level != '全部': filtered = filtered[filtered['lead_level']==level]
    if channel != '全部': filtered = filtered[filtered['channel_name']==channel]
    if high_val == '仅高价值': filtered = filtered[filtered['is_high_value'].fillna(0)==1]
    if status != '全部':
        codes = [k for k,v in STATUS_MAP.items() if v==status]
        filtered = filtered[filtered['lead_status'].isin(codes)] if codes else filtered.iloc[0:0]
    if search.strip():
        key = search.strip()
        mask = (filtered['phone'].astype(str).str.contains(key,case=False,na=False)|filtered['customer_name'].astype(str).str.contains(key,case=False,na=False)|filtered['city'].astype(str).str.contains(key,case=False,na=False)|filtered['consult_content'].astype(str).str.contains(key,case=False,na=False))
        filtered = filtered[mask]
    return sort_leads(filtered, sort_type)

# ========================== AI评分与标签 ==========================
def calculate_lead_score(channel_weight, info_full, consult_text, behavior_count=1, source_time=None):
    conn = get_conn()
    c = conn.cursor()
    rule = c.execute('SELECT * FROM score_rule').fetchone()
    cfg = c.execute('SELECT * FROM level_config').fetchone()
    keywords = c.execute('SELECT keyword,score_change FROM intent_keyword').fetchall()
    conn.close()
    if rule is None: rule = (0, 20, 10, 25, 10, -15, 10, 10)
    if cfg is None: cfg = (0, 75, 50, 30, 80)
    score = int(channel_weight)
    if info_full: score += int(rule[1])
    time_bonus = 0
    if source_time is not None:
        try:
            source_dt = pd.to_datetime(source_time, errors='coerce')
            if pd.notna(source_dt):
                days_ago = (datetime.datetime.now() - source_dt).days
                if days_ago < 0: time_bonus = 0
                elif days_ago <= 3: time_bonus = int(rule[2])
                elif days_ago <= 7: time_bonus = int(int(rule[2]) * 0.6)
                elif days_ago <= 30: time_bonus = int(int(rule[2]) * 0.3)
        except Exception: pass
    score += time_bonus
    for kw, delta in keywords:
        if kw in consult_text: score += int(delta)
    score += min(int(behavior_count) * 2, int(rule[6]))
    if any(char.isdigit() for char in consult_text): score += int(rule[7])
    score = int(max(0, min(score, 100)))
    a_min, b_min, c_min, high_val = int(cfg[1]), int(cfg[2]), int(cfg[3]), int(cfg[4])
    if score >= a_min: level = 'A'
    elif score >= b_min: level = 'B'
    elif score >= c_min: level = 'C'
    else: level = 'D'
    is_high = 1 if score >= high_val else 0
    return score, level, is_high

def _level_from_score(score, cfg):
    a_min, b_min, c_min, high_val = int(cfg[1]), int(cfg[2]), int(cfg[3]), int(cfg[4])
    if score >= a_min: level = 'A'
    elif score >= b_min: level = 'B'
    elif score >= c_min: level = 'C'
    else: level = 'D'
    return level, (1 if score >= high_val else 0)

def ai_generate_tags(consult_text, budget, city):
    tags = []
    if budget:
        try:
            num_str = ''.join([c for c in budget if c.isdigit() or c == '.'])
            if num_str:
                budget_amount = float(num_str)
                if '万' in budget: budget_amount *= 10000
                if budget_amount >= 30000: tags.append('高购买力')
                elif budget_amount >= 15000: tags.append('中购买力')
                else: tags.append('入门预算')
        except Exception: tags.append('入门预算')
    else: tags.append('入门预算')
    high_words = ['现车', '试驾', '订车', '置换']
    for w in high_words:
        if w in consult_text: tags.append('强购车意向'); break
    if '重庆' in city or '万州' in city or '涪陵' in city: tags.append('渝川大区')
    elif '成都' in city or '绵阳' in city or '德阳' in city or '宜宾' in city or '泸州' in city: tags.append('渝川大区')
    if '通勤' in consult_text or '代步' in consult_text: tags.append('通勤代步需求')
    if '摩旅' in consult_text or '续航' in consult_text: tags.append('摩旅出行需求')
    return ','.join(tags) if tags else '普通潜客'

def ai_analyze_call(call_content, lead):
    content_lower = call_content.lower()
    score_bonus, tags_to_add, status_suggestion, summary_parts = 0, [], None, []
    negative_words = ['不', '没', '未', '别', '拒绝']
    def check_intent(keywords, bonus, status, tag, summary):
        nonlocal score_bonus, status_suggestion, tags_to_add, summary_parts
        for kw in keywords:
            if kw in content_lower:
                idx = content_lower.find(kw)
                context = content_lower[max(0, idx-5):idx+len(kw)+5]
                is_negated = any(nw in context for nw in negative_words)
                if not is_negated:
                    score_bonus += bonus
                    status_suggestion = status
                    if tag: tags_to_add.append(tag)
                    summary_parts.append(summary)
                    return True
        return False
    if check_intent(['不买','不要了','不考虑','已购','放弃'], -20, 'lost', '客户流失', '客户明确表示不购买或放弃'):
        pass
    elif check_intent(['订车','下单','付定金','购买','就这辆'], 25, 'bargain', '强烈购买意向', '客户表达购买/订车意向'):
        pass
    elif check_intent(['试驾','预约','到店','周末','明天','下午'], 15, 'reserve_test', '预约到店', '客户明确表达试驾/到店意向'):
        pass
    elif check_intent(['考虑','再看看','对比','比较'], 5, 'contacted', '犹豫比较中', '客户仍在比较阶段'):
        pass
    elif check_intent(['太贵','预算不够','价格高','优惠'], -5, 'bargain', '价格敏感', '客户对价格敏感'):
        pass
    else:
        status_suggestion = 'contacted'
        summary_parts.append('客户已建立联系')
    if any(w in content_lower for w in ['配置','油耗','动力','续航']):
        score_bonus += 5; summary_parts.append('关注性能/配置')
    if any(w in content_lower for w in ['置换','金融','分期','贷款']):
        score_bonus += 5; tags_to_add.append('金融/置换需求'); summary_parts.append('关注金融/置换')
    old_score = clean_score(lead['total_score'])
    new_score = max(0, min(100, old_score + score_bonus))
    conn = get_conn()
    cfg = conn.execute('SELECT * FROM level_config').fetchone()
    conn.close()
    new_level, new_is_high = _level_from_score(new_score, cfg)
    old_tags = str(lead['user_tags']).split(',') if lead['user_tags'] else []
    old_tags = [t for t in old_tags if t and t != '普通潜客']
    combined_tags = list(dict.fromkeys(old_tags + tags_to_add))
    new_tags = ','.join(combined_tags) if combined_tags else '普通潜客'
    summary_text = '；'.join(summary_parts) if summary_parts else '通话已建立'
    ai_summary = f'{summary_text}。AI评分变化：{old_score}→{new_score}'
    if status_suggestion:
        ai_summary += f'，建议状态：{STATUS_MAP.get(status_suggestion, status_suggestion)}'
    return new_score, new_level, new_is_high, new_tags, status_suggestion, ai_summary

def get_ai_speech(scene, model="", budget=""):
    speeches = AI_SPEECH_SCENES.get(scene, ["您好，请问有什么可以帮您？"])
    speech = random.choice(speeches)
    try:
        return speech.format(model=model, budget=budget)
    except (KeyError, IndexError):
        return speech

def extract_info_from_call(transcript, lead):
    info = {
        "budget": lead.get("budget", ""), "model_interest": lead.get("model_id", None),
        "intent_level": "中", "next_follow_date": "", "key_points": [],
        "objections": [], "recommended_action": "继续跟进"
    }
    t = transcript.lower()
    budget_patterns = [r'(\d+[\.\d]*)\s*万', r'预算[大概约]*(\d+[\.\d]*)', r'(\d+[\.\d]*)\s*左右', r'最多[不超过]*(\d+[\.\d]*)']
    for pattern in budget_patterns:
        match = re.search(pattern, t)
        if match:
            info["budget"] = match.group(1) + "万"
            info["key_points"].append(f"客户预算：{info['budget']}")
            break
    models = {"rt150s": 1, "rt150": 1, "aq250": 2, "aqs250": 2, "rx500": 3}
    for m, mid in models.items():
        if m in t.replace(" ", ""):
            info["model_interest"] = mid
            info["key_points"].append(f"意向车型：{m.upper()}")
            break
    high_signals = ["订车", "下单", "买", "要", "确定", "成交", "现在", "今天"]
    mid_signals = ["试驾", "看看", "对比", "考虑", "商量"]
    low_signals = ["随便", "问问", "了解", "不急", "再说"]
    high_score = sum(1 for s in high_signals if s in t)
    mid_score = sum(1 for s in mid_signals if s in t)
    low_score = sum(1 for s in low_signals if s in t)
    if high_score >= 2: info["intent_level"] = "高"; info["recommended_action"] = "立即推进成交"
    elif mid_score >= 2: info["intent_level"] = "中"; info["recommended_action"] = "预约试驾/到店"
    elif low_score >= 2: info["intent_level"] = "低"; info["recommended_action"] = "长期培育"
    objections = []
    if "贵" in t or "高" in t or "超预算" in t: objections.append("价格敏感")
    if "远" in t or "不方便" in t: objections.append("距离/便利性")
    if "对比" in t or "别的" in t: objections.append("正在对比竞品")
    if "等" in t or "不急" in t: objections.append("不急于购买")
    info["objections"] = objections
    if "明天" in t: info["next_follow_date"] = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    elif "周末" in t or "周六" in t or "周日" in t:
        today = datetime.datetime.now().weekday()
        if today < 5: info["next_follow_date"] = (datetime.datetime.now() + datetime.timedelta(days=5-today)).strftime("%Y-%m-%d")
        else: info["next_follow_date"] = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    elif "下周" in t: info["next_follow_date"] = (datetime.datetime.now() + datetime.timedelta(days=7)).strftime("%Y-%m-%d")
    return info

# ========================== 统计计算 ==========================
def _compute_lead_counts(leads_df):
    """从线索DataFrame计算各状态/等级计数（get_today_stats与_update_daily_stats共用）"""
    leads_df = clean_score_column(leads_df)
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    return {
        'total': len(leads_df),
        'today_new': len(leads_df[leads_df['source_time'].astype(str).str.startswith(today)]),
        'high': len(leads_df[leads_df['is_high_value'].fillna(0)==1]),
        'untouch': len(leads_df[leads_df['lead_status']=='untouch']),
        'contacted': len(leads_df[leads_df['lead_status']=='contacted']),
        'reserve': len(leads_df[leads_df['lead_status']=='reserve_test']),
        'bargain': len(leads_df[leads_df['lead_status']=='bargain']),
        'deal': len(leads_df[leads_df['lead_status']=='deal']),
        'lost': len(leads_df[leads_df['lead_status']=='lost']),
        'a': len(leads_df[leads_df['lead_level']=='A']),
        'b': len(leads_df[leads_df['lead_level']=='B']),
        'c': len(leads_df[leads_df['lead_level']=='C']),
        'd': len(leads_df[leads_df['lead_level']=='D']),
        'avg_score': round(leads_df['total_score'].mean(), 1) if len(leads_df)>0 else 0,
    }

def get_today_stats():
    leads = db_query('SELECT * FROM customer_leads')
    if len(leads) == 0: return {}
    counts = _compute_lead_counts(leads)
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    calls = db_query("SELECT COUNT(*) as cnt FROM call_record WHERE create_time LIKE ?", (f'{today}%',))
    call_count = int(calls.iloc[0]['cnt']) if len(calls)>0 else 0
    call_duration = db_query("SELECT COALESCE(SUM(call_duration),0) as total FROM call_record WHERE create_time LIKE ?", (f'{today}%',))
    total_duration = int(call_duration.iloc[0]['total']) if len(call_duration)>0 else 0
    return {'total': counts['total'], 'today_new': counts['today_new'], 'high': counts['high'],
            'contacted': counts['contacted'], 'reserve': counts['reserve'], 'bargain': counts['bargain'],
            'deal': counts['deal'], 'lost': counts['lost'], 'untouch': counts['untouch'],
            'calls': call_count, 'duration': total_duration, 'avg_score': counts['avg_score'],
            'a': counts['a'], 'b': counts['b'], 'c': counts['c'], 'd': counts['d']}

def _update_daily_stats():
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    leads = db_query('SELECT * FROM customer_leads')
    if len(leads) == 0: return
    counts = _compute_lead_counts(leads)
    calls = db_query("SELECT COUNT(*) as cnt FROM call_record WHERE create_time LIKE ?", (f'{today}%',))
    call_count = int(calls.iloc[0]['cnt']) if len(calls)>0 else 0
    call_duration = db_query("SELECT COALESCE(SUM(call_duration),0) as total FROM call_record WHERE create_time LIKE ?", (f'{today}%',))
    total_duration = int(call_duration.iloc[0]['total']) if len(call_duration)>0 else 0
    db_exec('INSERT OR REPLACE INTO daily_stats (date,total_leads,new_leads,high_value_leads,contacted_leads,reserve_test_leads,bargain_leads,deal_leads,lost_leads,call_count,total_call_duration,avg_score,a_level_count,b_level_count,c_level_count,d_level_count) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (today,counts['total'],counts['today_new'],counts['high'],counts['contacted'],counts['reserve'],counts['bargain'],counts['deal'],counts['lost'],call_count,total_duration,counts['avg_score'],counts['a'],counts['b'],counts['c'],counts['d']))

def get_historical_stats(days=30):
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=days)
    df = db_query('SELECT * FROM daily_stats WHERE date >= ? AND date <= ? ORDER BY date', (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
    if len(df) == 0: return pd.DataFrame()
    df['date'] = pd.to_datetime(df['date'])
    return df

def calculate_yoy_mom():
    today = datetime.datetime.now()
    today_str = today.strftime('%Y-%m-%d')
    yesterday_str = (today - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    last_week_str = (today - datetime.timedelta(days=7)).strftime('%Y-%m-%d')
    last_month_str = (today - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
    today_stats = db_query('SELECT * FROM daily_stats WHERE date = ?', (today_str,))
    yesterday_stats = db_query('SELECT * FROM daily_stats WHERE date = ?', (yesterday_str,))
    last_week_stats = db_query('SELECT * FROM daily_stats WHERE date = ?', (last_week_str,))
    last_month_stats = db_query('SELECT * FROM daily_stats WHERE date = ?', (last_month_str,))
    def get_val(df, col, default=0):
        return df.iloc[0][col] if len(df) > 0 else default
    def calc_change(current, previous):
        return round((current - previous) / previous * 100, 1) if previous != 0 else 0
    metrics = ['total_leads', 'new_leads', 'high_value_leads', 'deal_leads', 'call_count', 'avg_score']
    result = {}
    for m in metrics:
        current = get_val(today_stats, m)
        result[m] = {
            'current': current,
            'day_change': calc_change(current, get_val(yesterday_stats, m)),
            'week_change': calc_change(current, get_val(last_week_stats, m)),
            'month_change': calc_change(current, get_val(last_month_stats, m))
        }
    return result

def calculate_funnel_stats(leads_df=None):
    if leads_df is None:
        leads_df = db_query('SELECT * FROM customer_leads')
    total = len(leads_df)
    if total == 0:
        return {'total': 0, 'funnel': {}, 'conversion_rates': {}}
    funnel = {}
    for i, stage in enumerate(FUNNEL_STAGES):
        count = len(leads_df[leads_df['lead_status'] == stage])
        funnel[stage] = {'name': FUNNEL_NAMES[i], 'count': count}
    funnel['total'] = total
    conversion_rates = {}
    prev_count = total
    for i, stage in enumerate(FUNNEL_STAGES):
        curr_count = funnel[stage]['count']
        if i == 0:
            conversion_rates[f'stage_{i}'] = {'from_prev': 100.0, 'of_total': round(curr_count / total * 100, 1)}
        else:
            rate = round(curr_count / prev_count * 100,1) if prev_count > 0 else 0
            conversion_rates[f'stage_{i}'] = {'from_prev': rate, 'of_total': round(curr_count / total * 100, 1)}
        prev_count = curr_count
    conversion_rates['overall'] = round(funnel['deal']['count'] / funnel['untouch']['count'] * 100, 2) if funnel['untouch']['count'] > 0 else 0
    funnel['conversion_rates'] = conversion_rates
    funnel['trend_30d'] = get_funnel_trend(days=30)
    return funnel

def get_funnel_trend(days=30):
    """获取最近N天各漏斗阶段的数量趋势（单次SQL查询，避免N+1问题）"""
    start_date = datetime.datetime.now() - datetime.timedelta(days=days)
    df = db_query("SELECT DATE(source_time) as dt, lead_status, COUNT(*) as cnt FROM customer_leads WHERE source_time >= ? GROUP BY DATE(source_time), lead_status", (start_date.strftime('%Y-%m-%d'),))
    all_dates = [(start_date + datetime.timedelta(days=i)).strftime('%Y-%m-%d') for i in range(days)]
    result = {}
    for date in all_dates:
        row = {'date': date, 'total': 0}
        for stage in FUNNEL_STAGES: row[stage] = 0
        result[date] = row
    if len(df) > 0:
        for _, r in df.iterrows():
            date = str(r['dt'])
            if date in result:
                status = r['lead_status']
                cnt = int(r['cnt'])
                if status in FUNNEL_STAGES: result[date][status] = cnt
                result[date]['total'] += cnt
    return [result[d] for d in all_dates]

def get_funnel_channel_breakdown(start_t=None, end_t=None):
    sql = '''SELECT c.channel_name, l.lead_status, COUNT(*) as cnt FROM customer_leads l LEFT JOIN channel_dict c ON l.channel_id = c.id WHERE l.source_time BETWEEN ? AND ? GROUP BY c.channel_name, l.lead_status'''
    df = db_query(sql, (start_t, end_t))
    if len(df) == 0: return []
    pivot = df.pivot_table(index='channel_name', columns='lead_status', values='cnt', aggfunc='sum', fill_value=0)
    result = []
    for channel in pivot.index:
        row = {'channel': channel}
        for stage in FUNNEL_STAGES:
            row[stage] = int(pivot.loc[channel, stage]) if stage in pivot.columns else 0
        row['total'] = sum(row[stage] for stage in FUNNEL_STAGES)
        result.append(row)
    return result

# ========================== 线索生成与分发 ==========================
def _get_existing_phones():
    try:
        df = db_query('SELECT phone FROM customer_leads')
        return set(df['phone'].dropna().astype(str))
    except Exception:
        return set()

def generate_random_lead():
    name = random.choice(NAME_POOL)
    existing_phones = _get_existing_phones()
    phone = None
    for _ in range(100):
        phone = random.choice(PHONE_PREFIX) + ''.join(random.choices(string.digits, k=8))
        if phone not in existing_phones:
            break
    else:
        phone = random.choice(PHONE_PREFIX) + str(int(time.time()))[-8:]
    city = random.choice(CITY_POOL)
    budget = random.choice(BUDGET_POOL)
    model_name = random.choice(MODEL_POOL)
    model_id = 1 if model_name == 'RT150S' else (2 if model_name == 'AQS250' else 3)
    consult = random.choice(CONSULT_TEMPLATES).format(model=model_name, budget=budget)
    return phone, name, city, budget, model_id, consult

def execute_distribute():
    unassign = db_query('SELECT * FROM customer_leads WHERE assign_shop_id IS NULL')
    sales = db_query("SELECT id,shop_id FROM sys_user WHERE role='sale'")
    shop_sale_map = {s['shop_id']: s['id'] for _,s in sales.iterrows()}
    cd_cities = ['成都','绵阳','德阳','宜宾','泸州','南充','自贡']
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    count = 0
    for _,lead in unassign.iterrows():
        city = lead['city'] or ''
        match_shop_id = 2 if city and any(c in str(city) for c in cd_cities) else 1
        sale_id = shop_sale_map.get(match_shop_id)
        if sale_id is None: continue
        if db_exec('UPDATE customer_leads SET assign_shop_id=?,assign_sale_id=?,assign_time=? WHERE id=?', (match_shop_id,sale_id,now,lead['id'])):
            count += 1
    return count

def auto_crawl_leads():
    channels_df = db_query("SELECT id,channel_name,weight FROM channel_dict WHERE channel_name!='批量导入'")
    if len(channels_df)==0: return 0, []
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    count = random.randint(2,4)
    success = 0
    results = []
    for _ in range(count):
        ch = channels_df.sample(1).iloc[0]
        phone,name,city,budget,model_id,consult = generate_random_lead()
        full = bool(phone and name and city and len(str(phone))>=7 and len(str(name))>=1 and len(str(city))>=1)
        score,level,high_val = calculate_lead_score(int(ch['weight']),full,consult,source_time=now)
        tags = ai_generate_tags(consult,budget,city)
        if db_exec('INSERT INTO customer_leads(phone,customer_name,city,budget,model_id,channel_id,consult_content,source_time,latest_source_time,total_score,lead_level,is_high_value,user_tags,lead_status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (phone,name,city,budget,int(model_id),int(ch['id']),consult,now,now,int(score),level,int(high_val),tags,'untouch')):
            success += 1
            results.append({
                'time': now,
                'platform': str(ch['channel_name']),
                'type': '线索采集',
                'score': int(score),
                'level': level,
                'confidence': f'{random.uniform(85, 99):.1f}%',
                'status': '成功',
            })
    return success, results

# ========================== Excel导出 ==========================
def get_excel_template():
    df = pd.DataFrame(columns=['手机号','客户姓名','城市','预算','意向车型','咨询内容'])
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer,engine='openpyxl') as w:
        df.to_excel(w,index=False,sheet_name='线索导入模板')
    buffer.seek(0)
    return buffer

def export_leads_excel(df):
    try:
        if df is None or len(df) == 0:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer,engine='openpyxl') as w:
                pd.DataFrame().to_excel(w,index=False,sheet_name='线索列表')
            buffer.seek(0)
            return buffer.getvalue()
        export_df = df.copy()
        export_df = clean_score_column(export_df)
        export_df['lead_status'] = export_df['lead_status'].apply(status_to_cn)
        export_df = export_df.rename(columns={
            'phone':'手机号','customer_name':'客户姓名','city':'城市','budget':'预算','model_name':'意向车型',
            'channel_name':'来源渠道','consult_content':'咨询内容','total_score':'AI评分','lead_level':'线索等级',
            'is_high_value':'是否高价值','user_tags':'用户标签','shop_name':'分配门店','source_time':'来源时间',
            'lead_status':'线索状态','first_contact_time':'首次接触时间','call_count':'外呼次数'
        })
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer,engine='openpyxl') as w:
            export_df.to_excel(w,index=False,sheet_name='线索列表')
        buffer.seek(0)
        return buffer.getvalue()
    except Exception as e:
        st.error(f'导出失败: {e}')
        return b''

# ========================== 弹窗对话框 ==========================
@st.dialog('编辑线索信息')
def dialog_edit_lead(lead_id):
    lead = db_query('SELECT * FROM customer_leads WHERE id=?',(lead_id,))
    if len(lead) == 0:
        st.error('线索不存在')
        return
    lead = lead.iloc[0]
    models = db_query('SELECT id,model_name FROM motorcycle_model')
    col1,col2 = st.columns(2)
    with col1:
        name = st.text_input('客户姓名',value=lead['customer_name'] or '')
        phone = st.text_input('手机号',value=lead['phone'])
        city = st.text_input('所在城市',value=lead['city'] or '')
        budget = st.text_input('购车预算',value=lead['budget'] or '')
    with col2:
        model_df = models[models['id']==lead['model_id']]
        cur_model = model_df.iloc[0]['model_name'] if len(model_df)>0 else models.iloc[0]['model_name']
        model_names_list = list(models['model_name'])
        try:
            model_idx = model_names_list.index(cur_model)
        except ValueError:
            model_idx = 0
        model_name = st.selectbox('意向车型',model_names_list,index=model_idx)
        status_list = list(STATUS_MAP.values())
        cur_status = status_to_cn(lead['lead_status'])
        try:
            status_idx = status_list.index(cur_status)
        except ValueError:
            status_idx = 0
        status_cn = st.selectbox('线索状态',status_list,index=status_idx)
        tags = st.text_input('用户标签',value=lead['user_tags'] or '')
    content = st.text_area('咨询/跟进内容',value=lead['consult_content'] or '')
    col1,col2 = st.columns(2)
    with col1:
        if st.button('取消',use_container_width=True):
            open_key = f"edit_open_{lead_id}"
            if open_key in st.session_state: del st.session_state[open_key]
            st.rerun()
    with col2:
        if st.button('保存修改',type='primary',use_container_width=True):
            exist = db_query('SELECT id FROM customer_leads WHERE phone=? AND id!=?',(phone,lead_id))
            if len(exist)>0:
                st.error('该手机号已存在，无法修改')
                return
            status_matches = [k for k,v in STATUS_MAP.items() if v==status_cn]
            status_code = status_matches[0] if status_matches else lead['lead_status']
            model_match = models[models['model_name']==model_name]
            model_id = int(model_match['id'].iloc[0]) if len(model_match)>0 else (lead['model_id'] or 1)
            db_exec('UPDATE customer_leads SET customer_name=?,phone=?,city=?,budget=?,model_id=?,lead_status=?,consult_content=?,user_tags=? WHERE id=?', (name,phone,city,budget,model_id,status_code,content,tags,lead_id))
            st.success('线索信息已更新')
            open_key = f"edit_open_{lead_id}"
            if open_key in st.session_state: del st.session_state[open_key]
            st.rerun()

@st.dialog("🤖 AI智能外呼", width="large")
def dialog_call_lead(lead_id, shop_id, sale_id):
    state_key = f"call_state_{lead_id}"
    start_key = f"call_start_{lead_id}"
    transcript_key = f"call_transcript_{lead_id}"
    ai_info_key = f"call_ai_info_{lead_id}"
    if state_key not in st.session_state: st.session_state[state_key] = "idle"
    if transcript_key not in st.session_state: st.session_state[transcript_key] = []
    if ai_info_key not in st.session_state: st.session_state[ai_info_key] = None
    lead_row = db_query("SELECT * FROM customer_leads WHERE id=?", (lead_id,))
    if len(lead_row) == 0:
        st.error("线索不存在"); return
    lead = lead_row.iloc[0]
    old_score = clean_score(lead["total_score"])
    model_name = "未指定"
    if lead["model_id"]:
        mdf = db_query("SELECT model_name FROM motorcycle_model WHERE id=?", (lead["model_id"],))
        if len(mdf) > 0: model_name = mdf.iloc[0]["model_name"]
    # FIX: 用 COUNT(*) 替代 SELECT * 计数
    call_cnt_df = db_query("SELECT COUNT(*) as cnt FROM call_record WHERE lead_id=?", (lead_id,))
    call_cnt = int(call_cnt_df.iloc[0]['cnt']) if len(call_cnt_df) > 0 else 0
    st.subheader(f"线索 #{lead_id} - {lead['customer_name']}")
    col_info1, col_info2, col_info3 = st.columns(3)
    with col_info1:
        st.write(f"**📱 {lead['phone']}**")
        st.caption(f"📍 {lead['city']} | 车型：{model_name}")
    with col_info2:
        st.write(f"**当前评分：{old_score}分 ({lead['lead_level']}级)**")
        st.caption(f"标签：{lead['user_tags']}")
    with col_info3:
        st.write(f"**状态：{status_to_cn(lead['lead_status'])}**")
        st.caption(f"历史外呼：{call_cnt} 次")
    st.divider()
    current_state = st.session_state[state_key]
    if current_state in ["idle", "dialing"]:
        if current_state == "idle":
            st.markdown("<div style='text-align:center; padding:40px 0;'><div style='font-size:60px; margin-bottom:20px;'>📞</div><div style='font-size:18px; color:#666; margin-bottom:30px;'>准备拨打客户电话</div></div>", unsafe_allow_html=True)
            col1, col2, col3 = st.columns([1,2,1])
            with col2:
                if st.button("🤖 启动AI智能外呼", type="primary", use_container_width=True):
                    st.session_state[state_key] = "connected"
                    st.session_state[start_key] = time.time()
                    opening = get_ai_speech("开场白", model=model_name, budget=lead.get("budget",""))
                    st.session_state[transcript_key].append({"role": "ai", "text": opening, "time": datetime.datetime.now().strftime("%H:%M:%S")})
                    st.rerun()
    elif current_state == "connected":
        elapsed = int(time.time() - st.session_state[start_key]) if start_key in st.session_state else 0
        timer_html = f"""<div style="background:linear-gradient(135deg, #52c41a 0%, #389e0d 100%); color:white; border-radius:12px; padding:15px; text-align:center; margin-bottom:16px;"><div style="font-size:14px; opacity:0.9;">⏱️ 通话时长</div><div style="font-size:36px; font-weight:bold; letter-spacing:3px;">{elapsed//60:02d}:{elapsed%60:02d}</div><div style="font-size:12px; margin-top:5px;">🔴 通话中 | AI机器人正在服务</div></div>"""
        st.components.v1.html(timer_html, height=120)
        st.divider()
        st.subheader("💬 AI智能对话记录")
        transcript = st.session_state[transcript_key]
        chat_html = "<div style='background:#f6ffed; border:1px solid #b7eb8f; border-radius:8px; padding:15px; max-height:300px; overflow-y:auto;'>"
        for msg in transcript:
            if msg["role"] == "ai":
                chat_html += f"<div style='margin-bottom:10px;'><span style='background:#1890ff; color:white; padding:4px 8px; border-radius:4px; font-size:12px;'>🤖 AI</span> <span style='color:#999; font-size:11px;'>{msg['time']}</span><div style='margin-top:4px; background:#e6f7ff; padding:8px 12px; border-radius:8px; display:inline-block; max-width:80%;'>{msg['text']}</div></div>"
            else:
                chat_html += f"<div style='margin-bottom:10px; text-align:right;'><span style='color:#999; font-size:11px;'>{msg['time']}</span> <span style='background:#52c41a; color:white; padding:4px 8px; border-radius:4px; font-size:12px;'>👤 客户</span><div style='margin-top:4px; background:#f6ffed; padding:8px 12px; border-radius:8px; display:inline-block; max-width:80%; text-align:left;'>{msg['text']}</div></div>"
        chat_html += "</div>"
        st.markdown(chat_html, unsafe_allow_html=True)
        if len(transcript) > 0 and transcript[-1]["role"] == "ai":
            wave_html = "<div style='text-align:center; padding:10px 0;'><span style='display:inline-block; width:4px; height:20px; background:#1890ff; border-radius:2px; animation:wave 1s infinite;'></span><span style='display:inline-block; width:4px; height:30px; background:#1890ff; border-radius:2px; animation:wave 1s infinite 0.1s; margin:0 2px;'></span><span style='display:inline-block; width:4px; height:15px; background:#1890ff; border-radius:2px; animation:wave 1s infinite 0.2s;'></span><span style='display:inline-block; width:4px; height:25px; background:#1890ff; border-radius:2px; animation:wave 1s infinite 0.3s; margin:0 2px;'></span><span style='display:inline-block; width:4px; height:18px; background:#1890ff; border-radius:2px; animation:wave 1s infinite 0.4s;'></span><span style='display:inline-block; width:4px; height:22px; background:#1890ff; border-radius:2px; animation:wave 1s infinite 0.5s; margin:0 2px;'></span><span style='display:inline-block; width:4px; height:28px; background:#1890ff; border-radius:2px; animation:wave 1s infinite 0.6s;'></span><style>@keyframes wave {0%,100%{transform:scaleY(0.5);} 50%{transform:scaleY(1);}}</style><div style='font-size:12px; color:#1890ff; margin-top:5px;'>AI正在说话...</div></div>"
            st.components.v1.html(wave_html, height=80)
        st.divider()
        col1, col2 = st.columns([3,1])
        with col1:
            user_input = st.text_area("🎤 客户语音转写（模拟ASR）", placeholder="在此输入客户回复内容，AI将自动分析并回应...", height=80, key=f"user_speech_{lead_id}")
        with col2:
            st.write(""); st.write("")
            if st.button("📤 发送", use_container_width=True, type="primary"):
                if user_input.strip():
                    st.session_state[transcript_key].append({"role": "user", "text": user_input.strip(), "time": datetime.datetime.now().strftime("%H:%M:%S")})
                    t_lower = user_input.strip().lower()
                    if any(w in t_lower for w in ["预算", "钱", "价格", "贵", "便宜"]): ai_reply = get_ai_speech("确认预算", model=model_name, budget=lead.get("budget",""))
                    elif any(w in t_lower for w in ["车型", "车", "摩托", "排", "cc"]): ai_reply = get_ai_speech("确认车型", model=model_name, budget=lead.get("budget",""))
                    elif any(w in t_lower for w in ["买", "订", "要", "成交", "确定"]): ai_reply = get_ai_speech("促成成交", model=model_name, budget=lead.get("budget",""))
                    elif any(w in t_lower for w in ["考虑", "想想", "对比", "犹豫"]): ai_reply = get_ai_speech("异议处理", model=model_name, budget=lead.get("budget",""))
                    else: ai_reply = get_ai_speech("确认车型", model=model_name, budget=lead.get("budget",""))
                    st.session_state[transcript_key].append({"role": "ai", "text": ai_reply, "time": datetime.datetime.now().strftime("%H:%M:%S")})
                    st.rerun()
        st.caption("💡 快捷场景：")
        qc_cols = st.columns(5)
        quick_scenes = [("💰 确认预算","确认预算"),("🏍️ 确认车型","确认车型"),("🎯 促成成交","促成成交"),("❓ 异议处理","异议处理"),("👋 结束语","结束语")]
        for idx, (btn_label, scene) in enumerate(quick_scenes):
            with qc_cols[idx]:
                if st.button(btn_label, use_container_width=True):
                    ai_reply = get_ai_speech(scene, model=model_name, budget=lead.get("budget",""))
                    st.session_state[transcript_key].append({"role": "ai", "text": ai_reply, "time": datetime.datetime.now().strftime("%H:%M:%S")})
                    st.rerun()
        st.divider()
        col_end1, col_end2 = st.columns([3,1])
        with col_end2:
            if st.button("🔴 挂断并AI分析", type="primary", use_container_width=True):
                st.session_state[state_key] = "analyzing"; st.rerun()
    elif current_state == "analyzing":
        st.markdown("<div style='text-align:center; padding:20px 0;'><div style='font-size:40px; margin-bottom:15px;'>🧠</div><div style='font-size:18px; font-weight:bold; color:#1890ff;'>AI正在分析通话内容...</div><div style='color:#999; font-size:14px; margin-top:10px;'>自动提取客户意向、预算、车型偏好等关键信息</div></div>", unsafe_allow_html=True)
        with st.spinner("AI分析中..."):
            time.sleep(1.5)
            transcript = st.session_state[transcript_key]
            full_text = " ".join([msg["text"] for msg in transcript])
            ai_info = extract_info_from_call(full_text, lead)
            st.session_state[ai_info_key] = ai_info
            new_score, new_level, new_is_high, new_tags, suggested_status, ai_summary = ai_analyze_call(full_text, lead)
            duration = max(1, int(time.time() - st.session_state[start_key]) if start_key in st.session_state else 1)
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            db_exec("INSERT INTO call_record(lead_id,shop_id,call_duration,call_content,ai_analysis,score_after_call,level_after_call,create_time) VALUES(?,?,?,?,?,?,?,?)", (lead_id, shop_id, duration, full_text, ai_summary, new_score, new_level, now))
            st.session_state["_temp_call_data"] = {"lead_id": lead_id, "shop_id": shop_id, "sale_id": sale_id, "new_score": new_score, "new_level": new_level, "new_is_high": new_is_high, "new_tags": new_tags, "suggested_status": suggested_status, "ai_summary": ai_summary, "duration": duration, "now": now, "full_text": full_text, "ai_info": ai_info}
            st.session_state[state_key] = "ended"; st.rerun()
    elif current_state == "ended":
        temp_data = st.session_state.get("_temp_call_data", {})
        if not temp_data:
            st.error("数据丢失，请重新拨打"); return
        ai_info = temp_data.get("ai_info", {})
        duration = temp_data.get("duration", 0)
        new_score = temp_data.get("new_score", 0)
        new_level = temp_data.get("new_level", "D")
        suggested_status = temp_data.get("suggested_status", "contacted")
        ai_summary = temp_data.get("ai_summary", "")
        st.success(f"✅ 通话结束！时长 {duration} 秒")
        st.divider()
        st.subheader("📊 AI智能分析结果")
        col1, col2, col3 = st.columns(3)
        with col1: st.metric("AI评分变化", f"{old_score} → {new_score}", f"{new_level}级")
        with col2: st.metric("客户意向等级", ai_info.get("intent_level", "中"))
        with col3: st.metric("建议动作", ai_info.get("recommended_action", "继续跟进"))
        st.subheader("🔍 AI自动提取的客户信息")
        col_a, col_b = st.columns(2)
        with col_a:
            new_budget = st.text_input("💰 更新预算", value=ai_info.get("budget", lead.get("budget", "")), key=f"ai_budget_{lead_id}")
            model_opts = ["RT150S", "AQS250", "RX500"]
            new_model = st.selectbox("🏍️ 更新意向车型", model_opts, index=model_opts.index(model_name) if model_name in model_opts else 0, key=f"ai_model_{lead_id}")
        with col_b:
            follow_date_str = ai_info.get("next_follow_date", "")
            follow_default = datetime.datetime.strptime(follow_date_str, "%Y-%m-%d") if follow_date_str else datetime.datetime.now()
            next_follow = st.date_input("📅 下次跟进日期", value=follow_default, key=f"ai_follow_{lead_id}")
            suggested_cn = status_to_cn(suggested_status)
            status_vals = list(STATUS_MAP.values())
            new_status = st.selectbox("🔄 更新线索状态", status_vals, index=status_vals.index(suggested_cn) if suggested_cn in status_vals else 0, key=f"ai_status_{lead_id}")
        if ai_info.get("key_points"):
            st.caption("📌 AI识别关键信息：")
            for point in ai_info["key_points"]: st.markdown(f"- {point}")
        if ai_info.get("objections"):
            st.caption("⚠️ 客户异议：")
            for obj in ai_info["objections"]: st.markdown(f"- {obj}")
        st.text_area("📝 AI通话总结", value=ai_summary, height=100, disabled=True, key=f"ai_summary_{lead_id}")
        st.divider()
        col_confirm1, col_confirm2 = st.columns([1,1])
        with col_confirm1:
            if st.button("❌ 放弃更新", use_container_width=True):
                for key in [state_key, start_key, transcript_key, ai_info_key, "_temp_call_data"]:
                    if key in st.session_state: del st.session_state[key]
                open_key = f"call_open_{lead_id}"
                if open_key in st.session_state: del st.session_state[open_key]
                st.rerun()
        with col_confirm2:
            if st.button("✅ 确认更新线索", type="primary", use_container_width=True):
                status_matches = [k for k,v in STATUS_MAP.items() if v==new_status]
                status_code = status_matches[0] if status_matches else 'contacted'
                model_id = {"RT150S": 1, "AQS250": 2, "RX500": 3}.get(new_model, 1)
                db_exec("UPDATE customer_leads SET total_score=?,lead_level=?,is_high_value=?,user_tags=?,lead_status=?,budget=?,model_id=?,first_contact_time=COALESCE(first_contact_time,?),latest_source_time=?,consult_content=COALESCE(consult_content,'')||? WHERE id=?", (new_score, new_level, temp_data["new_is_high"], temp_data["new_tags"], status_code, new_budget, model_id, temp_data["now"], temp_data["now"], f"\n[AI外呼]{temp_data['full_text'][:200]}...", temp_data["lead_id"]))
                follow_content = f"AI智能外呼 | 时长{duration}秒 | 意向:{ai_info.get('intent_level','中')} | 预算:{new_budget} | 建议:{ai_info.get('recommended_action','继续跟进')}"
                db_exec("INSERT INTO lead_follow_record(lead_id,sale_id,follow_type,follow_content,ai_summary,create_time) VALUES(?,?,?,?,?,?)", (temp_data["lead_id"], temp_data["sale_id"], "AI智能外呼", follow_content, ai_summary, temp_data["now"]))
                for key in [state_key, start_key, transcript_key, ai_info_key, "_temp_call_data"]:
                    if key in st.session_state: del st.session_state[key]
                open_key = f"call_open_{lead_id}"
                if open_key in st.session_state: del st.session_state[open_key]
                st.success("✅ 线索已更新！AI外呼闭环完成")
                time.sleep(1); st.rerun()

@st.dialog("🎙️ 手动外呼")
def dialog_manual_call(lead_id, shop_id, sale_id):
    """人工外呼：针对已有线索，销售手动打电话，手动记录通话内容，AI分析闭环"""
    lead_row = db_query("SELECT * FROM customer_leads WHERE id=?", (lead_id,))
    if len(lead_row) == 0:
        st.error("线索不存在"); return
    lead = lead_row.iloc[0]
    st.subheader(f"🎙️ 手动外呼 - #{lead_id} {lead['customer_name'] or '未知客户'}")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.write(f"**📱 {lead['phone']}**"); st.caption(f"📍 {lead['city'] or '未知'}")
    with col2:
        st.write(f"预算：{lead['budget'] or '未填写'}"); st.caption(f"标签：{lead['user_tags'] or '无'}")
    with col3:
        st.write(f"当前评分：**{clean_score(lead['total_score'])}分** ({lead['lead_level']}级)"); st.caption(f"状态：{status_to_cn(lead['lead_status'])}")
    st.divider()
    state_key = f"manual_call_state_{lead_id}"
    note_key = f"manual_call_note_{lead_id}"
    if state_key not in st.session_state: st.session_state[state_key] = "idle"
    if note_key not in st.session_state: st.session_state[note_key] = ""
    state = st.session_state[state_key]
    if state == "idle":
        st.markdown("<div style='text-align:center; padding:30px;'><div style='font-size:50px;'>📞</div></div>", unsafe_allow_html=True)
        if st.button("🟢 开始通话", type="primary", use_container_width=True):
            st.session_state[state_key] = "calling"; st.rerun()
    elif state == "calling":
        st.markdown("<div style='text-align:center; padding:20px; background:#f0f7ff; border-radius:12px;'><div style='font-size:40px;'>🎙️</div><div style='font-size:20px; font-weight:bold; color:#1890ff;'>通话中...</div></div>", unsafe_allow_html=True)
        widget_key = f"manual_text_widget_{lead_id}"
        if widget_key not in st.session_state: st.session_state[widget_key] = st.session_state.get(note_key, "")
        current_widget_value = st.text_area("📝 通话记录/要点", key=widget_key, height=150)
        if widget_key in st.session_state: st.session_state[note_key] = st.session_state[widget_key]
        tag_cols = st.columns(4)
        quick_tags = [("💰 提及预算"," [客户提及预算] "),("🏍️ 意向车型"," [确认意向车型] "),("📅 预约到店"," [预约到店] "),("❌ 意向降低"," [意向降低] ")]
        for idx, (btn_label, tag_text) in enumerate(quick_tags):
            with tag_cols[idx]:
                if st.button(btn_label, key=f"mc_tag_{idx}_{lead_id}", use_container_width=True):
                    st.session_state[note_key] = current_widget_value + tag_text
                    if widget_key in st.session_state: del st.session_state[widget_key]
                    st.rerun()
        if st.button("🔴 挂断并AI分析", type="primary", use_container_width=True):
            if not current_widget_value.strip(): st.warning("请先记录通话内容再挂断")
            else: st.session_state[state_key] = "analyzing"; st.rerun()
    elif state == "analyzing":
        st.markdown("<div style='text-align:center; padding:20px;'><div style='font-size:40px;'>🧠</div><div style='font-size:18px; font-weight:bold; color:#1890ff;'>AI正在分析通话内容...</div></div>", unsafe_allow_html=True)
        with st.spinner("AI分析中..."):
            time.sleep(1.2)
            call_text = st.session_state[note_key]
            ai_info = extract_info_from_call(call_text, lead)
            new_score, new_level, new_is_high, new_tags, suggested_status, ai_summary = ai_analyze_call(call_text, lead)
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            db_exec("INSERT INTO call_record(lead_id,shop_id,call_duration,call_content,ai_analysis,score_after_call,level_after_call,create_time) VALUES(?,?,?,?,?,?,?,?)", (lead_id, shop_id, 0, call_text, ai_summary, new_score, new_level, now))
            st.session_state["_temp_manual_call"] = {"lead_id": lead_id, "shop_id": shop_id, "sale_id": sale_id, "new_score": new_score, "new_level": new_level, "new_is_high": new_is_high, "new_tags": new_tags, "suggested_status": suggested_status, "ai_summary": ai_summary, "call_text": call_text, "now": now, "ai_info": ai_info}
            st.session_state[state_key] = "confirm"; st.rerun()
    elif state == "confirm":
        temp = st.session_state.get("_temp_manual_call", {})
        if not temp: st.error("分析数据丢失"); return
        st.subheader("📋 AI 通话分析结果")
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.metric("新评分", f"{temp['new_score']}分")
        with c2: st.metric("新等级", temp['new_level'])
        with c3: st.metric("建议状态", STATUS_MAP.get(temp['suggested_status'], temp['suggested_status'] or '已建联'))
        with c4: st.metric("高价值", "是" if temp['new_is_high'] else "否")
        st.write(f"**AI摘要：** {temp['ai_summary']}")
        st.write(f"**新标签：** {temp['new_tags']}")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("❌ 放弃", use_container_width=True):
                for k in [state_key, note_key, "_temp_manual_call"]:
                    if k in st.session_state: del st.session_state[k]
                open_key = f"mcall_open_{lead_id}"
                if open_key in st.session_state: del st.session_state[open_key]
                st.rerun()
        with col_b:
            if st.button("✅ 确认更新线索", type="primary", use_container_width=True):
                status_code = temp['suggested_status'] if temp['suggested_status'] else 'contacted'
                db_exec("UPDATE customer_leads SET total_score=?,lead_level=?,is_high_value=?,user_tags=?,lead_status=?,first_contact_time=COALESCE(first_contact_time,?),latest_source_time=?,consult_content=COALESCE(consult_content,'')||? WHERE id=?", (temp['new_score'], temp['new_level'], temp['new_is_high'], temp['new_tags'], status_code, temp['now'], temp['now'], f"\n[手动外呼]{temp['call_text'][:200]}...", temp['lead_id']))
                follow_content = f"手动外呼 | 意向:{temp['ai_info'].get('intent_level','中')} | 建议:{temp['ai_info'].get('recommended_action','继续跟进')}"
                db_exec("INSERT INTO lead_follow_record(lead_id,sale_id,follow_type,follow_content,ai_summary,create_time) VALUES(?,?,?,?,?,?)", (temp['lead_id'], temp['sale_id'], "手动外呼", follow_content, temp['ai_summary'], temp['now']))
                for k in [state_key, note_key, "_temp_manual_call"]:
                    if k in st.session_state: del st.session_state[k]
                open_key = f"mcall_open_{lead_id}"
                if open_key in st.session_state: del st.session_state[open_key]
                st.success("✅ 手动外呼闭环完成！线索已更新")
                time.sleep(1); st.rerun()

def dialog_dial_new(shop_id, sale_id):
    """手动拨号：输入手机号，可为新线索或更新已有线索"""
    st.subheader("📱 手动拨号中心")
    dial_state_key = "dial_new_state"
    dial_note_key = "dial_new_note"
    # FIX: 仅在键不存在时初始化（原代码每次rerun强制重置为idle导致通话流程中断）
    if dial_state_key not in st.session_state: st.session_state[dial_state_key] = "idle"
    if dial_note_key not in st.session_state: st.session_state[dial_note_key] = ""
    state = st.session_state[dial_state_key]
    col1, col2 = st.columns(2)
    with col1: phone = st.text_input("📱 手机号 *", placeholder="输入11位手机号", key="dial_phone")
    with col2: name = st.text_input("👤 客户姓名", placeholder="可选，新客户建议填写", key="dial_name")
    col3, col4 = st.columns(2)
    with col3: city = st.text_input("📍 城市", placeholder="可选", key="dial_city")
    with col4: budget = st.text_input("💰 预算", placeholder="可选", key="dial_budget")
    existing = None
    if phone and len(str(phone).strip()) >= 7:
        exist_df = db_query("SELECT * FROM customer_leads WHERE phone=?", (str(phone).strip(),))
        if len(exist_df) > 0:
            existing = exist_df.iloc[0]
            st.info(f"📌 该号码已有线索档案：{existing['customer_name'] or '未命名'} | {existing['city'] or '未知'} | 当前评分{clean_score(existing['total_score'])}分 | 状态：{status_to_cn(existing['lead_status'])}")
    st.divider()
    if state == "idle":
        st.markdown("<div style='text-align:center; padding:30px;'><div style='font-size:50px;'>📞</div></div>", unsafe_allow_html=True)
        if st.button("🟢 开始拨号", type="primary", use_container_width=True):
            phone_clean = str(phone).strip() if phone else ""
            if not phone_clean or len(phone_clean) < 7: st.error("请输入有效的手机号")
            else: st.session_state[dial_state_key] = "calling"; st.rerun()
    elif state == "calling":
        st.markdown("<div style='text-align:center; padding:20px; background:#f0f7ff; border-radius:12px;'><div style='font-size:40px;'>🎙️</div><div style='font-size:20px; font-weight:bold; color:#1890ff;'>通话中...</div></div>", unsafe_allow_html=True)
        dial_widget_key = "dial_note_widget"
        if dial_widget_key not in st.session_state: st.session_state[dial_widget_key] = st.session_state.get(dial_note_key, "")
        dial_current_value = st.text_area("📝 通话记录", placeholder="记录本次通话要点...", key=dial_widget_key, height=150)
        if dial_widget_key in st.session_state: st.session_state[dial_note_key] = st.session_state[dial_widget_key]
        tag_cols = st.columns(4)
        quick_tags = [("💰 提及预算"," [客户提及预算] "),("🏍️ 意向车型"," [确认意向车型] "),("📅 预约到店"," [预约到店] "),("❌ 意向降低"," [意向降低] ")]
        for idx, (btn_label, tag_text) in enumerate(quick_tags):
            with tag_cols[idx]:
                if st.button(btn_label, key=f"dial_t{idx}", use_container_width=True):
                    st.session_state[dial_note_key] = dial_current_value + tag_text
                    if dial_widget_key in st.session_state: del st.session_state[dial_widget_key]
                    st.rerun()
        if st.button("🔴 挂断并AI分析", type="primary", use_container_width=True):
            phone_clean = str(phone).strip() if phone else ""
            if not phone_clean or len(phone_clean) < 7: st.error("请输入有效的手机号"); return
            call_text = dial_current_value
            with st.spinner("AI正在分析通话内容..."):
                time.sleep(1.2)
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if existing is not None:
                    lead = existing
                    ai_info = extract_info_from_call(call_text, lead)
                    new_score, new_level, new_is_high, new_tags, suggested_status, ai_summary = ai_analyze_call(call_text, lead)
                    db_exec("INSERT INTO call_record(lead_id,shop_id,call_duration,call_content,ai_analysis,score_after_call,level_after_call,create_time) VALUES(?,?,?,?,?,?,?,?)", (lead['id'], shop_id, 0, call_text, ai_summary, new_score, new_level, now))
                    status_code = suggested_status if suggested_status else 'contacted'
                    db_exec("UPDATE customer_leads SET customer_name=COALESCE(?,customer_name),city=COALESCE(?,city),budget=COALESCE(?,budget),total_score=?,lead_level=?,is_high_value=?,user_tags=?,lead_status=?,first_contact_time=COALESCE(first_contact_time,?),latest_source_time=?,consult_content=COALESCE(consult_content,'')||? WHERE id=?", (name or None, city or None, budget or None, new_score, new_level, new_is_high, new_tags, status_code, now, now, f"\n[手动拨号]{call_text[:200]}...", lead['id']))
                    follow_content = f"手动拨号外呼 | 意向:{ai_info.get('intent_level','中')} | 建议:{ai_info.get('recommended_action','继续跟进')}"
                    db_exec("INSERT INTO lead_follow_record(lead_id,sale_id,follow_type,follow_content,ai_summary,create_time) VALUES(?,?,?,?,?,?)", (lead['id'], sale_id, "手动拨号", follow_content, ai_summary, now))
                    st.success(f"✅ 已有线索 #{lead['id']} 已更新！")
                else:
                    channel_df = db_query("SELECT id,weight FROM channel_dict WHERE channel_name='批量导入'")
                    if len(channel_df) == 0: channel_id, ch_weight = 7, 10
                    else: channel_id, ch_weight = int(channel_df.iloc[0]['id']), int(channel_df.iloc[0]['weight'])
                    full = bool(phone_clean and name and city and len(str(name))>=1 and len(str(city))>=1)
                    consult = call_text if call_text.strip() else "手动拨号获客"
                    score, level, high_val = calculate_lead_score(ch_weight, full, consult, source_time=now)
                    tags = ai_generate_tags(consult, budget, city)
                    db_exec('INSERT INTO customer_leads(phone,customer_name,city,budget,channel_id,consult_content,source_time,latest_source_time,total_score,lead_level,is_high_value,user_tags,lead_status,assign_shop_id,assign_sale_id,assign_time) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (phone_clean, name, city, budget, channel_id, consult, now, now, int(score), level, int(high_val), tags, 'untouch', shop_id, sale_id, now))
                    new_lead = db_query("SELECT id FROM customer_leads WHERE phone=? ORDER BY id DESC LIMIT 1", (phone_clean,))
                    if len(new_lead) > 0:
                        new_lead_id = int(new_lead.iloc[0]['id'])
                        db_exec("INSERT INTO call_record(lead_id,shop_id,call_duration,call_content,ai_analysis,score_after_call,level_after_call,create_time) VALUES(?,?,?,?,?,?,?,?)", (new_lead_id, shop_id, 0, call_text, f"手动拨号创建新线索 | 评分:{score} | 等级:{level}", score, level, now))
                        st.success(f"✅ 新线索 #{new_lead_id} 已创建并分配至本店！")
                for k in ["dial_phone", "dial_name", "dial_city", "dial_budget", dial_widget_key, dial_note_key, dial_state_key]:
                    if k in st.session_state: del st.session_state[k]
                time.sleep(1.5); st.rerun()

@st.dialog('➕ 手动新增线索')
def dialog_add_lead():
    channels = db_query('SELECT id,channel_name,weight FROM channel_dict')
    models = db_query('SELECT id,model_name FROM motorcycle_model')
    phone = st.text_input('手机号*')
    name = st.text_input('客户姓名')
    city = st.text_input('所在城市')
    budget = st.text_input('购车预算')
    ch = st.selectbox('来源渠道', channels['channel_name'])
    m = st.selectbox('意向车型', models['model_name'])
    content = st.text_area('客户咨询内容')
    col1,col2 = st.columns(2)
    with col1:
        if st.button('取消'): st.rerun()
    with col2:
        if st.button('提交并AI评级', type='primary'):
            if not phone.strip(): st.error('手机号不能为空'); return
            ch_row = channels[channels['channel_name']==ch].iloc[0]
            m_row = models[models['model_name']==m].iloc[0]
            full = bool(phone and name and city and len(str(phone))>=7 and len(str(name))>=1 and len(str(city))>=1)
            now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            score, level, high_val = calculate_lead_score(int(ch_row['weight']), full, content, source_time=now_str)
            tags = ai_generate_tags(content, budget, city)
            if db_exec('INSERT INTO customer_leads(phone,customer_name,city,budget,model_id,channel_id,consult_content,source_time,latest_source_time,total_score,lead_level,is_high_value,user_tags,lead_status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (phone,name,city,budget,int(m_row['id']),int(ch_row['id']),content,now_str,now_str,int(score),level,int(high_val),tags,'untouch')):
                st.success('录入成功！'); st.rerun()
            else: st.error('录入失败，手机号可能已存在')

@st.dialog('批量导入线索')
def dialog_import_lead():
    st.caption('支持.xlsx格式，模板包含字段：手机号、客户姓名、城市、预算、意向车型、咨询内容')
    st.download_button('📥 下载导入模板', data=get_excel_template(), file_name='线索导入模板.xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', use_container_width=True)
    st.divider()
    upload_file = st.file_uploader('上传填写好的Excel文件', type=['xlsx'])
    if upload_file:
        df = pd.read_excel(upload_file, dtype={'手机号': str})
        required_cols = ['手机号','客户姓名','城市','预算','意向车型','咨询内容']
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            # FIX: 正确缩进到 if 块内（原代码缩进错误导致 IndentationError）
            st.error(f"导入文件缺少必要列：{', '.join(missing)}，请下载模板并按要求填写。")
        else:
            st.write('数据预览：')
            st.dataframe(df.head(), use_container_width=True)
            if st.button('确认导入并AI批量评级', type='primary'):
                channels = db_query("SELECT id,weight FROM channel_dict WHERE channel_name='批量导入'")
                if len(channels) == 0: st.error('批量导入渠道未配置'); return
                channels = channels.iloc[0]
                models = db_query('SELECT id,model_name FROM motorcycle_model')
                success = 0; fail = 0
                now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                for _, row in df.iterrows():
                    try:
                        phone = str(row['手机号']).strip()
                        if '.' in phone: phone = phone.split('.')[0]
                        phone = phone.replace('+','').replace(' ','')
                        name = str(row.get('客户姓名',''))
                        city = str(row.get('城市',''))
                        budget = str(row.get('预算',''))
                        model_name = str(row.get('意向车型',''))
                        content = str(row.get('咨询内容',''))
                        model_match = models[models['model_name']==model_name]
                        model_id = int(model_match['id'].iloc[0]) if len(model_match)>0 else 1
                        full = bool(phone and name and city and len(str(phone))>=7 and len(str(name))>=1 and len(str(city))>=1)
                        score, level, high_val = calculate_lead_score(int(channels['weight']), full, content, source_time=now_str)
                        tags = ai_generate_tags(content, budget, city)
                        if db_exec('INSERT INTO customer_leads(phone,customer_name,city,budget,model_id,channel_id,consult_content,source_time,latest_source_time,total_score,lead_level,is_high_value,user_tags,lead_status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (phone,name,city,budget,model_id,int(channels['id']),content,now_str,now_str,int(score),level,int(high_val),tags,'untouch')):
                            success += 1
                        else: fail += 1
                    except Exception as e:
                        st.warning(f'导入单条失败: {e}'); fail += 1
                st.success(f'导入完成：成功{success}条，失败{fail}条')
                st.rerun()

# ========================== AI 采集日志弹窗 ==========================
@st.dialog('📋 AI 采集日志')
def dialog_ai_log():
    logs = st.session_state.get('ai_crawl_log', [])
    if not logs:
        st.info('暂无采集日志，请先启动 AI 采集。')
        return

    # 显示最近 100 条，最新的排最前
    rows = list(reversed(logs[-100:]))
    html = '<table style="width:100%;border-collapse:collapse;font-size:13px;">'
    html += '<thead><tr style="background:#f7f8fa;color:#666;font-weight:500;">'
    for h in ['时间', '平台', '类型', 'AI评分', '等级', '置信度', '状态']:
        html += f'<th style="padding:10px 8px;text-align:left;border-bottom:1px solid #eee;">{h}</th>'
    html += '</tr></thead><tbody>'

    LEVEL_STYLES = {
        'A级': ('#f6ffed', '#52c41a'),
        'B级': ('#e6f7ff', '#1890ff'),
        'C级': ('#fff7e6', '#fa8c16'),
        'D级': ('#fff2f0', '#ff4d4f'),
    }
    for r in rows:
        t_str = r.get('time', '')
        try:
            dt = datetime.datetime.strptime(t_str, '%Y-%m-%d %H:%M:%S')
            t_disp = dt.strftime('%m/%d<br>%H:%M')
        except:
            t_disp = t_str[:16]

        level = r.get('level', '')
        bg, fg = LEVEL_STYLES.get(level, ('#f5f5f5', '#999'))
        status_color = '#52c41a' if r.get('status') == '成功' else '#ff4d4f'

        html += '<tr style="border-bottom:1px solid #f0f0f0;">'
        html += f'<td style="padding:10px 8px;color:#666;">{t_disp}</td>'
        html += f'<td style="padding:10px 8px;">{r.get("platform", "")}</td>'
        html += f'<td style="padding:10px 8px;color:#666;">{r.get("type", "")}</td>'
        html += f'<td style="padding:10px 8px;">{r.get("score", "")}</td>'
        html += f'<td style="padding:10px 8px;"><span style="background:{bg};color:{fg};padding:2px 8px;border-radius:4px;font-size:12px;">{level}</span></td>'
        html += f'<td style="padding:10px 8px;">{r.get("confidence", "")}</td>'
        html += f'<td style="padding:10px 8px;color:{status_color};">{r.get("status", "")}</td>'
        html += '</tr>'
    html += '</tbody></table>'
    st.markdown(html, unsafe_allow_html=True)

# ========================== 自动任务 ==========================
@st.fragment(run_every=60)
def auto_task_fragment():
    now_time = datetime.datetime.now()
    if 'last_auto_crawl_time' not in st.session_state:
        st.session_state['last_auto_crawl_time'] = now_time - datetime.timedelta(seconds=60)
    if 'last_auto_run' not in st.session_state:
        st.session_state['last_auto_run'] = '即将执行'
        st.session_state['last_crawl_num'] = 0
        st.session_state['last_dist_num'] = 0
    if (now_time - st.session_state['last_auto_crawl_time']).total_seconds() >= 60:
        crawl_num, results = auto_crawl_leads()
        dist_num = execute_distribute()
        if 'ai_crawl_log' not in st.session_state:
            st.session_state['ai_crawl_log'] = []
        st.session_state['ai_crawl_log'].extend(results)
        if len(st.session_state['ai_crawl_log']) > 200:
            st.session_state['ai_crawl_log'] = st.session_state['ai_crawl_log'][-200:]
        _update_daily_stats()
        st.session_state['last_auto_run'] = now_time.strftime('%Y-%m-%d %H:%M:%S')
        st.session_state['last_crawl_num'] = crawl_num
        st.session_state['last_dist_num'] = dist_num
        st.session_state['last_auto_crawl_time'] = now_time
    countdown_html = f"""<div style='font-size:15px;line-height:1.8'><div style='color:#389e0d;font-weight:bold'>🤖 自动演示模式运行中</div><div>上次执行时间：{st.session_state['last_auto_run']}</div><div>上次新增线索：<b>{st.session_state['last_crawl_num']}</b> 条 | 自动分发：<b>{st.session_state['last_dist_num']}</b> 条</div><div>距离下次自动执行：<span id='autoCountdown' style='color:#d46b08;font-weight:bold'>60</span> 秒</div></div><script>let seconds=60;setInterval(()=>{{seconds--;if(seconds<0)seconds=60;document.getElementById('autoCountdown').innerText=seconds;}},1000);</script>"""
    st.components.v1.html(countdown_html, height=120)

def render_geo_map():
    """渲染中国地域分布图"""
    city_data = db_query("SELECT city, COUNT(*) as cnt FROM customer_leads GROUP BY city")

    _CITY_TO_PROVINCE = {
        '北京': '北京', '天津': '天津', '上海': '上海', '重庆': '重庆',
        '香港': '香港', '澳门': '澳门', '台湾': '台湾',
        '石家庄': '河北', '唐山': '河北', '秦皇岛': '河北', '邯郸': '河北', '邢台': '河北',
        '保定': '河北', '张家口': '河北', '承德': '河北', '沧州': '河北', '廊坊': '河北', '衡水': '河北',
        '太原': '山西', '大同': '山西', '阳泉': '山西', '长治': '山西', '晋城': '山西',
        '朔州': '山西', '晋中': '山西', '运城': '山西', '忻州': '山西', '临汾': '山西', '吕梁': '山西',
        '呼和浩特': '内蒙古',
        '沈阳': '辽宁', '大连': '辽宁', '鞍山': '辽宁', '抚顺': '辽宁', '本溪': '辽宁',
        '丹东': '辽宁', '锦州': '辽宁', '营口': '辽宁', '阜新': '辽宁', '辽阳': '辽宁',
        '盘锦': '辽宁', '铁岭': '辽宁', '朝阳': '辽宁', '葫芦岛': '辽宁',
        '长春': '吉林', '吉林': '吉林', '四平': '吉林', '辽源': '吉林', '通化': '吉林',
        '白山': '吉林', '松原': '吉林', '白城': '吉林', '延边': '吉林',
        '哈尔滨': '黑龙江', '齐齐哈尔': '黑龙江', '鸡西': '黑龙江', '鹤岗': '黑龙江', '双鸭山': '黑龙江',
        '大庆': '黑龙江', '伊春': '黑龙江', '佳木斯': '黑龙江', '七台河': '黑龙江', '牡丹江': '黑龙江',
        '黑河': '黑龙江', '绥化': '黑龙江', '大兴安岭': '黑龙江',
        '南京': '江苏', '无锡': '江苏', '徐州': '江苏', '常州': '江苏', '苏州': '江苏',
        '南通': '江苏', '连云港': '江苏', '淮安': '江苏', '盐城': '江苏', '扬州': '江苏',
        '镇江': '江苏', '泰州': '江苏', '宿迁': '江苏',
        '杭州': '浙江', '宁波': '浙江', '温州': '浙江', '嘉兴': '浙江', '湖州': '浙江',
        '绍兴': '浙江', '金华': '浙江', '衢州': '浙江', '舟山': '浙江', '台州': '浙江', '丽水': '浙江',
        '合肥': '安徽', '芜湖': '安徽', '蚌埠': '安徽', '淮南': '安徽', '马鞍山': '安徽',
        '淮北': '安徽', '铜陵': '安徽', '安庆': '安徽', '黄山': '安徽', '滁州': '安徽',
        '阜阳': '安徽', '宿州': '安徽', '六安': '安徽', '亳州': '安徽', '池州': '安徽', '宣城': '安徽',
        '福州': '福建', '厦门': '福建', '莆田': '福建', '三明': '福建', '泉州': '福建',
        '漳州': '福建', '南平': '福建', '龙岩': '福建', '宁德': '福建',
        '南昌': '江西', '景德镇': '江西', '萍乡': '江西', '九江': '江西', '新余': '江西',
        '鹰潭': '江西', '赣州': '江西', '吉安': '江西', '宜春': '江西', '抚州': '江西', '上饶': '江西',
        '济南': '山东', '青岛': '山东', '淄博': '山东', '枣庄': '山东', '东营': '山东',
        '烟台': '山东', '潍坊': '山东', '济宁': '山东', '泰安': '山东', '威海': '山东',
        '日照': '山东', '莱芜': '山东', '临沂': '山东', '德州': '山东', '聊城': '山东',
        '滨州': '山东', '菏泽': '山东',
        '郑州': '河南', '开封': '河南', '洛阳': '河南', '平顶山': '河南', '安阳': '河南',
        '鹤壁': '河南', '新乡': '河南', '焦作': '河南', '濮阳': '河南', '许昌': '河南',
        '漯河': '河南', '三门峡': '河南', '南阳': '河南', '商丘': '河南', '信阳': '河南',
        '周口': '河南', '驻马店': '河南', '济源': '河南',
        '武汉': '湖北', '黄石': '湖北', '十堰': '湖北', '宜昌': '湖北', '襄阳': '湖北',
        '鄂州': '湖北', '荆门': '湖北', '孝感': '湖北', '黄冈': '湖北', '咸宁': '湖北',
        '随州': '湖北', '恩施': '湖北', '仙桃': '湖北', '潜江': '湖北', '天门': '湖北', '神农架': '湖北',
        '长沙': '湖南', '株洲': '湖南', '湘潭': '湖南', '衡阳': '湖南', '邵阳': '湖南',
        '岳阳': '湖南', '常德': '湖南', '张家界': '湖南', '益阳': '湖南', '郴州': '湖南',
        '永州': '湖南', '怀化': '湖南', '娄底': '湖南', '湘西': '湖南',
        '广州': '广东', '韶关': '广东', '深圳': '广东', '珠海': '广东', '汕头': '广东',
        '佛山': '广东', '江门': '广东', '湛江': '广东', '茂名': '广东', '肇庆': '广东',
        '惠州': '广东', '梅州': '广东', '汕尾': '广东', '河源': '广东', '阳江': '广东',
        '清远': '广东', '东莞': '广东', '中山': '广东', '潮州': '广东', '揭阳': '广东', '云浮': '广东',
        '南宁': '广西', '柳州': '广西', '桂林': '广西', '梧州': '广西', '北海': '广西',
        '防城港': '广西', '钦州': '广西', '贵港': '广西', '玉林': '广西', '百色': '广西',
        '贺州': '广西', '河池': '广西', '来宾': '广西', '崇左': '广西',
        '海口': '海南', '三亚': '海南', '三沙': '海南', '儋州': '海南', '五指山': '海南',
        '琼海': '海南', '文昌': '海南', '万宁': '海南', '东方': '海南', '定安': '海南',
        '屯昌': '海南', '澄迈': '海南', '临高': '海南', '白沙': '海南', '昌江': '海南',
        '乐东': '海南', '陵水': '海南', '保亭': '海南', '琼中': '海南',
        '成都': '四川', '自贡': '四川', '攀枝花': '四川', '泸州': '四川', '德阳': '四川',
        '绵阳': '四川', '广元': '四川', '遂宁': '四川', '内江': '四川', '乐山': '四川',
        '南充': '四川', '眉山': '四川', '宜宾': '四川', '广安': '四川', '达州': '四川',
        '雅安': '四川', '巴中': '四川', '资阳': '四川', '阿坝': '四川', '甘孜': '四川', '凉山': '四川',
        '贵阳': '贵州', '六盘水': '贵州', '遵义': '贵州', '安顺': '贵州', '毕节': '贵州',
        '铜仁': '贵州', '黔西南': '贵州', '黔东南': '贵州', '黔南': '贵州',
        '昆明': '云南', '曲靖': '云南', '玉溪': '云南', '保山': '云南', '昭通': '云南',
        '丽江': '云南', '普洱': '云南', '临沧': '云南', '楚雄': '云南', '红河': '云南',
        '文山': '云南', '西双版纳': '云南', '大理': '云南', '德宏': '云南', '怒江': '云南', '迪庆': '云南',
        '拉萨': '西藏', '日喀则': '西藏', '昌都': '西藏', '林芝': '西藏', '山南': '西藏',
        '那曲': '西藏', '阿里': '西藏',
        '西安': '陕西', '铜川': '陕西', '宝鸡': '陕西', '咸阳': '陕西', '渭南': '陕西',
        '延安': '陕西', '汉中': '陕西', '榆林': '陕西', '安康': '陕西', '商洛': '陕西',
        '兰州': '甘肃', '嘉峪关': '甘肃', '金昌': '甘肃', '白银': '甘肃', '天水': '甘肃',
        '武威': '甘肃', '张掖': '甘肃', '平凉': '甘肃', '酒泉': '甘肃', '庆阳': '甘肃',
        '定西': '甘肃', '陇南': '甘肃', '临夏': '甘肃', '甘南': '甘肃',
        '西宁': '青海', '海东': '青海', '海北': '青海', '黄南': '青海', '海南': '青海',
        '果洛': '青海', '玉树': '青海', '海西': '青海',
        '银川': '宁夏', '石嘴山': '宁夏', '吴忠': '宁夏', '固原': '宁夏', '中卫': '宁夏',
        '乌鲁木齐': '新疆', '克拉玛依': '新疆', '吐鲁番': '新疆', '哈密': '新疆', '昌吉': '新疆',
        '博尔塔拉': '新疆', '巴音郭楞': '新疆', '阿克苏': '新疆', '克孜勒苏': '新疆', '喀什': '新疆',
        '和田': '新疆', '伊犁': '新疆', '塔城': '新疆', '阿勒泰': '新疆', '石河子': '新疆',
        '阿拉尔': '新疆', '图木舒克': '新疆', '五家渠': '新疆', '北屯': '新疆', '铁门关': '新疆',
        '双河': '新疆', '可克达拉': '新疆', '昆玉': '新疆', '胡杨河': '新疆', '新星': '新疆',
    }

    prov_counts = {}
    for _, row in city_data.iterrows():
        prov = _CITY_TO_PROVINCE.get(row['city'], None)
        if prov:
            prov_counts[prov] = prov_counts.get(prov, 0) + int(row['cnt'])

    if not prov_counts:
        st.info('暂无线索地域数据'); return

    try:
        from pyecharts.charts import Map
        from pyecharts import options as opts
        import streamlit.components.v1 as components

        data = list(prov_counts.items())
        max_val = max(v for _, v in data) if data else 100

        map_chart = (
            Map()
            .add("线索数量", data, "china", is_map_symbol_show=False)
            .set_global_opts(
                title_opts=opts.TitleOpts(
                    title="各省份线索分布",
                    title_textstyle_opts=opts.TextStyleOpts(font_size=14, color="#333")
                ),
                visualmap_opts=opts.VisualMapOpts(
                    max_=max_val,
                    pos_left="left",
                    pos_bottom="bottom",
                    range_color=["#e0f3f8", "#abd9e9", "#74add1", "#4575b4", "#313695"],
                ),
                tooltip_opts=opts.TooltipOpts(formatter="{b}: {c}条"),
            )
        )
        components.html(map_chart.render_embed(), height=500)
    except Exception:
        df = pd.DataFrame(list(prov_counts.items()), columns=['省份', '数量']).sort_values('数量', ascending=False)
        st.bar_chart(df.set_index('省份')['数量'])

# ========================== 实时数据大屏 ==========================
def real_time_dashboard(start_t, end_t):
    stats = get_today_stats()
    if not stats:
        st.warning('暂无线索数据，请先导入或生成线索'); return
    yoy_mom = calculate_yoy_mom()

    # ====== 页头：标题左 / Logo 右 ======
    c_title, c_logo = st.columns([5, 1])
    with c_title:
        st.markdown('### 实时数据大屏')
    with c_logo:
        st.markdown('''
        <div style="text-align:right;">
            <svg width="48" height="32" viewBox="0 0 56 36">
                <path d="M28 2 C14 2,4 12,4 22 C4 28,8 30,14 30 L28 20 L42 30 C48 30,52 28,52 22 C52 12,42 2,28 2 Z" fill="#c41c23"/>
                <path d="M28 8 L20 16 L28 12 L36 16 Z" fill="#fff" opacity="0.3"/>
            </svg>
        </div>
        ''', unsafe_allow_html=True)

    # ====== 核心指标 ======
    c1, c2, c3, c4 = st.columns(4)
    c1.metric('总线索', stats['total'], delta=f"{yoy_mom.get('total_leads', {}).get('day_change', 0):+}%")
    c2.metric('今日新增', stats['today_new'], delta=f"{yoy_mom.get('new_leads', {}).get('day_change', 0):+}%")
    c3.metric('高价值', stats['high'], delta=f"{yoy_mom.get('high_value_leads', {}).get('day_change', 0):+}%")
    c4.metric('已成交', stats['deal'], delta=f"{yoy_mom.get('deal_leads', {}).get('day_change', 0):+}%")

    st.divider()

    # ====== 趋势 + 渠道 ======
    col1, col2 = st.columns(2)
    with col1:
        st.caption('近30天趋势')
        hist_df = get_historical_stats(30)
        if len(hist_df) > 0 and USE_PLOTLY:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=hist_df['date'], y=hist_df['total_leads'],
                mode='lines', name='总线索', line=dict(color='#c41c23', width=1.5)))
            fig.add_trace(go.Scatter(x=hist_df['date'], y=hist_df['new_leads'],
                mode='lines', name='新增', line=dict(color='#1890ff', width=1.5)))
            fig.add_trace(go.Scatter(x=hist_df['date'], y=hist_df['deal_leads'],
                mode='lines', name='成交', line=dict(color='#52c41a', width=1.5)))
            fig.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10),
                legend=dict(orientation='h', y=1.05), plot_bgcolor='#fafafa')
            _plot(fig)
        elif len(hist_df) > 0:
            st.line_chart(hist_df.set_index('date')[['total_leads', 'new_leads', 'deal_leads']])

    with col2:
        st.caption('渠道分布')
        channel_data = db_query("""SELECT c.channel_name, COUNT(*) as cnt
            FROM customer_leads l JOIN channel_dict c ON l.channel_id = c.id
            GROUP BY c.channel_name ORDER BY cnt DESC""")
        if len(channel_data) > 0 and USE_PLOTLY:
            fig = go.Figure(data=[go.Pie(labels=channel_data['channel_name'],
                values=channel_data['cnt'], hole=0.5,
                marker_colors=['#c41c23', '#e8474b', '#f09595', '#f7cccc',
                               '#999', '#bbb', '#ddd'],
                textinfo='label+percent', textfont_size=11)])
            fig.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10))
            _plot(fig)
        elif len(channel_data) > 0:
            st.bar_chart(channel_data.set_index('channel_name')['cnt'])

    st.divider()

    # ====== 表格区：线索等级 + 健康度 + 最新线索 ======
    col_a, col_b, col_c = st.columns([1, 1, 2])
    with col_a:
        st.caption('线索等级')
        level_data = pd.DataFrame({
            '等级': ['A', 'B', 'C', 'D'],
            '数量': [stats['a'], stats['b'], stats['c'], stats['d']]
        })
        if USE_PLOTLY:
            fig = go.Figure(data=[go.Bar(x=level_data['等级'], y=level_data['数量'],
                marker_color=['#c41c23', '#1890ff', '#faad14', '#999'],
                text=level_data['数量'], textposition='outside')])
            fig.update_layout(height=220, margin=dict(l=10, r=10, t=10, b=10),
                plot_bgcolor='#fafafa', yaxis_title='')
            _plot(fig)
        else:
            st.bar_chart(level_data.set_index('等级')['数量'])

    with col_b:
        st.caption('健康指标')
        total = max(stats['total'], 1)
        health = [
            ('建联率', round(stats['contacted'] / total * 100, 1), '80%'),
            ('成交率', round(stats['deal'] / total * 100, 1), '15%'),
            ('流失率', round(stats['lost'] / total * 100, 1), '<10%'),
        ]
        for label, val, target in health:
            c = '#52c41a' if val >= (int(target.strip('%<>')) * 0.8) else '#faad14' if val >= (int(target.strip('%<>')) * 0.5) else '#c41c23'
            st.markdown(f'{label} <span style="color:{c};font-weight:bold;float:right">{val}%</span> / <span style="color:#999">{target}</span>', unsafe_allow_html=True)

    with col_c:
        st.caption('最新线索')
        recent = db_query("""SELECT l.customer_name, l.city, l.total_score,
            l.lead_level, c.channel_name, l.source_time
            FROM customer_leads l LEFT JOIN channel_dict c ON l.channel_id = c.id
            ORDER BY l.source_time DESC LIMIT 8""")
        if len(recent) > 0:
            recent = clean_score_column(recent)
            recent['时间'] = recent['source_time'].astype(str).str[:10]
            display = recent[['customer_name', 'city', 'channel_name', 'lead_level', 'total_score', '时间']]
            display.columns = ['姓名', '城市', '渠道', '等级', '评分', '时间']
            st.dataframe(display, use_container_width=True, hide_index=True, height=240)
        else:
            st.info('暂无')

# ========================== 销售漏斗看板 ==========================
def render_funnel_dashboard(viewer_type='admin'):
    """渲染销售漏斗看板（工厂端/商家端通用）"""
    st.header('🔻 销售漏斗看板')

    start_t, end_t = render_time_filter('funnel')

    leads = db_query("SELECT * FROM customer_leads WHERE source_time BETWEEN ? AND ?", (start_t, end_t))
    leads = clean_score_column(leads)

    if len(leads) == 0:
        st.warning('本周期暂无线索数据，漏斗为空')
        return

    funnel = calculate_funnel_stats(leads)
    funnel_rates = funnel.get('conversion_rates', {})
    overall_conv = funnel_rates.get('overall', 0)

    # ========== 顶部：漏斗各层级概览 ==========
    st.markdown('<div class="dashboard-section">', unsafe_allow_html=True)
    st.subheader('📊 漏斗层级概览')

    n = len(FUNNEL_STAGES)
    cols = st.columns(n + 2)  # 层级 + 各阶段 + 总线索
    with cols[0]:
        st.caption('层级')
    for i, stage in enumerate(FUNNEL_STAGES):
        with cols[i + 1]:
            count = funnel[stage]['count']
            pct_of_total = funnel_rates.get(f'stage_{i}', {}).get('of_total', 0)
            st.metric(FUNNEL_NAMES[i], f'{count}条 ({pct_of_total}%)')

    with cols[n + 1]:
        st.metric('总线索', f'{funnel["total"]}条')

    # ========== 转化率箭头展示 ==========
    col_rates = st.columns(len(FUNNEL_STAGES) - 1)
    for i in range(len(FUNNEL_STAGES) - 1):
        next_rate = funnel_rates.get(f'stage_{i+1}', {}).get('from_prev', 0)
        with col_rates[i]:
            if i == 0:
                st.caption(f'{FUNNEL_NAMES[i]} -> {FUNNEL_NAMES[i+1]}')
                st.markdown(f'<div style="font-size:20px;font-weight:bold;color:#52c41a;">{next_rate}%</div>', unsafe_allow_html=True)
            else:
                st.caption(f'{FUNNEL_NAMES[i]} -> {FUNNEL_NAMES[i+1]}')
                color = '#52c41a' if next_rate >= 30 else ('#faad14' if next_rate >= 15 else '#ff4d4f')
                st.markdown(f'<div style="font-size:20px;font-weight:bold;color:{color};">{next_rate}%</div>', unsafe_allow_html=True)

    # 整体转化率卡片
    st.markdown('<div style="background:#f0f7ff;border-radius:8px;padding:16px;text-align:center;margin:16px 0;border:1px solid #91d5ff;">', unsafe_allow_html=True)
    st.markdown(f'<div style="font-size:14px;color:#666;">整体转化率（待跟进->已成交）</div><div style="font-size:32px;font-weight:bold;color:#1890ff;">{overall_conv}%</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>')

    # ========== 中部：漏斗趋势 + 渠道分析 ==========
    st.subheader('📈 漏斗趋势分析')
    tab1, tab2 = st.tabs(['30天趋势', '渠道分解'])

    with tab1:
        trend_data = funnel.get('trend_30d', [])
        if len(trend_data) > 1:
            dates = [t.get('date', '') for t in trend_data]
            fig = make_subplots(rows=2, cols=1, specs=[[{"secondary_y": True}], [{}]],
                                subplot_titles=['各阶段数量趋势', '转化率趋势'],
                                row_heights=[0.55, 0.45])
            colors = ['#52c41a', '#1890ff', '#faad14', '#722ed1', '#389e0d', '#ff4d4f']
            for idx, stage in enumerate(FUNNEL_STAGES):
                values = [t.get(stage, 0) for t in trend_data]
                fig.add_trace(go.Scatter(x=dates, y=values, mode='lines+markers', name=FUNNEL_NAMES[idx],
                                        line=dict(color=colors[idx], width=2)), row=1, col=1)
            fig.update_layout(height=500, showlegend=True, legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1))
            fig.update_xaxes(title_text='日期', row=2, col=1)
            fig.update_yaxes(title_text='线索数', row=1, col=1)
            st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': False, 'displayModeBar': False})
        else:
            st.info('数据不足，无法生成趋势图（至少需要2天数据）')

    with tab2:
        channel_funnels = get_funnel_channel_breakdown(start_t, end_t)
        if len(channel_funnels) > 0:
            ch_display = pd.DataFrame(channel_funnels)
            ch_display['转化率'] = ch_display.apply(lambda r: round(r['deal'] / r['untouch'] * 100, 2) if r['untouch'] > 0 else 0, axis=1)
            st.dataframe(
                ch_display[['channel', 'untouch', 'contacted', 'reserve_test', 'bargain', 'deal', 'lost', '转化率']],
                use_container_width=True,
                hide_index=True
            )
            # 渠道漏斗柱状图
            if USE_PLOTLY:
                fig = go.Figure()
                colors_stages = ['#52c41a', '#1890ff', '#faad14', '#722ed1', '#389e0d', '#ff4d4f']
                for stage_idx, stage in enumerate(FUNNEL_STAGES):
                    values = [ch.get(stage, 0) for ch in channel_funnels]
                    fig.add_trace(go.Bar(name=FUNNEL_NAMES[stage_idx], x=[ch['channel'] for ch in channel_funnels], y=values, marker_color=colors_stages[stage_idx]))
                fig.update_layout(barmode='group', height=350, margin=dict(l=20, r=20, t=30, b=20), legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1))
                st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': False, 'displayModeBar': False})
        else:
            st.info('暂无渠道数据')

    # ========== 底部：商家端额外展示个人绩效 ==========
    if viewer_type == 'seller':
        st.divider()
        st.subheader('👤 我的漏斗表现')
        sale_id = st.session_state.get('user', {}).get('id')
        if sale_id:
            my_leads = db_query("SELECT * FROM customer_leads WHERE assign_sale_id=?", (sale_id,))
            my_leads = clean_score_column(my_leads)
            if len(my_leads) > 0:
                my_stats = pd.DataFrame(my_leads['lead_status'].value_counts()).reset_index()
                my_stats.columns = ['status', 'count']
                for stage in FUNNEL_STAGES:
                    if stage not in my_stats['status'].values:
                        my_stats = pd.concat([my_stats, pd.DataFrame([{'status': stage, 'count': 0}])], ignore_index=True)
                my_disp = my_stats[my_stats['status'].isin(FUNNEL_STAGES)].copy()
                my_disp['name'] = my_disp['status'].map(dict(zip(FUNNEL_STAGES, FUNNEL_NAMES)))
                my_disp = my_disp[['name', 'count']].set_index('name')

                # 个人漏斗柱状图
                if USE_PLOTLY:
                    fig = go.Figure()
                    fig.add_trace(go.Bar(x=my_disp.index, y=my_disp['count'], marker_color=['#52c41a', '#1890ff', '#faad14', '#722ed1', '#389e0d', '#ff4d4f']))
                    fig.update_layout(height=250, margin=dict(l=20, r=20, t=30, b=20), xaxis_title='阶段', yaxis_title='线索数')
                    st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': False, 'displayModeBar': False})

                # 关键指标
                c1, c2, c3 = st.columns(3)
                with c1:
                    my_dealt = len(my_leads[my_leads['lead_status'] == 'deal'])
                    st.metric('个人总线索', len(my_leads))
                with c2:
                    st.metric('已成交', my_dealt)
                with c3:
                    my_rate = round(my_dealt / len(my_leads) * 100, 1) if len(my_leads) > 0 else 0
                    st.metric('个人转化率', f'{my_rate}%')
            else:
                st.info('你没有分配到的线索')


# ========================== 工厂管理端 ==========================
def factory_admin():
    st.sidebar.header('🏭 工厂管理中心')
    user = st.session_state.get('user', {})
    st.sidebar.info(f'当前用户：{user["real_name"]}')

    # ---------- 侧边栏多级导航（expander + button，每次点击必rerun） ----------
    REALTIME_SUBS = ['📊 数据大屏', '🔻 销售漏斗看板', '📡 渠道效能分析', '🏆 销售团队排行', '📞 外呼效果分析']
    LEADS_SUBS    = ['📋 线索总览', '❤️ 线索健康度看板', '⚙️ 评分规则配置']
    PROFILE_KEY   = '👥 用户画像分析'

    def _get_category(sub):
        if sub in REALTIME_SUBS: return 'realtime'
        if sub in LEADS_SUBS:    return 'leads'
        if sub == PROFILE_KEY:   return 'profile'
        return 'realtime'

    # 初始化 session 默认值
    for k, v in [('realtime_sub', REALTIME_SUBS[0]), ('leads_sub', LEADS_SUBS[0]),
                 ('profile_sub', PROFILE_KEY), ('nav_sub', REALTIME_SUBS[0]),
                 ('nav_expander_active', 'realtime') ]:
        if k not in st.session_state:
            st.session_state[k] = v

    cur_cat = _get_category(st.session_state['nav_sub'])

    # 让 button 看起来像菜单项（去掉默认边框阴影，加悬停效果）
    st.sidebar.markdown('''
    <style>
    /* 子菜单按钮：扁平化、左对齐、无边框 */
    div[data-testid="stVerticalBlock"] div[data-testid="stButton"] > button {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        text-align: left !important;
        padding: 6px 12px 6px 28px !important;
        width: 100% !important;
        color: #555 !important;
        font-size: 13px !important;
        border-radius: 4px !important;
        margin: 1px 0 !important;
    }
    div[data-testid="stVerticalBlock"] div[data-testid="stButton"] > button:hover {
        background: #f0f2f5 !important;
        color: #333 !important;
    }
    div[data-testid="stVerticalBlock"] div[data-testid="stButton"] > button[kind="primary"] {
        background: #e8f0fe !important;
        color: #1a73e8 !important;
        font-weight: 600 !important;
    }
    div[data-testid="stVerticalBlock"] div[data-testid="stButton"] > button[kind="primary"]:hover {
        background: #d6e4ff !important;
    }
    /* 顶层独立按钮（用户画像分析） */
    .pf-nav-btn div[data-testid="stButton"] > button {
        padding: 10px 16px !important;
        font-size: 14px !important;
        color: #333 !important;
        font-weight: 600 !important;
    }
    .pf-nav-btn div[data-testid="stButton"] > button[kind="primary"] {
        color: #1a73e8 !important;
    }
    </style>
    ''', unsafe_allow_html=True)

    with st.sidebar:
        st.markdown('#### 功能菜单')

        # 实时经营看板
        rt_expanded = (st.session_state.get('nav_expander_active') == 'realtime' or cur_cat == 'realtime')
        with st.expander('📊 实时经营看板', expanded=rt_expanded):
            for sub in REALTIME_SUBS:
                is_active = st.session_state.get('nav_sub') == sub
                if st.button(sub, key=f'btn_rt_{sub}', type='primary' if is_active else 'secondary', use_container_width=True):
                    st.session_state['nav_sub'] = sub
                    st.session_state['realtime_sub'] = sub
                    st.session_state['nav_expander_active'] = 'realtime'
                    st.rerun()

        # 线索管理总览
        ld_expanded = (st.session_state.get('nav_expander_active') == 'leads' or cur_cat == 'leads')
        with st.expander('📋 线索管理总览', expanded=ld_expanded):
            for sub in LEADS_SUBS:
                is_active = st.session_state.get('nav_sub') == sub
                if st.button(sub, key=f'btn_ld_{sub}', type='primary' if is_active else 'secondary', use_container_width=True):
                    st.session_state['nav_sub'] = sub
                    st.session_state['leads_sub'] = sub
                    st.session_state['nav_expander_active'] = 'leads'
                    st.rerun()

        # 用户画像分析（无子项，直接独立按钮，一次点击即跳转）
        st.markdown('<div class="pf-nav-btn">', unsafe_allow_html=True)
        pf_active = cur_cat == 'profile'
        if st.button('👥 用户画像分析', key='btn_pf', type='primary' if pf_active else 'secondary', use_container_width=True):
            st.session_state['nav_sub'] = PROFILE_KEY
            st.session_state['profile_sub'] = PROFILE_KEY
            st.session_state['nav_expander_active'] = 'profile'
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # 从 nav_sub 推断当前主菜单和子菜单
    sub_menu = st.session_state['nav_sub']
    if sub_menu in REALTIME_SUBS:
        main_menu = '📊 实时经营看板'
    elif sub_menu in LEADS_SUBS:
        main_menu = '📋 线索管理总览'
    else:
        main_menu = PROFILE_KEY

    st.session_state['admin_current_menu'] = main_menu
    st.session_state[f'sub_{main_menu}'] = sub_menu

    # ===================== 内容区路由 =====================
    if main_menu == '📊 实时经营看板' and sub_menu == '📊 数据大屏':
        start_t, end_t = render_time_filter('dashboard')
        real_time_dashboard(start_t, end_t)

    elif main_menu == '📊 实时经营看板' and sub_menu == '🔻 销售漏斗看板':
        render_funnel_dashboard()
    elif main_menu == '📊 实时经营看板' and sub_menu == '📡 渠道效能分析':
        st.header('📡 渠道效能分析')
        start_t, end_t = render_time_filter('admin_channel')
        leads = db_query("SELECT l.*, c.channel_name FROM customer_leads l LEFT JOIN channel_dict c ON l.channel_id=c.id WHERE l.source_time BETWEEN ? AND ?", (start_t, end_t))
        leads = clean_score_column(leads)
        if len(leads) == 0:
            st.warning('本周期暂无线索数据')
        else:
            ch_stats = leads.groupby('channel_name').agg(线索量=('id', 'count'), 高价值数=('is_high_value', 'sum'), 平均评分=('total_score', 'mean'), 成交数=('lead_status', lambda x: (x == 'deal').sum())).reset_index()
            ch_stats['高价值率'] = round(ch_stats['高价值数'] / ch_stats['线索量'] * 100, 1)
            ch_stats['成交率'] = round(ch_stats['成交数'] / ch_stats['线索量'] * 100, 1)
            ch_stats['平均评分'] = round(ch_stats['平均评分'], 1)
            ch_stats = ch_stats.sort_values('线索量', ascending=False)
            st.subheader('📊 渠道核心指标')
            st.dataframe(ch_stats[['channel_name', '线索量', '高价值率', '平均评分', '成交率']].rename(columns={'channel_name': '渠道'}), use_container_width=True, hide_index=True)
            plot_ch = ch_stats.rename(columns={'channel_name': '渠道'})
            col1, col2 = st.columns(2)
            with col1: bar_chart(plot_ch, x='渠道', y='线索量')
            with col2: bar_chart(plot_ch, x='渠道', y='高价值率')
            st.subheader('🔽 渠道转化漏斗')
            for _, crow in ch_stats.head(5).iterrows():
                ch = crow['channel_name']
                ch_leads = leads[leads['channel_name'] == ch]
                total = len(ch_leads)
                touched = len(ch_leads[ch_leads['lead_status'] != 'untouch'])
                reserved = len(ch_leads[ch_leads['lead_status'] == 'reserve_test'])
                bargained = len(ch_leads[ch_leads['lead_status'] == 'bargain'])
                dealt = len(ch_leads[ch_leads['lead_status'] == 'deal'])
                st.write(f"**{ch}**: 总{total} -> 跟进{touched} -> 试驾{reserved} -> 议价{bargained} -> 成交{dealt}")
                if total > 0:
                    st.progress(min(dealt / total, 1.0))

    elif main_menu == '📊 实时经营看板' and sub_menu == '🏆 销售团队排行':
        st.header('🏆 销售团队排行')
        start_t, end_t = render_time_filter('admin_rank')
        shop_sql = "SELECT s.shop_name, COUNT(DISTINCT l.id) as lead_count, SUM(CASE WHEN l.lead_status='deal' THEN 1 ELSE 0 END) as deal_count, COUNT(cr.id) as call_count, COALESCE(AVG(cr.score_after_call),0) as avg_call_score FROM shop s LEFT JOIN customer_leads l ON s.id=l.assign_shop_id AND l.assign_time BETWEEN ? AND ? LEFT JOIN call_record cr ON l.id=cr.lead_id AND cr.create_time BETWEEN ? AND ? GROUP BY s.id, s.shop_name"
        shop_stats = db_query(shop_sql, (start_t, end_t, start_t, end_t))
        if len(shop_stats) > 0:
            shop_stats['成交率'] = round(shop_stats['deal_count'] / shop_stats['lead_count'].replace(0, 1) * 100, 1)
            shop_stats['平均通话评分'] = round(shop_stats['avg_call_score'], 1)
            shop_stats = shop_stats.sort_values('deal_count', ascending=False)
            st.subheader('🏬 门店排行')
            st.dataframe(shop_stats.rename(columns={'shop_name': '门店', 'lead_count': '线索数', 'deal_count': '成交数', 'call_count': '外呼数'}), use_container_width=True, hide_index=True)
            plot_shop = shop_stats.rename(columns={'shop_name': '门店', 'deal_count': '成交数'})
            bar_chart(plot_shop, x='门店', y='成交数')
        seller_sql = "SELECT u.real_name, s.shop_name, COUNT(DISTINCT l.id) as lead_count, SUM(CASE WHEN l.lead_status='deal' THEN 1 ELSE 0 END) as deal_count, COUNT(cr.id) as call_count FROM sys_user u LEFT JOIN shop s ON u.shop_id=s.id LEFT JOIN customer_leads l ON u.id=l.assign_sale_id AND l.assign_time BETWEEN ? AND ? LEFT JOIN call_record cr ON l.id=cr.lead_id AND cr.create_time BETWEEN ? AND ? WHERE u.role='sale' GROUP BY u.id, u.real_name, s.shop_name"
        seller_stats = db_query(seller_sql, (start_t, end_t, start_t, end_t))
        if len(seller_stats) > 0:
            seller_stats = seller_stats.sort_values('deal_count', ascending=False)
            st.subheader('👤 销售个人排行')
            st.dataframe(seller_stats.rename(columns={'real_name': '销售姓名', 'shop_name': '所属门店', 'lead_count': '负责线索', 'deal_count': '成交数', 'call_count': '外呼数'}), use_container_width=True, hide_index=True)

    elif main_menu == '📊 实时经营看板' and sub_menu == '📞 外呼效果分析':
        st.header('📞 外呼效果分析')
        start_t, end_t = render_time_filter('admin_call')
        calls = db_query("SELECT cr.*, cl.phone, cl.customer_name, u.real_name as sale_name, s.shop_name FROM call_record cr LEFT JOIN customer_leads cl ON cr.lead_id=cl.id LEFT JOIN sys_user u ON cr.shop_id=u.shop_id LEFT JOIN shop s ON cr.shop_id=s.id WHERE cr.create_time BETWEEN ? AND ? ORDER BY cr.create_time DESC", (start_t, end_t))
        if len(calls) == 0:
            st.info('本周期暂无外呼记录')
        else:
            calls = clean_score_column(calls, 'score_after_call')
            st.subheader('📊 外呼核心指标')
            col1, col2, col3, col4 = st.columns(4)
            col1.metric('总外呼次数', len(calls))
            col2.metric('平均通话后评分', round(calls['score_after_call'].mean(), 1))
            col3.metric('平均通话时长(秒)', int(calls['call_duration'].mean()))
            col4.metric('覆盖门店数', calls['shop_name'].nunique())
            st.divider()
            st.subheader('📈 评分变化趋势')
            calls['dt'] = calls['create_time'].astype(str).str[:10]
            trend = calls.groupby('dt').agg({'score_after_call': 'mean', 'call_duration': 'sum'}).reset_index()
            trend.columns = ['日期', '平均评分', '总时长']
            line_chart(trend, x='日期', y='平均评分', color='#52c41a')
            st.divider()
            st.subheader('📋 外呼明细')
            disp = calls[['customer_name', 'phone', 'shop_name', 'sale_name', 'call_duration', 'score_after_call', 'level_after_call', 'create_time']].rename(columns={'customer_name': '客户', 'phone': '手机号', 'shop_name': '门店', 'sale_name': '销售', 'call_duration': '时长(秒)', 'score_after_call': '通话后评分', 'level_after_call': '通话后等级', 'create_time': '时间'})
            st.dataframe(disp, use_container_width=True, hide_index=True)
    elif main_menu == '📋 线索管理总览' and sub_menu == '📋 线索总览':
        st.header('📋 线索管理总览')
        start_t, end_t = render_time_filter('admin_leads')

        # ========== 🤖 AI 智能采集中心 ==========
        st.markdown('''
        <style>
        .ai-collect-card {
            background: #fff;
            border: 1px solid #e8e8e8;
            border-radius: 12px;
            padding: 20px 24px;
            margin-bottom: 16px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        }
        .ai-collect-header {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 6px;
        }
        .ai-collect-header .icon {
            font-size: 22px;
        }
        .ai-collect-header .title {
            font-size: 16px;
            font-weight: 700;
            color: #1a1a1a;
            letter-spacing: 0.5px;
        }
        .ai-collect-desc {
            font-size: 13px;
            color: #888;
            margin-bottom: 14px;
            line-height: 1.5;
        }
        .ai-platform-label {
            font-size: 12px;
            font-weight: 600;
            color: #555;
            margin-bottom: 8px;
            display: block;
        }
        .kpi-card {
            background: #f8f9ff;
            border: 1px solid #e0e4ff;
            border-radius: 10px;
            padding: 14px 16px;
            text-align: center;
            margin-bottom: 10px;
        }
        .kpi-card .kpi-icon {
            font-size: 20px;
            margin-bottom: 4px;
        }
        .kpi-card .kpi-value {
            font-size: 26px;
            font-weight: 700;
            color: #1a73e8;
            line-height: 1.2;
        }
        .kpi-card .kpi-label {
            font-size: 12px;
            color: #888;
            margin-top: 2px;
        }
        .kpi-card-today {
            background: #fff8f0;
            border-color: #ffe0b2;
        }
        .kpi-card-today .kpi-value {
            color: #fa8c16;
        }
        .source-tag {
            display: inline-block;
            background: #f0f2f5;
            color: #555;
            font-size: 12px;
            padding: 3px 10px;
            border-radius: 12px;
            margin: 2px 4px 2px 0;
        }
        .pulse-row {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 6px 0;
        }
        .pulse-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #52c41a;
            animation: pulseDot 1.2s ease-in-out infinite;
            flex-shrink: 0;
        }
        .pulse-text {
            font-size: 12px;
            color: #52c41a;
            font-weight: 500;
        }
        @keyframes pulseDot {
            0%,100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.3; transform: scale(1.6); }
        }
        </style>
        ''', unsafe_allow_html=True)

        ai_left, ai_right = st.columns([3, 1])

        with ai_left:
            st.markdown('''
            <div class="ai-collect-card">
                <div class="ai-collect-header">
                    <span class="icon">🤖</span>
                    <span class="title">AI 智能采集中心</span>
                </div>
                <div class="ai-collect-desc">
                    AI 自动从社交媒体、汽车媒体、垂直社区等平台采集潜客线索，通过自然语言处理提取联系方式、预算、车型、购车意向，并自动评分定级。
                </div>
            </div>
            ''', unsafe_allow_html=True)

            # 平台选择（更紧凑）
            all_channels = list(db_query('SELECT channel_name FROM channel_dict')['channel_name'])
            ch_cols = st.columns(4)
            channel_sel = []
            for idx, ch in enumerate(all_channels):
                with ch_cols[idx % 4]:
                    if st.checkbox(ch, value=True, key=f'ai_ch_{ch}'):
                        channel_sel.append(ch)

            # 操作按钮行
            btn_col1, btn_col2, btn_col3 = st.columns([1.2, 1, 2])
            with btn_col1:
                if st.button('🚀 启动 AI 采集', use_container_width=True, type='primary', key='btn_ai_crawl'):
                    st.session_state['ai_crawl_running'] = True
                    st.rerun()
            with btn_col2:
                if st.button('📋 采集日志', use_container_width=True, key='btn_ai_log'):
                    dialog_ai_log()
            with btn_col3:
                st.checkbox('每60秒自动采集', value=False, key='auto_crawl_60s')

            # 自动采集脉冲动画
            if st.session_state.get('auto_crawl_60s', False):
                st.markdown('''
                <div class="pulse-row">
                    <div class="pulse-dot"></div>
                    <span class="pulse-text">AI 自动采集中...</span>
                </div>
                ''', unsafe_allow_html=True)

            # ========== AI 采集动画流程 ==========
            if st.session_state.get('ai_crawl_running', False):
                # 采集流程容器
                crawl_container = st.container()
                with crawl_container:
                    st.markdown('---')
                    progress_bar = st.progress(0, text='AI 正在连接平台...')
                    status_text = st.empty()
                    log_area = st.empty()

                    steps = [
                        ('AI 正在连接平台...', 0.05),
                        ('正在扫描 短视频 平台...', 0.15),
                        ('正在扫描 社交种草 平台...', 0.25),
                        ('正在扫描 垂直社区 平台...', 0.35),
                        ('正在扫描 社交媒体 平台...', 0.45),
                        ('正在扫描 资讯媒体 平台...', 0.55),
                        ('正在扫描 社区论坛 平台...', 0.65),
                        ('正在扫描 汽车媒体 平台...', 0.75),
                        ('正在扫描 问答社区 平台...', 0.80),
                        ('正在扫描 视频社区 平台...', 0.85),
                        ('正在扫描 二手交易 平台...', 0.90),
                        ('正在扫描 官方APP 平台...', 0.95),
                        ('正在提取联系方式、预算、车型...', 0.98),
                        ('AI 评分定级中...', 0.99),
                    ]

                    log_lines = []
                    for msg, pct in steps:
                        progress_bar.progress(pct, text=msg)
                        status_text.markdown(f"<div style='font-size:14px;color:#666;'>⏳ {msg}</div>", unsafe_allow_html=True)
                        # 模拟日志
                        if '扫描' in msg:
                            log_lines.append(f"✅ {msg.replace('正在扫描', '已扫描')}")
                            log_area.markdown('<div style="background:#f6ffed;border:1px solid #b7eb8f;border-radius:4px;padding:8px;font-size:12px;max-height:120px;overflow-y:auto;">' + '<br>'.join(log_lines[-6:]) + '</div>', unsafe_allow_html=True)
                        time.sleep(0.15)

                    progress_bar.progress(1.0, text='采集完成！')
                    status_text.markdown("<div style='font-size:14px;color:#52c41a;font-weight:bold;'>✅ 采集完成！</div>", unsafe_allow_html=True)

                # 执行真正的采集
                num, results = auto_crawl_leads()
                execute_distribute()
                if 'ai_crawl_log' not in st.session_state:
                    st.session_state['ai_crawl_log'] = []
                st.session_state['ai_crawl_log'].extend(results)
                # 限制日志最多 200 条
                if len(st.session_state['ai_crawl_log']) > 200:
                    st.session_state['ai_crawl_log'] = st.session_state['ai_crawl_log'][-200:]

                # 清除状态并显示结果
                st.session_state['ai_crawl_running'] = False
                st.success(f'🎉 采集完成！新增 {num} 条线索，已自动分配门店。')
                time.sleep(1.0)
                st.rerun()

        with ai_right:
            # 统计数据（精美 KPI 卡片）
            all_leads = db_query("SELECT * FROM customer_leads")
            today = datetime.datetime.now().strftime('%Y-%m-%d')
            total_ai = len(all_leads)
            today_ai = len(all_leads[all_leads['source_time'].astype(str).str.startswith(today)])

            st.markdown(f'''
            <div class="kpi-card">
                <div class="kpi-icon">📊</div>
                <div class="kpi-value">{total_ai}</div>
                <div class="kpi-label">累计 AI 采集</div>
            </div>
            <div class="kpi-card kpi-card-today">
                <div class="kpi-icon">📅</div>
                <div class="kpi-value">{today_ai}</div>
                <div class="kpi-label">今日采集</div>
            </div>
            ''', unsafe_allow_html=True)

            # 主要来源
            ch_counts = all_leads.groupby('channel_id').size().reset_index(name='cnt')
            ch_map = db_query('SELECT id, channel_name FROM channel_dict')
            ch_map = dict(zip(ch_map['id'], ch_map['channel_name']))
            ch_counts['name'] = ch_counts['channel_id'].map(ch_map)
            top3 = ch_counts.nlargest(3, 'cnt')
            if len(top3) > 0:
                tags_html = ''.join([f'<span class="source-tag">{r["name"]} {r["cnt"]}条</span>' for _, r in top3.iterrows()])
                st.markdown(f'''
                <div style="margin-top:4px;">
                    <div style="font-size:12px;color:#888;margin-bottom:6px;font-weight:500;">主要来源平台</div>
                    {tags_html}
                </div>
                ''', unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)
        st.divider()

        # ========== 线索列表筛选栏（横排） ==========
        # 查询数据
        leads = db_query("SELECT l.id,l.phone,l.customer_name,l.city,l.budget,l.total_score,l.lead_level,l.is_high_value,l.user_tags,l.source_time,l.lead_status,l.first_contact_time,c.channel_name,m.model_name,s.shop_name,l.consult_content,COALESCE(cr_count.cnt,0) as call_count FROM customer_leads l LEFT JOIN channel_dict c ON l.channel_id=c.id LEFT JOIN motorcycle_model m ON l.model_id=m.id LEFT JOIN shop s ON l.assign_shop_id=s.id LEFT JOIN (SELECT lead_id,COUNT(*) as cnt FROM call_record GROUP BY lead_id) cr_count ON l.id=cr_count.lead_id WHERE l.source_time BETWEEN ? AND ?", (start_t, end_t))
        leads = clean_score_column(leads)

        # 横排筛选
        channels = ['全部'] + list(db_query('SELECT channel_name FROM channel_dict')['channel_name'])
        f1, f2, f3, f4, f5, f6 = st.columns([1, 1.2, 1, 1.2, 2, 1])
        with f1:
            level_filter = st.selectbox('线索等级', ['全部', 'A', 'B', 'C', 'D'], key='list_level')
        with f2:
            channel_filter = st.selectbox('来源渠道', channels, key='list_channel')
        with f3:
            status_filter = st.selectbox('线索状态', ['全部'] + list(STATUS_MAP.values()), key='list_status')
        with f4:
            sort_type = st.selectbox('排序', SORT_OPTIONS, key='list_sort')
        with f5:
            search_key = st.text_input('搜索', placeholder='手机号、姓名、城市、内容', key='list_search')
        with f6:
            st.write('')
            st.write('')
            if st.button('➕ 新增线索', use_container_width=True, type='primary'):
                dialog_add_lead()

        # 应用筛选
        filtered = leads.copy()
        if level_filter != '全部':
            filtered = filtered[filtered['lead_level'] == level_filter]
        if channel_filter != '全部':
            filtered = filtered[filtered['channel_name'] == channel_filter]
        if status_filter != '全部':
            codes = [k for k, v in STATUS_MAP.items() if v == status_filter]
            filtered = filtered[filtered['lead_status'].isin(codes)] if codes else filtered.iloc[0:0]
        if search_key.strip():
            key = search_key.strip()
            mask = (filtered['phone'].astype(str).str.contains(key, case=False, na=False) |
                    filtered['customer_name'].astype(str).str.contains(key, case=False, na=False) |
                    filtered['city'].astype(str).str.contains(key, case=False, na=False) |
                    filtered['consult_content'].astype(str).str.contains(key, case=False, na=False))
            filtered = filtered[mask]
        filtered = sort_leads(filtered, sort_type)

        # 表格展示
        display = filtered.copy()
        display['线索状态'] = display['lead_status'].apply(status_to_cn)
        display['价值标识'] = display['is_high_value'].apply(lambda x: '⭐ 高价值' if x == 1 else '')
        col_rename = {'id': '线索ID', 'phone': '手机号', 'customer_name': '客户姓名', 'city': '所在城市', 'total_score': 'AI评分', 'lead_level': '线索等级', 'user_tags': '用户标签', 'source_time': '来源时间', 'first_contact_time': '首次接触时间', 'call_count': '外呼次数', 'channel_name': '来源渠道', 'model_name': '意向车型', 'shop_name': '分配门店'}
        display = display.rename(columns=col_rename)
        show_cols = ['线索ID', '手机号', '客户姓名', '所在城市', 'AI评分', '线索等级', '价值标识', '线索状态', '首次接触时间', '外呼次数', '来源渠道', '意向车型', '分配门店', '用户标签', '来源时间']
        col1, col2 = st.columns([4, 1])
        with col1:
            st.subheader('全量线索列表')
            st.caption(f'共筛选出 {len(filtered)} 条线索，当前排序：{sort_type}')
        with col2:
            st.write('')
            st.download_button('📥 导出当前结果', data=export_leads_excel(filtered), file_name=f"线索列表_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx", mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', use_container_width=True)
        st.dataframe(display[show_cols], use_container_width=True, height=500)

    elif main_menu == '📋 线索管理总览' and sub_menu == '⚙️ 评分规则配置':
        st.header('AI评分规则自定义')
        rule_df = db_query('SELECT * FROM score_rule')
        if len(rule_df) == 0:
            st.error('评分规则未配置')
            return
        rule = rule_df.iloc[0]
        col1, col2 = st.columns(2)
        with col1:
            full = st.number_input('信息完整度基础分', value=int(rule['full_info_score']))
            time_val = st.number_input('时效基础分(3天内满分)', value=int(rule['time_score']))
            high = st.number_input('高意向关键词加分', value=int(rule['high_intent_score']))
            mid = st.number_input('中性意向加分', value=int(rule['mid_intent_score']))
        with col2:
            low = st.number_input('低意向关键词扣分', value=int(rule['low_intent_score']))
            behavior = st.number_input('行为频次加分上限', value=int(rule['behavior_freq_score']))
            demand = st.number_input('需求明确度加分', value=int(rule['demand_clear_score']))
        st.divider()
        level_cfg = db_query('SELECT * FROM level_config').iloc[0]
        st.subheader('线索分层阈值')
        a = st.number_input('A级最低分', value=int(level_cfg['a_min']))
        b = st.number_input('B级最低分', value=int(level_cfg['b_min']))
        c = st.number_input('C级最低分', value=int(level_cfg['c_min']))
        high_val = st.number_input('高价值线索最低分', value=int(level_cfg['high_value_min']))
        if st.button('保存全部规则', type='primary'):
            db_exec('UPDATE score_rule SET full_info_score=?,time_score=?,high_intent_score=?,mid_intent_score=?,low_intent_score=?,behavior_freq_score=?,demand_clear_score=?', (int(full), int(time_val), int(high), int(mid), int(low), int(behavior), int(demand)))
            db_exec('UPDATE level_config SET a_min=?,b_min=?,c_min=?,high_value_min=?', (int(a), int(b), int(c), int(high_val)))
            st.success('规则保存成功')
    elif main_menu == '📋 线索管理总览' and sub_menu == '❤️ 线索健康度看板':
        st.header('🩺 线索健康度看板（多维度评估）')
        start_t, end_t = render_time_filter('health')
        leads_sql = "SELECT l.*, c.channel_name, (SELECT COUNT(*) FROM call_record cr WHERE cr.lead_id=l.id) as call_count, (SELECT MAX(cr.create_time) FROM call_record cr WHERE cr.lead_id=l.id) as last_call_time, (SELECT COUNT(*) FROM lead_follow_record fr WHERE fr.lead_id=l.id) as follow_count, (SELECT MAX(fr.create_time) FROM lead_follow_record fr WHERE fr.lead_id=l.id) as last_follow_time FROM customer_leads l LEFT JOIN channel_dict c ON l.channel_id=c.id WHERE l.source_time BETWEEN ? AND ?"
        all_leads = db_query(leads_sql, (start_t, end_t))
        all_leads = clean_score_column(all_leads)
        if len(all_leads) == 0:
            st.warning('暂无线索数据')
            return
        all_leads['source_dt'] = pd.to_datetime(all_leads['source_time'], errors='coerce')
        all_leads['last_call_dt'] = pd.to_datetime(all_leads['last_call_time'], errors='coerce')
        all_leads['last_follow_dt'] = pd.to_datetime(all_leads['last_follow_time'], errors='coerce')
        now = datetime.datetime.now()
        channel_weights = dict(db_query('SELECT channel_name, weight FROM channel_dict').values)

        def calc_dimension_scores(row):
            scores = {}
            # 基础质量
            base_quality = 0
            w = channel_weights.get(row['channel_name'], 0)
            base_quality += min(w, 20)
            info_fields = ['customer_name', 'city', 'budget', 'model_id', 'consult_content']
            if all(pd.notna(row[f]) and row[f] != '' for f in info_fields):
                base_quality += 20
            scores['基础质量'] = min(base_quality, 100)
            # 客户意向强度
            intent_score = 0
            lead_score = clean_score(row['total_score'])
            intent_score += lead_score * 0.8 if lead_score else 0
            tags = str(row['user_tags'])
            if '强购车意向' in tags or '预约到店' in tags:
                intent_score += 20
            if '犹豫比较中' in tags:
                intent_score -= 10
            scores['客户意向强度'] = max(0, min(intent_score, 100))
            # 互动活跃度
            activity_score = 0
            behavior = int(row['behavior_count']) if pd.notna(row['behavior_count']) else 1
            activity_score += min(behavior * 10, 30)
            latest_interact = pd.NaT
            if pd.notna(row['last_call_dt']):
                latest_interact = row['last_call_dt']
            if pd.notna(row['last_follow_dt']):
                if pd.isna(latest_interact) or row['last_follow_dt'] > latest_interact:
                    latest_interact = row['last_follow_dt']
            if pd.notna(latest_interact):
                days_since = (now - latest_interact).days
                if days_since <= 1:
                    activity_score += 30
                elif days_since <= 3:
                    activity_score += 20
                elif days_since <= 7:
                    activity_score += 10
            scores['互动活跃度'] = min(activity_score, 100)
            # 跟进健康
            follow_score = 0
            if pd.notna(row['first_contact_time']) and row['first_contact_time'] != '':
                follow_score += 30
            follow_cnt = int(row['follow_count']) if pd.notna(row['follow_count']) else 0
            follow_score += min(follow_cnt * 10, 30)
            if pd.notna(row['last_follow_dt']):
                days_follow = (now - row['last_follow_dt']).days
                if days_follow <= 1:
                    follow_score += 20
                elif days_follow <= 3:
                    follow_score += 10
            scores['跟进健康'] = min(follow_score, 100)
            # 资料完整
            complete = 0
            fields = {'customer_name': 20, 'phone': 20, 'city': 15, 'budget': 15, 'model_id': 15, 'consult_content': 15}
            for f, pts in fields.items():
                if pd.notna(row[f]) and row[f] != '':
                    complete += pts
            scores['资料完整'] = complete
            # 风险负面
            risk_score = 100
            consult = str(row['consult_content']).lower()
            negative_words = ['不买', '太贵', '放弃', '不考虑', '等新款', '随便看看']
            for nw in negative_words:
                if nw in consult:
                    risk_score -= 15
            if row['lead_status'] == 'lost':
                risk_score -= 30
            if '客户流失' in str(row['user_tags']):
                risk_score -= 25
            scores['风险负面'] = max(0, risk_score)
            # 综合健康分
            weights = {'基础质量': 0.15, '客户意向强度': 0.25, '互动活跃度': 0.2, '跟进健康': 0.2, '资料完整': 0.1, '风险负面': 0.1}
            overall = sum(scores[k] * weights[k] for k in weights)
            scores['综合健康分'] = round(overall)
            return pd.Series(scores)

        dim_scores = all_leads.apply(calc_dimension_scores, axis=1)
        all_leads = pd.concat([all_leads, dim_scores], axis=1)
        channel_list = ['全部'] + list(all_leads['channel_name'].dropna().unique())
        selected_channel = st.selectbox('选择渠道', channel_list, key='health_channel')
        display_leads = all_leads if selected_channel == '全部' else all_leads[all_leads['channel_name'] == selected_channel].copy()

        if selected_channel != '全部':
            st.subheader(f'📌 {selected_channel} 渠道健康度详情')
            total = len(display_leads)
            healthy = len(display_leads[display_leads['综合健康分'] >= 80])
            sub_healthy = len(display_leads[(display_leads['综合健康分'] >= 60) & (display_leads['综合健康分'] < 80)])
            cultivate = len(display_leads[display_leads['综合健康分'] < 60])
            col1, col2, col3, col4 = st.columns(4)
            col1.metric('线索总数', total)
            col2.metric('健康线索', f'{healthy} ({round(healthy/total*100,1)}%)' if total > 0 else '0')
            col3.metric('亚健康线索', f'{sub_healthy} ({round(sub_healthy/total*100,1)}%)' if total > 0 else '0')
            col4.metric('待培育', f'{cultivate} ({round(cultivate/total*100,1)}%)' if total > 0 else '0')
            health_cat = pd.cut(display_leads['综合健康分'], bins=[0, 60, 80, 101], labels=['待培育', '亚健康', '健康'])
            health_counts = health_cat.value_counts().reset_index()
            health_counts.columns = ['健康度', '数量']
            if USE_PLOTLY:
                fig = px.pie(health_counts, names='健康度', values='数量', color='健康度', color_discrete_map={'健康': '#52c41a', '亚健康': '#faad14', '待培育': '#ff4d4f'})
                fig.update_layout(height=350)
                st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': False, 'displayModeBar': False})
            else:
                st.bar_chart(health_counts.set_index('健康度')['数量'])
            dim_avg = display_leads[['基础质量', '客户意向强度', '互动活跃度', '跟进健康', '资料完整', '风险负面']].mean().reset_index()
            dim_avg.columns = ['维度', '平均分']
            bar_chart(dim_avg, x='维度', y='平均分')
            st.subheader('⚠️ 风险负面线索 (风险分<60)')
            risk_leads = display_leads[display_leads['风险负面'] < 60][['id', 'customer_name', 'phone', 'channel_name', '风险负面', 'consult_content']]
            if len(risk_leads) > 0:
                st.dataframe(risk_leads, use_container_width=True)
            else:
                st.info('暂无高风险线索')
        else:
            st.subheader('🌐 全渠道健康度对比')
            avg_score = display_leads.groupby('channel_name')['综合健康分'].mean().sort_values(ascending=False).reset_index()
            avg_score.columns = ['渠道', '平均健康分']
            bar_chart(avg_score, x='渠道', y='平均健康分')
            dim_avg_ch = display_leads.groupby('channel_name')[['基础质量', '客户意向强度', '互动活跃度', '跟进健康', '资料完整', '风险负面']].mean()
            if USE_PLOTLY:
                fig = px.bar(dim_avg_ch, x=dim_avg_ch.index, y=dim_avg_ch.columns, barmode='group', title='各渠道维度平均分对比')
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': False, 'displayModeBar': False})
            else:
                st.bar_chart(dim_avg_ch)

    elif main_menu == '👥 用户画像分析':
        st.header('👥 用户画像分析')
        start_t, end_t = render_time_filter('admin_profile')
        all_leads = db_query("SELECT * FROM customer_leads WHERE source_time BETWEEN ? AND ?", (start_t, end_t))
        all_leads = clean_score_column(all_leads)
        if len(all_leads) == 0:
            st.warning('暂无线索数据')
            return
        all_leads['source_dt'] = pd.to_datetime(all_leads['source_time'], errors='coerce')
        channel_df = db_query('SELECT id as channel_id, channel_name FROM channel_dict')
        all_leads = all_leads.merge(channel_df, on='channel_id', how='left')
        st.subheader('🌍 地域分布')
        all_leads['省份'] = all_leads['city'].apply(get_province)
        region = all_leads['省份'].value_counts().reset_index()
        region.columns = ['省份', '线索量']
        bar_chart(region, x='省份', y='线索量')
        st.subheader('💰 消费水平分布')
        def budget_level(b):
            if pd.isna(b):
                return '未知'
            b = str(b)
            try:
                num_str = ''.join([c for c in b if c.isdigit() or c == '.'])
                if num_str:
                    amt = float(num_str)
                    if '万' in b:
                        amt *= 10000
                    if amt >= 30000: return '高预算(>=3万)'
                    elif amt >= 15000: return '中预算(1.5-3万)'
                    else: return '入门预算(<1.5万)'
            except Exception:
                pass
            if '预算不多' in b: return '入门预算(<1.5万)'
            return '未知'
        all_leads['消费水平'] = all_leads['budget'].apply(budget_level)
        budget_counts = all_leads['消费水平'].value_counts().reset_index()
        budget_counts.columns = ['消费水平', '数量']
        if USE_PLOTLY:
            fig = px.pie(budget_counts, names='消费水平', values='数量', color='消费水平', color_discrete_sequence=px.colors.qualitative.Set2)
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': False, 'displayModeBar': False})
        else:
            st.bar_chart(budget_counts.set_index('消费水平')['数量'])
        st.subheader('🏍️ 意向车型偏好')
        model_df = db_query('SELECT id,model_name FROM motorcycle_model')
        all_leads = all_leads.merge(model_df[['id', 'model_name']], left_on='model_id', right_on='id', how='left')
        if 'model_name_y' in all_leads.columns:
            all_leads = all_leads.rename(columns={'model_name_y': 'model_name'})
        elif 'model_name' not in all_leads.columns and 'model_name_x' in all_leads.columns:
            all_leads = all_leads.rename(columns={'model_name_x': 'model_name'})
        all_leads = all_leads.drop(columns=[c for c in ['id_x', 'id_y'] if c in all_leads.columns], errors='ignore')
        model_counts = all_leads['model_name'].value_counts().reset_index()
        model_counts.columns = ['车型', '数量']
        bar_chart(model_counts, x='车型', y='数量')
        st.subheader('📡 渠道来源效能')
        ch_counts = all_leads.groupby('channel_name').size().reset_index(name='线索量')
        ch_high = all_leads.groupby('channel_name')['is_high_value'].mean().reset_index(name='高价值率')
        ch_stats = ch_counts.merge(ch_high, on='channel_name')
        ch_stats['高价值率'] = round(ch_stats['高价值率'] * 100, 1)
        col1, col2 = st.columns(2)
        with col1: st.dataframe(ch_stats, use_container_width=True, hide_index=True)
        with col2: bar_chart(ch_stats, x='channel_name', y='线索量')
        st.subheader('🏷️ 用户关注点标签')
        all_tags = []
        for t in all_leads['user_tags'].dropna():
            all_tags.extend(t.split(','))
        tag_counts = pd.Series(all_tags).value_counts().head(10).reset_index()
        tag_counts.columns = ['标签', '数量']
        if len(tag_counts) > 0:
            bar_chart(tag_counts, x='标签', y='数量')
        else:
            st.info('暂无标签数据')
        st.subheader('⏰ 线索活跃时段')
        valid_leads = all_leads.dropna(subset=['source_dt'])
        valid_leads['小时'] = valid_leads['source_dt'].dt.hour
        hour_counts = valid_leads['小时'].value_counts().sort_index().reset_index()
        hour_counts.columns = ['小时', '线索量']
        line_chart(hour_counts, x='小时', y='线索量', color='#722ed1')
        top_region = region.iloc[0]['省份'] if len(region) > 0 else '未知'
        top_budget = budget_counts.iloc[0]['消费水平'] if len(budget_counts) > 0 else '未知'
        top_model = model_counts.iloc[0]['车型'] if len(model_counts) > 0 else '未知'
        top_channel = ch_stats.sort_values('线索量', ascending=False).iloc[0]['channel_name'] if len(ch_stats) > 0 else '未知'
        top_tags = '、'.join(tag_counts['标签'].head(5).tolist()) if len(tag_counts) > 0 else '暂无'
        top_hours = hour_counts.nlargest(3, '线索量')['小时'].tolist() if len(hour_counts) > 0 else []
        top_hours_str = '、'.join([f'{h}点' for h in top_hours]) if top_hours else '暂无'

        st.divider()
        st.subheader('📋 综合画像总结')
        st.info(f'核心客群特征：\n- 主要分布在 {top_region} 区域。\n- 消费水平以 {top_budget} 为主。\n- 最受欢迎车型是 {top_model}。\n- 渠道中 {top_channel} 贡献最大。')

        # ========== 营销宣传建议 ==========
        st.divider()
        st.subheader('🎯 基于画像的营销宣传建议')

        # 构建建议数据
        budget_key = budget_counts.iloc[0]['消费水平'] if len(budget_counts) > 0 else ''
        top3_regions = region.head(3)['省份'].tolist() if len(region) > 0 else []
        top3_models = model_counts.head(3)['车型'].tolist() if len(model_counts) > 0 else []
        top3_channels = ch_stats.nlargest(3, '线索量')['channel_name'].tolist() if len(ch_stats) > 0 else []
        high_value_ch = ch_stats.nlargest(1, '高价值率')['channel_name'].iloc[0] if len(ch_stats) > 0 else '暂无'

        # 1. 广告投放建议
        st.markdown('**📢 广告投放策略**')
        advices = []
        advices.append(f'🔹 **核心投放区域**：重点在 {"、".join(top3_regions)} 加大 SEM/信息流投放，该区域贡献了最多的潜客线索。')
        advices.append(f'🔹 **主力渠道**：{"、".join(top3_channels)} 为获客主力渠道，建议保持预算；其中 **{high_value_ch}** 高价值率最高，可适当提高出价获客质量。')
        if top_hours:
            advices.append(f'🔹 **投放时段**：用户活跃高峰在 {"、".join([f"{h}点" for h in top_hours[:3]])}，建议在该时段集中投放，提高线索转化率。')
        for a in advices:
            st.markdown(a)

        # 2. 内容营销建议
        st.markdown('**📝 内容营销方向**')
        content_advices = []
        if top3_models:
            content_advices.append(f'🔹 主力推广车型 **{"、".join(top3_models)}**，制作试驾评测、车主访谈、对比横评等内容。')
        if top_tags:
            content_advices.append(f'🔹 围绕用户最关注的话题（{top_tags}）创作专题内容，匹配关键词布局提升搜索曝光。')
        if budget_key:
            if '入门' in budget_key or '<1.5万' in budget_key:
                content_advices.append(f'🔹 客户以入门预算为主，内容侧重"高性价比""首购推荐""0首付分期"等卖点。')
            elif '中预算' in budget_key or '1.5-3万' in budget_key:
                content_advices.append(f'🔹 客户预算中等，内容侧重"品质升级""配置对比""智能科技"等差异化卖点。')
            elif '高预算' in budget_key or '>=3万' in budget_key:
                content_advices.append(f'🔹 客户为高预算群体，内容侧重"高端体验""品牌文化""限量/定制"等溢价卖点。')
        for a in content_advices:
            st.markdown(a)

        # 3. 活动策划建议
        st.markdown('**🎪 线下活动建议**')
        event_advices = []
        event_advices.append(f'🔹 在 **{top_region}** 核心城市开展试驾体验日、车友聚会等线下活动，面对面转化高意向客户。')
        event_advices.append(f'🔹 联动 {"、".join(top3_channels[:2])} 平台发布活动招募，设置到店礼品、试驾抽奖等裂变机制。')
        if budget_key and '高预算' in budget_key:
            event_advices.append(f'🔹 针对高预算客户，策划 VIP 品鉴会、定制改装沙龙等高端活动，提升品牌调性。')
        for a in event_advices:
            st.markdown(a)

        # 4. 一句话行动清单
        st.markdown('**✅ 行动清单**')
        actions = [
            f'主投区域：{"、".join(top3_regions)}',
            f'主推车型：{"、".join(top3_models)}',
            f'核心渠道：{top3_channels[0]}',
            f'最佳时段：{top_hours_str}',
            f'内容方向：{top_tags}',
        ]
        act_cols = st.columns(len(actions))
        for i, act in enumerate(actions):
            with act_cols[i]:
                st.markdown(f'<div style="background:#fff7f7;border:1px solid #f5c6cb;border-radius:6px;padding:10px;text-align:center;font-size:13px;">{act}</div>', unsafe_allow_html=True)



# ========================== 商家操作端 ==========================
def shop_seller():
    st.sidebar.header('🏪 商家工作台')
    user = st.session_state.get('user')
    if user is None:
        st.error('会话已过期，请重新登录')
        st.rerun()
        return
    shop_id = user['shop_id']
    sale_id = user['id']
    shop_df = db_query('SELECT shop_name FROM shop WHERE id=?', (shop_id,))
    shop_name = shop_df.iloc[0]['shop_name'] if len(shop_df) > 0 else '未知门店'
    st.sidebar.info(f'门店：{shop_name}\n用户：{user["real_name"]}')
    menu = st.sidebar.radio('功能菜单', ['📋 今日工作台', '📁 我的线索池', '🔻 销售漏斗看板', '📞 外呼中心', '📈 门店数据看板'])
    if menu == '📋 今日工作台':
        st.header('📋 今日工作台 & 门店经营数据')
        today = datetime.date.today().strftime('%Y-%m-%d')
        my_leads = db_query('SELECT * FROM customer_leads WHERE assign_shop_id=?', (shop_id,))
        my_leads = clean_score_column(my_leads)
        today_new = my_leads[my_leads['assign_time'].astype(str).str.startswith(today)]
        high_val = my_leads[my_leads['is_high_value'].fillna(0) == 1]
        st.subheader('📌 今日重点指标')
        col1, col2, col3, col4 = st.columns(4)
        col1.metric('今日新线索', len(today_new))
        col2.metric('高价值线索', len(high_val))
        col3.metric('待跟进线索', len(my_leads[my_leads['lead_status'] == 'untouch']))
        col4.metric('已成交', len(my_leads[my_leads['lead_status'] == 'deal']))
        st.divider()
        st.subheader('🏬 门店经营看板')
        col1, col2, col3, col4 = st.columns(4)
        col1.metric('总线索数', len(my_leads))
        col2.metric('今日新增', len(today_new))
        col3.metric('高价值线索', len(high_val))
        col4.metric('外呼总次数', len(db_query('SELECT * FROM call_record WHERE shop_id=?', (shop_id,))))
        lv = my_leads['lead_level'].value_counts().reset_index()
        lv.columns = ['等级', '数量']
        bar_chart(lv, x='等级', y='数量')
        st.subheader('🔥 高优先级线索')
        top = db_query("SELECT l.id,l.phone,l.customer_name,l.city,l.total_score,l.lead_level,l.user_tags,l.consult_content,l.lead_status,l.first_contact_time,COALESCE(cr_count.cnt,0) as call_count FROM customer_leads l LEFT JOIN (SELECT lead_id,COUNT(*) as cnt FROM call_record GROUP BY lead_id) cr_count ON l.id=cr_count.lead_id WHERE l.assign_shop_id=? ORDER BY l.total_score DESC LIMIT 10", (shop_id,))
        top = clean_score_column(top)
        if len(top) > 0:
            top['线索状态'] = top['lead_status'].apply(status_to_cn)
        top = top.rename(columns={'id': '线索ID', 'phone': '手机号', 'customer_name': '客户姓名', 'city': '所在城市', 'total_score': 'AI评分', 'lead_level': '线索等级', 'user_tags': '用户标签', 'consult_content': '咨询内容', 'first_contact_time': '首次接触时间', 'call_count': '外呼次数'})
        st.dataframe(top, use_container_width=True)

    elif menu == '📁 我的线索池':
        st.header('我的线索池')
        # 使用共享筛选组件
        level_filter, channel_filter, high_value_filter, status_filter, sort_type, search_key = render_lead_filters('seller')

        leads = db_query("SELECT l.id,l.phone,l.customer_name,l.city,l.budget,l.total_score,l.lead_level,l.is_high_value,l.user_tags,l.source_time,l.lead_status,l.first_contact_time,c.channel_name,m.model_name,l.assign_time,l.consult_content,COALESCE(cr_count.cnt,0) as call_count FROM customer_leads l LEFT JOIN channel_dict c ON l.channel_id=c.id LEFT JOIN motorcycle_model m ON l.model_id=m.id LEFT JOIN (SELECT lead_id,COUNT(*) as cnt FROM call_record GROUP BY lead_id) cr_count ON l.id=cr_count.lead_id WHERE l.assign_shop_id=?", (shop_id,))
        leads = clean_score_column(leads)
        filtered = apply_lead_filters(leads, level_filter, channel_filter, high_value_filter, status_filter, sort_type, search_key)

        st.caption(f'共 {len(filtered)} 条线索，当前排序：{sort_type}')
        st.divider()
        for _, row in filtered.iterrows():
            lead_id = int(row['id'])
            high_tag = '⭐ ' if row['is_high_value'] == 1 else ''
            with st.container():
                c1, c2, c3, c4, c5, c6, c7 = st.columns([1, 2, 2, 1.5, 1.5, 1, 3])
                with c1:
                    st.markdown(f'**#{lead_id}**')
                    st.caption(row['channel_name'])
                with c2:
                    st.markdown(f"**{high_tag}{row['customer_name']}**")
                    st.caption(row['phone'])
                with c3:
                    st.write(f"📍 {row['city']}")
                    st.caption(f"车型：{row['model_name']}")
                with c4:
                    st.metric('AI评分', f"{int(row['total_score'])}分", f"{row['lead_level']}级")
                with c5:
                    st.write(f"状态：**{status_to_cn(row['lead_status'])}**")
                    st.caption(f"外呼 {int(row['call_count'])} 次")
                with c6:
                    st.caption(f"首触：{row['first_contact_time'] if row['first_contact_time'] else '未接触'}")
                    st.caption(f"分配：{row['assign_time'][:10] if row['assign_time'] else '-'}")
                with c7:
                    bc1, bc2, bc3 = st.columns(3)
                    with bc1:
                        if st.button('🤖 AI', key=f'call_{lead_id}', use_container_width=True, type='primary'):
                            st.session_state[f'call_open_{lead_id}'] = True
                            st.rerun()
                    with bc2:
                        if st.button('🎙️ 手动', key=f'mcall_{lead_id}', use_container_width=True):
                            st.session_state[f'mcall_open_{lead_id}'] = True
                            st.rerun()
                    with bc3:
                        if st.button('✏️ 编辑', key=f'edit_{lead_id}', use_container_width=True):
                            st.session_state[f'edit_open_{lead_id}'] = True
                            st.rerun()
                with st.expander('查看咨询内容 & 标签'):
                    st.write(f"**咨询内容：** {row['consult_content']}")
                    st.write(f"**用户标签：** {row['user_tags']}")
            st.divider()

        # 弹窗统一在循环外调用，避免 duplicate element ID 和闪退
        for _, row in filtered.iterrows():
            lead_id = int(row['id'])
            if st.session_state.get(f'edit_open_{lead_id}', False):
                dialog_edit_lead(lead_id)
                break
            elif st.session_state.get(f'call_open_{lead_id}', False):
                dialog_call_lead(lead_id, shop_id, sale_id)
                break
            elif st.session_state.get(f'mcall_open_{lead_id}', False):
                dialog_manual_call(lead_id, shop_id, sale_id)
                break

    elif menu == '📞 外呼中心':
        st.header('📞 外呼中心')
        st.markdown('<div class="auto-card">', unsafe_allow_html=True)
        st.write("在此可以进行手动拨号外呼，系统会自动检测号码是否已存在线索档案。")
        st.markdown('</div>', unsafe_allow_html=True)
        dialog_dial_new(shop_id, sale_id)
        st.divider()
        st.subheader("📞 最近外呼记录")
        start_t, end_t = render_time_filter("shop_calls")
        calls = db_query("SELECT cr.*, cl.phone, cl.customer_name FROM call_record cr LEFT JOIN customer_leads cl ON cr.lead_id=cl.id WHERE cr.shop_id=? AND cr.create_time BETWEEN ? AND ? ORDER BY cr.create_time DESC LIMIT 20", (shop_id, start_t, end_t))
        if len(calls) > 0:
            calls['create_time'] = calls['create_time'].astype(str).str[:16]
            calls_disp = calls[['customer_name', 'phone', 'call_duration', 'score_after_call', 'level_after_call', 'create_time']].rename(columns={'customer_name': '客户姓名', 'phone': '手机号', 'call_duration': '时长(秒)', 'score_after_call': '通话后评分', 'level_after_call': '通话后等级', 'create_time': '时间'})
            st.dataframe(calls_disp, use_container_width=True, hide_index=True)
        else:
            st.info("暂无外呼记录")

    elif menu == '🔻 销售漏斗看板':
        render_funnel_dashboard(viewer_type='seller')

    elif menu == '📈 门店数据看板':
        st.header('📈 门店数据看板')
        start_t, end_t = render_time_filter("shop_dashboard")
        # 核心指标
        my_leads = db_query("SELECT * FROM customer_leads WHERE assign_shop_id=?", (shop_id,))
        my_leads = clean_score_column(my_leads)
        period_leads = db_query("SELECT * FROM customer_leads WHERE assign_shop_id=? AND assign_time BETWEEN ? AND ?", (shop_id, start_t, end_t))
        period_leads = clean_score_column(period_leads)
        st.subheader('📌 核心指标')
        col1, col2, col3, col4 = st.columns(4)
        col1.metric('总线索数', len(my_leads))
        col2.metric('周期新增', len(period_leads))
        col3.metric('高价值线索', len(my_leads[my_leads['is_high_value'].fillna(0) == 1]))
        col4.metric('已成交', len(my_leads[my_leads['lead_status'] == 'deal']))
        st.divider()
        # 等级分布
        st.subheader('🏷️ 线索等级分布')
        lv = my_leads['lead_level'].value_counts().reset_index()
        lv.columns = ['等级', '数量']
        bar_chart(lv, x='等级', y='数量')
        st.divider()
        # 周期外呼统计
        st.subheader('📞 周期外呼统计')
        period_calls = db_query("SELECT * FROM call_record WHERE shop_id=? AND create_time BETWEEN ? AND ?", (shop_id, start_t, end_t))
        if len(period_calls) > 0:
            col1, col2, col3 = st.columns(3)
            col1.metric('外呼次数', len(period_calls))
            col2.metric('平均评分变化', round(period_calls['score_after_call'].mean(), 1))
            col3.metric('总通话时长(秒)', int(period_calls['call_duration'].sum()))
            # 评分变化趋势
            period_calls['dt'] = period_calls['create_time'].astype(str).str[:10]
            trend = period_calls.groupby('dt')['score_after_call'].mean().reset_index()
            trend.columns = ['日期', '平均评分']
            line_chart(trend, x='日期', y='平均评分', color='#1890ff')
        else:
            st.info('本周期暂无外呼记录')


# ========================== 登录页 ==========================
def login_page():
    st.title('AI潜客线索CRM系统')
    st.caption('工厂管理端 · 商家操作端 一体化系统')
    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader('账号登录')
        username = st.text_input('账号')
        pwd = st.text_input('密码', type='password')
        if st.button('登录', type='primary'):
            pwd_hash = hashlib.sha256(pwd.encode()).hexdigest()[:16]
            user = db_query('SELECT * FROM sys_user WHERE username=? AND password=?', (username, pwd_hash))
            if len(user) > 0:
                st.session_state['user'] = user.iloc[0].to_dict()
                st.rerun()
            else:
                st.error('账号密码错误')
    with col2:
        st.subheader('演示账号')
        st.info('工厂管理员：admin / 123456\n重庆A店商家：shop_a / 123456\n成都B店商家：shop_b / 123456')


# ========================== 主入口 ==========================
if __name__ == '__main__':
    init_db_once()
    if 'user' not in st.session_state:
        login_page()
    else:
        user = st.session_state.get('user')
        if user is None:
            st.error('会话已过期，请重新登录')
            st.rerun()
        if st.sidebar.button('退出登录'):
            del st.session_state['user']
            st.rerun()
        if user['role'] == 'admin':
            factory_admin()
        else:
            shop_seller()
