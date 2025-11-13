# 文件名: app.py
from flask import Flask, jsonify

app = Flask(__name__)

# 创建一个 /test 路由(API端点)
@app.route('/test', methods=['GET'])
def test_connection():
    # 当Unity访问这个地址时，返回一个JSON
    return jsonify({"message": "Hello from Flask!"})

if __name__ == '__main__':
    # 运行在本地，端口为5000
    app.run(host='0.0.0.0', port=6006)
