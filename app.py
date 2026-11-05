import streamlit as st
import streamlit.components.v1 as components
import sqlite3
from translator import parse_input, translate_queries
from ai_helper import AIConnectionError, test_connection, get_synonyms, chat_with_agent
from db import (
    load_settings, save_settings, 
    add_chat_msg, get_chat_history, clear_chat_history,
    add_recommendation_history, add_query_history
)

st.set_page_config(page_title="跨库检索式智能转译系统", page_icon="📚", layout="wide")

# ================= 初始化 session state =================
# 从数据库加载 AI 设置
db_settings = load_settings()

if "group_a" not in st.session_state:
    st.session_state.group_a = "作物\n植物\n叶片\ncrop\nplant\nleaf"
if "group_b" not in st.session_state:
    st.session_state.group_b = "病害\n虫害\n杂草\ndisease\npest\nweed"
if "group_d" not in st.session_state:
    st.session_state.group_d = "深度学习\n计算机视觉\n目标检测\ndeep learning\ncomputer vision\nobject detection\nYOLO"
if "messages" not in st.session_state:
    # 从数据库加载历史记录
    st.session_state.messages = get_chat_history()

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


def toggle_ai_lock():
    """解锁以供编辑"""
    clear_connection_notice()
    st.session_state.ai_locked = False


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
            with st.spinner("数字人思考中..."):
                ak = st.session_state.api_key
                bu = st.session_state.base_url
                mn = st.session_state.model_name
                try:
                    response = chat_with_agent([*st.session_state.messages, user_message], ak, bu, mn)
                except AIConnectionError as exc:
                    st.error(str(exc))
                    return
            st.session_state.messages.append(user_message)
            add_chat_msg("user", prompt)
            st.chat_message("assistant").write(response)
            st.session_state.messages.append({"role": "assistant", "content": response})
            add_chat_msg("assistant", response)

st.title("📚 跨库检索式智能转译系统")
st.markdown("基于多库语法规则，一键生成 CNKI、Web of Science、IEEE Xplore、超星发现 等平台的合规检索式。")

st.sidebar.header("⚙️ 检索设置")
dbs = st.sidebar.multiselect(
    "选择目标数据库",
    ["CNKI (知网)", "Web of Science", "IEEE Xplore", "超星发现"],
    default=["CNKI (知网)", "Web of Science", "IEEE Xplore", "超星发现"]
)
start_year = st.sidebar.number_input("起始年份", min_value=1900, max_value=2100, value=2019)
end_year = st.sidebar.number_input("结束年份", min_value=1900, max_value=2100, value=2026)

st.sidebar.markdown("---")
st.sidebar.header("🤖 AI 设置 (OpenAI 兼容)")

# AI 设置输入区
disabled = st.session_state.ai_locked
saved_settings = (st.session_state.api_key, st.session_state.base_url, st.session_state.model_name)
with st.sidebar:
    api_key = st.text_input("API Key (可选)", type="password", key="api_key_widget", value=saved_settings[0],
                            disabled=disabled, on_change=clear_connection_notice, help="留空并保存可使用离线词库。")
    base_url = st.text_input("Base URL", key="base_url_widget", value=saved_settings[1], disabled=disabled,
                             on_change=clear_connection_notice, help="填写发放该 Key 的服务商提供的 OpenAI 兼容接口地址。")
    model_name = st.text_input("Model", key="model_name_widget", value=saved_settings[2], disabled=disabled,
                               on_change=clear_connection_notice, help="使用该服务商为你的账号开放的模型 ID。")
    draft_settings = (api_key, base_url, model_name)
    has_unsaved_changes = not disabled and draft_settings != saved_settings
    if disabled:
        if api_key and st.button("测试连接", use_container_width=True):
            check_ai_settings(saved_settings, save=False)
        st.button("✏️ 编辑", on_click=toggle_ai_lock, use_container_width=True)
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
    elif not api_key:
        st.caption("当前使用离线体验模式。")

st.sidebar.markdown("---")
st.sidebar.header("👩‍🔬 数字人助手")
st.sidebar.image(avatar_url, use_column_width=True, caption="您的学术检索专属向导")
open_chat = st.sidebar.button("💬 点击与数字人对话", use_container_width=True, type="primary", disabled=has_unsaved_changes)
if open_chat and not has_unsaved_changes:
    chat_dialog()

# Inputs
st.subheader("📝 概念组关键词输入 (每行一个词)")
col1, col2, col3 = st.columns(3)

with col1:
    st.text_area("A组：对象层 (如：作物, plant)", key="group_a", height=200)
with col2:
    st.text_area("B组：危害层 (如：病害, disease)", key="group_b", height=200)
with col3:
    st.text_area("D组：方法层 (如：深度学习, YOLO)", key="group_d", height=200)

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
        
        # Display results in cards
        for db, data in results.items():
            st.markdown(f"### {db}")
            st.info(data['note'])
            st.code(data['query'], language="sql")
            st.markdown("---")

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
