import json
from urllib.parse import urlsplit, urlunsplit

import requests


class AIConnectionError(Exception):
    """可在界面直接展示的 API 错误，不包含密钥或原始响应。"""


def _connection_settings(api_key, base_url, model_name):
    key = (api_key or "").strip()
    if key.lower().startswith("bearer "):
        key = key[7:].strip()
    if not key or not key.isascii() or not all("!" <= char <= "~" for char in key):
        raise AIConnectionError("请填写完整的 API Key，并检查是否混入了空格、换行或中文符号。")
    url = (base_url or "").strip()
    try:
        parts = urlsplit(url)
        valid_url = (parts.scheme in {"http", "https"} and parts.hostname
                     and parts.username is None and parts.fragment == ""
                     and not any(c.isspace() for c in url))
        # urlsplit 只在访问 port 时检查端口是否合法。
        _ = parts.port
    except ValueError:
        valid_url = False
    if not valid_url:
        raise AIConnectionError("Base URL 格式无效。请填写服务商提供的完整 http 或 https 接口地址。")

    path = parts.path.rstrip("/")
    if path.endswith("/chat/completions"):
        path = path[:-len("/chat/completions")]
    if not path and parts.hostname in {"api.openai.com", "ai.space.opencsg.com"}:
        path = "/v1"
    model = (model_name or "").strip()
    if not model:
        raise AIConnectionError("请填写该服务商提供的模型 ID。")
    return key, urlunsplit(parts._replace(path=path)), model


def _raise_service_error(status, data):
    error = data.get("error") if isinstance(data, dict) else None
    code = str(error.get("code", "")).lower() if isinstance(error, dict) else ""
    if code in {"model_not_found", "invalid_model"}:
        advice = "请核对模型 ID，并确认当前 Key 有权使用该模型。"
    elif status == 401:
        advice = "身份验证失败，请检查 Key 是否完整、有效，并由当前服务商签发。"
    elif status == 403:
        advice = "服务商拒绝访问，请检查 Key 的模型权限、IP 或区域限制。"
    elif status == 402 or code in {"insufficient_quota", "insufficient_balance"}:
        advice = "可用额度不足，请检查服务商账户的余额和配额。"
    elif status == 404:
        advice = "接口或模型不存在，请核对 Base URL 的路径和模型 ID。"
    elif status == 429:
        advice = "请求频率或额度达到限制，请检查配额或稍后重试。"
    elif 300 <= status < 400:
        advice = "接口返回重定向，请直接填写服务商提供的最终 API 地址。"
    elif status >= 500:
        advice = "服务商或网关暂时出错，请稍后重试。"
    else:
        advice = "请确认地址支持 OpenAI 兼容的 Chat Completions 接口，并核对模型 ID。"
    raise AIConnectionError(f"服务商返回错误（HTTP {status}）。{advice}")


def _chat_completion(settings, messages):
    key, base_url, model = settings
    parts = urlsplit(base_url)
    endpoint = urlunsplit(parts._replace(path=parts.path + "/chat/completions"))
    try:
        response = requests.post(
            endpoint, headers={"Authorization": f"Bearer {key}"},
            json={"model": model, "messages": messages, "stream": False},
            timeout=(10, 90), allow_redirects=False,
        )
    except requests.exceptions.ProxyError:
        raise AIConnectionError("无法连接代理服务器，请检查系统代理和网络设置。") from None
    except requests.exceptions.SSLError:
        raise AIConnectionError("TLS 验证失败，请检查接口域名、证书及系统代理。") from None
    except requests.exceptions.Timeout:
        raise AIConnectionError("连接或等待模型回复超时，请检查网络或稍后重试。") from None
    except requests.exceptions.RequestException:
        raise AIConnectionError("无法访问 API，请检查 Base URL、网络、代理及本地服务是否已启动。") from None

    try:
        data = response.json()
    except ValueError:
        data = None
    if not 200 <= response.status_code < 300 or (isinstance(data, dict) and data.get("error")):
        _raise_service_error(response.status_code, data)
    if not isinstance(data, dict) or not isinstance(data.get("choices"), list) or not data["choices"]:
        raise AIConnectionError("已收到响应，但缺少模型回复。请检查 Base URL 是否指向对话 API。")
    choice = data["choices"][0]
    message = choice.get("message") if isinstance(choice, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        if isinstance(message, dict) and message.get("reasoning_content"):
            raise AIConnectionError("模型仅返回了推理过程，未给出最终回答。请检查服务商的输出限制或更换模型后重试。")
        raise AIConnectionError("模型返回了空回复，请检查模型 ID 或稍后重试。")
    return content.strip()


def test_connection(api_key, base_url, model_name):
    """用实际对话接口验证模型和密钥，并返回可保存的配置。"""
    settings = _connection_settings(api_key, base_url, model_name)
    _chat_completion(settings, [{"role": "user", "content": "请只回复 OK。"}])
    return settings

def get_synonyms(keyword, api_key, base_url, model_name):
    # Mock data for demonstration if no API key is provided
    if not (api_key or "").strip():
        keyword_lower = keyword.lower()
        if "深度学习" in keyword_lower or "deep learning" in keyword_lower:
            return ["CNN", "卷积神经网络", "ResNet", "YOLO", "Transformer", "ViT", "图像识别", "image recognition"]
        elif "病害" in keyword_lower or "disease" in keyword_lower:
            return ["病原菌", "真菌", "细菌", "pathogen", "fungus", "bacteria", "plant disease", "感染"]
        elif "番茄" in keyword_lower or "tomato" in keyword_lower:
            return ["Solanum lycopersicum", "西红柿", "茄科", "cherry tomato", "tomato leaf"]
        elif "分割" in keyword_lower or "segmentation" in keyword_lower:
            return ["实例分割", "语义分割", "instance segmentation", "semantic segmentation", "Mask R-CNN", "U-Net"]
        else:
            return [
                f"{keyword}同义词1",
                f"{keyword}同义词2",
                "academic term",
                "related keyword"
            ]

    settings = _connection_settings(api_key, base_url, model_name)
    prompt = (
        f"请为学术检索词“{keyword}”提供5-8个相关的同义词、下位词或常用学术表达（需包含中文和英文）。"
        '请严格以 JSON 数组的格式返回，例如：["同义词1", "同义词2", "synonym1", "synonym2"]。'
        "不要返回任何其他解释文本或 Markdown 标记。"
    )
    content = _chat_completion(settings, [
        {"role": "system", "content": "你是一个农业与计算机视觉领域的学术检索辅助专家。"},
        {"role": "user", "content": prompt},
    ])
    content = content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        words = json.loads(content)
    except ValueError:
        words = None
    if not isinstance(words, list) or not words or not all(isinstance(w, str) and w.strip() for w in words):
        raise AIConnectionError("已连接模型，但推荐结果不是有效的词语列表。请重试或更换模型。")
    return [word.strip() for word in words]

def chat_with_agent(messages, api_key, base_url, model_name):
    """数字人对话功能"""
    if not (api_key or "").strip():
        return "您尚未配置有效的 API Key，我目前处于离线体验模式。请在左侧配置您的 API Key 唤醒我！"
        
    settings = _connection_settings(api_key, base_url, model_name)
    api_messages = [{"role": "system", "content": "你是一个学术检索与农业计算机视觉领域的数字人助手，负责解答用户的疑问。你的回答应该专业、简洁且友好。"}]
    api_messages.extend({"role": msg["role"], "content": msg["content"]} for msg in messages)
    return _chat_completion(settings, api_messages)
