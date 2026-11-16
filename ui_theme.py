"""Shared visual theme for the research workspace."""
import streamlit as st

def apply_theme():
    st.markdown("""<style>
    html,body,[class*="css"] {font-family: "Microsoft YaHei", "Segoe UI", sans-serif;}
    .stApp {background:#F5F7FB;color:#172B4D;}
    .block-container {max-width:1280px;padding-top:2rem;padding-bottom:7rem;}
    h1 {font-size:28px!important;letter-spacing:-.5px;}
    h2,h3 {color:#17365B;}
    [data-testid="stSidebar"] {background:white;border-right:1px solid #E3EAF3;}
    [data-testid="stTextArea"] textarea, [data-testid="stTextInput"] input {background:white;border-radius:10px;}
    [data-testid="stTabs"] {background:white;padding:20px;border:1px solid #E3EAF3;border-radius:16px;}
    .stButton button,.stDownloadButton button {border-radius:9px;min-height:40px;}
    button:focus-visible,a:focus-visible {outline:3px solid #0891B2!important;outline-offset:3px;}
    [data-testid="stCodeBlock"] {border:1px solid #DFE7F1;border-radius:10px;}
    
    /* 侧边栏菜单长方形样式 */
    [data-testid="stSidebar"] div[role="radiogroup"] {
        gap: 8px;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] > label {
        background-color: #f8f9fa !important;
        border: 1px solid #e9ecef !important;
        padding: 12px 16px !important;
        border-radius: 10px !important;
        margin-bottom: 0px !important;
        cursor: pointer !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        display: flex !important;
        align-items: center !important;
        width: 100% !important;
        color: #495057 !important;
    }
    /* 隐藏单选圆点 */
    [data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-child {
        display: none !important;
    }
    /* 选中状态 */
    [data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
        background-color: #17365B !important;
        color: white !important;
        border-color: #17365B !important;
        box-shadow: 0 4px 6px rgba(23, 54, 91, 0.2) !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) p {
        color: white !important;
        font-weight: 600 !important;
    }
    /* 悬停效果 */
    [data-testid="stSidebar"] div[role="radiogroup"] label:hover {
        background-color: #edf2f7 !important;
        border-color: #cbd5e0 !important;
        transform: translateY(-1px) !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked):hover {
        background-color: #1e4576 !important;
        transform: translateY(-1px) !important;
    }
    
    @media(max-width:640px){.block-container{padding:1rem 1rem 7rem;}[data-testid="stHorizontalBlock"]{flex-wrap:wrap;}[data-testid="column"]{width:100%!important;flex:1 1 100%!important;}[data-testid="stSidebar"] [data-testid="stImage"]{display:none;}h1{font-size:24px!important;}}
    </style>""", unsafe_allow_html=True)
