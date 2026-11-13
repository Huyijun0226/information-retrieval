import streamlit as st
import streamlit.components.v1 as components
import sqlite3
import datetime
import pandas as pd
from translator import parse_input, translate_queries
from ai_helper import (
    AIConnectionError, test_connection, get_synonyms, 
    chat_with_agent, stream_chat_with_agent, parse_query_to_groups,
    search_wechat_articles
)
from db import (
    load_settings, save_settings, update_password,
    add_chat_msg, get_chat_history, clear_chat_history,
    add_recommendation_history, add_query_history,
    add_translation_history, get_query_history, get_translation_history,
    update_query_hit_counts, update_favorite_status
)

st.set_page_config(page_title="跨库检索式智能转译系统", page_icon="📚", layout="wide")

# ================= 初始化 session state =================
# 从数据库加载 AI 设置
db_settings = load_settings()

if "current_page" not in st.session_state:
    st.session_state.current_page = "home"
if "selected_iframe_url" not in st.session_state:
    st.session_state.selected_iframe_url = ""

if "group_a" not in st.session_state:
    st.session_state.group_a = "作物\n植物\n叶片\ncrop\nplant\nleaf"
if "group_b" not in st.session_state:
    st.session_state.group_b = "病害\n虫害\n杂草\ndisease\npest\nweed"
if "group_d" not in st.session_state:
    st.session_state.group_d = "深度学习\n计算机视觉\n目标检测\ndeep learning\ncomputer vision\nobject detection\nYOLO"
if "messages" not in st.session_state:
    # 从数据库加载历史记录 (默认加载最近50条)
    st.session_state.messages = get_chat_history(limit=50)

# 历史记录加载限制
if "history_q_limit" not in st.session_state:
    st.session_state.history_q_limit = 20
if "history_t_limit" not in st.session_state:
    st.session_state.history_t_limit = 20
if "history_c_limit" not in st.session_state:
    st.session_state.history_c_limit = 50

# AI 设置状态
if "ai_locked" not in st.session_state:
    # 如果数据库中有 key，默认锁定；否则默认解锁
    st.session_state.ai_locked = bool((db_settings["api_key"] or "").strip())
if "api_key" not in st.session_state:
    st.session_state.api_key = (db_settings["api_key"] or "").strip()
if "base_url" not in st.session_state:
    st.session_state.base_url = db_settings["base_url"] or ""
if "model_name" not in st.session_state:
    st.session_state.model_name = db_settings["model_name"] or ""


def clear_connection_notice():
    st.session_state.pop("connection_notice", None)


@st.dialog("🔒 验证密码")
def password_dialog():
    st.write("请输入密码以编辑 AI 设置 (默认: 123456)")
    pwd_input = st.text_input("密码", type="password", key="edit_pwd_input")
    if st.button("确认", use_container_width=True):
        if pwd_input == db_settings.get("password", "123456"):
            clear_connection_notice()
            st.session_state.ai_locked = False
            st.rerun()
        else:
            st.error("密码错误！")

@st.dialog("🔑 修改密码")
def change_password_dialog():
    old_pwd = st.text_input("原密码", type="password", key="old_pwd_input")
    new_pwd = st.text_input("新密码", type="password", key="new_pwd_input")
    confirm_pwd = st.text_input("确认新密码", type="password", key="confirm_pwd_input")
    
    if st.button("确认修改", use_container_width=True):
        if old_pwd != db_settings.get("password", "123456"):
            st.error("原密码错误！")
        elif new_pwd != confirm_pwd:
            st.error("两次输入的新密码不一致！")
        elif not new_pwd:
            st.error("新密码不能为空！")
        else:
            update_password(new_pwd)
            db_settings["password"] = new_pwd
            st.success("密码修改成功！")
            st.rerun()

def toggle_ai_lock():
    """解锁以供编辑 (需要密码)"""
    password_dialog()


def check_ai_settings(settings, *, save):
    api_key, base_url, model_name = (value.strip() for value in settings)
    notice = "已保存离线模式。"
    if api_key:
        try:
            with st.spinner("正在测试模型连接…"):
                api_key, base_url, model_name = test_connection(api_key, base_url, model_name)
        except AIConnectionError as exc:
            st.session_state.connection_notice = ("error", str(exc))
            return
        notice = f"模型 {model_name} 已响应。"
    if save:
        try:
            save_settings(api_key, base_url, model_name)
        except sqlite3.Error:
            st.session_state.connection_notice = ("error", "无法保存设置，请检查 settings.db 的写入权限后重试。")
            return
        st.session_state.api_key = api_key
        st.session_state.base_url = base_url
        st.session_state.model_name = model_name
        st.session_state.ai_locked = True
        if api_key:
            notice += "配置已保存。"
    st.session_state.connection_notice = ("success", notice)
    if save:
        st.rerun()


