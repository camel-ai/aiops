import os
import json
import uuid
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename, safe_join
from PIL import Image

app = Flask(__name__)
CORS(app)

# 设置上传目录
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'upload')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.route('/api/chat/upload', methods=['POST'])
def upload_file():
    """处理聊天中的文件上传请求"""
    try:
        # 设置用户目录 (测试用固定用户名)
        username = 'test_user'
        upload_dir = os.path.join(UPLOAD_FOLDER, username)
        
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)
        
        # 检查是否有文件上传
        if 'files' not in request.files:
            return jsonify({"error": "没有上传文件"}), 400
            
        uploaded_files = request.files.getlist('files')
        if not uploaded_files or uploaded_files[0].filename == '':
            return jsonify({"error": "文件为空"}), 400
            
        # 允许的图片格式
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}
        
        # 处理上传的文件
        file_info_list = []
        for file in uploaded_files:
            # 验证文件类型
            original_filename = file.filename
            file_ext = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else ''
            
            if file_ext not in allowed_extensions:
                continue  # 跳过不允许的文件类型
                
            # 生成安全的文件名
            filename = secure_filename(f"{uuid.uuid4().hex}.{file_ext}")
            file_path = os.path.join(upload_dir, filename)
            
            # 保存文件
            file.save(file_path)
            
            # 生成缩略图路径
            thumbnail_filename = f"thumb_{filename}"
            thumbnail_path = os.path.join(upload_dir, thumbnail_filename)
            
            # 生成缩略图
            try:
                with Image.open(file_path) as img:
                    img.thumbnail((100, 100))  # 调整为100x100的缩略图
                    img.save(thumbnail_path)
            except Exception as e:
                print(f"生成缩略图失败: {str(e)}")
                # 如果缩略图生成失败，使用原图作为缩略图
                thumbnail_filename = filename
            
            # 构建文件信息
            file_info = {
                "original_name": original_filename,
                "saved_name": filename,
                "thumbnail_name": thumbnail_filename,
                "file_type": file_ext,
                "file_url": f"/api/chat/files/{username}/{filename}",
                "thumbnail_url": f"/api/chat/files/{username}/{thumbnail_filename}",
                "is_image": True
            }
            
            file_info_list.append(file_info)
            
        if not file_info_list:
            return jsonify({"error": "没有有效的图片文件上传"}), 400
            
        # 返回成功结果和文件信息
        return jsonify({
            "success": True,
            "message": f"成功上传 {len(file_info_list)} 个文件",
            "files": file_info_list
        })
        
    except Exception as e:
        print(f"文件上传处理失败: {str(e)}")
        return jsonify({"error": f"文件上传失败: {str(e)}"}), 500

@app.route('/api/chat/files/<string:username>/<string:filename>', methods=['GET'])
def get_chat_file(username, filename):
    """获取上传的聊天文件"""
    try:
        # 验证路径安全性
        file_path = safe_join(UPLOAD_FOLDER, username, filename)
        if not os.path.exists(file_path):
            return jsonify({"error": "文件不存在"}), 404
            
        # 返回文件
        return send_file(file_path)
    except Exception as e:
        print(f"获取文件失败: {str(e)}")
        return jsonify({"error": f"获取文件失败: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000) 