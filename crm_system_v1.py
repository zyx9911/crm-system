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
.dashboard-card {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 12px; padding: 20px; color: white; text-align: center;
    margin-bottom: 16px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    transition: transform 0.3s ease;
}
.dashboard-card:hover {transform: translateY(-2px);}
.dashboard-card .metric-value {font-size: 32px; font-weight: bold; margin: 8px 0;}
.dashboard-card .metric-label {font-size: 14px; opacity: 0.9;}
.dashboard-card .metric-change {font-size: 12px; margin-top: 4px;}
.health-good {background: linear-gradient(135deg, #52c41a 0%, #389e0d 100%) !important;}
.health-warning {background: linear-gradient(135deg, #faad14 0%, #d46b08 100%) !important;}
.health-danger {background: linear-gradient(135deg, #ff4d4f 0%, #cf1322 100%) !important;}
.health-info {background: linear-gradient(135deg, #1890ff 0%, #096dd9 100%) !important;}
.health-purple {background: linear-gradient(135deg, #722ed1 0%, #531dab 100%) !important;}
.health-cyan {background: linear-gradient(135deg, #13c2c2 0%, #08979c 100%) !important;}
.dashboard-section {
    background: #fff; border-radius: 12px; padding: 20px;
    margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    border: 1px solid #f0f0f0;
}
.dashboard-title {
    font-size: 18px; font-weight: bold; color: #003366;
    margin-bottom: 16px; padding-left: 12px;
    border-left: 4px solid #1890ff;
}
</style>
''', unsafe_allow_html=True)

STATUS_MAP = {
    'untouch': '待跟进', 'contacted': '已建联', 'reserve_test': '预约试驾',
    'bargain': '议价中', 'deal': '已成交', 'lost': '已流失'
}
SORT_OPTIONS = ['按AI评分降序', '按留资时间降序', '按序号升序', '按线索等级排序']

# ================== 数据库工具 ==================
def get_conn():
    return sqlite3.connect('crm_demo.db')

def db_query(sql, params=()):
    conn = None
    try:
        conn = get_conn()
        df = pd.read_sql(sql, conn, params=params)
        return df
    except Exception as e:
        st.error(f'数据库查询异常: {e}')
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()

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
        if conn:
            conn.close()

def clean_score(score_val):
    if score_val is None:
        return 0
    try:
        return int(float(str(score_val).strip()))
    except:
        return 0

def clean_score_column(df, col='total_score'):
    df[col] = df[col].apply(clean_score)
    return df

def status_to_cn(s):
    return STATUS_MAP.get(s, s)

# ================== 初始化数据库 ==================
@st.cache_resource
def init_db_once():
    db_path = 'crm_demo.db'
    first_run = not os.path.exists(db_path)
    conn = get_conn()
    c = conn.cursor()
    # 建表
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
        c.execute("INSERT INTO sys_user(username,password,real_name,role,shop_id) VALUES ('admin',?,'工厂管理员','admin',NULL),('shop_a',?,'重庆店销售','sale',1),('shop_b',?,'成都店销售','sale',2)", (hash_pwd('123456'), hash_pwd('123456'), hash_pwd('123456')))
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

# ================== 核心AI功能 ==================
def calculate_lead_score(channel_weight, info_full, consult_text, behavior_count=1, source_time=None):
    conn = get_conn()
    c = conn.cursor()
    rule = c.execute('SELECT * FROM score_rule').fetchone()
    cfg = c.execute('SELECT * FROM level_config').fetchone()
    keywords = c.execute('SELECT keyword,score_change FROM intent_keyword').fetchall()
    conn.close()
    if rule is None:
        rule = (0, 20, 10, 25, 10, -15, 10, 10)
    if cfg is None:
        cfg = (0, 75, 50, 30, 80)
    score = int(channel_weight)
    if info_full:
        score += int(rule[1])
    time_bonus = 0
    if source_time is not None:
        try:
            source_dt = pd.to_datetime(source_time, errors='coerce')
            if pd.notna(source_dt):
                days_ago = (datetime.datetime.now() - source_dt).days
                if days_ago < 0:
                    time_bonus = 0
                elif days_ago <= 3:
                    time_bonus = int(rule[2])
                elif days_ago <= 7:
                    time_bonus = int(int(rule[2]) * 0.6)
                elif days_ago <= 30:
                    time_bonus = int(int(rule[2]) * 0.3)
        except Exception:
            pass
    score += time_bonus
    for kw, delta in keywords:
        if kw in consult_text:
            score += int(delta)
    score += min(int(behavior_count) * 2, int(rule[6]))
    if any(char.isdigit() for char in consult_text):
        score += int(rule[7])
    score = int(max(0, min(score, 100)))
    a_min, b_min, c_min, high_val = int(cfg[1]), int(cfg[2]), int(cfg[3]), int(cfg[4])
    if score >= a_min:
        level = 'A'
    elif score >= b_min:
        level = 'B'
    elif score >= c_min:
        level = 'C'
    else:
        level = 'D'
    is_high = 1 if score >= high_val else 0
    return score, level, is_high

def ai_generate_tags(consult_text, budget, city):
    tags = []
    if budget:
        try:
            num_str = ''.join([c for c in budget if c.isdigit() or c == '.'])
            if num_str:
                budget_amount = float(num_str)
                if '万' in budget:
                    budget_amount *= 10000
                if budget_amount >= 30000:
                    tags.append('高购买力')
                elif budget_amount >= 15000:
                    tags.append('中购买力')
                else:
                    tags.append('入门预算')
        except Exception:
            tags.append('入门预算')
    else:
        tags.append('入门预算')
    high_words = ['现车', '试驾', '订车', '置换']
    for w in high_words:
        if w in consult_text:
            tags.append('强购车意向')
            break
    if '重庆' in city or '万州' in city or '涪陵' in city:
        tags.append('渝川大区')
    elif '成都' in city or '绵阳' in city or '德阳' in city or '宜宾' in city or '泸州' in city:
        tags.append('渝川大区')
    if '通勤' in consult_text or '代步' in consult_text:
        tags.append('通勤代步需求')
    if '摩旅' in consult_text or '续航' in consult_text:
        tags.append('摩旅出行需求')
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
                    if tag:
                        tags_to_add.append(tag)
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
        score_bonus += 5
        summary_parts.append('关注性能/配置')
    if any(w in content_lower for w in ['置换','金融','分期','贷款']):
        score_bonus += 5
        tags_to_add.append('金融/置换需求')
        summary_parts.append('关注金融/置换')

    old_score = clean_score(lead.get('total_score', 0))
    new_score = max(0, min(100, old_score + score_bonus))
    conn = get_conn()
    cfg = conn.execute('SELECT * FROM level_config').fetchone()
    conn.close()
    if cfg is None:
        cfg = (0, 75, 50, 30, 80)
    a_min, b_min, c_min, high_val = int(cfg[1]), int(cfg[2]), int(cfg[3]), int(cfg[4])
    if new_score >= a_min:
        new_level = 'A'
    elif new_score >= b_min:
        new_level = 'B'
    elif new_score >= c_min:
        new_level = 'C'
    else:
        new_level = 'D'
    new_is_high = 1 if new_score >= high_val else 0

    old_tags = str(lead.get('user_tags', '')).split(',') if lead.get('user_tags') else []
    old_tags = [t for t in old_tags if t and t != '普通潜客']
    combined_tags = list(dict.fromkeys(old_tags + tags_to_add))
    new_tags = ','.join(combined_tags) if combined_tags else '普通潜客'

    summary_text = '；'.join(summary_parts) if summary_parts else '通话已建立'
    ai_summary = f'{summary_text}。AI评分变化：{old_score}→{new_score}'
    if status_suggestion:
        ai_summary += f'，建议状态：{STATUS_MAP.get(status_suggestion, status_suggestion)}'
    return new_score, new_level, new_is_high, new_tags, status_suggestion, ai_summary

def extract_info_from_call(transcript, lead):
    info = {
        "budget": lead.get("budget", ""),
        "model_interest": lead.get("model_id", None),
        "intent_level": "中",
        "next_follow_date": "",
        "key_points": [],
        "objections": [],
        "recommended_action": "继续跟进"
    }
    t = transcript.lower()
    import re
    budget_patterns = [
        r'(\d+[\.\d]*)\s*万',
        r'预算[大概约]*(\d+[\.\d]*)',
        r'(\d+[\.\d]*)\s*左右',
        r'最多[不超过]*(\d+[\.\d]*)'
    ]
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
    if high_score >= 2:
        info["intent_level"] = "高"
        info["recommended_action"] = "立即推进成交"
    elif mid_score >= 2:
        info["intent_level"] = "中"
        info["recommended_action"] = "预约试驾/到店"
    elif low_score >= 2:
        info["intent_level"] = "低"
        info["recommended_action"] = "长期培育"

    objections = []
    if "贵" in t or "高" in t or "超预算" in t:
        objections.append("价格敏感")
    if "远" in t or "不方便" in t:
        objections.append("距离/便利性")
    if "对比" in t or "别的" in t:
        objections.append("正在对比竞品")
    if "等" in t or "不急" in t:
        objections.append("不急于购买")
    info["objections"] = objections

    if "明天" in t:
        info["next_follow_date"] = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    elif "周末" in t or "周六" in t or "周日" in t:
        today = datetime.datetime.now().weekday()
        if today < 5:
            info["next_follow_date"] = (datetime.datetime.now() + datetime.timedelta(days=5-today)).strftime("%Y-%m-%d")
        else:
            info["next_follow_date"] = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    elif "下周" in t:
        info["next_follow_date"] = (datetime.datetime.now() + datetime.timedelta(days=7)).strftime("%Y-%m-%d")
    return info

# ================== 话术库 ==================
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

def get_ai_speech(scene, model="", budget=""):
    speeches = AI_SPEECH_SCENES.get(scene, ["您好，请问有什么可以帮您？"])
    speech = random.choice(speeches)
    try:
        return speech.format(model=model, budget=budget)
    except (KeyError, IndexError):
        return speech

# ================== 排序与工具 ==================
def sort_leads(df, sort_type):
    if sort_type == '按AI评分降序':
        return df.sort_values('total_score', ascending=False)
    elif sort_type == '按留资时间降序':
        return df.sort_values('source_time', ascending=False)
    elif sort_type == '按序号升序':
        return df.sort_values('id', ascending=True)
    elif sort_type == '按线索等级排序':
        level_order = {'A':0,'B':1,'C':2,'D':3}
        df['level_order'] = df['lead_level'].fillna('D').map(level_order)
        return df.sort_values('level_order', ascending=True).drop(columns=['level_order'])
    return df

def get_province(city):
    if pd.isna(city):
        return '其他'
    city = str(city)
    if any(c in city for c in ['重庆','万州','涪陵']):
        return '重庆市'
    if any(c in city for c in ['成都','宜宾','绵阳','德阳','泸州','南充','自贡']):
        return '四川省'
    return '其他'

def bar_chart(data, x, y, color=None, height=350):
    if USE_PLOTLY:
        fig = px.bar(data, x=x, y=y, color=color, color_discrete_sequence=px.colors.qualitative.Pastel)
        fig.update_layout(margin=dict(l=20,r=20,t=30,b=20), height=height)
        st.plotly_chart(fig, use_container_width=True, config={'scrollZoom':False,'displayModeBar':False})
    else:
        st.bar_chart(data[[x,y]].set_index(x), use_container_width=True)

def line_chart(data, x, y, color=None, height=300):
    if USE_PLOTLY:
        fig = px.line(data, x=x, y=y, color_discrete_sequence=[color] if color else None)
        fig.update_layout(margin=dict(l=20,r=20,t=30,b=20), height=height)
        st.plotly_chart(fig, use_container_width=True, config={'scrollZoom':False,'displayModeBar':False})
    else:
        st.line_chart(data[[x,y]].set_index(x), use_container_width=True)

# ================== 数据生成与导入导出 ==================
NAME_POOL = ['王先生','李女士','张先生','陈女士','刘先生','杨女士','黄先生','周女士','吴先生','赵女士','郑先生','孙女士','马先生','朱女士','胡先生','林女士','郭先生','何女士','高先生','罗女士']
CITY_POOL = ['重庆','成都','万州','涪陵','宜宾','绵阳','德阳','泸州','南充','自贡']
PHONE_PREFIX = ['138','139','137','136','135','150','151','152','158','159','188','189']
CONSULT_TEMPLATES = ['想了解{model}有没有现车，近期想试驾','咨询{model}的配置和油耗，日常通勤用','{model}有置换补贴吗？打算近期订车','问下{model}的落地价，预算{budget}左右','对比了几款车，想了解{model}的售后保养政策','摩旅用，想问问{model}动力和续航怎么样','新手代步，预算{budget}，推荐一下车型','随便看看，先了解下{model}的价格','等新款好久了，{model}什么时候上市？','有现车的话周末就过来订，{model}有优惠吗','旧车想置换，问下{model}的置换政策','上下班代步，{model}油耗高不高？']
BUDGET_POOL = ['1万出头','1.5万左右','2万以内','2-3万','3万以上','预算不多']
MODEL_POOL = ['RT150S','AQS250','RX500']

def _get_existing_phones():
    try:
        df = db_query('SELECT phone FROM customer_leads')
        return set(df['phone'].dropna().astype(str))
    except Exception:
        return set()

def generate_random_lead():
    name = random.choice(NAME_POOL)
    existing_phones = _get_existing_phones()
    max_attempts = 100
    phone = None
    for _ in range(max_attempts):
        phone = random.choice(PHONE_PREFIX) + ''.join(random.choices(string.digits, k=8))
        if phone not in existing_phones:
            break
    else:
        phone = random.choice(PHONE_PREFIX) + str(int(time.time()))[-8:]
    city = random.choice(CITY_POOL)
    budget = random.choice(BUDGET_POOL)
    model_name = random.choice(MODEL_POOL)
    model_id = 1 if model_name == 'RT150S' else (2 if model_name == 'AQS250' else 3)
    template = random.choice(CONSULT_TEMPLATES)
    consult = template.format(model=model_name, budget=budget)
    return phone, name, city, budget, model_id, consult

def auto_crawl_leads():
    channels_df = db_query("SELECT id,weight FROM channel_dict WHERE channel_name!='批量导入'")
    if len(channels_df) == 0:
        # 默认使用批量导入渠道
        channels_df = pd.DataFrame([{'id':7, 'weight':10}])
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    count = random.randint(2,4)
    success = 0
    for _ in range(count):
        ch = channels_df.sample(1).iloc[0]
        phone,name,city,budget,model_id,consult = generate_random_lead()
        full = bool(phone and name and city and len(str(phone))>=7 and len(str(name))>=1 and len(str(city))>=1)
        score, level, high_val = calculate_lead_score(int(ch['weight']), full, consult, source_time=now)
        tags = ai_generate_tags(consult, budget, city)
        if db_exec('INSERT INTO customer_leads(phone,customer_name,city,budget,model_id,channel_id,consult_content,source_time,latest_source_time,total_score,lead_level,is_high_value,user_tags,lead_status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                   (phone,name,city,budget,int(model_id),int(ch['id']),consult,now,now,int(score),level,int(high_val),tags,'untouch')):
            success += 1
    return success

def execute_distribute():
    unassign = db_query('SELECT * FROM customer_leads WHERE assign_shop_id IS NULL')
    sales = db_query("SELECT id,shop_id FROM sys_user WHERE role='sale'")
    shop_sale_map = {}
    for _, s in sales.iterrows():
        shop_sale_map[s['shop_id']] = s['id']
    cd_cities = ['成都','绵阳','德阳','宜宾','泸州','南充','自贡']
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    count = 0
    for _, lead in unassign.iterrows():
        city = lead['city'] or ''
        match_shop_id = 1
        if city:
            for c in cd_cities:
                if c in str(city):
                    match_shop_id = 2
                    break
        sale_id = shop_sale_map.get(match_shop_id)
        if sale_id is None:
            continue  # 跳过无销售的门店
        if db_exec('UPDATE customer_leads SET assign_shop_id=?,assign_sale_id=?,assign_time=? WHERE id=?',
                   (match_shop_id, sale_id, now, lead['id'])):
            count += 1
    return count

def get_excel_template():
    df = pd.DataFrame(columns=['手机号','客户姓名','城市','预算','意向车型','咨询内容'])
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as w:
        df.to_excel(w, index=False, sheet_name='线索导入模板')
    buffer.seek(0)
    return buffer

def export_leads_excel(df):
    try:
        if df is None or len(df) == 0:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as w:
                pd.DataFrame().to_excel(w, index=False, sheet_name='线索列表')
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
        with pd.ExcelWriter(buffer, engine='openpyxl') as w:
            export_df.to_excel(w, index=False, sheet_name='线索列表')
        buffer.seek(0)
        return buffer.getvalue()
    except Exception as e:
        st.error(f'导出失败: {e}')
        return b''

# ================== 时间筛选 ==================
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
    preset = "7天"
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

# ================== 定时任务 ==================
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
        crawl_num = auto_crawl_leads()
        dist_num = execute_distribute()
        _update_daily_stats()
        st.session_state['last_auto_run'] = now_time.strftime('%Y-%m-%d %H:%M:%S')
        st.session_state['last_crawl_num'] = crawl_num
        st.session_state['last_dist_num'] = dist_num
        st.session_state['last_auto_crawl_time'] = now_time
    countdown_html = f"""
    <div style='font-size:15px;line-height:1.8'><div style='color:#389e0d;font-weight:bold'>🤖 自动演示模式运行中</div>
    <div>上次执行时间：{st.session_state['last_auto_run']}</div>
    <div>上次新增线索：<b>{st.session_state['last_crawl_num']}</b> 条 | 自动分发：<b>{st.session_state['last_dist_num']}</b> 条</div>
    <div>距离下次自动执行：<span id='autoCountdown' style='color:#d46b08;font-weight:bold'>60</span> 秒</div></div>
    <script>let seconds=60;setInterval(()=>{{seconds--;if(seconds<0)seconds=60;document.getElementById('autoCountdown').innerText=seconds;}},1000);</script>
    """
    st.components.v1.html(countdown_html, height=120)

def _update_daily_stats():
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    leads = db_query('SELECT * FROM customer_leads')
    if len(leads) == 0:
        return
    leads = clean_score_column(leads)
    total = len(leads)
    new_today = len(leads[leads['source_time'].astype(str).str.startswith(today)])
    high = len(leads[leads['is_high_value'].fillna(0)==1])
    contacted = len(leads[leads['lead_status']=='contacted'])
    reserve = len(leads[leads['lead_status']=='reserve_test'])
    bargain = len(leads[leads['lead_status']=='bargain'])
    deal = len(leads[leads['lead_status']=='deal'])
    lost = len(leads[leads['lead_status']=='lost'])
    calls = db_query("SELECT COUNT(*) as cnt FROM call_record WHERE create_time LIKE ?", (f'{today}%',))
    call_count = int(calls.iloc[0]['cnt']) if len(calls)>0 else 0
    call_duration = db_query("SELECT COALESCE(SUM(call_duration),0) as total FROM call_record WHERE create_time LIKE ?", (f'{today}%',))
    total_duration = int(call_duration.iloc[0]['total']) if len(call_duration)>0 else 0
    avg_score = leads['total_score'].mean() if len(leads)>0 else 0
    a_c = len(leads[leads['lead_level']=='A'])
    b_c = len(leads[leads['lead_level']=='B'])
    c_c = len(leads[leads['lead_level']=='C'])
    d_c = len(leads[leads['lead_level']=='D'])
    db_exec('INSERT OR REPLACE INTO daily_stats (date,total_leads,new_leads,high_value_leads,contacted_leads,reserve_test_leads,bargain_leads,deal_leads,lost_leads,call_count,total_call_duration,avg_score,a_level_count,b_level_count,c_level_count,d_level_count) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (today,total,new_today,high,contacted,reserve,bargain,deal,lost,call_count,total_duration,avg_score,a_c,b_c,c_c,d_c))

# ================== 登录 ==================
def login_page():
    st.title('AI潜客线索CRM系统')
    st.caption('工厂管理端 · 商家操作端 一体化系统')
    col1, col2 = st.columns([1,1])
    with col1:
        st.subheader('账号登录')
        username = st.text_input('账号')
        pwd = st.text_input('密码', type='password')
        if st.button('登录', type='primary'):
            pwd_hash = hashlib.sha256(pwd.encode()).hexdigest()[:16]
            user = db_query('SELECT * FROM sys_user WHERE username=? AND password=?', (username, pwd_hash))
            if len(user)>0:
                st.session_state['user'] = user.iloc[0].to_dict()
                st.rerun()
            else:
                st.error('账号密码错误')
    with col2:
        st.subheader('演示账号')
        st.info('工厂管理员：admin / 123456\n重庆A店商家：shop_a / 123456\n成都B店商家：shop_b / 123456')

# ================== 弹窗：编辑线索 ==================
@st.dialog('编辑线索信息')
def dialog_edit_lead(lead_id):
    lead = db_query('SELECT * FROM customer_leads WHERE id=?', (lead_id,))
    if len(lead) == 0:
        st.error('线索不存在')
        return
    lead = lead.iloc[0]
    models = db_query('SELECT id,model_name FROM motorcycle_model')
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input('客户姓名', value=lead['customer_name'] or '')
        phone = st.text_input('手机号', value=lead['phone'])
        city = st.text_input('所在城市', value=lead['city'] or '')
        budget = st.text_input('购车预算', value=lead['budget'] or '')
    with col2:
        model_df = models[models['id']==lead['model_id']]
        cur_model = model_df.iloc[0]['model_name'] if len(model_df)>0 else models.iloc[0]['model_name']
        model_names_list = list(models['model_name'])
        try:
            model_idx = model_names_list.index(cur_model)
        except ValueError:
            model_idx = 0
        model_name = st.selectbox('意向车型', model_names_list, index=model_idx)
        status_list = list(STATUS_MAP.values())
        cur_status = status_to_cn(lead['lead_status'])
        status_cn = st.selectbox('线索状态', status_list, index=status_list.index(cur_status))
        tags = st.text_input('用户标签', value=lead['user_tags'] or '')
    content = st.text_area('咨询/跟进内容', value=lead['consult_content'] or '', height=120)
    col1, col2 = st.columns(2)
    with col1:
        if st.button('取消', use_container_width=True):
            st.session_state.pop(f'edit_open_{lead_id}', None)
            st.rerun()
    with col2:
        if st.button('保存修改', type='primary', use_container_width=True):
            exist = db_query('SELECT id FROM customer_leads WHERE phone=? AND id!=?', (phone, lead_id))
            if len(exist)>0:
                st.error('该手机号已存在，无法修改')
                return
            status_matches = [k for k,v in STATUS_MAP.items() if v==status_cn]
            status_code = status_matches[0] if status_matches else lead['lead_status']
            model_match = models[models['model_name']==model_name]
            model_id = int(model_match['id'].iloc[0]) if len(model_match)>0 else (lead['model_id'] or 1)
            db_exec('UPDATE customer_leads SET customer_name=?,phone=?,city=?,budget=?,model_id=?,lead_status=?,consult_content=?,user_tags=? WHERE id=?',
                    (name, phone, city, budget, model_id, status_code, content, tags, lead_id))
            st.success('线索信息已更新')
            st.session_state.pop(f'edit_open_{lead_id}', None)
            st.rerun()

# ================== 弹窗：AI智能外呼 ==================
@st.dialog("🤖 AI智能外呼", width="large")
def dialog_call_lead(lead_id, shop_id, sale_id):
    state_key = f"call_state_{lead_id}"
    start_key = f"call_start_{lead_id}"
    transcript_key = f"call_transcript_{lead_id}"
    ai_info_key = f"call_ai_info_{lead_id}"
    temp_key = "_temp_call_data"

    # 初始化状态
    if state_key not in st.session_state:
        st.session_state[state_key] = "idle"
    if transcript_key not in st.session_state:
        st.session_state[transcript_key] = []
    if ai_info_key not in st.session_state:
        st.session_state[ai_info_key] = None

    lead_row = db_query("SELECT * FROM customer_leads WHERE id=?", (lead_id,))
    if len(lead_row) == 0:
        st.error("线索不存在")
        return
    lead = lead_row.iloc[0]
    old_score = clean_score(lead["total_score"])

    model_name = "未指定"
    if lead["model_id"]:
        mdf = db_query("SELECT model_name FROM motorcycle_model WHERE id=?", (lead["model_id"],))
        if len(mdf) > 0:
            model_name = mdf.iloc[0]["model_name"]

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
        st.caption(f"历史外呼：{len(db_query('SELECT * FROM call_record WHERE lead_id=?', (lead_id,)))} 次")
    st.divider()

    current_state = st.session_state[state_key]

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
        if start_key in st.session_state:
            elapsed = int(time.time() - st.session_state[start_key])
        else:
            elapsed = 0
        timer_html = f"""
        <div style="background:linear-gradient(135deg, #52c41a 0%, #389e0d 100%); color:white; border-radius:12px; padding:15px; text-align:center; margin-bottom:16px;">
            <div style="font-size:14px; opacity:0.9;">⏱️ 通话时长</div>
            <div style="font-size:36px; font-weight:bold; letter-spacing:3px;">{elapsed//60:02d}:{elapsed%60:02d}</div>
            <div style="font-size:12px; margin-top:5px;">🔴 通话中 | AI机器人正在服务</div>
        </div>
        """
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
            st.write("")
            st.write("")
            if st.button("📤 发送", use_container_width=True, type="primary"):
                if user_input.strip():
                    st.session_state[transcript_key].append({"role": "user", "text": user_input.strip(), "time": datetime.datetime.now().strftime("%H:%M:%S")})
                    t_lower = user_input.strip().lower()
                    if any(w in t_lower for w in ["预算", "钱", "价格", "贵", "便宜"]):
                        ai_reply = get_ai_speech("确认预算", model=model_name, budget=lead.get("budget",""))
                    elif any(w in t_lower for w in ["车型", "车", "摩托", "排", "cc"]):
                        ai_reply = get_ai_speech("确认车型", model=model_name, budget=lead.get("budget",""))
                    elif any(w in t_lower for w in ["买", "订", "要", "成交", "确定"]):
                        ai_reply = get_ai_speech("促成成交", model=model_name, budget=lead.get("budget",""))
                    elif any(w in t_lower for w in ["考虑", "想想", "对比", "犹豫"]):
                        ai_reply = get_ai_speech("异议处理", model=model_name, budget=lead.get("budget",""))
                    else:
                        ai_reply = get_ai_speech("确认车型", model=model_name, budget=lead.get("budget",""))
                    st.session_state[transcript_key].append({"role": "ai", "text": ai_reply, "time": datetime.datetime.now().strftime("%H:%M:%S")})
                    st.rerun()

        st.caption("💡 快捷场景：")
        qc1, qc2, qc3, qc4, qc5 = st.columns(5)
        with qc1:
            if st.button("💰 确认预算", use_container_width=True):
                ai_reply = get_ai_speech("确认预算", model=model_name, budget=lead.get("budget",""))
                st.session_state[transcript_key].append({"role": "ai", "text": ai_reply, "time": datetime.datetime.now().strftime("%H:%M:%S")})
                st.rerun()
        with qc2:
            if st.button("🏍️ 确认车型", use_container_width=True):
                ai_reply = get_ai_speech("确认车型", model=model_name, budget=lead.get("budget",""))
                st.session_state[transcript_key].append({"role": "ai", "text": ai_reply, "time": datetime.datetime.now().strftime("%H:%M:%S")})
                st.rerun()
        with qc3:
            if st.button("🎯 促成成交", use_container_width=True):
                ai_reply = get_ai_speech("促成成交", model=model_name, budget=lead.get("budget",""))
                st.session_state[transcript_key].append({"role": "ai", "text": ai_reply, "time": datetime.datetime.now().strftime("%H:%M:%S")})
                st.rerun()
        with qc4:
            if st.button("❓ 异议处理", use_container_width=True):
                ai_reply = get_ai_speech("异议处理", model=model_name, budget=lead.get("budget",""))
                st.session_state[transcript_key].append({"role": "ai", "text": ai_reply, "time": datetime.datetime.now().strftime("%H:%M:%S")})
                st.rerun()
        with qc5:
            if st.button("👋 结束语", use_container_width=True):
                ai_reply = get_ai_speech("结束语", model=model_name, budget=lead.get("budget",""))
                st.session_state[transcript_key].append({"role": "ai", "text": ai_reply, "time": datetime.datetime.now().strftime("%H:%M:%S")})
                st.rerun()

        st.divider()
        col_end1, col_end2 = st.columns([3,1])
        with col_end2:
            if st.button("🔴 挂断并AI分析", type="primary", use_container_width=True):
                st.session_state[state_key] = "analyzing"
                st.rerun()

    elif current_state == "analyzing":
        st.markdown("<div style='text-align:center; padding:20px 0;'><div style='font-size:40px; margin-bottom:15px;'>🧠</div><div style='font-size:18px; font-weight:bold; color:#1890ff;'>AI正在分析通话内容...</div><div style='color:#999; font-size:14px; margin-top:10px;'>自动提取客户意向、预算、车型偏好等关键信息</div></div>", unsafe_allow_html=True)
        with st.spinner("AI分析中..."):
            time.sleep(1.5)
            transcript = st.session_state[transcript_key]
            full_text = " ".join([msg["text"] for msg in transcript])
            ai_info = extract_info_from_call(full_text, lead)
            st.session_state[ai_info_key] = ai_info
            new_score, new_level, new_is_high, new_tags, suggested_status, ai_summary = ai_analyze_call(full_text, lead)
            duration = int(time.time() - st.session_state.get(start_key, time.time()))
            if duration < 1:
                duration = 1
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            db_exec("INSERT INTO call_record(lead_id,shop_id,call_duration,call_content,ai_analysis,score_after_call,level_after_call,create_time) VALUES(?,?,?,?,?,?,?,?)",
                    (lead_id, shop_id, duration, full_text, ai_summary, new_score, new_level, now))
            st.session_state[temp_key] = {
                "lead_id": lead_id, "shop_id": shop_id, "sale_id": sale_id,
                "new_score": new_score, "new_level": new_level, "new_is_high": new_is_high,
                "new_tags": new_tags, "suggested_status": suggested_status,
                "ai_summary": ai_summary, "duration": duration, "now": now,
                "full_text": full_text, "ai_info": ai_info
            }
            st.session_state[state_key] = "ended"
            st.rerun()

    elif current_state == "ended":
        temp_data = st.session_state.get(temp_key, {})
        if not temp_data:
            st.error("数据丢失，请重新拨打")
            return
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
        with col1:
            st.metric("AI评分变化", f"{old_score} → {new_score}", f"{new_level}级")
        with col2:
            st.metric("客户意向等级", ai_info.get("intent_level", "中"))
        with col3:
            st.metric("建议动作", ai_info.get("recommended_action", "继续跟进"))

        st.subheader("🔍 AI自动提取的客户信息")
        col_a, col_b = st.columns(2)
        with col_a:
            new_budget = st.text_input("💰 更新预算", value=ai_info.get("budget", lead.get("budget", "")), key=f"ai_budget_{lead_id}")
            new_model = st.selectbox("🏍️ 更新意向车型", ["RT150S", "AQS250", "RX500"], index=["RT150S", "AQS250", "RX500"].index(model_name) if model_name in ["RT150S", "AQS250", "RX500"] else 0, key=f"ai_model_{lead_id}")
        with col_b:
            next_follow = st.date_input("📅 下次跟进日期", value=datetime.datetime.strptime(ai_info.get("next_follow_date", datetime.datetime.now().strftime("%Y-%m-%d")), "%Y-%m-%d") if ai_info.get("next_follow_date") else datetime.datetime.now(), key=f"ai_follow_{lead_id}")
            new_status = st.selectbox("🔄 更新线索状态", list(STATUS_MAP.values()), index=list(STATUS_MAP.values()).index(status_to_cn(suggested_status)) if status_to_cn(suggested_status) in STATUS_MAP.values() else 0, key=f"ai_status_{lead_id}")

        if ai_info.get("key_points"):
            st.caption("📌 AI识别关键信息：")
            for point in ai_info["key_points"]:
                st.markdown(f"- {point}")
        if ai_info.get("objections"):
            st.caption("⚠️ 客户异议：")
            for obj in ai_info["objections"]:
                st.markdown(f"- {obj}")

        st.text_area("📝 AI通话总结", value=ai_summary, height=100, disabled=True, key=f"ai_summary_{lead_id}")
        st.divider()

        col_confirm1, col_confirm2 = st.columns([1,1])
        with col_confirm1:
            if st.button("❌ 放弃更新", use_container_width=True):
                for key in [state_key, start_key, transcript_key, ai_info_key, temp_key]:
                    st.session_state.pop(key, None)
                st.session_state.pop(f'call_open_{lead_id}', None)
                st.rerun()
        with col_confirm2:
            if st.button("✅ 确认更新线索", type="primary", use_container_width=True):
                status_matches = [k for k,v in STATUS_MAP.items() if v==new_status]
                status_code = status_matches[0] if status_matches else 'contacted'
                model_id = {"RT150S": 1, "AQS250": 2, "RX500": 3}.get(new_model, 1)
                db_exec("UPDATE customer_leads SET total_score=?,lead_level=?,is_high_value=?,user_tags=?,lead_status=?,budget=?,model_id=?,first_contact_time=COALESCE(first_contact_time,?),latest_source_time=?,consult_content=COALESCE(consult_content,'')||? WHERE id=?",
                        (new_score, new_level, temp_data["new_is_high"], temp_data["new_tags"], status_code, new_budget, model_id, temp_data["now"], temp_data["now"], f"\n[AI外呼]{temp_data['full_text'][:200]}...", temp_data["lead_id"]))
                follow_content = f"AI智能外呼 | 时长{duration}秒 | 意向:{ai_info.get('intent_level','中')} | 预算:{new_budget} | 建议:{ai_info.get('recommended_action','继续跟进')}"
                db_exec("INSERT INTO lead_follow_record(lead_id,sale_id,follow_type,follow_content,ai_summary,create_time) VALUES(?,?,?,?,?,?)",
                        (temp_data["lead_id"], temp_data["sale_id"], "AI智能外呼", follow_content, ai_summary, temp_data["now"]))
                for key in [state_key, start_key, transcript_key, ai_info_key, temp_key]:
                    st.session_state.pop(key, None)
                st.session_state.pop(f'call_open_{lead_id}', None)
                st.success("✅ 线索已更新！AI外呼闭环完成")
                time.sleep(1)
                st.rerun()

# ================== 弹窗：手动外呼（针对已有线索）==================
@st.dialog("🎙️ 手动外呼")
def dialog_manual_call(lead_id, shop_id, sale_id):
    lead_row = db_query("SELECT * FROM customer_leads WHERE id=?", (lead_id,))
    if len(lead_row) == 0:
        st.error("线索不存在")
        return
    lead = lead_row.iloc[0]

    state_key = f"manual_call_state_{lead_id}"
    note_key = f"manual_call_note_{lead_id}"
    # 若状态为ended或confirm，重置为idle
    if st.session_state.get(state_key) in ["ended", "confirm"]:
        st.session_state[state_key] = "idle"
    if state_key not in st.session_state:
        st.session_state[state_key] = "idle"
    if note_key not in st.session_state:
        st.session_state[note_key] = ""

    st.subheader(f"🎙️ 手动外呼 - #{lead_id} {lead['customer_name'] or '未知客户'}")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.write(f"**📱 {lead['phone']}**")
        st.caption(f"📍 {lead['city'] or '未知'}")
    with col2:
        st.write(f"预算：{lead['budget'] or '未填写'}")
        st.caption(f"标签：{lead['user_tags'] or '无'}")
    with col3:
        st.write(f"当前评分：**{clean_score(lead['total_score'])}分** ({lead['lead_level']}级)")
        st.caption(f"状态：{status_to_cn(lead['lead_status'])}")

    st.divider()
    state = st.session_state[state_key]

    if state == "idle":
        st.markdown("<div style='text-align:center; padding:30px;'><div style='font-size:50px;'>📞</div></div>", unsafe_allow_html=True)
        if st.button("🟢 开始通话", type="primary", use_container_width=True):
            st.session_state[state_key] = "calling"
            st.rerun()

    elif state == "calling":
        st.markdown("<div style='text-align:center; padding:20px; background:#f0f7ff; border-radius:12px;'><div style='font-size:40px;'>🎙️</div><div style='font-size:20px; font-weight:bold; color:#1890ff;'>通话中...</div></div>", unsafe_allow_html=True)

        widget_key = f"manual_text_widget_{lead_id}"
        if widget_key not in st.session_state:
            st.session_state[widget_key] = st.session_state.get(note_key, "")
        current_widget_value = st.text_area("📝 通话记录/要点", key=widget_key, height=150)
        if widget_key in st.session_state:
            st.session_state[note_key] = st.session_state[widget_key]

        tag_col1, tag_col2, tag_col3, tag_col4 = st.columns(4)
        with tag_col1:
            if st.button("💰 提及预算", key=f"mc_budget_{lead_id}", use_container_width=True):
                st.session_state[note_key] = current_widget_value + " [客户提及预算] "
                st.session_state.pop(widget_key, None)
                st.rerun()
        with tag_col2:
            if st.button("🏍️ 意向车型", key=f"mc_model_{lead_id}", use_container_width=True):
                st.session_state[note_key] = current_widget_value + " [确认意向车型] "
                st.session_state.pop(widget_key, None)
                st.rerun()
        with tag_col3:
            if st.button("📅 预约到店", key=f"mc_book_{lead_id}", use_container_width=True):
                st.session_state[note_key] = current_widget_value + " [预约到店] "
                st.session_state.pop(widget_key, None)
                st.rerun()
        with tag_col4:
            if st.button("❌ 意向降低", key=f"mc_down_{lead_id}", use_container_width=True):
                st.session_state[note_key] = current_widget_value + " [意向降低] "
                st.session_state.pop(widget_key, None)
                st.rerun()

        if st.button("🔴 挂断并AI分析", type="primary", use_container_width=True):
            if not current_widget_value.strip():
                st.warning("请先记录通话内容再挂断")
            else:
                st.session_state[state_key] = "analyzing"
                st.rerun()

    elif state == "analyzing":
        st.markdown("<div style='text-align:center; padding:20px;'><div style='font-size:40px;'>🧠</div><div style='font-size:18px; font-weight:bold; color:#1890ff;'>AI正在分析通话内容...</div></div>", unsafe_allow_html=True)
        with st.spinner("AI分析中..."):
            time.sleep(1.2)
            call_text = st.session_state[note_key]
            ai_info = extract_info_from_call(call_text, lead)
            new_score, new_level, new_is_high, new_tags, suggested_status, ai_summary = ai_analyze_call(call_text, lead)
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            db_exec("INSERT INTO call_record(lead_id,shop_id,call_duration,call_content,ai_analysis,score_after_call,level_after_call,create_time) VALUES(?,?,?,?,?,?,?,?)",
                    (lead_id, shop_id, 0, call_text, ai_summary, new_score, new_level, now))
            st.session_state["_temp_manual_call"] = {
                "lead_id": lead_id, "shop_id": shop_id, "sale_id": sale_id,
                "new_score": new_score, "new_level": new_level, "new_is_high": new_is_high,
                "new_tags": new_tags, "suggested_status": suggested_status,
                "ai_summary": ai_summary, "call_text": call_text, "now": now, "ai_info": ai_info
            }
            st.session_state[state_key] = "confirm"
            st.rerun()

    elif state == "confirm":
        temp = st.session_state.get("_temp_manual_call", {})
        if not temp:
            st.error("分析数据丢失")
            return
        st.subheader("📋 AI 通话分析结果")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("新评分", f"{temp['new_score']}分")
        with c2:
            st.metric("新等级", temp['new_level'])
        with c3:
            st.metric("建议状态", STATUS_MAP.get(temp['suggested_status'], temp['suggested_status'] or '已建联'))
        with c4:
            st.metric("高价值", "是" if temp['new_is_high'] else "否")
        st.write(f"**AI摘要：** {temp['ai_summary']}")
        st.write(f"**新标签：** {temp['new_tags']}")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("❌ 放弃", use_container_width=True):
                for k in [state_key, note_key, "_temp_manual_call"]:
                    st.session_state.pop(k, None)
                st.session_state.pop(f'mcall_open_{lead_id}', None)
                st.rerun()
        with col_b:
            if st.button("✅ 确认更新线索", type="primary", use_container_width=True):
                status_code = temp['suggested_status'] if temp['suggested_status'] else 'contacted'
                model_id = lead.get('model_id', 1)
                db_exec("UPDATE customer_leads SET total_score=?,lead_level=?,is_high_value=?,user_tags=?,lead_status=?,first_contact_time=COALESCE(first_contact_time,?),latest_source_time=?,consult_content=COALESCE(consult_content,'')||? WHERE id=?",
                        (temp['new_score'], temp['new_level'], temp['new_is_high'], temp['new_tags'], status_code, temp['now'], temp['now'], f"\n[手动外呼]{temp['call_text'][:200]}...", temp['lead_id']))
                follow_content = f"手动外呼 | 意向:{temp['ai_info'].get('intent_level','中')} | 建议:{temp['ai_info'].get('recommended_action','继续跟进')}"
                db_exec("INSERT INTO lead_follow_record(lead_id,sale_id,follow_type,follow_content,ai_summary,create_time) VALUES(?,?,?,?,?,?)",
                        (temp['lead_id'], temp['sale_id'], "手动外呼", follow_content, temp['ai_summary'], temp['now']))
                for k in [state_key, note_key, "_temp_manual_call"]:
                    st.session_state.pop(k, None)
                st.session_state.pop(f'mcall_open_{lead_id}', None)
                st.success("✅ 手动外呼闭环完成！线索已更新")
                time.sleep(1)
                st.rerun()

# ================== 弹窗：手动拨号（新/老客户） ==================
@st.dialog("📱 手动拨号中心")
def dialog_dial_new(shop_id, sale_id):
    # 强制重置状态
    dial_state_key = "dial_new_state"
    dial_note_key = "dial_new_note"
    st.session_state[dial_state_key] = "idle"
    if dial_note_key not in st.session_state:
        st.session_state[dial_note_key] = ""

    st.subheader("📱 手动拨号中心")
    col1, col2 = st.columns(2)
    with col1:
        phone = st.text_input("📱 手机号 *", placeholder="输入11位手机号", key="dial_phone")
    with col2:
        name = st.text_input("👤 客户姓名", placeholder="可选，新客户建议填写", key="dial_name")
    col3, col4 = st.columns(2)
    with col3:
        city = st.text_input("📍 城市", placeholder="可选", key="dial_city")
    with col4:
        budget = st.text_input("💰 预算", placeholder="可选", key="dial_budget")

    existing = None
    if phone and len(str(phone).strip()) >= 7:
        exist_df = db_query("SELECT * FROM customer_leads WHERE phone=?", (str(phone).strip(),))
        if len(exist_df) > 0:
            existing = exist_df.iloc[0]
            st.info(f"📌 该号码已有线索档案：{existing['customer_name'] or '未命名'} | {existing['city'] or '未知'} | 当前评分{clean_score(existing['total_score'])}分 | 状态：{status_to_cn(existing['lead_status'])}")

    st.divider()
    state = st.session_state[dial_state_key]

    if state == "idle":
        st.markdown("<div style='text-align:center; padding:30px;'><div style='font-size:50px;'>📞</div></div>", unsafe_allow_html=True)
        if st.button("🟢 开始拨号", type="primary", use_container_width=True):
            phone_clean = str(phone).strip() if phone else ""
            if not phone_clean or len(phone_clean) < 7:
                st.error("请输入有效的手机号")
            else:
                st.session_state[dial_state_key] = "calling"
                st.rerun()

    elif state == "calling":
        st.markdown("<div style='text-align:center; padding:20px; background:#f0f7ff; border-radius:12px;'><div style='font-size:40px;'>🎙️</div><div style='font-size:20px; font-weight:bold; color:#1890ff;'>通话中...</div></div>", unsafe_allow_html=True)

        dial_widget_key = "dial_note_widget"
        if dial_widget_key not in st.session_state:
            st.session_state[dial_widget_key] = st.session_state.get(dial_note_key, "")
        dial_current_value = st.text_area("📝 通话记录", placeholder="记录本次通话要点...", key=dial_widget_key, height=150)
        if dial_widget_key in st.session_state:
            st.session_state[dial_note_key] = st.session_state[dial_widget_key]

        tag_col1, tag_col2, tag_col3, tag_col4 = st.columns(4)
        with tag_col1:
            if st.button("💰 提及预算", key="dial_t1", use_container_width=True):
                st.session_state[dial_note_key] = dial_current_value + " [客户提及预算] "
                st.session_state.pop(dial_widget_key, None)
                st.rerun()
        with tag_col2:
            if st.button("🏍️ 意向车型", key="dial_t2", use_container_width=True):
                st.session_state[dial_note_key] = dial_current_value + " [确认意向车型] "
                st.session_state.pop(dial_widget_key, None)
                st.rerun()
        with tag_col3:
            if st.button("📅 预约到店", key="dial_t3", use_container_width=True):
                st.session_state[dial_note_key] = dial_current_value + " [预约到店] "
                st.session_state.pop(dial_widget_key, None)
                st.rerun()
        with tag_col4:
            if st.button("❌ 意向降低", key="dial_t4", use_container_width=True):
                st.session_state[dial_note_key] = dial_current_value + " [意向降低] "
                st.session_state.pop(dial_widget_key, None)
                st.rerun()

        if st.button("🔴 挂断并AI分析", type="primary", use_container_width=True):
            phone_clean = str(phone).strip() if phone else ""
            if not phone_clean or len(phone_clean) < 7:
                st.error("请输入有效的手机号")
                return
            call_text = dial_current_value
            with st.spinner("AI正在分析通话内容..."):
                time.sleep(1.2)
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if existing is not None:
                    lead = existing
                    ai_info = extract_info_from_call(call_text, lead)
                    new_score, new_level, new_is_high, new_tags, suggested_status, ai_summary = ai_analyze_call(call_text, lead)
                    db_exec("INSERT INTO call_record(lead_id,shop_id,call_duration,call_content,ai_analysis,score_after_call,level_after_call,create_time) VALUES(?,?,?,?,?,?,?,?)",
                            (lead['id'], shop_id, 0, call_text, ai_summary, new_score, new_level, now))
                    status_code = suggested_status if suggested_status else 'contacted'
                    model_id = lead.get('model_id', 1)
                    db_exec("UPDATE customer_leads SET customer_name=COALESCE(?,customer_name),city=COALESCE(?,city),budget=COALESCE(?,budget),total_score=?,lead_level=?,is_high_value=?,user_tags=?,lead_status=?,first_contact_time=COALESCE(first_contact_time,?),latest_source_time=?,consult_content=COALESCE(consult_content,'')||? WHERE id=?",
                            (name or None, city or None, budget or None, new_score, new_level, new_is_high, new_tags, status_code, now, now, f"\n[手动拨号]{call_text[:200]}...", lead['id']))
                    follow_content = f"手动拨号外呼 | 意向:{ai_info.get('intent_level','中')} | 建议:{ai_info.get('recommended_action','继续跟进')}"
                    db_exec("INSERT INTO lead_follow_record(lead_id,sale_id,follow_type,follow_content,ai_summary,create_time) VALUES(?,?,?,?,?,?)",
                            (lead['id'], sale_id, "手动拨号", follow_content, ai_summary, now))
                    st.success(f"✅ 已有线索 #{lead['id']} 已更新！")
                else:
                    channel_df = db_query("SELECT id,weight FROM channel_dict WHERE channel_name='批量导入'")
                    if len(channel_df) == 0:
                        channel_id, ch_weight = 7, 10
                    else:
                        channel_id = int(channel_df.iloc[0]['id'])
                        ch_weight = int(channel_df.iloc[0]['weight'])
                    full = bool(phone_clean and name and city and len(str(name))>=1 and len(str(city))>=1)
                    consult = call_text if call_text.strip() else "手动拨号获客"
                    score, level, high_val = calculate_lead_score(ch_weight, full, consult, source_time=now)
                    tags = ai_generate_tags(consult, budget, city)
                    db_exec('INSERT INTO customer_leads(phone,customer_name,city,budget,channel_id,consult_content,source_time,latest_source_time,total_score,lead_level,is_high_value,user_tags,lead_status,assign_shop_id,assign_sale_id,assign_time) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                            (phone_clean, name, city, budget, channel_id, consult, now, now, int(score), level, int(high_val), tags, 'untouch', shop_id, sale_id, now))
                    new_lead = db_query("SELECT id FROM customer_leads WHERE phone=? ORDER BY id DESC LIMIT 1", (phone_clean,))
                    if len(new_lead) > 0:
                        new_lead_id = int(new_lead.iloc[0]['id'])
                        db_exec("INSERT INTO call_record(lead_id,shop_id,call_duration,call_content,ai_analysis,score_after_call,level_after_call,create_time) VALUES(?,?,?,?,?,?,?,?)",
                                (new_lead_id, shop_id, 0, call_text, f"手动拨号创建新线索 | 评分:{score} | 等级:{level}", score, level, now))
                        st.success(f"✅ 新线索 #{new_lead_id} 已创建并分配至本店！")
                for k in ["dial_phone", "dial_name", "dial_city", "dial_budget", dial_widget_key, dial_note_key, dial_state_key]:
                    st.session_state.pop(k, None)
                time.sleep(1.5)
                st.rerun()

# ================== 弹窗：手动新增线索 ==================
@st.dialog('手动新增线索')
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
    col1, col2 = st.columns(2)
    with col1:
        if st.button('取消'):
            st.rerun()
    with col2:
        if st.button('提交并AI评级', type='primary'):
            if not phone.strip():
                st.error('手机号不能为空')
                return
            ch_row = channels[channels['channel_name']==ch].iloc[0]
            m_row = models[models['model_name']==m].iloc[0]
            full = bool(phone and name and city and len(str(phone))>=7 and len(str(name))>=1 and len(str(city))>=1)
            now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            score, level, high_val = calculate_lead_score(int(ch_row['weight']), full, content, source_time=now_str)
            tags = ai_generate_tags(content, budget, city)
            if db_exec('INSERT INTO customer_leads(phone,customer_name,city,budget,model_id,channel_id,consult_content,source_time,latest_source_time,total_score,lead_level,is_high_value,user_tags,lead_status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                       (phone, name, city, budget, int(m_row['id']), int(ch_row['id']), content, now_str, now_str, int(score), level, int(high_val), tags, 'untouch')):
                st.success('录入成功！')
                st.rerun()
            else:
                st.error('录入失败，手机号可能已存在')

# ================== 弹窗：批量导入 ==================
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
            st.error(f'导入文件缺少必要列：{", ".join(missing)}，请下载模板并按要求填写。')
        else:
            st.write('数据预览：')
            st.dataframe(df.head(), use_container_width=True)
            if st.button('确认导入并AI批量评级', type='primary'):
                channels = db_query("SELECT id,weight FROM channel_dict WHERE channel_name='批量导入'")
                if len(channels) == 0:
                    st.error('批量导入渠道未配置')
                    return
                channels = channels.iloc[0]
                models = db_query('SELECT id,model_name FROM motorcycle_model')
                success = 0
                fail = 0
                now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                for _, row in df.iterrows():
                    try:
                        phone = str(row['手机号']).strip()
                        if '.' in phone:
                            phone = phone.split('.')[0]
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
                        if db_exec('INSERT INTO customer_leads(phone,customer_name,city,budget,model_id,channel_id,consult_content,source_time,latest_source_time,total_score,lead_level,is_high_value,user_tags,lead_status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                                   (phone, name, city, budget, model_id, int(channels['id']), content, now_str, now_str, int(score), level, int(high_val), tags, 'untouch')):
                            success += 1
                        else:
                            fail += 1
                    except Exception as e:
                        st.warning(f'导入单条失败: {e}')
                        fail += 1
                st.success(f'导入完成：成功{success}条，失败{fail}条')
                st.rerun()

# ================== 实时数据大屏 ==================
def render_metric_card(label, value, change=None, change_type='up', css_class=''):
    change_html = ''
    if change is not None:
        arrow = '▲' if change_type == 'up' else '▼'
        color = '#52c41a' if change_type == 'up' else '#ff4d4f'
        change_html = f'<div class="metric-change" style="color:{color}">{arrow} {change}%</div>'
    html = f'<div class="dashboard-card {css_class}"><div class="metric-label">{label}</div><div class="metric-value">{value}</div>{change_html}</div>'
    st.markdown(html, unsafe_allow_html=True)

def get_today_stats():
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    leads = db_query('SELECT * FROM customer_leads')
    if len(leads) == 0:
        return {}
    leads = clean_score_column(leads)
    today_new = len(leads[leads['source_time'].astype(str).str.startswith(today)])
    total = len(leads)
    high = len(leads[leads['is_high_value'].fillna(0)==1])
    contacted = len(leads[leads['lead_status']=='contacted'])
    reserve = len(leads[leads['lead_status']=='reserve_test'])
    bargain = len(leads[leads['lead_status']=='bargain'])
    deal = len(leads[leads['lead_status']=='deal'])
    lost = len(leads[leads['lead_status']=='lost'])
    untouch = len(leads[leads['lead_status']=='untouch'])
    calls = db_query("SELECT COUNT(*) as cnt FROM call_record WHERE create_time LIKE ?", (f'{today}%',))
    call_count = int(calls.iloc[0]['cnt']) if len(calls)>0 else 0
    call_duration = db_query("SELECT COALESCE(SUM(call_duration),0) as total FROM call_record WHERE create_time LIKE ?", (f'{today}%',))
    total_duration = int(call_duration.iloc[0]['total']) if len(call_duration)>0 else 0
    avg_score = round(leads['total_score'].mean(), 1) if len(leads)>0 else 0
    a_c = len(leads[leads['lead_level']=='A'])
    b_c = len(leads[leads['lead_level']=='B'])
    c_c = len(leads[leads['lead_level']=='C'])
    d_c = len(leads[leads['lead_level']=='D'])
    return {'total': total, 'today_new': today_new, 'high': high, 'contacted': contacted, 'reserve': reserve, 'bargain': bargain, 'deal': deal, 'lost': lost, 'untouch': untouch, 'calls': call_count, 'duration': total_duration, 'avg_score': avg_score, 'a': a_c, 'b': b_c, 'c': c_c, 'd': d_c}

def get_historical_stats(days=30):
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=days)
    df = db_query('SELECT * FROM daily_stats WHERE date >= ? AND date <= ? ORDER BY date',
                  (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
    if len(df) == 0:
        return pd.DataFrame()
    df['date'] = pd.to_datetime(df['date'])
    return df

def calculate_yoy_mom():
    today = datetime.datetime.now()
    yesterday = today - datetime.timedelta(days=1)
    last_week = today - datetime.timedelta(days=7)
    last_month = today - datetime.timedelta(days=30)
    today_str = today.strftime('%Y-%m-%d')
    yesterday_str = yesterday.strftime('%Y-%m-%d')
    last_week_str = last_week.strftime('%Y-%m-%d')
    last_month_str = last_month.strftime('%Y-%m-%d')
    today_stats = db_query('SELECT * FROM daily_stats WHERE date = ?', (today_str,))
    yesterday_stats = db_query('SELECT * FROM daily_stats WHERE date = ?', (yesterday_str,))
    last_week_stats = db_query('SELECT * FROM daily_stats WHERE date = ?', (last_week_str,))
    last_month_stats = db_query('SELECT * FROM daily_stats WHERE date = ?', (last_month_str,))

    def get_val(df, col, default=0):
        if len(df) == 0:
            return default
        return df.iloc[0][col]

    def calc_change(current, previous):
        if previous == 0:
            return 0
        return round((current - previous) / previous * 100, 1)

    metrics = ['total_leads', 'new_leads', 'high_value_leads', 'deal_leads', 'call_count', 'avg_score']
    result = {}
    for m in metrics:
        current = get_val(today_stats, m)
        day_before = get_val(yesterday_stats, m)
        week_before = get_val(last_week_stats, m)
        month_before = get_val(last_month_stats, m)
        result[m] = {'current': current, 'day_change': calc_change(current, day_before),
                     'week_change': calc_change(current, week_before),
                     'month_change': calc_change(current, month_before)}
    return result

def real_time_dashboard(start_t=None, end_t=None):
    st.header('📊 实时数据大屏')
    if start_t is None or end_t is None:
        start_t, end_t = render_time_filter('dashboard')
    stats = get_today_stats()
    if not stats:
        st.warning('暂无线索数据，请先导入或生成线索')
        return
    yoy_mom = calculate_yoy_mom()

    st.markdown('<div class="dashboard-section">', unsafe_allow_html=True)
    col_title, col_btn = st.columns([4, 1])
    with col_title:
        st.markdown('<div class="dashboard-title">📈 整体数据看板</div>', unsafe_allow_html=True)
    with col_btn:
        if st.button('查看更多 ➡', key='dash_overview_btn'):
            st.session_state['admin_current_menu'] = '📋 线索管理总览'
            st.rerun()
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        change = yoy_mom.get('total_leads', {}).get('day_change', 0)
        change_type = 'up' if change >= 0 else 'down'
        render_metric_card('总线索数', stats['total'], abs(change), change_type, 'health-info')
    with c2:
        change = yoy_mom.get('new_leads', {}).get('day_change', 0)
        change_type = 'up' if change >= 0 else 'down'
        render_metric_card('今日新增', stats['today_new'], abs(change), change_type, 'health-good')
    with c3:
        change = yoy_mom.get('high_value_leads', {}).get('day_change', 0)
        change_type = 'up' if change >= 0 else 'down'
        render_metric_card('高价值线索', stats['high'], abs(change), change_type, 'health-purple')
    with c4:
        change = yoy_mom.get('deal_leads', {}).get('day_change', 0)
        change_type = 'up' if change >= 0 else 'down'
        render_metric_card('已成交', stats['deal'], abs(change), change_type, 'health-cyan')
    with c5:
        render_metric_card('外呼次数', stats['calls'], css_class='health-warning')
    with c6:
        mins = stats['duration'] // 60
        render_metric_card('通话时长', f'{mins}分', css_class='health-danger')

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        render_metric_card('待跟进', stats['untouch'], css_class='')
    with c2:
        render_metric_card('已建联', stats['contacted'], css_class='health-info')
    with c3:
        render_metric_card('预约试驾', stats['reserve'], css_class='health-good')
    with c4:
        render_metric_card('议价中', stats['bargain'], css_class='health-warning')
    with c5:
        render_metric_card('已流失', stats['lost'], css_class='health-danger')
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="dashboard-section">', unsafe_allow_html=True)
    col_title, col_btn = st.columns([4, 1])
    with col_title:
        st.markdown('<div class="dashboard-title">🩺 线索健康度看板</div>', unsafe_allow_html=True)
    with col_btn:
        if st.button('查看详情 ➡', key='dash_health_btn'):
            st.session_state['admin_current_menu'] = '❤️ 线索健康度看板'
            st.rerun()
    col1, col2 = st.columns([1, 2])
    with col1:
        level_data = pd.DataFrame({'等级': ['A级', 'B级', 'C级', 'D级'],
                                   '数量': [stats['a'], stats['b'], stats['c'], stats['d']],
                                   '占比': [round(stats['a']/stats['total']*100, 1) if stats['total']>0 else 0,
                                            round(stats['b']/stats['total']*100, 1) if stats['total']>0 else 0,
                                            round(stats['c']/stats['total']*100, 1) if stats['total']>0 else 0,
                                            round(stats['d']/stats['total']*100, 1) if stats['total']>0 else 0]})
        if USE_PLOTLY:
            fig = go.Figure(data=[go.Pie(labels=level_data['等级'], values=level_data['数量'], hole=0.4,
                                         marker_colors=['#52c41a', '#1890ff', '#faad14', '#ff4d4f'],
                                         textinfo='label+percent', textfont_size=14)])
            fig.update_layout(title='线索等级分布', height=350, showlegend=False, margin=dict(l=20,r=20,t=40,b=20))
            st.plotly_chart(fig, use_container_width=True, config={'scrollZoom':False,'displayModeBar':False})
        else:
            st.bar_chart(level_data.set_index('等级')['数量'])
    with col2:
        total = stats['total']
        if total > 0:
            contact_rate = round(stats['contacted'] / total * 100, 1)
            deal_rate = round(stats['deal'] / total * 100, 1)
            lost_rate = round(stats['lost'] / total * 100, 1)
            high_rate = round(stats['high'] / total * 100, 1)
        else:
            contact_rate = deal_rate = lost_rate = high_rate = 0
        health_metrics = pd.DataFrame({'指标': ['建联率', '成交率', '流失率', '高价值率'],
                                       '数值': [contact_rate, deal_rate, lost_rate, high_rate],
                                       '目标': [80, 15, 10, 25],
                                       '健康度': ['健康' if contact_rate >= 80 else '亚健康' if contact_rate >= 60 else '待培育',
                                                  '健康' if deal_rate >= 15 else '亚健康' if deal_rate >= 8 else '待培育',
                                                  '健康' if lost_rate <= 10 else '亚健康' if lost_rate <= 20 else '待培育',
                                                  '健康' if high_rate >= 25 else '亚健康' if high_rate >= 15 else '待培育']})
        st.subheader('健康度指标')
        for _, row in health_metrics.iterrows():
            col_a, col_b, col_c = st.columns([2, 1, 1])
            with col_a:
                label = row['指标']
                val = row['数值']
                target = row['目标']
                st.write(f'**{label}**: {val}% (目标: {target}%)')
            with col_b:
                color = {'健康': '#52c41a', '亚健康': '#faad14', '待培育': '#ff4d4f'}[row['健康度']]
                st.markdown(f'<span style="color:{color};font-weight:bold">{row["健康度"]}</span>', unsafe_allow_html=True)
            with col_c:
                progress = min(row['数值'] / row['目标'] * 100, 100) if row['目标'] > 0 else 0
                st.progress(progress / 100)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="dashboard-section">', unsafe_allow_html=True)
    col_title, col_btn = st.columns([4, 1])
    with col_title:
        st.markdown('<div class="dashboard-title">📊 同比环比数据看板</div>', unsafe_allow_html=True)
    with col_btn:
        if st.button('查看更多 ➡', key='dash_trend_btn'):
            st.session_state['admin_current_menu'] = '📊 实时经营看板'
            st.rerun()
    hist_df = get_historical_stats(30)
    if len(hist_df) > 0:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader('线索增长趋势')
            if USE_PLOTLY:
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=hist_df['date'], y=hist_df['total_leads'], mode='lines+markers', name='总线索', line=dict(color='#1890ff', width=2)))
                fig.add_trace(go.Scatter(x=hist_df['date'], y=hist_df['new_leads'], mode='lines+markers', name='新增线索', line=dict(color='#52c41a', width=2)))
                fig.add_trace(go.Scatter(x=hist_df['date'], y=hist_df['deal_leads'], mode='lines+markers', name='成交', line=dict(color='#722ed1', width=2)))
                fig.update_layout(height=350, margin=dict(l=20,r=20,t=30,b=20), legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1))
                st.plotly_chart(fig, use_container_width=True, config={'scrollZoom':False,'displayModeBar':False})
            else:
                st.line_chart(hist_df.set_index('date')[['total_leads', 'new_leads', 'deal_leads']])
        with col2:
            st.subheader('外呼效能趋势')
            if USE_PLOTLY:
                fig = make_subplots(specs=[[{'secondary_y': True}]])
                fig.add_trace(go.Bar(x=hist_df['date'], y=hist_df['call_count'], name='外呼次数', marker_color='#1890ff', opacity=0.7), secondary_y=False)
                fig.add_trace(go.Scatter(x=hist_df['date'], y=hist_df['avg_score'], name='平均评分', mode='lines+markers', line=dict(color='#52c41a', width=2)), secondary_y=True)
                fig.update_layout(height=350, margin=dict(l=20,r=20,t=30,b=20), legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1))
                st.plotly_chart(fig, use_container_width=True, config={'scrollZoom':False,'displayModeBar':False})
            else:
                st.bar_chart(hist_df.set_index('date')[['call_count', 'avg_score']])
    st.subheader('核心指标对比')
    comparison_data = []
    metric_names = {'total_leads': '总线索数', 'new_leads': '新增线索', 'high_value_leads': '高价值线索', 'deal_leads': '成交数', 'call_count': '外呼次数', 'avg_score': '平均评分'}
    for metric, name in metric_names.items():
        if metric in yoy_mom:
            data = yoy_mom[metric]
            comparison_data.append({'指标': name, '今日': data['current'], '日环比': f'{data["day_change"]:+}%', '周环比': f'{data["week_change"]:+}%', '月同比': f'{data["month_change"]:+}%'})
    if comparison_data:
        comp_df = pd.DataFrame(comparison_data)
        st.dataframe(comp_df, use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="dashboard-section">', unsafe_allow_html=True)
    col_title, col_btn = st.columns([4, 1])
    with col_title:
        st.markdown('<div class="dashboard-title">📡 渠道效能分析</div>', unsafe_allow_html=True)
    with col_btn:
        if st.button('查看详情 ➡', key='dash_channel_btn'):
            st.session_state['admin_current_menu'] = '📡 渠道效能分析'
            st.rerun()
    channel_data = db_query("SELECT c.channel_name, COUNT(*) as lead_count, SUM(CASE WHEN l.is_high_value=1 THEN 1 ELSE 0 END) as high_count, SUM(CASE WHEN l.lead_status='deal' THEN 1 ELSE 0 END) as deal_count, AVG(l.total_score) as avg_score FROM customer_leads l JOIN channel_dict c ON l.channel_id = c.id GROUP BY c.channel_name")
    if len(channel_data) > 0:
        channel_data = clean_score_column(channel_data, 'avg_score')
        col1, col2 = st.columns(2)
        with col1:
            if USE_PLOTLY:
                fig = px.bar(channel_data, x='channel_name', y='lead_count', color='avg_score', color_continuous_scale='Blues', title='各渠道线索量')
                fig.update_layout(height=350, margin=dict(l=20,r=20,t=40,b=20))
                st.plotly_chart(fig, use_container_width=True, config={'scrollZoom':False,'displayModeBar':False})
            else:
                st.bar_chart(channel_data.set_index('channel_name')[['lead_count']])
        with col2:
            channel_data['转化率'] = round(channel_data['deal_count'] / channel_data['lead_count'] * 100, 1)
            channel_data['高价值率'] = round(channel_data['high_count'] / channel_data['lead_count'] * 100, 1)
            display_df = channel_data[['channel_name', 'lead_count', 'high_count', 'deal_count', '转化率', '高价值率']].rename(columns={'channel_name': '渠道', 'lead_count': '线索量', 'high_count': '高价值', 'deal_count': '成交数'})
            st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info('暂无渠道数据')
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="dashboard-section">', unsafe_allow_html=True)
    col_title, col_btn = st.columns([4, 1])
    with col_title:
        st.markdown('<div class="dashboard-title">⚡ 实时动态</div>', unsafe_allow_html=True)
    with col_btn:
        if st.button('查看更多 ➡', key='dash_recent_btn'):
            st.session_state['admin_current_menu'] = '📋 线索管理总览'
            st.rerun()
    recent_leads = db_query("SELECT l.id, l.customer_name, l.phone, l.city, l.total_score, l.lead_level, l.source_time, c.channel_name, m.model_name FROM customer_leads l LEFT JOIN channel_dict c ON l.channel_id = c.id LEFT JOIN motorcycle_model m ON l.model_id = m.id ORDER BY l.source_time DESC LIMIT 10")
    if len(recent_leads) > 0:
        recent_leads = clean_score_column(recent_leads)
        recent_leads['source_time'] = recent_leads['source_time'].astype(str).str[:16]
        display = recent_leads.rename(columns={'id': 'ID', 'customer_name': '姓名', 'phone': '手机号', 'city': '城市', 'total_score': '评分', 'lead_level': '等级', 'source_time': '时间', 'channel_name': '渠道', 'model_name': '车型'})
        st.dataframe(display, use_container_width=True, hide_index=True)
    else:
        st.info('暂无实时数据')
    st.markdown('</div>', unsafe_allow_html=True)

# ================== 工厂管理端 ==================
def factory_admin():
    st.sidebar.header('🏭 工厂管理中心')
    user = st.session_state.get('user', {})
    st.sidebar.info(f'当前用户：{user["real_name"]}')
    menu_options = ['📊 实时经营看板', '📋 线索管理总览', '⚙️ 评分规则配置', '❤️ 线索健康度看板', '👥 用户画像分析', '📡 渠道效能分析', '🏆 销售团队排行', '📞 外呼效果分析']
    if 'admin_current_menu' not in st.session_state:
        st.session_state['admin_current_menu'] = menu_options[0]
    current_index = menu_options.index(st.session_state['admin_current_menu']) if st.session_state['admin_current_menu'] in menu_options else 0
    menu = st.sidebar.radio('功能菜单', menu_options, index=current_index)
    if menu != st.session_state['admin_current_menu']:
        st.session_state['admin_current_menu'] = menu
        st.rerun()

    if menu == '📊 实时经营看板':
        start_t, end_t = render_time_filter('dashboard')
        real_time_dashboard(start_t, end_t)

    elif menu == '📋 线索管理总览':
        st.header('📋 线索管理总览')
        start_t, end_t = render_time_filter('admin_leads')
        st.markdown('<div class="auto-card">', unsafe_allow_html=True)
        auto_task_fragment()
        st.markdown('</div>', unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button('➕ 手动新增线索', use_container_width=True):
                dialog_add_lead()
        with col2:
            if st.button('📤 批量导入线索', use_container_width=True):
                dialog_import_lead()
        with col3:
            if st.button('🕷️ 手动AI抓取', use_container_width=True):
                num = auto_crawl_leads()
                execute_distribute()
                st.success(f'手动抓取完成，新增 {num} 条线索')
                st.rerun()
        st.divider()
        st.markdown('<div class="filter-bar">', unsafe_allow_html=True)
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            level_filter = st.selectbox('线索等级', ['全部','A','B','C','D'])
        with col2:
            channel_filter = st.selectbox('来源渠道', ['全部']+list(db_query('SELECT channel_name FROM channel_dict')['channel_name']))
        with col3:
            high_value_filter = st.selectbox('价值筛选', ['全部','仅高价值'])
        with col4:
            status_filter = st.selectbox('线索状态', ['全部']+list(STATUS_MAP.values()))
        with col5:
            sort_type = st.selectbox('排序方式', SORT_OPTIONS)
        col1, col2 = st.columns([3,1])
        with col1:
            search_key = st.text_input('🔍 关键词模糊搜索', placeholder='输入手机号、姓名、城市、咨询内容进行搜索')
        with col2:
            st.write('')
            st.write('')
            if st.button('🔄 刷新列表', use_container_width=True):
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        leads = db_query("SELECT l.id,l.phone,l.customer_name,l.city,l.budget,l.total_score,l.lead_level,l.is_high_value,l.user_tags,l.source_time,l.lead_status,l.first_contact_time,c.channel_name,m.model_name,s.shop_name,l.consult_content,COALESCE(cr_count.cnt,0) as call_count FROM customer_leads l LEFT JOIN channel_dict c ON l.channel_id=c.id LEFT JOIN motorcycle_model m ON l.model_id=m.id LEFT JOIN shop s ON l.assign_shop_id=s.id LEFT JOIN (SELECT lead_id,COUNT(*) as cnt FROM call_record GROUP BY lead_id) cr_count ON l.id=cr_count.lead_id WHERE l.source_time BETWEEN ? AND ?", (start_t, end_t))
        leads = clean_score_column(leads)
        filtered = leads.copy()
        if level_filter!='全部':
            filtered = filtered[filtered['lead_level']==level_filter]
        if channel_filter!='全部':
            filtered = filtered[filtered['channel_name']==channel_filter]
        if high_value_filter=='仅高价值':
            filtered = filtered[filtered['is_high_value'].fillna(0)==1]
        if status_filter!='全部':
            status_code = [k for k,v in STATUS_MAP.items() if v==status_filter][0]
            filtered = filtered[filtered['lead_status']==status_code]
        if search_key.strip():
            key = search_key.strip()
            mask = (filtered['phone'].astype(str).str.contains(key, case=False, na=False) |
                    filtered['customer_name'].astype(str).str.contains(key, case=False, na=False) |
                    filtered['city'].astype(str).str.contains(key, case=False, na=False) |
                    filtered['consult_content'].astype(str).str.contains(key, case=False, na=False))
            filtered = filtered[mask]
        filtered = sort_leads(filtered, sort_type)

        display = filtered.copy()
        display['线索状态'] = display['lead_status'].apply(status_to_cn)
        display['价值标识'] = display['is_high_value'].apply(lambda x: '⭐ 高价值' if x==1 else '')
        col_rename = {'id':'线索ID','phone':'手机号','customer_name':'客户姓名','city':'所在城市','total_score':'AI评分','lead_level':'线索等级','user_tags':'用户标签','source_time':'来源时间','first_contact_time':'首次接触时间','call_count':'外呼次数','channel_name':'来源渠道','model_name':'意向车型','shop_name':'分配门店'}
        display = display.rename(columns=col_rename)
        show_cols = ['线索ID','手机号','客户姓名','所在城市','AI评分','线索等级','价值标识','线索状态','首次接触时间','外呼次数','来源渠道','意向车型','分配门店','用户标签','来源时间']
        col1, col2 = st.columns([4,1])
        with col1:
            st.subheader('全量线索列表')
            st.caption(f'共筛选出 {len(filtered)} 条线索，当前排序：{sort_type}')
        with col2:
            st.write('')
            st.download_button('📥 导出当前结果', data=export_leads_excel(filtered), file_name=f"线索列表_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx", mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', use_container_width=True)
        st.dataframe(display[show_cols], use_container_width=True, height=500)

    elif menu == '⚙️ 评分规则配置':
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
            db_exec('UPDATE score_rule SET full_info_score=?,time_score=?,high_intent_score=?,mid_intent_score=?,low_intent_score=?,behavior_freq_score=?,demand_clear_score=?',
                    (int(full), int(time_val), int(high), int(mid), int(low), int(behavior), int(demand)))
            db_exec('UPDATE level_config SET a_min=?,b_min=?,c_min=?,high_value_min=?', (int(a), int(b), int(c), int(high_val)))
            st.success('规则保存成功')

    elif menu == '❤️ 线索健康度看板':
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
            base_quality = 0
            w = channel_weights.get(row['channel_name'], 0)
            base_quality += min(w, 20)
            info_fields = ['customer_name','city','budget','model_id','consult_content']
            if all(pd.notna(row[f]) and row[f]!='' for f in info_fields):
                base_quality += 20
            scores['基础质量'] = min(base_quality, 100)

            intent_score = 0
            lead_score = clean_score(row['total_score'])
            intent_score += lead_score * 0.8 if lead_score else 0
            tags = str(row['user_tags'])
            if '强购车意向' in tags or '预约到店' in tags:
                intent_score += 20
            if '犹豫比较中' in tags:
                intent_score -= 10
            scores['客户意向强度'] = max(0, min(intent_score, 100))

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

            follow_score = 0
            if pd.notna(row['first_contact_time']) and row['first_contact_time']!='':
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

            complete = 0
            fields = {'customer_name':20,'phone':20,'city':15,'budget':15,'model_id':15,'consult_content':15}
            for f, pts in fields.items():
                if pd.notna(row[f]) and row[f]!='':
                    complete += pts
            scores['资料完整'] = complete

            risk_score = 100
            consult = str(row['consult_content']).lower()
            negative_words = ['不买','太贵','放弃','不考虑','等新款','随便看看']
            for nw in negative_words:
                if nw in consult:
                    risk_score -= 15
            if row['lead_status'] == 'lost':
                risk_score -= 30
            if '客户流失' in str(row['user_tags']):
                risk_score -= 25
            scores['风险负面'] = max(0, risk_score)

            weights = {'基础质量':0.15,'客户意向强度':0.25,'互动活跃度':0.2,'跟进健康':0.2,'资料完整':0.1,'风险负面':0.1}
            overall = sum(scores[k]*weights[k] for k in weights)
            scores['综合健康分'] = round(overall)
            return pd.Series(scores)

        dim_scores = all_leads.apply(calc_dimension_scores, axis=1)
        all_leads = pd.concat([all_leads, dim_scores], axis=1)
        channel_list = ['全部'] + list(all_leads['channel_name'].dropna().unique())
        selected_channel = st.selectbox('选择渠道', channel_list, key='health_channel')
        if selected_channel != '全部':
            display_leads = all_leads[all_leads['channel_name'] == selected_channel].copy()
        else:
            display_leads = all_leads.copy()

        if selected_channel != '全部':
            st.subheader(f'📌 {selected_channel} 渠道健康度详情')
            total = len(display_leads)
            healthy = len(display_leads[display_leads['综合健康分']>=80])
            sub_healthy = len(display_leads[(display_leads['综合健康分']>=60) & (display_leads['综合健康分']<80)])
            cultivate = len(display_leads[display_leads['综合健康分']<60])
            col1, col2, col3, col4 = st.columns(4)
            col1.metric('线索总数', total)
            col2.metric('健康线索', f'{healthy} ({round(healthy/total*100,1)}%)' if total>0 else '0')
            col3.metric('亚健康线索', f'{sub_healthy} ({round(sub_healthy/total*100,1)}%)' if total>0 else '0')
            col4.metric('待培育', f'{cultivate} ({round(cultivate/total*100,1)}%)' if total>0 else '0')
            health_cat = pd.cut(display_leads['综合健康分'], bins=[0,60,80,101], labels=['待培育','亚健康','健康'])
            health_counts = health_cat.value_counts().reset_index()
            health_counts.columns = ['健康度','数量']
            if USE_PLOTLY:
                fig = px.pie(health_counts, names='健康度', values='数量', color='健康度', color_discrete_map={'健康':'#52c41a','亚健康':'#faad14','待培育':'#ff4d4f'})
                fig.update_layout(height=350)
                st.plotly_chart(fig, use_container_width=True, config={'scrollZoom':False,'displayModeBar':False})
            else:
                st.bar_chart(health_counts.set_index('健康度')['数量'])
            dim_avg = display_leads[['基础质量','客户意向强度','互动活跃度','跟进健康','资料完整','风险负面']].mean().reset_index()
            dim_avg.columns = ['维度','平均分']
            bar_chart(dim_avg, x='维度', y='平均分')
            st.subheader('⚠️ 风险负面线索 (风险分<60)')
            risk_leads = display_leads[display_leads['风险负面']<60][['id','customer_name','phone','channel_name','风险负面','consult_content']]
            if len(risk_leads)>0:
                st.dataframe(risk_leads, use_container_width=True)
            else:
                st.info('暂无高风险线索')
        else:
            st.subheader('🌐 全渠道健康度对比')
            avg_score = display_leads.groupby('channel_name')['综合健康分'].mean().sort_values(ascending=False).reset_index()
            avg_score.columns = ['渠道','平均健康分']
            bar_chart(avg_score, x='渠道', y='平均健康分')
            dim_avg_ch = display_leads.groupby('channel_name')[['基础质量','客户意向强度','互动活跃度','跟进健康','资料完整','风险负面']].mean()
            if USE_PLOTLY:
                fig = px.bar(dim_avg_ch, x=dim_avg_ch.index, y=dim_avg_ch.columns, barmode='group', title='各渠道维度平均分对比')
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True, config={'scrollZoom':False,'displayModeBar':False})
            else:
                st.bar_chart(dim_avg_ch)

    elif menu == '👥 用户画像分析':
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
        region.columns = ['省份','线索量']
        bar_chart(region, x='省份', y='线索量')

        st.subheader('💰 消费水平分布')
        def budget_level(b):
            if pd.isna(b):
                return '未知'
            b = str(b)
            try:
                num_str = ''.join([c for c in b if c.isdigit() or c=='.'])
                if num_str:
                    amt = float(num_str)
                    if '万' in b:
                        amt *= 10000
                    if amt >= 30000:
                        return '高预算(≥3万)'
                    elif amt >= 15000:
                        return '中预算(1.5-3万)'
                    else:
                        return '入门预算(<1.5万)'
            except Exception:
                pass
            if '预算不多' in b:
                return '入门预算(<1.5万)'
            return '未知'
        all_leads['消费水平'] = all_leads['budget'].apply(budget_level)
        budget_counts = all_leads['消费水平'].value_counts().reset_index()
        budget_counts.columns = ['消费水平','数量']
        if USE_PLOTLY:
            fig = px.pie(budget_counts, names='消费水平', values='数量', color='消费水平', color_discrete_sequence=px.colors.qualitative.Set2)
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True, config={'scrollZoom':False,'displayModeBar':False})
        else:
            st.bar_chart(budget_counts.set_index('消费水平')['数量'])

        st.subheader('🏍️ 意向车型偏好')
        model_df = db_query('SELECT id,model_name FROM motorcycle_model')
        all_leads = all_leads.merge(model_df[['id','model_name']], left_on='model_id', right_on='id', how='left')
        if 'model_name_y' in all_leads.columns:
            all_leads = all_leads.rename(columns={'model_name_y':'model_name'})
        elif 'model_name' not in all_leads.columns and 'model_name_x' in all_leads.columns:
            all_leads = all_leads.rename(columns={'model_name_x':'model_name'})
        all_leads = all_leads.drop(columns=[c for c in ['id_x','id_y'] if c in all_leads.columns], errors='ignore')
        model_counts = all_leads['model_name'].value_counts().reset_index()
        model_counts.columns = ['车型','数量']
        bar_chart(model_counts, x='车型', y='数量')

        st.subheader('📡 渠道来源效能')
        ch_counts = all_leads.groupby('channel_name').size().reset_index(name='线索量')
        ch_high = all_leads.groupby('channel_name')['is_high_value'].mean().reset_index(name='高价值率')
        ch_stats = ch_counts.merge(ch_high, on='channel_name')
        ch_stats['高价值率'] = round(ch_stats['高价值率']*100,1)
        col1, col2 = st.columns(2)
        with col1:
            st.dataframe(ch_stats, use_container_width=True, hide_index=True)
        with col2:
            bar_chart(ch_stats, x='channel_name', y='线索量')

        st.subheader('🏷️ 用户关注点标签')
        all_tags = []
        for t in all_leads['user_tags'].dropna():
            all_tags.extend(t.split(','))
        tag_counts = pd.Series(all_tags).value_counts().head(10).reset_index()
        tag_counts.columns = ['标签','数量']
        if len(tag_counts)>0:
            bar_chart(tag_counts, x='标签', y='数量')
        else:
            st.info('暂无标签数据')

        st.subheader('⏰ 线索活跃时段')
        valid_leads = all_leads.dropna(subset=['source_dt'])
        valid_leads['小时'] = valid_leads['source_dt'].dt.hour
        hour_counts = valid_leads['小时'].value_counts().sort_index().reset_index()
        hour_counts.columns = ['小时','线索量']
        line_chart(hour_counts, x='小时', y='线索量', color='#722ed1')

        top_region = region.iloc[0]['省份'] if len(region)>0 else '未知'
        top_budget = budget_counts.iloc[0]['消费水平'] if len(budget_counts)>0 else '未知'
        top_model = model_counts.iloc[0]['车型'] if len(model_counts)>0 else '未知'
        top_channel = ch_stats.sort_values('线索量',ascending=False).iloc[0]['channel_name'] if len(ch_stats)>0 else '未知'
        st.subheader('📋 综合画像总结')
        st.info(f'核心客群特征：\n- 主要分布在 {top_region} 区域。\n- 消费水平以 {top_budget} 为主。\n- 最受欢迎车型是 {top_model}。\n- 渠道中 {top_channel} 贡献最大。')

    elif menu == '📡 渠道效能分析':
        st.header('📡 渠道效能分析')
        start_t, end_t = render_time_filter('admin_channel')
        leads = db_query("SELECT l.*, c.channel_name FROM customer_leads l LEFT JOIN channel_dict c ON l.channel_id=c.id WHERE l.source_time BETWEEN ? AND ?", (start_t, end_t))
        leads = clean_score_column(leads)
        if len(leads) == 0:
            st.warning('本周期暂无线索数据')
        else:
            ch_stats = leads.groupby('channel_name').agg(线索量=('id','count'),高价值数=('is_high_value','sum'),平均评分=('total_score','mean'),成交数=('lead_status', lambda x: (x=='deal').sum())).reset_index()
            ch_stats['高价值率'] = round(ch_stats['高价值数']/ch_stats['线索量']*100,1)
            ch_stats['成交率'] = round(ch_stats['成交数']/ch_stats['线索量']*100,1)
            ch_stats['平均评分'] = round(ch_stats['平均评分'],1)
            ch_stats = ch_stats.sort_values('线索量', ascending=False)
            st.subheader('📊 渠道核心指标')
            st.dataframe(ch_stats[['channel_name','线索量','高价值率','平均评分','成交率']].rename(columns={'channel_name':'渠道'}), use_container_width=True, hide_index=True)
            plot_ch = ch_stats.rename(columns={'channel_name':'渠道'})
            col1, col2 = st.columns(2)
            with col1:
                bar_chart(plot_ch, x='渠道', y='线索量')
            with col2:
                bar_chart(plot_ch, x='渠道', y='高价值率')
            st.subheader('🔽 渠道转化漏斗')
            for _, crow in ch_stats.head(5).iterrows():
                ch = crow['channel_name']
                ch_leads = leads[leads['channel_name']==ch]
                total = len(ch_leads)
                touched = len(ch_leads[ch_leads['lead_status']!='untouch'])
                reserved = len(ch_leads[ch_leads['lead_status']=='reserve_test'])
                bargained = len(ch_leads[ch_leads['lead_status']=='bargain'])
                dealt = len(ch_leads[ch_leads['lead_status']=='deal'])
                st.write(f"**{ch}**: 总{total} → 跟进{touched} → 试驾{reserved} → 议价{bargained} → 成交{dealt}")
                if total > 0:
                    st.progress(min(dealt/total, 1.0))

    elif menu == '🏆 销售团队排行':
        st.header('🏆 销售团队排行')
        start_t, end_t = render_time_filter('admin_rank')
        shop_sql = "SELECT s.shop_name, COUNT(DISTINCT l.id) as lead_count, SUM(CASE WHEN l.lead_status='deal' THEN 1 ELSE 0 END) as deal_count, COUNT(cr.id) as call_count, COALESCE(AVG(cr.score_after_call),0) as avg_call_score FROM shop s LEFT JOIN customer_leads l ON s.id=l.assign_shop_id AND l.assign_time BETWEEN ? AND ? LEFT JOIN call_record cr ON l.id=cr.lead_id AND cr.create_time BETWEEN ? AND ? GROUP BY s.id, s.shop_name"
        shop_stats = db_query(shop_sql, (start_t, end_t, start_t, end_t))
        if len(shop_stats) > 0:
            shop_stats['成交率'] = round(shop_stats['deal_count']/shop_stats['lead_count'].replace(0,1)*100,1)
            shop_stats['平均通话评分'] = round(shop_stats['avg_call_score'],1)
            shop_stats = shop_stats.sort_values('deal_count', ascending=False)
            st.subheader('🏬 门店排行')
            st.dataframe(shop_stats.rename(columns={'shop_name':'门店','lead_count':'线索数','deal_count':'成交数','call_count':'外呼数'}), use_container_width=True, hide_index=True)
            plot_shop = shop_stats.rename(columns={'shop_name':'门店','deal_count':'成交数'})
            bar_chart(plot_shop, x='门店', y='成交数')
        seller_sql = "SELECT u.real_name, s.shop_name, COUNT(DISTINCT l.id) as lead_count, SUM(CASE WHEN l.lead_status='deal' THEN 1 ELSE 0 END) as deal_count, COUNT(cr.id) as call_count FROM sys_user u LEFT JOIN shop s ON u.shop_id=s.id LEFT JOIN customer_leads l ON u.id=l.assign_sale_id AND l.assign_time BETWEEN ? AND ? LEFT JOIN call_record cr ON l.id=cr.lead_id AND cr.create_time BETWEEN ? AND ? WHERE u.role='sale' GROUP BY u.id, u.real_name, s.shop_name"
        seller_stats = db_query(seller_sql, (start_t, end_t, start_t, end_t))
        if len(seller_stats) > 0:
            seller_stats = seller_stats.sort_values('deal_count', ascending=False)
            st.subheader('👤 销售个人排行')
            st.dataframe(seller_stats.rename(columns={'real_name':'销售姓名','shop_name':'所属门店','lead_count':'负责线索','deal_count':'成交数','call_count':'外呼数'}), use_container_width=True, hide_index=True)

    elif menu == '📞 外呼效果分析':
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
            col2.metric('平均通话后评分', round(calls['score_after_call'].mean(),1))
            col3.metric('平均通话时长(秒)', int(calls['call_duration'].mean()))
            col4.metric('覆盖门店数', calls['shop_name'].nunique())
            st.divider()
            st.subheader('📈 评分变化趋势')
            calls['dt'] = calls['create_time'].astype(str).str[:10]
            trend = calls.groupby('dt').agg({'score_after_call':'mean','call_duration':'sum'}).reset_index()
            trend.columns = ['日期','平均评分','总时长']
            line_chart(trend, x='日期', y='平均评分', color='#52c41a')
            st.divider()
            st.subheader('📋 外呼明细')
            disp = calls[['customer_name','phone','shop_name','sale_name','call_duration','score_after_call','level_after_call','create_time']].rename(columns={'customer_name':'客户','phone':'手机号','shop_name':'门店','sale_name':'销售','call_duration':'时长(秒)','score_after_call':'通话后评分','level_after_call':'通话后等级','create_time':'时间'})
            st.dataframe(disp, use_container_width=True, hide_index=True)

# ================== 商家操作端 ==================
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
    shop_name = shop_df.iloc[0]['shop_name'] if len(shop_df)>0 else '未知门店'
    st.sidebar.info(f'门店：{shop_name}\n用户：{user["real_name"]}')
    menu = st.sidebar.radio('功能菜单', ['📋 今日工作台', '📁 我的线索池', '📞 外呼中心', '📈 门店数据看板'])

    if menu == '📋 今日工作台':
        st.header('📋 今日工作台 & 门店经营数据')
        today = datetime.date.today().strftime('%Y-%m-%d')
        my_leads = db_query('SELECT * FROM customer_leads WHERE assign_shop_id=?', (shop_id,))
        my_leads = clean_score_column(my_leads)
        today_new = my_leads[my_leads['assign_time'].astype(str).str.startswith(today)]
        high_val = my_leads[my_leads['is_high_value'].fillna(0)==1]
        st.subheader('📌 今日重点指标')
        col1, col2, col3, col4 = st.columns(4)
        col1.metric('今日新线索', len(today_new))
        col2.metric('高价值线索', len(high_val))
        col3.metric('待跟进线索', len(my_leads[my_leads['lead_status']=='untouch']))
        col4.metric('已成交', len(my_leads[my_leads['lead_status']=='deal']))
        st.divider()
        st.subheader('🏬 门店经营看板')
        col1, col2, col3, col4 = st.columns(4)
        col1.metric('总线索数', len(my_leads))
        col2.metric('今日新增', len(today_new))
        col3.metric('高价值线索', len(high_val))
        col4.metric('外呼总次数', len(db_query('SELECT * FROM call_record WHERE shop_id=?', (shop_id,))))
        lv = my_leads['lead_level'].value_counts().reset_index()
        lv.columns = ['等级','数量']
        bar_chart(lv, x='等级', y='数量')
        st.subheader('🔥 高优先级线索')
        top = db_query("SELECT l.id,l.phone,l.customer_name,l.city,l.total_score,l.lead_level,l.user_tags,l.consult_content,l.lead_status,l.first_contact_time,COALESCE(cr_count.cnt,0) as call_count FROM customer_leads l LEFT JOIN (SELECT lead_id,COUNT(*) as cnt FROM call_record GROUP BY lead_id) cr_count ON l.id=cr_count.lead_id WHERE l.assign_shop_id=? ORDER BY l.total_score DESC LIMIT 10", (shop_id,))
        top = clean_score_column(top)
        if len(top) > 0:
            top['线索状态'] = top['lead_status'].apply(status_to_cn)
        top = top.rename(columns={'id':'线索ID','phone':'手机号','customer_name':'客户姓名','city':'所在城市','total_score':'AI评分','lead_level':'线索等级','user_tags':'用户标签','consult_content':'咨询内容','first_contact_time':'首次接触时间','call_count':'外呼次数'})
        st.dataframe(top, use_container_width=True)

    elif menu == '📁 我的线索池':
        st.header('我的线索池')
        st.markdown('<div class="filter-bar">', unsafe_allow_html=True)
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            level_filter = st.selectbox('线索等级', ['全部','A','B','C','D'])
        with col2:
            channel_filter = st.selectbox('来源渠道', ['全部']+list(db_query('SELECT channel_name FROM channel_dict')['channel_name']))
        with col3:
            high_value_filter = st.selectbox('价值筛选', ['全部','仅高价值'])
        with col4:
            status_filter = st.selectbox('线索状态', ['全部']+list(STATUS_MAP.values()))
        with col5:
            sort_type = st.selectbox('排序方式', SORT_OPTIONS)
        col1, col2 = st.columns([3,1])
        with col1:
            search_key = st.text_input('🔍 关键词模糊搜索', placeholder='输入手机号、姓名、城市、咨询内容进行搜索')
        with col2:
            st.write('')
            st.write('')
            if st.button('🔄 刷新列表', use_container_width=True):
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        leads = db_query("SELECT l.id,l.phone,l.customer_name,l.city,l.budget,l.total_score,l.lead_level,l.is_high_value,l.user_tags,l.source_time,l.lead_status,l.first_contact_time,c.channel_name,m.model_name,l.assign_time,l.consult_content,COALESCE(cr_count.cnt,0) as call_count FROM customer_leads l LEFT JOIN channel_dict c ON l.channel_id=c.id LEFT JOIN motorcycle_model m ON l.model_id=m.id LEFT JOIN (SELECT lead_id,COUNT(*) as cnt FROM call_record GROUP BY lead_id) cr_count ON l.id=cr_count.lead_id WHERE l.assign_shop_id=?", (shop_id,))
        leads = clean_score_column(leads)
        filtered = leads.copy()
        if level_filter!='全部':
            filtered = filtered[filtered['lead_level']==level_filter]
        if channel_filter!='全部':
            filtered = filtered[filtered['channel_name']==channel_filter]
        if high_value_filter=='仅高价值':
            filtered = filtered[filtered['is_high_value'].fillna(0)==1]
        if status_filter!='全部':
            status_codes = [k for k,v in STATUS_MAP.items() if v==status_filter]
            if status_codes:
                filtered = filtered[filtered['lead_status']==status_codes[0]]
            else:
                filtered = filtered.iloc[0:0]
        if search_key.strip():
            key = search_key.strip()
            mask = (filtered['phone'].astype(str).str.contains(key,case=False,na=False) |
                    filtered['customer_name'].astype(str).str.contains(key,case=False,na=False) |
                    filtered['city'].astype(str).str.contains(key,case=False,na=False) |
                    filtered['consult_content'].astype(str).str.contains(key,case=False,na=False))
            filtered = filtered[mask]
        filtered = sort_leads(filtered, sort_type)
        st.caption(f'共 {len(filtered)} 条线索，当前排序：{sort_type}')
        st.divider()

        # 显示线索列表
        for _, row in filtered.iterrows():
            lead_id = int(row['id'])
            high_tag = '⭐ ' if row['is_high_value']==1 else ''
            with st.container():
                c1,c2,c3,c4,c5,c6,c7 = st.columns([1,2,2,1.5,1.5,1,3])
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
                    bc1,bc2,bc3 = st.columns(3)
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

        # 统一处理弹窗（仅当存在标志时调用一次）
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
            calls_disp = calls[['customer_name','phone','call_duration','score_after_call','level_after_call','create_time']].rename(columns={'customer_name':'客户姓名','phone':'手机号','call_duration':'时长(秒)','score_after_call':'通话后评分','level_after_call':'通话后等级','create_time':'时间'})
            st.dataframe(calls_disp, use_container_width=True, hide_index=True)
        else:
            st.info("暂无外呼记录")

    elif menu == '📈 门店数据看板':
        st.header('📈 门店数据看板')
        start_t, end_t = render_time_filter("shop_dashboard")
        my_leads = db_query("SELECT * FROM customer_leads WHERE assign_shop_id=?", (shop_id,))
        my_leads = clean_score_column(my_leads)
        period_leads = db_query("SELECT * FROM customer_leads WHERE assign_shop_id=? AND assign_time BETWEEN ? AND ?", (shop_id, start_t, end_t))
        period_leads = clean_score_column(period_leads)
        st.subheader('📌 核心指标')
        col1, col2, col3, col4 = st.columns(4)
        col1.metric('总线索数', len(my_leads))
        col2.metric('周期新增', len(period_leads))
        col3.metric('高价值线索', len(my_leads[my_leads['is_high_value'].fillna(0)==1]))
        col4.metric('已成交', len(my_leads[my_leads['lead_status']=='deal']))
        st.divider()
        st.subheader('🏷️ 线索等级分布')
        lv = my_leads['lead_level'].value_counts().reset_index()
        lv.columns = ['等级','数量']
        bar_chart(lv, x='等级', y='数量')
        st.divider()
        st.subheader('📞 周期外呼统计')
        period_calls = db_query("SELECT * FROM call_record WHERE shop_id=? AND create_time BETWEEN ? AND ?", (shop_id, start_t, end_t))
        if len(period_calls) > 0:
            col1, col2, col3 = st.columns(3)
            col1.metric('外呼次数', len(period_calls))
            col2.metric('平均评分变化', round(period_calls['score_after_call'].mean(),1))
            col3.metric('总通话时长(秒)', int(period_calls['call_duration'].sum()))
            period_calls['dt'] = period_calls['create_time'].astype(str).str[:10]
            trend = period_calls.groupby('dt')['score_after_call'].mean().reset_index()
            trend.columns = ['日期','平均评分']
            line_chart(trend, x='日期', y='平均评分', color='#1890ff')
        else:
            st.info('本周期暂无外呼记录')

# ================== 程序入口 ==================
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