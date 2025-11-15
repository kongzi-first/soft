# 文件名: app.py

import json
import uuid
import requests
import time
# 导入 render_template 来渲染HTML页面
from flask import Flask, jsonify, request, render_template

# ... (API_URL, HEADERS, RAW_DATA, ChatSession 类的代码保持不变) ...
# 请确保你的凭证是最新的！
# ==============================================================================
# 1. GPT 对话核心代码 (这部分不用动)
# ==============================================================================
API_URL = "https://share.zhangsan.cool/backend-api/conversation"
HEADERS = {
    # ... 请确保这里的凭证是最新的 ...
    "authorization": "Bearer 5a79549e250ea720081f765c6631865c",
    "openai-sentinel-chat-requirements-token": "994e7fb1-1953-4d0f-9e8d-8dc33ef79a76",
    "cookie": "oai-did=f1bc09d2-d193-4352-82e4-7ae8176cea1d; oai-hm=AGENDA_TODAY%20%7C%20ON_YOUR_MIND; oai-gn=; oai-locale=zh-CN; oai-nav-state=1; __Secure-next-auth.session-token=15eab5v1e7y4kydda0xfb84m8p3swy30; next-device-id=26fdb8c5mhvevuz3; oai-last-model=gemini-2.5-plus; _dd_s=rum=0&expire=1763173459570",
    "accept": "text/event-stream", "accept-language": "zh-CN,zh;q=0.9,en;q=0.8", "content-type": "application/json",
    "oai-client-version": "prod-cc38ec2e6b91c1fedb3366fbf95d4336b52ee140",
    "oai-device-id": "f1bc09d2-d193-4352-82e4-7ae8176cea1d", "oai-language": "zh-CN",
    "origin": "https://share.zhangsan.cool", "referer": "https://share.zhangsan.cool/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
}
RAW_DATA = r'''{
  "action": "next", "messages": [{"id": "aaa", "author": { "role": "user" }, "create_time": 1718180905.159, "content": { "content_type": "text", "parts": ["你好"] }}],
  "conversation_id": null, "parent_message_id": "bbb", "model": "gpt-5-1",
  "timezone_offset_min": -480, "history_and_training_disabled": false,
  "conversation_mode": { "kind": "primary_assistant" }, "force_paragen": false, "force_rate_limit": false
}'''


class ChatSession:
    def __init__(self):
        self.conversation_id = None
        self.parent_message_id = str(uuid.uuid4())

    def build_payload(self, q: str) -> dict:
        p = json.loads(RAW_DATA);
        p["messages"][0]["content"]["parts"] = [q];
        p["messages"][0]["id"] = str(uuid.uuid4());
        p["messages"][0]["create_time"] = time.time();
        p["conversation_id"] = self.conversation_id;
        p["parent_message_id"] = self.parent_message_id;
        return p

    def ask(self, question: str) -> str:
        payload = self.build_payload(question)
        full_text = ""
        last_assistant_message_id = None
        conv_id_from_resp = None

        try:
            with requests.post(
                    API_URL,
                    headers=HEADERS,
                    json=payload,
                    stream=True,
                    timeout=300,
            ) as resp:
                print(f"服务器响应状态码: {resp.status_code}")
                if resp.status_code >= 400:
                    error_detail = resp.text
                    print(f"请求失败，状态码 {resp.status_code}, 详情: {error_detail}")
                    if resp.status_code == 401: return "错误：认证失败(401)。'authorization' token 已过期或无效，请更新。"
                    if resp.status_code == 403: return "错误：禁止访问(403)。'requirements-token' 或 Cookie 已过期，请更新。"
                    return f"错误：请求失败，状态码 {resp.status_code}。请检查后端日志。"

                resp.raise_for_status()

                for line in resp.iter_lines(decode_unicode=True):
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[len("data:"):].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        obj = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(obj, dict):
                        continue

                    if "conversation_id" in obj and obj["conversation_id"] is not None:
                        conv_id_from_resp = obj["conversation_id"]

                    v = obj.get("v")

                    if isinstance(v, list):  # 情况 1：v 是“操作列表”
                        for op in v:
                            if not isinstance(op, dict): continue
                            op_type = op.get("o")
                            path = op.get("p", "")
                            val = op.get("v")
                            if op_type == "append" and isinstance(val, str) and "/message/content/parts" in path:
                                full_text += val
                            if isinstance(val, dict) and val.get("author", {}).get("role") == "assistant":
                                msg_id = val.get("id")
                                if isinstance(msg_id, str): last_assistant_message_id = msg_id
                    elif isinstance(v, dict) and "message" in v:  # 情况 2：v 是一个完整的 snapshot
                        msg = v["message"]
                        if isinstance(msg, dict) and msg.get("author", {}).get("role") == "assistant":
                            msg_id = msg.get("id")
                            if isinstance(msg_id, str): last_assistant_message_id = msg_id
                            parts = msg.get("content", {}).get("parts")
                            if isinstance(parts, list) and parts and isinstance(parts[0], str):
                                # 这是一个完整的文本快照，直接覆盖之前的流式文本
                                full_text = parts[0]

            if not full_text:
                return "抱歉，未能从API响应中解析出回答。"

            if conv_id_from_resp: self.conversation_id = conv_id_from_resp
            if last_assistant_message_id: self.parent_message_id = last_assistant_message_id

            return full_text
        except requests.exceptions.RequestException as e:
            print(f"请求GPT API时发生网络错误: {e}")
            return f"错误：无法连接到GPT服务。请检查网络连接和API地址。详情: {e}"


# ==============================================================================
# 2. Flask 应用和全局会话 (这部分不用动)
# ==============================================================================
app = Flask(__name__)
chat_session = ChatSession()


# ==============================================================================
# 3. 【核心修改】创建根路由，用于显示聊天页面
# ==============================================================================
@app.route('/')
def home():
    # 当用户访问根目录时，返回 index.html 页面
    return render_template('index.html')


# ==============================================================================
# 4. 保留 /chat 路由作为后端的API接口
#    (前端页面的JavaScript会调用这个接口)
# ==============================================================================
@app.route('/chat', methods=['POST'])
def handle_chat():
    # 这个接口现在专门给前端的JS调用
    if not request.is_json:
        return jsonify({"error": "请求必须是JSON格式"}), 400
    data = request.get_json()
    question = data.get('question')
    if not question:
        return jsonify({"error": "JSON中缺少 'question' 字段"}), 400

    print(f"收到网页问题: {question}")
    answer = chat_session.ask(question)
    print(f"GPT 回答: {answer}")

    return jsonify({"answer": answer})

@app.route('/reset', methods=['POST'])
def reset_session():
    global chat_session
    # 通过创建一个新的ChatSession实例来重置会话
    chat_session = ChatSession()
    print("会话已重置，新对话已开始。")
    return jsonify({"status": "ok", "message": "Session has been reset."})

# ==============================================================================
# 5. 主程序入口 (这部分不用动)
# ==============================================================================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=6006, debug=True)