# 追加词汇回调函数
def append_synonyms():
    selected = st.session_state.get("selected_synonyms_widget", [])
    target = st.session_state.get("target_group_widget", "A组：对象层")
    
    if selected:
        added_text = "\n" + "\n".join(selected)
        if "A组" in target:
            st.session_state.group_a += added_text
        elif "B组" in target:
            st.session_state.group_b += added_text
        elif "D组" in target:
            st.session_state.group_d += added_text
            
        # 添加成功后清空推荐列表
        st.session_state.recommended_synonyms = []

# ================= 页面布局 =================

avatar_url = "https://core-normal.traeapi.us/api/ide/v1/text_to_image?prompt=A%20professional%203D%20digital%20human%20assistant%2C%20female%20researcher%2C%20wearing%20a%20white%20lab%20coat%2C%20futuristic%20smart%20agriculture%20background%2C%20holographic%20leaves%20and%20data%20elements%2C%20friendly%20smile%2C%20high%20quality%2C%20portrait&image_size=square"

@st.dialog("👩‍🔬 您的专属学术检索数字人", width="large")
def chat_dialog():
    col1, col2 = st.columns([1, 4])
    with col1:
        st.image(avatar_url, use_column_width=True)
    with col2:
        st.markdown("**你好！我是数字人助手小跨。**\n我精通农业与计算机视觉领域的文献检索，随时准备解答您的问题！")
        if st.button("🗑️ 清空对话", use_container_width=True):
            clear_chat_history()
            st.session_state.messages = []
            st.rerun()

    st.markdown("---")
    
    chat_container = st.container(height=400)
    with chat_container:
        for msg in st.session_state.messages:
            st.chat_message(msg["role"]).write(msg["content"])
            
    if prompt := st.chat_input("向数字人提问..."):
        user_message = {"role": "user", "content": prompt}
        
        with chat_container:
            st.chat_message("user").write(prompt)
            # 获取 LLM 回复
            with st.chat_message("assistant"):
                ak = st.session_state.api_key
                bu = st.session_state.base_url
                mn = st.session_state.model_name
                try:
                    # 使用流式输出
                    full_response = st.write_stream(
                        stream_chat_with_agent([*st.session_state.messages, user_message], ak, bu, mn)
                    )
                except AIConnectionError as exc:
                    st.error(str(exc))
                    return
            
            st.session_state.messages.append(user_message)
            add_chat_msg("user", prompt)
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            add_chat_msg("assistant", full_response)

