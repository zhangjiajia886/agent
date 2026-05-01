#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
南网推理平台模型验证脚本
用于测试 southgrid API 的连通性和模型功能
"""

import os
import sys
import json
import time
import base64
import hmac
from hashlib import sha256
from datetime import datetime, timedelta
import requests
from dotenv import load_dotenv
import urllib3

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 加载环境变量
load_dotenv(dotenv_path=".env", override=False)

def get_sign(data, key):
    """生成HMAC-SHA256签名"""
    key = key.encode("utf-8")
    message = data.encode("utf-8")
    sign = base64.b64encode(hmac.new(key, message, digestmod=sha256).digest())
    sign = str(sign, 'utf-8')
    return sign

def get_auth_info(customer_code, secret_key):
    """生成认证信息"""
    gmt_format = "%a, %d %b %Y %H:%M:%S GMT"
    x_date = (datetime.now() - timedelta(hours=8)).strftime(gmt_format)
    str_to_sign = "x-date: " + x_date
    sign_str = get_sign(str_to_sign, secret_key)
    auth = f'hmac username="{customer_code}", algorithm="hmac-sha256", headers="x-date", signature="{sign_str}"'
    return x_date, auth

def test_southgrid_model(
    api_url: str,
    model: str,
    custcode: str,
    api_key: str,
    componentcode: str,
    test_message: str = "你好，请介绍一下你自己。",
    temperature: float = 0.6,
    max_tokens: int = 512
):
    """
    测试南网推理平台模型
    
    Args:
        api_url: API地址，例如 http://192.168.0.131:5030/ai-gateway/predict
        model: 模型名称，例如 qwen2.5-omni:7b
        custcode: 客户编码
        api_key: API密钥
        componentcode: 组件编码
        test_message: 测试消息
        temperature: 温度参数
        max_tokens: 最大token数
    """
    
    print("=" * 80)
    print("南网推理平台模型验证测试")
    print("=" * 80)
    print(f"API地址: {api_url}")
    print(f"模型名称: {model}")
    print(f"客户编码: {custcode}")
    print(f"组件编码: {componentcode}")
    print(f"测试消息: {test_message}")
    print("=" * 80)
    
    # 1. 检查参数完整性
    print("\n[步骤 1/5] 检查参数完整性...")
    missing_params = []
    if not api_url:
        missing_params.append("api_url")
    if not model:
        missing_params.append("model")
    if not custcode:
        missing_params.append("custcode")
    if not api_key:
        missing_params.append("api_key")
    if not componentcode:
        missing_params.append("componentcode")
    
    if missing_params:
        print(f"❌ 缺少必要参数: {', '.join(missing_params)}")
        return False
    print("✅ 参数完整")
    
    # 2. 测试网络连通性
    print("\n[步骤 2/5] 测试网络连通性...")
    try:
        # 提取主机和端口
        from urllib.parse import urlparse
        parsed = urlparse(api_url)
        host = parsed.hostname
        port = parsed.port or 80
        
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print(f"✅ 网络连通 ({host}:{port})")
        else:
            print(f"❌ 网络不通 ({host}:{port})")
            return False
    except Exception as e:
        print(f"❌ 网络测试失败: {e}")
        return False
    
    # 3. 生成认证信息
    print("\n[步骤 3/5] 生成认证信息...")
    try:
        x_date, authorization = get_auth_info(custcode, api_key)
        print(f"✅ 认证信息生成成功")
        print(f"   X-Date: {x_date}")
        print(f"   Authorization: {authorization[:50]}...")
    except Exception as e:
        print(f"❌ 认证信息生成失败: {e}")
        return False
    
    # 4. 构建请求
    print("\n[步骤 4/5] 构建API请求...")
    headers = {
        "Content-Type": "application/json",
        "x-date": x_date,
        "Authorization": authorization
    }
    
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": test_message}
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
        "componentCode": componentcode
    }
    
    print(f"✅ 请求构建完成")
    print(f"   Headers: {json.dumps({k: v[:50] + '...' if len(str(v)) > 50 else v for k, v in headers.items()}, indent=2, ensure_ascii=False)}")
    print(f"   Payload: {json.dumps({k: v if k != 'messages' else '...' for k, v in payload.items()}, indent=2, ensure_ascii=False)}")
    
    # 5. 发送请求
    print("\n[步骤 5/5] 发送API请求...")
    start_time = time.time()
    
    try:
        response = requests.post(
            api_url,
            headers=headers,
            json=payload,
            timeout=60,
            stream=True,
            verify=False
        )
        
        print(f"✅ 连接成功")
        print(f"   状态码: {response.status_code}")
        
        # 检查响应状态
        if response.status_code == 200:
            print("✅ HTTP状态码正常 (200)")
            print("\n开始接收流式响应...")
            
            # 处理流式响应
            full_content = ""
            chunk_count = 0
            
            try:
                for line in response.iter_lines():
                    if line:
                        line_str = line.decode('utf-8')
                        
                        # 跳过空行和注释
                        if not line_str.strip() or line_str.startswith(':'):
                            continue
                        
                        # 解析 SSE 格式: data: {...}
                        if line_str.startswith('data: '):
                            data_str = line_str[6:]  # 移除 "data: " 前缀
                            
                            # 跳过 [DONE] 标记
                            if data_str.strip() == '[DONE]':
                                break
                            
                            try:
                                chunk_data = json.loads(data_str)
                                chunk_count += 1
                                
                                # 提取内容
                                if "choices" in chunk_data and len(chunk_data["choices"]) > 0:
                                    delta = chunk_data["choices"][0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        full_content += content
                                        print(content, end='', flush=True)
                                
                            except json.JSONDecodeError:
                                continue
                
                elapsed_time = time.time() - start_time
                print(f"\n\n✅ 流式响应完成 (耗时: {elapsed_time:.2f}秒)")
                print(f"   接收到 {chunk_count} 个数据块")
                
                if full_content:
                    print(f"\n✅ 模型响应内容:")
                    print("-" * 80)
                    print(full_content)
                    print("-" * 80)
                    print(f"\n🎉 测试成功！模型 {model} 工作正常")
                    return True
                else:
                    print(f"❌ 响应中没有内容")
                    return False
                    
            except Exception as e:
                print(f"\n❌ 流式响应处理失败: {e}")
                return False
        else:
            print(f"❌ HTTP状态码异常: {response.status_code}")
            print(f"响应内容: {response.text[:500]}")
            return False
            
    except requests.exceptions.Timeout:
        print(f"❌ 请求超时 (>60秒)")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"❌ 连接错误: {e}")
        return False
    except Exception as e:
        print(f"❌ 请求失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("\n" + "=" * 80)
    print("南网推理平台模型验证工具")
    print("=" * 80 + "\n")
    
    # 从环境变量或命令行参数获取配置
    api_url = os.getenv("MMP_BINDING_HOST", "http://192.168.0.131:5030/ai-gateway/predict")
    model = os.getenv("MMP_MODEL", "qwen2.5-omni:7b")
    custcode = os.getenv("MMP_CUSTCODE", "")
    api_key = os.getenv("MMP_BINDING_API_KEY", "")
    componentcode = os.getenv("MMP_COMPONENTCODE", "")
    
    # 支持命令行参数覆盖
    if len(sys.argv) > 1:
        api_url = sys.argv[1]
    if len(sys.argv) > 2:
        model = sys.argv[2]
    if len(sys.argv) > 3:
        custcode = sys.argv[3]
    if len(sys.argv) > 4:
        api_key = sys.argv[4]
    if len(sys.argv) > 5:
        componentcode = sys.argv[5]
    
    # 运行测试
    success = test_southgrid_model(
        api_url=api_url,
        model=model,
        custcode=custcode,
        api_key=api_key,
        componentcode=componentcode,
        test_message="你好，请用一句话介绍你自己。",
        temperature=0.6,
        max_tokens=512
    )
    
    print("\n" + "=" * 80)
    if success:
        print("✅ 测试结果: 成功")
        print("=" * 80 + "\n")
        sys.exit(0)
    else:
        print("❌ 测试结果: 失败")
        print("=" * 80 + "\n")
        print("排查建议:")
        print("1. 检查网络连接是否正常")
        print("2. 确认 API 地址是否正确")
        print("3. 验证客户编码(custcode)和组件编码(componentcode)是否有效")
        print("4. 检查 API 密钥是否正确")
        print("5. 确认模型名称是否存在")
        print("6. 查看服务端日志获取更多信息")
        print("=" * 80 + "\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
