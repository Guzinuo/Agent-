import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(encoding="utf-8")

client = OpenAI(
    api_key=os.getenv("SILICONFLOW_API_KEY"),
    base_url="https://api.siliconflow.cn/v1",
)

resp = client.chat.completions.create(
    model=os.getenv("SILICONFLOW_MODEL", "Qwen/Qwen2.5-72B-Instruct"),
    messages=[
        {"role": "system", "content": "你是一个助手。"},
        {"role": "user", "content": "请只回复：硅基流动API测试成功"}
    ],
    temperature=0.2,
)

print(resp.choices[0].message.content)