@st.dialog("🕒 历史记录", width="large")
def history_dialog():
    st.subheader("🔍 记录筛选")
    f_col1, f_col2, f_col3, f_col4 = st.columns([3, 2, 2, 2])
    with f_col1:
        search_keyword = st.text_input("关键词查询 (支持模糊搜索)", placeholder="输入要查询的内容...", key="history_search_keyword")
    with f_col2:
        start_date = st.date_input("开始日期", value=None, key="history_start_date")
    with f_col3:
        end_date = st.date_input("结束日期", value=None, key="history_end_date")
    with f_col4:
        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
        fav_only = st.checkbox("⭐ 仅看收藏", key="history_fav_only")
        do_search = st.button("🔎 查询", use_container_width=True)

    def is_match(text_contents, item_timestamp, is_fav):
        # 收藏过滤
        if st.session_state.get("history_applied_fav_only") and not is_fav:
            return False
            
        # 如果用户没有点击查询按钮，默认不应用任何过滤（显示全部）
        if not st.session_state.get("history_searched", False):
            return True
            
        # 关键词匹配
        if st.session_state.get("history_applied_keyword"):
            text_to_search = " ".join([str(t) for t in text_contents if t]).lower()
            if st.session_state.history_applied_keyword.lower() not in text_to_search:
                return False
        # 日期匹配
        applied_start = st.session_state.get("history_applied_start")
        applied_end = st.session_state.get("history_applied_end")
        if applied_start or applied_end:
            try:
                item_date_str = item_timestamp.split(' ')[0]
                item_date = datetime.datetime.strptime(item_date_str, "%Y-%m-%d").date()
                if applied_start and item_date < applied_start:
                    return False
                if applied_end and item_date > applied_end:
                    return False
            except Exception:
                pass
        return True

    if do_search:
        st.session_state.history_searched = True
        st.session_state.history_applied_keyword = search_keyword
        st.session_state.history_applied_start = start_date
        st.session_state.history_applied_end = end_date
        st.session_state.history_applied_fav_only = fav_only
        # 取消这里的 st.rerun()，因为 st.dialog 会在 rerun 时被关闭

    import re
    def highlight_text(text):
        """如果存在搜索关键词，则使用 Markdown 高亮显示匹配的部分"""
        keyword = st.session_state.get("history_applied_keyword")
        if not keyword or not st.session_state.get("history_searched", False):
            return text
        # 使用不区分大小写的正则替换，背景设为黄色
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        # 用 HTML span 标签进行高亮，Streamlit 的 markdown 支持部分 HTML
        return pattern.sub(lambda m: f"<span style='background-color: yellow; color: black;'>{m.group(0)}</span>", str(text))

    htab1, htab2, htab3 = st.tabs(["💬 聊天记录", "🔍 生成检索记录", "🪄 智能转译记录"])
    
    with htab1:
        msgs = get_chat_history(limit=st.session_state.history_c_limit)
        filtered_msgs = [m for m in msgs if is_match([m["content"]], m.get("timestamp", ""), False)]
        if not filtered_msgs:
            st.info("暂无符合条件的聊天记录。")
        else:
            for msg in filtered_msgs:
                with st.chat_message(msg["role"]):
                    st.caption(msg.get("timestamp", ""))
                    st.markdown(highlight_text(msg["content"]), unsafe_allow_html=True)
            
            if len(msgs) >= st.session_state.history_c_limit:
                if st.button("加载更多聊天记录", key="load_more_chat"):
                    st.session_state.history_c_limit += 50
                    st.rerun()
                    
    with htab2:
        q_history = get_query_history(limit=st.session_state.history_q_limit)
        filtered_q = [q for q in q_history if is_match([q["group_a"], q["group_b"], q["group_d"], q["dbs"], q["results"]], q.get("timestamp", ""), q.get("is_favorite", 0))]
        if not filtered_q:
            st.info("暂无符合条件的生成检索记录。")
        else:
            for item in filtered_q:
                title = f"{'⭐ ' if item.get('is_favorite') else ''}🕒 {item['timestamp']} - {item['dbs']}"
                with st.expander(title):
                    c1, c2 = st.columns([4, 1])
                    with c2:
                        fav_label = "取消收藏" if item.get('is_favorite') else "设为收藏"
                        if st.button(fav_label, key=f"fav_q_{item['id']}", use_container_width=True):
                            update_favorite_status("query_history", item['id'], not item.get('is_favorite'))
                            st.rerun()
                    
                    st.markdown("**A组 (对象层):** " + highlight_text(item['group_a'].replace('\n', ', ')), unsafe_allow_html=True)
                    st.markdown("**B组 (危害层):** " + highlight_text(item['group_b'].replace('\n', ', ')), unsafe_allow_html=True)
                    st.markdown("**D组 (方法层):** " + highlight_text(item['group_d'].replace('\n', ', ')), unsafe_allow_html=True)
                    
                    # 命中数统计与可视化
                    st.markdown("---")
                    st.subheader("📊 命中数统计")
                    import json
                    try:
                        hits = json.loads(item.get('hit_counts', '{}'))
                        dbs_list = json.loads(item['dbs'])
                        
                        # 编辑命中数
                        edit_hits = {}
                        h_cols = st.columns(len(dbs_list))
                        for idx, db_name in enumerate(dbs_list):
                            with h_cols[idx]:
                                val = hits.get(db_name, 0)
                                new_val = st.number_input(f"{db_name}", min_value=0, value=int(val), key=f"hit_{item['id']}_{db_name}")
                                edit_hits[db_name] = new_val
                        
                        if st.button("保存命中数", key=f"save_hit_{item['id']}"):
                            update_query_hit_counts(item['id'], edit_hits)
                            st.toast("✅ 命中数已保存")
                            st.rerun()
                            
                        # 可视化对比
                        if any(edit_hits.values()):
                            st.bar_chart(edit_hits)
                            
                    except Exception as e:
                        st.error(f"加载统计数据失败: {e}")

                    st.markdown("---")
                    st.markdown("**检索结果详情:**")
                    try:
                        results = json.loads(item['results'])
                        for db, data in results.items():
                            st.markdown(f"*{db}*")
                            st.code(data['query'], language="sql")
                    except:
                        st.markdown(highlight_text(item['results']), unsafe_allow_html=True)

            if len(q_history) >= st.session_state.history_q_limit:
                if st.button("加载更多生成记录", key="load_more_query"):
                    st.session_state.history_q_limit += 20
                    st.rerun()

    with htab3:
        t_history = get_translation_history(limit=st.session_state.history_t_limit)
        filtered_t = [t for t in t_history if is_match([t["source_query"], t["group_a"], t["group_b"], t["group_d"]], t.get("timestamp", ""), t.get("is_favorite", 0))]
        if not filtered_t:
            st.info("暂无符合条件的智能转译记录。")
        else:
            for item in filtered_t:
                title = f"{'⭐ ' if item.get('is_favorite') else ''}🕒 {item['timestamp']}"
                with st.expander(title):
                    c1, c2 = st.columns([4, 1])
                    with c2:
                        fav_label = "取消收藏" if item.get('is_favorite') else "设为收藏"
                        if st.button(fav_label, key=f"fav_t_{item['id']}", use_container_width=True):
                            update_favorite_status("translation_history", item['id'], not item.get('is_favorite'))
                            st.rerun()
                    st.markdown("**原始检索式:**")
                    st.code(item['source_query'])
                    st.markdown("**解析结果:**")
                    st.markdown(f"- **A组:** {highlight_text(item['group_a'].replace(chr(10), ', '))}", unsafe_allow_html=True)
                    st.markdown(f"- **B组:** {highlight_text(item['group_b'].replace(chr(10), ', '))}", unsafe_allow_html=True)
                    st.markdown(f"- **D组:** {highlight_text(item['group_d'].replace(chr(10), ', '))}", unsafe_allow_html=True)

            if len(t_history) >= st.session_state.history_t_limit:
                if st.button("加载更多转译记录", key="load_more_trans"):
                    st.session_state.history_t_limit += 20
                    st.rerun()


