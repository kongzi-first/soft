# 文件名: app.py
from flask import Flask, jsonify, request # 确保导入了 request

app = Flask(__name__)

# 创建一个 /test 路由(API端点)
@app.route('/test', methods=['GET'])
def test_connection():
    # 当Unity访问这个地址时，返回一个JSON
    return jsonify({"message": "Hello from Flask!"})
@app.route('/')
def home():
    # 返回一个简单的JSON，表明服务已启动
    # 这就像餐厅门口挂一个“正在营业”的牌子
    return jsonify({"status": "ok", "message": "Flask server is running on Vercel!"})
@app.route('/asr', methods=['POST'])
def handle_asr():
    # 检查请求中是否包含文件
    if 'audio_data' not in request.files:
        # 如果没有名为 'audio_data' 的文件，返回错误
        return jsonify({"error": "No audio file part"}), 400

    file = request.files['audio_data']

    # 检查文件名是否为空
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file:
        # 在实际应用中，你会在这里处理文件，比如保存或直接传给OpenAI
        # 但现在，我们只是确认收到了文件，然后直接返回一个模拟结果
        
        # 为了调试，我们可以在服务器日志里打印一下，确认收到了文件
        print(f"Received file: {file.filename}, content type: {file.content_type}")
        
        # 无论收到什么，都返回一个固定的JSON
        return jsonify({"text": "这是模拟的语音识别结果"})
    
if __name__ == '__main__':
    # 运行在本地，端口为5000
    app.run(host='0.0.0.0', port=6006)
