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
        self.messages = []

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


class SessionManager:
    def __init__(self):
        # 使用字典存储所有会话，key=session_id, value=ChatSession对象
        self.sessions = {}

    def create_session(self) -> str:
        """创建一个新的会话，并返回其唯一ID"""
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = ChatSession()
        print(f"新会话已创建: {session_id}")
        return session_id

    def get_session(self, session_id: str) -> ChatSession:
        """根据ID获取一个已存在的会话"""
        return self.sessions.get(session_id)

    def get_all_sessions_info(self) -> dict:
        """获取所有会话的摘要信息（ID和第一个问题）"""
        info = {}
        for session_id, session in self.sessions.items():
            # 使用会话的第一个用户问题作为标题，如果没有则使用默认标题
            title = session.messages[0]['content'] if session.messages else "新对话"
            info[session_id] = title
        return info


# 创建一个全局的会话管理器实例
session_manager = SessionManager()

# ==============================================================================
# 3. Flask 应用和重构后的路由
# ==============================================================================
app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')


# 【修改】/chat 路由现在需要接收 session_id
@app.route('/chat', methods=['POST'])
def handle_chat():
    data = request.get_json()
    session_id = data.get('session_id')
    question = data.get('question')

    if not all([session_id, question]):
        return jsonify({"error": "请求中缺少 'session_id' 或 'question'"}), 400

    chat_session = session_manager.get_session(session_id)
    if not chat_session:
        return jsonify({"error": "无效的 session_id"}), 404

    print(f"会话[{session_id[:8]}...] 收到问题: {question}")
    answer = chat_session.ask(question)
    print(f"会话[{session_id[:8]}...] GPT 回答: {answer}")

    # 将问答记录保存到会话中
    chat_session.messages.append({"role": "user", "content": question})
    chat_session.messages.append({"role": "gpt", "content": answer})

    return jsonify({"answer": answer})


# 【新增】/session/new 路由用于创建新会话
@app.route('/session/new', methods=['POST'])
def new_session():
    session_id = session_manager.create_session()
    # 顺便返回所有会话的列表，方便前端更新侧边栏
    all_sessions = session_manager.get_all_sessions_info()
    return jsonify({"new_session_id": session_id, "all_sessions": all_sessions})


# 【新增】/session/all 路由用于获取所有会话列表
@app.route('/session/all', methods=['GET'])
def get_all_sessions():
    return jsonify(session_manager.get_all_sessions_info())


# 【新增】/session/history 路由用于获取指定会话的历史记录
@app.route('/session/history', methods=['GET'])
def get_session_history():
    session_id = request.args.get('session_id')
    if not session_id:
        return jsonify({"error": "缺少 session_id 参数"}), 400

    chat_session = session_manager.get_session(session_id)
    if not chat_session:
        return jsonify({"error": "无效的 session_id"}), 404

    return jsonify({"messages": chat_session.messages})

@app.route('/session/delete', methods=['POST'])
def delete_session():
    data = request.get_json()
    session_id_to_delete = data.get('session_id')

    if not session_id_to_delete:
        return jsonify({"error": "请求中缺少 'session_id'"}), 400

    # 检查会话是否存在并删除
    if session_id_to_delete in session_manager.sessions:
        del session_manager.sessions[session_id_to_delete]
        print(f"会话已删除: {session_id_to_delete}")
        return jsonify({"status": "ok", "message": "会话已删除"})
    else:
        return jsonify({"error": "无效的 session_id"}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=6006, debug=True)