st.sidebar.markdown("---")
st.sidebar.header("🌐 页面导航")
if st.session_state.current_page == "home":
    if st.sidebar.button("🚀 切换至专业检索入口", use_container_width=True):
        st.session_state.current_page = "search_portal"
        st.rerun()
else:
    if st.sidebar.button("🏠 返回智能转译主页", use_container_width=True):
        st.session_state.current_page = "home"
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("⚙️ 检索设置")
dbs = st.sidebar.multiselect(
    "选择目标数据库",
    ["CNKI (知网)", "Web of Science", "IEEE Xplore", "超星发现"],
    default=["CNKI (知网)", "Web of Science", "IEEE Xplore", "超星发现"]
)
start_year = st.sidebar.number_input("起始年份", min_value=1900, max_value=2100, value=2019)
end_year = st.sidebar.number_input("结束年份", min_value=1900, max_value=2100, value=2026)

st.sidebar.markdown("---")

disabled = st.session_state.ai_locked
saved_settings = (st.session_state.api_key, st.session_state.base_url, st.session_state.model_name)
display_api_key = "********" if st.session_state.api_key else ""

with st.sidebar.expander("🤖 AI 设置 (OpenAI 兼容)", expanded=not disabled):
    # AI 设置输入区
    api_key_input = st.text_input("API Key (可选)", type="password", key="api_key_widget", 
                            value=display_api_key if disabled else "",
                            disabled=disabled, on_change=clear_connection_notice, 
                            help="如果已保存过密钥，留空则保持不变。否则留空为离线模式。",
                            placeholder="留空则保持原密钥不变" if st.session_state.api_key else "")
    
    # 判断最终使用的 api key
    if not disabled and api_key_input == "" and st.session_state.api_key:
        final_api_key = st.session_state.api_key
    elif disabled:
        final_api_key = st.session_state.api_key
    else:
        final_api_key = api_key_input

    base_url = st.text_input("Base URL", key="base_url_widget", value=saved_settings[1], disabled=disabled,
                             on_change=clear_connection_notice, help="填写发放该 Key 的服务商提供的 OpenAI 兼容接口地址。")
    model_name = st.text_input("Model", key="model_name_widget", value=saved_settings[2], disabled=disabled,
                               on_change=clear_connection_notice, help="使用该服务商为你的账号开放的模型 ID。")
    draft_settings = (final_api_key, base_url, model_name)
    has_unsaved_changes = not disabled and draft_settings != saved_settings
    if disabled:
        if final_api_key and st.button("测试连接", use_container_width=True):
            check_ai_settings(saved_settings, save=False)
        col1, col2 = st.columns(2)
        with col1:
            st.button("✏️ 编辑", on_click=toggle_ai_lock, use_container_width=True)
        with col2:
            st.button("🔑 改密", on_click=change_password_dialog, use_container_width=True)
    elif st.button("验证并保存", type="primary", use_container_width=True):
        check_ai_settings(draft_settings, save=True)

    if "connection_notice" in st.session_state:
        level, message = st.session_state.connection_notice
        if level == "error":
            st.error(message)
        else:
            st.success(message)
    if has_unsaved_changes:
        st.caption("请先验证并保存更改，再获取推荐或发起对话。")
    elif not final_api_key:
        st.caption("当前使用离线体验模式。")

st.sidebar.markdown("---")
st.sidebar.header("🕒 历史记录")
if st.sidebar.button("查看历史记录", use_container_width=True):
    history_dialog()

st.sidebar.markdown("---")
st.sidebar.header("👩‍🔬 数字人助手")
st.sidebar.image(avatar_url, use_column_width=True, caption="您的学术检索专属向导")
open_chat = st.sidebar.button("💬 点击与数字人对话", use_container_width=True, type="primary", disabled=has_unsaved_changes)
if open_chat and not has_unsaved_changes:
    chat_dialog()

# ================= 主界面 =================
if st.session_state.current_page == "home":
    st.title("📚 跨库检索式智能转译系统")
    st.markdown("基于多库语法规则，一键生成 CNKI、Web of Science、IEEE Xplore、超星发现 等平台的合规检索式。")

    # Inputs
    tab1, tab2, tab3 = st.tabs(["🧩 概念组拼接模式", "🪄 智能转译模式 (输入完整检索式)", "📱 微信公众号检索"])

    with tab1:
        st.subheader("📝 概念组关键词输入 (每行一个词)")
        col1, col2, col3 = st.columns(3)
    
        with col1:
            st.text_area("A组：对象层 (如：作物, plant)", key="group_a_widget", value=st.session_state.group_a, height=200, on_change=lambda: st.session_state.update(group_a=st.session_state.group_a_widget))
            if st.button("🧹 清空A组", key="clear_a"):
                st.session_state.group_a = ""
                st.rerun()
        with col2:
            st.text_area("B组：危害层 (如：病害, disease)", key="group_b_widget", value=st.session_state.group_b, height=200, on_change=lambda: st.session_state.update(group_b=st.session_state.group_b_widget))
            if st.button("🧹 清空B组", key="clear_b"):
                st.session_state.group_b = ""
                st.rerun()
        with col3:
            st.text_area("D组：方法层 (如：深度学习, YOLO)", key="group_d_widget", value=st.session_state.group_d, height=200, on_change=lambda: st.session_state.update(group_d=st.session_state.group_d_widget))
            if st.button("🧹 清空D组", key="clear_d"):
                st.session_state.group_d = ""
                st.rerun()

    with tab2:
        st.subheader("🪄 输入现有文献库的完整检索式")
        source_query = st.text_area("例如: TS=(\"plant\" OR \"crop\") AND TS=(\"disease\")", key="source_query", height=200)
        if st.button("🚀 解析并更新到概念组", use_container_width=True, disabled=has_unsaved_changes):
            if source_query.strip():
                with st.spinner("AI 正在解析检索式..."):
                    try:
                        groups = parse_query_to_groups(
                            source_query, 
                            st.session_state.api_key, 
                            st.session_state.base_url, 
                            st.session_state.model_name
                        )
                        group_a_str = "\n".join(groups.get("group_a", []))
                        group_b_str = "\n".join(groups.get("group_b", []))
                        group_d_str = "\n".join(groups.get("group_d", []))
                        st.session_state.group_a = group_a_str
                        st.session_state.group_b = group_b_str
                        st.session_state.group_d = group_d_str
                    
                        add_translation_history(source_query, group_a_str, group_b_str, group_d_str)
                    
                        st.toast("✅ 解析成功！已自动填入概念组中。")
                        st.rerun()
                    except AIConnectionError as exc:
                        st.error(str(exc))
            else:
                st.warning("请输入完整的检索式")

        if st.button("🔄 转译为其他文献库语法", type="primary", use_container_width=True, disabled=has_unsaved_changes):
            if source_query.strip():
                with st.spinner("AI 正在解析并转译..."):
                    try:
                        groups = parse_query_to_groups(
                            source_query, 
                            st.session_state.api_key, 
                            st.session_state.base_url, 
                            st.session_state.model_name
                        )
                        group_a_str = "\n".join(groups.get("group_a", []))
                        group_b_str = "\n".join(groups.get("group_b", []))
                        group_d_str = "\n".join(groups.get("group_d", []))
                        st.session_state.group_a = group_a_str
                        st.session_state.group_b = group_b_str
                        st.session_state.group_d = group_d_str
                    
                        add_translation_history(source_query, group_a_str, group_b_str, group_d_str)
                    
                        parsed_a = parse_input(group_a_str)
                        parsed_b = parse_input(group_b_str)
                        parsed_d = parse_input(group_d_str)
                        valid_groups = [parsed_a, parsed_b, parsed_d]
                    
                        if not any(valid_groups):
                            st.session_state.direct_translate_msg = ("warning", "⚠️ 未能从检索式中解析出有效关键词，请检查输入！")
                        elif not dbs:
                            st.session_state.direct_translate_msg = ("warning", "⚠️ 请至少在左侧选择一个目标数据库！")
                        else:
                            results = translate_queries(valid_groups, dbs, start_year, end_year)
                            add_query_history(group_a_str, group_b_str, group_d_str, dbs, start_year, end_year, results)
                            st.session_state.direct_translate_msg = ("success", "✅ 解析并转译成功！")
                            st.session_state.direct_translate_results = results
                    
                        st.rerun()
                    except AIConnectionError as exc:
                        st.error(str(exc))
            else:
                st.warning("请输入完整的检索式")
            
        # 用于在 rerun 后展示单次转译结果
        if "direct_translate_msg" in st.session_state:
            msg_type, msg_text = st.session_state.direct_translate_msg
            if msg_type == "success":
                st.success(msg_text)
            else:
                st.warning(msg_text)
            del st.session_state.direct_translate_msg
        
        if "direct_translate_results" in st.session_state:
            st.markdown("---")
            # 汇总结果
            all_direct_queries = ""
            for db in dbs:
                if db in st.session_state.direct_translate_results:
                    all_direct_queries += f"--- {db} ---\n{st.session_state.direct_translate_results[db]['query']}\n\n"
            
            with st.expander("📋 一键复制所有结果"):
                st.text_area("所有转译结果汇总", value=all_direct_queries, height=150, key="copy_all_direct")
            
            # 导出按钮
            export_direct_md = f"# 跨库检索式转译报告 (智能转译模式)\n\n生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            export_direct_md += f"**源检索式**:\n```sql\n{source_query}\n```\n\n"
            export_direct_md += "---\n\n"
            for db in dbs:
                if db in st.session_state.direct_translate_results:
                    data = st.session_state.direct_translate_results[db]
                    export_direct_md += f"## {db}\n\n**提示**: {data['note']}\n\n```sql\n{data['query']}\n```\n\n"
            
            st.download_button(
                label="📥 导出转译结果",
                data=export_direct_md,
                file_name=f"智能转译报告_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                mime="text/markdown",
                use_container_width=True,
                key="download_direct"
            )

            st.markdown("---")
            for db in dbs:
                if db in st.session_state.direct_translate_results:
                    data = st.session_state.direct_translate_results[db]
                    st.markdown(f"### {db}")
                    st.info(data['note'])
                    st.code(data['query'], language="sql")
                    st.markdown("---")
            del st.session_state.direct_translate_results

    with tab3:
        st.subheader("📱 微信公众号相关文章检索")
        st.markdown("输入您感兴趣的文章主题或相关文章关键词，AI 将为您检索并罗列优质公众号及代表作。")
        
        wechat_topic = st.text_input("文章主题 / 关键词", placeholder="例如：目标检测、农业无人机、YOLOv11 实战...", key="wechat_topic_input")
        
        col_c1, col_c2, col_c3 = st.columns([2, 2, 4])
        with col_c1:
            article_count = st.number_input("检索篇数", min_value=1, max_value=20, value=5, step=1, key="wechat_article_count")
        with col_c2:
            st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
            do_wechat_search = st.button("🔍 确认检索", type="primary", use_container_width=True, disabled=has_unsaved_changes)
        
        if do_wechat_search:
            if wechat_topic.strip():
                with st.spinner("AI 正在深度检索中..."):
                    try:
                        results = search_wechat_articles(
                            wechat_topic,
                            st.session_state.api_key,
                            st.session_state.base_url,
                            st.session_state.model_name,
                            article_count=article_count
                        )
                        st.session_state.wechat_search_results = results
                        st.session_state.wechat_search_topic = wechat_topic
                    except AIConnectionError as exc:
                        st.error(str(exc))
            else:
                st.warning("请输入主题或关键词")
        
        if "wechat_search_results" in st.session_state and st.session_state.wechat_search_results:
            st.markdown(f"### 🔍 关于 “{st.session_state.wechat_search_topic}” 的检索结果")
            
            # 注入自定义 CSS 以调窄行间距并使复制按钮常驻
            components.html("""
                <style>
                /* 强制修改父页面的样式 */
                body {
                    --compact-padding: 2px;
                }
                </style>
                <script>
                const parentDoc = window.parent.document;
                
                // 1. 注入 CSS 到父页面以确保复制按钮图标常驻显示，并调窄间距
                const style = parentDoc.createElement('style');
                style.innerHTML = `
                    /* 调窄列间距 */
                    [data-testid="column"] {
                        padding-left: 5px !important;
                        padding-right: 5px !important;
                    }
                    /* 美化并压缩 st.code 块 */
                    [data-testid="stCodeBlock"] {
                        margin-top: -8px !important;
                        margin-bottom: -8px !important;
                        background-color: transparent !important;
                    }
                    [data-testid="stCodeBlock"] pre {
                        padding: 5px 40px 5px 10px !important;
                        background-color: #f0f2f6 !important;
                        border-radius: 4px !important;
                        font-size: 0.85rem !important;
                    }
                    /* 强制显示复制按钮图标 */
                    [data-testid="stCodeBlock"] button {
                        opacity: 1 !important;
                        visibility: visible !important;
                        display: flex !important;
                        right: 5px !important;
                        top: 50% !important;
                        transform: translateY(-50%) !important;
                        background: rgba(255,255,255,0.8) !important;
                        border-radius: 4px !important;
                        width: 28px !important;
                        height: 28px !important;
                    }
                    /* 调整内容侧重方向的文本 */
                    .compact-text {
                        margin: 0 !important;
                        padding: 2px 0 !important;
                        line-height: 1.3 !important;
                        font-size: 0.9rem !important;
                    }
                `;
                parentDoc.head.appendChild(style);

                // 2. 监听点击事件以显示“复制成功”提示
                parentDoc.addEventListener('click', function(e) {
                    // 检查点击的是否是复制按钮（或者按钮内的图标）
                    const btn = e.target.closest('button');
                    if (btn && (btn.getAttribute('aria-label') === 'Copy to clipboard' || btn.title === 'Copy to clipboard')) {
                        // 延迟一点点显示，确保复制操作已触发
                        setTimeout(() => {
                            const notice = parentDoc.createElement('div');
                            notice.innerText = '✅ 复制成功';
                            notice.style.position = 'fixed';
                            notice.style.top = '80px';
                            notice.style.left = '50%';
                            notice.style.transform = 'translateX(-50%)';
                            notice.style.backgroundColor = '#00cc66';
                            notice.style.color = 'white';
                            notice.style.padding = '8px 16px';
                            notice.style.borderRadius = '20px';
                            notice.style.zIndex = '9999999';
                            notice.style.fontSize = '14px';
                            notice.style.fontWeight = 'bold';
                            notice.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
                            notice.style.transition = 'opacity 0.3s, transform 0.3s';
                            
                            parentDoc.body.appendChild(notice);
                            
                            setTimeout(() => {
                                notice.style.opacity = '0';
                                notice.style.transform = 'translateX(-50%) translateY(-10px)';
                                setTimeout(() => parentDoc.body.removeChild(notice), 300);
                            }, 1500);
                        }, 50);
                    }
                }, true); // 使用捕获阶段以确保能截获点击
                </script>
            """, height=0, width=0)

            # 自定义表格头部
            h_col1, h_col2, h_col3 = st.columns([2.5, 4, 3.5])
            h_col1.markdown("**公众号名称**")
            h_col2.markdown("**代表文章标题**")
            h_col3.markdown("**内容侧重方向**")
            st.markdown("<hr style='margin: 5px 0;'>", unsafe_allow_html=True)

            # 遍历结果并显示
            for idx, item in enumerate(st.session_state.wechat_search_results):
                name = item.get('公众号名称', '')
                title = item.get('代表文章标题', '')
                direction = item.get('内容侧重方向', '')
                
                row_col1, row_col2, row_col3 = st.columns([2.5, 4, 3.5])
                
                with row_col1:
                    st.code(name, language=None)
                with row_col2:
                    st.code(title, language=None)
                with row_col3:
                    st.markdown(f"<p class='compact-text'>{direction}</p>", unsafe_allow_html=True)
                
                st.markdown("<hr style='margin: 2px 0;'>", unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # 导出功能
            export_wechat_md = f"# 微信公众号文章检索报告\n\n检索主题: {st.session_state.wechat_search_topic}\n生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            export_wechat_md += "| 公众号名称 | 代表文章标题 | 内容侧重方向 |\n"
            export_wechat_md += "| :--- | :--- | :--- |\n"
            for item in st.session_state.wechat_search_results:
                export_wechat_md += f"| {item.get('公众号名称', '')} | {item.get('代表文章标题', '')} | {item.get('内容侧重方向', '')} |\n"
            
            st.download_button(
                label="📥 导出为表格报告 (Markdown)",
                data=export_wechat_md,
                file_name=f"微信检索报告_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                mime="text/markdown",
                use_container_width=True,
                key="download_wechat"
            )
            
            if st.button("🧹 清空检索结果", key="clear_wechat"):
                del st.session_state.wechat_search_results
                del st.session_state.wechat_search_topic
                st.rerun()

    # AI 推荐模块
    st.markdown("---")
    st.subheader("🤖 AI 智能同义词推荐")
    ai_col1, ai_col2, ai_col3 = st.columns([2, 2, 1])

    with ai_col1:
        st.selectbox("选择要扩充的概念组", ["A组：对象层", "B组：危害层", "D组：方法层"], key="target_group_widget")
    with ai_col2:
        seed_keyword = st.text_input("输入种子词汇 (例如：番茄 或 分割)")
    with ai_col3:
        st.markdown("<br>", unsafe_allow_html=True)
        get_recommendations = st.button("✨ 获取推荐", use_container_width=True, disabled=has_unsaved_changes)

    if get_recommendations and not has_unsaved_changes:
        if seed_keyword.strip():
            with st.spinner("AI 正在思考..."):
                try:
                    synonyms = get_synonyms(seed_keyword, *saved_settings)
                except AIConnectionError as exc:
                    st.session_state.recommended_synonyms = []
                    st.error(str(exc))
                else:
                    st.session_state.recommended_synonyms = synonyms
                    add_recommendation_history(seed_keyword, synonyms)
        else:
            st.warning("请输入种子词汇")

    if "recommended_synonyms" in st.session_state and st.session_state.recommended_synonyms:
        st.info("💡 推荐结果：")
        st.multiselect("请勾选您认为合适的同义词：", st.session_state.recommended_synonyms, default=st.session_state.recommended_synonyms, key="selected_synonyms_widget")
        st.button("➕ 将勾选词汇追加到选中组", on_click=append_synonyms)

    st.markdown("---")

    if st.button("🚀 一键生成检索式", type="primary", use_container_width=True):
        # Parse inputs
        group_a = parse_input(st.session_state.group_a)
        group_b = parse_input(st.session_state.group_b)
        group_d = parse_input(st.session_state.group_d)
    
        groups = [group_a, group_b, group_d]
    
        if not any(groups):
            st.warning("⚠️ 请至少输入一组关键词！")
        elif not dbs:
            st.warning("⚠️ 请至少在左侧选择一个目标数据库！")
        else:
            st.success("✅ 生成成功！请复制下方对应的检索式。")
            results = translate_queries(groups, dbs, start_year, end_year)
            
            # 记录到数据库
            add_query_history(st.session_state.group_a, st.session_state.group_b, st.session_state.group_d, dbs, start_year, end_year, results)
        
            # 汇总所有结果方便一键复制
            all_queries = ""
            for db in dbs:
                if db in results:
                    all_queries += f"--- {db} ---\n{results[db]['query']}\n\n"
            
            with st.expander("📋 一键复制所有结果"):
                st.text_area("所有数据库检索式汇总", value=all_queries, height=150)
            
            # 导出按钮
            export_md = f"# 跨库检索转译报告\n\n生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            export_md += f"**检索年份**: {start_year} - {end_year}\n\n"
            export_md += f"**关键词组**:\n- A组: {st.session_state.group_a.replace(chr(10), ', ')}\n- B组: {st.session_state.group_b.replace(chr(10), ', ')}\n- D组: {st.session_state.group_d.replace(chr(10), ', ')}\n\n"
            export_md += "---\n\n"
            for db in dbs:
                if db in results:
                    export_md += f"## {db}\n\n**提示**: {results[db]['note']}\n\n```sql\n{results[db]['query']}\n```\n\n"
            
            st.download_button(
                label="📥 导出为 Markdown 报告",
                data=export_md,
                file_name=f"检索式转译报告_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                mime="text/markdown",
                use_container_width=True
            )

            st.markdown("---")
            # Display results in cards, ONLY for the selected databases in `dbs`
            for db in dbs:
                if db in results:
                    data = results[db]
                    st.markdown(f"### {db}")
                    st.info(data['note'])
                    st.code(data['query'], language="sql")
                    st.markdown("---")

elif st.session_state.current_page == "search_portal":
    st.title("🌐 专业文献检索入口")
    st.markdown("点击下方按钮，即可在新标签页访问各大文献库的专业检索系统。")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.link_button("CNKI (知网)", "https://kns.cnki.net/kns8s/AdvSearch", use_container_width=True)
    col2.link_button("Web of Science", "https://www.webofscience.com/wos/alldb/advanced-search", use_container_width=True)
    col3.link_button("IEEE Xplore", "https://ieeexplore.ieee.org/search/advanced", use_container_width=True)
    col4.link_button("超星发现", "https://www.zhizhen.com/s?adv=Su%3D%28plant%7Ccrop%29*%28disease%7Cpest%29*%28%22deep+learning%22%7CYOLO%29+AND+Y%3D2019%7C2020%7C2021%7C2022%7C2023%7C2024%7C2025%7C2026&aorp=p&size=15&isort=0&x=0_1348", use_container_width=True)

# ================= 注入悬浮可拖拽数字人组件 =================
components.html(f"""
<script>
const parentDoc = window.parent.document;
if (!parentDoc.getElementById('draggable-avatar')) {{
    const avatar = parentDoc.createElement('div');
    avatar.id = 'draggable-avatar';
    avatar.style.position = 'fixed';
    avatar.style.bottom = '50px';
    avatar.style.right = '50px';
    avatar.style.width = '80px';
    avatar.style.height = '80px';
    avatar.style.borderRadius = '50%';
    avatar.style.boxShadow = '0 4px 12px rgba(0,0,0,0.4)';
    avatar.style.cursor = 'grab';
    avatar.style.zIndex = '999999';
    avatar.style.backgroundImage = 'url("{avatar_url}")';
    avatar.style.backgroundSize = 'cover';
    avatar.style.backgroundPosition = 'center';
    avatar.style.userSelect = 'none';
    avatar.style.transition = 'transform 0.2s';

    avatar.onmouseenter = () => avatar.style.transform = 'scale(1.05)';
    avatar.onmouseleave = () => avatar.style.transform = 'scale(1)';

    let isDragging = false;
    let dragged = false;
    let startX, startY, initialX, initialY;

    avatar.addEventListener('mousedown', function(e) {{
        isDragging = true;
        dragged = false;
        startX = e.clientX;
        startY = e.clientY;
        initialX = avatar.offsetLeft;
        initialY = avatar.offsetTop;
        avatar.style.cursor = 'grabbing';
        e.preventDefault(); 
    }});

    parentDoc.addEventListener('mousemove', function(e) {{
        if (isDragging) {{
            dragged = true;
            const dx = e.clientX - startX;
            const dy = e.clientY - startY;
            avatar.style.left = initialX + dx + 'px';
            avatar.style.top = initialY + dy + 'px';
            avatar.style.right = 'auto';
            avatar.style.bottom = 'auto';
        }}
    }});

    parentDoc.addEventListener('mouseup', function(e) {{
        if (isDragging) {{
            isDragging = false;
            avatar.style.cursor = 'grab';
            // 如果没有拖拽，说明是点击事件
            if (!dragged) {{
                // 寻找侧边栏中包含 '点击与数字人对话' 的按钮并触发点击
                const btns = Array.from(parentDoc.querySelectorAll('button'));
                const targetBtn = btns.find(b => b.innerText.includes('点击与数字人对话'));
                if (targetBtn) targetBtn.click();
            }}
        }}
    }});

    parentDoc.body.appendChild(avatar);
}}
</script>
""", height=0, width=0)
